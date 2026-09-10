"""普通 ``torch.nn.Module`` 到 SERModel 的显式、可重建适配。"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import torch
from torch import nn

from ser_lib.config.model import (
    TorchModelAdapterConfig,
    TorchOutputMappingConfig,
    TorchTensorSpecConfig,
)
from ser_lib.data.types import SERBatch, TensorSpec
from ser_lib.models.base import ModelOutput, SERModel
from ser_lib.models.registry import ModelDescriptor, model_registry
from ser_lib.models.specs import ModelSpec

TORCH_ADAPTER_MODEL_ID = "torch_model_adapter"

_DTYPE_BY_NAME: dict[str, torch.dtype] = {
    "float16": torch.float16,
    "float32": torch.float32,
    "float64": torch.float64,
    "bfloat16": torch.bfloat16,
    "int8": torch.int8,
    "int16": torch.int16,
    "int32": torch.int32,
    "int64": torch.int64,
    "uint8": torch.uint8,
    "bool": torch.bool,
}


def _tensor_spec(config: TorchTensorSpecConfig) -> TensorSpec:
    return TensorSpec(
        layout=config.layout,
        dtype=_DTYPE_BY_NAME[config.dtype],
        feature_dim=config.feature_dim,
        pad_value=config.pad_value,
    )


def _tensor_spec_config(spec: TensorSpec) -> TorchTensorSpecConfig:
    dtype = str(spec.dtype).removeprefix("torch.")
    if dtype not in _DTYPE_BY_NAME:
        raise ValueError(f"TorchModelAdapter 不支持持久化 dtype={spec.dtype}")
    return TorchTensorSpecConfig(
        layout=spec.layout,
        dtype=dtype,
        feature_dim=spec.feature_dim,
        pad_value=spec.pad_value,
    )


def _model_spec_from_config(params: dict[str, Any]) -> ModelSpec:
    config = TorchModelAdapterConfig.model_validate(params)
    return ModelSpec(
        model_id=TORCH_ADAPTER_MODEL_ID,
        required_inputs={
            key: _tensor_spec(value) for key, value in config.required_inputs.items()
        },
        supports_masks=config.supports_masks,
        supports_variable_length=config.supports_variable_length,
        num_classes=config.num_classes,
        expected_sample_rate=config.expected_sample_rate,
    )


def _resolve_batch_source(batch: SERBatch, source: str) -> torch.Tensor:
    if source == "labels":
        if batch.labels is None:
            raise ValueError("TorchModelAdapter input_map 请求 labels，但当前 batch 无标签")
        return batch.labels

    namespace, key = source.split(".", 1)
    values = {
        "inputs": batch.inputs,
        "masks": batch.masks,
        "lengths": batch.lengths,
    }[namespace]
    try:
        return values[key]
    except KeyError:
        raise ValueError(
            f"TorchModelAdapter input_map 请求 {source!r}，但 batch 中不存在该值"
        ) from None


def _select_output(value: Any, selector: str, *, field: str) -> torch.Tensor:
    current = value
    for part in selector.split("."):
        if isinstance(current, Mapping):
            if part not in current:
                raise ValueError(f"TorchModelAdapter 输出选择器 {selector!r} 缺少 key {part!r}")
            current = current[part]
        elif isinstance(current, (tuple, list)):
            try:
                index = int(part)
                current = current[index]
            except (ValueError, IndexError):
                raise ValueError(
                    f"TorchModelAdapter 输出选择器 {selector!r} 的索引 {part!r} 无效"
                ) from None
        else:
            if part.startswith("_") or not hasattr(current, part):
                raise ValueError(
                    f"TorchModelAdapter 输出选择器 {selector!r} 无法读取属性 {part!r}"
                )
            current = getattr(current, part)
    if not isinstance(current, torch.Tensor):
        raise ValueError(
            f"TorchModelAdapter {field} 选择器 {selector!r} 必须得到 tensor，"
            f"实际 {type(current)!r}"
        )
    return current


class TorchModelAdapter(SERModel):
    """用显式输入/输出映射包装普通 ``nn.Module``。

    adapter 作为正常子模块参与 ``parameters()``、``to()``、train/eval 模式切换；
    但持久化权重直接委托给被包装 module，因此不会引入 ``module.``、``model.``
    或 ``_module.`` state_dict 前缀。
    """

    def __init__(self, module: nn.Module, config: TorchModelAdapterConfig) -> None:
        super().__init__()
        if not isinstance(module, nn.Module):
            raise TypeError(f"module 必须是 torch.nn.Module，实际 {type(module)!r}")
        if isinstance(module, SERModel):
            raise ValueError("已有 SERModel 不应再次使用 TorchModelAdapter 包装")
        self._module = module
        self._adapter_config = config
        if config.freeze_module:
            for parameter in self._module.parameters():
                parameter.requires_grad_(False)

    @classmethod
    def wrap(
        cls,
        module: nn.Module,
        *,
        required_inputs: Mapping[str, TensorSpec],
        input_map: Mapping[str, str],
        num_classes: int,
        output: TorchOutputMappingConfig | Mapping[str, Any] | None = None,
        supports_masks: bool = False,
        supports_variable_length: bool = False,
        expected_sample_rate: int | None = None,
        freeze_module: bool = False,
        factory_id: str | None = None,
        factory_params: Mapping[str, Any] | None = None,
    ) -> "TorchModelAdapter":
        """显式包装现有 module；factory 可缺省用于仅本地/checkpoint 场景。"""
        if output is None:
            output_config = TorchOutputMappingConfig()
        elif isinstance(output, TorchOutputMappingConfig):
            output_config = output
        else:
            output_config = TorchOutputMappingConfig.model_validate(dict(output))
        config = TorchModelAdapterConfig(
            factory_id=factory_id,
            factory_params=dict(factory_params or {}),
            input_map=dict(input_map),
            output=output_config,
            required_inputs={
                key: _tensor_spec_config(spec) for key, spec in required_inputs.items()
            },
            supports_masks=supports_masks,
            supports_variable_length=supports_variable_length,
            num_classes=num_classes,
            expected_sample_rate=expected_sample_rate,
            freeze_module=freeze_module,
        )
        return cls(module, config)

    @property
    def wrapped_module(self) -> nn.Module:
        return self._module

    @property
    def model_spec(self) -> ModelSpec:
        return _model_spec_from_config(self.model_config)

    @property
    def model_config(self) -> dict[str, Any]:
        return self._adapter_config.model_dump(mode="json")

    def state_dict(self, *args: Any, **kwargs: Any):  # type: ignore[override]
        """返回底层 module 原始 key，避免 adapter 路径污染权重契约。"""
        return self._module.state_dict(*args, **kwargs)

    def load_state_dict(  # type: ignore[override]
        self,
        state_dict: Mapping[str, torch.Tensor],
        strict: bool = True,
        assign: bool = False,
    ):
        return self._module.load_state_dict(state_dict, strict=strict, assign=assign)

    def forward(self, batch: SERBatch) -> ModelOutput:
        kwargs = {
            argument: _resolve_batch_source(batch, source)
            for argument, source in self._adapter_config.input_map.items()
        }
        raw = self._module(**kwargs)
        output_mapping = self._adapter_config.output

        if isinstance(raw, ModelOutput):
            if any(
                selector is not None
                for selector in (
                    output_mapping.logits,
                    output_mapping.embeddings,
                    output_mapping.loss,
                )
            ):
                raise ValueError(
                    "module 已返回 ModelOutput 时不能再配置 output selector"
                )
            result = raw
        else:
            if output_mapping.logits is None:
                if not isinstance(raw, torch.Tensor):
                    raise ValueError(
                        "module 非直接返回 logits tensor 时必须配置 output.logits 选择器"
                    )
                logits = raw
            else:
                logits = _select_output(raw, output_mapping.logits, field="logits")
            embeddings = (
                _select_output(raw, output_mapping.embeddings, field="embeddings")
                if output_mapping.embeddings is not None
                else None
            )
            loss = (
                _select_output(raw, output_mapping.loss, field="loss")
                if output_mapping.loss is not None
                else None
            )
            result = ModelOutput(logits=logits, embeddings=embeddings, loss=loss)

        if result.logits.shape[1] != self._adapter_config.num_classes:
            raise ValueError(
                "TorchModelAdapter logits 类别维与 num_classes 不一致: "
                f"{result.logits.shape[1]} != {self._adapter_config.num_classes}"
            )
        return result


def _build_registered_adapter(**params: Any) -> TorchModelAdapter:
    config = TorchModelAdapterConfig.model_validate(params)
    if config.factory_id is None:
        raise ValueError("可重建 TorchModelAdapter 必须提供 factory_id")
    module = model_registry.create_torch_module(config.factory_id, **config.factory_params)
    return TorchModelAdapter(module, config)


def _validate_reconstructible(params: dict[str, Any]) -> None:
    config = TorchModelAdapterConfig.model_validate(params)
    if config.factory_id is None:
        raise ValueError("缺少 factory_id；手工包装 module 不能导出为可移植 artifact")
    model_registry.validate_torch_factory_config(config.factory_id, config.factory_params)


model_registry.register(
    TORCH_ADAPTER_MODEL_ID,
    _build_registered_adapter,
    config_model=TorchModelAdapterConfig,
    descriptor=ModelDescriptor(
        id=TORCH_ADAPTER_MODEL_ID,
        display_name="通用 PyTorch Module Adapter",
        description="通过显式 batch/output 映射接入已注册的普通 torch.nn.Module。",
        config_schema=TorchModelAdapterConfig.model_json_schema(),
        input_layouts={},
        status="stable",
    ),
    spec_factory=_model_spec_from_config,
    reconstructibility_check=_validate_reconstructible,
)


__all__ = ["TORCH_ADAPTER_MODEL_ID", "TorchModelAdapter"]
