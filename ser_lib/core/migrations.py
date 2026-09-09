"""Stage 05 过渡兼容层：migration 实现已归属 config/data/engine/artifacts。"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from ser_lib.artifacts.migrations import validate_artifact_manifest_version
from ser_lib.config.migrations import (
    MigrationFunction,
    MigrationRegistry,
    SchemaMigration,
    list_config_migrations,
    migrate_config_payload,
    register_config_migration,
    validate_schema_version as validate_config_schema_version,
)
from ser_lib.data.migrations import migrate_data_payload
from ser_lib.engine.migrations import migrate_engine_payload

_DATA_DOMAINS = frozenset({"dataset_manifest", "dataset_revision"})
_ENGINE_DOMAINS = frozenset({"training_run", "evaluation_run"})


def register_schema_migration(
    domain: str,
    from_version: int,
    to_version: int,
    function: MigrationFunction,
) -> SchemaMigration:
    """兼容旧 API；Stage 05 结束后随 ``ser_lib.core`` 删除。"""
    return register_config_migration(domain, from_version, to_version, function)


def list_schema_migrations(domain: str | None = None) -> tuple[SchemaMigration, ...]:
    return list_config_migrations(domain)


def migrate_schema_payload(
    domain: str,
    payload: Mapping[str, Any],
    *,
    target_version: int,
) -> dict[str, Any]:
    if domain in _DATA_DOMAINS:
        return migrate_data_payload(domain, payload, target_version=target_version)
    if domain in _ENGINE_DOMAINS:
        return migrate_engine_payload(domain, payload, target_version=target_version)
    return migrate_config_payload(domain, payload, target_version=target_version)


def validate_schema_version(
    domain: str,
    payload: Mapping[str, Any],
    *,
    supported_versions: set[int] | frozenset[int] | tuple[int, ...],
) -> int:
    if domain == "artifact_manifest":
        return validate_artifact_manifest_version(
            payload,
            supported_versions=supported_versions,
        )
    return validate_config_schema_version(
        domain,
        payload,
        supported_versions=supported_versions,
    )


__all__ = [
    "MigrationFunction",
    "SchemaMigration",
    "MigrationRegistry",
    "validate_schema_version",
    "register_schema_migration",
    "list_schema_migrations",
    "migrate_schema_payload",
]
