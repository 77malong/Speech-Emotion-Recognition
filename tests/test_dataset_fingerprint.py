import json
from pathlib import Path

from ser_lib.data import DatasetFingerprint, fingerprint_manifest


def _dataset(tmp_path: Path) -> Path:
    (tmp_path / "train.jsonl").write_text(
        '{"uid":"a","audio_path":"a.wav","label":0}\n',
        encoding="utf-8",
    )
    (tmp_path / "val.jsonl").write_text(
        '{"uid":"b","audio_path":"b.wav","label":1}\n',
        encoding="utf-8",
    )
    dataset_yaml = tmp_path / "dataset.yaml"
    dataset_yaml.write_text(
        ""
        "dataset_id: fingerprint-demo\n"
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


def test_dataset_fingerprint_is_stable_and_json_safe(tmp_path: Path):
    dataset_yaml = _dataset(tmp_path)
    events = []

    first = fingerprint_manifest(dataset_yaml, event_callback=events.append)
    second = fingerprint_manifest(dataset_yaml)

    assert isinstance(first, DatasetFingerprint)
    assert first.algorithm == "sha256"
    assert len(first.digest) == 64
    assert first.digest == second.digest
    assert set(first.files) == {"dataset.yaml", "split:train", "split:val"}
    assert len(events) == 3
    assert events[-1].stage == "dataset_fingerprint"
    assert events[-1].completed == 3
    assert events[-1].total == 3
    json.dumps(first.to_dict())


def test_dataset_fingerprint_changes_when_manifest_content_changes(tmp_path: Path):
    dataset_yaml = _dataset(tmp_path)
    before = fingerprint_manifest(dataset_yaml)

    (tmp_path / "train.jsonl").write_text(
        '{"uid":"a","audio_path":"a.wav","label":1}\n',
        encoding="utf-8",
    )
    after = fingerprint_manifest(dataset_yaml)

    assert before.digest != after.digest
    assert before.files["split:train"] != after.files["split:train"]
    assert before.files["split:val"] == after.files["split:val"]


def test_dataset_fingerprint_does_not_hash_audio_payload(tmp_path: Path):
    dataset_yaml = _dataset(tmp_path)
    (tmp_path / "a.wav").write_bytes(b"first audio payload")
    first = fingerprint_manifest(dataset_yaml)

    (tmp_path / "a.wav").write_bytes(b"changed audio payload")
    second = fingerprint_manifest(dataset_yaml)

    assert first.digest == second.digest
