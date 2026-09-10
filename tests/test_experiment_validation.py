from __future__ import annotations

import json
from pathlib import Path

from ser_lib.data import BatchingConfig
from ser_lib.data.config import AudioSettings, ComponentConfig, DataConfig
from ser_lib.engine import validate_experiment
from ser_lib.engine.config import ExperimentConfig, ModelConfig, TrainerConfig
from ser_lib.models.registry import model_registry


def _manifest(tmp_path: Path, *, classes: int = 2, split_exists: bool = True) -> Path:
    labels = "\n".join(
        f"  {index}: {{en: class-{index}}}" for index in range(classes)
    )
    path = tmp_path / "dataset.yaml"
    path.write_text(
        "schema_version: 1\n"
        "dataset_id: dry-run\n"
        "root: .\n"
        "splits:\n"
        "  train: train.jsonl\n"
        "labels:\n"
        f"{labels}\n",
        encoding="utf-8",
    )
    if split_exists:
        (tmp_path / "train.jsonl").write_text("", encoding="utf-8")
    return path


def _labels(count: int) -> dict[int, dict[str, str]]:
    return {index: {"en": f"class-{index}"} for index in range(count)}


def _cnn_experiment(tmp_path: Path) -> ExperimentConfig:
    return ExperimentConfig(
        data=DataConfig(
            manifest=_manifest(tmp_path),
            labels=_labels(2),
            audio=AudioSettings(target_sample_rate=16000),
            representation=ComponentConfig(
                type="log_mel",
                params={
                    "sample_rate": 16000,
                    "n_fft": 256,
                    "win_length": 256,
                    "hop_length": 80,
                    "n_mels": 16,
                },
            ),
            batching=BatchingConfig(type="dynamic"),
        ),
        model=ModelConfig(
            type="cnn_baseline",
            params={"feature_dim": 16, "num_classes": 2, "dropout": 0},
        ),
        trainer=TrainerConfig(
            epochs=1,
            device="cpu",
            checkpoint_dir=tmp_path / "checkpoints",
        ),
        output_dir=tmp_path / "run",
    )


def test_valid_dry_run_is_json_safe_and_does_not_create_model_or_output(monkeypatch, tmp_path: Path):
    config = _cnn_experiment(tmp_path)

    def forbidden_create(*args, **kwargs):
        raise AssertionError("dry-run must not instantiate a model")

    monkeypatch.setattr(model_registry, "create", forbidden_create)
    result = validate_experiment(config)

    assert result.valid is True
    assert result.diagnostics == ()
    assert result.summary["dataset_id"] == "dry-run"
    assert result.summary["model_id"] == "cnn_baseline"
    assert result.summary["pipeline_outputs"]["features"]["feature_dim"] == 16
    assert result.summary["model_inputs"]["features"]["layout"] == "FT"
    assert result.normalized_config["model"]["params"]["hidden_dim"] == 128
    assert not (tmp_path / "run").exists()
    assert not (tmp_path / "checkpoints").exists()
    json.dumps(result.to_dict(), ensure_ascii=False)


def test_hf_dry_run_does_not_import_transformers_or_load_weights(monkeypatch, tmp_path: Path):
    manifest = _manifest(tmp_path)
    config = ExperimentConfig(
        data=DataConfig(
            manifest=manifest,
            labels=_labels(2),
            audio=AudioSettings(target_sample_rate=16000),
            representation=ComponentConfig(type="waveform"),
            batching=BatchingConfig(type="dynamic"),
        ),
        model=ModelConfig(
            type="hf_audio_classifier",
            params={
                "num_classes": 2,
                "pretrained_model_name_or_path": "local/model",
                "expected_sample_rate": 16000,
            },
        ),
        trainer=TrainerConfig(epochs=1, device="cpu"),
        output_dir=tmp_path / "run-hf",
    )

    def forbidden_transformers():
        raise AssertionError("dry-run must not import transformers")

    def forbidden_create(*args, **kwargs):
        raise AssertionError("dry-run must not instantiate hf model")

    monkeypatch.setattr(
        "ser_lib.models.adapters.huggingface._transformers",
        forbidden_transformers,
    )
    monkeypatch.setattr(model_registry, "create", forbidden_create)

    result = validate_experiment(config)

    assert result.valid is True
    assert result.summary["model_inputs"]["waveform"]["layout"] == "T"
    assert result.summary["sample_rate"] == 16000
    assert not (tmp_path / "run-hf").exists()


def test_dry_run_accumulates_dataset_pipeline_loss_path_and_device_errors(tmp_path: Path):
    manifest = _manifest(tmp_path, classes=3, split_exists=False)
    output_file = tmp_path / "not-a-directory"
    output_file.write_text("occupied", encoding="utf-8")
    config = ExperimentConfig(
        data=DataConfig(
            manifest=manifest,
            labels=_labels(2),
            audio=AudioSettings(target_sample_rate=16000),
            representation=ComponentConfig(type="waveform"),
            batching=BatchingConfig(type="dynamic"),
        ),
        model=ModelConfig(
            type="cnn_baseline",
            params={"feature_dim": 16, "num_classes": 2},
        ),
        trainer=TrainerConfig(epochs=1, device="cpu", amp=True),
        loss={"type": "cross_entropy", "class_weights": [1.0]},
        output_dir=output_file,
    )

    result = validate_experiment(config)
    codes = {diagnostic.code for diagnostic in result.diagnostics}

    assert result.valid is False
    assert {
        "dataset_split_missing",
        "label_count_mismatch",
        "missing_model_input",
        "loss_class_weights_mismatch",
        "output_path_not_directory",
        "amp_device_mismatch",
    } <= codes
    json.dumps(result.to_dict(), ensure_ascii=False)


def test_dry_run_from_invalid_yaml_returns_diagnostic_instead_of_raising(tmp_path: Path):
    config_path = tmp_path / "invalid.yaml"
    config_path.write_text(
        "schema_version: 1\n"
        "data: {manifest: dataset.yaml}\n"
        "model: {type: cnn_baseline, params: {feature_dim: 16}}\n",
        encoding="utf-8",
    )

    result = validate_experiment(config_path)

    assert result.valid is False
    assert result.normalized_config == {}
    assert result.summary == {}
    assert [item.code for item in result.diagnostics] == ["experiment_config_invalid"]
    assert result.diagnostics[0].path == str(config_path)


def test_static_specs_are_available_for_all_builtin_models_without_instantiation(monkeypatch):
    def forbidden_create(*args, **kwargs):
        raise AssertionError("inspect_spec must never instantiate models")

    monkeypatch.setattr(model_registry, "create", forbidden_create)
    cases = {
        "cnn_baseline": {"feature_dim": 8, "num_classes": 2},
        "gru_baseline": {"feature_dim": 8, "num_classes": 2},
        "transformer_baseline": {"feature_dim": 8, "num_classes": 2},
        "hf_audio_classifier": {
            "num_classes": 2,
            "pretrained_model_name_or_path": "local/model",
        },
    }

    specs = {
        name: model_registry.inspect_spec(name, params)
        for name, params in cases.items()
    }

    assert specs["cnn_baseline"].required_inputs["features"].feature_dim == 8
    assert specs["gru_baseline"].required_inputs["features"].layout == "FT"
    assert specs["transformer_baseline"].num_classes == 2
    assert specs["hf_audio_classifier"].required_inputs["waveform"].layout == "T"
    assert specs["hf_audio_classifier"].expected_sample_rate == 16000
