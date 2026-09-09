import json
from pathlib import Path

import torch

from ser_lib.data import SERBatch, TensorSpec
from ser_lib.data.config import AudioSettings, BatchingConfig, ComponentConfig, DataConfig
from ser_lib.data.validation import ModelSpec
from ser_lib.engine import Trainer, TrainerConfig
from ser_lib.models import CNNBaseline, ModelOutput, SERModel
from ser_lib.services import (
    ArtifactService,
    CatalogService,
    DatasetService,
    EvaluationService,
    RuntimeService,
    TrainingService,
)


class TinyModel(SERModel):
    def __init__(self) -> None:
        super().__init__()
        self.linear = torch.nn.Linear(2, 2)

    @property
    def model_spec(self) -> ModelSpec:
        return ModelSpec(
            model_id="tiny_service_test",
            required_inputs={"scores": TensorSpec(layout="D", feature_dim=2)},
            supports_masks=False,
            supports_variable_length=False,
            num_classes=2,
        )

    @property
    def model_config(self):
        return {}

    def forward(self, batch: SERBatch) -> ModelOutput:
        return ModelOutput(logits=self.linear(batch.inputs["scores"]))


def _batch() -> SERBatch:
    return SERBatch(
        inputs={"scores": torch.tensor([[1.0, 0.0], [0.0, 1.0]])},
        lengths={},
        masks={},
        labels=torch.tensor([0, 1], dtype=torch.long),
        uids=["a", "b"],
        metadata=[{}, {}],
    )


def _dataset(tmp_path: Path) -> Path:
    (tmp_path / "train.jsonl").write_text(
        '{"uid":"a","audio_path":"a.wav","label":0,"speaker_id":"s1"}\n',
        encoding="utf-8",
    )
    (tmp_path / "val.jsonl").write_text(
        '{"uid":"b","audio_path":"b.wav","label":1,"speaker_id":"s2"}\n',
        encoding="utf-8",
    )
    path = tmp_path / "dataset.yaml"
    path.write_text(
        "schema_version: 1\n"
        "dataset_id: service-demo\n"
        "root: .\n"
        "splits:\n"
        "  train: train.jsonl\n"
        "  val: val.jsonl\n"
        "labels:\n"
        "  0: {en: neutral}\n"
        "  1: {en: happy}\n",
        encoding="utf-8",
    )
    return path


def _data_config(tmp_path: Path) -> DataConfig:
    return DataConfig(
        manifest=tmp_path / "unused-dataset.yaml",
        audio=AudioSettings(target_sample_rate=16000),
        representation=ComponentConfig(
            type="log_mel",
            params={
                "sample_rate": 16000,
                "n_mels": 16,
                "n_fft": 128,
                "win_length": 128,
                "hop_length": 64,
                "f_max": 8000,
            },
        ),
        batching=BatchingConfig(type="dynamic"),
        labels={0: {"en": "neutral"}, 1: {"en": "happy"}},
    )


def test_dataset_catalog_and_runtime_services(tmp_path: Path):
    manifest = _dataset(tmp_path)

    summary = DatasetService.summary(manifest)
    page = DatasetService.query(manifest, split="train", limit=10)
    fingerprint = DatasetService.fingerprint(manifest)
    editor = DatasetService.editor(manifest)

    assert summary.dataset_id == "service-demo"
    assert summary.total_records == 2
    assert page.total == 1
    assert page.items[0].uid == "a"
    assert len(fingerprint.digest) == 64
    editor.move_records(["a"], "val")
    assert editor.dirty is True
    editor.rollback()
    assert editor.dirty is False

    catalog = CatalogService.snapshot()
    assert CatalogService.get("model", "cnn_baseline").id == "cnn_baseline"
    assert CatalogService.list("model") == catalog.list("model")

    capabilities = RuntimeService.capabilities()
    json.dumps(capabilities.to_dict())
    assert capabilities.devices[0].id == "cpu"


def test_training_and_evaluation_services_return_standard_results():
    model = TinyModel()
    trainer = Trainer(
        model,
        TrainerConfig(epochs=1, device="cpu"),
        optimizer=torch.optim.AdamW(model.parameters(), lr=0.01),
        run_id="service-run",
    )

    training = TrainingService.run(trainer, [_batch()])
    evaluation = EvaluationService.run(model, [_batch()], num_classes=2)

    assert training.run_id == "service-run"
    assert training.status == "completed"
    assert len(training.epochs) == 1
    assert evaluation.sample_count == 2
    json.dumps(training.to_dict())
    json.dumps(evaluation.to_dict())


def test_artifact_service_delegates_safe_artifact_workflow(tmp_path: Path):
    model = CNNBaseline(feature_dim=16, num_classes=2, hidden_dim=4, dropout=0)
    directory = ArtifactService.export(
        tmp_path / "artifact",
        model,
        model_name="cnn_baseline",
        data_config=_data_config(tmp_path),
        labels={0: "neutral", 1: "happy"},
    )

    inspected = ArtifactService.inspect(directory)
    verified = ArtifactService.verify(directory)

    assert inspected.model_name == "cnn_baseline"
    assert verified.weights_sha256 == inspected.weights_sha256
