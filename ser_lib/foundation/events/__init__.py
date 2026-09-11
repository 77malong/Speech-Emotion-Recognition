"""SER-lib 的结构化事件与取消协议。"""

from ser_lib.foundation.events.base import (
    CancellationCheck,
    CancellationToken,
    EventCallback,
    EventContext,
    EventLike,
)
from ser_lib.foundation.events.inference import PredictionEvent
from ser_lib.foundation.events.lifecycle import (
    LifecycleEvent,
    LogEvent,
    MetricEvent,
    ProgressEvent,
)
from ser_lib.foundation.events.training import CheckpointEvent

LibraryEvent = ProgressEvent | MetricEvent | LogEvent | LifecycleEvent

__all__ = [
    "EventContext",
    "ProgressEvent",
    "MetricEvent",
    "LogEvent",
    "LifecycleEvent",
    "CheckpointEvent",
    "PredictionEvent",
    "EventLike",
    "LibraryEvent",
    "EventCallback",
    "CancellationCheck",
    "CancellationToken",
]
