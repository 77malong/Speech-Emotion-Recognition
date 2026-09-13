"""Offline integration probes for review baseline 64ff7e2."""

import json
import tempfile
from pathlib import Path
from types import SimpleNamespace

import torch
import yaml

from scripts.audit_latest_only_review import batch, config
from ser_lib.cli.workflows import export_checkpoint_artifact
from ser_lib.engine import Trainer, evaluate, evaluate_artifact, train_experiment
from ser_lib.config import TrainerConfig
from ser_lib.engine.evaluation_reports import inspect_evaluation_report, iter_evaluation_predictions
from ser_lib.inference import PredictionResult, StreamingConfig, StreamingEmotionRecognizer
from ser_lib.models import CNNBaseline
from ser_lib.models.base import ModelOutput


def rewind_history(root):
    cfg = config(root / "rewind")
    cfg = cfg.model_copy(update={"trainer": cfg.trainer.model_copy(update={"epochs": 4})})
    train_experiment(cfg)
    cfg = cfg.model_copy(update={"trainer": cfg.trainer.model_copy(update={"epochs": 2})})
    resumed = train_experiment(cfg, resume=cfg.trainer.checkpoint_dir / "epoch-0001.pt")
    epochs = [row["epoch"] for row in json.loads(resumed.history_path.read_text())]
    metrics = [json.loads(row)["epoch"] for row in resumed.metrics_log.read_text().splitlines()]
    assert resumed.run.last_epoch == 2 and epochs == [1, 2, 3, 4]
    return {
        "last_epoch": resumed.run.last_epoch,
        "history_epochs": epochs,
        "metric_epochs": metrics,
    }


def stale_evaluation(root):
    cfg = config(root / "evaluation")
    trained = train_experiment(cfg)
    path = root / "export.yaml"
    path.write_text(yaml.safe_dump(cfg.model_dump(mode="json")))
    artifact = root / "artifact"
    export_checkpoint_artifact(path, trained.last_checkpoint, artifact)
    directory = root / "report"
    evaluate_artifact(artifact, split="train", output=directory)
    old_predictions = (directory / "predictions.jsonl").read_bytes()
    records = cfg.data.manifest.parent / "train.jsonl"
    records.write_text(records.read_text().splitlines()[0] + "\n")
    current = evaluate_artifact(artifact, split="train", output=directory, retain_predictions=False)
    try:
        inspect_evaluation_report(directory)
    except ValueError as exc:
        inspection_error = str(exc)
        assert "metric_unit" in inspection_error
    else:
        raise AssertionError("Expected current report schema mismatch")
    fresh = evaluate_artifact(
        artifact, split="train", output=root / "fresh_report", retain_predictions=False
    )
    assert fresh.run.predictions_file == "predictions.jsonl"
    assert not (fresh.output_dir / fresh.run.predictions_file).exists()
    old_count = len(list(iter_evaluation_predictions(directory)))
    assert current.evaluation.sample_count == 1 and old_count == 2
    assert (directory / "predictions.jsonl").read_bytes() == old_predictions
    return {
        "current_samples": current.evaluation.sample_count,
        "returned_predictions_path": current.predictions_path,
        "record_predictions_file": current.run.predictions_file,
        "report_inspection_error": inspection_error,
        "readable_prediction_rows": old_count,
        "fresh_record_references_missing_predictions": True,
    }


class FailingPredictor:
    def __init__(self):
        self.audio_loader = SimpleNamespace(
            config=SimpleNamespace(target_sample_rate=8, normalize_peak=False)
        )
        self.labels = {0: "neutral", 1: "happy"}
        self.calls = 0

    def predict_audio(self, audio, *, uid):
        self.calls += 1
        if self.calls == 2:
            raise RuntimeError("transient inference error")
        return PredictionResult(uid, 0, "neutral", 0.8, [0.8, 0.2])


def stream_delivery(root):
    session = StreamingEmotionRecognizer(
        FailingPredictor(),
        StreamingConfig(input_sample_rate=8, window_ms=500, hop_ms=500, max_chunk_ms=2000),
    )
    try:
        session.push_pcm(torch.ones(12))
    except RuntimeError:
        pass
    else:
        raise AssertionError("Expected transient failure")
    delivered = session.push_pcm(torch.empty(0))
    sequences = [item.sequence for item in delivered]
    assert sequences == [1, 2]
    return {"sequences_delivered_after_retry": sequences, "sequence_zero_lost": True}


class NonfiniteModel(CNNBaseline):
    def forward(self, batch):
        return ModelOutput(
            logits=torch.full((len(batch.labels), 2), float("nan")),
            loss=self.classifier.weight.sum() * 0,
        )


def nonfinite_logits(root):
    model = NonfiniteModel(feature_dim=16, num_classes=2)
    result = evaluate(model, [batch([0])], num_classes=2)
    training = Trainer(model, TrainerConfig(epochs=1)).fit([batch([0])])
    assert result.accuracy == 1 and training.status == "completed"
    assert torch.isnan(torch.tensor(result.predictions[0].confidence))
    return {
        "evaluation_accuracy": result.accuracy,
        "evaluation_loss": result.loss,
        "confidence_is_nan": True,
        "training_status": training.status,
    }


def main():
    with tempfile.TemporaryDirectory(prefix="ser-deep-review-") as directory:
        root = Path(directory)
        results = {
            probe.__name__: probe(root)
            for probe in (rewind_history, stale_evaluation, stream_delivery, nonfinite_logits)
        }
        print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
