"""SER 基础库的 0.2.x 兼容入口。

通用基础设施已迁移到 ``ser_lib.foundation``；配置与 migration 仍将在后续阶段迁移。
"""

from __future__ import annotations

import importlib
from typing import Any

from ser_lib.core.config import (
    StrictConfig,
    load_versioned_config,
    load_yaml_mapping,
    require_schema_version,
    resolve_config_path,
)
from ser_lib.core.events import (
    EVENT_SCHEMA_VERSION,
    CancellationCheck,
    CancellationToken,
    EventCallback,
    EventContext,
    LibraryEvent,
    LifecycleEvent,
    LogEvent,
    MetricEvent,
    ProgressEvent,
)
from ser_lib.core.migrations import (
    MigrationFunction,
    MigrationRegistry,
    SchemaMigration,
    list_schema_migrations,
    migrate_schema_payload,
    register_schema_migration,
    validate_schema_version,
)
from ser_lib.foundation.diagnostics import Diagnostic, DiagnosticSeverity
from ser_lib.foundation.errors import (
    ConfigurationError,
    OperationCancelled,
    SchemaMigrationError,
    SERError,
)
from ser_lib.foundation.logging import configure_library_logging, get_logger

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
