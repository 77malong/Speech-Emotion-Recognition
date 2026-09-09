"""快速检查、完整校验并加载模型 artifact。"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import torch
from safetensors.torch import load_file

from ser_lib._version import __version__
from ser_lib.artifacts.manifest import ModelArtifactManifest
from ser_lib.artifacts.migrations import validate_artifact_manifest_version
from ser_lib.foundation.events import (
    CancellationCheck,
    EventCallback,
    EventContext,
    LifecycleEvent,
    ProgressEvent,
)
from ser_lib.foundation.errors import OperationCancelled
from ser_lib.data.audio import AudioLoader
from ser_lib.data.collate import SERCollator, build_collator
from ser_lib.data.config import DataConfig
from ser_lib.data.pipeline import SamplePipeline, build_components
from ser_lib.data.validation import validate_compatibility
from ser_lib.models.base import SERModel
from ser_lib.models.registry import model_registry


@dataclass(frozen=True, slots=True)
class LoadedArtifact:
    manifest: ModelArtifactManifest
    model: SERModel
    audio_loader: AudioLoader
    pipeline: SamplePipeline
    collator: SERCollator


def _sha256(path: Path) -> str:
    """兼容旧内部测试/调用的无观察 SHA256 helper。"""
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sha256_with_progress(
    path: Path,
    *,
    cancellation: CancellationCheck | None = None,
    on_chunk: Callable[[int], None] | None = None,
) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while True:
            if cancellation is not None:
                cancellation.raise_if_cancelled()
            chunk = source.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
            if on_chunk is not None:
                on_chunk(len(chunk))
    if cancellation is not None:
        cancellation.raise_if_cancelled()
    return digest.hexdigest()


def _major(version: str) -> int:
    try:
        return int(version.split(".", 1)[0])
    except (TypeError, ValueError) as exc:
        raise ValueError(f"artifact library_version 非法: {version!r}") from exc


def _safe_component_path(source: Path, name: str) -> Path:
    candidate = source / name
    if candidate.parent.resolve() != source.resolve():
        raise ValueError(f"artifact 文件名越出根目录: {name!r}")
    return candidate


def _read_manifest(source: Path) -> ModelArtifactManifest:
    manifest_path = source / "manifest.json"
    if not manifest_path.is_file():
        raise FileNotFoundError(f"artifact manifest 不存在: {manifest_path}")
    try:
        raw = json.loads(manifest_path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError("artifact manifest 顶层必须是映射")
        raw.setdefault("schema_version", 1)
        validate_artifact_manifest_version(raw, supported_versions=(1, 2))
        return ModelArtifactManifest.model_validate(raw)
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        raise ValueError(
            f"artifact manifest 无法读取或校验失败: {manifest_path}"
        ) from exc


def _validate_manifest_compatibility(manifest: ModelArtifactManifest) -> None:
    if (
        manifest.schema_version >= 2
        and _major(manifest.library_version) != _major(__version__)
    ):
        raise ValueError(
            f"artifact 需要 ser_lib {manifest.library_version}，"
            f"当前版本 {__version__} 不兼容"
        )


def _validate_external_metadata(source: Path, manifest: ModelArtifactManifest) -> None:
    if manifest.schema_version < 2:
        return
    expected = {
        "data_config.json": manifest.preprocessing,
        "model_config.json": manifest.model_params,
        "labels.json": {str(key): value for key, value in manifest.labels.items()},
        "metrics.json": manifest.metrics,
    }
    for name, embedded in expected.items():
        path = _safe_component_path(source, name)
        try:
            actual = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            raise FileNotFoundError(f"artifact 元数据文件不存在: {path}") from None
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise ValueError(f"artifact 元数据文件无法读取: {name}") from exc
        if actual != embedded:
            raise ValueError(f"artifact {name} 与 manifest 内容不一致")


def inspect_model_artifact(directory: Path | str) -> ModelArtifactManifest:
    """快速检查 artifact 结构和轻量 metadata，不计算任何文件 SHA256。"""
    source = Path(directory)
    manifest = _read_manifest(source)
    _validate_manifest_compatibility(manifest)

    weights = _safe_component_path(source, manifest.weights_file)
    if not weights.is_file():
        raise FileNotFoundError(f"模型权重不存在: {weights}")

    if manifest.schema_version >= 2:
        if not manifest.files_sha256:
            raise ValueError("schema v2 artifact 缺少 files_sha256")
        if manifest.files_sha256.get(manifest.weights_file) != manifest.weights_sha256:
            raise ValueError("weights_sha256 与 files_sha256 不一致")
        for name in manifest.files_sha256:
            path = _safe_component_path(source, name)
            if not path.is_file():
                raise FileNotFoundError(f"artifact 组成文件不存在: {path}")

    _validate_external_metadata(source, manifest)
    return manifest


def verify_model_artifact(
    directory: Path | str,
    *,
    event_callback: EventCallback | None = None,
    cancellation: CancellationCheck | None = None,
    event_context: EventContext | None = None,
) -> ModelArtifactManifest:
    """完整校验全部 SHA256，并以读取字节数暴露进度。"""
    source = Path(directory)
    context = event_context or EventContext()

    def emit(event: LifecycleEvent | ProgressEvent) -> None:
        if event_callback is not None:
            event_callback(event)

    emit(
        LifecycleEvent(
            "artifact_verify",
            "started",
            details={"directory": source},
            context=context,
        )
    )

    completed_bytes = 0
    files_completed = 0
    try:
        if cancellation is not None:
            cancellation.raise_if_cancelled()
        manifest = inspect_model_artifact(source)

        if manifest.schema_version >= 2:
            file_entries = [(manifest.weights_file, manifest.weights_sha256)]
            file_entries.extend(
                (name, expected)
                for name, expected in manifest.files_sha256.items()
                if name != manifest.weights_file
            )
        else:
            file_entries = [(manifest.weights_file, manifest.weights_sha256)]

        resolved = [
            (name, expected, _safe_component_path(source, name))
            for name, expected in file_entries
        ]
        total_bytes = sum(path.stat().st_size for _, _, path in resolved)
        emit(
            ProgressEvent(
                stage="artifact_verify",
                completed=0,
                total=total_bytes,
                message="ready",
                details={
                    "files_completed": 0,
                    "files_total": len(resolved),
                    "bytes_total": total_bytes,
                },
                context=context,
            )
        )

        for name, expected, path in resolved:
            file_completed = 0
            file_total = path.stat().st_size

            def on_chunk(size: int) -> None:
                nonlocal completed_bytes, file_completed
                completed_bytes += size
                file_completed += size
                emit(
                    ProgressEvent(
                        stage="artifact_verify",
                        completed=completed_bytes,
                        total=total_bytes,
                        message=f"hashing {name}",
                        details={
                            "file": name,
                            "file_bytes_completed": file_completed,
                            "file_bytes_total": file_total,
                            "files_completed": files_completed,
                            "files_total": len(resolved),
                        },
                        context=context,
                    )
                )

            actual = _sha256_with_progress(
                path,
                cancellation=cancellation,
                on_chunk=on_chunk,
            )
            if actual != expected:
                if name == manifest.weights_file:
                    raise ValueError("模型权重 SHA-256 校验失败，文件可能损坏或被修改")
                raise ValueError(f"artifact 文件 SHA-256 校验失败: {name}")
            files_completed += 1

        emit(
            LifecycleEvent(
                "artifact_verify",
                "completed",
                details={
                    "directory": source,
                    "bytes_verified": completed_bytes,
                    "files_verified": files_completed,
                },
                context=context,
            )
        )
        return manifest
    except OperationCancelled:
        emit(
            LifecycleEvent(
                "artifact_verify",
                "cancelled",
                details={
                    "directory": source,
                    "bytes_verified": completed_bytes,
                    "files_verified": files_completed,
                },
                context=context,
            )
        )
        raise
    except Exception as exc:
        emit(
            LifecycleEvent(
                "artifact_verify",
                "failed",
                message=str(exc),
                details={
                    "directory": source,
                    "error_type": type(exc).__name__,
                    "bytes_verified": completed_bytes,
                    "files_verified": files_completed,
                },
                context=context,
            )
        )
        raise


def load_model_artifact(
    directory: Path | str,
    *,
    map_location: str | torch.device = "cpu",
    allow_legacy_pickle: bool = False,
) -> LoadedArtifact:
    """完整验证并加载 artifact；旧 v1 pickle 必须显式授权。"""
    source = Path(directory)
    manifest = verify_model_artifact(source)
    target_device = torch.device(map_location)
    if target_device.type == "cuda" and not torch.cuda.is_available():
        raise ValueError("artifact 加载请求 CUDA，但当前环境不可用")
    data_config = DataConfig.model_validate(manifest.preprocessing)
    model = model_registry.create(manifest.model_name, **manifest.model_params)
    audio_loader, pipeline = build_components(data_config, train=False)
    validate_compatibility(
        pipeline.output_specs,
        model.model_spec,
        data_config.batching,
        num_classes=len(manifest.labels),
        sample_rate=data_config.audio.target_sample_rate,
    )
    collator = build_collator(pipeline.output_specs, data_config.batching)
    weights = source / manifest.weights_file
    if manifest.weights_format == "safetensors":
        state = load_file(weights, device="cpu")
    elif manifest.weights_format == "pytorch" and allow_legacy_pickle:
        state = torch.load(weights, map_location="cpu", weights_only=True)
    else:
        raise ValueError(
            "旧 PyTorch artifact 可能包含 pickle；仅可信文件可设置 allow_legacy_pickle=True"
        )
    if not isinstance(state, dict) or not all(
        isinstance(key, str) and isinstance(value, torch.Tensor)
        for key, value in state.items()
    ):
        raise ValueError("artifact 权重不是合法 tensor state_dict")
    model.load_state_dict(state, strict=True)
    model.to(target_device)
    return LoadedArtifact(manifest, model, audio_loader, pipeline, collator)


__all__ = [
    "LoadedArtifact",
    "inspect_model_artifact",
    "verify_model_artifact",
    "load_model_artifact",
]
