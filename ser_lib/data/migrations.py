"""Dataset 持久化格式的 read-time version gate。"""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from typing import Any

from ser_lib.foundation.errors import SchemaMigrationError

_DATA_DOMAINS = frozenset({"dataset_manifest", "dataset_revision"})


def migrate_data_payload(
    domain: str,
    payload: Mapping[str, Any],
    *,
    target_version: int,
) -> dict[str, Any]:
    """迁移 data 域 payload；当前真实格式尚无跨版本结构迁移。"""
    if domain not in _DATA_DOMAINS:
        raise ValueError(f"未知 data migration domain: {domain!r}")
    if target_version < 1:
        raise ValueError("target_version 必须 >= 1")
    version = _schema_version(payload, domain=domain)
    if version > target_version:
        raise SchemaMigrationError(
            f"{domain} schema_version={version} 高于当前支持版本 {target_version}",
            code="schema_version_future",
            details={"domain": domain, "actual": version, "target": target_version},
        )
    if version < target_version:
        raise SchemaMigrationError(
            f"{domain} 缺少 schema migration: v{version} -> v{version + 1}",
            code="schema_migration_missing",
            details={
                "domain": domain,
                "from_version": version,
                "target": target_version,
            },
        )
    return deepcopy(dict(payload))


def _schema_version(payload: Mapping[str, Any], *, domain: str) -> int:
    version = payload.get("schema_version")
    if isinstance(version, bool) or not isinstance(version, int) or version < 1:
        raise SchemaMigrationError(
            f"{domain} 缺少合法的 schema_version",
            code="schema_version_invalid",
            details={"domain": domain, "actual": version},
        )
    return version


__all__ = ["migrate_data_payload"]
