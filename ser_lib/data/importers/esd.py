"""Emotional Speech Dataset (ESD) directory importer."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal, Mapping

from pydantic import BaseModel, ConfigDict

from ser_lib.core.diagnostics import Diagnostic
from ser_lib.core.events import CancellationCheck, EventCallback, EventContext
from ser_lib.data.importers._conversion import run_manifest_conversion, write_partitioned_manifest
from ser_lib.data.importers.base import ImportPreview, ImportTask
from ser_lib.data.importers.csemotions import _automatic_speaker_splits, _validate_speaker_splits
from ser_lib.data.manifest import DatasetManifest
from ser_lib.data.registry import ComponentDescriptor
from ser_lib.data.types import AudioRecord

ESD_LABELS = {"Neutral": 0, "Happy": 1, "Angry": 2, "Sad": 3, "Surprise": 4}
ESD_ZH = {"Neutral": "中性", "Happy": "快乐", "Angry": "愤怒", "Sad": "悲伤", "Surprise": "惊讶"}


class EsdImportConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    languages: list[Literal["zh", "en"]] = ["zh", "en"]
    encoding: str = "utf-8-sig"
    label_mapping: dict[str, int] | None = None
    speaker_splits: dict[str, list[str]] | None = None


def _language(speaker: str) -> str | None:
    if speaker.isdigit() and 1 <= int(speaker) <= 10:
        return "zh"
    if speaker.isdigit() and 11 <= int(speaker) <= 20:
        return "en"
    return None


def _speaker_splits(configured: dict[str, list[str]] | None, speakers: set[str]) -> dict[str, list[str]]:
    if configured is not None:
        return _validate_speaker_splits(configured, speakers)
    result: dict[str, list[str]] = {"train": [], "val": [], "test": []}
    for language in ("zh", "en"):
        members = {speaker for speaker in speakers if _language(speaker) == language}
        if not members:
            continue
        splits = _automatic_speaker_splits(members)
        for split in result:
            result[split].extend(splits[split])
    return result


def _transcripts(path: Path, encoding: str) -> tuple[dict[str, str], list[Diagnostic]]:
    result: dict[str, str] = {}
    diagnostics: list[Diagnostic] = []
    if not path.is_file():
        return result, [
            Diagnostic("error", "esd_transcript_missing", "说话人文本文件不存在", stage="transcript", path=path)
        ]
    for line_number, raw in enumerate(path.read_text(encoding=encoding).splitlines(), start=1):
        if not raw.strip():
            continue
        fields = raw.split("\t")
        if len(fields) < 2 or not fields[0].strip():
            diagnostics.append(
                Diagnostic(
                    "error", "esd_transcript_row_invalid", "文本行不是制表符分隔格式",
                    stage="transcript", path=path, details={"entry_index": line_number},
                )
            )
            continue
        uid = fields[0].strip()
        if uid in result:
            diagnostics.append(
                Diagnostic(
                    "error", "esd_transcript_uid_duplicate", f"文本 UID 重复: {uid}",
                    stage="transcript", path=path, details={"entry_index": line_number},
                )
            )
            continue
        result[uid] = fields[1].strip()
    return result, diagnostics


class EsdImporter:
    descriptor = ComponentDescriptor(
        id="esd",
        display_name="ESD 导入",
        category="importer",
        description="解析 ESD 20 位中英语者目录，并生成语言分层、说话人独立划分。",
        config_schema=EsdImportConfig.model_json_schema(),
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
        cfg = EsdImportConfig(**dict(config))
        source = Path(source).resolve()
        if not source.is_dir():
            raise NotADirectoryError(f"ESD 目录不存在: {source}")
        preview = ImportPreview(importer_id=self.descriptor.id)
        mapping = dict(cfg.label_mapping or ESD_LABELS)
        selected_languages = set(cfg.languages)
        seen: set[str] = set()
        with ImportTask(
            self.descriptor.id,
            "scan",
            source=source,
            event_callback=event_callback,
            cancellation=cancellation,
            event_context=event_context,
        ) as task:
            candidates: list[tuple[str, str, int, str, dict[str, str], Path]] = []
            for speaker_dir in sorted(path for path in source.iterdir() if path.is_dir()):
                task.check()
                speaker = speaker_dir.name
                language = _language(speaker)
                if language is None:
                    preview.diagnostics.append(
                        Diagnostic(
                            "warning", "esd_unknown_speaker_directory",
                            f"忽略非 ESD 说话人目录: {speaker_dir}",
                            stage="scan", path=speaker_dir,
                        )
                    )
                    continue
                if language not in selected_languages:
                    continue
                texts, diagnostics = _transcripts(speaker_dir / f"{speaker}.txt", cfg.encoding)
                preview.diagnostics.extend(diagnostics)
                for emotion, label in mapping.items():
                    task.check()
                    emotion_dir = speaker_dir / emotion
                    if not emotion_dir.is_dir():
                        preview.diagnostics.append(
                            Diagnostic(
                                "error", "esd_emotion_directory_missing",
                                f"缺少情感目录: {emotion}", stage="directory", path=emotion_dir,
                            )
                        )
                        continue
                    for audio in sorted(emotion_dir.glob("*.wav")):
                        candidates.append((speaker, language, label, emotion, texts, audio))
            total = len(candidates)
            for index, (speaker, language, label, emotion, texts, audio) in enumerate(candidates):
                task.check()
                try:
                    uid = audio.stem
                    if uid in seen:
                        preview.diagnostics.append(
                            Diagnostic("error", "esd_uid_duplicate", f"UID 重复: {uid}", stage="uid", path=audio)
                        )
                        continue
                    seen.add(uid)
                    if not uid.startswith(f"{speaker}_"):
                        preview.diagnostics.append(
                            Diagnostic(
                                "error", "esd_filename_speaker_mismatch",
                                "文件名说话人前缀与目录不一致", stage="filename", path=audio,
                            )
                        )
                        continue
                    text = texts.get(uid)
                    if text is None:
                        preview.diagnostics.append(
                            Diagnostic(
                                "error", "esd_transcript_entry_missing",
                                "音频在文本文件中没有转写", stage="transcript", path=audio,
                            )
                        )
                        continue
                    preview.records.append(
                        AudioRecord(
                            uid=f"esd-{uid}",
                            audio_path=audio.relative_to(source),
                            label=label,
                            speaker_id=speaker,
                            metadata={"emotion_text": emotion.casefold(), "text": text, "language": language},
                        )
                    )
                finally:
                    task.progress(
                        index + 1, total, message=audio.name,
                        details={
                            "records_discovered": len(preview.records),
                            "errors": preview.error_count,
                            "diagnostics": len(preview.diagnostics),
                        },
                    )
            preview.label_mapping = mapping
            if not preview.records and preview.error_count == 0:
                preview.diagnostics.append(
                    Diagnostic("error", "esd_no_audio", "未发现符合条件的 ESD WAV", stage="scan", path=source)
                )
            task.update_details(
                records=len(preview.records), errors=preview.error_count,
                warnings=preview.warning_count, diagnostics=len(preview.diagnostics), candidates=total,
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
        cfg = EsdImportConfig(**dict(config))
        source = Path(source).resolve()
        destination = Path(destination).resolve()

        def build(preview: ImportPreview, task: ImportTask):
            speakers = {record.speaker_id for record in preview.records if record.speaker_id}
            split_speakers = _speaker_splits(cfg.speaker_splits, speakers)
            speaker_to_split = {
                speaker: split for split, members in split_speakers.items() for speaker in members
            }
            assignments = {
                record.uid: speaker_to_split[record.speaker_id]
                for record in preview.records
                if record.speaker_id
            }
            task.progress(2, 3, message="speaker splits resolved")
            result = write_partitioned_manifest(
                destination=destination,
                dataset_id="esd",
                root=source,
                split_names=tuple(split_speakers),
                labels={
                    label: {"en": emotion.casefold(), "zh": ESD_ZH.get(emotion, emotion)}
                    for emotion, label in preview.label_mapping.items()
                },
                records=preview.records,
                assignments=assignments,
                task=task,
            )
            return result, {"splits": {name: len(members) for name, members in split_speakers.items()}}

        return run_manifest_conversion(
            importer_id=self.descriptor.id,
            scan=self.scan,
            source=source,
            destination=destination,
            config=config,
            build_manifest=build,
            failure_message=lambda preview: f"ESD 扫描失败: {preview.format_errors() or '没有记录'}",
            event_callback=event_callback,
            cancellation=cancellation,
            event_context=event_context,
        )


__all__ = ["ESD_LABELS", "ESD_ZH", "EsdImportConfig", "EsdImporter"]
