"""Importer convert 阶段共享编排；只处理通用写盘，不包含数据集解析规则。"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any

import yaml

from ser_lib.core.events import CancellationCheck, EventCallback, EventContext
from ser_lib.data.importers.base import ImportPreview, ImportTask
from ser_lib.data.manifest import DatasetManifest, write_jsonl
from ser_lib.data.types import AudioRecord

ScanCallable = Callable[..., ImportPreview]
RecordResolver = Callable[[ImportPreview], Sequence[AudioRecord]]
LabelResolver = Callable[[ImportPreview], Mapping[Any, Any]]
FailureFormatter = Callable[[ImportPreview], str]


def run_single_manifest_conversion(
    *,
    importer_id: str,
    scan: ScanCallable,
    source: Path,
    destination: Path,
    config: Mapping[str, Any],
    dataset_id: str,
    root: Path | str,
    labels: LabelResolver | None = None,
    records: RecordResolver | None = None,
    failure_message: FailureFormatter | None = None,
    event_callback: EventCallback | None = None,
    cancellation: CancellationCheck | None = None,
    event_context: EventContext | None = None,
) -> DatasetManifest:
    """执行单 JSONL manifest importer 的唯一标准 convert 流程。"""
    source = Path(source)
    destination = Path(destination)
    with ImportTask(
        importer_id,
        "convert",
        source=source,
        destination=destination,
        event_callback=event_callback,
        cancellation=cancellation,
        event_context=event_context,
    ) as task:
        preview = scan(
            source,
            config,
            event_callback=event_callback,
            cancellation=cancellation,
            event_context=event_context,
        )
        task.progress(
            1,
            3,
            message="scan completed",
            details={
                "records": len(preview.records),
                "errors": preview.error_count,
                "diagnostics": len(preview.diagnostics),
            },
        )
        if not preview.ok or not preview.records:
            if failure_message is not None:
                raise ValueError(failure_message(preview))
            detail = preview.format_errors() or "没有记录"
            raise ValueError(f"{importer_id} 扫描失败: {detail}")

        resolved_records = list(records(preview) if records is not None else preview.records)
        destination.mkdir(parents=True, exist_ok=True)
        task.check()
        write_jsonl(resolved_records, destination / "manifest.jsonl")
        task.progress(2, 3, message="manifest written")

        document: dict[str, Any] = {
            "schema_version": 1,
            "dataset_id": dataset_id,
            "root": str(root),
            "splits": {"default": "manifest.jsonl"},
        }
        if labels is not None:
            resolved_labels = dict(labels(preview))
            if resolved_labels:
                document["labels"] = resolved_labels
        (destination / "dataset.yaml").write_text(
            yaml.safe_dump(document, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )
        task.progress(3, 3, message="dataset manifest written")
        result = DatasetManifest.load(destination / "dataset.yaml")
        task.update_details(
            records=len(resolved_records),
            errors=preview.error_count,
            warnings=preview.warning_count,
            diagnostics=len(preview.diagnostics),
        )
        return result


__all__ = ["run_single_manifest_conversion"]
