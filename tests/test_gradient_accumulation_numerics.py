from __future__ import annotations

import copy

import pytest
import torch

from ser_lib.config.training import LossConfig, TrainerConfig
from ser_lib.data.types import SERBatch, TensorSpec
from ser_lib.engine.training import EpochResult
from ser_lib.engine.objectives import ClassificationLoss
from ser_lib.engine.training import Trainer
from ser_lib.models.adapters.torch import TorchModelAdapter


def _batch(features: torch.Tensor, labels: torch.Tensor) -> SERBatch:
    size = int(labels.shape[0])
    return SERBatch(
        {"features": features},
        {},
        {},
        labels,
        [f"sample-{index}" for index in range(size)],
        [{} for _ in range(size)],
    )


def _model(module: torch.nn.Module):
    return TorchModelAdapter.wrap(
        module,
        required_inputs={"features": TensorSpec(layout="D", feature_dim=2)},
        input_map={"input": "inputs.features"},
        num_classes=2,
    )


def _train_details(
    base: torch.nn.Linear,
    batches: list[SERBatch],
    *,
    accumulation_steps: int,
    loss_fn: torch.nn.Module | None = None,
    device: str = "cpu",
    amp: bool = False,
) -> tuple[torch.Tensor, EpochResult, Trainer]:
    module = copy.deepcopy(base)
    model = _model(module)
    optimizer = torch.optim.SGD(model.parameters(), lr=0.1)
    trainer = Trainer(
        model,
        TrainerConfig(
            epochs=1,
            device=device,
            amp=amp,
            gradient_accumulation_steps=accumulation_steps,
        ),
        optimizer=optimizer,
        loss_fn=loss_fn,
    )
    result = trainer.train_epoch(batches, epoch=1)
    return module.weight.detach().cpu().clone(), result, trainer


def _train_once(
    base: torch.nn.Linear,
    batches: list[SERBatch],
    *,
    accumulation_steps: int,
    loss_fn: torch.nn.Module | None = None,
    device: str = "cpu",
    amp: bool = False,
) -> torch.Tensor:
    weights, result, _ = _train_details(
        base,
        batches,
        accumulation_steps=accumulation_steps,
        loss_fn=loss_fn,
        device=device,
        amp=amp,
    )
    assert result.optimizer_steps == 1
    return weights


def test_tail_accumulation_matches_single_large_batch_with_uneven_microbatches():
    torch.manual_seed(7)
    base = torch.nn.Linear(2, 2, bias=False)
    features = torch.tensor(
        [[1.0, 2.0], [-1.0, 0.5], [0.25, -0.75], [2.0, -1.0], [0.5, 1.5]]
    )
    labels = torch.tensor([0, 1, 1, 0, 1])

    large = _train_once(base, [_batch(features, labels)], accumulation_steps=1)
    micro = _train_once(
        base,
        [
            _batch(features[:2], labels[:2]),
            _batch(features[2:3], labels[2:3]),
            _batch(features[3:], labels[3:]),
        ],
        accumulation_steps=4,
    )

    assert torch.allclose(micro, large, atol=1e-7, rtol=1e-6)


def test_weighted_cross_entropy_accumulation_uses_weight_mass_denominator():
    torch.manual_seed(11)
    base = torch.nn.Linear(2, 2, bias=False)
    features = torch.tensor(
        [[1.0, 0.0], [0.0, 1.0], [1.0, 1.0], [-1.0, 0.5], [0.5, -1.0]]
    )
    labels = torch.tensor([0, 1, 1, 0, 1])
    config = LossConfig(type="cross_entropy", class_weights=[1.0, 3.0])

    large = _train_once(
        base,
        [_batch(features, labels)],
        accumulation_steps=1,
        loss_fn=ClassificationLoss(config, num_classes=2),
    )
    micro = _train_once(
        base,
        [
            _batch(features[:1], labels[:1]),
            _batch(features[1:4], labels[1:4]),
            _batch(features[4:], labels[4:]),
        ],
        accumulation_steps=4,
        loss_fn=ClassificationLoss(config, num_classes=2),
    )

    assert torch.allclose(micro, large, atol=1e-7, rtol=1e-6)


def test_single_tail_microbatch_is_not_divided_by_configured_accumulation_steps():
    torch.manual_seed(13)
    base = torch.nn.Linear(2, 2, bias=False)
    features = torch.tensor([[1.0, 2.0]])
    labels = torch.tensor([0])

    reference = _train_once(base, [_batch(features, labels)], accumulation_steps=1)
    accumulated = _train_once(base, [_batch(features, labels)], accumulation_steps=4)

    assert torch.allclose(accumulated, reference, atol=1e-7, rtol=1e-6)


@pytest.mark.skipif(not torch.cuda.is_available(), reason="CUDA required for AMP numerical check")
def test_amp_tail_accumulation_matches_large_batch_and_applies_real_step():
    torch.manual_seed(17)
    base = torch.nn.Linear(2, 2, bias=False)
    initial = base.weight.detach().clone()
    features = torch.tensor(
        [[1.0, 2.0], [-1.0, 0.5], [0.25, -0.75], [2.0, -1.0], [0.5, 1.5]]
    )
    labels = torch.tensor([0, 1, 1, 0, 1])

    fp32 = _train_once(base, [_batch(features, labels)], accumulation_steps=1)
    large, large_result, large_trainer = _train_details(
        base,
        [_batch(features, labels)],
        accumulation_steps=1,
        device="cuda",
        amp=True,
    )
    micro, micro_result, micro_trainer = _train_details(
        base,
        [_batch(features[:2], labels[:2]), _batch(features[2:], labels[2:])],
        accumulation_steps=4,
        device="cuda",
        amp=True,
    )

    assert torch.linalg.vector_norm(large - initial).item() > 0
    assert torch.linalg.vector_norm(micro - initial).item() > 0
    assert torch.allclose(large, fp32, atol=5e-4, rtol=5e-4)
    assert torch.allclose(micro, fp32, atol=5e-4, rtol=5e-4)
    assert torch.allclose(micro, large, atol=5e-4, rtol=5e-4)

    assert large_result.optimizer_steps == 1
    assert micro_result.optimizer_steps == 1
    assert large_trainer.optimizer_step_attempted == 1
    assert micro_trainer.optimizer_step_attempted == 1
    assert large_trainer.optimizer_step == 1
    assert micro_trainer.optimizer_step == 1
    assert large_trainer.optimizer_step_skipped == 0
    assert micro_trainer.optimizer_step_skipped == 0
