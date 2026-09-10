"""RAVDESS 官方七段文件名格式适配器。"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from ser_lib.config.importers import RavdessImportConfig
from ser_lib.data.importers._conversion import run_single_manifest_conversion
from ser_lib.data.importers.base import ImportPreview, ImportTask
from ser_lib.data.manifest import DatasetManifest
from ser_lib.data.registry import ComponentDescriptor
from ser_lib.data.types import AudioRecord
from ser_lib.foundation.diagnostics import Diagnostic
from ser_lib.foundation.events import CancellationCheck, EventCallback, EventContext

RAVDESS_EMOTIONS = {
    "01": (0, "neutral"),
    "02": (1, "calm"),
    "03": (2, "happy"),
    "04": (3, "sad"),
    "05": (4, "angry"),
    "06": (5, "fearful"),
    "07": (6, "disgust"),
    "08": (7, "surprised"),
}


class RavdessImporter:
    descriptor = ComponentDescriptor(
        id="ravdess",
        display_name="RAVDESS 导入",
        category="importer",
        description="解析 RAVDESS 官方 7 段文件名，仅引用本地 audio-only WAV。",
        config_schema=RavdessImportConfig.model_json_schema(),
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
        cfg = RavdessImportConfig(**dict(config))
        source = Path(source).resolve()
        if not source.is_dir():
            raise NotADirectoryError(f"导入源不是目录: {source}")
        preview = ImportPreview(importer_id=self.descriptor.id)
        preview.diagnostics.append(
            Diagnostic(
                "warning",
                "ravdess_license_notice",
                "RAVDESS 官方数据采用 CC BY-NC-SA 4.0；使用者须自行确认许可条件。",
                stage="scan",
            )
        )
        channel_code = {"speech": "01", "song": "02", "all": None}[cfg.vocal_channel]
        with ImportTask(
            self.descriptor.id,
            "scan",
            source=source,
            event_callback=event_callback,
            cancellation=cancellation,
            event_context=event_context,
        ) as task:
            candidates = sorted(source.rglob("*.wav"))
            total = len(candidates)
            for index, path in enumerate(candidates):
                task.check()
                try:
                    fields = path.stem.split("-")
                    if len(fields) != 7 or any(len(field) != 2 or not field.isdigit() for field in fields):
                        preview.diagnostics.append(
                            Diagnostic(
                                "error",
                                "ravdess_filename_invalid",
                                "文件名不是 RAVDESS 七段两位数字格式",
                                stage="filename",
                                path=path,
                                details={"entry_index": index},
                            )
                        )
                        continue
                    modality, channel, emotion, intensity, statement, repetition, actor = fields
                    if modality != "03":
                        continue
                    if channel_code is not None and channel != channel_code:
                        continue
                    emotion_entry = RAVDESS_EMOTIONS.get(emotion)
                    actor_number = int(actor)
                    if emotion_entry is None:
                        preview.diagnostics.append(
                            Diagnostic(
                                "error",
                                "ravdess_emotion_code_invalid",
                                "文件名包含超出 RAVDESS 官方范围的情感编码",
                                stage="filename",
                                path=path,
                                details={"entry_index": index},
                            )
                        )
                        continue
                    invalid = (
                        channel not in {"01", "02"}
                        or intensity not in {"01", "02"}
                        or statement not in {"01", "02"}
                        or repetition not in {"01", "02"}
                        or actor_number not in range(1, 25)
                        or (emotion == "01" and intensity != "01")
                    )
                    if invalid:
                        preview.diagnostics.append(
                            Diagnostic(
                                "error",
                                "ravdess_field_code_invalid",
                                "文件名包含超出 RAVDESS 官方范围的字段编码",
                                stage="filename",
                                path=path,
                                details={"entry_index": index},
                            )
                        )
                        continue
                    label, emotion_name = emotion_entry
                    audio_path = path.relative_to(source) if cfg.relative_paths else path
                    preview.records.append(
                        AudioRecord(
                            uid=f"ravdess-{path.stem}",
                            audio_path=audio_path,
                            label=label,
                            speaker_id=f"actor-{actor}",
                            metadata={
                                "emotion_text": emotion_name,
                                "vocal_channel": "speech" if channel == "01" else "song",
                                "intensity": "normal" if intensity == "01" else "strong",
                                "statement": int(statement),
                                "repetition": int(repetition),
                                "actor_gender": "male" if actor_number % 2 else "female",
                            },
                        )
                    )
                finally:
                    task.progress(
                        index + 1,
                        total,
                        message=path.name,
                        details={
                            "records_discovered": len(preview.records),
                            "errors": preview.error_count,
                            "diagnostics": len(preview.diagnostics),
                        },
                    )
            preview.label_mapping = {name: label for label, name in RAVDESS_EMOTIONS.values()}
            if not preview.records and preview.error_count == 0:
                preview.diagnostics.append(
                    Diagnostic(
                        "error",
                        "ravdess_no_audio",
                        "未发现符合筛选条件的 RAVDESS audio-only WAV",
                        stage="scan",
                        path=source,
                    )
                )
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
        cfg = RavdessImportConfig(**dict(config))
        source = Path(source)
        return run_single_manifest_conversion(
            importer_id=self.descriptor.id,
            scan=self.scan,
            source=source,
            destination=destination,
            config=config,
            dataset_id=self.descriptor.id,
            root=source.resolve() if cfg.relative_paths else ".",
            labels=lambda preview: {
                str(label): {"en": name} for label, name in RAVDESS_EMOTIONS.values()
            },
            failure_message=lambda preview: (
                f"RAVDESS 扫描失败，取消导入: {preview.format_errors() or '没有记录'}"
            ),
            event_callback=event_callback,
            cancellation=cancellation,
            event_context=event_context,
        )


__all__ = ["RavdessImporter", "RavdessImportConfig", "RAVDESS_EMOTIONS"]
