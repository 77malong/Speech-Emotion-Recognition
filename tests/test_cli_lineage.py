from __future__ import annotations

import json
import math
import struct
import wave
from pathlib import Path

import torch

from ser_lib.artifacts import inspect_model_artifact
from ser_lib.cli.workflows import (
    evaluate_artifact,
    export_checkpoint_artifact,
    train_experiment,
)


def _write_wav(path: Path, frequency: float) -> None:
    frames = bytearray()
    for index in range(1200):
        frames.extend(
            struct.pack(
                "<h",
                int(5000 * math.sin(2 * math.pi * frequency * index / 16000)),
            )
        )
    with wave.open(str(path), "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(16000)
        output.writeframes(frames)


def test_cli_training_persists_run_lineage_and_exports_it_to_artifact(tmp_path: Path):
    for index, frequency in enumerate((220.0, 660.0)):
        _write_wav(tmp_path / f"sample-{index}.wav", frequency)
    (tmp_path / "train.jsonl").write_text(
        '{"uid":"low","audio_path":"sample-0.wav","label":0}\n'
        '{"uid":"high","audio_path":"sample-1.wav","label":1}\n',
        encoding="utf-8",
    )
    (tmp_path / "dataset.yaml").write_text(
        """schema_version: 1
dataset_id: cli-lineage
root: .
splits: {train: train.jsonl}
labels:
  0: {en: low}
  1: {en: high}
""",
        encoding="utf-8",
    )
    config = tmp_path / "experiment.yaml"
    config.write_text(
        """schema_version: 1
data:
  manifest: dataset.yaml
  labels: {0: {en: low}, 1: {en: high}}
  representation:
    type: log_mel
    params: {sample_rate: 16000, n_fft: 256, hop_length: 80, n_mels: 16}
model:
  type: cnn_baseline
  params: {feature_dim: 16, num_classes: 2, hidden_dim: 8, dropout: 0}
trainer:
  epochs: 1
optimizer: {type: adamw, params: {learning_rate: 0.001}}
output_dir: run
""",
        encoding="utf-8",
    )

    result = train_experiment(
        config,
        split="train",
        batch_size=2,
        workers=0,
        resume=None,
    )

    run_record = Path(result["run_record"])
    assert run_record.is_file()
    saved_run = json.loads(run_record.read_text(encoding="utf-8"))
    assert saved_run["run_id"] == result["run_id"]
    assert saved_run["dataset_id"] == "cli-lineage"
    assert saved_run["dataset_fingerprint"] == result["dataset_fingerprint"]
    assert len(saved_run["dataset_fingerprint"]) == 64
    assert saved_run["model_id"] == "cnn_baseline"
    assert saved_run["status"] == "completed"

    checkpoint = Path(result["last_checkpoint"])
    payload = torch.load(checkpoint, map_location="cpu", weights_only=False)
    checkpoint_lineage = payload["metadata"]["run_metadata"]
    assert checkpoint_lineage["run_id"] == result["run_id"]
    assert checkpoint_lineage["dataset_id"] == "cli-lineage"
    assert checkpoint_lineage["dataset_fingerprint"] == result["dataset_fingerprint"]

    artifact = tmp_path / "artifact"
    exported = export_checkpoint_artifact(config, checkpoint, artifact)
    artifact_manifest = inspect_model_artifact(artifact)
    assert exported["source_run_id"] == result["run_id"]
    assert artifact_manifest.metadata["source_run_id"] == result["run_id"]
    assert artifact_manifest.metadata["dataset_id"] == "cli-lineage"
    assert artifact_manifest.metadata["dataset_fingerprint"] == result["dataset_fingerprint"]

    evaluation_dir = tmp_path / "evaluation"
    evaluated = evaluate_artifact(
        artifact,
        manifest_path=tmp_path / "dataset.yaml",
        split="train",
        batch_size=2,
        workers=0,
        device="cpu",
        output=evaluation_dir,
    )
    evaluation_record = Path(evaluated["evaluation_record"])
    assert evaluation_record.is_file()
    saved_evaluation = json.loads(evaluation_record.read_text(encoding="utf-8"))
    assert evaluated["evaluation_id"].startswith("eval_")
    assert saved_evaluation["evaluation_id"] == evaluated["evaluation_id"]
    assert saved_evaluation["source_run_id"] == result["run_id"]
    assert saved_evaluation["source_artifact"] == artifact.as_posix()
    assert saved_evaluation["dataset_id"] == "cli-lineage"
    assert saved_evaluation["dataset_fingerprint"] == result["dataset_fingerprint"]
    assert saved_evaluation["model_name"] == "cnn_baseline"
    assert saved_evaluation["split"] == "train"
    assert saved_evaluation["sample_count"] == 2
    assert saved_evaluation["metrics"]["accuracy"] == evaluated["accuracy"]
    assert (evaluation_dir / "metrics.json").is_file()
    assert (evaluation_dir / "predictions.jsonl").is_file()
