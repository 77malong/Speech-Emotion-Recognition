"""兼容入口：异常实现已迁移到 :mod:`ser_lib.foundation.errors`。

该 shim 仅用于 0.2.x 过渡，计划在 Stage 05 删除。
"""

from ser_lib.foundation.errors import (
    ConfigurationError,
    OperationCancelled,
    SchemaMigrationError,
    SERError,
)

__all__ = [
    "SERError",
    "ConfigurationError",
    "SchemaMigrationError",
    "OperationCancelled",
]
