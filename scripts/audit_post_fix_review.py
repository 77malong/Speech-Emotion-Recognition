"""Reproduce remaining checkpoint defects on 3e4c66a, using temporary data."""

import copy
import json
import tempfile
from pathlib import Path

import torch

from scripts.audit_latest_only_review import batch, wrap
from ser_lib.config import TrainerConfig
from ser_lib.engine import Trainer, load_checkpoint, save_checkpoint
from ser_lib.models import CNNBaseline


def main():
    with tempfile.TemporaryDirectory(prefix="ser-post-fix-") as directory:
        root = Path(directory)
        torch.manual_seed(9)
        base = torch.nn.Linear(2, 2)

        def trainer(epochs):
            model = wrap(copy.deepcopy(base))
            return Trainer(
                model,
                TrainerConfig(epochs=epochs, checkpoint_dir=root),
                optimizer=torch.optim.SGD(model.parameters(), lr=0.2),
            )

        a = trainer(2)
        a.fit([batch([0])], val_batches=[batch([0])])
        b = trainer(3)
        b.resume_from(root / "epoch-0001.pt")
        best = torch.load(b._best_checkpoint, weights_only=False)
        assert b.best_epoch == 1 and best["epoch"] == 2
        results = {
            "historical_best": {
                "resumed_epoch": b.last_completed_epoch,
                "metadata_best_epoch": b.best_epoch,
                "referenced_best_actual_epoch": best["epoch"],
            }
        }
        results["resume_counters"] = {
            "applied": b.optimizer_step,
            "attempted": b.optimizer_step_attempted,
            "skipped": b.optimizer_step_skipped,
        }
        assert b.optimizer_step > b.optimizer_step_attempted

        (root / "best.pt").unlink()
        c = trainer(3)
        before = copy.deepcopy(c.model.state_dict())
        try:
            c.resume_from(root / "last.pt")
        except FileNotFoundError as exc:
            changed = any(not torch.equal(before[k], v) for k, v in c.model.state_dict().items())
            assert changed and c.last_completed_epoch == 2
            results["missing_best_partial_restore"] = {
                "error": str(exc),
                "model_changed": changed,
                "last_completed_epoch_after_error": c.last_completed_epoch,
            }
        else:
            raise AssertionError("Expected missing best rejection")

        source = CNNBaseline(feature_dim=16, num_classes=2)
        path = save_checkpoint(root / "bad-model.pt", source, None, epoch=1)
        payload = torch.load(path, weights_only=False)
        payload["model_state"]["classifier.bias"] = torch.zeros(3)
        torch.save(payload, path)
        target = CNNBaseline(feature_dim=16, num_classes=2)
        before = copy.deepcopy(target.state_dict())
        try:
            load_checkpoint(path, target)
        except RuntimeError as exc:
            changed = any(not torch.equal(before[k], v) for k, v in target.state_dict().items())
            assert changed
            results["invalid_model_partial_restore"] = {"error": str(exc), "model_changed": changed}
        else:
            raise AssertionError("Expected invalid model rejection")
        print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
