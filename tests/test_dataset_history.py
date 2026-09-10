from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from ser_lib.data import (
    DatasetEditConflictError,
    DatasetEditor,
    DatasetManifest,
    create_dataset_revision,
    fingerprint_manifest,
    inspect_dataset_revision,
    restore_dataset_revision,
    scan_dataset_revisions,
)
from ser_lib.foundation.errors import OperationCancelled
from ser_lib.foundation.events import CancellationToken, ProgressEvent
from ser_lib.services import DatasetService


def _write_dataset(root: Path) -> Path:
    (root / "audio").mkdir()
    (root / "audio" / "a.wav").write_bytes(b"audio-a")
    (root / "audio" / "b.wav").write_bytes(b"audio-b")
    (root / "train.jsonl").write_text(
        '{"uid":"a","audio_path":"audio/a.wav","label":0}\n',
        encoding="utf-8",
    )
    (root / "val.jsonl").write_text(
        '{"uid":"b","audio_path":"audio/b.wav","label":1}\n',
        encoding="utf-8",
    )
    manifest = root / "dataset.yaml"
    manifest.write_text(
        """schema_version: 1
dataset_id: history-demo
root: .
splits:
  train: train.jsonl
  val: val.jsonl
labels:
  0: {en: low}
  1: {en: high}
""",
        encoding="utf-8",
    )
    return manifest


def test_create_revision_snapshots_only_manifest_files(tmp_path: Path):
    manifest = _write_dataset(tmp_path)
    expected = fingerprint_manifest(manifest)
    events = []

    revision = create_dataset_revision(
        manifest,
        revision_id="baseline",
        note="before edit",
        event_callback=events.append,
    )

    directory = Path(revision.directory)
    assert revision.fingerprint == expected.digest
    assert revision.dataset_id == "history-demo"
    assert revision.note == "before edit"
    assert revision.file_count == 3
    assert (directory / "revision.json").is_file()
    assert (directory / "dataset.yaml").is_file()
    assert len(list(directory.glob("split-*.jsonl"))) == 2
    assert not list(directory.rglob("*.wav"))
    assert inspect_dataset_revision(directory, verify=True) == revision
    assert json.dumps(revision.to_dict())

    progress = [event for event in events if isinstance(event, ProgressEvent)]
    assert progress[0].completed == 0
    assert progress[-1].completed == progress[-1].total
    assert all(
        left.completed <= right.completed
        for left, right in zip(progress, progress[1:])
    )


def test_revision_history_orders_newest_and_isolates_bad_records(tmp_path: Path):
    manifest = _write_dataset(tmp_path)
    first = create_dataset_revision(
        manifest,
        revision_id="first",
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    second = DatasetService.snapshot_revision(
        manifest,
        revision_id="second",
        created_at=datetime(2026, 1, 2, tzinfo=timezone.utc),
    )
    broken = tmp_path / ".ser_history" / "broken"
    broken.mkdir()
    (broken / "revision.json").write_text("{bad", encoding="utf-8")

    catalog = DatasetService.revision_history(manifest)
    assert [item.revision_id for item in catalog.revisions] == ["second", "first"]
    assert {Path(item.directory).name for item in catalog.revisions} == {
        Path(first.directory).name,
        Path(second.directory).name,
    }
    assert len(catalog.failures) == 1
    assert catalog.total == 3
    assert json.dumps(catalog.to_dict())

    with pytest.raises(Exception):
        scan_dataset_revisions(manifest, fail_fast=True)


def test_restore_revision_restores_records_without_touching_audio(tmp_path: Path):
    manifest_path = _write_dataset(tmp_path)
    revision = create_dataset_revision(manifest_path, revision_id="original")
    original_audio = (tmp_path / "audio" / "a.wav").read_bytes()

    editor = DatasetEditor(manifest_path)
    editor.update_record("a", label=1)
    editor.commit()
    changed = DatasetManifest.load(manifest_path)
    assert changed.records[0].label == 1
    current_fingerprint = fingerprint_manifest(changed).digest
    assert current_fingerprint != revision.fingerprint

    restored = restore_dataset_revision(
        changed,
        revision.directory,
        expected_current_fingerprint=current_fingerprint,
    )
    assert restored.records[0].label == 0
    assert fingerprint_manifest(restored).digest == revision.fingerprint
    assert (tmp_path / "audio" / "a.wav").read_bytes() == original_audio


def test_restore_rejects_stale_current_fingerprint(tmp_path: Path):
    manifest_path = _write_dataset(tmp_path)
    revision = create_dataset_revision(manifest_path, revision_id="baseline")
    before = (tmp_path / "train.jsonl").read_text(encoding="utf-8")

    with pytest.raises(DatasetEditConflictError, match="expected_current_fingerprint"):
        DatasetService.restore_revision(
            manifest_path,
            revision.directory,
            expected_current_fingerprint="0" * 64,
        )
    assert (tmp_path / "train.jsonl").read_text(encoding="utf-8") == before


def test_restore_verifies_revision_before_modifying_current_dataset(tmp_path: Path):
    manifest_path = _write_dataset(tmp_path)
    revision = create_dataset_revision(manifest_path, revision_id="baseline")
    current_fingerprint = fingerprint_manifest(manifest_path).digest
    current_train = (tmp_path / "train.jsonl").read_bytes()

    snapshot_split = next(Path(revision.directory).glob("split-*.jsonl"))
    snapshot_split.write_bytes(snapshot_split.read_bytes() + b"corrupt")

    with pytest.raises(ValueError, match="大小不一致|SHA256 不一致"):
        restore_dataset_revision(
            manifest_path,
            revision.directory,
            expected_current_fingerprint=current_fingerprint,
        )
    assert (tmp_path / "train.jsonl").read_bytes() == current_train


def test_revision_validation_and_cancellation(tmp_path: Path):
    manifest_path = _write_dataset(tmp_path)
    with pytest.raises(ValueError, match="时区"):
        create_dataset_revision(
            manifest_path,
            created_at=datetime(2026, 1, 1),
        )

    token = CancellationToken()
    token.cancel()
    with pytest.raises(OperationCancelled):
        create_dataset_revision(manifest_path, cancellation=token)
