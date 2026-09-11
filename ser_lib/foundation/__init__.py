"""SER-lib 的轻量跨领域基础设施。"""

from ser_lib.foundation.diagnostics import Diagnostic, DiagnosticSeverity
from ser_lib.foundation.errors import (
    CompatibilityError,
    ConfigurationError,
    OperationCancelled,
    RegistryError,
    SERError,
)
from ser_lib.foundation.events import (
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
    "OperationCancelled",
    "RegistryError",
    "CompatibilityError",
    "Diagnostic",
    "DiagnosticSeverity",
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
