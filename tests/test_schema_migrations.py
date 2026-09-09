from __future__ import annotations

import pytest

from ser_lib.artifacts.migrations import validate_artifact_manifest_version
from ser_lib.config.migrations import MigrationRegistry
from ser_lib.data.migrations import migrate_data_payload
from ser_lib.engine.migrations import migrate_engine_payload
from ser_lib.foundation.errors import SchemaMigrationError


def test_schema_migration_chains_without_mutating_input():
    registry = MigrationRegistry()

    def v1_to_v2(payload: dict):
        payload["schema_version"] = 2
        payload["nested"]["value"] = 2
        return payload

    def v2_to_v3(payload: dict):
        payload["schema_version"] = 3
        payload["added"] = True
        return payload

    registry.register("demo", 1, 2, v1_to_v2)
    registry.register("demo", 2, 3, v2_to_v3)
    original = {"schema_version": 1, "nested": {"value": 1}}

    migrated = registry.migrate("demo", original, target_version=3)

    assert original == {"schema_version": 1, "nested": {"value": 1}}
    assert migrated == {
        "schema_version": 3,
        "nested": {"value": 2},
        "added": True,
    }


def test_schema_migration_current_version_is_deep_copy_noop():
    registry = MigrationRegistry()
    original = {"schema_version": 2, "nested": {"items": [1]}}

    migrated = registry.migrate("demo", original, target_version=2)
    migrated["nested"]["items"].append(2)

    assert original["nested"]["items"] == [1]


def test_schema_migration_rejects_invalid_future_and_missing_path():
    registry = MigrationRegistry()

    with pytest.raises(SchemaMigrationError) as invalid:
        registry.migrate("demo", {"schema_version": True}, target_version=1)
    assert invalid.value.code == "schema_version_invalid"

    with pytest.raises(SchemaMigrationError) as future:
        registry.migrate("demo", {"schema_version": 3}, target_version=2)
    assert future.value.code == "schema_version_future"

    with pytest.raises(SchemaMigrationError) as missing:
        registry.migrate("demo", {"schema_version": 1}, target_version=2)
    assert missing.value.code == "schema_migration_missing"


def test_schema_migration_rejects_non_consecutive_and_invalid_result():
    registry = MigrationRegistry()
    with pytest.raises(ValueError, match="N -> N\\+1"):
        registry.register("demo", 1, 3, lambda payload: payload)

    registry.register("demo", 1, 2, lambda payload: {**payload, "schema_version": 3})
    with pytest.raises(SchemaMigrationError) as invalid:
        registry.migrate("demo", {"schema_version": 1}, target_version=2)
    assert invalid.value.code == "schema_migration_invalid_result"


def test_schema_migration_wraps_function_failure_and_rejects_duplicate():
    registry = MigrationRegistry()

    def explode(payload: dict):
        raise RuntimeError("boom")

    registry.register("demo", 1, 2, explode)
    with pytest.raises(ValueError, match="重复"):
        registry.register("demo", 1, 2, explode)

    with pytest.raises(SchemaMigrationError) as failed:
        registry.migrate("demo", {"schema_version": 1}, target_version=2)
    assert failed.value.code == "schema_migration_failed"
    assert failed.value.details["error_type"] == "RuntimeError"


def test_data_and_engine_version_gates_preserve_current_payload_and_errors():
    source = {"schema_version": 1, "nested": {"items": [1]}}
    data = migrate_data_payload("dataset_manifest", source, target_version=1)
    engine = migrate_engine_payload("training_run", source, target_version=1)
    data["nested"]["items"].append(2)
    engine["nested"]["items"].append(3)
    assert source == {"schema_version": 1, "nested": {"items": [1]}}

    with pytest.raises(SchemaMigrationError) as future:
        migrate_engine_payload("evaluation_run", {"schema_version": 2}, target_version=1)
    assert future.value.code == "schema_version_future"

    with pytest.raises(SchemaMigrationError) as missing:
        migrate_data_payload("dataset_revision", {"schema_version": 1}, target_version=2)
    assert missing.value.code == "schema_migration_missing"


def test_artifact_versions_are_validated_without_fake_upgrade():
    v1 = {"schema_version": 1, "weights_file": "model_state.pt"}
    v2 = {"schema_version": 2, "weights_file": "model.safetensors", "files_sha256": {}}

    assert validate_artifact_manifest_version(v1) == 1
    assert validate_artifact_manifest_version(v2) == 2
    assert "files_sha256" not in v1

    with pytest.raises(SchemaMigrationError) as future:
        validate_artifact_manifest_version({"schema_version": 3})
    assert future.value.code == "schema_version_future"
