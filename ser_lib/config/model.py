"""内置 SER 模型、Hugging Face 与通用 Torch adapter 的用户配置 schema。

本模块只定义可序列化配置，不导入 torch、模型实现或 transformers。
"""

from __future__ import annotations

import json
from typing import Any, Literal

from pydantic import Field, model_validator

from ser_lib.config.base import StrictConfig


class ModelConfig(StrictConfig):
    """注册表模型及其构造参数。"""

    type: str = Field(min_length=1)
    params: dict[str, Any] = Field(default_factory=dict)


class CNNBaselineConfig(StrictConfig):
    feature_dim: int = Field(ge=1)
    num_classes: int = Field(ge=2)
    hidden_dim: int = Field(default=128, ge=1)
    dropout: float = Field(default=0.2, ge=0, lt=1)


class GRUBaselineConfig(StrictConfig):
    feature_dim: int = Field(ge=1)
    num_classes: int = Field(ge=2)
    hidden_dim: int = Field(default=128, ge=1)
    num_layers: int = Field(default=1, ge=1)
    bidirectional: bool = True
    dropout: float = Field(default=0.0, ge=0, lt=1)

    @model_validator(mode="after")
    def _dropout_requires_multiple_layers(self) -> "GRUBaselineConfig":
        if self.num_layers == 1 and self.dropout != 0:
            raise ValueError("num_layers=1 时 dropout 必须为 0")
        return self


class TransformerBaselineConfig(StrictConfig):
    feature_dim: int = Field(ge=1)
    num_classes: int = Field(ge=2)
    d_model: int = Field(default=128, ge=4)
    num_heads: int = Field(default=4, ge=1)
    num_layers: int = Field(default=2, ge=1)
    feedforward_dim: int = Field(default=256, ge=1)
    dropout: float = Field(default=0.1, ge=0, lt=1)
    activation: Literal["relu", "gelu"] = "gelu"
    norm_first: bool = False

    @model_validator(mode="after")
    def _validate_attention_dimensions(self) -> "TransformerBaselineConfig":
        if self.d_model % self.num_heads:
            raise ValueError("d_model 必须能被 num_heads 整除")
        if self.feedforward_dim < self.d_model:
            raise ValueError("feedforward_dim 必须 >= d_model")
        return self


class HFProcessorConfig(StrictConfig):
    """可离线重建的 HF waveform feature extractor 快照。"""

    class_name: Literal["Wav2Vec2FeatureExtractor"]
    config: dict[str, Any]

    @model_validator(mode="after")
    def _validate_json_snapshot(self) -> "HFProcessorConfig":
        try:
            json.dumps(self.config, allow_nan=False)
        except (TypeError, ValueError) as exc:
            raise ValueError("processor config 必须是有限数值组成的 JSON-safe 数据") from exc
        sampling_rate = self.config.get("sampling_rate")
        if not isinstance(sampling_rate, int) or sampling_rate < 1000:
            raise ValueError("processor config 必须包含合法 sampling_rate")
        feature_size = self.config.get("feature_size", 1)
        if feature_size != 1:
            raise ValueError("首期 HF waveform processor 只支持 feature_size=1")
        return self


class HFAudioClassifierConfig(StrictConfig):
    """Hugging Face 音频模型配置；定义本身不依赖 transformers。"""

    num_classes: int = Field(ge=2)
    pretrained_model_name_or_path: str | None = None
    encoder_config: dict[str, Any] | None = None
    local_files_only: bool = True
    revision: str | None = None
    freeze_encoder: bool = False
    dropout: float = Field(default=0.1, ge=0, lt=1)
    pooling: Literal["mean", "max"] = "mean"
    expected_sample_rate: int = Field(default=16000, ge=1000, le=192000)
    strategy: Literal["encoder_head", "audio_classification"] = "encoder_head"
    reset_classifier_head: bool = False
    label_names: dict[int, str] | None = None
    processor_name_or_path: str | None = None
    processor_config: HFProcessorConfig | None = None
    processor_revision: str | None = None

    @model_validator(mode="after")
    def _validate_sources_and_head(self) -> "HFAudioClassifierConfig":
        supplied = sum(
            value is not None
            for value in (self.pretrained_model_name_or_path, self.encoder_config)
        )
        if supplied != 1:
            raise ValueError(
                "pretrained_model_name_or_path 与 encoder_config 必须且只能提供一个"
            )
        if self.pretrained_model_name_or_path == "":
            raise ValueError("pretrained_model_name_or_path 不能为空")

        processor_sources = sum(
            value is not None
            for value in (self.processor_name_or_path, self.processor_config)
        )
        if processor_sources > 1:
            raise ValueError("processor_name_or_path 与 processor_config 最多提供一个")
        if self.processor_name_or_path == "":
            raise ValueError("processor_name_or_path 不能为空")
        if self.processor_config is not None:
            sampling_rate = int(self.processor_config.config["sampling_rate"])
            if sampling_rate != self.expected_sample_rate:
                raise ValueError(
                    "processor sampling_rate 与 expected_sample_rate 不一致: "
                    f"{sampling_rate} != {self.expected_sample_rate}"
                )

        if self.label_names is not None:
            if sorted(self.label_names) != list(range(self.num_classes)):
                raise ValueError("label_names 必须从 0 开始连续并覆盖 num_classes")
            if any(not value for value in self.label_names.values()):
                raise ValueError("label_names 不允许空标签")
            if len(set(self.label_names.values())) != len(self.label_names):
                raise ValueError("label_names 必须唯一")

        if self.strategy == "audio_classification":
            if self.label_names is None:
                raise ValueError("audio_classification strategy 必须显式提供 label_names")
        elif self.reset_classifier_head:
            raise ValueError("reset_classifier_head 仅适用于 audio_classification strategy")
        return self


TorchDTypeName = Literal[
    "float16",
    "float32",
    "float64",
    "bfloat16",
    "int8",
    "int16",
    "int32",
    "int64",
    "uint8",
    "bool",
]
TorchLayoutName = Literal["T", "FT", "TD", "D", "CFT"]


class TorchTensorSpecConfig(StrictConfig):
    """Torch adapter 所需 TensorSpec 的 JSON-safe 表示。"""

    layout: TorchLayoutName
    dtype: TorchDTypeName = "float32"
    feature_dim: int | None = Field(default=None, ge=1)
    pad_value: float = 0.0

    @model_validator(mode="after")
    def _waveform_has_no_feature_dim(self) -> "TorchTensorSpecConfig":
        if self.layout == "T" and self.feature_dim is not None:
            raise ValueError("layout='T' 不允许配置 feature_dim")
        return self


class TorchOutputMappingConfig(StrictConfig):
    """普通 nn.Module 输出到 ModelOutput 的显式选择器。

    ``logits=None`` 表示模块本身直接返回 logits tensor；字符串选择器可读取
    mapping key、tuple/list 索引或对象属性，并支持 ``a.b.0`` 形式的嵌套路径。
    """

    logits: str | None = Field(default=None, min_length=1)
    embeddings: str | None = Field(default=None, min_length=1)
    loss: str | None = Field(default=None, min_length=1)


class TorchModelAdapterConfig(StrictConfig):
    """普通 ``torch.nn.Module`` 的可移植 SER adapter 配置。

    ``factory_id=None`` 只允许进程内手工包装，可用于训练、评估、推理与可信
    checkpoint；可分发 artifact 必须提供已注册 factory ID。配置中不接受 callable，
    artifact 只保存 JSON 数据与注册 ID。
    """

    factory_id: str | None = Field(default=None, min_length=1)
    factory_params: dict[str, Any] = Field(default_factory=dict)
    input_map: dict[str, str] = Field(min_length=1)
    output: TorchOutputMappingConfig = Field(default_factory=TorchOutputMappingConfig)
    required_inputs: dict[str, TorchTensorSpecConfig] = Field(min_length=1)
    supports_masks: bool = False
    supports_variable_length: bool = False
    num_classes: int = Field(ge=2)
    expected_sample_rate: int | None = Field(default=None, ge=1000, le=192000)
    freeze_module: bool = False

    @model_validator(mode="after")
    def _validate_adapter_contract(self) -> "TorchModelAdapterConfig":
        try:
            json.dumps(self.factory_params, allow_nan=False)
        except (TypeError, ValueError) as exc:
            raise ValueError("factory_params 必须是有限数值组成的 JSON-safe 数据") from exc

        mapped_inputs: set[str] = set()
        for argument, source in self.input_map.items():
            if not argument:
                raise ValueError("input_map 的模块参数名不能为空")
            if source == "labels":
                continue
            if "." not in source:
                raise ValueError(
                    "input_map source 必须是 inputs.<key>、masks.<key>、lengths.<key> 或 labels"
                )
            namespace, key = source.split(".", 1)
            if namespace not in {"inputs", "masks", "lengths"} or not key:
                raise ValueError(
                    "input_map source 必须是 inputs.<key>、masks.<key>、lengths.<key> 或 labels"
                )
            if key not in self.required_inputs:
                raise ValueError(f"input_map 引用了未声明的 required_inputs key: {key!r}")
            if namespace == "inputs":
                mapped_inputs.add(key)
            elif namespace == "masks" and not self.supports_masks:
                raise ValueError("input_map 使用 masks.* 时 supports_masks 必须为 True")
            elif namespace == "lengths" and not self.supports_variable_length:
                raise ValueError(
                    "input_map 使用 lengths.* 时 supports_variable_length 必须为 True"
                )

        missing = set(self.required_inputs) - mapped_inputs
        if missing:
            raise ValueError(f"required_inputs 必须全部映射到模块输入: {sorted(missing)}")
        return self


__all__ = [
    "ModelConfig",
    "CNNBaselineConfig",
    "GRUBaselineConfig",
    "TransformerBaselineConfig",
    "HFProcessorConfig",
    "HFAudioClassifierConfig",
    "TorchDTypeName",
    "TorchLayoutName",
    "TorchTensorSpecConfig",
    "TorchOutputMappingConfig",
    "TorchModelAdapterConfig",
]
