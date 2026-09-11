"""事件共享协议、序列化 helper 与取消令牌。"""

from __future__ import annotations

import itertools
import math
import threading
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Protocol

from ser_lib.foundation.errors import OperationCancelled

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


class EventLike(Protocol):
    """所有可由事件 callback 消费的只读结构化事件协议。"""

    @property
    def sequence(self) -> int: ...

    def to_dict(self) -> dict[str, Any]: ...


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
    "EventContext",
    "EventLike",
    "EventCallback",
    "CancellationCheck",
    "CancellationToken",
]
