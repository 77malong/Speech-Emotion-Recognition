"""Artifact manifest 的真实版本门禁。"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from ser_lib.foundation.errors import SchemaMigrationError


def validate_artifact_manifest_version(
    payload: Mapping[str, Any],
    *,
    supported_versions: set[int] | frozenset[int] | tuple[int, ...] = (1, 2),
) -> int:
    """接受真实 v1/v2 manifest；不会把 v1 伪升级成带 hash 的 v2。"""
    version = payload.get("schema_version")
    if isinstance(version, bool) or not isinstance(version, int) or version < 1:
        raise SchemaMigrationError(
            "artifact_manifest 缺少合法的 schema_version",
            code="schema_version_invalid",
            details={"domain": "artifact_manifest", "actual": version},
        )
    supported = frozenset(supported_versions)
    if not supported:
        raise ValueError("supported_versions 不能为空")
    if version not in supported:
        code = "schema_version_future" if version > max(supported) else "schema_version_unsupported"
        raise SchemaMigrationError(
            f"artifact_manifest 不支持 schema_version={version}；支持: {sorted(supported)}",
            code=code,
            details={
                "domain": "artifact_manifest",
                "actual": version,
                "supported": sorted(supported),
            },
        )
    return version


__all__ = ["validate_artifact_manifest_version"]
