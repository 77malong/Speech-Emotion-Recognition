"""快速检查、完整校验并加载模型 artifact。"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

import torch
from safetensors.torch import load_file

from ser_lib import __version__
from ser_lib.artifacts.manifest import ModelArtifactManifest
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
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
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
        return ModelArtifactManifest.model_validate_json(
            manifest_path.read_text(encoding="utf-8")
        )
    except (OSError, UnicodeError, ValueError) as exc:
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
    """快速检查 artifact 结构和轻量 metadata，不计算任何文件 SHA256。

    该入口用于模型列表与详情页首屏：只读取 ``manifest.json`` 和小型 metadata，
    并检查 manifest 声明的组成文件是否存在。权重即使数 GB 也不会被完整读取。
    用户明确执行完整性验证时再调用 :func:`verify_model_artifact`。
    """
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


def verify_model_artifact(directory: Path | str) -> ModelArtifactManifest:
    """在快速 inspect 基础上计算并校验全部 SHA256，不加载模型。"""
    source = Path(directory)
    manifest = inspect_model_artifact(source)
    weights = _safe_component_path(source, manifest.weights_file)
    weights_digest = _sha256(weights)
    if weights_digest != manifest.weights_sha256:
        raise ValueError("模型权重 SHA-256 校验失败，文件可能损坏或被修改")

    if manifest.schema_version >= 2:
        for name, expected in manifest.files_sha256.items():
            if name == manifest.weights_file:
                actual = weights_digest
            else:
                actual = _sha256(_safe_component_path(source, name))
            if actual != expected:
                raise ValueError(f"artifact 文件 SHA-256 校验失败: {name}")
    return manifest


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
            "旧 PyTorch artifact 可能包含 pickle；"
            "仅可信文件可设置 allow_legacy_pickle=True"
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
