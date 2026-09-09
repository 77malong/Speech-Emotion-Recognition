from __future__ import annotations

import json

from ser_lib.engine import ExperimentConfig
from ser_lib.services import CatalogService


def test_catalog_service_exposes_experiment_preset_workflow():
    catalog = CatalogService.presets()
    assert catalog.total >= 3
    json.dumps(catalog.to_dict())

    preset = CatalogService.get_preset("cnn_logmel_baseline")
    assert preset.preset_id == "cnn_logmel_baseline"

    config = CatalogService.build_experiment(
        "cnn_logmel_baseline",
        overrides={"trainer": {"epochs": 2}, "output_dir": "runs/service-preset"},
    )
    assert isinstance(config, ExperimentConfig)
    assert config.trainer.epochs == 2
    assert config.output_dir.as_posix() == "runs/service-preset"
