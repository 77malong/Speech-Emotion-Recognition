"""无需加载/Hash 权重的本地 Artifact Catalog 扫描。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ser_lib.artifacts.loader import inspect_model_artifact
from ser_lib.artifacts.manifest import ModelArtifactManifest
from ser_lib.core._catalog_scan import scan_catalog_candidates
from ser_lib.core.events import CancellationCheck, EventCallback


@dataclass(frozen=True, slots=True)
class ArtifactInfo:
    """模型管理列表所需的轻量、JSON-safe Artifact 信息。"""

    artifact_id: str
    directory: str
    model_name: str
    schema_version: int
    library_version: str
    weights_format: str
    weights_file: str
    weights_bytes: int
    total_bytes: int
    num_classes: int
    labels: dict[int, str]
    metrics: dict[str, float]
    dataset_id: str | None
    dataset_fingerprint: str | None
    source_run_id: str | None
    created_at: str | None
    parameter_count: int | None
    metadata: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "artifact_id": self.artifact_id,
            "directory": self.directory,
            "model_name": self.model_name,
            "schema_version": self.schema_version,
            "library_version": self.library_version,
            "weights_format": self.weights_format,
            "weights_file": self.weights_file,
            "weights_bytes": self.weights_bytes,
            "total_bytes": self.total_bytes,
            "num_classes": self.num_classes,
            "labels": dict(self.labels),
            "metrics": dict(self.metrics),
            "dataset_id": self.dataset_id,
            "dataset_fingerprint": self.dataset_fingerprint,
            "source_run_id": self.source_run_id,
            "created_at": self.created_at,
            "parameter_count": self.parameter_count,
            "metadata": dict(self.metadata),
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
    artifacts: tuple[ArtifactInfo, ...]
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


def _optional_str(value: Any) -> str | None:
    return value if isinstance(value, str) and value else None


def _optional_nonnegative_int(value: Any) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else None


def _artifact_info(directory: Path, manifest: ModelArtifactManifest) -> ArtifactInfo:
    metadata = dict(manifest.metadata)
    artifact_id = _optional_str(metadata.get("artifact_id")) or directory.name
    dataset_id = _optional_str(metadata.get("dataset_id"))
    if dataset_id is None:
        dataset_id = _optional_str(manifest.preprocessing.get("dataset_id"))

    declared_files = (
        set(manifest.files_sha256)
        if manifest.schema_version >= 2
        else {manifest.weights_file}
    )
    declared_files.add(manifest.weights_file)
    total_bytes = (directory / "manifest.json").stat().st_size
    for name in declared_files:
        total_bytes += (directory / name).stat().st_size

    weights_path = directory / manifest.weights_file
    return ArtifactInfo(
        artifact_id=artifact_id,
        directory=directory.as_posix(),
        model_name=manifest.model_name,
        schema_version=manifest.schema_version,
        library_version=manifest.library_version,
        weights_format=manifest.weights_format,
        weights_file=manifest.weights_file,
        weights_bytes=weights_path.stat().st_size,
        total_bytes=total_bytes,
        num_classes=len(manifest.labels),
        labels=dict(manifest.labels),
        metrics=dict(manifest.metrics),
        dataset_id=dataset_id,
        dataset_fingerprint=_optional_str(metadata.get("dataset_fingerprint")),
        source_run_id=(
            _optional_str(metadata.get("source_run_id"))
            or _optional_str(metadata.get("run_id"))
        ),
        created_at=_optional_str(metadata.get("created_at")),
        parameter_count=_optional_nonnegative_int(metadata.get("parameter_count")),
        metadata=metadata,
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
    """扫描 Artifact 根目录；只调用轻量 inspect，绝不计算文件 SHA256。"""
    root_path = Path(root)
    if not root_path.is_dir():
        raise NotADirectoryError(f"Artifact Catalog 根目录不存在或不是目录: {root_path}")
    candidates = _candidate_directories(root_path, recursive=recursive)

    def inspect_candidate(directory: Path) -> ArtifactInfo:
        manifest = inspect_model_artifact(directory)
        return _artifact_info(directory, manifest)

    artifacts, failures = scan_catalog_candidates(
        candidates,
        inspect_candidate=inspect_candidate,
        failure_factory=lambda directory, exc: ArtifactScanFailure(
            directory=directory.as_posix(),
            error_type=type(exc).__name__,
            message=str(exc),
        ),
        stage="artifact_catalog_scan",
        candidate_detail_key="directory",
        fail_fast=fail_fast,
        event_callback=event_callback,
        cancellation=cancellation,
    )
    artifacts.sort(
        key=lambda item: (item.model_name.casefold(), item.artifact_id.casefold())
    )
    return ArtifactCatalog(
        root=root_path.as_posix(),
        artifacts=tuple(artifacts),
        failures=tuple(failures),
    )


__all__ = [
    "ArtifactInfo",
    "ArtifactScanFailure",
    "ArtifactCatalog",
    "scan_model_artifacts",
]
