"""内置 SER 模型的用户配置 schema；本模块不加载模型实现或 transformers。"""

from __future__ import annotations

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


class HFAudioClassifierConfig(StrictConfig):
    """Hugging Face 音频编码器分类器配置；定义本身不依赖 transformers。"""

    num_classes: int = Field(ge=2)
    pretrained_model_name_or_path: str | None = None
    encoder_config: dict[str, Any] | None = None
    local_files_only: bool = True
    revision: str | None = None
    freeze_encoder: bool = False
    dropout: float = Field(default=0.1, ge=0, lt=1)
    pooling: Literal["mean", "max"] = "mean"
    expected_sample_rate: int = Field(default=16000, ge=1000, le=192000)

    @model_validator(mode="after")
    def _exactly_one_encoder_source(self) -> "HFAudioClassifierConfig":
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
        return self


__all__ = [
    "ModelConfig",
    "CNNBaselineConfig",
    "GRUBaselineConfig",
    "TransformerBaselineConfig",
    "HFAudioClassifierConfig",
]
