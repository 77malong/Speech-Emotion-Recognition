"""跨领域共享的进度、指标、日志、生命周期和取消协议。"""

from __future__ import annotations

import itertools
import math
import threading
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, ClassVar, Protocol

from ser_lib.foundation.errors import OperationCancelled

EVENT_SCHEMA_VERSION = 2
_LIFECYCLE_STATUSES = frozenset({
    "started",
    "phase_started",
    "phase_completed",
    "completed",
    "cancelled",
    "failed",
    "early_stopped",
})
_SEQUENCE_COUNTER = itertools.count(1)
_SEQUENCE_LOCK = threading.Lock()


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _next_event_sequence() -> int:
    with _SEQUENCE_LOCK:
        return next(_SEQUENCE_COUNTER)


def _timestamp_to_iso(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat()


def _json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, bool)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("事件字段包含非有限浮点值，无法序列化为严格 JSON")
        return value
    if isinstance(value, datetime):
        return _timestamp_to_iso(value)
    if isinstance(value, Path):
        return value.as_posix()
    if isinstance(value, Enum):
        return _json_safe(value.value)
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [_json_safe(item) for item in value]
    raise TypeError(f"事件字段包含不可 JSON 序列化的类型: {type(value).__name__}")


@dataclass(frozen=True, slots=True)
class EventContext:
    """跨事件共享的运行上下文。"""

    run_id: str | None = None
    epoch: int | None = None
    total_epochs: int | None = None
    batch: int | None = None
    total_batches: int | None = None
    global_step: int | None = None
    split: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "epoch": self.epoch,
            "total_epochs": self.total_epochs,
            "batch": self.batch,
            "total_batches": self.total_batches,
            "global_step": self.global_step,
            "split": self.split,
        }


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

    schema_version: ClassVar[int] = EVENT_SCHEMA_VERSION
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
            "schema_version": self.schema_version,
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

    schema_version: ClassVar[int] = EVENT_SCHEMA_VERSION
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
            "schema_version": self.schema_version,
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

    schema_version: ClassVar[int] = EVENT_SCHEMA_VERSION
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
            "schema_version": self.schema_version,
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

    schema_version: ClassVar[int] = EVENT_SCHEMA_VERSION
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
            "schema_version": self.schema_version,
            "event_type": self.event_type,
            "sequence": self.sequence,
            "stage": self.stage,
            "status": self.status,
            "timestamp": _timestamp_to_iso(self.timestamp),
            "context": self.context.to_dict(),
            "message": self.message,
            "details": _json_safe(self.details),
        }


class EventLike(Protocol):
    """所有可由事件 callback 消费的只读结构化事件协议。"""

    @property
    def sequence(self) -> int: ...

    def to_dict(self) -> dict[str, Any]: ...


LibraryEvent = ProgressEvent | MetricEvent | LogEvent | LifecycleEvent
EventCallback = Callable[[EventLike], None]


class CancellationCheck(Protocol):
    """长操作只依赖此协议，不依赖具体调度器。"""

    @property
    def is_cancelled(self) -> bool: ...

    def raise_if_cancelled(self) -> None: ...


class CancellationToken:
    """可在线程间安全共享的协作式取消令牌。"""

    def __init__(self) -> None:
        self._event = threading.Event()

    @property
    def is_cancelled(self) -> bool:
        return self._event.is_set()

    def cancel(self) -> None:
        self._event.set()

    def raise_if_cancelled(self) -> None:
        if self.is_cancelled:
            raise OperationCancelled("操作已取消")


__all__ = [
    "EVENT_SCHEMA_VERSION",
    "EventContext",
    "ProgressEvent",
    "MetricEvent",
    "LogEvent",
    "LifecycleEvent",
    "EventLike",
    "LibraryEvent",
    "EventCallback",
    "CancellationCheck",
    "CancellationToken",
]
