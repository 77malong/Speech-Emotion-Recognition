from __future__ import annotations

import json

import pytest

from ser_lib import (
    CATALOG_CATEGORIES,
    CATALOG_SCHEMA_VERSION,
    ComponentCatalog as RootComponentCatalog,
    ComponentDescriptor as RootComponentDescriptor,
    get_component_catalog as root_get_component_catalog,
)
from ser_lib.catalog import (
    ComponentCatalog,
    ComponentDescriptor,
    get_component_catalog,
    list_component_descriptors,
)
from ser_lib.data.errors import RegistryError
from ser_lib.models.registry import model_registry


EXPECTED_CATEGORIES = (
    "model",
    "representation",
    "waveform_transform",
    "feature_transform",
    "importer",
    "optimizer",
    "scheduler",
    "loss",
    "sampler",
)


def test_catalog_public_api_and_categories_are_stable():
    assert CATALOG_SCHEMA_VERSION == 1
    assert CATALOG_CATEGORIES == EXPECTED_CATEGORIES
    assert RootComponentCatalog is ComponentCatalog
    assert RootComponentDescriptor is ComponentDescriptor
    assert root_get_component_catalog is get_component_catalog

    catalog = get_component_catalog()
    assert catalog.categories == EXPECTED_CATEGORIES
    assert set(item.category for item in catalog.components) == set(EXPECTED_CATEGORIES)


def test_catalog_contains_builtin_data_model_and_training_components():
    catalog = get_component_catalog()

    assert {item.id for item in catalog.list("model")} >= {
        "cnn_baseline",
        "gru_baseline",
        "transformer_baseline",
        "hf_audio_classifier",
    }
    assert {item.id for item in catalog.list("representation")} >= {"waveform", "log_mel"}
    assert {item.id for item in catalog.list("importer")} >= {"folder", "csv", "jsonl"}
    assert {item.id for item in catalog.list("optimizer")} == {"adamw", "adam", "sgd"}
    assert {item.id for item in catalog.list("scheduler")} == {"step", "cosine"}
    assert {item.id for item in catalog.list("loss")} == {"cross_entropy", "focal"}
    assert {item.id for item in catalog.list("sampler")} == {"shuffle", "weighted"}


def test_catalog_is_json_safe_complete_and_has_no_duplicate_keys():
    catalog = get_component_catalog()
    payload = catalog.to_dict()

    assert payload["schema_version"] == 1
    assert payload["categories"] == list(EXPECTED_CATEGORIES)
    keys = [(item.category, item.id) for item in catalog.components]
    assert len(keys) == len(set(keys))

    required_fields = {
        "id",
        "display_name",
        "category",
        "version",
        "status",
        "description",
        "config_schema",
        "capabilities",
        "input_specs",
        "output_specs",
    }
    for descriptor in payload["components"]:
        assert required_fields <= set(descriptor)
    json.dumps(payload, ensure_ascii=False)


def test_model_catalog_exposes_status_schema_and_machine_capabilities(monkeypatch):
    def forbidden_create(*args, **kwargs):
        raise AssertionError("catalog query must not instantiate models")

    monkeypatch.setattr(model_registry, "create", forbidden_create)
    catalog = get_component_catalog()

    cnn = catalog.get("model", "cnn_baseline")
    assert cnn.status == "stable"
    assert cnn.capabilities["input_layouts"] == {"features": "FT"}
    assert cnn.capabilities["supports_static_spec"] is True
    assert cnn.config_schema["properties"]["hidden_dim"]["default"] == 128

    hf = catalog.get("model", "hf_audio_classifier")
    assert hf.status == "optional"
    assert hf.capabilities["input_layouts"] == {"waveform": "T"}
    assert hf.capabilities["supports_static_spec"] is True

    stable_models = {item.id for item in catalog.list("model", statuses=("stable",))}
    assert "cnn_baseline" in stable_models
    assert "hf_audio_classifier" not in stable_models


def test_training_component_schemas_are_form_ready_and_match_runtime_defaults():
    catalog = get_component_catalog()

    adamw = catalog.get("optimizer", "adamw")
    assert "type" not in adamw.config_schema["properties"]
    assert adamw.config_schema["properties"]["learning_rate"]["default"] == 0.001
    assert adamw.config_schema["properties"]["weight_decay"]["default"] == 0.0

    cosine = catalog.get("scheduler", "cosine")
    assert "t_max" in cosine.config_schema["required"]
    assert cosine.config_schema["properties"]["eta_min"]["default"] == 0.0

    cross_entropy = catalog.get("loss", "cross_entropy")
    assert set(cross_entropy.config_schema["properties"]) == {
        "class_weights",
        "label_smoothing",
    }
    focal = catalog.get("loss", "focal")
    assert "focal_gamma" in focal.config_schema["properties"]
    assert focal.config_schema["properties"]["focal_gamma"]["default"] == 2.0

    shuffle = catalog.get("sampler", "shuffle")
    assert shuffle.config_schema["properties"] == {}
    weighted = catalog.get("sampler", "weighted")
    assert set(weighted.config_schema["properties"]) == {
        "class_weights",
        "replacement",
        "num_samples",
    }
    assert weighted.capabilities["auto_class_weights"] is True


def test_data_descriptors_keep_registry_schema_and_gain_catalog_capabilities():
    catalog = get_component_catalog()

    waveform = catalog.get("representation", "waveform")
    assert waveform.capabilities["pipeline_stage"] == "representation"
    assert isinstance(waveform.config_schema, dict)

    folder = catalog.get("importer", "folder")
    assert folder.capabilities["supports_scan"] is True
    assert folder.capabilities["supports_convert"] is True
    assert "audio_extensions" in folder.config_schema["properties"]


def test_catalog_convenience_query_and_unknown_component_errors():
    optimizers = list_component_descriptors("optimizer")
    assert {item.id for item in optimizers} == {"adam", "adamw", "sgd"}

    catalog = get_component_catalog()
    with pytest.raises(RegistryError, match="未知 Catalog category"):
        catalog.list("unknown")
    with pytest.raises(RegistryError, match="未知 Catalog 组件"):
        catalog.get("model", "not-a-model")
