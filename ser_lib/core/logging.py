"""兼容入口：日志 helper 已迁移到 :mod:`ser_lib.foundation.logging`。

该 shim 仅用于 0.2.x 过渡，计划在 Stage 05 删除。
"""

from ser_lib.foundation.logging import (
    LOGGER_NAME,
    configure_library_logging,
    get_logger,
)

__all__ = ["LOGGER_NAME", "get_logger", "configure_library_logging"]
