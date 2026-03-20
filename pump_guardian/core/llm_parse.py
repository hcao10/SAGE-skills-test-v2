from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional, Tuple

import numpy as np


def try_parse_fft_from_llm_text(text: str) -> Optional[Dict[str, Any]]:
    """
    If the model emitted a JSON/code block with frequencies + amplitudes, parse it.
    Returns dict with frequencies, amplitudes, peak_frequency, peak_amplitude or None.
    """
    if not text:
        return None
    for m in re.finditer(r"```(?:json)?\s*([\s\S]*?)```", text, flags=re.IGNORECASE):
        body = m.group(1).strip()
        try:
            obj = json.loads(body)
        except json.JSONDecodeError:
            continue
        if not isinstance(obj, dict):
            continue
        freqs = obj.get("frequencies") or obj.get("freq") or obj.get("f")
        amps = obj.get("amplitudes") or obj.get("amp") or obj.get("magnitude") or obj.get("a")
        if not isinstance(freqs, list) or not isinstance(amps, list):
            continue
        if len(freqs) < 8 or len(freqs) != len(amps):
            continue
        try:
            fx = [float(x) for x in freqs]
            ay = [float(x) for x in amps]
        except (TypeError, ValueError):
            continue
        peak_i = int(np.argmax(np.asarray(ay)))
        peak_f = float(fx[peak_i])
        peak_a = float(ay[peak_i])
        return {
            "frequencies": fx,
            "amplitudes": ay,
            "peak_frequency": peak_f,
            "peak_amplitude": peak_a,
        }
    return None


def try_parse_workorder_from_llm_text(text: str) -> Optional[str]:
    """Heuristic: treat fenced markdown or obvious WO headings as a work order."""
    if not text or len(text.strip()) < 40:
        return None
    fence = re.search(r"```(?:markdown|md)?\s*([\s\S]*?)```", text, flags=re.IGNORECASE)
    if fence:
        inner = fence.group(1).strip()
        if len(inner) > 40:
            return inner
    markers = (
        "# Maintenance",
        "# 维护",
        "Work Order",
        "维护工单",
        "## Diagnostic",
        "## 诊断",
        "## Equipment",
        "## 设备",
        "Spare Parts",
        "备件",
    )
    if any(m in text for m in markers) and ("##" in text or "#" in text):
        return text.strip()
    return None
