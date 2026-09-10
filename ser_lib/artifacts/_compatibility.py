"""Shared static model/preprocessing compatibility checks for artifacts."""

from __future__ import annotations

from ser_lib.data.config import DataConfig
from ser_lib.data.pipeline import build_components
from ser_lib.engine.compatibility import validate_compatibility
from ser_lib.models.base import SERModel


def validate_artifact_compatibility(
    model: SERModel,
    data_config: DataConfig,
    *,
    num_classes: int,
) -> None:
    """Reject artifact combinations that cannot satisfy the model input contract."""
    _, pipeline = build_components(data_config, train=False)
    validate_compatibility(
        pipeline.output_specs,
        model.model_spec,
        data_config.batching,
        num_classes=num_classes,
        sample_rate=data_config.audio.target_sample_rate,
    )


__all__ = ["validate_artifact_compatibility"]
