"""SER-lib 的轻量跨领域基础设施。"""

from ser_lib.foundation.diagnostics import Diagnostic, DiagnosticSeverity
from ser_lib.foundation.errors import (
    ConfigurationError,
    OperationCancelled,
    RegistryError,
    SchemaMigrationError,
    SERError,
)
from ser_lib.foundation.events import (
    EVENT_SCHEMA_VERSION,
    CancellationCheck,
    CancellationToken,
    EventCallback,
    EventContext,
    EventLike,
    LibraryEvent,
    LifecycleEvent,
    LogEvent,
    MetricEvent,
    ProgressEvent,
)
from ser_lib.foundation.logging import configure_library_logging, get_logger

__all__ = [
    "SERError",
    "ConfigurationError",
    "SchemaMigrationError",
    "OperationCancelled",
    "RegistryError",
    "Diagnostic",
    "DiagnosticSeverity",
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
    "get_logger",
    "configure_library_logging",
]
