from __future__ import annotations

from datetime import datetime
from typing import Dict


def render_work_order(template: str, payload: Dict[str, str]) -> str:
    merged_payload = {
        **payload,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    return template.format(**merged_payload)
