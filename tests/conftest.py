"""Current-contract fixtures, independent of historical release snapshots."""

from pathlib import Path

import pytest


@pytest.fixture
def current_experiment_config(tmp_path: Path):
    import numpy as np
    import soundfile as sf
    import yaml

    from ser_lib.config import ExperimentConfig
    from ser_lib.data.manifest import write_jsonl
    from ser_lib.data.types import AudioRecord

    labels = {0: {"en": "neutral"}, 1: {"en": "happy"}}
    records = []
    time = np.arange(1600) / 16000
    for label in labels:
        path = tmp_path / f"sample-{label}.wav"
        sf.write(path, 0.2 * np.sin(2 * np.pi * (220 + label * 110) * time), 16000)
        records.append(AudioRecord(f"sample-{label}", path, label=label))
    write_jsonl(records, tmp_path / "train.jsonl")
    manifest = tmp_path / "dataset.yaml"
    manifest.write_text(
        yaml.safe_dump(
            {
                "dataset_id": "current-contract",
                "root": str(tmp_path),
                "splits": {"train": "train.jsonl"},
                "labels": labels,
            }
        ),
        encoding="utf-8",
    )
    return ExperimentConfig.model_validate(
        {
            "data": {
                "manifest": manifest,
                "labels": labels,
                "audio": {"backend": "soundfile"},
                "cache": {"enabled": False, "directory": tmp_path / "cache"},
                "representation": {
                    "type": "log_mel",
                    "params": {"n_fft": 256, "win_length": 256, "hop_length": 80, "n_mels": 16},
                },
            },
            "model": {
                "type": "cnn_baseline",
                "params": {"feature_dim": 16, "num_classes": 2, "hidden_dim": 6, "dropout": 0.0},
            },
            "trainer": {"epochs": 1, "device": "cpu", "checkpoint_dir": tmp_path / "checkpoints"},
            "output_dir": tmp_path / "run",
        }
    )
