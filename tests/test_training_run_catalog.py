from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest
import torch
from pydantic import ValidationError

from ser_lib.core import CancellationToken, OperationCancelled, ProgressEvent
from ser_lib.data import BatchingConfig, SERCollator, SERSample, TensorSpec
from ser_lib.data.config import AudioSettings, ComponentConfig, DataConfig
from ser_lib.engine import (
    ExperimentConfig,
    ModelConfig,
    Trainer,
    TrainerConfig,
    TrainingRunInfo,
    load_training_run_info,
    scan_training_runs,
)
from ser_lib.models import CNNBaseline
from ser_lib.services import TrainingService


def _experiment(tmp_path: Path) -> ExperimentConfig:
    data = DataConfig(
        manifest=tmp_path / "dataset.yaml",
        audio=AudioSettings(target_sample_rate=16000),
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
    trainer = TrainingService.create_trainer(
        _model(),
        _experiment(tmp_path),
        run_id="run-catalog-demo",
        dataset_id="manifest-demo",
        dataset_fingerprint="d" * 64,
    )
    result = TrainingService.run(trainer, [_batch()])
    return trainer, result


def test_training_service_persists_and_inspects_run_record(tmp_path: Path):
    trainer, result = _completed_run(tmp_path)
    run_dir = tmp_path / "runs" / "demo"

    info = TrainingService.save_run(run_dir, trainer, result)

    assert isinstance(info, TrainingRunInfo)
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

    by_directory = TrainingService.inspect_run(run_dir)
    by_file = load_training_run_info(run_dir / "run.json")
    assert by_directory == by_file == info


def test_run_record_tracks_actual_directory_after_move(tmp_path: Path):
    trainer, result = _completed_run(tmp_path)
    original = tmp_path / "runs" / "original"
    TrainingService.save_run(original, trainer, result)
    moved = tmp_path / "runs" / "moved"
    original.rename(moved)

    loaded = load_training_run_info(moved)

    assert loaded.directory == moved.as_posix()
    assert loaded.run_id == "run-catalog-demo"


def test_run_catalog_is_lightweight_isolates_failures_and_emits_progress(tmp_path: Path):
    trainer, result = _completed_run(tmp_path)
    runs_root = tmp_path / "runs"
    good = runs_root / "good"
    TrainingService.save_run(good, trainer, result)
    bad = runs_root / "nested" / "bad"
    bad.mkdir(parents=True)
    (bad / "run.json").write_text("{broken", encoding="utf-8")
    events = []

    shallow = TrainingService.scan_runs(runs_root, event_callback=events.append)
    assert shallow.total == 1
    assert len(shallow.runs) == 1
    assert shallow.failures == ()

    events.clear()
    catalog = TrainingService.scan_runs(
        runs_root,
        recursive=True,
        event_callback=events.append,
    )
    assert catalog.total == 2
    assert [run.run_id for run in catalog.runs] == ["run-catalog-demo"]
    assert len(catalog.failures) == 1
    assert catalog.failures[0].error_type == "JSONDecodeError"
    progress = [event for event in events if isinstance(event, ProgressEvent)]
    assert [event.completed for event in progress] == [1, 2]
    assert all(event.total == 2 for event in progress)
    json.dumps(catalog.to_dict())

    root_catalog = scan_training_runs(good)
    assert root_catalog.total == 1
    assert root_catalog.runs[0].directory == good.as_posix()


def test_run_catalog_supports_fail_fast_cancellation_and_missing_root(tmp_path: Path):
    bad = tmp_path / "runs" / "bad"
    bad.mkdir(parents=True)
    (bad / "run.json").write_text("{broken", encoding="utf-8")

    with pytest.raises(json.JSONDecodeError):
        scan_training_runs(tmp_path / "runs", fail_fast=True)

    token = CancellationToken()
    token.cancel()
    with pytest.raises(OperationCancelled):
        scan_training_runs(tmp_path / "runs", cancellation=token)

    with pytest.raises(NotADirectoryError):
        scan_training_runs(tmp_path / "missing")


def test_run_record_validation_rejects_corruption(tmp_path: Path):
    trainer, result = _completed_run(tmp_path)
    run_dir = tmp_path / "run"
    info = TrainingService.save_run(run_dir, trainer, result)
    payload = info.to_dict()

    payload["schema_version"] = 2
    with pytest.raises(ValidationError):
        TrainingRunInfo.from_dict(payload)

    payload = info.to_dict()
    payload["created_at"] = "2026-09-09T00:00:00"
    with pytest.raises(ValidationError, match="时区"):
        TrainingRunInfo.from_dict(payload)

    payload = info.to_dict()
    payload["unexpected"] = True
    with pytest.raises(ValidationError):
        TrainingRunInfo.from_dict(payload)

    list_record = tmp_path / "list.json"
    list_record.write_text("[]", encoding="utf-8")
    with pytest.raises(ValueError, match="顶层"):
        load_training_run_info(list_record)

    with pytest.raises(FileNotFoundError):
        load_training_run_info(tmp_path / "missing.json")


def test_run_record_rejects_mismatched_ids_and_untracked_trainer(tmp_path: Path):
    trainer, result = _completed_run(tmp_path)
    metadata = TrainingService.get_run_metadata(trainer)
    assert metadata is not None

    with pytest.raises(ValueError, match="run_id"):
        TrainingRunInfo.from_training(
            tmp_path / "run",
            metadata,
            replace(result, run_id="different-run"),
        )

    direct = Trainer(_model(), TrainerConfig(epochs=1))
    direct_result = TrainingService.run(direct, [_batch()])
    with pytest.raises(ValueError, match="TrainingRunMetadata"):
        TrainingService.save_run(tmp_path / "direct", direct, direct_result)
