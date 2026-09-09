"""配置 YAML 读取、schema version 门禁与确定性路径解析。"""

from __future__ import annotations

from pathlib import Path
from typing import Any, TypeVar

import yaml
from pydantic import BaseModel, ValidationError

from ser_lib.config.migrations import migrate_config_payload
from ser_lib.foundation.errors import ConfigurationError, SchemaMigrationError

ConfigT = TypeVar("ConfigT", bound=BaseModel)


def resolve_config_path(value: Path | str, *, base_dir: Path | str) -> Path:
    """相对 ``base_dir`` 解析路径，不依赖当前工作目录。"""
    path = Path(value).expanduser()
    base = Path(base_dir).expanduser()
    return path.resolve() if path.is_absolute() else (base / path).resolve()


def require_schema_version(
    raw: dict[str, Any],
    *,
    supported: set[int] | frozenset[int] | tuple[int, ...],
    source: Path | str | None = None,
) -> int:
    """读取并验证配置 schema 版本，拒绝缺失、布尔值和未知版本。"""
    version = raw.get("schema_version")
    location = f": {source}" if source is not None else ""
    if isinstance(version, bool) or not isinstance(version, int):
        raise ConfigurationError(f"配置缺少合法的 schema_version{location}")
    supported_versions = frozenset(supported)
    if version not in supported_versions:
        expected = ", ".join(str(item) for item in sorted(supported_versions))
        raise ConfigurationError(
            f"不支持 schema_version={version}，支持版本: {expected}{location}",
            details={"actual": version, "supported": sorted(supported_versions)},
        )
    return version


def load_yaml_mapping(path: Path | str) -> tuple[dict[str, Any], Path]:
    """安全读取 YAML 映射，并返回内容与规范化文件路径。"""
    source = Path(path).expanduser().resolve()
    try:
        with source.open("r", encoding="utf-8") as stream:
            raw = yaml.safe_load(stream)
    except (OSError, yaml.YAMLError) as exc:
        raise ConfigurationError(f"无法读取 YAML 配置: {source}") from exc
    if not isinstance(raw, dict):
        raise ConfigurationError(f"配置文件必须是 YAML 映射: {source}")
    return dict(raw), source


def load_versioned_config(
    path: Path | str,
    model: type[ConfigT],
    *,
    supported_versions: set[int] | frozenset[int] | tuple[int, ...] = (1,),
    schema_domain: str | None = None,
    target_version: int | None = None,
) -> ConfigT:
    """读取版本化 YAML，按需使用 config 域 registry 迁移并严格校验。"""
    raw, source = load_yaml_mapping(path)
    if schema_domain is None:
        require_schema_version(raw, supported=supported_versions, source=source)
    else:
        resolved_target = target_version
        if resolved_target is None:
            versions = frozenset(supported_versions)
            if not versions:
                raise ValueError("supported_versions 不能为空")
            resolved_target = max(versions)
        try:
            raw = migrate_config_payload(
                schema_domain,
                raw,
                target_version=resolved_target,
            )
        except SchemaMigrationError as exc:
            raise ConfigurationError(
                f"配置 schema 迁移失败: {source}: {exc}",
                code=exc.code,
                details={**exc.details, "source": source.as_posix()},
            ) from exc
    try:
        return model.model_validate(raw)
    except ValidationError as exc:
        raise ConfigurationError(
            f"配置内容校验失败: {source}", details={"errors": exc.errors()}
        ) from exc


__all__ = [
    "resolve_config_path",
    "require_schema_version",
    "load_yaml_mapping",
    "load_versioned_config",
]
