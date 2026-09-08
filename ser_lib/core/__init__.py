"""SER 基础库的轻量公共基础设施。"""

from ser_lib.core.config import (
    StrictConfig,
    load_versioned_config,
    load_yaml_mapping,
    require_schema_version,
    resolve_config_path,
)
from ser_lib.core.diagnostics import Diagnostic, DiagnosticSeverity
from ser_lib.core.events import (
    EVENT_SCHEMA_VERSION,
    CancellationCheck,
    CancellationToken,
    CheckpointEvent,
    EventCallback,
    EventContext,
    LibraryEvent,
    LifecycleEvent,
    LogEvent,
    MetricEvent,
    ProgressEvent,
)
from ser_lib.core.exceptions import ConfigurationError, OperationCancelled, SERError
from ser_lib.core.logging import configure_library_logging, get_logger

__all__ = [
    "SERError", "ConfigurationError", "OperationCancelled",
    "Diagnostic", "DiagnosticSeverity",
    "StrictConfig", "load_yaml_mapping", "load_versioned_config",
    "require_schema_version", "resolve_config_path",
    "EVENT_SCHEMA_VERSION", "EventContext", "ProgressEvent", "MetricEvent",
    "LogEvent", "LifecycleEvent", "CheckpointEvent", "LibraryEvent", "EventCallback",
    "CancellationCheck", "CancellationToken",
    "get_logger", "configure_library_logging",
]
