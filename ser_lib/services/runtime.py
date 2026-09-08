"""运行环境能力应用服务。"""

from __future__ import annotations

from ser_lib.runtime import RuntimeCapabilities, get_runtime_capabilities


class RuntimeService:
    """提供一次性 RuntimeCapabilities 快照。"""

    @staticmethod
    def capabilities() -> RuntimeCapabilities:
        return get_runtime_capabilities()


__all__ = ["RuntimeService"]
