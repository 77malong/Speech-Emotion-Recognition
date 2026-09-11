"""Integration regressions for LO-01 through LO-05 (review baseline 2e4839a)."""

import copy
import json
import random

import numpy as np
import pytest
import torch
import yaml

from scripts.audit_latest_only_review import batch, config, wrap
from ser_lib.cli.workflows import export_checkpoint_artifact
from ser_lib.config import LossConfig, TrainerConfig
from ser_lib.engine import Trainer, load_checkpoint, save_checkpoint, train_experiment
from ser_lib.engine.objectives import ClassificationLoss
from ser_lib.models import CNNBaseline


def test_weighted_fit_metrics_are_partition_invariant():
    expected = torch.nn.functional.cross_entropy(
        torch.tensor([[4.0, 0.0], [4.0, 0.0]]),
        torch.tensor([0, 1]),
        weight=torch.tensor([1.0, 9.0]),
    ).item()
    for chunks in [[batch([0, 1])], [batch([0]), batch([1])]]:
        module = torch.nn.Linear(2, 2, bias=False)
        with torch.no_grad():
            module.weight.copy_(torch.tensor([[4.0, 0.0], [0.0, 0.0]]))
        model = wrap(module)
        events = []
        trainer = Trainer(
            model,
            TrainerConfig(epochs=1),
            optimizer=torch.optim.SGD(model.parameters(), lr=0),
            loss_fn=ClassificationLoss(LossConfig(class_weights=[1.0, 9.0]), 2),
            event_callback=events.append,
        )
        result = trainer.fit(chunks, val_batches=chunks).epochs[0]
        assert result.loss == pytest.approx(expected)
        assert result.validation["loss"] == pytest.approx(expected)
        losses = [
            e.value
            for e in events
            if getattr(e, "name", None) == "loss" and getattr(e, "split", None) == "train"
        ]
        assert losses == pytest.approx([expected])
        progress = [e for e in events if getattr(e, "stage", None) == "train_batch"]
        assert progress[-1].details["running_loss"] == pytest.approx(expected)


def test_resume_relocates_best_for_subsequent_resume(tmp_path):
    base = torch.nn.Linear(2, 2)

    def make(directory, epochs):
        model = wrap(copy.deepcopy(base))
        return Trainer(
            model,
            TrainerConfig(epochs=epochs, checkpoint_dir=directory),
            optimizer=torch.optim.SGD(model.parameters(), lr=0),
        )

    source, destination = tmp_path / "source", tmp_path / "destination"
    a = make(source, 1)
    a.fit([batch([0, 1])], val_batches=[batch([0, 1])])
    original_best = (source / "best.pt").read_bytes()
    b = make(destination, 2)
    b.resume_from(source / "last.pt")
    b.fit([batch([0, 1])], val_batches=[batch([0, 1])])
    assert (destination / "best.pt").read_bytes() == original_best
    (source / "best.pt").unlink()
    (source / "last.pt").unlink()
    c = make(destination, 3)
    c.resume_from(destination / "last.pt")
    assert c.fit([batch([0, 1])], val_batches=[batch([0, 1])]).status == "completed"


def test_fresh_run_does_not_inherit_history(tmp_path):
    cfg = config(tmp_path / "experiment")
    old = train_experiment(cfg)
    cfg = cfg.model_copy(update={"trainer": cfg.trainer.model_copy(update={"epochs": 1})})
    new = train_experiment(cfg)
    assert old.training.run_id != new.training.run_id
    history = json.loads(new.history_path.read_text())
    assert [e["epoch"] for e in history] == [1]
    assert len(new.metrics_log.read_text().splitlines()) == 1


def test_resume_rejects_history_owned_by_another_run(tmp_path):
    cfg = config(tmp_path / "experiment")
    first = train_experiment(cfg)
    checkpoint = tmp_path / "first.pt"
    checkpoint.write_bytes(first.last_checkpoint.read_bytes())
    second = train_experiment(cfg)
    before = second.history_path.read_bytes()
    with pytest.raises(ValueError, match="不同 run"):
        train_experiment(cfg, resume=checkpoint)
    assert second.history_path.read_bytes() == before


@pytest.mark.parametrize("change", ["labels", "both_labels", "preprocessing", "missing_lineage"])
def test_export_rejects_semantic_changes(tmp_path, change):
    cfg = config(tmp_path / "experiment")
    trained = train_experiment(cfg)
    raw = cfg.model_dump(mode="json")
    if change in {"labels", "both_labels"}:
        raw["data"]["labels"] = {0: {"en": "happy"}, 1: {"en": "neutral"}}
        if change == "both_labels":
            manifest = yaml.safe_load(cfg.data.manifest.read_text())
            manifest["labels"] = raw["data"]["labels"]
            cfg.data.manifest.write_text(yaml.safe_dump(manifest))
    elif change == "preprocessing":
        raw["data"]["representation"]["params"]["hop_length"] = 160
    else:
        payload = torch.load(trained.last_checkpoint, weights_only=False)
        payload["metadata"].pop("run_metadata")
        torch.save(payload, trained.last_checkpoint)
    path = tmp_path / "export.yaml"
    path.write_text(yaml.safe_dump(raw))
    destination = tmp_path / "artifact"
    with pytest.raises(ValueError, match="标签|预处理|lineage"):
        export_checkpoint_artifact(path, trained.last_checkpoint, destination)
    assert not destination.exists()


@pytest.mark.parametrize("field", ["python", "numpy", "torch_cpu", "torch_cuda"])
def test_invalid_rng_does_not_mutate_model_or_global_rng(tmp_path, field):
    source = CNNBaseline(feature_dim=16, num_classes=2)
    path = save_checkpoint(tmp_path / "checkpoint.pt", source, None, epoch=1)
    payload = torch.load(path, weights_only=False)
    payload["rng_state"][field] = "invalid"
    torch.save(payload, path)
    target = CNNBaseline(feature_dim=16, num_classes=2)
    weights = copy.deepcopy(target.state_dict())
    python_rng, numpy_rng, torch_rng = (
        random.getstate(),
        np.random.get_state(),
        torch.get_rng_state(),
    )
    with pytest.raises((ValueError, TypeError, AttributeError, RuntimeError)):
        load_checkpoint(path, target)
    assert all(torch.equal(weights[k], v) for k, v in target.state_dict().items())
    assert random.getstate() == python_rng
    current_numpy = np.random.get_state()
    assert current_numpy[0] == numpy_rng[0]
    np.testing.assert_array_equal(current_numpy[1], numpy_rng[1])
    assert current_numpy[2:] == numpy_rng[2:]
    assert torch.equal(torch_rng, torch.get_rng_state())
