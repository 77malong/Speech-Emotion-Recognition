"""兼容入口：通用事件已迁移到 foundation，领域事件已回归所属领域。

该 shim 保留 0.2.x 旧导入路径，并计划在 Stage 05 删除。
"""

from __future__ import annotations

import importlib
from typing import Any

from ser_lib.foundation.events import (
    EVENT_SCHEMA_VERSION,
    CancellationCheck,
    CancellationToken,
    EventCallback,
    EventContext,
    EventLike,
    LifecycleEvent,
    LogEvent,
    MetricEvent,
    ProgressEvent,
)

# 旧 core.LibraryEvent 作为结构化事件协议保留，使领域事件无需让
# foundation 反向 import engine/inference 即可继续被旧 callback 注解接受。
LibraryEvent = EventLike

# Annotation-only 声明让静态工具识别惰性导出；运行时没有创建绑定，
# 所以 getattr/import 仍会进入 __getattr__，不会提前加载领域包。
CheckpointEvent: Any
PredictionEvent: Any


def __getattr__(name: str) -> Any:
    if name == "CheckpointEvent":
        value = getattr(importlib.import_module("ser_lib.engine.events"), name)
    elif name == "PredictionEvent":
        value = getattr(importlib.import_module("ser_lib.inference.events"), name)
    else:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    globals()[name] = value
    return value


__all__ = [
    "EVENT_SCHEMA_VERSION",
    "EventContext",
    "ProgressEvent",
    "MetricEvent",
    "LogEvent",
    "LifecycleEvent",
    "CheckpointEvent",
    "PredictionEvent",
    "LibraryEvent",
    "EventCallback",
    "CancellationCheck",
    "CancellationToken",
]
