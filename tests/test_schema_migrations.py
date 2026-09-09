from __future__ import annotations

import pytest

from ser_lib.core import MigrationRegistry, SchemaMigrationError


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
