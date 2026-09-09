from __future__ import annotations

import importlib
from pathlib import Path

import pytest

from ser_lib.core import CancellationToken, OperationCancelled, ProgressEvent
from ser_lib.engine import inspect_checkpoint_file, scan_checkpoints
from ser_lib.services import TrainingService

checkpoint_catalog = importlib.import_module("ser_lib.engine.checkpoint_catalog")


def test_inspect_checkpoint_file_classifies_names_without_loading_payload(tmp_path: Path):
    fixtures = {
        "best.pt": ("best", None),
        "last.pt": ("last", None),
        "epoch-0012.pt": ("epoch", 12),
        "manual.pt": ("other", None),
    }
    for index, (name, (kind, epoch)) in enumerate(fixtures.items(), start=1):
        path = tmp_path / name
        path.write_bytes(b"not-a-torch-checkpoint" * index)
        info = inspect_checkpoint_file(path)
        assert info.path == path.as_posix()
        assert info.name == name
        assert info.kind == kind
        assert info.epoch == epoch
        assert info.size_bytes == path.stat().st_size
        assert info.modified_at.tzinfo is not None
        assert info.to_dict()["kind"] == kind


def test_scan_checkpoints_is_lightweight_recursive_and_observable(tmp_path: Path):
    root = tmp_path / "checkpoints"
    root.mkdir()
    (root / "epoch-0001.pt").write_bytes(b"invalid-pickle")
    (root / "best.pt").write_bytes(b"also-invalid")
    (root / "notes.txt").write_text("ignored", encoding="utf-8")
    nested = root / "archive"
    nested.mkdir()
    (nested / "epoch-0002.pt").write_bytes(b"still-invalid")

    events = []
    shallow = scan_checkpoints(root, event_callback=events.append)
    assert {item.name for item in shallow.checkpoints} == {"epoch-0001.pt", "best.pt"}
    assert shallow.failures == ()
    progress = [event for event in events if isinstance(event, ProgressEvent)]
    assert len(progress) == 2
    assert progress[-1].stage == "checkpoint_catalog_scan"
    assert progress[-1].completed == 2
    assert progress[-1].total == 2

    recursive = TrainingService.scan_checkpoints(root, recursive=True)
    assert {item.name for item in recursive.checkpoints} == {
        "epoch-0001.pt",
        "epoch-0002.pt",
        "best.pt",
    }


def test_scan_checkpoints_isolates_stat_failures(monkeypatch, tmp_path: Path):
    root = tmp_path / "checkpoints"
    root.mkdir()
    good = root / "epoch-0001.pt"
    bad = root / "broken.pt"
    good.write_bytes(b"good")
    bad.write_bytes(b"bad")
    original = checkpoint_catalog.inspect_checkpoint_file

    def flaky(path):
        if Path(path).name == "broken.pt":
            raise OSError("stat failed")
        return original(path)

    monkeypatch.setattr(checkpoint_catalog, "inspect_checkpoint_file", flaky)
    catalog = checkpoint_catalog.scan_checkpoints(root)
    assert [item.name for item in catalog.checkpoints] == ["epoch-0001.pt"]
    assert len(catalog.failures) == 1
    assert catalog.failures[0].path == bad.as_posix()
    assert catalog.failures[0].error_type == "OSError"
    assert catalog.total == 2

    with pytest.raises(OSError, match="stat failed"):
        checkpoint_catalog.scan_checkpoints(root, fail_fast=True)


def test_checkpoint_catalog_validation_and_cancellation(tmp_path: Path):
    text = tmp_path / "checkpoint.txt"
    text.write_text("not checkpoint", encoding="utf-8")
    with pytest.raises(ValueError, match=".pt"):
        inspect_checkpoint_file(text)
    with pytest.raises(NotADirectoryError, match="checkpoint 根目录"):
        scan_checkpoints(tmp_path / "missing")

    root = tmp_path / "checkpoints"
    root.mkdir()
    (root / "last.pt").write_bytes(b"payload")
    token = CancellationToken()
    token.cancel()
    with pytest.raises(OperationCancelled):
        scan_checkpoints(root, cancellation=token)
