"""CSV importer：映射音频路径列、标签列与可选元数据列。"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any, Mapping

from pydantic import BaseModel, ConfigDict, Field

from ser_lib.core.diagnostics import Diagnostic
from ser_lib.core.events import CancellationCheck, EventCallback, EventContext
from ser_lib.data.importers._conversion import run_single_manifest_conversion
from ser_lib.data.importers.base import ImportPreview, ImportTask
from ser_lib.data.manifest import DatasetManifest
from ser_lib.data.registry import ComponentDescriptor
from ser_lib.data.types import AudioRecord


class CsvImportConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    audio_path_column: str = Field(default="audio_path", min_length=1)
    label_column: str | None = Field(default="label")
    label_mapping: dict[str, int] | None = None
    speaker_column: str | None = None
    metadata_columns: list[str] = Field(default_factory=list)
    uid_column: str | None = None
    uid_prefix: str = Field(default="audio", min_length=1)
    delimiter: str = Field(default=",", min_length=1, max_length=1)
    encoding: str = "utf-8-sig"
    root: Path | None = None


class CsvImporter:
    descriptor = ComponentDescriptor(
        id="csv",
        display_name="CSV 导入",
        category="importer",
        description="映射 CSV 的音频路径列、标签列与可选元数据列，生成标准 manifest。",
        config_schema=CsvImportConfig.model_json_schema(),
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
        cfg = CsvImportConfig(**dict(config))
        source = Path(source)
        if not source.is_file():
            raise FileNotFoundError(f"CSV 文件不存在: {source}")
        preview = ImportPreview(importer_id=self.descriptor.id)
        with ImportTask(
            self.descriptor.id,
            "scan",
            source=source,
            event_callback=event_callback,
            cancellation=cancellation,
            event_context=event_context,
        ) as task:
            with open(source, "r", encoding=cfg.encoding, newline="") as stream:
                reader = csv.DictReader(stream, delimiter=cfg.delimiter)
                if reader.fieldnames is None:
                    preview.diagnostics.append(
                        Diagnostic("error", "import_csv_header_missing", "CSV 为空或没有表头", stage="scan", path=source)
                    )
                    task.update_details(records=0, errors=1, diagnostics=1, rows=0)
                    return preview
                required = [cfg.audio_path_column]
                if cfg.label_column:
                    required.append(cfg.label_column)
                missing = [column for column in required if column not in reader.fieldnames]
                if missing:
                    preview.diagnostics.append(
                        Diagnostic(
                            "error",
                            "import_csv_columns_missing",
                            f"缺少必需列: {missing}，实际表头: {reader.fieldnames}",
                            stage="scan",
                            path=source,
                        )
                    )
                    task.update_details(records=0, errors=1, diagnostics=1, rows=0)
                    return preview
                rows = list(reader)

            task.check()
            label_names: set[str] = set()
            if cfg.label_column:
                for row in rows:
                    value = (row.get(cfg.label_column) or "").strip()
                    if value:
                        label_names.add(value)
            if cfg.label_mapping is not None:
                label_mapping = dict(cfg.label_mapping)
                unknown = label_names - set(label_mapping)
                if unknown:
                    preview.diagnostics.append(
                        Diagnostic(
                            "error",
                            "import_label_mapping_missing",
                            f"以下标签值未在 label_mapping 中声明: {sorted(unknown)}",
                            stage="scan",
                            path=source,
                        )
                    )
            elif label_names and all(_is_int(name) for name in label_names):
                label_mapping = {name: int(name) for name in label_names}
            else:
                label_mapping = {name: idx for idx, name in enumerate(sorted(label_names))}

            total = len(rows)
            for index, row in enumerate(rows):
                task.check()
                try:
                    path_value = (row.get(cfg.audio_path_column) or "").strip()
                    if not path_value:
                        preview.diagnostics.append(
                            Diagnostic(
                                "error",
                                "import_audio_path_missing",
                                "音频路径为空，跳过该行",
                                stage="validate",
                                path=source,
                                details={"entry_index": index},
                            )
                        )
                        continue
                    audio_path = Path(path_value)
                    if not audio_path.is_absolute() and cfg.root is not None:
                        audio_path = Path(cfg.root) / audio_path

                    label: int | None = None
                    if cfg.label_column:
                        raw_label = (row.get(cfg.label_column) or "").strip()
                        if raw_label:
                            if cfg.label_mapping is not None or not _is_int(raw_label):
                                label = label_mapping.get(raw_label)
                                if label is None:
                                    preview.diagnostics.append(
                                        Diagnostic(
                                            "error",
                                            "import_unknown_label",
                                            f"未知标签值 '{raw_label}'，跳过该行",
                                            stage="validate",
                                            path=source,
                                            details={"entry_index": index},
                                        )
                                    )
                                    continue
                            else:
                                label = int(raw_label)

                    uid = (
                        row[cfg.uid_column].strip()
                        if cfg.uid_column and (row.get(cfg.uid_column) or "").strip()
                        else f"{cfg.uid_prefix}-{index:06d}"
                    )
                    speaker = None
                    if cfg.speaker_column and (row.get(cfg.speaker_column) or "").strip():
                        speaker = row[cfg.speaker_column].strip()
                    metadata = {
                        column: row[column]
                        for column in cfg.metadata_columns
                        if column in row and row[column] is not None
                    }
                    preview.records.append(
                        AudioRecord(
                            uid=uid,
                            audio_path=audio_path,
                            label=label,
                            speaker_id=speaker,
                            metadata=metadata,
                        )
                    )
                finally:
                    task.progress(
                        index + 1,
                        total,
                        message=f"row {index + 1}",
                        details={
                            "records_discovered": len(preview.records),
                            "errors": preview.error_count,
                            "diagnostics": len(preview.diagnostics),
                        },
                    )

            preview.label_mapping = label_mapping
            task.update_details(
                records=len(preview.records),
                errors=preview.error_count,
                warnings=preview.warning_count,
                diagnostics=len(preview.diagnostics),
                rows=total,
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
        cfg = CsvImportConfig(**dict(config))
        source = Path(source)
        return run_single_manifest_conversion(
            importer_id=self.descriptor.id,
            scan=self.scan,
            source=source,
            destination=destination,
            config=config,
            dataset_id=self.descriptor.id,
            root=cfg.root if cfg.root is not None else source.resolve().parent,
            labels=lambda preview: {
                str(label_id): {"en": name}
                for name, label_id in sorted(preview.label_mapping.items(), key=lambda item: item[1])
            },
            failure_message=lambda preview: (
                f"扫描发现 {preview.error_count} 个错误，取消导入: {preview.format_errors()}"
            ),
            event_callback=event_callback,
            cancellation=cancellation,
            event_context=event_context,
        )


def _is_int(value: str) -> bool:
    try:
        int(value)
        return True
    except ValueError:
        return False


__all__ = ["CsvImportConfig", "CsvImporter"]
