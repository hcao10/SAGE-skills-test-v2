from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd

from core.config import minimax_api_key
from core.i18n import t
from core.minimax_client import chat_completion
from core.skill_loader import (
    discover_skills,
    load_asset_template,
    load_diag_tool,
    load_reference_json,
    load_skill_markdown,
)
from core.trace import AgentTrace
from core.workorder import render_work_order


def _minimax_model() -> str:
    return os.environ.get("MINIMAX_MODEL", "MiniMax-M2.5")


def _has_minimax_key() -> bool:
    return bool(minimax_api_key())


def _general_llm_prompts(
    equipment_id: str,
    *,
    locale: str,
    has_csv_upload: bool,
) -> tuple[str, str]:
    """
    General path uses the same professional persona as the skill-backed advisor, but the
    user message intentionally omits raw samples / tool outputs / standard tables. We do
    not instruct the model that it is “blocked” from tools—fairness comes from what is
    (not) included in the message, not from meta disclaimers in the system prompt.
    """
    if locale == "zh":
        system = (
            "你是工厂设备管理顾问，熟悉旋转机械与现场运维。"
            "请仅依据用户消息中给出的信息作答：给出清晰、可执行的建议。"
            "若关键测量数据或记录未在消息中出现，请明确不确定性，并列出建议补采的数据项与排查步骤；"
            "避免把未经提供的采样结果写成确定数值结论。"
        )
        user_msg = f"设备编号：{equipment_id}。\n"
        if has_csv_upload:
            user_msg += (
                "现场反馈振动偏高，已完成 time/amplitude 振动采样并整理为 CSV。\n"
                "请结合常见工业实践给出初步判断方向、风险定性、以及下一步测试与记录要点。\n"
            )
        else:
            user_msg += (
                "现场反馈振动异常。\n"
                "请结合常见工业实践给出初步判断方向、风险定性、以及下一步测试与记录要点。\n"
            )
        return system, user_msg

    system = (
        "You are an industrial plant equipment advisor with experience in rotating machinery "
        "maintenance. Answer using only the information present in the user message. "
        "If key measurements or records are not included, state uncertainty clearly and list "
        "what to collect next; avoid presenting specific numeric diagnostics as measured facts "
        "when those values were not provided."
    )
    user_msg = f"Equipment ID: {equipment_id}.\n"
    if has_csv_upload:
        user_msg += (
            "Field report: elevated vibration; time/amplitude samples were recorded as a CSV.\n"
            "Using common industrial practice, outline likely directions, qualitative risk framing, "
            "and next diagnostic steps.\n"
        )
    else:
        user_msg += (
            "Field report: abnormal vibration.\n"
            "Using common industrial practice, outline likely directions, qualitative risk framing, "
            "and next diagnostic steps.\n"
        )
    return system, user_msg


def _skill_llm_prompts(
    *,
    locale: str,
    equipment_id: str,
    metrics: Dict[str, Any],
) -> tuple[str, str]:
    if locale == "zh":
        system = (
            "你是工厂设备管理顾问。以下字段来自工业技能流水线（本地脚本 + ISO JSON + 模板），"
            "数据可信。请用 3~6 句中文摘要，语气专业，供厂长快速决策。"
        )
        user_msg = (
            f"设备：{equipment_id}\n"
            f"RMS：{metrics['rms']:.2f} mm/s\n"
            f"主频：{metrics['peak_frequency']:.2f} Hz\n"
            f"故障类型：{metrics['fault_type']}\n"
            f"严重度：{metrics['severity']}（区 {metrics['zone']}）\n"
            f"ISO 依据：{metrics['iso_evidence']}\n"
            f"建议：{metrics['recommendation']}\n"
            f"备件：{metrics['spare_parts']}\n"
        )
        return system, user_msg

    system = (
        "You are an industrial reliability advisor. The following fields were produced by a "
        "skill-enabled pipeline (local scripts + ISO JSON + template) and are trustworthy. "
        "Write a concise 3-6 sentence executive summary for a plant manager."
    )
    user_msg = (
        f"Equipment: {equipment_id}\n"
        f"RMS: {metrics['rms']:.2f} mm/s\n"
        f"Peak frequency: {metrics['peak_frequency']:.2f} Hz\n"
        f"Fault type: {metrics['fault_type']}\n"
        f"Severity: {metrics['severity']} (zone {metrics['zone']})\n"
        f"ISO evidence: {metrics['iso_evidence']}\n"
        f"Recommendation: {metrics['recommendation']}\n"
        f"Spare parts: {metrics['spare_parts']}\n"
    )
    return system, user_msg


def run_general_ai_mode(
    equipment_id: str,
    *,
    locale: str,
    has_csv_upload: bool,
) -> Dict[str, Any]:
    trace = AgentTrace()
    model = _minimax_model()
    od = t("on_demand", locale)

    trace.start(t("stage_general_ai", locale), t("trace_gen_start", locale))

    summary: str
    llm_used = False
    api_error: str | None = None
    system_msg, user_msg = _general_llm_prompts(
        equipment_id, locale=locale, has_csv_upload=has_csv_upload
    )
    messages: List[Dict[str, str]] = [
        {"role": "system", "content": system_msg},
        {"role": "user", "content": user_msg},
    ]

    if not _has_minimax_key():
        trace.done(
            t("stage_llm_inference", locale),
            t("trace_gen_no_key", locale),
        )
        summary = t("fallback_general_body", locale)
    else:
        trace.start(
            t("stage_llm_inference", locale),
            t("trace_gen_llm_call_model", locale).format(model=model),
        )
        try:
            summary = chat_completion(
                messages,
                model=model,
            )
            llm_used = True
            trace.done(t("stage_llm_inference", locale), t("trace_gen_llm_ok", locale))
        except Exception as exc:
            api_error = str(exc)
            trace.error(
                t("stage_llm_inference", locale),
                f"{t('trace_gen_api_fail', locale)} ({exc})",
            )
            summary = t("fallback_general_body", locale)

    trace.done(t("stage_general_ai", locale), t("trace_gen_complete", locale))

    llm_exchanges: List[Dict[str, Any]] = [
        {
            "title": t("llm_exchange_general", locale),
            "model": model,
            "messages": messages,
            "response": summary,
            "api_called": bool(_has_minimax_key()) and (llm_used or api_error is not None),
            "error": api_error,
        }
    ]

    return {
        "mode": "general",
        "summary": summary,
        "llm_used": llm_used,
        "llm_exchanges": llm_exchanges,
        "trace": trace.to_dicts(),
    }


def _classify_with_iso(rms_value: float, iso_ref: dict) -> Dict[str, str]:
    matched = None
    for zone in iso_ref["zones"]:
        if zone["min_inclusive"] <= rms_value < zone["max_exclusive"]:
            matched = zone
            break

    if matched is None:
        matched = iso_ref["zones"][-1]

    return {
        "severity": matched["severity"],
        "zone": matched["zone"],
        "threshold_text": (
            f'{iso_ref["standard"]} ({iso_ref["class"]}): '
            f'{rms_value:.2f} mm/s -> {matched["zone"]} zone'
        ),
        "recommendation": matched["recommendation"],
        "spare_parts": ", ".join(matched["spare_parts"]),
    }


def run_skill_agent_mode(
    equipment_id: str,
    data: pd.DataFrame,
    project_root: Path,
    *,
    locale: str,
) -> Dict[str, Any]:
    trace = AgentTrace()
    skills_root = project_root / "skills"
    od = t("on_demand", locale)

    trace.start(t("stage_skill_discovery", locale), f"{od} {t('trace_scan_registry', locale)}")
    skills = discover_skills(skills_root)
    trace.done(t("stage_skill_discovery", locale), t("trace_found_skills_n", locale).format(n=len(skills)))

    if not skills:
        trace.error(t("stage_skill_discovery", locale), t("trace_no_skill", locale))
        raise RuntimeError("No skills discovered in skills directory.")

    skill_dir = skills_root / "bearing_analyzer"

    trace.start(t("stage_progressive_disclosure", locale), f"{od} {t('trace_load_skill_md', locale)}")
    skill_doc = load_skill_markdown(skill_dir)
    trace.done(
        t("stage_progressive_disclosure", locale),
        t("trace_loaded_skill_chars", locale).format(n=len(skill_doc)),
    )

    trace.start(t("stage_script_execution", locale), f"{od} {t('trace_load_diag_tool', locale)}")
    diag_tool = load_diag_tool(skill_dir)
    trace.done(t("stage_script_execution", locale), t("trace_diag_tool_ready", locale))

    trace.start(t("stage_script_execution", locale), t("trace_running_fft", locale))
    analysis = diag_tool.analyze_signal(data)
    trace.done(
        t("stage_script_execution", locale),
        t("trace_fft_done", locale).format(
            rms=analysis["rms"],
            peak=analysis["peak_frequency"],
        ),
    )

    trace.start(t("stage_reference_retrieval", locale), f"{od} {t('trace_load_iso', locale)}")
    iso_ref = load_reference_json(skill_dir, "ISO_10816.json")
    trace.done(t("stage_reference_retrieval", locale), t("trace_iso_ready", locale))

    classification = _classify_with_iso(analysis["rms"], iso_ref)
    trace.done(
        t("stage_reference_retrieval", locale),
        t("trace_iso_classified", locale).format(
            sev=classification["severity"],
            zone=classification["zone"],
        ),
    )

    trace.start(t("stage_asset_rendering", locale), f"{od} {t('trace_load_template', locale)}")
    template = load_asset_template(skill_dir, "wo_template.md")
    trace.done(t("stage_asset_rendering", locale), t("trace_template_ready", locale))

    payload = {
        "equipment_id": equipment_id,
        "rms": f'{analysis["rms"]:.2f} mm/s',
        "peak_frequency": f'{analysis["peak_frequency"]:.2f} Hz',
        "fault_type": analysis["fault_type"],
        "severity": classification["severity"],
        "zone": classification["zone"],
        "recommendation": classification["recommendation"],
        "spare_parts": classification["spare_parts"],
        "iso_evidence": classification["threshold_text"],
    }
    work_order_md = render_work_order(template, payload)
    trace.done(t("stage_asset_rendering", locale), t("trace_wo_rendered", locale))

    metrics_dict: Dict[str, Any] = {
        "rms": analysis["rms"],
        "peak_frequency": analysis["peak_frequency"],
        "fault_type": analysis["fault_type"],
        "severity": classification["severity"],
        "zone": classification["zone"],
        "iso_evidence": classification["threshold_text"],
        "recommendation": classification["recommendation"],
        "spare_parts": classification["spare_parts"],
    }

    llm_summary = ""
    model = _minimax_model()
    system_msg, user_msg = _skill_llm_prompts(
        locale=locale,
        equipment_id=equipment_id,
        metrics=metrics_dict,
    )
    syn_messages: List[Dict[str, str]] = [
        {"role": "system", "content": system_msg},
        {"role": "user", "content": user_msg},
    ]
    syn_error: str | None = None
    syn_called = False

    if not _has_minimax_key():
        trace.done(t("stage_llm_synthesis", locale), t("trace_llm_syn_skip", locale))
    else:
        trace.start(t("stage_llm_synthesis", locale), t("trace_llm_syn_start", locale))
        try:
            llm_summary = chat_completion(
                syn_messages,
                model=model,
            )
            syn_called = True
            trace.done(t("stage_llm_synthesis", locale), t("trace_llm_syn_ok", locale))
        except Exception as exc:
            syn_error = str(exc)
            trace.error(
                t("stage_llm_synthesis", locale),
                f"{t('trace_llm_syn_fail', locale)} ({exc})",
            )
            llm_summary = ""

    llm_exchanges: List[Dict[str, Any]] = [
        {
            "title": t("llm_exchange_skill_summary", locale),
            "model": model,
            "messages": syn_messages,
            "response": llm_summary,
            "api_called": bool(_has_minimax_key()) and (syn_called or syn_error is not None),
            "error": syn_error,
        }
    ]

    return {
        "mode": "skill",
        "metrics": metrics_dict,
        "fft": {
            "frequencies": analysis["frequencies"],
            "amplitudes": analysis["amplitudes"],
            "peak_frequency": analysis["peak_frequency"],
            "peak_amplitude": analysis["peak_amplitude"],
        },
        "work_order_md": work_order_md,
        "llm_summary": llm_summary,
        "llm_exchanges": llm_exchanges,
        "trace": trace.to_dicts(),
    }
