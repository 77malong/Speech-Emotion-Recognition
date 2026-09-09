"""目录扫描 importer：按目录结构与文件名规则导入。"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from pydantic import BaseModel, ConfigDict, Field, field_validator

from ser_lib.core.diagnostics import Diagnostic
from ser_lib.core.events import CancellationCheck, EventCallback, EventContext
from ser_lib.data.importers.base import ImportPreview, ImportTask
from ser_lib.data.manifest import DatasetManifest, write_jsonl
from ser_lib.data.registry import ComponentDescriptor
from ser_lib.data.types import AudioRecord

DEFAULT_AUDIO_EXTENSIONS = (".wav", ".flac", ".mp3", ".ogg", ".m4a", ".wv", ".aiff")


class FolderImportConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    audio_extensions: list[str] = Field(default_factory=lambda: list(DEFAULT_AUDIO_EXTENSIONS))
    label_dir_level: int = Field(default=0, ge=0, le=2)
    speaker_dir_level: int | None = Field(default=None, ge=0, le=3)
    label_mapping: dict[str, int] | None = None
    uid_prefix: str = Field(default="audio", min_length=1)
    relative_paths: bool = True

    @field_validator("audio_extensions")
    @classmethod
    def _normalize_ext(cls, value: list[str]) -> list[str]:
        result = []
        for ext in value:
            ext = ext.lower()
            if not ext.startswith("."):
                ext = "." + ext
            result.append(ext)
        return result


class FolderImporter:
    descriptor = ComponentDescriptor(
        id="folder",
        display_name="目录导入",
        category="importer",
        description="扫描目录树，按目录名推导标签与说话人，生成标准 manifest。",
        config_schema=FolderImportConfig.model_json_schema(),
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
        cfg = FolderImportConfig(**dict(config))
        source = Path(source).resolve()
        if not source.is_dir():
            raise NotADirectoryError(f"导入源不是目录: {source}")

        preview = ImportPreview(importer_id=self.descriptor.id)
        with ImportTask(
            self.descriptor.id,
            "scan",
            source=source,
            event_callback=event_callback,
            cancellation=cancellation,
            event_context=event_context,
        ) as task:
            extensions = set(cfg.audio_extensions)
            candidates = [
                path
                for path in sorted(source.rglob("*"))
                if path.is_file() and path.suffix.lower() in extensions
            ]
            found: list[tuple[Path, str, str | None]] = []
            label_names: set[str] = set()
            total = len(candidates)
            for index, path in enumerate(candidates):
                task.check()
                try:
                    try:
                        label_name = path.relative_to(source).parts[-1 - cfg.label_dir_level]
                    except IndexError:
                        preview.diagnostics.append(
                            Diagnostic(
                                "error",
                                "import_label_path_invalid",
                                f"目录层级不足，无法提取标签 (label_dir_level={cfg.label_dir_level})",
                                stage="scan",
                                path=path,
                                details={"entry_index": index},
                            )
                        )
                        continue
                    speaker: str | None = None
                    if cfg.speaker_dir_level is not None:
                        try:
                            speaker = path.relative_to(source).parts[-1 - cfg.speaker_dir_level]
                        except IndexError:
                            speaker = None
                    found.append((path, label_name, speaker))
                    label_names.add(label_name)
                finally:
                    task.progress(
                        index + 1,
                        total,
                        message=path.name,
                        details={
                            "phase": "discover",
                            "records_discovered": len(found),
                            "errors": preview.error_count,
                            "diagnostics": len(preview.diagnostics),
                        },
                    )

            if cfg.label_mapping is not None:
                unknown = label_names - set(cfg.label_mapping)
                if unknown:
                    preview.diagnostics.append(
                        Diagnostic(
                            "error",
                            "import_label_mapping_missing",
                            f"以下标签目录未在 label_mapping 中声明: {sorted(unknown)}",
                            stage="scan",
                            path=source,
                        )
                    )
                label_mapping = dict(cfg.label_mapping)
            else:
                label_mapping = {name: idx for idx, name in enumerate(sorted(label_names))}
                if not label_mapping:
                    preview.diagnostics.append(
                        Diagnostic(
                            "error",
                            "import_no_audio",
                            "未发现任何音频文件",
                            stage="scan",
                            path=source,
                        )
                    )

            for index, (path, label_name, speaker) in enumerate(found):
                task.check()
                label = label_mapping.get(label_name)
                if label is None:
                    preview.diagnostics.append(
                        Diagnostic(
                            "error",
                            "import_unknown_label",
                            f"未知标签 '{label_name}'，跳过该条目",
                            stage="scan",
                            path=path,
                            details={"entry_index": index},
                        )
                    )
                    continue
                audio_path = path.relative_to(source) if cfg.relative_paths else path.resolve()
                preview.records.append(
                    AudioRecord(
                        uid=f"{cfg.uid_prefix}-{index:06d}",
                        audio_path=Path(audio_path),
                        label=label,
                        speaker_id=speaker,
                        metadata={"label_name": label_name},
                    )
                )

            preview.label_mapping = label_mapping
            task.update_details(
                records=len(preview.records),
                errors=preview.error_count,
                warnings=preview.warning_count,
                diagnostics=len(preview.diagnostics),
                candidates=total,
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
        cfg = FolderImportConfig(**dict(config))
        source = Path(source)
        destination = Path(destination)
        with ImportTask(
            self.descriptor.id,
            "convert",
            source=source,
            destination=destination,
            event_callback=event_callback,
            cancellation=cancellation,
            event_context=event_context,
        ) as task:
            destination.mkdir(parents=True, exist_ok=True)
            preview = self.scan(
                source,
                config,
                event_callback=event_callback,
                cancellation=cancellation,
                event_context=event_context,
            )
            task.progress(1, 3, message="scan completed", details={"records": len(preview.records)})
            if not preview.ok:
                raise ValueError(
                    f"扫描发现 {preview.error_count} 个错误，取消导入: {preview.format_errors()}"
                )
            records = preview.records
            if not cfg.relative_paths:
                records = [
                    AudioRecord(
                        uid=record.uid,
                        audio_path=source / record.audio_path,
                        label=record.label,
                        speaker_id=record.speaker_id,
                        metadata=dict(record.metadata),
                    )
                    for record in records
                ]
            task.check()
            write_jsonl(records, destination / "manifest.jsonl")
            task.progress(2, 3, message="manifest written")
            labels_yaml = {
                str(label_id): {"en": name}
                for name, label_id in sorted(preview.label_mapping.items(), key=lambda item: item[1])
            }
            root = source.resolve() if cfg.relative_paths else "."
            (destination / "dataset.yaml").write_text(
                _dataset_yaml(self.descriptor.id, root, {"default": "manifest.jsonl"}, labels_yaml),
                encoding="utf-8",
            )
            task.progress(3, 3, message="dataset manifest written")
            result = DatasetManifest.load(destination / "dataset.yaml")
            task.update_details(
                records=len(preview.records),
                errors=preview.error_count,
                diagnostics=len(preview.diagnostics),
            )
            return result


def _dataset_yaml(
    dataset_id: str,
    root: Any,
    splits: Mapping[str, str],
    labels: Mapping[str, Any],
) -> str:
    import yaml

    return yaml.safe_dump(
        {
            "schema_version": 1,
            "dataset_id": dataset_id,
            "root": str(root),
            "splits": dict(splits),
            "labels": dict(labels),
        },
        allow_unicode=True,
        sort_keys=False,
    )


__all__ = ["FolderImportConfig", "FolderImporter", "DEFAULT_AUDIO_EXTENSIONS"]
