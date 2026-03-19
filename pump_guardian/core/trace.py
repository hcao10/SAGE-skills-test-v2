from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import List


@dataclass
class TraceEvent:
    stage: str
    message: str
    status: str
    timestamp: str = field(default_factory=lambda: datetime.now().strftime("%H:%M:%S"))


class AgentTrace:
    """Stores trace events for white-box agent visualization."""

    def __init__(self) -> None:
        self.events: List[TraceEvent] = []

    def start(self, stage: str, message: str) -> None:
        self.events.append(TraceEvent(stage=stage, message=message, status="running"))

    def done(self, stage: str, message: str) -> None:
        self.events.append(TraceEvent(stage=stage, message=message, status="done"))

    def error(self, stage: str, message: str) -> None:
        self.events.append(TraceEvent(stage=stage, message=message, status="error"))

    def to_dicts(self) -> List[dict]:
        return [
            {
                "stage": event.stage,
                "message": event.message,
                "status": event.status,
                "timestamp": event.timestamp,
            }
            for event in self.events
        ]
