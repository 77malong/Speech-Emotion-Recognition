"""Importer convert 阶段共享编排；只处理通用写盘，不包含数据集解析规则。"""

from __future__ import annotations

import shutil
import tempfile
import uuid
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any

import yaml

from ser_lib.data.importers.base import ImportPreview, ImportTask
from ser_lib.data.manifest import DatasetManifest, ManifestMeta, write_jsonl
from ser_lib.data.types import AudioRecord
from ser_lib.foundation.events import CancellationCheck, EventCallback, EventContext

ScanCallable = Callable[..., ImportPreview]
RecordResolver = Callable[[ImportPreview], Sequence[AudioRecord]]
LabelResolver = Callable[[ImportPreview], Mapping[Any, Any]]
FailureFormatter = Callable[[ImportPreview], str]
BuildManifest = Callable[
    [ImportPreview, ImportTask],
    tuple[DatasetManifest, Mapping[str, Any] | None],
]


def run_manifest_conversion(
    *,
    importer_id: str,
    scan: ScanCallable,
    source: Path,
    destination: Path,
    config: Mapping[str, Any],
    build_manifest: BuildManifest,
    failure_message: FailureFormatter | None = None,
    event_callback: EventCallback | None = None,
    cancellation: CancellationCheck | None = None,
    event_context: EventContext | None = None,
) -> DatasetManifest:
    """统一 convert 生命周期、scan 调用、preview 门禁和终态统计。"""
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
            raise ValueError(
                f"{importer_id} 扫描失败: {preview.format_errors() or '没有记录'}"
            )

        result, extra_details = build_manifest(preview, task)
        task.progress(3, 3, message="dataset manifest written")
        task.update_details(
            records=len(preview.records),
            errors=preview.error_count,
            warnings=preview.warning_count,
            diagnostics=len(preview.diagnostics),
            **dict(extra_details or {}),
        )
        return result


def _commit_staged_directory(staging: Path, destination: Path) -> None:
    """Replace a dataset directory with rollback on commit-time exceptions."""
    if destination.exists() and not destination.is_dir():
        raise ValueError(f"导入目标已存在且不是目录: {destination}")

    backup: Path | None = None
    if destination.exists():
        backup = destination.parent / f".{destination.name}.backup-{uuid.uuid4().hex}"
        destination.replace(backup)

    try:
        staging.replace(destination)
    except BaseException:
        if backup is not None and backup.exists() and not destination.exists():
            backup.replace(destination)
        raise
    else:
        if backup is not None:
            shutil.rmtree(backup, ignore_errors=True)


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
    """执行单 JSONL manifest importer 的标准 convert 流程。

    所有输出先写到目标同级 staging 目录，并在那里完成 ``DatasetManifest.load``
    验证。只有 staging 完整有效后才替换正式目标；提交阶段发生异常时恢复原目录，
    避免“导入失败但旧数据集已经被覆盖”。
    """
    destination = Path(destination)

    def build(preview: ImportPreview, task: ImportTask):
        resolved_records = list(records(preview) if records is not None else preview.records)
        destination.parent.mkdir(parents=True, exist_ok=True)
        staging = Path(
            tempfile.mkdtemp(
                prefix=f".{destination.name}.import-",
                dir=destination.parent,
            )
        )
        try:
            task.check()
            write_jsonl(resolved_records, staging / "manifest.jsonl")
            task.progress(2, 3, message="manifest staged")
            document: dict[str, Any] = {

                "dataset_id": dataset_id,
                "root": str(root),
                "splits": {"default": "manifest.jsonl"},
            }
            if labels is not None:
                resolved_labels = dict(labels(preview))
                if resolved_labels:
                    document["labels"] = resolved_labels
            (staging / "dataset.yaml").write_text(
                yaml.safe_dump(document, allow_unicode=True, sort_keys=False),
                encoding="utf-8",
            )

            # Validate the complete candidate before touching the existing target.
            DatasetManifest.load(staging / "dataset.yaml")
            task.check()
            _commit_staged_directory(staging, destination)
            return DatasetManifest.load(destination / "dataset.yaml"), None
        finally:
            if staging.exists():
                shutil.rmtree(staging, ignore_errors=True)

    return run_manifest_conversion(
        importer_id=importer_id,
        scan=scan,
        source=source,
        destination=destination,
        config=config,
        build_manifest=build,
        failure_message=failure_message,
        event_callback=event_callback,
        cancellation=cancellation,
        event_context=event_context,
    )


def write_partitioned_manifest(
    *,
    destination: Path,
    dataset_id: str,
    root: Path | str,
    split_names: Sequence[str],
    labels: Mapping[int, Mapping[str, str]],
    records: Sequence[AudioRecord],
    assignments: Mapping[str, str],
    task: ImportTask,
) -> DatasetManifest:
    """统一写入带显式 record→split 映射的标准 DatasetManifest。"""
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    task.check()
    meta = ManifestMeta(
        dataset_id=dataset_id,
        root=Path(root),
        yaml_path=destination / "dataset.yaml",
        splits={name: destination / f"{name}.jsonl" for name in split_names},
        labels={key: dict(value) for key, value in labels.items()},
    )
    DatasetManifest(meta, list(records), dict(assignments)).write()
    return DatasetManifest.load(destination / "dataset.yaml")


__all__ = [
    "run_manifest_conversion",
    "run_single_manifest_conversion",
    "write_partitioned_manifest",
]
