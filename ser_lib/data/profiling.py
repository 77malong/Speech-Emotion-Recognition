"""标准 manifest 的轻量摘要与可视化详细 profiling。"""

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
class DurationHistogramBin:
    lower_seconds: float
    upper_seconds: float
    count: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


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
    median_duration_seconds: float | None = None
    p90_duration_seconds: float | None = None
    p95_duration_seconds: float | None = None
    p99_duration_seconds: float | None = None
    duration_histogram: tuple[DurationHistogramBin, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class DatasetSummary:
    """供 CLI/Web 列表和详情首屏直接消费的数据集摘要。

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


@dataclass(frozen=True, slots=True)
class DatasetProfile:
    """供可视化数据集分析页使用的详细、JSON-safe profile。"""

    dataset_id: str
    name: str
    total_records: int
    num_classes: int | None
    num_speakers: int
    unlabeled_records: int
    records_without_speaker: int
    splits: dict[str, int]
    labels: dict[str, int]
    label_display_names: dict[str, str]
    split_labels: dict[str, dict[str, int]]
    speaker_counts: dict[str, int]
    audio_profile: DatasetAudioProfile | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "dataset_id": self.dataset_id,
            "name": self.name,
            "total_records": self.total_records,
            "num_classes": self.num_classes,
            "num_speakers": self.num_speakers,
            "unlabeled_records": self.unlabeled_records,
            "records_without_speaker": self.records_without_speaker,
            "splits": dict(self.splits),
            "labels": dict(self.labels),
            "label_display_names": dict(self.label_display_names),
            "split_labels": {
                split: dict(counts) for split, counts in self.split_labels.items()
            },
            "speaker_counts": dict(self.speaker_counts),
            "audio_profile": (
                self.audio_profile.to_dict() if self.audio_profile is not None else None
            ),
        }


def _percentile(sorted_values: list[float], quantile: float) -> float | None:
    if not sorted_values:
        return None
    if len(sorted_values) == 1:
        return sorted_values[0]
    position = (len(sorted_values) - 1) * quantile
    lower = int(position)
    upper = min(lower + 1, len(sorted_values) - 1)
    fraction = position - lower
    return sorted_values[lower] * (1.0 - fraction) + sorted_values[upper] * fraction


def _duration_histogram(
    durations: list[float],
    *,
    bins: int,
) -> tuple[DurationHistogramBin, ...]:
    if bins < 1:
        raise ValueError("histogram_bins 必须 >= 1")
    if not durations:
        return ()
    minimum = min(durations)
    maximum = max(durations)
    if maximum == minimum:
        return (DurationHistogramBin(minimum, maximum, len(durations)),)

    width = (maximum - minimum) / bins
    counts = [0] * bins
    for duration in durations:
        index = min(int((duration - minimum) / width), bins - 1)
        counts[index] += 1

    result: list[DurationHistogramBin] = []
    for index, count in enumerate(counts):
        lower = minimum + width * index
        upper = maximum if index == bins - 1 else minimum + width * (index + 1)
        result.append(DurationHistogramBin(lower, upper, count))
    return tuple(result)


def _label_display_name(label_id: int, metadata: dict[str, Any]) -> str:
    for key in ("display_name", "zh", "en", "name"):
        value = metadata.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    for value in metadata.values():
        if isinstance(value, str) and value.strip():
            return value.strip()
    return str(label_id)


def profile_manifest_audio(
    manifest: DatasetManifest | Path | str,
    *,
    split: str | None = None,
    fail_fast: bool = False,
    histogram_bins: int = 10,
    event_callback: EventCallback | None = None,
    cancellation: CancellationCheck | None = None,
) -> DatasetAudioProfile:
    """使用音频 header 统计时长、分位数、采样率、声道和损坏/缺失文件。"""
    if histogram_bins < 1:
        raise ValueError("histogram_bins 必须 >= 1")
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
    sorted_durations = sorted(durations)
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
        median_duration_seconds=_percentile(sorted_durations, 0.50),
        p90_duration_seconds=_percentile(sorted_durations, 0.90),
        p95_duration_seconds=_percentile(sorted_durations, 0.95),
        p99_duration_seconds=_percentile(sorted_durations, 0.99),
        duration_histogram=_duration_histogram(durations, bins=histogram_bins),
    )


def summarize_manifest(
    manifest: DatasetManifest | Path | str,
    *,
    include_audio_profile: bool = False,
    fail_fast: bool = False,
    event_callback: EventCallback | None = None,
    cancellation: CancellationCheck | None = None,
) -> DatasetSummary:
    """构建稳定、JSON-safe 的轻量数据集摘要。

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


def profile_dataset(
    manifest: DatasetManifest | Path | str,
    *,
    include_audio: bool = False,
    fail_fast: bool = False,
    histogram_bins: int = 10,
    event_callback: EventCallback | None = None,
    cancellation: CancellationCheck | None = None,
) -> DatasetProfile:
    """构建数据集分析页所需的详细 profile。

    manifest 扫描提供 split×label、speaker 和缺失字段统计；``include_audio=True``
    时额外进行 header profiling，并附带时长分位数与 histogram。不会解码完整波形。
    """
    if histogram_bins < 1:
        raise ValueError("histogram_bins 必须 >= 1")
    dataset = (
        manifest
        if isinstance(manifest, DatasetManifest)
        else DatasetManifest.load(manifest)
    )

    split_counts = {name: 0 for name in dataset.meta.splits}
    label_counts = {str(label_id): 0 for label_id in sorted(dataset.meta.labels)}
    split_labels: dict[str, dict[str, int]] = {
        split: {str(label_id): 0 for label_id in sorted(dataset.meta.labels)}
        for split in dataset.meta.splits
    }
    speaker_counts: dict[str, int] = {}
    observed_labels: set[int] = set()
    unlabeled_records = 0
    records_without_speaker = 0
    total_records = len(dataset.records)
    progress_interval = max(total_records // 100, 1)

    for index, record in enumerate(dataset.records, start=1):
        if cancellation is not None:
            cancellation.raise_if_cancelled()
        split = dataset.record_splits.get(record.uid, "unassigned")
        split_counts[split] = split_counts.get(split, 0) + 1
        split_counts_for_label = split_labels.setdefault(split, {})

        if record.label is None:
            label_key = "unlabeled"
            unlabeled_records += 1
        else:
            observed_labels.add(record.label)
            label_key = str(record.label)
        label_counts[label_key] = label_counts.get(label_key, 0) + 1
        split_counts_for_label[label_key] = split_counts_for_label.get(label_key, 0) + 1

        if record.speaker_id is None:
            records_without_speaker += 1
        else:
            speaker_counts[record.speaker_id] = speaker_counts.get(record.speaker_id, 0) + 1

        if event_callback is not None and (
            index % progress_interval == 0 or index == total_records
        ):
            event_callback(
                ProgressEvent(
                    stage="dataset_manifest_profile",
                    completed=index,
                    total=total_records,
                )
            )

    all_label_keys = set(label_counts)
    for counts in split_labels.values():
        for key in all_label_keys:
            counts.setdefault(key, 0)

    label_display_names = {
        str(label_id): _label_display_name(label_id, metadata)
        for label_id, metadata in sorted(dataset.meta.labels.items())
    }
    for label_id in sorted(observed_labels):
        label_display_names.setdefault(str(label_id), str(label_id))
    if unlabeled_records:
        label_display_names["unlabeled"] = "unlabeled"

    audio_profile: DatasetAudioProfile | None = None
    if include_audio:
        audio_profile = profile_manifest_audio(
            dataset,
            fail_fast=fail_fast,
            histogram_bins=histogram_bins,
            event_callback=event_callback,
            cancellation=cancellation,
        )

    ordered_speakers = dict(
        sorted(speaker_counts.items(), key=lambda item: (-item[1], item[0].casefold()))
    )
    ordered_split_labels = {
        split: dict(sorted(counts.items()))
        for split, counts in sorted(split_labels.items())
    }
    num_classes = dataset.meta.num_classes or len(observed_labels) or None
    return DatasetProfile(
        dataset_id=dataset.meta.dataset_id,
        name=dataset.meta.dataset_id,
        total_records=total_records,
        num_classes=num_classes,
        num_speakers=len(speaker_counts),
        unlabeled_records=unlabeled_records,
        records_without_speaker=records_without_speaker,
        splits=dict(sorted(split_counts.items())),
        labels=dict(sorted(label_counts.items())),
        label_display_names=dict(sorted(label_display_names.items())),
        split_labels=ordered_split_labels,
        speaker_counts=ordered_speakers,
        audio_profile=audio_profile,
    )


__all__ = [
    "AudioProbeFailure",
    "DurationHistogramBin",
    "DatasetAudioProfile",
    "DatasetSummary",
    "DatasetProfile",
    "profile_manifest_audio",
    "summarize_manifest",
    "profile_dataset",
]
