import copy
import json

import pytest
import torch
import yaml

from scripts.audit_latest_only_review import batch, config
from scripts.audit_deep_workflows import NonfiniteModel, FailingPredictor
from scripts.audit_data_boundaries import InvalidRepresentation, MemoryLoader
from ser_lib.cli.workflows import export_checkpoint_artifact
from ser_lib.config import TrainerConfig
from ser_lib.models.base import ModelOutput
from ser_lib.data.dataset import SERDataset
from ser_lib.data.manifest import DatasetManifest, ManifestMeta
from ser_lib.data.pipeline import SamplePipeline
from ser_lib.data.types import AudioRecord
from ser_lib.engine import Trainer, evaluate, evaluate_artifact, train_experiment
from ser_lib.engine.evaluation_reports import inspect_evaluation_report
from ser_lib.engine.evaluator import JsonlPredictionSink
from ser_lib.foundation.errors import ManifestError, RepresentationError
from ser_lib.inference import StreamingConfig, StreamingEmotionRecognizer


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -float("inf")])
def test_nonfinite_output_cannot_report_success(tmp_path, value):
    model = NonfiniteModel(feature_dim=16, num_classes=2)
    model.forward = lambda batch: ModelOutput(
        torch.full((len(batch.labels), 2), value), loss=model.classifier.weight.sum() * 0
    )
    before = copy.deepcopy(model.state_dict())
    with pytest.raises(FloatingPointError, match="logits"):
        evaluate(model, [batch([0])], num_classes=2)
    trainer = Trainer(model, TrainerConfig(epochs=1, checkpoint_dir=tmp_path))
    with pytest.raises(FloatingPointError, match="logits"):
        trainer.fit([batch([0])])
    assert trainer.optimizer_step == 0
    assert all(torch.equal(before[k], v) for k, v in model.state_dict().items())
    assert not list(tmp_path.glob("*.pt"))


@pytest.fixture
def artifact(tmp_path):
    cfg = config(tmp_path / "dataset")
    trained = train_experiment(cfg)
    path = tmp_path / "export.yaml"
    path.write_text(yaml.safe_dump(cfg.model_dump(mode="json")))
    target = tmp_path / "artifact"
    export_checkpoint_artifact(path, trained.last_checkpoint, target)
    return target


@pytest.mark.parametrize("existing", [False, True])
def test_evaluation_without_details_has_consistent_record(artifact, tmp_path, existing):
    output = tmp_path / "report"
    if existing:
        evaluate_artifact(artifact, split="train", output=output)
    result = evaluate_artifact(artifact, split="train", output=output, retain_predictions=False)
    report = inspect_evaluation_report(output)
    assert report.metric_unit == "sample"
    assert result.run.predictions_file is None
    assert result.predictions_path is None
    assert report.predictions_file is None


@pytest.mark.parametrize("retain", [False, True])
def test_local_prediction_sink_is_preserved(artifact, tmp_path, retain):
    output = tmp_path / "report"
    with JsonlPredictionSink(output / "predictions.jsonl") as sink:
        result = evaluate_artifact(
            artifact, split="train", output=output, retain_predictions=retain, prediction_sink=sink
        )
        assert result.run.predictions_file == "predictions.jsonl"
        assert len(sink.path.read_text().splitlines()) == result.evaluation.sample_count


def test_rewind_requires_new_output_directory(tmp_path):
    cfg = config(tmp_path / "dataset")
    train_experiment(cfg)
    before = {p.name: p.read_bytes() for p in cfg.output_dir.iterdir() if p.is_file()}
    checkpoint = cfg.trainer.checkpoint_dir / "epoch-0001.pt"
    with pytest.raises(ValueError, match="回溯"):
        train_experiment(cfg, resume=checkpoint)
    assert before == {p.name: p.read_bytes() for p in cfg.output_dir.iterdir() if p.is_file()}
    moved = cfg.model_copy(
        update={
            "output_dir": tmp_path / "new_run",
            "trainer": cfg.trainer.model_copy(
                update={"checkpoint_dir": tmp_path / "new_checkpoints"}
            ),
        }
    )
    result = train_experiment(moved, resume=checkpoint)
    assert result.run.last_epoch == 2
    assert [x["epoch"] for x in json.loads(result.history_path.read_text())] == [2]


@pytest.mark.parametrize("flush", [False, True])
def test_stream_retry_delivers_completed_prefix(flush):
    predictor = FailingPredictor()
    session = StreamingEmotionRecognizer(
        predictor,
        StreamingConfig(input_sample_rate=8, window_ms=500, hop_ms=500, max_chunk_ms=2000),
    )
    with pytest.raises(RuntimeError, match="transient"):
        session.push_pcm(torch.ones(12))
    results = session.flush() if flush else session.push_pcm(torch.empty(0))
    assert [r.sequence for r in results] == [0, 1, 2]
    assert [r.start_ms for r in results] == [0, 500, 1000]
    assert session.flush() == []


def test_failed_flush_can_be_retried():
    session = StreamingEmotionRecognizer(
        FailingPredictor(),
        StreamingConfig(input_sample_rate=8, window_ms=500, hop_ms=500, max_chunk_ms=2000),
    )
    assert [r.sequence for r in session.push_pcm(torch.ones(7))] == [0]
    with pytest.raises(RuntimeError, match="transient"):
        session.flush(pad_final=True)
    assert [r.sequence for r in session.flush(pad_final=True)] == [1]
    assert session.flush(pad_final=True) == []


def test_unassigned_collision_does_not_overwrite(tmp_path):
    split = tmp_path / "unassigned.jsonl"
    split.write_text("original")
    manifest = DatasetManifest(
        ManifestMeta("test", tmp_path, tmp_path / "dataset.yaml", {"unassigned": split}),
        [AudioRecord("a", tmp_path / "a.wav"), AudioRecord("b", tmp_path / "b.wav")],
        {"a": "unassigned"},
    )
    with pytest.raises(ManifestError, match="冲突"):
        manifest.write()
    assert split.read_text() == "original"


def test_empty_split_roundtrip(tmp_path):
    manifest = DatasetManifest(
        ManifestMeta(
            "test",
            tmp_path,
            tmp_path / "dataset.yaml",
            {"train": tmp_path / "train.jsonl", "val": tmp_path / "val.jsonl"},
        ),
        [AudioRecord("a", tmp_path / "a.wav")],
        {"a": "train"},
    )
    manifest.write()
    restored = DatasetManifest.load(tmp_path / "dataset.yaml")
    assert set(restored.meta.splits) == {"train", "val"}
    assert restored.get_records("val") == []


@pytest.mark.parametrize("strict_first", [False, True])
def test_dataset_validation_does_not_mutate_shared_pipeline(tmp_path, strict_first):
    pipeline = SamplePipeline(InvalidRepresentation())
    record = AudioRecord("sample", tmp_path / "a.wav")
    datasets = {
        strict: SERDataset([record], MemoryLoader(), pipeline, strict=strict)
        for strict in [strict_first, not strict_first]
    }
    for _ in range(2):
        assert datasets[False][0].inputs["waveform"].dtype == torch.float64
        with pytest.raises(RepresentationError):
            datasets[True][0]
    assert pipeline.validate_contract is True


def test_window_report_roundtrip(tmp_path):
    cfg = config(tmp_path / "dataset")
    raw = cfg.model_dump(mode="json")
    raw["data"]["batching"] = {"type": "sliding", "sliding": {"window_size": 8, "stride": 4}}
    cfg = type(cfg).model_validate(raw)
    trained = train_experiment(cfg)
    path = tmp_path / "export.yaml"
    path.write_text(yaml.safe_dump(raw))
    artifact = tmp_path / "artifact"
    export_checkpoint_artifact(path, trained.last_checkpoint, artifact)
    result = evaluate_artifact(artifact, split="train", output=tmp_path / "report")
    inspected = inspect_evaluation_report(result.output_dir)
    assert inspected.metric_unit == result.metric_unit == "window"
    assert inspected.sample_count > 2
