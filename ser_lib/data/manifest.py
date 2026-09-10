"""标准 Manifest：JSONL 记录 + dataset.yaml 元信息（设计文档 §6）。

路径解析规则（确定且可复现，不依赖 cwd）：

- manifest 内部音频相对路径相对于 ``dataset.yaml`` 声明的 ``root`` 解析；
- ``dataset.yaml`` 的 ``root`` 与 splits 文件名相对于 ``dataset.yaml`` 所在目录解析；
- 数据集根目录内部尽量保存相对路径，外部引用保存规范化绝对路径。
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator, Mapping

import yaml

from ser_lib.data.errors import ManifestError
from ser_lib.data.migrations import migrate_data_payload
from ser_lib.data.types import AudioRecord
from ser_lib.foundation.errors import SchemaMigrationError

logger = logging.getLogger(__name__)

MANIFEST_SCHEMA_VERSION = 1


@dataclass(frozen=True)
class ManifestMeta:
    """dataset.yaml 元信息。"""

    dataset_id: str
    root: Path
    yaml_path: Path
    splits: dict[str, Path] = field(default_factory=dict)
    labels: dict[int, dict[str, Any]] = field(default_factory=dict)
    schema_version: int = MANIFEST_SCHEMA_VERSION

    @property
    def num_classes(self) -> int:
        return len(self.labels)


def parse_record(
    raw: Mapping[str, Any],
    *,
    source: Path,
    line_number: int | None = None,
) -> AudioRecord:
    """解析并校验一条标准 manifest 记录。"""
    where = f"{source.name}" + (f":{line_number}" if line_number is not None else "")
    uid = raw.get("uid")
    if not isinstance(uid, str) or not uid:
        raise ManifestError(f"记录缺少合法的 uid 字段 ({where})")
    audio_path = raw.get("audio_path")
    if not isinstance(audio_path, str) or not audio_path:
        raise ManifestError(
            f"记录 {uid} 缺少合法的 audio_path 字段 ({where})", uid=uid
        )
    label = raw.get("label")
    if (label is not None and not isinstance(label, int)) or isinstance(label, bool):
        raise ManifestError(
            f"记录 {uid} 的 label 必须是 int 或 null，实际: {label!r} ({where})", uid=uid
        )
    start_ms = raw.get("start_ms")
    end_ms = raw.get("end_ms")
    if start_ms is not None:
        if not isinstance(start_ms, int) or isinstance(start_ms, bool) or start_ms < 0:
            raise ManifestError(
                f"记录 {uid} 的 start_ms 必须是 >= 0 的整数，实际: {start_ms!r} ({where})",
                uid=uid,
            )
    if end_ms is not None:
        if not isinstance(end_ms, int) or isinstance(end_ms, bool):
            raise ManifestError(
                f"记录 {uid} 的 end_ms 必须是整数，实际: {end_ms!r} ({where})", uid=uid
            )
    try:
        return AudioRecord(
            uid=uid,
            audio_path=Path(audio_path),
            label=label,
            start_ms=start_ms,
            end_ms=end_ms,
            speaker_id=raw.get("speaker_id"),
            sample_rate_hint=raw.get("sample_rate_hint"),
            metadata=dict(raw.get("metadata") or {}),
        )
    except ValueError as exc:
        raise ManifestError(str(exc), uid=uid) from exc


def write_jsonl(records: list[AudioRecord], path: Path) -> None:
    """把记录写入标准 JSONL（音频路径保留为给定形式）。"""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    try:
        with open(tmp, "w", encoding="utf-8", newline="\n") as f:
            for record in records:
                entry: dict[str, Any] = {"uid": record.uid, "audio_path": str(record.audio_path)}
                if record.label is not None:
                    entry["label"] = record.label
                if record.start_ms is not None:
                    entry["start_ms"] = record.start_ms
                if record.end_ms is not None:
                    entry["end_ms"] = record.end_ms
                if record.speaker_id is not None:
                    entry["speaker_id"] = record.speaker_id
                if record.sample_rate_hint is not None:
                    entry["sample_rate_hint"] = record.sample_rate_hint
                if record.metadata:
                    entry["metadata"] = dict(record.metadata)
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        tmp.replace(path)
    except OSError as exc:
        raise ManifestError(f"写入 manifest 失败: {path}", path=path) from exc


def read_jsonl(path: Path) -> list[AudioRecord]:
    """读取标准 JSONL manifest。文件内 uid 必须唯一。"""
    path = Path(path)
    if not path.exists():
        raise ManifestError(f"manifest 文件不存在: {path}", path=path)
    records: list[AudioRecord] = []
    seen: dict[str, int] = {}
    with open(path, "r", encoding="utf-8") as f:
        for line_number, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                raw = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ManifestError(
                    f"JSONL 解析失败 ({path.name}:{line_number}): {exc}", path=path
                ) from exc
            record = parse_record(raw, source=path, line_number=line_number)
            if record.uid in seen:
                raise ManifestError(
                    f"UID 重复: '{record.uid}' 出现于第 {seen[record.uid]} 行和第 "
                    f"{line_number} 行 ({path})",
                    path=path,
                    uid=record.uid,
                )
            seen[record.uid] = line_number
            records.append(record)
    return records


def load_meta(yaml_path: Path) -> ManifestMeta:
    """加载、read-time migrate 并校验 dataset.yaml。"""
    yaml_path = Path(yaml_path)
    if not yaml_path.exists():
        raise ManifestError(f"dataset.yaml 不存在: {yaml_path}", path=yaml_path)
    try:
        with open(yaml_path, "r", encoding="utf-8") as f:
            raw = yaml.safe_load(f)
    except yaml.YAMLError as exc:
        raise ManifestError(f"dataset.yaml 解析失败: {yaml_path}: {exc}", path=yaml_path) from exc
    if not isinstance(raw, dict):
        raise ManifestError(f"dataset.yaml 必须是映射: {yaml_path}", path=yaml_path)

    payload = dict(raw)
    payload.setdefault("schema_version", MANIFEST_SCHEMA_VERSION)
    try:
        payload = migrate_data_payload(
            "dataset_manifest",
            payload,
            target_version=MANIFEST_SCHEMA_VERSION,
        )
    except SchemaMigrationError as exc:
        raise ManifestError(str(exc), path=yaml_path) from exc

    schema_version = payload["schema_version"]
    dataset_id = payload.get("dataset_id")
    if not dataset_id:
        raise ManifestError(f"dataset.yaml 缺少 dataset_id: {yaml_path}", path=yaml_path)

    root_raw = payload.get("root")
    root = Path(str(root_raw)) if root_raw else yaml_path.parent
    if not root.is_absolute():
        root = (yaml_path.parent / root).resolve()
    else:
        root = root.resolve()

    splits: dict[str, Path] = {}
    for split_name, split_file in (payload.get("splits") or {}).items():
        split_path = Path(str(split_file))
        if not split_path.is_absolute():
            split_path = yaml_path.parent / split_path
        splits[str(split_name)] = split_path.resolve()

    labels: dict[int, dict[str, Any]] = {}
    for key, value in (payload.get("labels") or {}).items():
        try:
            label_id = int(key)
        except (TypeError, ValueError) as exc:
            raise ManifestError(
                f"dataset.yaml labels 的 key 必须是整数: {key!r}", path=yaml_path
            ) from exc
        labels[label_id] = dict(value or {})

    return ManifestMeta(
        dataset_id=str(dataset_id),
        root=root,
        yaml_path=yaml_path.resolve(),
        splits=splits,
        labels=labels,
        schema_version=schema_version,
    )


def _resolved_audio_path(meta: ManifestMeta, record: AudioRecord) -> Path:
    if record.audio_path.is_absolute():
        return record.audio_path.resolve()
    return (meta.root / record.audio_path).resolve()


def _validate_cross_split_audio_overlap(
    records: list[AudioRecord],
    record_splits: Mapping[str, str],
    meta: ManifestMeta,
) -> None:
    """拒绝同一音频在不同 split 中出现重叠区间。

    这是与具体 split 策略无关的最小泄漏门禁。speaker overlap 是否非法取决于
    speaker-independent 等显式策略，因此不在这里做无条件判断。
    """
    by_audio: dict[Path, list[tuple[int, float, str, str]]] = {}
    for record in records:
        split = record_splits.get(record.uid)
        if split is None:
            continue
        start = record.start_ms if record.start_ms is not None else 0
        end = float(record.end_ms) if record.end_ms is not None else float("inf")
        by_audio.setdefault(_resolved_audio_path(meta, record), []).append(
            (start, end, split, record.uid)
        )

    for audio_path, intervals in by_audio.items():
        intervals.sort(key=lambda item: (item[0], item[1]))
        furthest_by_split: dict[str, tuple[float, str]] = {}
        for start, end, split, uid in intervals:
            for other_split, (other_end, other_uid) in furthest_by_split.items():
                if other_split != split and other_end > start:
                    raise ManifestError(
                        "音频片段跨 split 重叠: "
                        f"'{other_uid}' ({other_split}) 与 '{uid}' ({split}) "
                        f"引用同一音频 {audio_path}",
                        uid=uid,
                        path=meta.yaml_path,
                    )
            previous = furthest_by_split.get(split)
            if previous is None or end > previous[0]:
                furthest_by_split[split] = (end, uid)


class DatasetManifest:
    """标准数据集 manifest：迭代记录、按 split 获取、轻量统计。"""

    def __init__(
        self,
        meta: ManifestMeta,
        records: list[AudioRecord],
        record_splits: dict[str, str] | None = None,
    ) -> None:
        self.meta = meta
        self.records = records
        self.record_splits = record_splits or {}

    @classmethod
    def load(cls, yaml_path: Path | str) -> "DatasetManifest":
        """加载 dataset.yaml 及其全部 splits，并拒绝无歧义的跨 split 音频泄漏。"""
        yaml_path = Path(yaml_path)
        meta = load_meta(yaml_path)
        records: list[AudioRecord] = []
        record_splits: dict[str, str] = {}
        for split_name, split_path in meta.splits.items():
            for record in read_jsonl(split_path):
                if record.uid in record_splits:
                    raise ManifestError(
                        f"UID 跨 split 重复: '{record.uid}' 同时出现在 "
                        f"'{record_splits[record.uid]}' 与 '{split_name}'",
                        uid=record.uid,
                        path=yaml_path,
                    )
                records.append(record)
                record_splits[record.uid] = split_name
        _validate_label_range(records, meta, yaml_path)
        _validate_cross_split_audio_overlap(records, record_splits, meta)
        return cls(meta, records, record_splits)

    def resolve_audio_path(self, record: AudioRecord) -> Path:
        return _resolved_audio_path(self.meta, record)

    def iter_records(self, split: str | None = None) -> Iterator[AudioRecord]:
        for record in self.records:
            if split is None or self.record_splits.get(record.uid) == split:
                yield record

    def get_records(self, split: str | None = None) -> list[AudioRecord]:
        return list(self.iter_records(split))

    def resolved_records(self, split: str | None = None) -> list[AudioRecord]:
        resolved = []
        for record in self.iter_records(split):
            resolved.append(
                AudioRecord(
                    uid=record.uid,
                    audio_path=self.resolve_audio_path(record),
                    label=record.label,
                    start_ms=record.start_ms,
                    end_ms=record.end_ms,
                    speaker_id=record.speaker_id,
                    sample_rate_hint=record.sample_rate_hint,
                    metadata=dict(record.metadata),
                )
            )
        return resolved

    def stats(self) -> dict[str, Any]:
        split_counts: dict[str, int] = {}
        label_counts: dict[str, int] = {}
        for record in self.records:
            split = self.record_splits.get(record.uid, "unassigned")
            split_counts[split] = split_counts.get(split, 0) + 1
            label_key = "unlabeled" if record.label is None else str(record.label)
            label_counts[label_key] = label_counts.get(label_key, 0) + 1
        return {
            "dataset_id": self.meta.dataset_id,
            "total": len(self.records),
            "splits": split_counts,
            "labels": label_counts,
            "num_classes": self.meta.num_classes or None,
        }

    def write(self, yaml_path: Path | None = None) -> None:
        yaml_path = Path(yaml_path or self.meta.yaml_path)
        meta = self.meta
        by_split: dict[str, list[AudioRecord]] = {}
        unassigned: list[AudioRecord] = []
        for record in self.records:
            split = self.record_splits.get(record.uid)
            if split is None:
                unassigned.append(record)
            else:
                by_split.setdefault(split, []).append(record)

        splits_section: dict[str, str] = {}
        for split_name, records in by_split.items():
            split_file = meta.splits.get(split_name)
            file_name = split_file.name if split_file else f"{split_name}.jsonl"
            write_jsonl(records, yaml_path.parent / file_name)
            splits_section[split_name] = file_name
        if unassigned:
            write_jsonl(unassigned, yaml_path.parent / "unassigned.jsonl")
            splits_section["unassigned"] = "unassigned.jsonl"

        doc: dict[str, Any] = {
            "schema_version": meta.schema_version,
            "dataset_id": meta.dataset_id,
            "root": str(meta.root),
            "splits": splits_section,
        }
        if meta.labels:
            doc["labels"] = {str(k): v for k, v in sorted(meta.labels.items())}
        tmp = yaml_path.with_suffix(yaml_path.suffix + ".tmp")
        with open(tmp, "w", encoding="utf-8", newline="\n") as f:
            yaml.safe_dump(doc, f, allow_unicode=True, sort_keys=False)
        tmp.replace(yaml_path)


def _validate_label_range(
    records: list[AudioRecord],
    meta: ManifestMeta,
    yaml_path: Path,
) -> None:
    if not meta.labels:
        return
    valid = set(meta.labels)
    for record in records:
        if record.label is not None and record.label not in valid:
            raise ManifestError(
                f"记录 {record.uid} 的 label={record.label} 超出 labels 表范围 "
                f"{sorted(valid)} ({yaml_path})",
                uid=record.uid,
                path=yaml_path,
            )
