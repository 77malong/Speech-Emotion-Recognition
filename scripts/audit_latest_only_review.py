"""Offline review probes for 2e4839a; all data lives in a disposable directory."""

from __future__ import annotations

import copy
import json
import tempfile
from pathlib import Path

import numpy as np
import soundfile as sf
import torch
import yaml

from ser_lib.config import ExperimentConfig, LossConfig, TrainerConfig
from ser_lib.data.types import SERBatch, TensorSpec
from ser_lib.engine import Trainer, load_checkpoint, save_checkpoint, train_experiment
from ser_lib.engine.objectives import ClassificationLoss
from ser_lib.models import CNNBaseline, TorchModelAdapter


def wrap(module):
    return TorchModelAdapter.wrap(
        module,
        required_inputs={"features": TensorSpec(layout="D", feature_dim=2)},
        input_map={"input": "inputs.features"},
        num_classes=2,
    )


def batch(labels):
    n = len(labels)
    return SERBatch(
        {"features": torch.tensor([[1.0, 0.0]] * n)},
        {},
        {},
        torch.tensor(labels),
        [str(i) for i in range(n)],
        [{} for _ in range(n)],
    )


def weighted_validation(root):
    result = []
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
        fit = trainer.fit(chunks, val_batches=chunks)
        train_loss_events = [
            e.value
            for e in events
            if getattr(e, "name", None) == "loss" and getattr(e, "split", None) == "train"
        ]
        result.append(
            {
                "batches": len(chunks),
                "training_loss": fit.epochs[0].loss,
                "validation_loss": fit.epochs[0].validation["loss"],
                "training_loss_events": train_loss_events,
            }
        )
    assert abs(result[0]["validation_loss"] - result[1]["validation_loss"]) > 1
    return result


def moved_resume(root):
    base = torch.nn.Linear(2, 2)

    def trainer(directory, epochs):
        model = wrap(copy.deepcopy(base))
        return Trainer(
            model,
            TrainerConfig(epochs=epochs, checkpoint_dir=directory),
            optimizer=torch.optim.SGD(model.parameters(), lr=0),
        )

    a = trainer(root / "source", 1)
    a.fit([batch([0, 1])], val_batches=[batch([0, 1])])
    b = trainer(root / "destination", 2)
    b.resume_from(root / "source" / "last.pt")
    b.fit([batch([0, 1])], val_batches=[batch([0, 1])])
    checkpoint = root / "destination" / "last.pt"
    c = trainer(root / "destination", 3)
    try:
        c.resume_from(checkpoint)
    except FileNotFoundError as exc:
        return {
            "first_resume_succeeded": True,
            "saved_best_reference": torch.load(checkpoint, weights_only=False)["metadata"][
                "best_checkpoint"
            ],
            "best_only_in_source": (root / "source" / "best.pt").exists()
            and not (root / "destination" / "best.pt").exists(),
            "second_resume_error": str(exc),
        }
    raise AssertionError("Expected dangling best checkpoint reference")


def config(root):
    root.mkdir()
    t = np.arange(1600) / 16000
    for label in range(2):
        sf.write(root / f"{label}.wav", 0.2 * np.sin(2 * np.pi * (220 + 110 * label) * t), 16000)
    (root / "train.jsonl").write_text(
        "\n".join(
            json.dumps({"uid": str(i), "audio_path": f"{i}.wav", "label": i}) for i in range(2)
        )
        + "\n"
    )
    labels = {0: {"en": "neutral"}, 1: {"en": "happy"}}
    path = root / "dataset.yaml"
    path.write_text(
        yaml.safe_dump(
            {
                "dataset_id": "audit",
                "root": str(root),
                "splits": {"train": "train.jsonl"},
                "labels": labels,
            }
        )
    )
    return ExperimentConfig.model_validate(
        {
            "data": {
                "manifest": path,
                "labels": labels,
                "cache": {"enabled": False},
                "representation": {
                    "type": "log_mel",
                    "params": {"n_fft": 256, "win_length": 256, "hop_length": 80, "n_mels": 16},
                },
            },
            "model": {
                "type": "cnn_baseline",
                "params": {"feature_dim": 16, "num_classes": 2, "hidden_dim": 6, "dropout": 0.0},
            },
            "trainer": {"epochs": 2, "checkpoint_dir": root / "checkpoints"},
            "output_dir": root / "run",
        }
    )


def history_and_export(root):
    from ser_lib.cli.workflows import export_checkpoint_artifact
    from ser_lib.artifacts import load_model_artifact

    cfg = config(root / "experiment")
    a = train_experiment(cfg)
    one_epoch = cfg.model_copy(update={"trainer": cfg.trainer.model_copy(update={"epochs": 1})})
    b = train_experiment(one_epoch)
    history = json.loads((cfg.output_dir / "history.json").read_text())
    result = {
        "different_runs": a.training.run_id != b.training.run_id,
        "new_run_epochs": b.run.epochs_completed,
        "history_epochs": [e["epoch"] for e in history],
        "metrics_lines": len((cfg.output_dir / "metrics.jsonl").read_text().splitlines()),
    }
    raw = one_epoch.model_dump(mode="json")
    raw["data"]["labels"] = {0: {"en": "happy"}, 1: {"en": "neutral"}}
    cfg_path = root / "relabeled.yaml"
    cfg_path.write_text(yaml.safe_dump(raw))
    artifact = root / "relabeled_artifact"
    exported = export_checkpoint_artifact(cfg_path, b.last_checkpoint, artifact)
    loaded = load_model_artifact(artifact)
    result["checkpoint_labels"] = torch.load(b.last_checkpoint, weights_only=False)["metadata"][
        "run_metadata"
    ]["config"]["data"]["labels"]
    result["exported_labels"] = loaded.manifest.labels
    result["export_success"] = exported["artifact"] == str(artifact)
    assert result["different_runs"] and result["history_epochs"] == [1, 2]
    assert loaded.manifest.labels == {0: "happy", 1: "neutral"}
    return result


def malformed_rng(root):
    source = CNNBaseline(feature_dim=16, num_classes=2)
    path = save_checkpoint(root / "invalid-rng.pt", source, None, epoch=1)
    payload = torch.load(path, weights_only=False)
    payload["rng_state"]["numpy"] = "not a numpy state"
    torch.save(payload, path)
    target = CNNBaseline(feature_dim=16, num_classes=2)
    before = {k: v.clone() for k, v in target.state_dict().items()}
    try:
        load_checkpoint(path, target)
    except (TypeError, ValueError) as exc:
        changed = any(not torch.equal(before[k], v) for k, v in target.state_dict().items())
        assert changed
        return {
            "error": f"{type(exc).__name__}: {exc}",
            "model_changed_despite_failed_load": changed,
        }
    raise AssertionError("Expected invalid RNG rejection")


def main():
    with tempfile.TemporaryDirectory(prefix="ser-latest-review-") as directory:
        root = Path(directory)
        results = {}
        for probe in [weighted_validation, moved_resume, history_and_export, malformed_rng]:
            try:
                results[probe.__name__] = probe(root)
            except Exception as exc:
                results[probe.__name__] = {"probe_error": f"{type(exc).__name__}: {exc}"}
        print(json.dumps(results, ensure_ascii=False, indent=2))
        assert not any("probe_error" in value for value in results.values())


if __name__ == "__main__":
    main()
