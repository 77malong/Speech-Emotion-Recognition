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
    PredictionEvent,
    ProgressEvent,
)
from ser_lib.core.exceptions import (
    ConfigurationError,
    OperationCancelled,
    SchemaMigrationError,
    SERError,
)
from ser_lib.core.logging import configure_library_logging, get_logger
from ser_lib.core.migrations import (
    MigrationFunction,
    MigrationRegistry,
    SchemaMigration,
    list_schema_migrations,
    migrate_schema_payload,
    register_schema_migration,
    validate_schema_version,
)

__all__ = [
    "SERError", "ConfigurationError", "SchemaMigrationError", "OperationCancelled",
    "Diagnostic", "DiagnosticSeverity",
    "StrictConfig", "load_yaml_mapping", "load_versioned_config",
    "require_schema_version", "resolve_config_path",
    "MigrationFunction", "SchemaMigration", "MigrationRegistry",
    "validate_schema_version", "register_schema_migration",
    "list_schema_migrations", "migrate_schema_payload",
    "EVENT_SCHEMA_VERSION", "EventContext", "ProgressEvent", "MetricEvent",
    "LogEvent", "LifecycleEvent", "CheckpointEvent", "PredictionEvent",
    "LibraryEvent", "EventCallback", "CancellationCheck", "CancellationToken",
    "get_logger", "configure_library_logging",
]
