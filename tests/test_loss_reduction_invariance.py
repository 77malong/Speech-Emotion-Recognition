from __future__ import annotations

import copy

import pytest
import torch
import torch.nn.functional as F

from ser_lib.config.training import LossConfig, TrainerConfig
from ser_lib.data.types import SERBatch, TensorSpec
from ser_lib.engine.evaluator import evaluate
from ser_lib.engine.objectives import ClassificationLoss
from ser_lib.engine.training import Trainer
from ser_lib.models.adapters.torch import TorchModelAdapter


def _batch(features: torch.Tensor, labels: torch.Tensor, offset: int = 0) -> SERBatch:
    size = int(labels.shape[0])
    return SERBatch(
        {"features": features},
        {},
        {},
        labels,
        [f"sample-{offset + index}" for index in range(size)],
        [{} for _ in range(size)],
    )


def _model(module: torch.nn.Linear):
    return TorchModelAdapter.wrap(
        module,
        required_inputs={"features": TensorSpec(layout="D", feature_dim=2)},
        input_map={"input": "inputs.features"},
        num_classes=2,
    )


def _base_linear() -> torch.nn.Linear:
    module = torch.nn.Linear(2, 2, bias=False)
    with torch.no_grad():
        module.weight.copy_(torch.eye(2))
    return module


def test_weighted_evaluation_loss_is_invariant_to_batch_partition():
    features = torch.tensor([[4.0, 0.0], [4.0, 0.0]])
    labels = torch.tensor([0, 1])
    loss_config = LossConfig(type="cross_entropy", class_weights=[1.0, 9.0])
    expected = F.cross_entropy(
        features,
        labels,
        weight=torch.tensor([1.0, 9.0]),
    ).item()

    large = evaluate(
        _model(_base_linear()),
        [_batch(features, labels)],
        num_classes=2,
        loss_fn=ClassificationLoss(loss_config, num_classes=2),
    )
    split = evaluate(
        _model(_base_linear()),
        [_batch(features[:1], labels[:1]), _batch(features[1:], labels[1:], 1)],
        num_classes=2,
        loss_fn=ClassificationLoss(loss_config, num_classes=2),
    )

    assert large.loss == pytest.approx(expected, rel=1e-7, abs=1e-7)
    assert split.loss == pytest.approx(expected, rel=1e-7, abs=1e-7)
    assert split.loss == pytest.approx(large.loss, rel=1e-7, abs=1e-7)


def test_weighted_training_epoch_loss_is_invariant_to_batch_partition():
    features = torch.tensor([[4.0, 0.0], [4.0, 0.0]])
    labels = torch.tensor([0, 1])
    loss_config = LossConfig(type="cross_entropy", class_weights=[1.0, 9.0])
    expected = F.cross_entropy(
        features,
        labels,
        weight=torch.tensor([1.0, 9.0]),
    ).item()

    def run(batches: list[SERBatch]) -> float:
        module = copy.deepcopy(_base_linear())
        model = _model(module)
        trainer = Trainer(
            model,
            TrainerConfig(epochs=1),
            optimizer=torch.optim.SGD(model.parameters(), lr=0.0),
            loss_fn=ClassificationLoss(loss_config, num_classes=2),
        )
        return trainer.train_epoch(batches, epoch=1).loss

    large = run([_batch(features, labels)])
    split = run(
        [_batch(features[:1], labels[:1]), _batch(features[1:], labels[1:], 1)]
    )

    assert large == pytest.approx(expected, rel=1e-7, abs=1e-7)
    assert split == pytest.approx(expected, rel=1e-7, abs=1e-7)
    assert split == pytest.approx(large, rel=1e-7, abs=1e-7)
