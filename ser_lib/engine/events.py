"""训练/Checkpoint 领域事件。"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, ClassVar

from ser_lib.foundation.events import (
    EVENT_SCHEMA_VERSION,
    EventContext,
    _json_safe,
    _next_event_sequence,
    _timestamp_to_iso,
    _utc_now,
)

_CHECKPOINT_ACTIONS = frozenset({
    "started",
    "saved",
    "failed",
    "best_model_updated",
})


@dataclass(frozen=True, slots=True)
class CheckpointEvent:
    """描述 checkpoint 保存生命周期。"""

    action: str
    kind: str
    path: str | Path
    epoch: int
    metric_name: str | None = None
    metric_value: float | None = None
    message: str = ""
    details: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=_utc_now)
    context: EventContext = field(default_factory=EventContext)
    sequence: int = field(default_factory=_next_event_sequence)

    schema_version: ClassVar[int] = EVENT_SCHEMA_VERSION
    event_type: ClassVar[str] = "checkpoint"

    def __post_init__(self) -> None:
        if self.action not in _CHECKPOINT_ACTIONS:
            allowed = ", ".join(sorted(_CHECKPOINT_ACTIONS))
            raise ValueError(f"CheckpointEvent.action 非法: {self.action!r}; 支持: {allowed}")
        if not self.kind:
            raise ValueError("CheckpointEvent.kind 不能为空")
        if not str(self.path):
            raise ValueError("CheckpointEvent.path 不能为空")
        if self.epoch < 0:
            raise ValueError("CheckpointEvent.epoch 不能为负数")
        if self.sequence <= 0:
            raise ValueError("sequence 必须为正整数")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "event_type": self.event_type,
            "sequence": self.sequence,
            "action": self.action,
            "kind": self.kind,
            "path": _json_safe(self.path),
            "epoch": self.epoch,
            "metric_name": self.metric_name,
            "metric_value": _json_safe(self.metric_value),
            "timestamp": _timestamp_to_iso(self.timestamp),
            "context": self.context.to_dict(),
            "message": self.message,
            "details": _json_safe(self.details),
        }


__all__ = ["CheckpointEvent"]
