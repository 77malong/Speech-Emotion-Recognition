"""可信本地训练 checkpoint 的原子保存与完整恢复。"""

from __future__ import annotations

import random
from collections.abc import Callable
from pathlib import Path
from typing import Any

import numpy as np
import torch
from pydantic import BaseModel, ConfigDict, Field

from ser_lib._version import __version__
from ser_lib.models.base import SERModel


class _CheckpointPayload(BaseModel):
    """Current trusted-local payload; validate before applying any runtime state."""

    model_config = ConfigDict(extra="forbid", strict=True, arbitrary_types_allowed=True)

    library_version: str = Field(min_length=1)
    model_id: str = Field(min_length=1)
    model_configuration: dict[str, Any] = Field(alias="model_config")
    model_state: dict[str, Any]
    optimizer_state: dict[str, Any] | None
    scheduler_state: dict[str, Any] | None
    scaler_state: dict[str, Any] | None
    rng_state: dict[str, Any]
    epoch: int = Field(ge=0)
    metrics: dict[str, float]
    metadata: dict[str, Any]
    trainer_config: dict[str, Any]


_RUNTIME_ONLY_TRAINER_CONFIG_FIELDS = {
    "epochs",
    "checkpoint_dir",
    "save_best",
    "save_last",
}


def _rng_state() -> dict[str, Any]:
    state: dict[str, Any] = {
        "python": random.getstate(),
        "numpy": np.random.get_state(),
        "torch_cpu": torch.get_rng_state(),
    }
    if torch.cuda.is_available():
        state["torch_cuda"] = torch.cuda.get_rng_state_all()
    return state


def _restore_rng_state(state: dict[str, Any]) -> None:
    if "python" in state:
        random.setstate(state["python"])
    if "numpy" in state:
        np.random.set_state(state["numpy"])
    if "torch_cpu" in state:
        torch.set_rng_state(state["torch_cpu"].cpu())
    if "torch_cuda" in state and torch.cuda.is_available():
        torch.cuda.set_rng_state_all(state["torch_cuda"])


def _validate_rng_state(state: dict[str, Any]) -> None:
    """Validate checkpoint RNG payloads without mutating process-global RNG state."""
    try:
        python_rng = random.Random()
        python_rng.setstate(state["python"])
    except (TypeError, ValueError) as exc:
        raise ValueError("checkpoint Python RNG state 非法") from exc

    try:
        numpy_rng = np.random.RandomState()
        numpy_rng.set_state(state["numpy"])
    except (TypeError, ValueError) as exc:
        raise ValueError("checkpoint NumPy RNG state 非法") from exc

    torch_cpu_state = state["torch_cpu"]
    if not isinstance(torch_cpu_state, torch.Tensor):
        raise ValueError("checkpoint Torch CPU RNG state 必须是 Tensor")
    try:
        torch.Generator(device="cpu").set_state(torch_cpu_state.detach().cpu())
    except (TypeError, RuntimeError) as exc:
        raise ValueError("checkpoint Torch CPU RNG state 非法") from exc

    cuda_state = state.get("torch_cuda")
    if cuda_state is None:
        return
    if not isinstance(cuda_state, (list, tuple)) or not all(
        isinstance(item, torch.Tensor) for item in cuda_state
    ):
        raise ValueError("checkpoint Torch CUDA RNG state 必须是 Tensor 序列")
    if not torch.cuda.is_available():
        return
    if len(cuda_state) > torch.cuda.device_count():
        raise ValueError("checkpoint Torch CUDA RNG state 超出当前设备数量")
    try:
        for index, item in enumerate(cuda_state):
            torch.Generator(device=f"cuda:{index}").set_state(item.detach().cpu())
    except (TypeError, RuntimeError) as exc:
        raise ValueError("checkpoint Torch CUDA RNG state 非法") from exc


def _resume_trainer_signature(config: dict[str, Any]) -> dict[str, Any]:
    """Return only trainer fields that must stay stable for numerical resume semantics."""
    return {
        key: value
        for key, value in config.items()
        if key not in _RUNTIME_ONLY_TRAINER_CONFIG_FIELDS
    }


def save_checkpoint(
    path: Path | str,
    model: SERModel,
    optimizer: torch.optim.Optimizer | None,
    *,
    epoch: int,
    scheduler: torch.optim.lr_scheduler.LRScheduler | None = None,
    scaler: torch.cuda.amp.GradScaler | None = None,
    metrics: dict[str, float] | None = None,
    metadata: dict[str, Any] | None = None,
    trainer_config: dict[str, Any] | None = None,
) -> Path:
    """原子保存继续训练所需状态。

    Checkpoint 使用 pickle，只能加载由本库在可信本地环境生成的文件；用于分发
    的模型必须使用 artifact。
    """
    if isinstance(epoch, bool) or not isinstance(epoch, int) or epoch < 0:
        raise ValueError("checkpoint epoch 不能为负数")
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + ".tmp")
    payload = {
        "library_version": __version__,
        "model_id": model.model_spec.model_id,
        "model_config": model.model_config,
        "model_state": model.state_dict(),
        "optimizer_state": optimizer.state_dict() if optimizer else None,
        "scheduler_state": scheduler.state_dict() if scheduler else None,
        "scaler_state": scaler.state_dict() if scaler else None,
        "rng_state": _rng_state(),
        "epoch": int(epoch),
        "metrics": dict(metrics or {}),
        "metadata": dict(metadata or {}),
        "trainer_config": dict(trainer_config or {}),
    }
    _CheckpointPayload.model_validate(payload)
    try:
        torch.save(payload, temporary)
        temporary.replace(target)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise
    return target


def load_checkpoint(
    path: Path | str,
    model: SERModel,
    optimizer: torch.optim.Optimizer | None = None,
    *,
    scheduler: torch.optim.lr_scheduler.LRScheduler | None = None,
    scaler: torch.cuda.amp.GradScaler | None = None,
    map_location: str | torch.device = "cpu",
    restore_rng: bool = True,
    expected_trainer_config: dict[str, Any] | None = None,
    metadata_validator: Callable[[dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    """严格加载当前结构的可信本地 checkpoint。

    ``metadata_validator`` 在任何 model/optimizer/scheduler/scaler 状态应用之前执行，
    用于高层实验入口检查 lineage、数据指纹和完整实验配置兼容性，避免“不兼容后
    才报错但当前对象已被部分恢复”的半状态。
    """
    source = Path(path)
    if not source.is_file():
        raise FileNotFoundError(f"checkpoint 不存在: {source}")
    payload = torch.load(source, map_location=map_location, weights_only=False)
    if not isinstance(payload, dict):
        raise ValueError("checkpoint 顶层结构必须是映射")
    _CheckpointPayload.model_validate(payload)
    rng_state = payload["rng_state"]
    if set(rng_state) - {"python", "numpy", "torch_cpu", "torch_cuda"} or not {
        "python", "numpy", "torch_cpu"
    }.issubset(rng_state):
        raise ValueError("checkpoint rng_state 字段不完整或包含未知字段")
    _validate_rng_state(rng_state)
    if payload.get("model_id") != model.model_spec.model_id:
        raise ValueError("checkpoint 与当前模型类型不一致")
    saved_model_config = payload.get("model_config")
    if saved_model_config is not None and saved_model_config != model.model_config:
        raise ValueError("checkpoint 与当前模型配置不一致")
    if expected_trainer_config is not None:
        saved_trainer_config = payload.get("trainer_config")
        if saved_trainer_config and (
            _resume_trainer_signature(saved_trainer_config)
            != _resume_trainer_signature(expected_trainer_config)
        ):
            raise ValueError("checkpoint trainer_config 与当前训练配置不一致")

    metadata = payload.get("metadata")
    if metadata is None:
        normalized_metadata: dict[str, Any] = {}
    elif isinstance(metadata, dict):
        normalized_metadata = metadata
    else:
        raise ValueError("checkpoint metadata 必须是映射")
    if metadata_validator is not None:
        metadata_validator(normalized_metadata)

    model_state = payload.get("model_state")
    if not isinstance(model_state, dict):
        raise ValueError("checkpoint 缺少合法 model_state")
    model.load_state_dict(model_state)
    if optimizer is not None and payload.get("optimizer_state") is not None:
        optimizer.load_state_dict(payload["optimizer_state"])
    if scheduler is not None and payload.get("scheduler_state") is not None:
        scheduler.load_state_dict(payload["scheduler_state"])
    if scaler is not None and payload.get("scaler_state") is not None:
        scaler.load_state_dict(payload["scaler_state"])
    if restore_rng:
        _restore_rng_state(payload["rng_state"])
    return payload


__all__ = ["save_checkpoint", "load_checkpoint"]
