from __future__ import annotations

import random
from pathlib import Path

import numpy as np
import pytest
import torch
import yaml

from ser_lib.cli.workflows import export_checkpoint_artifact
from ser_lib.config import LossConfig, TrainerConfig
from ser_lib.data.types import SERBatch, TensorSpec
from ser_lib.engine import (
    Trainer,
    build_experiment_components,
    build_training_metadata,
    load_checkpoint,
    load_training_history,
    save_checkpoint,
    train_experiment,
)
from ser_lib.engine.objectives import ClassificationLoss
from ser_lib.foundation.events import MetricEvent
from ser_lib.models import CNNBaseline, TorchModelAdapter


def _batch(labels: list[int], *, offset: int = 0) -> SERBatch:
    return SERBatch(
        {"features": torch.tensor([[4.0, 0.0]] * len(labels))},
        {},
        {},
        torch.tensor(labels),
        [f"sample-{offset + index}" for index in range(len(labels))],
        [{} for _ in labels],
    )


def _linear_model() -> TorchModelAdapter:
    module = torch.nn.Linear(2, 2, bias=False)
    with torch.no_grad():
        module.weight.copy_(torch.tensor([[4.0, 0.0], [0.0, 0.0]]))
    return TorchModelAdapter.wrap(
        module,
        required_inputs={"features": TensorSpec(layout="D", feature_dim=2)},
        input_map={"input": "inputs.features"},
        num_classes=2,
    )


def _weighted_fit(batches: list[SERBatch]):
    events = []
    model = _linear_model()
    trainer = Trainer(
        model,
        TrainerConfig(epochs=1),
        optimizer=torch.optim.SGD(model.parameters(), lr=0.0),
        loss_fn=ClassificationLoss(
            LossConfig(type="cross_entropy", class_weights=[1.0, 9.0]),
            num_classes=2,
        ),
        event_callback=events.append,
    )
    result = trainer.fit(batches, val_batches=batches)
    return result, events


def test_review_lo01_weighted_validation_is_invariant_to_batch_partition():
    large, _ = _weighted_fit([_batch([0, 1])])
    split, _ = _weighted_fit([_batch([0]), _batch([1], offset=1)])

    large_validation = large.epochs[0].validation
    split_validation = split.epochs[0].validation
    assert large_validation is not None
    assert split_validation is not None
    assert split_validation["loss"] == pytest.approx(
        large_validation["loss"], rel=1e-7, abs=1e-7
    )


def test_review_lo01_training_loss_event_matches_training_result():
    result, events = _weighted_fit([_batch([0]), _batch([1], offset=1)])

    loss_events = [
        event
        for event in events
        if isinstance(event, MetricEvent)
        and event.name == "loss"
        and event.split == "train"
        and event.step == 1
    ]
    assert len(loss_events) == 1
    assert loss_events[0].value == pytest.approx(
        result.epochs[0].loss, rel=1e-7, abs=1e-7
    )


def _resume_trainer(checkpoint_dir: Path, *, epochs: int) -> Trainer:
    model = _linear_model()
    return Trainer(
        model,
        TrainerConfig(epochs=epochs, checkpoint_dir=checkpoint_dir),
        optimizer=torch.optim.SGD(model.parameters(), lr=0.0),
    )


def test_review_lo02_moved_checkpoint_directory_supports_second_resume(tmp_path: Path):
    batches = [_batch([0, 1])]
    source_dir = tmp_path / "source"
    destination_dir = tmp_path / "destination"

    source = _resume_trainer(source_dir, epochs=1)
    source.fit(batches, val_batches=batches)
    assert (source_dir / "best.pt").is_file()

    moved = _resume_trainer(destination_dir, epochs=2)
    moved.resume_from(source_dir / "last.pt")
    moved.fit(batches, val_batches=batches)
    assert (destination_dir / "last.pt").is_file()

    second_resume = _resume_trainer(destination_dir, epochs=3)
    second_resume.resume_from(destination_dir / "last.pt")


def test_review_lo03_export_rejects_swapped_checkpoint_label_semantics(
    current_experiment_config,
    tmp_path: Path,
):
    config = current_experiment_config
    components = build_experiment_components(config, train=False)
    lineage = build_training_metadata(
        run_id="run-label-contract",
        model_id=components.model.model_spec.model_id,
        config=config.model_dump(mode="json"),
        seed=config.trainer.seed,
        device="cpu",
        library_version="0.3.0",
    )
    checkpoint = save_checkpoint(
        tmp_path / "label-contract.pt",
        components.model,
        None,
        epoch=1,
        metadata={"run_metadata": lineage.to_dict()},
        trainer_config=config.trainer.model_dump(mode="json"),
    )

    raw = config.model_dump(mode="json")
    raw["data"]["labels"] = {
        0: {"en": "happy"},
        1: {"en": "neutral"},
    }
    swapped_config = tmp_path / "swapped-labels.yaml"
    swapped_config.write_text(
        yaml.safe_dump(raw, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    destination = tmp_path / "artifact"

    with pytest.raises(ValueError, match="标签|label"):
        export_checkpoint_artifact(swapped_config, checkpoint, destination)

    assert not destination.exists()


def test_review_lo04_fresh_run_does_not_inherit_previous_history(
    current_experiment_config,
):
    config = current_experiment_config
    first = config.model_copy(
        update={"trainer": config.trainer.model_copy(update={"epochs": 2})}
    )
    first_result = train_experiment(first, batch_size=2)

    second = config.model_copy(
        update={"trainer": config.trainer.model_copy(update={"epochs": 1})}
    )
    second_result = train_experiment(second, batch_size=2)

    assert first_result.training.run_id != second_result.training.run_id
    history = load_training_history(config.output_dir)
    assert [epoch.epoch for epoch in history.epochs] == [1]
    assert history.epoch_count == second_result.run.epochs_completed


def test_review_lo05_failed_checkpoint_load_does_not_mutate_model(tmp_path: Path):
    source = CNNBaseline(feature_dim=16, num_classes=2)
    with torch.no_grad():
        for parameter in source.parameters():
            parameter.fill_(1.0)
    checkpoint = save_checkpoint(
        tmp_path / "invalid-rng.pt",
        source,
        None,
        epoch=1,
    )
    payload = torch.load(checkpoint, weights_only=False)
    payload["rng_state"]["numpy"] = "not a numpy state"
    torch.save(payload, checkpoint)

    target = CNNBaseline(feature_dim=16, num_classes=2)
    with torch.no_grad():
        for parameter in target.parameters():
            parameter.zero_()
    before = {name: value.detach().clone() for name, value in target.state_dict().items()}

    python_rng = random.getstate()
    numpy_rng = np.random.get_state()
    torch_rng = torch.get_rng_state()
    try:
        with pytest.raises((TypeError, ValueError)):
            load_checkpoint(checkpoint, target)

        assert all(
            torch.equal(before[name], value)
            for name, value in target.state_dict().items()
        )
    finally:
        random.setstate(python_rng)
        np.random.set_state(numpy_rng)
        torch.set_rng_state(torch_rng)
