from __future__ import annotations

from pathlib import Path

import pytest

from ser_lib.data import DatasetEditError, DatasetEditor


def _dataset(tmp_path: Path) -> Path:
    (tmp_path / "train.jsonl").write_text(
        '{"uid":"a","audio_path":"a.wav","label":0,"speaker_id":"alice"}\n',
        encoding="utf-8",
    )
    dataset_yaml = tmp_path / "dataset.yaml"
    dataset_yaml.write_text(
        ""
        "dataset_id: atomic-edit\n"
        "root: .\n"
        "splits:\n"
        "  train: train.jsonl\n"
        "labels:\n"
        "  0: {en: neutral}\n",
        encoding="utf-8",
    )
    return dataset_yaml


def test_failed_update_does_not_mutate_record_or_split_state(tmp_path: Path):
    editor = DatasetEditor(_dataset(tmp_path))
    before = editor.snapshot()
    before_record = before.records[0]
    before_split = before.record_splits[before_record.uid]

    with pytest.raises(DatasetEditError, match="split"):
        editor.update_record(
            before_record.uid,
            speaker_id="should-not-stick",
            split="",
        )

    after = editor.snapshot()
    assert after.records[0] == before_record
    assert after.record_splits[before_record.uid] == before_split
    assert editor.dirty is False


def test_update_applies_record_and_split_together_after_validation(tmp_path: Path):
    editor = DatasetEditor(_dataset(tmp_path))

    updated = editor.update_record("a", speaker_id="bob", split="review")

    snapshot = editor.snapshot()
    assert updated.speaker_id == "bob"
    assert snapshot.records[0].speaker_id == "bob"
    assert snapshot.record_splits["a"] == "review"
    assert editor.dirty is True
