from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from ser_lib.config import (
    ExperimentConfig,
    build_experiment_config,
    get_experiment_preset_payload,
    list_experiment_preset_ids,
    parse_optimizer_config,
    parse_scheduler_config,
)
from ser_lib.data import default_registry
from ser_lib.models.registry import model_registry


def test_experiment_preset_ids_and_payloads_are_stable_and_json_safe():
    preset_ids = list_experiment_preset_ids()

    assert preset_ids == (
        "cnn_logmel_baseline",
        "gru_mfcc_baseline",
        "transformer_logmel_baseline",
    )
    for preset_id in preset_ids:
        payload = get_experiment_preset_payload(preset_id)
        assert payload["model"]["type"]
        json.dumps(payload)


def test_each_preset_builds_existing_experiment_config_and_registered_components():
    for preset_id in list_experiment_preset_ids():
        config = build_experiment_config(preset_id)
        assert isinstance(config, ExperimentConfig)
        model_registry.descriptor(config.model.type)
        default_registry.get_entry("representation", config.data.representation.type)
        parse_optimizer_config(config.optimizer)
        parse_scheduler_config(config.scheduler)
        assert config.loss.type in {"cross_entropy", "focal"}
        assert config.sampling.type in {"shuffle", "weighted"}
        json.dumps(config.model_dump(mode="json"))


def test_preset_payload_is_deep_copied():
    first = get_experiment_preset_payload("cnn_logmel_baseline")
    first["model"]["type"] = "mutated"

    second = get_experiment_preset_payload("cnn_logmel_baseline")

    assert second["model"]["type"] == "cnn_baseline"


def test_preset_overrides_are_deep_merged_then_strictly_validated(tmp_path: Path):
    config = build_experiment_config(
        "cnn_logmel_baseline",
        {
            "data": {"manifest": tmp_path / "dataset.yaml"},
            "trainer": {"epochs": 3, "device": "cpu"},
            "output_dir": tmp_path / "run",
        },
    )

    assert config.data.manifest == tmp_path / "dataset.yaml"
    assert config.data.representation.type == "log_mel"
    assert config.trainer.epochs == 3
    assert config.trainer.monitor == "val_uar"
    assert config.output_dir == tmp_path / "run"

    with pytest.raises(ValidationError):
        build_experiment_config(
            "cnn_logmel_baseline",
            {"trainer": {"unknown_option": True}},
        )


def test_preset_lookup_rejects_unknown_id():
    payload = get_experiment_preset_payload("gru_mfcc_baseline")
    assert payload["model"]["type"] == "gru_baseline"
    with pytest.raises(KeyError, match="未知 experiment preset"):
        get_experiment_preset_payload("missing")
    with pytest.raises(KeyError, match="未知 experiment preset"):
        build_experiment_config("missing")
