from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict

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
    if locale == "zh":
        system = (
            "你是通用助手，无法使用振动分析工具、FFT、ISO 10816 标准库或工单系统。"
            "不要编造任何 RMS、主频、ISO 分区或具体测量值。"
        )
        user_msg = f"设备编号：{equipment_id}。\n"
        if has_csv_upload:
            user_msg += "用户声称上传了振动 CSV，但你无法读取其中的数值序列。\n"
        else:
            user_msg += "当前为演示场景，用户未上传文件。\n"
        user_msg += "请用 2~4 句中文给出非常笼统的设备维护建议，避免结构化字段与具体指标。"
        return system, user_msg

    system = (
        "You are a generic assistant without vibration tools, FFT, ISO 10816 reference data, "
        "or CMMS. Do not invent RMS, peak frequency, ISO zones, or any numeric measurements."
    )
    user_msg = f"Equipment ID: {equipment_id}.\n"
    if has_csv_upload:
        user_msg += "The user says they uploaded a vibration CSV, but you cannot see numeric samples.\n"
    else:
        user_msg += "Demo scenario: no file was uploaded.\n"
    user_msg += (
        "Reply in 2-4 short sentences with vague maintenance guidance only. "
        "No structured fields, no standards citations."
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
            "数据可信。请写 3~5 句中文摘要，语气专业，供厂长快速决策。"
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
        "Write a concise 3-5 sentence executive summary for a plant manager."
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

    trace.start(t("stage_general_ai", locale), t("trace_gen_start", locale))

    summary: str
    llm_used = False

    if not _has_minimax_key():
        trace.done(
            t("stage_llm_inference", locale),
            t("trace_gen_no_key", locale),
        )
        summary = t("fallback_general_body", locale)
    else:
        trace.start(
            t("stage_llm_inference", locale),
            t("trace_gen_llm_call", locale),
        )
        system_msg, user_msg = _general_llm_prompts(
            equipment_id, locale=locale, has_csv_upload=has_csv_upload
        )
        try:
            summary = chat_completion(
                [
                    {"role": "system", "content": system_msg},
                    {"role": "user", "content": user_msg},
                ],
                model=model,
            )
            llm_used = True
            trace.done(t("stage_llm_inference", locale), t("trace_gen_llm_ok", locale))
        except Exception as exc:
            trace.error(
                t("stage_llm_inference", locale),
                f"{t('trace_gen_api_fail', locale)} ({exc})",
            )
            summary = t("fallback_general_body", locale)

    trace.done(t("stage_general_ai", locale), t("trace_gen_complete", locale))

    return {
        "mode": "general",
        "summary": summary,
        "llm_used": llm_used,
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

    trace.start(t("stage_skill_discovery", locale), f"{od} Scanning skill registry metadata...")
    skills = discover_skills(skills_root)
    trace.done(t("stage_skill_discovery", locale), f"Found {len(skills)} skill(s).")

    if not skills:
        trace.error(t("stage_skill_discovery", locale), "No skill available.")
        raise RuntimeError("No skills discovered in skills directory.")

    skill_dir = skills_root / "bearing_analyzer"

    trace.start(t("stage_progressive_disclosure", locale), f"{od} Loading SKILL.md...")
    skill_doc = load_skill_markdown(skill_dir)
    trace.done(
        t("stage_progressive_disclosure", locale),
        f"{od} Loaded skill doc ({len(skill_doc)} chars).",
    )

    trace.start(t("stage_script_execution", locale), f"{od} Loading diag_tool.py...")
    diag_tool = load_diag_tool(skill_dir)
    trace.done(t("stage_script_execution", locale), f"{od} Diagnostic module loaded.")

    trace.start(t("stage_script_execution", locale), "Running RMS + FFT analysis locally...")
    analysis = diag_tool.analyze_signal(data)
    trace.done(
        t("stage_script_execution", locale),
        f'Computed RMS={analysis["rms"]:.2f} mm/s, peak={analysis["peak_frequency"]:.2f} Hz.',
    )

    trace.start(t("stage_reference_retrieval", locale), f"{od} Loading ISO_10816.json...")
    iso_ref = load_reference_json(skill_dir, "ISO_10816.json")
    trace.done(t("stage_reference_retrieval", locale), f"{od} ISO thresholds loaded.")

    classification = _classify_with_iso(analysis["rms"], iso_ref)
    trace.done(
        t("stage_reference_retrieval", locale),
        f'Classified as {classification["severity"]} in {classification["zone"]} zone.',
    )

    trace.start(t("stage_asset_rendering", locale), f"{od} Loading wo_template.md...")
    template = load_asset_template(skill_dir, "wo_template.md")
    trace.done(t("stage_asset_rendering", locale), f"{od} Template loaded.")

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
    trace.done(t("stage_asset_rendering", locale), "Work order rendered.")

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
    if not _has_minimax_key():
        trace.done(t("stage_llm_synthesis", locale), t("trace_llm_syn_skip", locale))
    else:
        trace.start(t("stage_llm_synthesis", locale), t("trace_llm_syn_start", locale))
        system_msg, user_msg = _skill_llm_prompts(
            locale=locale,
            equipment_id=equipment_id,
            metrics=metrics_dict,
        )
        try:
            llm_summary = chat_completion(
                [
                    {"role": "system", "content": system_msg},
                    {"role": "user", "content": user_msg},
                ],
                model=model,
            )
            trace.done(t("stage_llm_synthesis", locale), t("trace_llm_syn_ok", locale))
        except Exception as exc:
            trace.error(
                t("stage_llm_synthesis", locale),
                f"{t('trace_llm_syn_fail', locale)} ({exc})",
            )
            llm_summary = ""

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
        "trace": trace.to_dicts(),
    }
