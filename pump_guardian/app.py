from __future__ import annotations

import json
import os
import time
from io import StringIO
from pathlib import Path
from typing import Any, Dict, List, Tuple

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from core.config import (
    config_diagnostics,
    iter_config_check_paths,
    load_minimax_config_files,
    merge_streamlit_secrets_into_environ,
    minimax_api_key,
)
from core.i18n import t
from core.llm_parse import try_parse_fft_from_llm_text, try_parse_workorder_from_llm_text
from core.router import run_general_ai_mode, run_skill_agent_mode
from data.generator import generate_synthetic_vibration

_APP_DIR = Path(__file__).resolve().parent
load_minimax_config_files(_APP_DIR)
SAMPLE_CSV = _APP_DIR / "data" / "samples" / "bearing_fault_81hz_demo.csv"


def _load_skill_playbook(locale: str) -> str:
    name = "skill_playbook_zh.md" if locale == "zh" else "skill_playbook_en.md"
    path = _APP_DIR / "docs" / name
    if path.is_file():
        return path.read_text(encoding="utf-8")
    return ""


def _style_app(page_title: str) -> None:
    st.set_page_config(page_title=page_title, layout="wide")
    st.markdown(
        """
        <style>
        .main-title {font-size: 2.0rem; font-weight: 700; margin-bottom: 0.1rem;}
        .subtitle {color: #6b7280; margin-bottom: 1rem;}
        .trace-line {font-family: Consolas, monospace; font-size: 0.86rem; margin-bottom: 6px;}
        .status-running {color: #f59e0b; font-weight: 600;}
        .status-done {color: #10b981; font-weight: 600;}
        .status-error {color: #ef4444; font-weight: 600;}
        .evidence-box {
            border: 1px solid #334155;
            border-radius: 8px;
            padding: 10px;
            background: #0f172a;
            color: #e2e8f0;
        }
        .danger-zone {background: #7f1d1d; color: #fecaca; font-weight: 700; padding: 2px 6px; border-radius: 4px;}
        </style>
        """,
        unsafe_allow_html=True,
    )


def _load_input_data(uploaded_file, use_harmonic: bool, noise_level: float) -> pd.DataFrame:
    if uploaded_file is not None:
        content = uploaded_file.getvalue().decode("utf-8")
        data = pd.read_csv(StringIO(content))
        expected_cols = {"time", "amplitude"}
        if not expected_cols.issubset(data.columns):
            missing = expected_cols.difference(set(data.columns))
            raise ValueError(f"CSV missing columns: {', '.join(sorted(missing))}")
        return data

    return generate_synthetic_vibration(
        base_fault_hz=81.0,
        base_amplitude=6.8,
        noise_level=noise_level,
        harmonic_enabled=use_harmonic,
    )


def _render_trace(trace_events: List[Dict[str, str]], trace_placeholder) -> None:
    rendered_lines: List[str] = []
    for event in trace_events:
        status_cls = f'status-{event["status"]}'
        rendered_lines.append(
            (
                '<div class="trace-line">'
                f'[{event["timestamp"]}] '
                f'<span class="{status_cls}">{event["status"].upper()}</span> '
                f'- <strong>{event["stage"]}</strong>: {event["message"]}'
                "</div>"
            )
        )
        trace_placeholder.markdown("".join(rendered_lines), unsafe_allow_html=True)
        time.sleep(0.35)


def _fft_figure(
    freqs: List[float],
    amps: List[float],
    peak_f: float,
    peak_a: float,
    locale: str,
) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=freqs,
            y=amps,
            mode="lines",
            name="Spectrum",
            line=dict(color="#3b82f6", width=2),
        )
    )
    fig.add_trace(
        go.Scatter(
            x=[peak_f],
            y=[peak_a],
            mode="markers+text",
            text=[f'{t("peak_label", locale)} {peak_f:.2f} Hz'],
            textposition="top center",
            marker=dict(size=11, color="#ef4444"),
            name=t("peak_label", locale),
        )
    )
    fig.update_layout(
        title=t("fft_title", locale),
        xaxis_title=t("fft_x", locale),
        yaxis_title=t("fft_y", locale),
        template="plotly_white",
        height=420,
        margin=dict(l=20, r=20, t=50, b=20),
    )
    return fig


def _render_llm_content(result: dict, locale: str) -> None:
    exchanges: List[Dict[str, Any]] = result.get("llm_exchanges") or []
    if not exchanges:
        st.caption("—")
        return
    for ex in exchanges:
        st.markdown(f"#### {ex.get('title', 'LLM')}")
        st.caption(f"{t('llm_model_label', locale)} `{ex.get('model', '')}`")
        messages = ex.get("messages") or []
        with st.expander(t("llm_request_json", locale), expanded=False):
            st.code(json.dumps(messages, ensure_ascii=False, indent=2), language="json")
        system_msgs = [m for m in messages if m.get("role") == "system"]
        other_msgs = [m for m in messages if m.get("role") != "system"]
        if system_msgs:
            with st.expander(t("llm_role_system", locale), expanded=False):
                st.markdown(system_msgs[0].get("content", ""))
        for m in other_msgs:
            role = m.get("role", "user")
            if role not in ("user", "assistant"):
                role = "user"
            with st.chat_message(role):
                st.markdown(m.get("content", ""))
        with st.chat_message("assistant"):
            if ex.get("error"):
                st.error(str(ex["error"]))
            if not ex.get("api_called"):
                st.caption(t("llm_not_called", locale))
            resp = (ex.get("response") or "").strip()
            if resp:
                st.markdown(resp)
            elif not ex.get("error"):
                st.caption("—")
        st.divider()


def _render_general_mode(center_tabs: Tuple, result: dict, locale: str) -> None:
    tab_summary, tab_fft, tab_wo = center_tabs
    summary_text = result.get("summary") or ""
    parsed_fft = try_parse_fft_from_llm_text(summary_text)
    parsed_wo = try_parse_workorder_from_llm_text(summary_text)

    with tab_summary:
        st.info(t("general_banner", locale))
        if not minimax_api_key():
            st.warning(t("no_api_key", locale))
        st.markdown(f"### {t('llm_summary', locale)}")
        st.markdown(summary_text)

    with tab_fft:
        if parsed_fft:
            st.success(t("general_fft_from_llm", locale))
            fig = _fft_figure(
                freqs=parsed_fft["frequencies"],
                amps=parsed_fft["amplitudes"],
                peak_f=parsed_fft["peak_frequency"],
                peak_a=parsed_fft["peak_amplitude"],
                locale=locale,
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.warning(t("general_fft_none", locale))

    with tab_wo:
        if parsed_wo:
            st.success(t("general_wo_from_llm", locale))
            st.markdown(parsed_wo)
        else:
            st.warning(t("general_wo_none", locale))


def _render_skill_mode(center_tabs: Tuple, result: dict, equipment_id: str, locale: str) -> None:
    tab_summary, tab_fft, tab_wo = center_tabs
    metrics = result["metrics"]

    with tab_summary:
        c1, c2, c3 = st.columns(3)
        c1.metric("RMS (mm/s)", f'{metrics["rms"]:.2f}')
        c2.metric("Peak (Hz)", f'{metrics["peak_frequency"]:.2f}')
        c3.metric("Severity", metrics["severity"])

        st.success(f"{t('fault_type', locale)}: {metrics['fault_type']}")
        severity_zone = metrics["zone"]
        zone_html = (
            f"<span class='danger-zone'>{severity_zone}</span>" if severity_zone == "D" else severity_zone
        )
        st.markdown(
            (
                "<div class='evidence-box'>"
                f"<strong>{t('iso_evidence_title', locale)}</strong><br/>"
                f"{metrics['iso_evidence']} "
                f"-> {t('matched_zone', locale)} {zone_html}"
                "</div>"
            ),
            unsafe_allow_html=True,
        )
        st.write(f"{t('recommendation', locale)}: {metrics['recommendation']}")
        st.write(f"{t('spare_parts', locale)}: {metrics['spare_parts']}")

    with tab_fft:
        fig = _fft_figure(
            freqs=result["fft"]["frequencies"],
            amps=result["fft"]["amplitudes"],
            peak_f=result["fft"]["peak_frequency"],
            peak_a=result["fft"]["peak_amplitude"],
            locale=locale,
        )
        st.plotly_chart(fig, use_container_width=True)

    with tab_wo:
        st.markdown(result["work_order_md"])
        st.download_button(
            label=t("download_wo", locale),
            data=result["work_order_md"],
            file_name=f"work_order_{equipment_id}.md",
            mime="text/markdown",
        )


def main() -> None:
    try:
        merge_streamlit_secrets_into_environ(st.secrets)
    except Exception:
        pass

    with st.sidebar:
        lang_choice = st.selectbox(
            "语言 / Language",
            options=["中文", "English"],
            index=0,
            key="pg_ui_language",
        )
        locale = "zh" if lang_choice == "中文" else "en"

        st.markdown(f"**{t('api_settings_title', locale)}**")
        st.caption(t("api_sidebar_hint", locale))
        session_key = st.text_input(
            t("api_session_key", locale),
            type="password",
            key="pg_api_session_key",
            help=t("api_session_help", locale),
        )
        if session_key.strip():
            os.environ["MINIMAX_API_KEY"] = session_key.strip()

        with st.expander(t("config_files_title", locale), expanded=False):
            lines = []
            for label, p in iter_config_check_paths(_APP_DIR):
                try:
                    ok = p.resolve().is_file()
                except OSError:
                    ok = False
                mark = "OK" if ok else "—"
                lines.append(f"[{mark}] {label}\n    {p}")
            st.code("\n".join(lines), language="text")

        if st.checkbox(t("api_show_key_status", locale), key="pg_api_show_key_status"):
            st.write(
                t("api_status_ok", locale)
                if minimax_api_key()
                else t("api_status_missing", locale)
            )
            with st.expander(t("api_diagnostics", locale)):
                st.code("\n".join(config_diagnostics(_APP_DIR)), language="text")

    st.session_state.setdefault("pumpguardian_mode", "skill")
    page_title = t("page_title", locale)
    _style_app(page_title)

    st.markdown(f"<div class='main-title'>{page_title}</div>", unsafe_allow_html=True)
    st.markdown(f"<div class='subtitle'>{t('subtitle', locale)}</div>", unsafe_allow_html=True)

    left_col, center_col, llm_col, right_col = st.columns([1.0, 1.35, 1.15, 1.05], gap="medium")

    with llm_col:
        st.subheader(t("llm_io_title", locale))
        llm_area = st.container()

    with left_col:
        st.subheader(t("input_mode", locale))
        equipment_id = st.text_input(t("equipment_id", locale), value="PUMP-07B")

        mode_internal = st.radio(
            t("select_mode", locale),
            options=["general", "skill"],
            horizontal=True,
            format_func=lambda v: t("mode_general", locale) if v == "general" else t("mode_skill", locale),
            key="pumpguardian_mode",
        )

        uploaded_file = st.file_uploader(t("upload_csv", locale), type=["csv"])
        st.caption(t("csv_caption", locale))

        st.markdown(f"#### {t('sample_csv_title', locale)}")
        st.caption(t("sample_csv_hint", locale))
        if SAMPLE_CSV.is_file():
            st.download_button(
                t("sample_csv_download", locale),
                data=SAMPLE_CSV.read_bytes(),
                file_name=SAMPLE_CSV.name,
                mime="text/csv",
                key="pg_dl_sample_csv",
            )

        st.markdown(f"#### {t('demo_signal', locale)}")
        use_harmonic = st.checkbox(t("harmonic", locale), value=True)
        noise_level = st.slider(t("noise_level", locale), 0.1, 2.0, 0.8, 0.1)

        run_clicked = st.button(t("run", locale), type="primary", use_container_width=True)

    with center_col:
        st.subheader(t("analysis_output", locale))
        tabs = st.tabs(
            [
                t("tab_summary", locale),
                t("tab_fft", locale),
                t("tab_workorder", locale),
            ]
        )

    with right_col:
        st.subheader(t("agent_trace", locale))
        trace_placeholder = st.empty()
        trace_placeholder.info(t("trace_waiting", locale))

        with st.expander(t("skill_playbook_expander", locale), expanded=False):
            body = _load_skill_playbook(locale)
            if body.strip():
                st.markdown(body)
            else:
                st.caption("—")

    if not run_clicked:
        with llm_area:
            st.caption(t("llm_io_placeholder", locale))
        return

    project_root = Path(__file__).resolve().parent
    has_csv_upload = uploaded_file is not None

    trace_placeholder.success(t("diagnosis_started", locale))
    time.sleep(0.25)

    try:
        if mode_internal == "general":
            result = run_general_ai_mode(
                equipment_id,
                locale=locale,
                has_csv_upload=has_csv_upload,
            )
            _render_trace(result["trace"], trace_placeholder)
            _render_general_mode(tabs, result, locale)
            with llm_area:
                _render_llm_content(result, locale)
            return

        data = _load_input_data(uploaded_file, use_harmonic, noise_level)
        result = run_skill_agent_mode(
            equipment_id=equipment_id,
            data=data,
            project_root=project_root,
            locale=locale,
        )
        _render_trace(result["trace"], trace_placeholder)
        _render_skill_mode(tabs, result, equipment_id, locale)
        with llm_area:
            _render_llm_content(result, locale)
    except Exception as exc:
        st.error(f"{t('exec_failed', locale)}: {exc}")


if __name__ == "__main__":
    main()
