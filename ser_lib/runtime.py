"""面向 CLI/Web 的轻量运行环境能力与资源快照。"""

from __future__ import annotations

import platform
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
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


@dataclass(frozen=True, slots=True)
class RuntimeMetrics:
    """单设备即时资源快照；设计为由 Web Backend 低频主动轮询。"""

    device_id: str
    device_type: str
    captured_at: datetime
    allocated_memory: int | None = None
    reserved_memory: int | None = None
    max_allocated_memory: int | None = None
    free_memory: int | None = None
    total_memory: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "device_id": self.device_id,
            "device_type": self.device_type,
            "captured_at": self.captured_at.isoformat(),
            "allocated_memory": self.allocated_memory,
            "reserved_memory": self.reserved_memory,
            "max_allocated_memory": self.max_allocated_memory,
            "free_memory": self.free_memory,
            "total_memory": self.total_memory,
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


def _resolve_cuda_index(device: torch.device) -> int:
    if not torch.cuda.is_available():
        raise ValueError("请求 CUDA RuntimeMetrics，但当前环境 CUDA 不可用")
    index = device.index
    if index is None:
        index = int(torch.cuda.current_device())
    count = int(torch.cuda.device_count())
    if index < 0 or index >= count:
        raise ValueError(f"CUDA 设备索引 {index} 超出当前设备数量 {count}")
    return index


def get_runtime_metrics(
    device: str | torch.device = "cpu",
) -> RuntimeMetrics:
    """返回一个设备的即时资源快照，不做 GPU synchronize。

    CUDA 暴露 PyTorch allocator 的 allocated/reserved/max allocated，以及驱动层
    ``mem_get_info`` 的 free/total。CPU/MPS 当前不引入 psutil 或平台专用依赖，
    因此内存字段保持 ``None``。该函数只负责单次采样，轮询频率由 Backend 决定。
    """
    try:
        resolved = torch.device(device)
    except (TypeError, RuntimeError) as exc:
        raise ValueError(f"无效运行设备: {device!r}") from exc

    captured_at = datetime.now(timezone.utc)
    if resolved.type != "cuda":
        return RuntimeMetrics(
            device_id=str(resolved),
            device_type=resolved.type,
            captured_at=captured_at,
        )

    index = _resolve_cuda_index(resolved)
    free_memory, total_memory = torch.cuda.mem_get_info(index)
    return RuntimeMetrics(
        device_id=f"cuda:{index}",
        device_type="cuda",
        captured_at=captured_at,
        allocated_memory=int(torch.cuda.memory_allocated(index)),
        reserved_memory=int(torch.cuda.memory_reserved(index)),
        max_allocated_memory=int(torch.cuda.max_memory_allocated(index)),
        free_memory=int(free_memory),
        total_memory=int(total_memory),
    )


__all__ = [
    "RuntimeDevice",
    "RuntimeCapabilities",
    "RuntimeMetrics",
    "get_runtime_capabilities",
    "get_runtime_metrics",
]
