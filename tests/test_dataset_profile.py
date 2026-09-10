import json
import wave
from pathlib import Path

import pytest

from ser_lib.data import DatasetProfile, profile_dataset, profile_manifest_audio
from ser_lib.foundation.errors import OperationCancelled
from ser_lib.foundation.events import CancellationToken
from ser_lib.services import DatasetService


def _write_wav(path: Path, *, seconds: float, sample_rate: int = 8000) -> None:
    frame_count = int(seconds * sample_rate)
    with wave.open(str(path), "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(b"\x00\x00" * frame_count)


def _write_dataset(root: Path) -> Path:
    (root / "train.jsonl").write_text(
        '{"uid":"a","audio_path":"a.wav","label":0,"speaker_id":"spk-a"}\n'
        '{"uid":"b","audio_path":"b.wav","speaker_id":"spk-b"}\n',
        encoding="utf-8",
    )
    (root / "val.jsonl").write_text(
        '{"uid":"c","audio_path":"c.wav","label":1,"speaker_id":"spk-a"}\n'
        '{"uid":"d","audio_path":"d.wav","label":1}\n',
        encoding="utf-8",
    )
    dataset_yaml = root / "dataset.yaml"
    dataset_yaml.write_text(
        "schema_version: 1\n"
        "dataset_id: profile-demo\n"
        "root: .\n"
        "splits:\n"
        "  train: train.jsonl\n"
        "  val: val.jsonl\n"
        "labels:\n"
        "  0: {en: neutral, zh: 平静}\n"
        "  1: {en: happy, zh: 开心}\n",
        encoding="utf-8",
    )
    return dataset_yaml


def test_detailed_profile_exposes_web_ready_manifest_statistics(tmp_path: Path):
    dataset_yaml = _write_dataset(tmp_path)
    events = []

    profile = profile_dataset(dataset_yaml, event_callback=events.append)

    assert isinstance(profile, DatasetProfile)
    assert profile.dataset_id == "profile-demo"
    assert profile.total_records == 4
    assert profile.num_classes == 2
    assert profile.num_speakers == 2
    assert profile.unlabeled_records == 1
    assert profile.records_without_speaker == 1
    assert profile.splits == {"train": 2, "val": 2}
    assert profile.labels == {"0": 1, "1": 2, "unlabeled": 1}
    assert profile.label_display_names == {
        "0": "平静",
        "1": "开心",
        "unlabeled": "unlabeled",
    }
    assert profile.split_labels == {
        "train": {"0": 1, "1": 0, "unlabeled": 1},
        "val": {"0": 0, "1": 2, "unlabeled": 0},
    }
    assert profile.speaker_counts == {"spk-a": 2, "spk-b": 1}
    assert profile.audio_profile is None
    assert events[-1].stage == "dataset_manifest_profile"
    assert events[-1].completed == 4
    assert events[-1].total == 4
    json.dumps(profile.to_dict(), ensure_ascii=False)


def test_audio_profile_adds_percentiles_and_histogram(tmp_path: Path):
    dataset_yaml = _write_dataset(tmp_path)
    for name, seconds in (("a.wav", 1.0), ("b.wav", 2.0), ("c.wav", 3.0), ("d.wav", 4.0)):
        _write_wav(tmp_path / name, seconds=seconds)

    profile = DatasetService.detailed_profile(
        dataset_yaml,
        include_audio=True,
        histogram_bins=4,
    )

    audio = profile.audio_profile
    assert audio is not None
    assert audio.probed_records == 4
    assert audio.failed_records == 0
    assert audio.total_duration_seconds == pytest.approx(10.0)
    assert audio.median_duration_seconds == pytest.approx(2.5)
    assert audio.p90_duration_seconds == pytest.approx(3.7)
    assert audio.p95_duration_seconds == pytest.approx(3.85)
    assert audio.p99_duration_seconds == pytest.approx(3.97)
    assert [item.count for item in audio.duration_histogram] == [1, 1, 1, 1]
    assert audio.sample_rates == {"8000": 4}
    assert audio.channels == {"1": 4}
    json.dumps(profile.to_dict(), ensure_ascii=False)


def test_audio_profile_preserves_failure_isolation_and_old_service_api(tmp_path: Path):
    dataset_yaml = _write_dataset(tmp_path)
    _write_wav(tmp_path / "a.wav", seconds=1.0)

    audio = DatasetService.profile(dataset_yaml, histogram_bins=5)

    assert audio.total_records == 4
    assert audio.probed_records == 1
    assert audio.failed_records == 3
    assert len(audio.failures) == 3
    assert sum(item.count for item in audio.duration_histogram) == 1


def test_profile_dataset_honors_cancellation_before_scanning(tmp_path: Path):
    dataset_yaml = _write_dataset(tmp_path)
    token = CancellationToken()
    token.cancel()

    with pytest.raises(OperationCancelled):
        profile_dataset(dataset_yaml, cancellation=token)


def test_histogram_bins_must_be_positive(tmp_path: Path):
    dataset_yaml = _write_dataset(tmp_path)

    with pytest.raises(ValueError, match="histogram_bins"):
        profile_manifest_audio(dataset_yaml, histogram_bins=0)
