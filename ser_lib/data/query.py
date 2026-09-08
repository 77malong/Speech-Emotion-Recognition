"""面向数据浏览器的稳定查询与分页 DTO。"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from ser_lib.data.manifest import DatasetManifest
from ser_lib.data.types import AudioRecord


@dataclass(frozen=True, slots=True)
class RecordView:
    """不泄漏内部 ``AudioRecord`` 的 JSON-safe 浏览视图。"""

    uid: str
    audio_path: str
    split: str
    label_id: int | None
    speaker_id: str | None
    start_ms: int | None
    end_ms: int | None
    sample_rate_hint: int | None
    metadata: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class RecordPage:
    items: tuple[RecordView, ...]
    total: int
    offset: int
    limit: int

    @property
    def has_more(self) -> bool:
        return self.offset + len(self.items) < self.total

    def to_dict(self) -> dict[str, Any]:
        return {
            "items": [item.to_dict() for item in self.items],
            "total": self.total,
            "offset": self.offset,
            "limit": self.limit,
            "has_more": self.has_more,
        }


def query_records(
    manifest: DatasetManifest | Path | str,
    *,
    split: str | None = None,
    label_id: int | None = None,
    speaker_id: str | None = None,
    keyword: str | None = None,
    offset: int = 0,
    limit: int = 50,
) -> RecordPage:
    """过滤标准 manifest 并返回稳定分页结果。

    结果顺序始终保持 manifest 原始顺序。``keyword`` 为大小写不敏感的包含查询，
    覆盖 uid、音频路径、speaker_id 与 metadata。扫描时间为 O(N)，额外分页内存
    仅为 O(limit)，不会为所有命中记录提前构建 DTO。
    """
    if offset < 0:
        raise ValueError(f"offset 必须 >= 0，实际: {offset}")
    if limit <= 0:
        raise ValueError(f"limit 必须 > 0，实际: {limit}")
    if split is not None and not split:
        raise ValueError("split 不能是空字符串")
    if speaker_id is not None and not speaker_id:
        raise ValueError("speaker_id 不能是空字符串")

    dataset = (
        manifest
        if isinstance(manifest, DatasetManifest)
        else DatasetManifest.load(manifest)
    )
    normalized_keyword = keyword.strip().casefold() if keyword is not None else None
    if normalized_keyword == "":
        normalized_keyword = None

    items: list[RecordView] = []
    total = 0
    for record in dataset.records:
        record_split = dataset.record_splits.get(record.uid, "unassigned")
        if split is not None and record_split != split:
            continue
        if label_id is not None and record.label != label_id:
            continue
        if speaker_id is not None and record.speaker_id != speaker_id:
            continue
        if normalized_keyword is not None and not _matches_keyword(
            record, normalized_keyword
        ):
            continue

        if total >= offset and len(items) < limit:
            items.append(_to_view(record, record_split))
        total += 1

    return RecordPage(
        items=tuple(items),
        total=total,
        offset=offset,
        limit=limit,
    )


def _to_view(record: AudioRecord, split: str) -> RecordView:
    return RecordView(
        uid=record.uid,
        audio_path=record.audio_path.as_posix(),
        split=split,
        label_id=record.label,
        speaker_id=record.speaker_id,
        start_ms=record.start_ms,
        end_ms=record.end_ms,
        sample_rate_hint=record.sample_rate_hint,
        metadata=_json_safe_mapping(record.metadata),
    )


def _matches_keyword(record: AudioRecord, keyword: str) -> bool:
    metadata = _json_safe_mapping(record.metadata)
    haystack = "\n".join(
        (
            record.uid,
            record.audio_path.as_posix(),
            record.speaker_id or "",
            json.dumps(metadata, ensure_ascii=False, sort_keys=True),
        )
    ).casefold()
    return keyword in haystack


def _json_safe_mapping(value: Mapping[str, Any]) -> dict[str, Any]:
    return {str(key): _json_safe(item) for key, item in value.items()}


def _json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Path):
        return value.as_posix()
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [_json_safe(item) for item in value]
    raise TypeError(
        "AudioRecord.metadata 包含不可 JSON 序列化的类型: "
        f"{type(value).__name__}"
    )


__all__ = ["RecordPage", "RecordView", "query_records"]
