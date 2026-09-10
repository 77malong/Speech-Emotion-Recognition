from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
import torch

from ser_lib.artifacts import (
    inspect_model_artifact,
    load_model_artifact,
    verify_model_artifact,
)
from ser_lib.data import DatasetManifest
from ser_lib.engine import load_checkpoint, load_experiment_config
from ser_lib.models import CNNBaseline


_FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "release_compat"


def _load_json(name: str) -> dict:
    return json.loads((_FIXTURE_DIR / name).read_text(encoding="utf-8"))


def _cnn() -> CNNBaseline:
    return CNNBaseline(feature_dim=4, num_classes=2, hidden_dim=6, dropout=0.0)


def test_legacy_experiment_v1_fixture_loads_with_relative_paths_preserved():
    config = load_experiment_config(_FIXTURE_DIR / "experiment_v1.yaml")

    assert config.schema_version == 1
    assert config.data.manifest == (_FIXTURE_DIR / "dataset_v1.yaml").resolve()
    assert config.output_dir == (_FIXTURE_DIR / "run").resolve()
    assert config.trainer.checkpoint_dir == (_FIXTURE_DIR / "checkpoints").resolve()
    assert config.model.type == "cnn_baseline"
    assert config.model.params == {
        "feature_dim": 4,
        "num_classes": 2,
        "hidden_dim": 6,
        "dropout": 0.0,
    }


def test_legacy_dataset_fixture_without_schema_version_still_reads():
    manifest = DatasetManifest.load(_FIXTURE_DIR / "dataset_v1.yaml")

    assert manifest.meta.schema_version == 1
    assert manifest.meta.dataset_id == "legacy-release-fixture"
    records = manifest.get_records("train")
    assert len(records) == 1
    assert records[0].uid == "legacy-1"
    assert records[0].label == 0
    assert records[0].speaker_id == "speaker-1"
    assert records[0].metadata == {"source": "release-compat"}
    assert manifest.resolve_audio_path(records[0]) == (
        _FIXTURE_DIR / "audio" / "legacy.wav"
    ).resolve()


def test_legacy_checkpoint_v1_fixture_restores_model_state(tmp_path: Path):
    payload = _load_json("checkpoint_v1.json")
    source = _cnn()
    source_state = {
        name: value.detach().clone() for name, value in source.state_dict().items()
    }
    payload["model_state"] = source_state

    checkpoint = tmp_path / "legacy-v1.pt"
    torch.save(payload, checkpoint)

    target = _cnn()
    with torch.no_grad():
        for parameter in target.parameters():
            parameter.zero_()

    loaded = load_checkpoint(checkpoint, target, restore_rng=True)

    assert loaded["format_version"] == 1
    assert loaded["epoch"] == 3
    assert loaded["metrics"] == {"uar": 0.5}
    assert loaded["metadata"] == {"fixture": "pre-stage12"}
    for name, expected in source_state.items():
        assert torch.equal(target.state_dict()[name], expected)


def test_legacy_artifact_v1_requires_explicit_pickle_authorization(tmp_path: Path):
    artifact = tmp_path / "artifact-v1"
    artifact.mkdir()
    source = _cnn()
    weights = artifact / "model_state.pt"
    torch.save(source.state_dict(), weights)

    raw_manifest = _load_json("artifact_v1_manifest.json")
    raw_manifest["weights_sha256"] = hashlib.sha256(weights.read_bytes()).hexdigest()
    (artifact / "manifest.json").write_text(
        json.dumps(raw_manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    inspected = inspect_model_artifact(artifact)
    assert inspected.schema_version == 1
    assert inspected.weights_file == "model_state.pt"
    assert inspected.weights_format == "pytorch"
    assert verify_model_artifact(artifact) == inspected

    with pytest.raises(ValueError, match="allow_legacy_pickle=True"):
        load_model_artifact(artifact)

    loaded = load_model_artifact(artifact, allow_legacy_pickle=True)
    assert loaded.manifest.schema_version == 1
    assert loaded.manifest.library_version == "0.1.0"
    assert loaded.manifest.metadata == {"fixture": "pre-stage12"}
    for name, expected in source.state_dict().items():
        assert torch.equal(loaded.model.state_dict()[name], expected)
