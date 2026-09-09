"""0.2.x 兼容入口：配置基础设施已迁移到 ``ser_lib.config``。

该 shim 只保留旧 import path；正式定义位于 config/base.py 与 config/loader.py。
计划随剩余 core 迁移在 Stage 05 前后删除。
"""

from ser_lib.config.base import StrictConfig
from ser_lib.config.loader import (
    load_versioned_config,
    load_yaml_mapping,
    require_schema_version,
    resolve_config_path,
)

__all__ = [
    "StrictConfig",
    "resolve_config_path",
    "require_schema_version",
    "load_yaml_mapping",
    "load_versioned_config",
]
