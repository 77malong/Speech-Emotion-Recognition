from pathlib import Path

import pytest

import ser_lib.artifacts.loader as loader_module
from ser_lib.artifacts import (
    export_model_artifact,
    inspect_model_artifact,
    verify_model_artifact,
)
from ser_lib.data.config import AudioSettings, BatchingConfig, ComponentConfig, DataConfig
from ser_lib.models import CNNBaseline


def _config(tmp_path: Path) -> DataConfig:
    return DataConfig(
        manifest=tmp_path / "unused-dataset.yaml",
        audio=AudioSettings(target_sample_rate=16000),
        representation=ComponentConfig(
            type="log_mel",
            params={
                "sample_rate": 16000,
                "n_mels": 16,
                "n_fft": 128,
                "win_length": 128,
                "hop_length": 64,
                "f_max": 8000,
            },
        ),
        batching=BatchingConfig(type="dynamic"),
        labels={0: {"en": "neutral"}, 1: {"en": "happy"}},
    )


def _artifact(tmp_path: Path) -> Path:
    model = CNNBaseline(feature_dim=16, num_classes=2, hidden_dim=4, dropout=0)
    return export_model_artifact(
        tmp_path / "artifact",
        model,
        model_name="cnn_baseline",
        model_params={
            "feature_dim": 16,
            "num_classes": 2,
            "hidden_dim": 4,
            "dropout": 0,
        },
        data_config=_config(tmp_path),
        labels={0: "neutral", 1: "happy"},
        metrics={"uar": 0.75},
        metadata={"dataset_fingerprint": "demo-fingerprint"},
    )


def test_artifact_inspect_never_calls_sha256(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    directory = _artifact(tmp_path)

    def forbidden_hash(path: Path) -> str:
        raise AssertionError(f"inspect must not hash {path}")

    monkeypatch.setattr(loader_module, "_sha256", forbidden_hash)

    manifest = inspect_model_artifact(directory)

    assert manifest.model_name == "cnn_baseline"
    assert manifest.metrics == {"uar": 0.75}
    assert manifest.metadata["dataset_fingerprint"] == "demo-fingerprint"


def test_tampered_weights_pass_fast_inspect_but_fail_full_verify(tmp_path: Path):
    directory = _artifact(tmp_path)
    weights = directory / "weights.safetensors"
    with weights.open("ab") as stream:
        stream.write(b"tampered")

    inspected = inspect_model_artifact(directory)
    assert inspected.model_name == "cnn_baseline"

    with pytest.raises(ValueError, match="SHA-256"):
        verify_model_artifact(directory)


def test_artifact_inspect_still_validates_lightweight_metadata(tmp_path: Path):
    directory = _artifact(tmp_path)
    (directory / "metrics.json").write_text('{"uar": 0.1}', encoding="utf-8")

    with pytest.raises(ValueError, match="metrics.json"):
        inspect_model_artifact(directory)


def test_artifact_inspect_requires_declared_component_files(tmp_path: Path):
    directory = _artifact(tmp_path)
    (directory / "weights.safetensors").unlink()

    with pytest.raises(FileNotFoundError, match="模型权重不存在"):
        inspect_model_artifact(directory)
