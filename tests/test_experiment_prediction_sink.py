from __future__ import annotations

import json
from types import SimpleNamespace

import torch

import ser_lib.artifacts.loader as artifact_loader
import ser_lib.engine.experiment as experiment
from ser_lib.engine.evaluator import EvaluationResult, PredictionRecord


class CollectSink:
    def __init__(self) -> None:
        self.records: list[PredictionRecord] = []

    def write(self, record: PredictionRecord) -> None:
        self.records.append(record)


def _empty_result() -> EvaluationResult:
    return EvaluationResult(
        accuracy=1.0,
        macro_f1=1.0,
        uar=1.0,
        confusion_matrix=torch.tensor([[1, 0], [0, 1]], dtype=torch.long),
        sample_count=2,
        loss=0.1,
        war=1.0,
        per_class=(),
        predictions=(),
        weighted_precision=1.0,
        weighted_recall=1.0,
        weighted_f1=1.0,
        balanced_accuracy=1.0,
        matthews_correlation_coefficient=1.0,
        cohen_kappa=1.0,
    )


def test_evaluate_artifact_forwards_streaming_sink_without_retaining_predictions(
    monkeypatch,
    tmp_path,
):
    dataset_manifest = SimpleNamespace(
        meta=SimpleNamespace(
            dataset_id="streaming-eval",
            labels={0: {"en": "neutral"}, 1: {"en": "happy"}},
        )
    )
    loaded = SimpleNamespace(
        model=object(),
        manifest=SimpleNamespace(
            labels={0: "neutral", 1: "happy"},
            preprocessing={
                "manifest": "unused.yaml",
                "batching": {
                    "type": "sliding",
                    "sliding": {"window_size": 100, "stride": 50},
                },
            },
            metadata={},
            model_name="tiny",
        ),
    )
    monkeypatch.setattr(
        artifact_loader,
        "load_model_artifact",
        lambda *args, **kwargs: loaded,
    )
    monkeypatch.setattr(experiment.DatasetManifest, "load", lambda *args: dataset_manifest)
    monkeypatch.setattr(
        experiment,
        "fingerprint_manifest",
        lambda manifest: SimpleNamespace(digest="dataset-fingerprint"),
    )
    monkeypatch.setattr(
        experiment,
        "build_evaluation_metadata",
        lambda **kwargs: SimpleNamespace(evaluation_id="eval-1"),
    )
    monkeypatch.setattr(experiment, "_loader", lambda *args, **kwargs: ["batch"])

    captured = {}

    def fake_evaluate(model, batches, **kwargs):
        captured.update(kwargs)
        kwargs["prediction_sink"].write(
            PredictionRecord(
                uid="sample-1",
                target=0,
                predicted=0,
                confidence=0.9,
                probabilities=(0.9, 0.1),
            )
        )
        return _empty_result()

    monkeypatch.setattr(experiment, "evaluate", fake_evaluate)
    monkeypatch.setattr(
        experiment,
        "write_evaluation_record",
        lambda output_dir, *args, **kwargs: output_dir / "evaluation-run.json",
    )
    monkeypatch.setattr(
        experiment,
        "load_evaluation_record",
        lambda path: SimpleNamespace(
            evaluation_id="eval-1",
            source_artifact=(tmp_path / "artifact").as_posix(),
            source_run_id=None,
            dataset_id="streaming-eval",
            dataset_fingerprint="dataset-fingerprint",
            model_name="tiny",
            split="default",
            device="cpu",
            sample_count=2,
            metrics={
                "loss": 0.1,
                "accuracy": 1.0,
                "war": 1.0,
                "uar": 1.0,
                "macro_f1": 1.0,
                "weighted_precision": 1.0,
                "weighted_recall": 1.0,
                "weighted_f1": 1.0,
                "balanced_accuracy": 1.0,
                "matthews_correlation_coefficient": 1.0,
                "cohen_kappa": 1.0,
            },
            to_dict=lambda: {
                "evaluation_id": "eval-1",
                "source_artifact": (tmp_path / "artifact").as_posix(),
                "source_run_id": None,
                "dataset_id": "streaming-eval",
                "dataset_fingerprint": "dataset-fingerprint",
                "model_name": "tiny",
                "split": "default",
                "device": "cpu",
                "sample_count": 2,
            },
        ),
    )

    sink = CollectSink()
    output_dir = tmp_path / "evaluation"
    result = experiment.evaluate_artifact(
        tmp_path / "artifact",
        output=output_dir,
        prediction_sink=sink,
        retain_predictions=False,
    )

    assert captured["prediction_sink"] is sink
    assert captured["retain_predictions"] is False
    assert result.evaluation.predictions == ()
    assert result.metric_unit == "window"
    assert result.to_dict()["metric_unit"] == "window"
    assert [record.uid for record in sink.records] == ["sample-1"]
    assert not (output_dir / "predictions.jsonl").exists()
    metrics = json.loads((output_dir / "metrics.json").read_text(encoding="utf-8"))
    assert metrics["sample_count"] == 2
    assert metrics["metric_unit"] == "window"


def test_evaluation_metric_unit_does_not_guess_legacy_artifacts():
    assert experiment._evaluation_metric_unit({}) == "batch_row"
    assert experiment._evaluation_metric_unit({"batching": {"type": "dynamic"}}) == "sample"
    assert experiment._evaluation_metric_unit({"batching": {"type": "fixed"}}) == "sample"
