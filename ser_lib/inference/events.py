"""推理领域事件。"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, ClassVar

from ser_lib.foundation.events import (
    EventContext,
    _json_safe,
    _next_event_sequence,
    _timestamp_to_iso,
    _utc_now,
)


@dataclass(frozen=True, slots=True)
class PredictionEvent:
    """单条推理结果事件。"""

    uid: str
    emotion: str
    confidence: float
    label_id: int | None = None
    probabilities: tuple[float, ...] = ()
    details: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=_utc_now)
    context: EventContext = field(default_factory=EventContext)
    sequence: int = field(default_factory=_next_event_sequence)

    event_type: ClassVar[str] = "prediction"

    def __post_init__(self) -> None:
        if not self.uid:
            raise ValueError("PredictionEvent.uid 不能为空")
        if not self.emotion:
            raise ValueError("PredictionEvent.emotion 不能为空")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("PredictionEvent.confidence 必须位于 [0, 1]")
        if self.label_id is not None and self.label_id < 0:
            raise ValueError("PredictionEvent.label_id 不能为负数")
        if any(value < 0.0 or value > 1.0 for value in self.probabilities):
            raise ValueError("PredictionEvent.probabilities 必须位于 [0, 1]")
        if self.sequence <= 0:
            raise ValueError("sequence 必须为正整数")

    def to_dict(self) -> dict[str, Any]:
        return {

            "event_type": self.event_type,
            "sequence": self.sequence,
            "uid": self.uid,
            "emotion": self.emotion,
            "confidence": self.confidence,
            "label_id": self.label_id,
            "probabilities": list(self.probabilities),
            "timestamp": _timestamp_to_iso(self.timestamp),
            "context": self.context.to_dict(),
            "details": _json_safe(self.details),
        }


__all__ = ["PredictionEvent"]
