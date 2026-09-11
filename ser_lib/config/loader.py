"""配置 YAML 读取与确定性路径解析。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from ser_lib.foundation.errors import ConfigurationError


def resolve_config_path(value: Path | str, *, base_dir: Path | str) -> Path:
    """相对 ``base_dir`` 解析路径，不依赖当前工作目录。"""
    path = Path(value).expanduser()
    base = Path(base_dir).expanduser()
    return path.resolve() if path.is_absolute() else (base / path).resolve()


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


__all__ = [
    "resolve_config_path",
    "load_yaml_mapping",
]
