"""数据集应用服务：为 Web/CLI 提供稳定的领域入口。"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from ser_lib.core.events import CancellationCheck, EventCallback
from ser_lib.data.editor import DatasetEditor
from ser_lib.data.fingerprint import DatasetFingerprint, fingerprint_manifest
from ser_lib.data.history import (
    DatasetRevisionCatalog,
    DatasetRevisionInfo,
    create_dataset_revision,
    inspect_dataset_revision,
    restore_dataset_revision,
    scan_dataset_revisions,
)
from ser_lib.data.manifest import DatasetManifest
from ser_lib.data.profiling import (
    DatasetAudioProfile,
    DatasetProfile,
    DatasetSummary,
    profile_dataset,
    profile_manifest_audio,
    summarize_manifest,
)
from ser_lib.data.query import RecordPage, query_records


class DatasetService:
    """薄 facade；不复制 Manifest/Query/Editor/History 的业务规则。"""

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
        histogram_bins: int = 10,
        event_callback: EventCallback | None = None,
        cancellation: CancellationCheck | None = None,
    ) -> DatasetAudioProfile:
        """保留现有音频 header profile API。"""
        return profile_manifest_audio(
            manifest,
            split=split,
            fail_fast=fail_fast,
            histogram_bins=histogram_bins,
            event_callback=event_callback,
            cancellation=cancellation,
        )

    @staticmethod
    def detailed_profile(
        manifest: DatasetManifest | Path | str,
        *,
        include_audio: bool = False,
        fail_fast: bool = False,
        histogram_bins: int = 10,
        event_callback: EventCallback | None = None,
        cancellation: CancellationCheck | None = None,
    ) -> DatasetProfile:
        """返回数据集分析页使用的 split/label/speaker/audio 详细统计。"""
        return profile_dataset(
            manifest,
            include_audio=include_audio,
            fail_fast=fail_fast,
            histogram_bins=histogram_bins,
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

    @staticmethod
    def snapshot_revision(
        manifest: DatasetManifest | Path | str,
        *,
        history_root: Path | str | None = None,
        revision_id: str | None = None,
        note: str = "",
        created_at: datetime | None = None,
        event_callback: EventCallback | None = None,
        cancellation: CancellationCheck | None = None,
    ) -> DatasetRevisionInfo:
        return create_dataset_revision(
            manifest,
            history_root=history_root,
            revision_id=revision_id,
            note=note,
            created_at=created_at,
            event_callback=event_callback,
            cancellation=cancellation,
        )

    @staticmethod
    def inspect_revision(
        revision: Path | str,
        *,
        verify: bool = False,
        cancellation: CancellationCheck | None = None,
    ) -> DatasetRevisionInfo:
        return inspect_dataset_revision(
            revision,
            verify=verify,
            cancellation=cancellation,
        )

    @staticmethod
    def revision_history(
        manifest: DatasetManifest | Path | str,
        *,
        history_root: Path | str | None = None,
        fail_fast: bool = False,
        event_callback: EventCallback | None = None,
        cancellation: CancellationCheck | None = None,
    ) -> DatasetRevisionCatalog:
        return scan_dataset_revisions(
            manifest,
            history_root=history_root,
            fail_fast=fail_fast,
            event_callback=event_callback,
            cancellation=cancellation,
        )

    @staticmethod
    def restore_revision(
        manifest: DatasetManifest | Path | str,
        revision: Path | str,
        *,
        expected_current_fingerprint: str,
        event_callback: EventCallback | None = None,
        cancellation: CancellationCheck | None = None,
    ) -> DatasetManifest:
        return restore_dataset_revision(
            manifest,
            revision,
            expected_current_fingerprint=expected_current_fingerprint,
            event_callback=event_callback,
            cancellation=cancellation,
        )


__all__ = ["DatasetService"]
