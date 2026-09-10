from __future__ import annotations

import importlib

import pytest

import ser_lib
import ser_lib.artifacts as artifacts
import ser_lib.config as config
import ser_lib.data as data
import ser_lib.engine as engine
import ser_lib.foundation as foundation
import ser_lib.inference as inference
import ser_lib.models as models


def _assert_explicit_public_surface(module) -> None:
    public = tuple(module.__all__)
    assert len(public) == len(set(public))
    assert all(not name.startswith("_") for name in public)
    for name in public:
        assert hasattr(module, name), f"{module.__name__}.{name}"


def test_package_public_surfaces_are_resolvable_and_unique():
    for module in (
        ser_lib,
        foundation,
        config,
        data,
        engine,
        artifacts,
        inference,
        models,
    ):
        _assert_explicit_public_surface(module)
    assert ser_lib.__version__ == "0.2.0"


def test_canonical_domain_types_have_intentional_public_paths():
    assert ser_lib.ArtifactEntry is artifacts.ArtifactEntry
    assert ser_lib.ComponentDescriptor is data.ComponentDescriptor
    assert ser_lib.build_experiment_config is config.build_experiment_config
    assert ser_lib.iter_evaluation_predictions is engine.iter_evaluation_predictions
    assert ser_lib.EvaluationPredictionFileInfo is engine.EvaluationPredictionFileInfo
    assert ser_lib.EtaSnapshot is engine.EtaSnapshot
    assert ser_lib.EtaEstimator is engine.EtaEstimator

    assert ser_lib.Diagnostic is foundation.Diagnostic
    assert ser_lib.CompatibilityReport is engine.CompatibilityReport
    assert ser_lib.inspect_compatibility is engine.inspect_compatibility
    assert models.ModelSpec.__module__ == "ser_lib.models.specs"
    assert models.TorchModelAdapter.__module__ == "ser_lib.models.adapters.torch"
    assert models.TORCH_ADAPTER_MODEL_ID == "torch_model_adapter"
    assert "torch_model_adapter" in models.model_registry.names()
    assert models.model_registry.supports_static_spec("torch_model_adapter") is True
    assert models.HFAudioClassifier.__module__ == "ser_lib.models.adapters.huggingface"
    assert "hf_audio_classifier" in models.model_registry.names()
    assert config.HFProcessorConfig.__module__ == "ser_lib.config.model"
    assert config.HFAudioClassifierConfig.__module__ == "ser_lib.config.model"
    assert config.TorchModelAdapterConfig.__module__ == "ser_lib.config.model"
    assert config.TorchTensorSpecConfig.__module__ == "ser_lib.config.model"
    assert engine.CompatibilityReport.__module__ == "ser_lib.engine.compatibility"
    assert config.StrictConfig.__module__ == "ser_lib.config.base"
    assert foundation.SchemaMigrationError.__module__ == "ser_lib.foundation.errors"
    assert foundation.RegistryError.__module__ == "ser_lib.foundation.errors"
    assert foundation.CompatibilityError.__module__ == "ser_lib.foundation.errors"


def test_application_wrappers_are_absent_from_public_surfaces():
    retired = {
        "RecordView",
        "RecordPage",
        "query_records",
        "TrainingRunDetail",
        "inspect_training_run_detail",
        "EvaluationRunDetail",
        "inspect_evaluation_run_detail",
        "EvaluationPredictionPage",
        "query_evaluation_predictions",
        "ArtifactInfo",
        "ComponentCatalog",
        "get_component_catalog",
        "list_component_descriptors",
        "ExperimentPresetInfo",
        "ExperimentPresetCatalog",
        "PresetStatus",
        "list_experiment_presets",
        "get_experiment_preset",
    }
    for module in (ser_lib, data, engine, artifacts):
        assert retired.isdisjoint(module.__all__), module.__name__
        assert all(not hasattr(module, name) for name in retired), module.__name__


def test_internal_modules_are_not_required_for_stable_imports():
    for module_name in (
        "ser_lib",
        "ser_lib.foundation",
        "ser_lib.config",
        "ser_lib.data",
        "ser_lib.engine",
        "ser_lib.artifacts",
        "ser_lib.inference",
        "ser_lib.models",
    ):
        module = importlib.import_module(module_name)
        assert module.__all__


def test_retired_internal_namespaces_are_not_importable():
    for module_name in (
        "ser_lib.core",
        "ser_lib.services",
        "ser_lib.catalog",
        "ser_lib.models.pretrained",
    ):
        with pytest.raises(ModuleNotFoundError):
            importlib.import_module(module_name)
