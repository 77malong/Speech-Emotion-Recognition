from __future__ import annotations

import importlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from pydantic import ValidationError
from torch import nn

import ser_lib
from scripts.check_coverage import DEFAULT_THRESHOLDS
from ser_lib.artifacts import ModelArtifactManifest
from ser_lib.data import DATASET_REVISION_SCHEMA_VERSION
from ser_lib.data.config import AudioSettings, load_data_config
from ser_lib.data.manifest import MANIFEST_SCHEMA_VERSION
from ser_lib.engine import EVALUATION_RUN_SCHEMA_VERSION, RUN_RECORD_SCHEMA_VERSION
from ser_lib.engine.checkpoint import CHECKPOINT_FORMAT_VERSION
from ser_lib.foundation.events import EVENT_SCHEMA_VERSION
from ser_lib.models import HFAudioClassifier, model_registry


_FIXTURE = Path(__file__).parent / "fixtures" / "pre_refactor_contract_snapshot.json"


def _snapshot() -> dict:
    return json.loads(_FIXTURE.read_text(encoding="utf-8"))


def _replace_name(current: list[str], old: str, new: str) -> None:
    index = current.index(old)
    current[index] = new


def _retire_names(current: list[str], retired: set[str]) -> list[str]:
    return [name for name in current if name not in retired]


def _expected_current_public_api(module_name: str, expected: list[str]) -> list[str]:
    """Apply only explicitly planned namespace moves while preserving Stage 01 evidence."""
    current = list(expected)
    if module_name == "ser_lib":
        current = _retire_names(
            current,
            {
                "CATALOG_SCHEMA_VERSION",
                "CATALOG_CATEGORIES",
                "ComponentCatalog",
                "get_component_catalog",
                "list_component_descriptors",
                "TrainingRunDetail",
                "EvaluationRunDetail",
                "EvaluationPredictionPage",
                "query_evaluation_predictions",
                "ExperimentPresetInfo",
                "ExperimentPresetCatalog",
                "PresetStatus",
                "list_experiment_presets",
                "get_experiment_preset",
            },
        )
        _replace_name(current, "ArtifactInfo", "ArtifactEntry")
        insertion = current.index("inspect_evaluation_report") + 1
        current.insert(insertion, "iter_evaluation_predictions")
    elif module_name == "ser_lib.data":
        retired = {
            "ModelSpec",
            "CompatibilityReport",
            "inspect_compatibility",
            "validate_compatibility",
            "RecordView",
            "RecordPage",
        }
        current = _retire_names(current, retired)
        _replace_name(current, "query_records", "iter_records")
    elif module_name == "ser_lib.models":
        current.insert(2, "ModelSpec")
    elif module_name == "ser_lib.engine":
        compatibility = [
            "CompatibilityReport",
            "inspect_compatibility",
            "validate_compatibility",
        ]
        current[7:7] = compatibility
        current = _retire_names(
            current,
            {
                "PresetStatus",
                "ExperimentPresetInfo",
                "ExperimentPresetCatalog",
                "list_experiment_presets",
                "get_experiment_preset",
                "build_experiment_config",
                "TrainingRunDetail",
                "EvaluationRunDetail",
                "EvaluationPredictionPage",
                "query_evaluation_predictions",
            },
        )
        experiment_api = [
            "TrainingExperimentResult",
            "EvaluationExperimentResult",
            "train_experiment",
            "evaluate_artifact",
        ]
        insertion = current.index("validate_experiment") + 1
        current[insertion:insertion] = experiment_api
        insertion = current.index("inspect_evaluation_report") + 1
        current.insert(insertion, "iter_evaluation_predictions")
    elif module_name == "ser_lib.artifacts":
        _replace_name(current, "ArtifactInfo", "ArtifactEntry")
    return current


def test_pre_refactor_public_api_exact_snapshot():
    snapshot = _snapshot()
    assert ser_lib.__version__ == snapshot["version"]

    for module_name, expected in snapshot["public_api"].items():
        if module_name in {"ser_lib.core", "ser_lib.services"}:
            continue
        module = importlib.import_module(module_name)
        assert list(module.__all__) == _expected_current_public_api(module_name, expected), module_name

    # Stage 01 的历史快照继续记录已退役 namespace/包装，不能通过改 fixture 抹掉基线证据。
    assert snapshot["public_api"]["ser_lib.core"]
    assert snapshot["public_api"]["ser_lib.services"]
    assert "RecordPage" in snapshot["public_api"]["ser_lib.data"]
    assert "TrainingRunDetail" in snapshot["public_api"]["ser_lib.engine"]
    assert "EvaluationPredictionPage" in snapshot["public_api"]["ser_lib.engine"]
    assert "ArtifactInfo" in snapshot["public_api"]["ser_lib.artifacts"]
    assert "ComponentCatalog" in snapshot["public_api"]["ser_lib"]

    # Stage 06/07/08/09 的计划内迁移与新增只在测试中显式记录。
    assert "ModelSpec" in snapshot["public_api"]["ser_lib.data"]
    assert "CompatibilityReport" in snapshot["public_api"]["ser_lib.data"]
    assert "train_experiment" not in snapshot["public_api"]["ser_lib.engine"]
    assert "iter_records" not in snapshot["public_api"]["ser_lib.data"]
    assert "iter_evaluation_predictions" not in snapshot["public_api"]["ser_lib.engine"]
    assert "ArtifactEntry" not in snapshot["public_api"]["ser_lib.artifacts"]


def test_pre_refactor_persistent_format_versions_are_locked():
    expected = _snapshot()["persistent_versions"]
    assert EVENT_SCHEMA_VERSION == expected["event_schema"]
    assert MANIFEST_SCHEMA_VERSION == expected["dataset_manifest_schema"]
    assert DATASET_REVISION_SCHEMA_VERSION == expected["dataset_revision_schema"]
    assert RUN_RECORD_SCHEMA_VERSION == expected["training_run_schema"]
    assert EVALUATION_RUN_SCHEMA_VERSION == expected["evaluation_run_schema"]
    assert CHECKPOINT_FORMAT_VERSION == expected["checkpoint_format"]
    assert (
        ModelArtifactManifest.model_fields["schema_version"].default
        == expected["artifact_manifest_schema"]
    )


def test_legacy_artifact_v1_defaults_remain_pytorch_without_fake_upgrade():
    manifest = ModelArtifactManifest.model_validate(
        {
            "schema_version": 1,
            "library_version": ser_lib.__version__,
            "model_name": "cnn_baseline",
            "model_params": {"feature_dim": 4, "num_classes": 2},
            "weights_sha256": "0" * 64,
            "preprocessing": {},
            "labels": {0: "neutral", 1: "happy"},
        }
    )

    assert manifest.schema_version == 1
    assert manifest.weights_file == "model_state.pt"
    assert manifest.weights_format == "pytorch"
    assert manifest.files_sha256 == {}


def test_audio_settings_round_trip_unknown_field_and_config_relative_path(tmp_path: Path):
    payload = AudioSettings().model_dump(mode="json")
    assert payload == {
        "target_sample_rate": 16000,
        "mono": True,
        "normalize_peak": False,
        "backend": "soundfile",
    }
    assert AudioSettings.model_validate(payload).model_dump(mode="json") == payload

    with pytest.raises(ValidationError):
        AudioSettings.model_validate({**payload, "target_sample_rate_typo": 8000})

    config_dir = tmp_path / "configs"
    config_dir.mkdir()
    config_path = config_dir / "demo.yaml"
    config_path.write_text(
        "schema_version: 1\n"
        "manifest: ../data/dataset.yaml\n"
        "representation:\n"
        "  type: waveform\n",
        encoding="utf-8",
    )
    loaded = load_data_config(config_path)
    assert loaded.manifest == (config_dir / "../data/dataset.yaml").resolve()


def test_pre_refactor_coverage_thresholds_and_ci_matrix_are_recorded():
    snapshot = _snapshot()
    for prefix, minimum in snapshot["coverage_thresholds"].items():
        if prefix == "ser_lib/core/":
            continue
        assert DEFAULT_THRESHOLDS[prefix] == minimum
    assert "ser_lib/core/" not in DEFAULT_THRESHOLDS
    assert DEFAULT_THRESHOLDS["ser_lib/foundation/"] == 85.0
    assert DEFAULT_THRESHOLDS["ser_lib/config/"] == 85.0

    root = Path(__file__).resolve().parents[1]
    workflow = (root / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    for os_name in snapshot["ci"]["os"]:
        assert os_name in workflow
    for python_version in snapshot["ci"]["python"]:
        assert f'"{python_version}"' in workflow
    assert "python -m pytest -q" in workflow
    assert "python scripts/smoke_train_epoch.py --device cpu" in workflow
    assert "python scripts/check_coverage.py coverage.json" in workflow


class _FakeConfig:
    model_type = "fake_audio"
    hidden_size = 4

    def __init__(self, **values):
        self.hidden_size = values.get("hidden_size", 4)

    def to_dict(self):
        return {"model_type": self.model_type, "hidden_size": self.hidden_size}


class _FakeEncoder(nn.Module):
    def __init__(self, config=None):
        super().__init__()
        self.config = config or _FakeConfig()
        self.projection = nn.Linear(1, self.config.hidden_size, bias=False)


def test_hf_registration_and_state_dict_key_shape_are_locked(monkeypatch):
    class AutoConfig:
        @staticmethod
        def for_model(model_type, **values):
            assert model_type == "fake_audio"
            return _FakeConfig(**values)

    class AutoModel:
        @staticmethod
        def from_config(config):
            return _FakeEncoder(config)

    monkeypatch.setattr(
        "ser_lib.models.pretrained._transformers",
        lambda: SimpleNamespace(AutoConfig=AutoConfig, AutoModel=AutoModel),
    )
    model = HFAudioClassifier(
        num_classes=2,
        encoder_config={"model_type": "fake_audio", "hidden_size": 4},
        dropout=0,
    )

    assert "hf_audio_classifier" in model_registry.names()
    descriptor = model_registry.descriptor("hf_audio_classifier")
    assert descriptor["id"] == "hf_audio_classifier"
    assert descriptor["status"] == "optional"
    assert tuple(model.state_dict()) == (
        "encoder.projection.weight",
        "classifier.weight",
        "classifier.bias",
    )
