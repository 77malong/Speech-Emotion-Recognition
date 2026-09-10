from __future__ import annotations

import json

from ser_lib.config import (
    AdamConfig,
    AdamWConfig,
    CosineSchedulerConfig,
    LossConfig,
    SGDConfig,
    SamplingConfig,
    StepSchedulerConfig,
)
from ser_lib.data import default_registry
from ser_lib.models.registry import model_registry


DATA_NAMESPACES = (
    "representation",
    "waveform_transform",
    "feature_transform",
    "importer",
)


def test_data_registry_exposes_builtin_descriptors_without_catalog_wrapper():
    assert set(default_registry.names("representation")) >= {"waveform", "log_mel"}
    assert set(default_registry.names("importer")) >= {"folder", "csv", "jsonl"}

    seen: set[tuple[str, str]] = set()
    for namespace in DATA_NAMESPACES:
        descriptors = default_registry.descriptors(namespace, statuses=None)
        for descriptor in descriptors:
            key = (namespace, descriptor.id)
            assert key not in seen
            seen.add(key)
            payload = descriptor.to_json_safe()
            assert payload["id"] == descriptor.id
            assert isinstance(payload["config_schema"], dict)
            json.dumps(payload, ensure_ascii=False)


def test_model_registry_exposes_schema_status_and_capabilities_without_instantiation(monkeypatch):
    def forbidden_create(*args, **kwargs):
        raise AssertionError("descriptor query must not instantiate models")

    monkeypatch.setattr(model_registry, "create", forbidden_create)

    assert set(model_registry.names()) >= {
        "cnn_baseline",
        "gru_baseline",
        "transformer_baseline",
        "hf_audio_classifier",
    }

    cnn = model_registry.descriptor("cnn_baseline")
    assert cnn["status"] == "stable"
    assert cnn["input_layouts"] == {"features": "FT"}
    assert cnn["config_schema"]["properties"]["hidden_dim"]["default"] == 128
    assert model_registry.supports_static_spec("cnn_baseline") is True

    hf = model_registry.descriptor("hf_audio_classifier")
    assert hf["status"] == "optional"
    assert hf["input_layouts"] == {"waveform": "T"}
    assert model_registry.supports_static_spec("hf_audio_classifier") is True


def test_training_component_configuration_is_discoverable_from_canonical_schemas():
    adamw = AdamWConfig.model_json_schema()
    assert adamw["properties"]["learning_rate"]["default"] == 0.001
    assert adamw["properties"]["weight_decay"]["default"] == 0.0

    adam = AdamConfig.model_json_schema()
    sgd = SGDConfig.model_json_schema()
    assert adam["properties"]["type"]["default"] == "adam"
    assert sgd["properties"]["momentum"]["default"] == 0.0

    step = StepSchedulerConfig.model_json_schema()
    cosine = CosineSchedulerConfig.model_json_schema()
    assert step["properties"]["step_size"]["default"] == 10
    assert "t_max" in cosine["required"]
    assert cosine["properties"]["eta_min"]["default"] == 0.0

    loss = LossConfig.model_json_schema()
    sampling = SamplingConfig.model_json_schema()
    assert loss["properties"]["type"]["default"] == "cross_entropy"
    assert loss["properties"]["focal_gamma"]["default"] == 2.0
    assert sampling["properties"]["type"]["default"] == "shuffle"
    assert sampling["properties"]["replacement"]["default"] is True
