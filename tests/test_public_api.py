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
import ser_lib.services as services


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
        services,
    ):
        _assert_explicit_public_surface(module)
    assert ser_lib.__version__ == "0.2.0"


def test_new_stabilization_types_have_intentional_public_paths():
    assert ser_lib.TrainingRunDetail is engine.TrainingRunDetail
    assert ser_lib.EvaluationRunDetail is engine.EvaluationRunDetail
    assert ser_lib.ExperimentPresetInfo is engine.ExperimentPresetInfo
    assert ser_lib.ExperimentPresetCatalog is engine.ExperimentPresetCatalog
    assert ser_lib.EtaSnapshot is engine.EtaSnapshot
    assert ser_lib.EtaEstimator is engine.EtaEstimator

    assert ser_lib.Diagnostic is foundation.Diagnostic
    assert ser_lib.CompatibilityReport is engine.CompatibilityReport
    assert ser_lib.inspect_compatibility is engine.inspect_compatibility
    assert models.ModelSpec.__module__ == "ser_lib.models.specs"
    assert engine.CompatibilityReport.__module__ == "ser_lib.engine.compatibility"
    assert config.StrictConfig.__module__ == "ser_lib.config.base"
    assert foundation.SchemaMigrationError.__module__ == "ser_lib.foundation.errors"
    assert foundation.RegistryError.__module__ == "ser_lib.foundation.errors"
    assert foundation.CompatibilityError.__module__ == "ser_lib.foundation.errors"


def test_services_are_public_only_from_service_facade_not_root_package():
    expected = {
        "DatasetService",
        "TrainingService",
        "EvaluationService",
        "InferenceService",
        "ArtifactService",
        "CatalogService",
        "RuntimeService",
    }
    assert expected <= set(services.__all__)
    assert expected.isdisjoint(ser_lib.__all__)


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
        "ser_lib.services",
    ):
        module = importlib.import_module(module_name)
        assert module.__all__


def test_retired_core_namespace_is_not_importable():
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("ser_lib.core")
