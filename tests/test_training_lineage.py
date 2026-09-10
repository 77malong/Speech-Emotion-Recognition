from __future__ import annotations

import json
from pathlib import Path

import torch

from ser_lib.artifacts import export_model_artifact, inspect_model_artifact
from ser_lib.data import BatchingConfig, SERCollator, SERSample, TensorSpec
from ser_lib.data.config import AudioSettings, ComponentConfig, DataConfig
from ser_lib.engine import (
    ExperimentConfig,
    ModelConfig,
    Trainer,
    TrainerConfig,
    TrainingRunMetadata,
)
from ser_lib.engine.lineage import artifact_provenance_from_training_run
from ser_lib.models import CNNBaseline


def _data_config(tmp_path: Path) -> DataConfig:
    return DataConfig(
        manifest=tmp_path / "dataset.yaml",
        dataset_id="lineage-dataset",
        audio=AudioSettings(target_sample_rate=16000),
        representation=ComponentConfig(
            type="log_mel",
            params={"sample_rate": 16000, "n_mels": 4},
        ),
        batching=BatchingConfig(type="dynamic"),
        labels={0: {"en": "neutral"}, 1: {"en": "happy"}},
    )


def _experiment(tmp_path: Path) -> ExperimentConfig:
    return ExperimentConfig(
        data=_data_config(tmp_path),
        model=ModelConfig(
            type="cnn_baseline",
            params={
                "feature_dim": 4,
                "num_classes": 2,
                "hidden_dim": 6,
                "dropout": 0,
            },
        ),
        trainer=TrainerConfig(
            epochs=1,
            device="cpu",
            checkpoint_dir=tmp_path / "checkpoints",
        ),
        output_dir=tmp_path / "run",
    )


def _batch():
    samples = [
        SERSample("a", {"features": torch.randn(4, 5)}, {"features": 5}, 0, {}),
        SERSample("b", {"features": torch.randn(4, 3)}, {"features": 3}, 1, {}),
    ]
    return SERCollator(
        {"features": TensorSpec(layout="FT", feature_dim=4)},
        BatchingConfig(type="dynamic"),
    )(samples)


def _model() -> CNNBaseline:
    return CNNBaseline(feature_dim=4, num_classes=2, hidden_dim=6, dropout=0)


def test_trainer_from_experiment_builds_json_safe_lineage_without_dataset_io(tmp_path: Path):
    fingerprint = "a" * 64
    trainer = Trainer.from_experiment(
        _model(),
        _experiment(tmp_path),
        run_id="lineage-run",
        dataset_fingerprint=fingerprint,
    )

    metadata = trainer.run_metadata

    assert isinstance(metadata, TrainingRunMetadata)
    assert metadata.run_id == "lineage-run"
    assert metadata.dataset_id == "lineage-dataset"
    assert metadata.dataset_fingerprint == fingerprint
    assert metadata.model_id == "cnn_baseline"
    assert metadata.seed == 42
    assert metadata.device == "cpu"
    assert metadata.config["model"]["type"] == "cnn_baseline"
    json.dumps(metadata.to_dict())


def test_checkpoint_and_artifact_preserve_training_lineage(tmp_path: Path):
    fingerprint = "b" * 64
    model = _model()
    experiment = _experiment(tmp_path)
    trainer = Trainer.from_experiment(
        model,
        experiment,
        run_id="lineage-run",
        dataset_fingerprint=fingerprint,
    )
    metadata = trainer.run_metadata
    assert metadata is not None

    result = trainer.fit([_batch()])
    assert result.status == "completed"

    checkpoint_path = experiment.trainer.checkpoint_dir / "last.pt"
    payload = torch.load(checkpoint_path, map_location="cpu", weights_only=False)
    saved_lineage = payload["metadata"]["run_metadata"]
    assert saved_lineage["run_id"] == "lineage-run"
    assert saved_lineage["dataset_id"] == "lineage-dataset"
    assert saved_lineage["dataset_fingerprint"] == fingerprint
    assert saved_lineage["model_id"] == "cnn_baseline"

    artifact_dir = export_model_artifact(
        tmp_path / "artifact",
        model,
        model_name="cnn_baseline",
        data_config=experiment.data,
        labels={0: "neutral", 1: "happy"},
        metadata=artifact_provenance_from_training_run(metadata),
    )
    manifest = inspect_model_artifact(artifact_dir)
    assert manifest.metadata["source_run_id"] == "lineage-run"
    assert manifest.metadata["dataset_id"] == "lineage-dataset"
    assert manifest.metadata["dataset_fingerprint"] == fingerprint


def test_resume_restores_saved_lineage_when_run_id_is_not_explicit(tmp_path: Path):
    fingerprint = "c" * 64
    experiment = _experiment(tmp_path)
    source = Trainer.from_experiment(
        _model(),
        experiment,
        run_id="original-run",
        dataset_fingerprint=fingerprint,
    )
    source.fit([_batch()])

    resumed = Trainer.from_experiment(_model(), experiment)
    resumed.resume_from(experiment.trainer.checkpoint_dir / "last.pt")
    metadata = resumed.run_metadata

    assert resumed.run_id == "original-run"
    assert metadata is not None
    assert metadata.run_id == "original-run"
    assert metadata.dataset_fingerprint == fingerprint
    assert metadata.created_at.tzinfo is not None
