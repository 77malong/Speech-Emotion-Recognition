"""面向 CLI/Web 的轻量运行环境能力发现。"""

from __future__ import annotations

import platform
from dataclasses import asdict, dataclass
from typing import Any

import torch


@dataclass(frozen=True, slots=True)
class RuntimeDevice:
    """一个可供单设备训练/评估/推理选择的运行设备。"""

    id: str
    type: str
    name: str
    total_memory: int | None
    amp_supported: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class RuntimeCapabilities:
    """一次性环境能力快照；不承担持续 CPU/GPU 资源监控。"""

    python_version: str
    torch_version: str
    cuda_available: bool
    devices: tuple[RuntimeDevice, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "python_version": self.python_version,
            "torch_version": self.torch_version,
            "cuda_available": self.cuda_available,
            "devices": [device.to_dict() for device in self.devices],
        }


def get_runtime_capabilities() -> RuntimeCapabilities:
    """返回 JSON-safe 的 Python/PyTorch 与本机可选设备信息。

    当前项目仍是单设备训练，因此这里列出所有设备只是为了让上层界面选择
    ``cpu`` 或某一张 ``cuda:N``，并不表示 Trainer 已支持多卡/多机训练。
    ``amp_supported`` 与当前 Trainer 行为保持一致：仅 CUDA 为 ``True``。
    """
    cuda_available = bool(torch.cuda.is_available())
    devices: list[RuntimeDevice] = [
        RuntimeDevice(
            id="cpu",
            type="cpu",
            name="CPU",
            total_memory=None,
            amp_supported=False,
        )
    ]

    if cuda_available:
        for index in range(torch.cuda.device_count()):
            properties = torch.cuda.get_device_properties(index)
            devices.append(
                RuntimeDevice(
                    id=f"cuda:{index}",
                    type="cuda",
                    name=properties.name,
                    total_memory=int(properties.total_memory),
                    amp_supported=True,
                )
            )

    mps_backend = getattr(torch.backends, "mps", None)
    if mps_backend is not None and mps_backend.is_available():
        devices.append(
            RuntimeDevice(
                id="mps",
                type="mps",
                name="Apple Metal Performance Shaders",
                total_memory=None,
                amp_supported=False,
            )
        )

    return RuntimeCapabilities(
        python_version=platform.python_version(),
        torch_version=str(torch.__version__),
        cuda_available=cuda_available,
        devices=tuple(devices),
    )


__all__ = ["RuntimeDevice", "RuntimeCapabilities", "get_runtime_capabilities"]
