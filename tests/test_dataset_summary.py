import json
import wave
from pathlib import Path

import pytest

from ser_lib.data import DatasetSummary, summarize_manifest


def _write_dataset(
    root: Path,
    *,
    train_lines: list[str],
    val_lines: list[str] | None = None,
) -> Path:
    (root / "train.jsonl").write_text("".join(train_lines), encoding="utf-8")
    (root / "val.jsonl").write_text("".join(val_lines or []), encoding="utf-8")
    dataset_yaml = root / "dataset.yaml"
    dataset_yaml.write_text(
        ""
        "dataset_id: demo\n"
        "root: .\n"
        "splits:\n"
        "  train: train.jsonl\n"
        "  val: val.jsonl\n"
        "labels:\n"
        "  0: {en: neutral}\n"
        "  1: {en: happy}\n",
        encoding="utf-8",
    )
    return dataset_yaml


def _write_wav(path: Path, *, sample_rate: int = 8000, seconds: float = 1.0) -> None:
    frame_count = int(sample_rate * seconds)
    with wave.open(str(path), "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(b"\x00\x00" * frame_count)


def test_dataset_summary_is_lightweight_and_json_safe(tmp_path: Path):
    dataset_yaml = _write_dataset(
        tmp_path,
        train_lines=[
            '{"uid":"a","audio_path":"missing-a.wav","label":0,'
            '"speaker_id":"speaker-a"}\n',
            '{"uid":"b","audio_path":"missing-b.wav",'
            '"speaker_id":"speaker-b"}\n',
        ],
    )

    summary = summarize_manifest(dataset_yaml)

    assert isinstance(summary, DatasetSummary)
    assert summary.dataset_id == "demo"
    assert summary.name == "demo"
    assert summary.total_records == 2
    assert summary.num_classes == 2
    assert summary.num_speakers == 2
    assert summary.splits == {"train": 2, "val": 0}
    assert summary.labels == {"0": 1, "1": 0, "unlabeled": 1}
    assert summary.total_duration_seconds is None
    assert summary.audio_profiled is False
    assert summary.profiled_records == 0
    assert summary.failed_audio_records == 0
    assert summary.sample_rates == {}
    assert summary.channels == {}
    json.dumps(summary.to_dict())


def test_dataset_summary_can_include_audio_profile(tmp_path: Path):
    _write_wav(tmp_path / "valid.wav", sample_rate=8000, seconds=1.0)
    dataset_yaml = _write_dataset(
        tmp_path,
        train_lines=[
            '{"uid":"valid","audio_path":"valid.wav","label":0,'
            '"speaker_id":"speaker-a"}\n',
            '{"uid":"missing","audio_path":"missing.wav","label":1,'
            '"speaker_id":"speaker-b"}\n',
        ],
    )
    events = []

    summary = summarize_manifest(
        dataset_yaml,
        include_audio_profile=True,
        event_callback=events.append,
    )

    assert summary.audio_profiled is True
    assert summary.profiled_records == 1
    assert summary.failed_audio_records == 1
    assert summary.total_duration_seconds == pytest.approx(1.0)
    assert summary.sample_rates == {"8000": 1}
    assert summary.channels == {"1": 1}
    assert len(events) == 2
    assert events[-1].stage == "dataset_audio_profile"
    assert events[-1].completed == 2
    assert events[-1].total == 2


def test_dataset_summary_infers_classes_without_label_table(tmp_path: Path):
    (tmp_path / "train.jsonl").write_text(
        '{"uid":"a","audio_path":"a.wav","label":2}\n'
        '{"uid":"b","audio_path":"b.wav","label":5}\n',
        encoding="utf-8",
    )
    dataset_yaml = tmp_path / "dataset.yaml"
    dataset_yaml.write_text(
        ""
        "dataset_id: inferred\n"
        "root: .\n"
        "splits: {train: train.jsonl}\n",
        encoding="utf-8",
    )

    summary = summarize_manifest(dataset_yaml)

    assert summary.num_classes == 2
    assert summary.labels == {"2": 1, "5": 1}
