"""适用于 MFCC/Mel/Log-Mel 的轻量卷积基线。"""

from __future__ import annotations

from typing import Any

import torch
from torch import nn

from ser_lib.config.model import CNNBaselineConfig
from ser_lib.data.types import SERBatch, TensorSpec
from ser_lib.models.base import ModelOutput, SERModel
from ser_lib.models.registry import ModelDescriptor, model_registry
from ser_lib.models.specs import ModelSpec


class _MaskedBatchNorm1d(nn.BatchNorm1d):
    """BatchNorm1d that excludes padded time steps from training statistics.

    The class intentionally subclasses ``nn.BatchNorm1d`` so its persistent
    ``weight``, ``bias``, ``running_mean``, ``running_var`` and
    ``num_batches_tracked`` state remains compatible with existing CNN artifacts.
    """

    def forward(
        self,
        input: torch.Tensor,
        mask: torch.Tensor | None = None,
    ) -> torch.Tensor:
        if mask is None:
            return super().forward(input)
        if input.dim() != 3:
            raise ValueError("masked BatchNorm1d 期望 [B,C,T]")
        if mask.shape != (input.shape[0], input.shape[-1]):
            raise ValueError(
                f"masked BatchNorm1d mask 期望 {(input.shape[0], input.shape[-1])}，"
                f"实际 {tuple(mask.shape)}"
            )
        valid_mask = mask.to(device=input.device, dtype=torch.bool)
        time_major = input.transpose(1, 2)
        valid_values = time_major[valid_mask]
        if valid_values.shape[0] == 0:
            raise ValueError("masked BatchNorm1d 至少需要一个有效时间步")
        normalized = super().forward(valid_values)
        output = torch.zeros_like(time_major)
        output[valid_mask] = normalized
        return output.transpose(1, 2)


class CNNBaseline(SERModel):
    """保持时间分辨率的一维卷积分类器。

    输入 ``features`` 为 ``[B,F,T]``。优先使用显式 mask；当 collator 只提供
    ``lengths`` 时会据此构造连续前缀 mask。无效时间步在每个卷积块之间都被清零，
    并从 BatchNorm 统计中排除，因此同一有效序列的输出不依赖右侧 padding 长度或
    同 batch 中最长样本。随后根据有效位置做 masked mean pooling。
    """

    def __init__(
        self,
        feature_dim: int,
        num_classes: int,
        hidden_dim: int = 128,
        dropout: float = 0.2,
    ) -> None:
        super().__init__()
        if feature_dim < 1 or num_classes < 2 or hidden_dim < 1:
            raise ValueError("feature_dim/hidden_dim 必须为正，num_classes 必须 >= 2")
        if not 0.0 <= dropout < 1.0:
            raise ValueError("dropout 必须位于 [0, 1)")
        self.feature_dim = int(feature_dim)
        self.num_classes = int(num_classes)
        self.hidden_dim = int(hidden_dim)
        self.dropout = float(dropout)
        self.encoder = nn.Sequential(
            nn.Conv1d(feature_dim, hidden_dim, kernel_size=5, padding=2),
            _MaskedBatchNorm1d(hidden_dim),
            nn.ReLU(),
            nn.Conv1d(hidden_dim, hidden_dim, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.Dropout(dropout),
        )
        self.classifier = nn.Linear(hidden_dim, num_classes)

    @property
    def model_spec(self) -> ModelSpec:
        return _model_spec_from_config(self.model_config)

    @property
    def model_config(self) -> dict[str, int | float]:
        return CNNBaselineConfig(
            feature_dim=self.feature_dim,
            num_classes=self.num_classes,
            hidden_dim=self.hidden_dim,
            dropout=self.dropout,
        ).model_dump(mode="json")

    def _encode_masked(self, features: torch.Tensor, mask: torch.Tensor) -> torch.Tensor:
        valid = mask.to(device=features.device, dtype=torch.bool)
        weights = valid.to(features.dtype).unsqueeze(1)
        hidden = features * weights
        hidden = self.encoder[0](hidden)
        batch_norm = self.encoder[1]
        assert isinstance(batch_norm, _MaskedBatchNorm1d)
        hidden = batch_norm(hidden, valid)
        hidden = self.encoder[2](hidden)
        hidden = hidden * weights
        hidden = self.encoder[3](hidden)
        hidden = self.encoder[4](hidden)
        hidden = hidden * weights
        hidden = self.encoder[5](hidden)
        return hidden * weights

    def _resolve_mask(self, batch: SERBatch, features: torch.Tensor) -> torch.Tensor | None:
        mask = batch.masks.get("features")
        if mask is not None:
            return mask
        lengths = batch.lengths.get("features")
        if lengths is None:
            return None
        if lengths.shape != (features.shape[0],):
            raise ValueError(
                f"features lengths 期望 {(features.shape[0],)}，实际 {tuple(lengths.shape)}"
            )
        lengths = lengths.to(device=features.device)
        if torch.any(lengths <= 0):
            raise ValueError("CNNBaseline 的每个样本必须至少包含一个有效时间步")
        if torch.any(lengths > features.shape[-1]):
            raise ValueError("CNNBaseline features lengths 不能超过时间轴长度")
        positions = torch.arange(features.shape[-1], device=features.device).unsqueeze(0)
        return positions < lengths.unsqueeze(1)

    def forward(self, batch: SERBatch) -> ModelOutput:
        try:
            features = batch.inputs["features"]
        except KeyError:
            raise ValueError("CNNBaseline 需要 batch.inputs['features']") from None
        if features.dim() != 3 or features.shape[1] != self.feature_dim:
            raise ValueError(
                f"CNNBaseline 期望 [B,{self.feature_dim},T]，实际 {tuple(features.shape)}"
            )
        if features.shape[0] < 1 or features.shape[-1] < 1:
            raise ValueError("CNNBaseline 不接受空 batch 或零长度时间轴")
        if not features.is_floating_point():
            raise ValueError(f"CNNBaseline features 必须是浮点 tensor，实际 {features.dtype}")
        mask = self._resolve_mask(batch, features)
        if mask is None:
            encoded = self.encoder(features)
            embeddings = encoded.mean(dim=-1)
        else:
            if mask.shape != (features.shape[0], features.shape[-1]):
                raise ValueError(
                    f"features mask 期望 {(features.shape[0], features.shape[-1])}，"
                    f"实际 {tuple(mask.shape)}"
                )
            if torch.any(mask.sum(dim=-1) == 0):
                raise ValueError("CNNBaseline 的每个样本必须至少包含一个有效时间步")
            encoded = self._encode_masked(features, mask)
            weights = mask.to(device=encoded.device, dtype=encoded.dtype).unsqueeze(1)
            embeddings = (encoded * weights).sum(dim=-1) / weights.sum(dim=-1)
        return ModelOutput(logits=self.classifier(embeddings), embeddings=embeddings)


def _model_spec_from_config(params: dict[str, Any]) -> ModelSpec:
    return ModelSpec(
        model_id="cnn_baseline",
        required_inputs={
            "features": TensorSpec(layout="FT", feature_dim=int(params["feature_dim"]))
        },
        supports_masks=True,
        supports_variable_length=True,
        num_classes=int(params["num_classes"]),
    )


model_registry.register(
    "cnn_baseline",
    CNNBaseline,
    config_model=CNNBaselineConfig,
    descriptor=ModelDescriptor(
        id="cnn_baseline",
        display_name="CNN 基线",
        description="适用于 MFCC/Mel/Log-Mel 的轻量时间卷积分类器。",
        config_schema=CNNBaselineConfig.model_json_schema(),
        input_layouts={"features": "FT"},
    ),
    spec_factory=_model_spec_from_config,
)


__all__ = ["CNNBaseline", "CNNBaselineConfig"]