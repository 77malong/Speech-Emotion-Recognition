"""无需加载/Hash 权重的本地 Artifact Catalog 扫描。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ser_lib.artifacts.loader import inspect_model_artifact
from ser_lib.artifacts.manifest import ModelArtifactManifest
from ser_lib.foundation.events import CancellationCheck, EventCallback, ProgressEvent


@dataclass(frozen=True, slots=True)
class ArtifactEntry:
    """Artifact 扫描的最小资源条目；manifest 保持领域原始结构。"""

    path: str
    manifest: ModelArtifactManifest
    weights_bytes: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "manifest": self.manifest.model_dump(mode="json"),
            "weights_bytes": self.weights_bytes,
        }


@dataclass(frozen=True, slots=True)
class ArtifactScanFailure:
    directory: str
    error_type: str
    message: str

    def to_dict(self) -> dict[str, str]:
        return {
            "directory": self.directory,
            "error_type": self.error_type,
            "message": self.message,
        }


@dataclass(frozen=True, slots=True)
class ArtifactCatalog:
    root: str
    artifacts: tuple[ArtifactEntry, ...]
    failures: tuple[ArtifactScanFailure, ...]

    @property
    def total(self) -> int:
        return len(self.artifacts) + len(self.failures)

    def to_dict(self) -> dict[str, Any]:
        return {
            "root": self.root,
            "total": self.total,
            "artifacts": [artifact.to_dict() for artifact in self.artifacts],
            "failures": [failure.to_dict() for failure in self.failures],
        }


def _artifact_entry(directory: Path, manifest: ModelArtifactManifest) -> ArtifactEntry:
    weights_path = directory / manifest.weights_file
    return ArtifactEntry(
        path=directory.as_posix(),
        manifest=manifest,
        weights_bytes=weights_path.stat().st_size,
    )


def _candidate_directories(root: Path, *, recursive: bool) -> list[Path]:
    candidates: set[Path] = set()
    if (root / "manifest.json").is_file():
        candidates.add(root)
    if recursive:
        for manifest_path in root.rglob("manifest.json"):
            directory = manifest_path.parent
            if directory.name.startswith(".") and ".tmp-" in directory.name:
                continue
            candidates.add(directory)
    else:
        candidates.update(
            child
            for child in root.iterdir()
            if child.is_dir() and (child / "manifest.json").is_file()
        )
    return sorted(candidates, key=lambda path: path.as_posix().casefold())


def scan_model_artifacts(
    root: Path | str,
    *,
    recursive: bool = False,
    fail_fast: bool = False,
    event_callback: EventCallback | None = None,
    cancellation: CancellationCheck | None = None,
) -> ArtifactCatalog:
    """扫描 Artifact 根目录；只调用轻量 inspect/stat，绝不计算文件 SHA256。"""
    root_path = Path(root)
    if not root_path.is_dir():
        raise NotADirectoryError(f"Artifact Catalog 根目录不存在或不是目录: {root_path}")
    candidates = _candidate_directories(root_path, recursive=recursive)
    artifacts: list[ArtifactEntry] = []
    failures: list[ArtifactScanFailure] = []
    total = len(candidates)

    for index, directory in enumerate(candidates, start=1):
        if cancellation is not None:
            cancellation.raise_if_cancelled()
        try:
            manifest = inspect_model_artifact(directory)
            artifacts.append(_artifact_entry(directory, manifest))
        except Exception as exc:
            if fail_fast:
                raise
            failures.append(
                ArtifactScanFailure(
                    directory=directory.as_posix(),
                    error_type=type(exc).__name__,
                    message=str(exc),
                )
            )
        if event_callback is not None:
            event_callback(
                ProgressEvent(
                    stage="artifact_catalog_scan",
                    completed=index,
                    total=total,
                    details={
                        "valid": len(artifacts),
                        "failed": len(failures),
                        "directory": directory,
                    },
                )
            )

    artifacts.sort(
        key=lambda item: (
            item.manifest.model_name.casefold(),
            item.path.casefold(),
        )
    )
    return ArtifactCatalog(
        root=root_path.as_posix(),
        artifacts=tuple(artifacts),
        failures=tuple(failures),
    )


__all__ = [
    "ArtifactEntry",
    "ArtifactScanFailure",
    "ArtifactCatalog",
    "scan_model_artifacts",
]
