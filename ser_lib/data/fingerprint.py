"""标准 manifest 的轻量数据版本指纹。"""

from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from ser_lib.data.manifest import DatasetManifest
from ser_lib.foundation.events import CancellationCheck, EventCallback, ProgressEvent

_CHUNK_SIZE = 1024 * 1024


@dataclass(frozen=True, slots=True)
class DatasetFingerprint:
    """由 dataset.yaml 与 split manifests 生成的稳定内容指纹。"""

    dataset_id: str
    algorithm: str
    digest: str
    files: dict[str, str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def fingerprint_manifest(
    manifest: DatasetManifest | Path | str,
    *,
    event_callback: EventCallback | None = None,
    cancellation: CancellationCheck | None = None,
) -> DatasetFingerprint:
    """计算 dataset.yaml + 所有声明 split 文件的 SHA256 指纹。

    音频文件本体不会参与 hash，因此该操作适合频繁用于缓存键、运行记录和
    Artifact 元数据。combined digest 同时包含逻辑文件名与各文件 digest，避免
    split 内容互换时得到相同结果。
    """
    dataset = (
        manifest
        if isinstance(manifest, DatasetManifest)
        else DatasetManifest.load(manifest)
    )
    sources = [("dataset.yaml", dataset.meta.yaml_path)]
    sources.extend(
        (f"split:{split}", path)
        for split, path in sorted(dataset.meta.splits.items())
    )

    file_digests: dict[str, str] = {}
    combined = hashlib.sha256()
    total = len(sources)
    for index, (logical_name, path) in enumerate(sources, start=1):
        if cancellation is not None:
            cancellation.raise_if_cancelled()
        digest = _sha256_file(path, cancellation=cancellation)
        file_digests[logical_name] = digest
        combined.update(logical_name.encode("utf-8"))
        combined.update(b"\0")
        combined.update(digest.encode("ascii"))
        combined.update(b"\n")
        if event_callback is not None:
            event_callback(
                ProgressEvent(
                    stage="dataset_fingerprint",
                    completed=index,
                    total=total,
                    details={"file": logical_name},
                )
            )

    return DatasetFingerprint(
        dataset_id=dataset.meta.dataset_id,
        algorithm="sha256",
        digest=combined.hexdigest(),
        files=file_digests,
    )


def _sha256_file(
    path: Path,
    *,
    cancellation: CancellationCheck | None = None,
) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as file_obj:
        while chunk := file_obj.read(_CHUNK_SIZE):
            if cancellation is not None:
                cancellation.raise_if_cancelled()
            hasher.update(chunk)
    return hasher.hexdigest()


__all__ = ["DatasetFingerprint", "fingerprint_manifest"]