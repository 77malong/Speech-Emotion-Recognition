"""已落盘 evaluation.json 的轻量 Catalog 扫描。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ser_lib.engine.evaluation_runs import EvaluationRunInfo, load_evaluation_run_info
from ser_lib.foundation.events import CancellationCheck, EventCallback, ProgressEvent

_EVALUATION_RECORD_NAME = "evaluation.json"


@dataclass(frozen=True, slots=True)
class EvaluationRunScanFailure:
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
class EvaluationRunCatalog:
    """评估历史列表；扫描时不读取 metrics/predictions/artifact。"""

    root: str
    runs: tuple[EvaluationRunInfo, ...]
    failures: tuple[EvaluationRunScanFailure, ...]

    @property
    def total(self) -> int:
        return len(self.runs) + len(self.failures)

    def to_dict(self) -> dict[str, Any]:
        return {
            "root": self.root,
            "total": self.total,
            "runs": [run.to_dict() for run in self.runs],
            "failures": [failure.to_dict() for failure in self.failures],
        }


def scan_evaluation_runs(
    root: Path | str,
    *,
    recursive: bool = False,
    fail_fast: bool = False,
    event_callback: EventCallback | None = None,
    cancellation: CancellationCheck | None = None,
) -> EvaluationRunCatalog:
    """扫描 ``evaluation.json``，不加载模型、Artifact、指标文件或预测明细。"""
    root_path = Path(root)
    if not root_path.is_dir():
        raise NotADirectoryError(f"评估运行根目录不存在或不是目录: {root_path}")
    candidates = _candidate_directories(root_path, recursive=recursive)
    runs: list[EvaluationRunInfo] = []
    failures: list[EvaluationRunScanFailure] = []
    total = len(candidates)

    for index, directory in enumerate(candidates, start=1):
        if cancellation is not None:
            cancellation.raise_if_cancelled()
        try:
            runs.append(load_evaluation_run_info(directory))
        except Exception as exc:
            if fail_fast:
                raise
            failures.append(
                EvaluationRunScanFailure(
                    directory=directory.as_posix(),
                    error_type=type(exc).__name__,
                    message=str(exc),
                )
            )
        if event_callback is not None:
            event_callback(
                ProgressEvent(
                    stage="evaluation_run_catalog_scan",
                    completed=index,
                    total=total,
                    details={
                        "valid": len(runs),
                        "failed": len(failures),
                        "directory": directory,
                    },
                )
            )

    runs.sort(key=lambda item: (item.created_at, item.evaluation_id), reverse=True)
    return EvaluationRunCatalog(
        root=root_path.as_posix(),
        runs=tuple(runs),
        failures=tuple(failures),
    )


def _candidate_directories(root: Path, *, recursive: bool) -> list[Path]:
    candidates: set[Path] = set()
    if (root / _EVALUATION_RECORD_NAME).is_file():
        candidates.add(root)
    if recursive:
        candidates.update(path.parent for path in root.rglob(_EVALUATION_RECORD_NAME))
    else:
        candidates.update(
            child
            for child in root.iterdir()
            if child.is_dir() and (child / _EVALUATION_RECORD_NAME).is_file()
        )
    return sorted(candidates, key=lambda path: path.as_posix().casefold())


__all__ = [
    "EvaluationRunScanFailure",
    "EvaluationRunCatalog",
    "scan_evaluation_runs",
]
