"""SER 模型的静态输入能力契约。"""

from __future__ import annotations

from dataclasses import dataclass

from ser_lib.data.types import TensorSpec


@dataclass(frozen=True)
class ModelSpec:
    """模型输入规格（模型显式声明，禁止调用方猜测 tensor shape）。"""

    model_id: str
    required_inputs: dict[str, TensorSpec]
    supports_masks: bool
    supports_variable_length: bool
    num_classes: int | None
    expected_sample_rate: int | None = None


__all__ = ["ModelSpec"]
