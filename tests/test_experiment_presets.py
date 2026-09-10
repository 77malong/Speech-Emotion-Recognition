from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from ser_lib.config import parse_optimizer_config, parse_scheduler_config
from ser_lib.data import default_registry
from ser_lib.engine import (
    ExperimentConfig,
    build_experiment_config,
    get_experiment_preset,
    list_experiment_presets,
)
from ser_lib.models.registry import model_registry


def test_experiment_preset_catalog_is_stable_and_json_safe():
    catalog = list_experiment_presets()

    assert [item.preset_id for item in catalog.presets] == [
        "cnn_logmel_baseline",
        "gru_mfcc_baseline",
        "transformer_logmel_baseline",
    ]
    assert all(item.status == "stable" for item in catalog.presets)
    json.dumps(catalog.to_dict())


def test_each_preset_builds_existing_experiment_config_and_registered_components():
    for preset in list_experiment_presets().presets:
        config = build_experiment_config(preset.preset_id)
        assert isinstance(config, ExperimentConfig)
        model_registry.descriptor(config.model.type)
        default_registry.get_entry("representation", config.data.representation.type)
        parse_optimizer_config(config.optimizer)
        parse_scheduler_config(config.scheduler)
        assert config.loss.type in {"cross_entropy", "focal"}
        assert config.sampling.type in {"shuffle", "weighted"}
        json.dumps(config.model_dump(mode="json"))


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
    assert get_experiment_preset("gru_mfcc_baseline").display_name.startswith("GRU")
    with pytest.raises(KeyError, match="未知 experiment preset"):
        get_experiment_preset("missing")
    with pytest.raises(KeyError, match="未知 experiment preset"):
        build_experiment_config("missing")
