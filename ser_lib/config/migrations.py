"""用户配置 schema 的显式 read-time migration 支持。"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from copy import deepcopy
from dataclasses import dataclass
from typing import Any

from ser_lib.foundation.errors import SchemaMigrationError

MigrationFunction = Callable[[dict[str, Any]], Mapping[str, Any]]


@dataclass(frozen=True, slots=True)
class SchemaMigration:
    """一个严格的 ``N -> N+1`` schema migration。"""

    domain: str
    from_version: int
    to_version: int
    function: MigrationFunction

    def __post_init__(self) -> None:
        if not self.domain.strip():
            raise ValueError("migration domain 不能为空")
        if self.from_version < 1:
            raise ValueError("from_version 必须 >= 1")
        if self.to_version != self.from_version + 1:
            raise ValueError("schema migration 只允许注册连续的 N -> N+1")


class MigrationRegistry:
    """配置域内按 domain/from_version 注册并顺序执行 migration。"""

    def __init__(self) -> None:
        self._migrations: dict[tuple[str, int], SchemaMigration] = {}

    def register(
        self,
        domain: str,
        from_version: int,
        to_version: int,
        function: MigrationFunction,
    ) -> SchemaMigration:
        migration = SchemaMigration(domain, from_version, to_version, function)
        key = (migration.domain, migration.from_version)
        if key in self._migrations:
            raise ValueError(
                f"schema migration 重复: {migration.domain} v{migration.from_version}"
            )
        self._migrations[key] = migration
        return migration

    def registered(self, domain: str | None = None) -> tuple[SchemaMigration, ...]:
        items = tuple(self._migrations.values())
        if domain is not None:
            items = tuple(item for item in items if item.domain == domain)
        return tuple(sorted(items, key=lambda item: (item.domain, item.from_version)))

    def migrate(
        self,
        domain: str,
        payload: Mapping[str, Any],
        *,
        target_version: int,
    ) -> dict[str, Any]:
        if not domain.strip():
            raise ValueError("migration domain 不能为空")
        if target_version < 1:
            raise ValueError("target_version 必须 >= 1")
        current = schema_version(payload, domain=domain)
        if current > target_version:
            raise SchemaMigrationError(
                f"{domain} schema_version={current} 高于当前支持版本 {target_version}",
                code="schema_version_future",
                details={
                    "domain": domain,
                    "actual": current,
                    "target": target_version,
                },
            )

        migrated = deepcopy(dict(payload))
        while current < target_version:
            migration = self._migrations.get((domain, current))
            if migration is None:
                raise SchemaMigrationError(
                    f"{domain} 缺少 schema migration: v{current} -> v{current + 1}",
                    code="schema_migration_missing",
                    details={
                        "domain": domain,
                        "from_version": current,
                        "target": target_version,
                    },
                )
            try:
                result = migration.function(deepcopy(migrated))
            except SchemaMigrationError:
                raise
            except Exception as exc:
                raise SchemaMigrationError(
                    f"{domain} schema migration v{current} -> v{current + 1} 执行失败",
                    code="schema_migration_failed",
                    details={
                        "domain": domain,
                        "from_version": current,
                        "to_version": current + 1,
                        "error_type": type(exc).__name__,
                    },
                ) from exc
            if not isinstance(result, Mapping):
                raise SchemaMigrationError(
                    f"{domain} migration 必须返回 mapping",
                    code="schema_migration_invalid_result",
                    details={"domain": domain, "from_version": current},
                )
            migrated = deepcopy(dict(result))
            actual = schema_version(migrated, domain=domain)
            if actual != migration.to_version:
                raise SchemaMigrationError(
                    f"{domain} migration v{current} 必须输出 schema_version={migration.to_version}",
                    code="schema_migration_invalid_result",
                    details={
                        "domain": domain,
                        "from_version": current,
                        "expected": migration.to_version,
                        "actual": actual,
                    },
                )
            current = actual
        return migrated


def schema_version(payload: Mapping[str, Any], *, domain: str) -> int:
    version = payload.get("schema_version")
    if isinstance(version, bool) or not isinstance(version, int) or version < 1:
        raise SchemaMigrationError(
            f"{domain} 缺少合法的 schema_version",
            code="schema_version_invalid",
            details={"domain": domain, "actual": version},
        )
    return version


def validate_schema_version(
    domain: str,
    payload: Mapping[str, Any],
    *,
    supported_versions: set[int] | frozenset[int] | tuple[int, ...],
) -> int:
    """校验配置 payload 是否属于显式支持的 schema 版本。"""
    version = schema_version(payload, domain=domain)
    supported = frozenset(supported_versions)
    if not supported:
        raise ValueError("supported_versions 不能为空")
    if version not in supported:
        code = "schema_version_future" if version > max(supported) else "schema_version_unsupported"
        raise SchemaMigrationError(
            f"{domain} 不支持 schema_version={version}；支持: {sorted(supported)}",
            code=code,
            details={"domain": domain, "actual": version, "supported": sorted(supported)},
        )
    return version


_config_registry = MigrationRegistry()


def register_config_migration(
    domain: str,
    from_version: int,
    to_version: int,
    function: MigrationFunction,
) -> SchemaMigration:
    return _config_registry.register(domain, from_version, to_version, function)


def list_config_migrations(domain: str | None = None) -> tuple[SchemaMigration, ...]:
    return _config_registry.registered(domain)


def migrate_config_payload(
    domain: str,
    payload: Mapping[str, Any],
    *,
    target_version: int,
) -> dict[str, Any]:
    return _config_registry.migrate(domain, payload, target_version=target_version)


__all__ = [
    "MigrationFunction",
    "SchemaMigration",
    "MigrationRegistry",
    "schema_version",
    "validate_schema_version",
    "register_config_migration",
    "list_config_migrations",
    "migrate_config_payload",
]
