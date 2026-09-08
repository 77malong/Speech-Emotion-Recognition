from __future__ import annotations

import inspect
from pathlib import Path

import pytest

from ser_lib.core import (
    CancellationToken,
    EventContext,
    LifecycleEvent,
    OperationCancelled,
    ProgressEvent,
)
from ser_lib.data.importers import (
    CasiaImporter,
    CremaDImporter,
    CsemotionsImporter,
    CsvImporter,
    EmotionTalkImporter,
    EsdImporter,
    FolderImporter,
    JsonlImporter,
    RavdessImporter,
)


IMPORTERS = (
    FolderImporter,
    CsvImporter,
    JsonlImporter,
    CasiaImporter,
    RavdessImporter,
    CsemotionsImporter,
    EsdImporter,
    CremaDImporter,
    EmotionTalkImporter,
)


def _folder_dataset(root: Path) -> None:
    for label, count in (("happy", 2), ("sad", 1)):
        directory = root / label
        directory.mkdir(parents=True)
        for index in range(count):
            (directory / f"{index}.wav").write_bytes(b"not-decoded-by-importer")


def test_all_builtin_importers_expose_observability_keyword_contract():
    for importer_cls in IMPORTERS:
        for method_name in ("scan", "convert"):
            parameters = inspect.signature(getattr(importer_cls, method_name)).parameters
            assert "event_callback" in parameters
            assert "cancellation" in parameters
            assert "event_context" in parameters
            assert parameters["event_callback"].kind is inspect.Parameter.KEYWORD_ONLY
            assert parameters["cancellation"].kind is inspect.Parameter.KEYWORD_ONLY
            assert parameters["event_context"].kind is inspect.Parameter.KEYWORD_ONLY


def test_folder_scan_emits_known_total_progress_and_lifecycle(tmp_path: Path):
    source = tmp_path / "source"
    _folder_dataset(source)
    events = []

    preview = FolderImporter().scan(
        source,
        {},
        event_callback=events.append,
        event_context=EventContext(run_id="import-run"),
    )

    assert len(preview.records) == 3
    lifecycle = [event for event in events if isinstance(event, LifecycleEvent)]
    assert [(event.stage, event.status) for event in lifecycle] == [
        ("import_scan", "started"),
        ("import_scan", "completed"),
    ]
    assert all(event.context.run_id == "import-run" for event in lifecycle)
    assert lifecycle[-1].details["records"] == 3
    assert lifecycle[-1].details["candidates"] == 3

    progress = [event for event in events if isinstance(event, ProgressEvent)]
    assert [event.completed for event in progress] == [1, 2, 3]
    assert [event.total for event in progress] == [3, 3, 3]
    assert all(event.stage == "import_scan" for event in progress)
    assert all(event.context.run_id == "import-run" for event in progress)
    assert progress[-1].details["records_discovered"] == 3
    assert progress[-1].details["elapsed_seconds"] >= 0


def test_folder_convert_emits_nested_scan_and_convert_progress(tmp_path: Path):
    source = tmp_path / "source"
    destination = tmp_path / "workspace"
    _folder_dataset(source)
    events = []

    manifest = FolderImporter().convert(
        source,
        destination,
        {},
        event_callback=events.append,
        event_context=EventContext(run_id="convert-run"),
    )

    assert len(manifest.records) == 3
    assert (destination / "manifest.jsonl").is_file()
    assert (destination / "dataset.yaml").is_file()
    lifecycle = [event for event in events if isinstance(event, LifecycleEvent)]
    assert [(event.stage, event.status) for event in lifecycle] == [
        ("import_convert", "started"),
        ("import_scan", "started"),
        ("import_scan", "completed"),
        ("import_convert", "completed"),
    ]
    convert_progress = [
        event for event in events
        if isinstance(event, ProgressEvent) and event.stage == "import_convert"
    ]
    assert [event.completed for event in convert_progress] == [1, 2, 3]
    assert all(event.total == 3 for event in convert_progress)
    assert lifecycle[-1].details["records"] == 3


def test_pre_cancelled_import_emits_started_then_cancelled(tmp_path: Path):
    source = tmp_path / "source"
    source.mkdir()
    token = CancellationToken()
    token.cancel()
    events = []

    with pytest.raises(OperationCancelled):
        FolderImporter().scan(
            source,
            {},
            event_callback=events.append,
            cancellation=token,
            event_context=EventContext(run_id="cancel-import"),
        )

    lifecycle = [event for event in events if isinstance(event, LifecycleEvent)]
    assert [(event.stage, event.status) for event in lifecycle] == [
        ("import_scan", "started"),
        ("import_scan", "cancelled"),
    ]
    assert all(event.context.run_id == "cancel-import" for event in lifecycle)


def test_convert_failure_emits_failed_terminal_event(tmp_path: Path):
    source = tmp_path / "source"
    (source / "unknown").mkdir(parents=True)
    (source / "unknown" / "a.wav").write_bytes(b"audio")
    events = []

    with pytest.raises(ValueError, match="取消导入"):
        FolderImporter().convert(
            source,
            tmp_path / "workspace",
            {"label_mapping": {"happy": 0}},
            event_callback=events.append,
        )

    convert_lifecycle = [
        event for event in events
        if isinstance(event, LifecycleEvent) and event.stage == "import_convert"
    ]
    assert [event.status for event in convert_lifecycle] == ["started", "failed"]
    assert convert_lifecycle[-1].details["error_type"] == "ValueError"
