"""进度、指标、日志与生命周期事件。"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime
from typing import Any, ClassVar

from ser_lib.foundation.events.base import (
    EventContext,
    _json_safe,
    _next_event_sequence,
    _timestamp_to_iso,
    _utc_now,
)

_LIFECYCLE_STATUSES = frozenset({
    "started",
    "phase_started",
    "phase_completed",
    "completed",
    "cancelled",
    "failed",
    "early_stopped",
})


@dataclass(frozen=True, slots=True)
class ProgressEvent:
    stage: str
    completed: int
    total: int | None = None
    message: str = ""
    timestamp: datetime = field(default_factory=_utc_now)
    context: EventContext = field(default_factory=EventContext)
    sequence: int = field(default_factory=_next_event_sequence)
    details: dict[str, Any] = field(default_factory=dict)

    event_type: ClassVar[str] = "progress"

    def __post_init__(self) -> None:
        if not self.stage:
            raise ValueError("ProgressEvent.stage 不能为空")
        if self.completed < 0 or (self.total is not None and self.total < 0):
            raise ValueError("completed/total 不能为负数")
        if self.total is not None and self.completed > self.total:
            raise ValueError("completed 不能大于 total")
        if self.sequence <= 0:
            raise ValueError("sequence 必须为正整数")

    @property
    def fraction(self) -> float | None:
        if self.total is None or self.total == 0:
            return None
        return self.completed / self.total

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_type": self.event_type,
            "sequence": self.sequence,
            "stage": self.stage,
            "timestamp": _timestamp_to_iso(self.timestamp),
            "context": self.context.to_dict(),
            "completed": self.completed,
            "total": self.total,
            "message": self.message,
            "details": _json_safe(self.details),
        }


@dataclass(frozen=True, slots=True)
class MetricEvent:
    name: str
    value: float
    step: int | None = None
    split: str | None = None
    timestamp: datetime = field(default_factory=_utc_now)
    context: EventContext = field(default_factory=EventContext)
    sequence: int = field(default_factory=_next_event_sequence)

    event_type: ClassVar[str] = "metric"

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("MetricEvent.name 不能为空")
        if self.sequence <= 0:
            raise ValueError("sequence 必须为正整数")
        if self.split is not None:
            if self.context.split is None:
                object.__setattr__(self, "context", replace(self.context, split=self.split))
            elif self.context.split != self.split:
                raise ValueError("MetricEvent.split 与 context.split 不一致")

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_type": self.event_type,
            "sequence": self.sequence,
            "name": self.name,
            "value": _json_safe(self.value),
            "step": self.step,
            "split": self.split,
            "timestamp": _timestamp_to_iso(self.timestamp),
            "context": self.context.to_dict(),
        }


@dataclass(frozen=True, slots=True)
class LogEvent:
    level: str
    message: str
    stage: str | None = None
    details: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=_utc_now)
    context: EventContext = field(default_factory=EventContext)
    sequence: int = field(default_factory=_next_event_sequence)

    event_type: ClassVar[str] = "log"

    def __post_init__(self) -> None:
        if not self.level:
            raise ValueError("LogEvent.level 不能为空")
        if not self.message:
            raise ValueError("LogEvent.message 不能为空")
        if self.sequence <= 0:
            raise ValueError("sequence 必须为正整数")

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_type": self.event_type,
            "sequence": self.sequence,
            "level": self.level,
            "message": self.message,
            "stage": self.stage,
            "timestamp": _timestamp_to_iso(self.timestamp),
            "context": self.context.to_dict(),
            "details": _json_safe(self.details),
        }


@dataclass(frozen=True, slots=True)
class LifecycleEvent:
    """描述长任务或其阶段的生命周期变化。"""

    stage: str
    status: str
    message: str = ""
    details: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=_utc_now)
    context: EventContext = field(default_factory=EventContext)
    sequence: int = field(default_factory=_next_event_sequence)

    event_type: ClassVar[str] = "lifecycle"

    def __post_init__(self) -> None:
        if not self.stage:
            raise ValueError("LifecycleEvent.stage 不能为空")
        if self.status not in _LIFECYCLE_STATUSES:
            allowed = ", ".join(sorted(_LIFECYCLE_STATUSES))
            raise ValueError(f"LifecycleEvent.status 非法: {self.status!r}; 支持: {allowed}")
        if self.sequence <= 0:
            raise ValueError("sequence 必须为正整数")

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_type": self.event_type,
            "sequence": self.sequence,
            "stage": self.stage,
            "status": self.status,
            "timestamp": _timestamp_to_iso(self.timestamp),
            "context": self.context.to_dict(),
            "message": self.message,
            "details": _json_safe(self.details),
        }


__all__ = ["ProgressEvent", "MetricEvent", "LogEvent", "LifecycleEvent"]
