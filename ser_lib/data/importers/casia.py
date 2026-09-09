"""CASIA 导入器：把 data/casia_process.py 的扫描逻辑迁移为标准适配器。"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from pydantic import BaseModel, ConfigDict, Field

from ser_lib.core.events import CancellationCheck, EventCallback, EventContext
from ser_lib.data.importers.base import ImportIssue, ImportPreview, ImportTask
from ser_lib.data.importers.folder import DEFAULT_AUDIO_EXTENSIONS, _dataset_yaml
from ser_lib.data.manifest import DatasetManifest, write_jsonl
from ser_lib.data.registry import ComponentDescriptor
from ser_lib.data.types import AudioRecord

CASIA_EMOTION_MAPPING: dict[str, int] = {
    "neutral": 0,
    "happy": 1,
    "angry": 2,
    "sad": 3,
    "surprise": 4,
    "fear": 5,
}

CASIA_EMOTION_ZH: dict[str, str] = {
    "neutral": "平静",
    "happy": "高兴",
    "angry": "愤怒",
    "sad": "悲伤",
    "surprise": "惊吓",
    "fear": "恐惧",
}


class CasiaImportConfig(BaseModel):
    """casia importer 参数。"""

    model_config = ConfigDict(extra="forbid")
    audio_extensions: list[str] = Field(default_factory=lambda: list(DEFAULT_AUDIO_EXTENSIONS))
    label_mapping: dict[str, int] | None = None


class CasiaImporter:
    """CASIA（说话人/情感两级目录）导入适配器。"""

    descriptor = ComponentDescriptor(
        id="casia",
        display_name="CASIA 导入",
        category="importer",
        description="按 <root>/<speaker>/<emotion>/<utt>.wav 结构扫描 CASIA 数据集，"
                    "标签映射与 data/casia_process.py 一致。",
        config_schema=CasiaImportConfig.model_json_schema(),
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
        cfg = CasiaImportConfig(**dict(config))
        source = Path(source).resolve()
        if not source.is_dir():
            raise NotADirectoryError(f"导入源不是目录: {source}")

        label_mapping = dict(cfg.label_mapping or CASIA_EMOTION_MAPPING)
        extensions = {ext.lower() for ext in cfg.audio_extensions}
        preview = ImportPreview(importer_id=self.descriptor.id)
        with ImportTask(
            self.descriptor.id, "scan", source=source,
            event_callback=event_callback, cancellation=cancellation,
            event_context=event_context,
        ) as task:
            candidates: list[tuple[Path, str, int, Path]] = []
            for speaker_dir in sorted(source.iterdir()):
                task.check()
                if not speaker_dir.is_dir():
                    continue
                for emotion_dir in sorted(speaker_dir.iterdir()):
                    task.check()
                    if not emotion_dir.is_dir():
                        continue
                    emotion = emotion_dir.name.lower()
                    label = label_mapping.get(emotion)
                    if label is None:
                        preview.issues.append(
                            ImportIssue(
                                entry_index=None, path=emotion_dir, stage="scan",
                                message=f"发现未知情感目录 '{emotion}'，已跳过（与原脚本行为一致）",
                            )
                        )
                        continue
                    for audio_file in sorted(emotion_dir.glob("*")):
                        if audio_file.is_file() and audio_file.suffix.lower() in extensions:
                            candidates.append((speaker_dir, emotion, label, audio_file))

            total = len(candidates)
            for index, (speaker_dir, emotion, label, audio_file) in enumerate(candidates):
                task.check()
                preview.records.append(
                    AudioRecord(
                        uid=f"casia-{index:06d}",
                        audio_path=audio_file.relative_to(source),
                        label=label,
                        speaker_id=speaker_dir.name,
                        metadata={"emotion_text": emotion},
                    )
                )
                task.progress(
                    index + 1, total, message=audio_file.name,
                    details={"records_discovered": len(preview.records), "issues": len(preview.issues)},
                )

            preview.label_mapping = label_mapping
            task.update_details(
                records=len(preview.records), issues=len(preview.issues),
                warnings=len(preview.warnings), candidates=total,
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
        source = Path(source)
        destination = Path(destination)
        with ImportTask(
            self.descriptor.id, "convert", source=source, destination=destination,
            event_callback=event_callback, cancellation=cancellation,
            event_context=event_context,
        ) as task:
            destination.mkdir(parents=True, exist_ok=True)
            preview = self.scan(
                source, config, event_callback=event_callback,
                cancellation=cancellation, event_context=event_context,
            )
            task.progress(1, 3, message="scan completed", details={"records": len(preview.records)})
            if not preview.records:
                issues = "; ".join(str(i) for i in preview.issues[:10])
                raise ValueError(f"未发现任何 CASIA 音频: {issues or '目录为空'}")

            task.check()
            write_jsonl(preview.records, destination / "manifest.jsonl")
            task.progress(2, 3, message="manifest written")
            labels_yaml = {
                str(label_id): {"en": name, "zh": CASIA_EMOTION_ZH.get(name, name)}
                for name, label_id in sorted(preview.label_mapping.items(), key=lambda kv: kv[1])
            }
            (destination / "dataset.yaml").write_text(
                _dataset_yaml("casia", source.resolve(), {"default": "manifest.jsonl"}, labels_yaml),
                encoding="utf-8",
            )
            task.progress(3, 3, message="dataset manifest written")
            result = DatasetManifest.load(destination / "dataset.yaml")
            task.update_details(records=len(preview.records), issues=len(preview.issues))
            return result


__all__ = [
    "CasiaImportConfig",
    "CasiaImporter",
    "CASIA_EMOTION_MAPPING",
    "CASIA_EMOTION_ZH",
]
