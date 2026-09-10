from __future__ import annotations

from pathlib import Path

import pytest

from ser_lib.artifacts import export_model_artifact
from ser_lib.config import AudioSettings, BatchingConfig, ComponentConfig, DataConfig
from ser_lib.models import CNNBaseline


def _data_config(tmp_path: Path, *, n_mels: int) -> DataConfig:
    return DataConfig(
        manifest=tmp_path / "dataset.yaml",
        audio=AudioSettings(target_sample_rate=16000),
        representation=ComponentConfig(
            type="log_mel",
            params={"sample_rate": 16000, "n_mels": n_mels},
        ),
        batching=BatchingConfig(type="dynamic"),
        labels={0: {"en": "neutral"}, 1: {"en": "happy"}},
    )


def test_export_rejects_incompatible_preprocessing_before_creating_target(tmp_path: Path):
    target = tmp_path / "bad-artifact"
    model = CNNBaseline(feature_dim=16, num_classes=2, hidden_dim=8, dropout=0.0)

    with pytest.raises(Exception, match="feature|输入|维度|兼容"):
        export_model_artifact(
            target,
            model,
            model_name="cnn_baseline",
            data_config=_data_config(tmp_path, n_mels=32),
            labels={0: "neutral", 1: "happy"},
        )

    assert not target.exists()


def test_export_allows_compatible_preprocessing(tmp_path: Path):
    target = tmp_path / "good-artifact"
    model = CNNBaseline(feature_dim=16, num_classes=2, hidden_dim=8, dropout=0.0)

    exported = export_model_artifact(
        target,
        model,
        model_name="cnn_baseline",
        data_config=_data_config(tmp_path, n_mels=16),
        labels={0: "neutral", 1: "happy"},
    )

    assert exported == target
    assert (target / "manifest.json").is_file()
