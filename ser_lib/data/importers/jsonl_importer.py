"""JSONL importer：校验标准或近似标准 manifest。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from ser_lib.config.importers import JsonlImportConfig
from ser_lib.data.errors import ManifestError
from ser_lib.data.importers._conversion import run_single_manifest_conversion
from ser_lib.data.importers.base import ImportPreview, ImportTask
from ser_lib.data.manifest import DatasetManifest, parse_record
from ser_lib.data.registry import ComponentDescriptor
from ser_lib.data.types import AudioRecord
from ser_lib.foundation.diagnostics import Diagnostic
from ser_lib.foundation.events import CancellationCheck, EventCallback, EventContext

STANDARD_FIELDS = frozenset(
    {"uid", "audio_path", "label", "start_ms", "end_ms", "speaker_id", "sample_rate_hint", "metadata"}
)
LEGACY_ALIASES = {
    "start_time_ms": "start_ms",
    "end_time_ms": "end_ms",
    "sample_rate": "sample_rate_hint",
    "sr": "sample_rate_hint",
}


def normalize_raw_record(raw: Mapping[str, Any], *, index: int, uid_prefix: str) -> dict[str, Any]:
    entry: dict[str, Any] = {}
    metadata: dict[str, Any] = {}
    for key, value in raw.items():
        if key in ("uid", "audio_path", "label", "speaker_id", "metadata"):
            if value is not None:
                entry[key] = value
        elif key in LEGACY_ALIASES:
            canonical = LEGACY_ALIASES[key]
            if value is not None and canonical not in entry:
                entry[canonical] = value
        elif key in ("start_ms", "end_ms", "sample_rate_hint"):
            if value is not None:
                entry[key] = value
        else:
            metadata[key] = value
    if entry.get("metadata"):
        metadata.update(dict(entry.pop("metadata")))
    if metadata:
        entry["metadata"] = metadata
    if not entry.get("uid"):
        entry["uid"] = f"{uid_prefix}-{index:06d}"
    return entry


def normalize_raw_records(raw_records: list[Mapping[str, Any]], *, uid_prefix: str) -> list[AudioRecord]:
    records: list[AudioRecord] = []
    seen_uids: set[str] = set()
    for index, raw in enumerate(raw_records):
        entry = normalize_raw_record(raw, index=index, uid_prefix=uid_prefix)
        record = parse_record(entry, source=Path("<normalized>"), line_number=index + 1)
        if record.uid in seen_uids:
            raise ManifestError(f"UID 重复: '{record.uid}'（第 {index + 1} 条）", uid=record.uid)
        seen_uids.add(record.uid)
        records.append(record)
    return records


class JsonlImporter:
    descriptor = ComponentDescriptor(
        id="jsonl",
        display_name="JSONL 导入",
        category="importer",
        description="校验标准或近似标准的 JSONL manifest，规范化字段并生成标准 manifest。",
        config_schema=JsonlImportConfig.model_json_schema(),
    )

    def scan(
        self,
        source: Path,
        config: Mapping[str, Any],
        *,
        event_callback: EventCallback | None = None,
        cancellation: CancellationCheck | None = None,
        event_context: EventContext | None = None,
    ) -> ImportPreview:
        cfg = JsonlImportConfig(**dict(config))
        source = Path(source)
        preview = ImportPreview(importer_id=self.descriptor.id)
        with ImportTask(
            self.descriptor.id,
            "scan",
            source=source,
            event_callback=event_callback,
            cancellation=cancellation,
            event_context=event_context,
        ) as task:
            lines = source.read_text(encoding="utf-8").splitlines()
            nonempty = [(line_number, line) for line_number, line in enumerate(lines, start=1) if line.strip()]
            total = len(nonempty)
            raw_records: list[dict[str, Any]] = []
            for index, (line_number, line) in enumerate(nonempty):
                task.check()
                try:
                    try:
                        raw = json.loads(line.strip())
                    except json.JSONDecodeError as exc:
                        preview.diagnostics.append(
                            Diagnostic(
                                "error",
                                "import_json_parse_error",
                                f"JSON 解析失败 (第 {line_number} 行): {exc.msg}",
                                stage="scan",
                                path=source,
                                details={"entry_index": len(raw_records), "line_number": line_number},
                            )
                        )
                        raw_records.append({})
                        continue
                    if not isinstance(raw, dict):
                        preview.diagnostics.append(
                            Diagnostic(
                                "error",
                                "import_json_record_invalid",
                                f"JSONL 第 {line_number} 行顶层必须是对象",
                                stage="scan",
                                path=source,
                                details={"entry_index": len(raw_records), "line_number": line_number},
                            )
                        )
                        raw_records.append({})
                        continue
                    raw_records.append(raw)
                finally:
                    task.progress(
                        index + 1,
                        total,
                        message=f"line {line_number}",
                        details={"phase": "parse", "errors": preview.error_count, "diagnostics": len(preview.diagnostics)},
                    )

            for index, raw in enumerate(raw_records):
                task.check()
                if not raw:
                    continue
                entry = normalize_raw_record(raw, index=index, uid_prefix=cfg.uid_prefix)
                try:
                    record = parse_record(entry, source=source, line_number=index + 1)
                except ManifestError as exc:
                    preview.diagnostics.append(
                        Diagnostic(
                            "error",
                            "import_record_invalid",
                            str(exc),
                            stage="validate",
                            path=source,
                            details={"entry_index": index},
                        )
                    )
                    continue
                preview.records.append(record)

            task.update_details(
                records=len(preview.records),
                errors=preview.error_count,
                warnings=preview.warning_count,
                diagnostics=len(preview.diagnostics),
                entries=total,
            )
            return preview

    def convert(
        self,
        source: Path,
        destination: Path,
        config: Mapping[str, Any],
        *,
        event_callback: EventCallback | None = None,
        cancellation: CancellationCheck | None = None,
        event_context: EventContext | None = None,
    ) -> DatasetManifest:
        cfg = JsonlImportConfig(**dict(config))
        source = Path(source)
        return run_single_manifest_conversion(
            importer_id=self.descriptor.id,
            scan=self.scan,
            source=source,
            destination=destination,
            config=config,
            dataset_id=self.descriptor.id,
            root=cfg.root if cfg.root is not None else source.resolve().parent,
            failure_message=lambda preview: (
                f"扫描发现 {preview.error_count} 个错误，取消导入: {preview.format_errors()}"
            ),
            event_callback=event_callback,
            cancellation=cancellation,
            event_context=event_context,
        )


__all__ = ["JsonlImportConfig", "JsonlImporter", "normalize_raw_record", "normalize_raw_records", "STANDARD_FIELDS"]
