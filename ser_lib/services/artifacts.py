"""模型 Artifact 应用服务。"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

import torch

from ser_lib.artifacts import (
    ArtifactCatalog,
    LoadedArtifact,
    ModelArtifactManifest,
    ModelCard,
    export_model_artifact,
    inspect_model_artifact,
    load_model_artifact,
    scan_model_artifacts,
    verify_model_artifact,
)
from ser_lib.core.events import CancellationCheck, EventCallback, EventContext
from ser_lib.data.config import DataConfig
from ser_lib.models.base import SERModel


class ArtifactService:
    """统一模型管理页所需的 scan/inspect/verify/export/load 入口。"""

    @staticmethod
    def scan(
        root: Path | str,
        *,
        recursive: bool = False,
        fail_fast: bool = False,
        event_callback: EventCallback | None = None,
        cancellation: CancellationCheck | None = None,
    ) -> ArtifactCatalog:
        return scan_model_artifacts(
            root,
            recursive=recursive,
            fail_fast=fail_fast,
            event_callback=event_callback,
            cancellation=cancellation,
        )

    @staticmethod
    def inspect(directory: Path | str) -> ModelArtifactManifest:
        return inspect_model_artifact(directory)

    @staticmethod
    def verify(
        directory: Path | str,
        *,
        event_callback: EventCallback | None = None,
        cancellation: CancellationCheck | None = None,
        event_context: EventContext | None = None,
    ) -> ModelArtifactManifest:
        return verify_model_artifact(
            directory,
            event_callback=event_callback,
            cancellation=cancellation,
            event_context=event_context,
        )

    @staticmethod
    def export(
        directory: Path | str,
        model: SERModel,
        *,
        model_name: str,
        data_config: DataConfig,
        labels: Mapping[int, str],
        model_params: Mapping[str, Any] | None = None,
        metrics: Mapping[str, float] | None = None,
        metadata: Mapping[str, Any] | None = None,
        model_card: ModelCard | Mapping[str, Any] | None = None,
        event_callback: EventCallback | None = None,
        cancellation: CancellationCheck | None = None,
        event_context: EventContext | None = None,
    ) -> Path:
        return export_model_artifact(
            directory,
            model,
            model_name=model_name,
            model_params=model_params,
            data_config=data_config,
            labels=labels,
            metrics=metrics,
            metadata=metadata,
            model_card=model_card,
            event_callback=event_callback,
            cancellation=cancellation,
            event_context=event_context,
        )

    @staticmethod
    def load(
        directory: Path | str,
        *,
        map_location: str | torch.device = "cpu",
        allow_legacy_pickle: bool = False,
    ) -> LoadedArtifact:
        return load_model_artifact(
            directory,
            map_location=map_location,
            allow_legacy_pickle=allow_legacy_pickle,
        )


__all__ = ["ArtifactService"]
