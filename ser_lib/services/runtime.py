"""运行环境能力与资源快照应用服务。"""

from __future__ import annotations

import torch

from ser_lib.runtime import (
    RuntimeCapabilities,
    RuntimeMetrics,
    get_runtime_capabilities,
    get_runtime_metrics,
)


class RuntimeService:
    """提供环境能力与按需资源快照；不负责后台轮询。"""

    @staticmethod
    def capabilities() -> RuntimeCapabilities:
        return get_runtime_capabilities()

    @staticmethod
    def metrics(device: str | torch.device = "cpu") -> RuntimeMetrics:
        return get_runtime_metrics(device)


__all__ = ["RuntimeService"]
