from __future__ import annotations

import random

import numpy as np
import torch

from ser_lib.engine.config import build_experiment_components, load_experiment_config


def _valid_release_config():
    config = load_experiment_config("tests/fixtures/release_compat/experiment_v1.yaml")
    raw = config.model_dump()
    raw["data"]["representation"]["params"]["n_mels"] = 16
    raw["model"]["params"]["feature_dim"] = 16
    return type(config).model_validate(raw)


def test_experiment_component_build_seeds_model_initialization_before_construction() -> None:
    config = _valid_release_config()
    states: list[torch.Tensor] = []

    for ambient_seed in (111, 222):
        random.seed(ambient_seed)
        np.random.seed(ambient_seed)
        torch.manual_seed(ambient_seed)
        components = build_experiment_components(config)
        states.append(next(components.model.parameters()).detach().clone())

    torch.testing.assert_close(states[0], states[1], rtol=0.0, atol=0.0)


def test_experiment_component_build_resets_python_numpy_and_torch_rngs() -> None:
    config = _valid_release_config()
    samples: list[tuple[float, float, torch.Tensor]] = []

    for ambient_seed in (333, 444):
        random.seed(ambient_seed)
        np.random.seed(ambient_seed)
        torch.manual_seed(ambient_seed)
        build_experiment_components(config)
        samples.append((random.random(), float(np.random.random()), torch.rand(4)))

    assert samples[0][0] == samples[1][0]
    assert samples[0][1] == samples[1][1]
    torch.testing.assert_close(samples[0][2], samples[1][2], rtol=0.0, atol=0.0)
