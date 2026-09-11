"""Current-format contracts and rejection before runtime state mutation."""

import json
from pathlib import Path

import pytest
import torch
import yaml
from pydantic import ValidationError

from ser_lib.artifacts import export_model_artifact, load_model_artifact, verify_model_artifact
from ser_lib.config import DataConfig, ExperimentConfig, load_data_config
from ser_lib.data.manifest import DatasetManifest
from ser_lib.foundation.errors import ManifestError
from ser_lib.engine import load_checkpoint, save_checkpoint
from ser_lib.foundation.errors import ConfigurationError
from ser_lib.models import CNNBaseline


@pytest.mark.parametrize("field", ["schema_version", "format_version", "unexpected"])
def test_configs_reject_obsolete_and_unknown_fields(current_experiment_config, tmp_path, field):
    for model, original in [
        (ExperimentConfig, current_experiment_config),
        (DataConfig, current_experiment_config.data),
    ]:
        payload = original.model_dump(mode="json")
        assert "schema_version" not in payload
        with pytest.raises(ValidationError):
            model.model_validate({**payload, field: 1})
    path = tmp_path / "data.yaml"
    path.write_text(
        yaml.safe_dump({**current_experiment_config.data.model_dump(mode="json"), field: 1})
    )
    with pytest.raises(ConfigurationError):
        load_data_config(path)


@pytest.mark.parametrize("change", ["version", "missing", "type", "extra"])
def test_manifest_rejects_invalid_current_document(current_experiment_config, change):
    path = current_experiment_config.data.manifest
    raw = yaml.safe_load(path.read_text())
    if change == "version":
        raw["schema_version"] = 1
    elif change == "missing":
        raw.pop("splits")
    elif change == "type":
        raw["dataset_id"] = 123
    else:
        raw["unexpected"] = True
    path.write_text(yaml.safe_dump(raw))
    with pytest.raises(ManifestError):
        DatasetManifest.load(path)


@pytest.fixture
def current_artifact(tmp_path, current_experiment_config):
    model = CNNBaseline(feature_dim=16, num_classes=2)
    return export_model_artifact(
        tmp_path / "artifact",
        model,
        model_name="cnn_baseline",
        data_config=current_experiment_config.data,
        labels={0: "neutral", 1: "happy"},
    )


@pytest.mark.parametrize("field", ["schema_version", "weights_format", "unexpected"])
def test_artifact_rejects_obsolete_fields_without_loading_pickle(
    current_artifact, monkeypatch, field
):
    path = current_artifact / "manifest.json"
    raw = json.loads(path.read_text())
    raw[field] = 1
    path.write_text(json.dumps(raw))

    def forbidden(*args, **kwargs):
        pytest.fail("artifact loading must never call torch.load")

    monkeypatch.setattr(torch, "load", forbidden)
    with pytest.raises(ValueError, match="manifest"):
        load_model_artifact(current_artifact)


def test_artifact_library_version_is_provenance_only(current_artifact):
    path = current_artifact / "manifest.json"
    raw = json.loads(path.read_text())
    assert "schema_version" not in raw and "weights_format" not in raw
    raw["library_version"] = "99.0.0"
    path.write_text(json.dumps(raw))
    loaded = load_model_artifact(current_artifact)
    assert loaded.manifest.library_version == "99.0.0"


@pytest.mark.parametrize("change", ["hash_missing", "weights_name", "required_missing"])
def test_artifact_requires_current_files_and_metadata(current_artifact, change):
    path = current_artifact / "manifest.json"
    raw = json.loads(path.read_text())
    if change == "hash_missing":
        raw["files_sha256"].pop("data_config.json")
    elif change == "weights_name":
        raw["weights_file"] = "model_state.pt"
    else:
        raw.pop("files_sha256")
    path.write_text(json.dumps(raw))
    with pytest.raises(ValueError):
        verify_model_artifact(current_artifact)


@pytest.mark.parametrize("change", ["version", "missing", "wrong_type", "extra", "rng_missing"])
def test_checkpoint_rejects_invalid_payload_before_loading_model(tmp_path, change):
    model = CNNBaseline(feature_dim=16, num_classes=2)
    path = save_checkpoint(tmp_path / "current.pt", model, None, epoch=1)
    payload = torch.load(path, weights_only=False)
    assert "format_version" not in payload
    assert payload["library_version"]
    if change == "version":
        payload["format_version"] = 2
    elif change == "missing":
        payload.pop("trainer_config")
    elif change == "wrong_type":
        payload["epoch"] = True
    elif change == "rng_missing":
        payload["rng_state"].pop("numpy")
    else:
        payload["unexpected"] = True
    torch.save(payload, path)
    target = CNNBaseline(feature_dim=16, num_classes=2)
    before = {k: v.clone() for k, v in target.state_dict().items()}
    with pytest.raises(ValueError):
        load_checkpoint(path, target)
    for key, value in target.state_dict().items():
        torch.testing.assert_close(value, before[key], rtol=0, atol=0)


def test_training_and_evaluation_write_current_records(
    current_experiment_config, current_artifact, tmp_path
):
    from ser_lib.engine import evaluate_artifact, train_experiment
    from ser_lib.engine.runs import TrainingRunInfo
    from ser_lib.engine.evaluation_runs import EvaluationRunInfo

    train_experiment(current_experiment_config)
    output = tmp_path / "evaluation"
    evaluate_artifact(current_artifact, split="train", output=output)
    for path, record in [
        (current_experiment_config.output_dir / "run.json", TrainingRunInfo),
        (output / "evaluation.json", EvaluationRunInfo),
    ]:
        raw = json.loads(Path(path).read_text())
        assert "schema_version" not in raw
        assert raw["library_version"]
        record.from_dict(raw)
        with pytest.raises(ValidationError):
            record.from_dict({**raw, "schema_version": 1})
