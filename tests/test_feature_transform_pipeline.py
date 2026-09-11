from __future__ import annotations

import torch

from ser_lib.data.config import ComponentConfig
from ser_lib.data.pipeline import _build_feature_transforms
from ser_lib.data.types import TensorSpec


def test_feature_transform_pipeline_only_applies_to_temporal_inputs():
    specs = {
        "features": TensorSpec(layout="FT", feature_dim=4),
        "global": TensorSpec(layout="D", feature_dim=3),
    }
    pipeline = _build_feature_transforms(
        [
            ComponentConfig(
                type="spec_masking",
                params={"time_mask_param": 2, "freq_mask_param": 2},
                probability=1.0,
            )
        ],
        specs=specs,
        allow_random=True,
    )
    assert pipeline is not None

    temporal = torch.arange(24, dtype=torch.float32).reshape(4, 6)
    global_vector = torch.tensor([1.0, 2.0, 3.0])
    torch.manual_seed(11)

    outputs = pipeline({"features": temporal, "global": global_vector})

    assert outputs["features"].shape == temporal.shape
    assert torch.equal(outputs["global"], global_vector)
