import copy

import pytest
import torch

from scripts.audit_latest_only_review import batch, wrap
from ser_lib.config import TrainerConfig
from ser_lib.engine import Trainer, load_checkpoint, save_checkpoint
from ser_lib.models import CNNBaseline


def make_trainer(path, epochs=2, save_best=True):
    torch.manual_seed(9)
    model = wrap(torch.nn.Linear(2, 2))
    return Trainer(
        model,
        TrainerConfig(epochs=epochs, checkpoint_dir=path, save_best=save_best),
        optimizer=torch.optim.SGD(model.parameters(), lr=0.2, momentum=0.9),
    )


def train(trainer):
    return trainer.fit([batch([0])], val_batches=[batch([0])])


def test_historical_best_is_immutable(tmp_path):
    trainer = make_trainer(tmp_path)
    train(trainer)
    old = torch.load(tmp_path / "epoch-0001.pt", weights_only=False)
    snapshot = tmp_path / old["metadata"]["best_checkpoint"]
    contents = snapshot.read_bytes()
    resumed = make_trainer(tmp_path, 3)
    resumed.resume_from(tmp_path / "epoch-0001.pt")
    assert resumed.best_epoch == 1
    assert torch.load(resumed._best_checkpoint, weights_only=False)["epoch"] == 1
    train(resumed)
    assert snapshot.read_bytes() == contents


@pytest.mark.parametrize("fault", ["missing_best", "wrong_best", "sampler", "counter"])
def test_resume_metadata_failure_preserves_runtime(tmp_path, fault):
    train(make_trainer(tmp_path))
    path = tmp_path / "last.pt"
    payload = torch.load(path, weights_only=False)
    if fault == "missing_best":
        (tmp_path / payload["metadata"]["best_checkpoint"]).unlink()
    elif fault == "wrong_best":
        payload["metadata"]["best_epoch"] = 99
    elif fault == "sampler":
        payload["metadata"]["sampling_generator_state"] = torch.zeros(1, dtype=torch.uint8)
    else:
        payload["metadata"]["optimizer_step_attempted"] = 0
    torch.save(payload, path)
    resumed = make_trainer(tmp_path, 3)
    generator = torch.Generator().manual_seed(7)
    resumed.attach_sampling_generator(generator)
    before = copy.deepcopy(resumed.model.state_dict())
    rng = torch.get_rng_state()
    sampling = generator.get_state()
    with pytest.raises((ValueError, RuntimeError, FileNotFoundError)):
        resumed.resume_from(path)
    assert resumed.last_completed_epoch == 0
    assert resumed.optimizer_step == 0
    assert not resumed.optimizer.state
    assert all(torch.equal(before[k], v) for k, v in resumed.model.state_dict().items())
    assert torch.equal(rng, torch.get_rng_state())
    assert torch.equal(sampling, generator.get_state())


@pytest.mark.parametrize("fault", ["model", "optimizer"])
def test_component_load_failure_rolls_back(tmp_path, fault):
    source = CNNBaseline(feature_dim=16, num_classes=2)
    path = save_checkpoint(
        tmp_path / "state.pt", source, torch.optim.Adam(source.parameters()), epoch=1
    )
    payload = torch.load(path, weights_only=False)
    if fault == "model":
        payload["model_state"]["classifier.bias"] = torch.zeros(3)
    else:
        payload["optimizer_state"]["param_groups"] = []
    torch.save(payload, path)
    target = CNNBaseline(feature_dim=16, num_classes=2)
    optimizer = torch.optim.Adam(target.parameters(), lr=0.123)
    before = copy.deepcopy(target.state_dict())
    with pytest.raises((RuntimeError, ValueError)):
        load_checkpoint(path, target, optimizer)
    assert all(torch.equal(before[k], v) for k, v in target.state_dict().items())
    assert optimizer.param_groups[0]["lr"] == 0.123


def test_step_counters_survive_resume(tmp_path):
    train(make_trainer(tmp_path))
    resumed = make_trainer(tmp_path, 3)
    resumed.resume_from(tmp_path / "last.pt")
    assert resumed.optimizer_step == resumed.optimizer_step_attempted == 2
    assert resumed.optimizer_step_skipped == 0
    train(resumed)
    assert resumed.optimizer_step == resumed.optimizer_step_attempted == 3


def test_resume_without_saving_best(tmp_path):
    train(make_trainer(tmp_path, save_best=False))
    resumed = make_trainer(tmp_path, 3, save_best=False)
    resumed.resume_from(tmp_path / "last.pt")
    assert resumed._best_checkpoint is None
    assert train(resumed).status == "completed"
