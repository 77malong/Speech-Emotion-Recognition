"""标准 manifest 的轻量摘要与音频 header profiling。"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from ser_lib.core.events import CancellationCheck, EventCallback, ProgressEvent
from ser_lib.data.audio import probe_audio
from ser_lib.data.manifest import DatasetManifest


@dataclass(frozen=True, slots=True)
class AudioProbeFailure:
    uid: str
    path: str
    error_type: str
    message: str


@dataclass(frozen=True, slots=True)
class DatasetAudioProfile:
    dataset_id: str
    split: str | None
    total_records: int
    probed_records: int
    failed_records: int
    total_duration_seconds: float
    min_duration_seconds: float | None
    max_duration_seconds: float | None
    mean_duration_seconds: float | None
    sample_rates: dict[str, int]
    channels: dict[str, int]
    failures: tuple[AudioProbeFailure, ...]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class DatasetSummary:
    """供 CLI/Web 直接消费的数据集摘要。

    默认摘要只扫描 manifest，不打开音频文件；只有显式请求音频 profiling 时，
    才填充时长、采样率、声道和失败记录统计。
    """

    dataset_id: str
    name: str
    total_records: int
    num_classes: int | None
    num_speakers: int
    splits: dict[str, int]
    labels: dict[str, int]
    total_duration_seconds: float | None = None
    audio_profiled: bool = False
    profiled_records: int = 0
    failed_audio_records: int = 0
    sample_rates: dict[str, int] = field(default_factory=dict)
    channels: dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def profile_manifest_audio(
    manifest: DatasetManifest | Path | str,
    *,
    split: str | None = None,
    fail_fast: bool = False,
    event_callback: EventCallback | None = None,
    cancellation: CancellationCheck | None = None,
) -> DatasetAudioProfile:
    """使用音频 header 统计时长、采样率、声道和损坏/缺失文件。"""
    dataset = (
        manifest
        if isinstance(manifest, DatasetManifest)
        else DatasetManifest.load(manifest)
    )
    records = dataset.get_records(split)
    durations: list[float] = []
    sample_rates: dict[str, int] = {}
    channels: dict[str, int] = {}
    failures: list[AudioProbeFailure] = []
    for index, record in enumerate(records, start=1):
        if cancellation is not None:
            cancellation.raise_if_cancelled()
        path = dataset.resolve_audio_path(record)
        try:
            info = probe_audio(path)
            rate = info.sample_rate
            channel_count = info.num_channels
            if rate <= 0 or info.num_frames <= 0 or channel_count <= 0:
                raise ValueError("音频 header 包含非正采样率、帧数或声道数")
            start = (record.start_ms or 0) / 1000.0
            end = (
                record.end_ms / 1000.0
                if record.end_ms is not None
                else info.num_frames / rate
            )
            duration = max(0.0, min(end, info.num_frames / rate) - start)
            if duration <= 0:
                raise ValueError("记录片段没有有效时长")
            durations.append(duration)
            sample_rates[str(rate)] = sample_rates.get(str(rate), 0) + 1
            channels[str(channel_count)] = channels.get(str(channel_count), 0) + 1
        except Exception as exc:
            if fail_fast:
                raise
            failures.append(
                AudioProbeFailure(
                    uid=record.uid,
                    path=path.as_posix(),
                    error_type=type(exc).__name__,
                    message=str(exc),
                )
            )
        if event_callback is not None:
            event_callback(
                ProgressEvent(
                    stage="dataset_audio_profile",
                    completed=index,
                    total=len(records),
                )
            )
    total_duration = sum(durations)
    return DatasetAudioProfile(
        dataset_id=dataset.meta.dataset_id,
        split=split,
        total_records=len(records),
        probed_records=len(durations),
        failed_records=len(failures),
        total_duration_seconds=total_duration,
        min_duration_seconds=min(durations) if durations else None,
        max_duration_seconds=max(durations) if durations else None,
        mean_duration_seconds=total_duration / len(durations) if durations else None,
        sample_rates=dict(sorted(sample_rates.items())),
        channels=dict(sorted(channels.items())),
        failures=tuple(failures),
    )


def summarize_manifest(
    manifest: DatasetManifest | Path | str,
    *,
    include_audio_profile: bool = False,
    fail_fast: bool = False,
    event_callback: EventCallback | None = None,
    cancellation: CancellationCheck | None = None,
) -> DatasetSummary:
    """构建稳定、JSON-safe 的数据集摘要。

    ``include_audio_profile=False`` 时只遍历 manifest，适合数据集列表和详情页首屏。
    开启后复用 :func:`profile_manifest_audio`，仅读取音频 header，不解码整段音频。
    """
    dataset = (
        manifest
        if isinstance(manifest, DatasetManifest)
        else DatasetManifest.load(manifest)
    )

    split_counts = {name: 0 for name in dataset.meta.splits}
    label_counts = {str(label_id): 0 for label_id in sorted(dataset.meta.labels)}
    speakers: set[str] = set()
    observed_labels: set[int] = set()

    for record in dataset.records:
        if cancellation is not None:
            cancellation.raise_if_cancelled()
        split = dataset.record_splits.get(record.uid, "unassigned")
        split_counts[split] = split_counts.get(split, 0) + 1

        if record.label is None:
            label_counts["unlabeled"] = label_counts.get("unlabeled", 0) + 1
        else:
            observed_labels.add(record.label)
            label_key = str(record.label)
            label_counts[label_key] = label_counts.get(label_key, 0) + 1

        if record.speaker_id is not None:
            speakers.add(record.speaker_id)

    num_classes = dataset.meta.num_classes or len(observed_labels) or None
    audio_profile: DatasetAudioProfile | None = None
    if include_audio_profile:
        audio_profile = profile_manifest_audio(
            dataset,
            fail_fast=fail_fast,
            event_callback=event_callback,
            cancellation=cancellation,
        )

    return DatasetSummary(
        dataset_id=dataset.meta.dataset_id,
        # 当前 manifest schema 尚无独立 display name，先稳定回退到 dataset_id。
        name=dataset.meta.dataset_id,
        total_records=len(dataset.records),
        num_classes=num_classes,
        num_speakers=len(speakers),
        splits=dict(sorted(split_counts.items())),
        labels=dict(sorted(label_counts.items())),
        total_duration_seconds=(
            audio_profile.total_duration_seconds if audio_profile is not None else None
        ),
        audio_profiled=audio_profile is not None,
        profiled_records=(audio_profile.probed_records if audio_profile is not None else 0),
        failed_audio_records=(
            audio_profile.failed_records if audio_profile is not None else 0
        ),
        sample_rates=(audio_profile.sample_rates if audio_profile is not None else {}),
        channels=(audio_profile.channels if audio_profile is not None else {}),
    )


__all__ = [
    "AudioProbeFailure",
    "DatasetAudioProfile",
    "DatasetSummary",
    "profile_manifest_audio",
    "summarize_manifest",
]
