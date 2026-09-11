from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest
import torch
from pydantic import ValidationError

from ser_lib.config import BatchingConfig
from ser_lib.data import SERCollator, SERSample, TensorSpec
from ser_lib.config import AudioConfig, ComponentConfig, DataConfig
from ser_lib.engine import (
    ExperimentConfig,
    ModelConfig,
    Trainer,
    TrainerConfig,
    TrainingRecord,
    load_training_record,
    write_training_record,
)
from ser_lib.models import CNNBaseline


def _experiment(tmp_path: Path) -> ExperimentConfig:
    data = DataConfig(
        manifest=tmp_path / "dataset.yaml",
        audio=AudioConfig(target_sample_rate=16000),
        representation=ComponentConfig(
            type="log_mel",
            params={"sample_rate": 16000, "n_mels": 4},
        ),
        batching=BatchingConfig(type="dynamic"),
        labels={0: {"en": "neutral"}, 1: {"en": "happy"}},
    )
    return ExperimentConfig(
        data=data,
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
            checkpoint_dir=tmp_path / "checkpoints",
        ),
        output_dir=tmp_path / "run",
    )


def _model() -> CNNBaseline:
    return CNNBaseline(feature_dim=4, num_classes=2, hidden_dim=6, dropout=0)


def _batch():
    samples = [
        SERSample("a", {"features": torch.randn(4, 5)}, {"features": 5}, 0, {}),
        SERSample("b", {"features": torch.randn(4, 3)}, {"features": 3}, 1, {}),
    ]
    return SERCollator(
        {"features": TensorSpec(layout="FT", feature_dim=4)},
        BatchingConfig(type="dynamic"),
    )(samples)


def _completed_run(tmp_path: Path):
    trainer = Trainer.from_experiment(
        _model(),
        _experiment(tmp_path),
        run_id="run-catalog-demo",
        dataset_id="manifest-demo",
        dataset_fingerprint="d" * 64,
    )
    result = trainer.fit([_batch()])
    return trainer, result


def _save_run(directory: Path, trainer: Trainer, result) -> TrainingRecord:
    metadata = trainer.run_metadata
    if metadata is None:
        raise ValueError("Trainer 没有 TrainingMetadata，无法保存训练运行记录")
    path = write_training_record(directory, metadata, result)
    return load_training_record(path)


def test_direct_api_persists_and_inspects_run_record(tmp_path: Path):
    trainer, result = _completed_run(tmp_path)
    run_dir = tmp_path / "runs" / "demo"

    info = _save_run(run_dir, trainer, result)

    assert isinstance(info, TrainingRecord)
    assert info.run_id == "run-catalog-demo"
    assert info.dataset_id == "manifest-demo"
    assert info.dataset_fingerprint == "d" * 64
    assert info.status == "completed"
    assert info.epochs_completed == 1
    assert info.last_epoch == 1
    assert info.model_id == "cnn_baseline"
    assert info.directory == run_dir.as_posix()
    assert info.last_checkpoint is not None
    assert (run_dir / "run.json").is_file()
    json.dumps(info.to_dict())

    by_directory = load_training_record(run_dir)
    by_file = load_training_record(run_dir / "run.json")
    assert by_directory == by_file == info


def test_run_record_tracks_actual_directory_after_move(tmp_path: Path):
    trainer, result = _completed_run(tmp_path)
    original = tmp_path / "runs" / "original"
    _save_run(original, trainer, result)
    moved = tmp_path / "runs" / "moved"
    original.rename(moved)

    loaded = load_training_record(moved)

    assert loaded.directory == moved.as_posix()
    assert loaded.run_id == "run-catalog-demo"


def test_run_record_validation_rejects_corruption(tmp_path: Path):
    trainer, result = _completed_run(tmp_path)
    run_dir = tmp_path / "run"
    info = _save_run(run_dir, trainer, result)
    payload = info.to_dict()

    payload["schema_version"] = 2
    with pytest.raises(ValidationError):
        TrainingRecord.from_dict(payload)

    payload = info.to_dict()
    payload["created_at"] = "2026-09-09T00:00:00"
    with pytest.raises(ValidationError, match="时区"):
        TrainingRecord.from_dict(payload)

    payload = info.to_dict()
    payload["unexpected"] = True
    with pytest.raises(ValidationError):
        TrainingRecord.from_dict(payload)

    list_record = tmp_path / "list.json"
    list_record.write_text("[]", encoding="utf-8")
    with pytest.raises(ValueError, match="顶层"):
        load_training_record(list_record)

    with pytest.raises(FileNotFoundError):
        load_training_record(tmp_path / "missing.json")


def test_run_record_rejects_mismatched_ids_and_untracked_trainer(tmp_path: Path):
    trainer, result = _completed_run(tmp_path)
    metadata = trainer.run_metadata
    assert metadata is not None

    with pytest.raises(ValueError, match="run_id"):
        TrainingRecord.from_training(
            tmp_path / "run",
            metadata,
            replace(result, run_id="different-run"),
        )

    direct = Trainer(_model(), TrainerConfig(epochs=1))
    direct_result = direct.fit([_batch()])
    with pytest.raises(ValueError, match="TrainingMetadata"):
        _save_run(tmp_path / "direct", direct, direct_result)
