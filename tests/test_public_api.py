from __future__ import annotations

import importlib

import ser_lib
import ser_lib.artifacts as artifacts
import ser_lib.core as core
import ser_lib.data as data
import ser_lib.engine as engine
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
        core,
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

    assert hasattr(core, "SchemaMigration")
    assert hasattr(core, "MigrationRegistry")
    assert hasattr(core, "SchemaMigrationError")
    assert hasattr(core, "migrate_schema_payload")


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
        "ser_lib.core",
        "ser_lib.data",
        "ser_lib.engine",
        "ser_lib.artifacts",
        "ser_lib.inference",
        "ser_lib.models",
        "ser_lib.services",
    ):
        module = importlib.import_module(module_name)
        assert module.__all__
