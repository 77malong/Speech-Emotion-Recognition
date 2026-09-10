"""BAAI EmotionTalk JSON/WAV importer."""

from __future__ import annotations

import json
from pathlib import Path, PurePosixPath
from typing import Any, Mapping

from ser_lib.config.importers import EmotionTalkImportConfig
from ser_lib.data.importers._conversion import run_manifest_conversion, write_partitioned_manifest
from ser_lib.data.importers.base import ImportPreview, ImportTask
from ser_lib.data.importers.csemotions import _validate_speaker_splits
from ser_lib.data.manifest import DatasetManifest
from ser_lib.data.registry import ComponentDescriptor
from ser_lib.data.types import AudioRecord
from ser_lib.foundation.diagnostics import Diagnostic
from ser_lib.foundation.events import CancellationCheck, EventCallback, EventContext

EMOTIONTALK_LABELS = {
    "neutral": 0, "happy": 1, "angry": 2, "sad": 3,
    "surprised": 4, "fearful": 5, "disgusted": 6,
}
EMOTIONTALK_ZH = {
    "neutral": "中性", "happy": "快乐", "angry": "愤怒", "sad": "悲伤",
    "surprised": "惊讶", "fearful": "恐惧", "disgusted": "厌恶",
}
EMOTIONTALK_OFFICIAL_SPLITS = {"val": {"G00001", "G00012"}, "test": {"G00003", "G00015"}}


def _automatic_splits(speakers: set[str]) -> dict[str, list[str]]:
    if len(speakers) < 3:
        raise ValueError("EmotionTalk 说话人独立划分至少需要 3 位说话人")
    ordered = sorted(speakers)
    val_count = max(1, round(len(ordered) * 0.2))
    test_count = max(1, round(len(ordered) * 0.2))
    train_count = len(ordered) - val_count - test_count
    return {
        "train": ordered[:train_count],
        "val": ordered[train_count:train_count + val_count],
        "test": ordered[train_count + val_count:],
    }


def _safe_relative_audio(raw: Any) -> Path | None:
    if not isinstance(raw, str) or not raw.strip():
        return None
    posix = PurePosixPath(raw.strip())
    if posix.is_absolute() or ".." in posix.parts or posix.suffix.casefold() != ".wav":
        return None
    return Path(*posix.parts)


class EmotionTalkImporter:
    descriptor = ComponentDescriptor(
        id="emotiontalk",
        display_name="BAAI EmotionTalk 导入",
        category="importer",
        description="解析逐句 JSON/WAV、标注者置信度及描述，支持说话人独立或官方对话划分。",
        config_schema=EmotionTalkImportConfig.model_json_schema(),
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
        cfg = EmotionTalkImportConfig(**dict(config))
        source = Path(source).resolve()
        if not source.is_dir():
            raise NotADirectoryError(f"EmotionTalk 目录不存在: {source}")
        json_root = source / cfg.json_directory
        audio_root = source / cfg.audio_directory
        if not json_root.is_dir() or not audio_root.is_dir():
            raise NotADirectoryError("EmotionTalk 必须包含 json 和 wav 目录")
        mapping = dict(cfg.label_mapping or EMOTIONTALK_LABELS)
        if set(mapping) != set(EMOTIONTALK_LABELS) or len(set(mapping.values())) != len(mapping):
            raise ValueError("EmotionTalk label_mapping 必须完整覆盖七类情感且标签不能重复")
        preview = ImportPreview(importer_id=self.descriptor.id)
        if cfg.split_strategy == "official_dialogue":
            preview.diagnostics.append(
                Diagnostic(
                    "warning", "emotiontalk_official_split_speaker_overlap",
                    "官方对话划分会让部分 speaker_id 跨 split；严格说话人泛化实验请使用默认策略。",
                    stage="scan",
                )
            )
        seen: set[str] = set()
        with ImportTask(
            self.descriptor.id,
            "scan",
            source=source,
            event_callback=event_callback,
            cancellation=cancellation,
            event_context=event_context,
        ) as task:
            candidates = sorted(json_root.rglob("*.json"))
            total = len(candidates)
            for index, annotation in enumerate(candidates):
                task.check()
                try:
                    try:
                        payload = json.loads(annotation.read_text(encoding=cfg.encoding))
                    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
                        preview.diagnostics.append(
                            Diagnostic(
                                "error", "emotiontalk_json_invalid", "无法读取 JSON",
                                stage="json", path=annotation,
                                details={"entry_index": index, "detail": str(exc)},
                            )
                        )
                        continue
                    emotion = payload.get("emotion_result")
                    speaker = payload.get("speaker_id")
                    relative_audio = _safe_relative_audio(payload.get("file_path"))
                    if emotion not in mapping or not isinstance(speaker, str) or not speaker or relative_audio is None:
                        preview.diagnostics.append(
                            Diagnostic(
                                "error", "emotiontalk_schema_invalid",
                                "emotion_result/speaker_id/file_path 非法",
                                stage="schema", path=annotation, details={"entry_index": index},
                            )
                        )
                        continue
                    expected_json = json_root / relative_audio.with_suffix(".json")
                    if annotation.resolve() != expected_json.resolve():
                        preview.diagnostics.append(
                            Diagnostic(
                                "error", "emotiontalk_path_mismatch", "JSON 路径与 file_path 不对应",
                                stage="path", path=annotation, details={"entry_index": index},
                            )
                        )
                        continue
                    audio = audio_root / relative_audio
                    if not audio.is_file():
                        preview.diagnostics.append(
                            Diagnostic(
                                "error", "emotiontalk_audio_missing", "JSON 对应音频不存在",
                                stage="audio", path=audio, details={"entry_index": index},
                            )
                        )
                        continue
                    uid = f"emotiontalk-{relative_audio.stem}"
                    if uid in seen:
                        preview.diagnostics.append(
                            Diagnostic(
                                "error", "emotiontalk_uid_duplicate", f"UID 重复: {uid}",
                                stage="uid", path=annotation, details={"entry_index": index},
                            )
                        )
                        continue
                    seen.add(uid)
                    paragraphs = payload.get("paragraphs") if isinstance(payload.get("paragraphs"), dict) else {}
                    metadata = {
                        "language": "zh",
                        "text": payload.get("content", ""),
                        "emotion_text": emotion,
                        "dialogue_id": relative_audio.parts[0],
                        "turn_group": relative_audio.parent.name,
                        "start_sec": paragraphs.get("startTime"),
                        "end_sec": paragraphs.get("endTime"),
                        "duration_sec": paragraphs.get("duration"),
                        "annotator_votes": payload.get("data", {}),
                        "descriptions": payload.get("sourceAttr", {}),
                    }
                    preview.records.append(
                        AudioRecord(
                            uid=uid,
                            audio_path=Path(cfg.audio_directory) / relative_audio,
                            label=mapping[emotion],
                            speaker_id=speaker,
                            metadata=metadata,
                        )
                    )
                finally:
                    task.progress(
                        index + 1, total, message=annotation.name,
                        details={
                            "records_discovered": len(preview.records),
                            "errors": preview.error_count,
                            "diagnostics": len(preview.diagnostics),
                        },
                    )
            preview.label_mapping = mapping
            if not preview.records and preview.error_count == 0:
                preview.diagnostics.append(
                    Diagnostic("error", "emotiontalk_no_json", "未发现 EmotionTalk JSON", stage="scan", path=json_root)
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
        cfg = EmotionTalkImportConfig(**dict(config))
        source = Path(source).resolve()
        destination = Path(destination).resolve()

        def build(preview: ImportPreview, task: ImportTask):
            if cfg.split_strategy == "official_dialogue":
                if cfg.speaker_splits is not None:
                    raise ValueError("official_dialogue 策略不能同时配置 speaker_splits")
                assignments: dict[str, str] = {}
                for record in preview.records:
                    task.check()
                    dialogue = str(record.metadata["dialogue_id"])
                    split = (
                        "val"
                        if dialogue in EMOTIONTALK_OFFICIAL_SPLITS["val"]
                        else "test"
                        if dialogue in EMOTIONTALK_OFFICIAL_SPLITS["test"]
                        else "train"
                    )
                    assignments[record.uid] = split
            else:
                speakers = {record.speaker_id for record in preview.records if record.speaker_id}
                splits = (
                    _validate_speaker_splits(cfg.speaker_splits, speakers)
                    if cfg.speaker_splits is not None
                    else _automatic_splits(speakers)
                )
                speaker_to_split = {
                    speaker: split for split, members in splits.items() for speaker in members
                }
                assignments = {
                    record.uid: speaker_to_split[record.speaker_id]
                    for record in preview.records
                    if record.speaker_id
                }
            task.progress(2, 3, message="splits resolved")
            result = write_partitioned_manifest(
                destination=destination,
                dataset_id="emotiontalk",
                root=source,
                split_names=("train", "val", "test"),
                labels={
                    label: {"en": emotion, "zh": EMOTIONTALK_ZH[emotion]}
                    for emotion, label in preview.label_mapping.items()
                },
                records=preview.records,
                assignments=assignments,
                task=task,
            )
            return result, None

        return run_manifest_conversion(
            importer_id=self.descriptor.id,
            scan=self.scan,
            source=source,
            destination=destination,
            config=config,
            build_manifest=build,
            failure_message=lambda preview: (
                f"EmotionTalk 扫描失败: {preview.format_errors() or '没有记录'}"
            ),
            event_callback=event_callback,
            cancellation=cancellation,
            event_context=event_context,
        )


__all__ = ["EMOTIONTALK_LABELS", "EmotionTalkImportConfig", "EmotionTalkImporter"]
