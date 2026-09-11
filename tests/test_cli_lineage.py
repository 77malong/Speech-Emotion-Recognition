from __future__ import annotations

import json
import math
import struct
import wave
from pathlib import Path

import torch

from ser_lib.artifacts import inspect_model_artifact
from ser_lib.cli.workflows import export_checkpoint_artifact
from ser_lib.engine import evaluate_artifact, load_training_history, train_experiment


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


def _write_minimal_experiment(
    tmp_path: Path,
    *,
    save_last: bool = True,
    save_best: bool = True,
) -> Path:
    for index, frequency in enumerate((220.0, 660.0)):
        _write_wav(tmp_path / f"sample-{index}.wav", frequency)
    (tmp_path / "train.jsonl").write_text(
        '{"uid":"low","audio_path":"sample-0.wav","label":0}\n'
        '{"uid":"high","audio_path":"sample-1.wav","label":1}\n',
        encoding="utf-8",
    )
    (tmp_path / "dataset.yaml").write_text(
        """dataset_id: cli-lineage
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
        f"""data:
  manifest: dataset.yaml
  labels: {{0: {{en: low}}, 1: {{en: high}}}}
  representation:
    type: log_mel
    params: {{sample_rate: 16000, n_fft: 256, hop_length: 80, n_mels: 16}}
model:
  type: cnn_baseline
  params: {{feature_dim: 16, num_classes: 2, hidden_dim: 8, dropout: 0}}
trainer:
  epochs: 1
  save_last: {str(save_last).lower()}
  save_best: {str(save_best).lower()}
optimizer: {{type: adamw, params: {{learning_rate: 0.001}}}}
output_dir: run
""",
        encoding="utf-8",
    )
    return config


def test_engine_experiment_api_persists_training_and_evaluation_lineage(tmp_path: Path):
    config = _write_minimal_experiment(tmp_path)

    execution = train_experiment(
        config,
        split="train",
        batch_size=2,
        workers=0,
        resume=None,
    )
    result = execution.to_dict()
    assert execution.training.status == "completed"
    assert execution.run.run_id == execution.training.run_id

    run_record = execution.run_record
    assert run_record.is_file()
    saved_run = json.loads(run_record.read_text(encoding="utf-8"))
    assert saved_run["run_id"] == result["run_id"]
    assert saved_run["dataset_id"] == "cli-lineage"
    assert saved_run["dataset_fingerprint"] == result["dataset_fingerprint"]
    assert len(saved_run["dataset_fingerprint"]) == 64
    assert saved_run["model_id"] == "cnn_baseline"
    assert saved_run["status"] == "completed"

    history = load_training_history(execution.output_dir)
    assert history.epoch_count == 1
    assert history.epochs[0].epoch == 1
    assert history.epochs[0].sample_count == 2

    checkpoint = execution.last_checkpoint
    assert checkpoint is not None
    assert checkpoint == execution.training.last_checkpoint
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
    evaluation = evaluate_artifact(
        artifact,
        manifest_path=tmp_path / "dataset.yaml",
        split="train",
        batch_size=2,
        workers=0,
        device="cpu",
        output=evaluation_dir,
    )
    evaluated = evaluation.to_dict()
    evaluation_record = evaluation.evaluation_record
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


def test_training_result_does_not_claim_disabled_checkpoints(tmp_path: Path):
    config = _write_minimal_experiment(
        tmp_path,
        save_last=False,
        save_best=False,
    )

    execution = train_experiment(
        config,
        split="train",
        batch_size=2,
        workers=0,
        resume=None,
    )

    assert execution.training.last_checkpoint is None
    assert execution.training.best_checkpoint is None
    assert execution.last_checkpoint is None
    assert execution.best_checkpoint is None
    assert execution.to_dict()["last_checkpoint"] is None
    assert execution.to_dict()["best_checkpoint"] is None
