"""标准 Dataset 记录过滤 iterator。"""

from __future__ import annotations

import json
from collections.abc import Iterator, Mapping
from pathlib import Path
from typing import Any

from ser_lib.data.manifest import DatasetManifest
from ser_lib.data.types import AudioRecord


def iter_records(
    manifest: DatasetManifest | Path | str,
    *,
    split: str | None = None,
    label_id: int | None = None,
    speaker_id: str | None = None,
    keyword: str | None = None,
) -> Iterator[AudioRecord]:
    """按 manifest 原始顺序惰性产出满足条件的 ``AudioRecord``。

    ``keyword`` 为大小写不敏感的包含查询，覆盖 uid、音频路径、speaker_id
    与 metadata。函数不计算命中总数，也不提供分页 DTO；需要分页时由调用方
    使用 ``itertools.islice`` 等 iterator 工具自行切片。
    """
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
        yield record


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


__all__ = ["iter_records"]
