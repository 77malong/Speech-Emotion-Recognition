"""面向 Web/CLI 的 Dataset 编辑器与多文件事务提交。"""

from __future__ import annotations

import os
import shutil
import tempfile
from collections.abc import Iterable, Mapping
from dataclasses import replace
from pathlib import Path
from typing import Any

import yaml

from ser_lib.data.errors import (
    DatasetEditConflictError,
    DatasetEditError,
    DatasetTransactionError,
)
from ser_lib.data.fingerprint import fingerprint_manifest
from ser_lib.data.manifest import DatasetManifest, write_jsonl
from ser_lib.data.types import AudioRecord

_UNSET = object()


class DatasetEditor:
    """对标准 Dataset 做内存编辑，并通过事务层一次性提交。

    编辑操作不会立即写盘。``commit()`` 会执行：

    1. fingerprint 乐观并发检查；
    2. sibling staging 目录写完整数据；
    3. ``DatasetManifest.load()`` 验证 staging；
    4. 备份当前文件并逐文件原子替换；
    5. 任一步失败时恢复原文件。

    ``rollback()`` 仅丢弃当前未提交的内存修改。
    """

    def __init__(self, manifest: DatasetManifest | Path | str) -> None:
        dataset = (
            manifest
            if isinstance(manifest, DatasetManifest)
            else DatasetManifest.load(manifest)
        )
        self._yaml_path = dataset.meta.yaml_path
        self._manifest = dataset
        self._records = list(dataset.records)
        self._record_splits = dict(dataset.record_splits)
        self._base_records = tuple(dataset.records)
        self._base_splits = dict(dataset.record_splits)
        self._base_fingerprint = fingerprint_manifest(dataset).digest

    @property
    def dataset_id(self) -> str:
        return self._manifest.meta.dataset_id

    @property
    def dirty(self) -> bool:
        return (
            tuple(self._records) != self._base_records
            or self._record_splits != self._base_splits
        )

    def snapshot(self) -> DatasetManifest:
        """返回当前内存编辑状态的独立 ``DatasetManifest`` 视图。"""
        return DatasetManifest(
            self._manifest.meta,
            list(self._records),
            dict(self._record_splits),
        )

    def update_record(
        self,
        uid: str,
        *,
        audio_path: Path | str | object = _UNSET,
        label: int | None | object = _UNSET,
        split: str | object = _UNSET,
        speaker_id: str | None | object = _UNSET,
        start_ms: int | None | object = _UNSET,
        end_ms: int | None | object = _UNSET,
        sample_rate_hint: int | None | object = _UNSET,
        metadata: Mapping[str, Any] | object = _UNSET,
    ) -> AudioRecord:
        """修改单条记录；所有字段通过验证后才一次性应用内存状态。"""
        index = self._index_for_uid(uid)
        current = self._records[index]
        changes: dict[str, Any] = {}
        if audio_path is not _UNSET:
            changes["audio_path"] = Path(audio_path)  # type: ignore[arg-type]
        if label is not _UNSET:
            self._validate_label(label)
            changes["label"] = label
        if speaker_id is not _UNSET:
            if speaker_id is not None and not isinstance(speaker_id, str):
                raise DatasetEditError("speaker_id 必须是字符串或 None", uid=uid)
            changes["speaker_id"] = speaker_id
        if start_ms is not _UNSET:
            changes["start_ms"] = start_ms
        if end_ms is not _UNSET:
            changes["end_ms"] = end_ms
        if sample_rate_hint is not _UNSET:
            changes["sample_rate_hint"] = sample_rate_hint
        if metadata is not _UNSET:
            if not isinstance(metadata, Mapping):
                raise DatasetEditError("metadata 必须是 Mapping", uid=uid)
            changes["metadata"] = dict(metadata)
        if split is not _UNSET:
            self._validate_split(split)
        try:
            updated = replace(current, **changes)
        except (TypeError, ValueError) as exc:
            raise DatasetEditError(str(exc), uid=uid) from exc

        # Do not mutate either record or split state until every requested field
        # has passed validation and the replacement record has been constructed.
        self._records[index] = updated
        if split is not _UNSET:
            self._record_splits[uid] = split  # type: ignore[assignment]
        return updated

    def delete_records(self, uids: Iterable[str]) -> int:
        """删除一批记录；任一 uid 不存在时整个操作拒绝执行。"""
        uid_set = self._normalize_uids(uids)
        self._require_uids(uid_set)
        self._records = [record for record in self._records if record.uid not in uid_set]
        for uid in uid_set:
            self._record_splits.pop(uid, None)
        return len(uid_set)

    def move_records(self, uids: Iterable[str], split: str) -> int:
        """批量移动记录到目标 split。"""
        self._validate_split(split)
        uid_set = self._normalize_uids(uids)
        self._require_uids(uid_set)
        for uid in uid_set:
            self._record_splits[uid] = split
        return len(uid_set)

    def replace_label(
        self,
        source_label: int | None,
        target_label: int | None,
        *,
        split: str | None = None,
    ) -> int:
        """批量把 ``source_label`` 替换成 ``target_label``。"""
        self._validate_label(target_label)
        if split is not None:
            self._validate_split(split)
        changed = 0
        for index, record in enumerate(self._records):
            if record.label != source_label:
                continue
            if split is not None and self._record_splits.get(record.uid) != split:
                continue
            self._records[index] = replace(record, label=target_label)
            changed += 1
        return changed

    def update_speaker(self, uids: Iterable[str], speaker_id: str | None) -> int:
        """批量设置或清空 speaker_id。"""
        if speaker_id is not None and not isinstance(speaker_id, str):
            raise DatasetEditError("speaker_id 必须是字符串或 None")
        uid_set = self._normalize_uids(uids)
        self._require_uids(uid_set)
        for index, record in enumerate(self._records):
            if record.uid in uid_set:
                self._records[index] = replace(record, speaker_id=speaker_id)
        return len(uid_set)

    def rollback(self) -> "DatasetEditor":
        """丢弃所有尚未提交的内存修改。"""
        self._records = list(self._base_records)
        self._record_splits = dict(self._base_splits)
        return self

    def commit(self) -> DatasetManifest:
        """把当前编辑状态事务化写回磁盘，并返回重新加载后的 Dataset。"""
        if not self.dirty:
            self._assert_source_unchanged()
            return self._manifest

        self._assert_source_unchanged()
        yaml_path = self._yaml_path
        staging_root = Path(
            tempfile.mkdtemp(
                prefix=f".{yaml_path.stem}.staging-",
                dir=str(yaml_path.parent),
            )
        )
        try:
            plan = self._write_staging(staging_root)
            try:
                DatasetManifest.load(plan.validation_yaml)
            except Exception as exc:
                raise DatasetTransactionError(
                    "staging Dataset 验证失败",
                    path=yaml_path,
                    stage="validate",
                ) from exc

            # staging 期间也可能有其他进程修改 Dataset，因此提交前再次检查。
            self._assert_source_unchanged()
            self._commit_plan(plan)
            try:
                committed = DatasetManifest.load(yaml_path)
            except Exception as exc:
                raise DatasetTransactionError(
                    "提交后的 Dataset 无法重新加载",
                    path=yaml_path,
                    stage="reload",
                ) from exc
        finally:
            shutil.rmtree(staging_root, ignore_errors=True)

        self._manifest = committed
        self._records = list(committed.records)
        self._record_splits = dict(committed.record_splits)
        self._base_records = tuple(committed.records)
        self._base_splits = dict(committed.record_splits)
        self._base_fingerprint = fingerprint_manifest(committed).digest
        return committed

    def _write_staging(self, staging_root: Path) -> "_CommitPlan":
        split_order = list(self._manifest.meta.splits)
        for record in self._records:
            split = self._record_splits.get(record.uid)
            if split is None:
                raise DatasetEditError(
                    "记录缺少 split，无法提交",
                    uid=record.uid,
                )
            if split not in split_order:
                split_order.append(split)

        by_split: dict[str, list[AudioRecord]] = {name: [] for name in split_order}
        for record in self._records:
            split = self._record_splits[record.uid]
            by_split.setdefault(split, []).append(record)

        target_paths: dict[str, Path] = {}
        staged_paths: dict[str, Path] = {}
        used_targets: set[Path] = set()
        for index, split in enumerate(split_order):
            target = self._manifest.meta.splits.get(split)
            if target is None:
                target = self._yaml_path.parent / f"{split}.jsonl"
            target = target.resolve()
            if target in used_targets:
                raise DatasetEditError(
                    f"多个 split 指向同一文件: {target}",
                    path=target,
                )
            used_targets.add(target)
            target_paths[split] = target
            staged = staging_root / f"split-{index:04d}.jsonl"
            write_jsonl(by_split.get(split, []), staged)
            staged_paths[split] = staged

        validation_yaml = staging_root / "dataset.validate.yaml"
        validation_doc = self._dataset_doc(
            {split: staged_paths[split].name for split in split_order}
        )
        _write_yaml(validation_doc, validation_yaml)

        final_yaml = staging_root / "dataset.final.yaml"
        final_doc = self._dataset_doc(
            {
                split: _path_reference(target_paths[split], self._yaml_path.parent)
                for split in split_order
            }
        )
        _write_yaml(final_doc, final_yaml)
        return _CommitPlan(
            validation_yaml=validation_yaml,
            final_yaml=final_yaml,
            staged_paths=staged_paths,
            target_paths=target_paths,
        )

    def _dataset_doc(self, split_refs: Mapping[str, str]) -> dict[str, Any]:
        meta = self._manifest.meta
        doc: dict[str, Any] = {
            "schema_version": meta.schema_version,
            "dataset_id": meta.dataset_id,
            "root": str(meta.root),
            "splits": dict(split_refs),
        }
        if meta.labels:
            doc["labels"] = {str(key): value for key, value in sorted(meta.labels.items())}
        return doc

    def _commit_plan(self, plan: "_CommitPlan") -> None:
        targets = list(plan.target_paths.values()) + [self._yaml_path]
        backup_root = plan.final_yaml.parent / "backup"
        backup_root.mkdir(parents=True, exist_ok=True)
        backups: dict[Path, Path | None] = {}
        for index, target in enumerate(targets):
            if target.exists():
                backup = backup_root / f"backup-{index:04d}"
                shutil.copy2(target, backup)
                backups[target] = backup
            else:
                backups[target] = None

        try:
            for split, target in plan.target_paths.items():
                _commit_replace_file(plan.staged_paths[split], target)
            _commit_replace_file(plan.final_yaml, self._yaml_path)
        except Exception as exc:
            restore_errors = _restore_backups(backups)
            if restore_errors:
                details = "; ".join(restore_errors)
                raise DatasetTransactionError(
                    f"Dataset 提交失败，且自动恢复不完整: {details}",
                    path=self._yaml_path,
                    stage="restore",
                ) from exc
            raise DatasetTransactionError(
                "Dataset 提交失败，已恢复原文件",
                path=self._yaml_path,
                stage="commit",
            ) from exc

    def _assert_source_unchanged(self) -> None:
        try:
            current = fingerprint_manifest(self._yaml_path).digest
        except Exception as exc:
            raise DatasetEditConflictError(
                "编辑期间源 Dataset 已变更或无法重新读取",
                path=self._yaml_path,
            ) from exc
        if current != self._base_fingerprint:
            raise DatasetEditConflictError(
                "编辑期间源 Dataset 已被其他进程修改，拒绝覆盖新版本",
                path=self._yaml_path,
            )

    def _index_for_uid(self, uid: str) -> int:
        for index, record in enumerate(self._records):
            if record.uid == uid:
                return index
        raise DatasetEditError("记录不存在", uid=uid)

    def _require_uids(self, uids: set[str]) -> None:
        existing = {record.uid for record in self._records}
        missing = sorted(uids - existing)
        if missing:
            raise DatasetEditError(f"记录不存在: {missing}")

    @staticmethod
    def _normalize_uids(uids: Iterable[str]) -> set[str]:
        uid_set = {uid for uid in uids}
        if not uid_set:
            raise DatasetEditError("uids 不能为空")
        if any(not isinstance(uid, str) or not uid for uid in uid_set):
            raise DatasetEditError("uids 必须全部为非空字符串")
        return uid_set

    def _validate_label(self, label: object) -> None:
        if label is not None and not isinstance(label, int):
            raise DatasetEditError(f"label 必须是 int 或 None，实际: {label!r}")
        labels = self._manifest.meta.labels
        if label is not None and labels and label not in labels:
            raise DatasetEditError(
                f"label={label} 超出 labels 表范围 {sorted(labels)}"
            )

    @staticmethod
    def _validate_split(split: object) -> None:
        if not isinstance(split, str) or not split:
            raise DatasetEditError("split 必须是非空字符串")
        if split in {".", ".."} or Path(split).name != split or "/" in split or "\\" in split:
            raise DatasetEditError(f"split 不能包含路径成分: {split!r}")


class _CommitPlan:
    def __init__(
        self,
        *,
        validation_yaml: Path,
        final_yaml: Path,
        staged_paths: dict[str, Path],
        target_paths: dict[str, Path],
    ) -> None:
        self.validation_yaml = validation_yaml
        self.final_yaml = final_yaml
        self.staged_paths = staged_paths
        self.target_paths = target_paths


def _write_yaml(doc: Mapping[str, Any], path: Path) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as file_obj:
        yaml.safe_dump(dict(doc), file_obj, allow_unicode=True, sort_keys=False)


def _path_reference(path: Path, base: Path) -> str:
    try:
        return path.relative_to(base.resolve()).as_posix()
    except ValueError:
        return str(path)


def _commit_replace_file(source: Path, target: Path) -> None:
    """把 staged 文件在目标目录中通过 ``os.replace`` 原子替换。"""
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(
        prefix=f".{target.name}.txn-",
        dir=str(target.parent),
    )
    os.close(fd)
    temp_path = Path(temp_name)
    try:
        shutil.copy2(source, temp_path)
        os.replace(temp_path, target)
    finally:
        temp_path.unlink(missing_ok=True)


def _restore_backups(backups: Mapping[Path, Path | None]) -> list[str]:
    errors: list[str] = []
    for target, backup in backups.items():
        try:
            if backup is None:
                target.unlink(missing_ok=True)
            else:
                _restore_file(backup, target)
        except Exception as exc:  # pragma: no cover - 极端磁盘/权限二次故障
            errors.append(f"{target}: {type(exc).__name__}: {exc}")
    return errors


def _restore_file(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(
        prefix=f".{target.name}.restore-",
        dir=str(target.parent),
    )
    os.close(fd)
    temp_path = Path(temp_name)
    try:
        shutil.copy2(source, temp_path)
        os.replace(temp_path, target)
    finally:
        temp_path.unlink(missing_ok=True)


__all__ = ["DatasetEditor"]
