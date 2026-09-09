from pathlib import Path

import pytest

from ser_lib.artifacts import export_model_artifact, verify_model_artifact
from ser_lib.core import (
    CancellationToken,
    LifecycleEvent,
    OperationCancelled,
    ProgressEvent,
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


def _model() -> CNNBaseline:
    return CNNBaseline(feature_dim=16, num_classes=2, hidden_dim=4, dropout=0)


def _artifact(tmp_path: Path) -> Path:
    return export_model_artifact(
        tmp_path / "artifact",
        _model(),
        model_name="cnn_baseline",
        data_config=_config(tmp_path),
        labels={0: "neutral", 1: "happy"},
    )


def test_verify_reports_byte_progress_and_lifecycle(tmp_path: Path):
    directory = _artifact(tmp_path)
    events = []

    manifest = verify_model_artifact(directory, event_callback=events.append)

    assert manifest.model_name == "cnn_baseline"
    lifecycle = [event for event in events if isinstance(event, LifecycleEvent)]
    assert [(event.stage, event.status) for event in lifecycle] == [
        ("artifact_verify", "started"),
        ("artifact_verify", "completed"),
    ]
    progress = [event for event in events if isinstance(event, ProgressEvent)]
    assert progress
    assert progress[0].completed == 0
    assert progress[0].total is not None
    assert progress[0].total > 0
    assert progress[-1].completed == progress[-1].total
    assert all(event.stage == "artifact_verify" for event in progress)
    assert all(event.total == progress[0].total for event in progress)


def test_verify_can_cancel_during_hashing(tmp_path: Path):
    directory = _artifact(tmp_path)
    token = CancellationToken()
    events = []

    def callback(event):
        events.append(event)
        if isinstance(event, ProgressEvent) and event.completed > 0:
            token.cancel()

    with pytest.raises(OperationCancelled):
        verify_model_artifact(
            directory,
            event_callback=callback,
            cancellation=token,
        )

    lifecycle = [event for event in events if isinstance(event, LifecycleEvent)]
    assert lifecycle[-1].stage == "artifact_verify"
    assert lifecycle[-1].status == "cancelled"
    assert any(
        isinstance(event, ProgressEvent) and event.completed > 0
        for event in events
    )


def test_export_reports_phases_and_hash_progress(tmp_path: Path):
    events = []
    target = tmp_path / "artifact"

    result = export_model_artifact(
        target,
        _model(),
        model_name="cnn_baseline",
        data_config=_config(tmp_path),
        labels={0: "neutral", 1: "happy"},
        event_callback=events.append,
    )

    assert result == target
    assert target.is_dir()
    lifecycle = [event for event in events if isinstance(event, LifecycleEvent)]
    assert lifecycle[0].status == "started"
    assert lifecycle[-1].status == "completed"
    completed_phases = {
        event.details.get("phase")
        for event in lifecycle
        if event.status == "phase_completed"
    }
    assert completed_phases == {
        "write_weights",
        "write_metadata",
        "hash_files",
        "write_manifest",
        "commit",
    }
    progress = [
        event
        for event in events
        if isinstance(event, ProgressEvent)
        and event.stage == "artifact_export_hash"
    ]
    assert progress
    assert progress[0].completed == 0
    assert progress[0].total is not None
    assert progress[0].total > 0
    assert progress[-1].completed == progress[-1].total


def test_cancelled_export_removes_target_and_staging(tmp_path: Path):
    token = CancellationToken()
    events = []
    target = tmp_path / "artifact"

    def callback(event):
        events.append(event)
        if (
            isinstance(event, LifecycleEvent)
            and event.status == "phase_started"
            and event.details.get("phase") == "hash_files"
        ):
            token.cancel()

    with pytest.raises(OperationCancelled):
        export_model_artifact(
            target,
            _model(),
            model_name="cnn_baseline",
            data_config=_config(tmp_path),
            labels={0: "neutral", 1: "happy"},
            event_callback=callback,
            cancellation=token,
        )

    assert not target.exists()
    assert list(tmp_path.glob(".artifact.tmp-*")) == []
    lifecycle = [event for event in events if isinstance(event, LifecycleEvent)]
    assert lifecycle[-1].stage == "artifact_export"
    assert lifecycle[-1].status == "cancelled"
