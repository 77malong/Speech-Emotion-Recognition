"""数据集应用服务：为 Web/CLI 提供稳定的领域入口。"""

from __future__ import annotations

from pathlib import Path

from ser_lib.core.events import CancellationCheck, EventCallback
from ser_lib.data.editor import DatasetEditor
from ser_lib.data.fingerprint import DatasetFingerprint, fingerprint_manifest
from ser_lib.data.manifest import DatasetManifest
from ser_lib.data.profiling import (
    DatasetAudioProfile,
    DatasetSummary,
    profile_manifest_audio,
    summarize_manifest,
)
from ser_lib.data.query import RecordPage, query_records


class DatasetService:
    """薄 facade；不复制 Manifest/Query/Editor 的业务规则。"""

    @staticmethod
    def summary(
        manifest: DatasetManifest | Path | str,
        *,
        include_audio_profile: bool = False,
        fail_fast: bool = False,
        event_callback: EventCallback | None = None,
        cancellation: CancellationCheck | None = None,
    ) -> DatasetSummary:
        return summarize_manifest(
            manifest,
            include_audio_profile=include_audio_profile,
            fail_fast=fail_fast,
            event_callback=event_callback,
            cancellation=cancellation,
        )

    @staticmethod
    def profile(
        manifest: DatasetManifest | Path | str,
        *,
        split: str | None = None,
        fail_fast: bool = False,
        event_callback: EventCallback | None = None,
        cancellation: CancellationCheck | None = None,
    ) -> DatasetAudioProfile:
        return profile_manifest_audio(
            manifest,
            split=split,
            fail_fast=fail_fast,
            event_callback=event_callback,
            cancellation=cancellation,
        )

    @staticmethod
    def query(
        manifest: DatasetManifest | Path | str,
        *,
        split: str | None = None,
        label_id: int | None = None,
        speaker_id: str | None = None,
        keyword: str | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> RecordPage:
        return query_records(
            manifest,
            split=split,
            label_id=label_id,
            speaker_id=speaker_id,
            keyword=keyword,
            offset=offset,
            limit=limit,
        )

    @staticmethod
    def fingerprint(
        manifest: DatasetManifest | Path | str,
        *,
        event_callback: EventCallback | None = None,
        cancellation: CancellationCheck | None = None,
    ) -> DatasetFingerprint:
        return fingerprint_manifest(
            manifest,
            event_callback=event_callback,
            cancellation=cancellation,
        )

    @staticmethod
    def editor(manifest: DatasetManifest | Path | str) -> DatasetEditor:
        return DatasetEditor(manifest)


__all__ = ["DatasetService"]
