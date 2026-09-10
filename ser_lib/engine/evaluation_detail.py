"""评估运行的轻量详情聚合 DTO 与 prediction 文件元数据。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ser_lib.engine.evaluation_reports import EvaluationReportInfo, inspect_evaluation_report
from ser_lib.engine.evaluation_runs import EvaluationRunInfo, load_evaluation_run_info
from ser_lib.foundation.diagnostics import Diagnostic


@dataclass(frozen=True, slots=True)
class EvaluationPredictionFileInfo:
    """仅通过 evaluation metadata 与文件 stat 获得的 prediction 文件信息。"""

    path: str | None
    exists: bool
    size_bytes: int | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "exists": self.exists,
            "size_bytes": self.size_bytes,
        }


@dataclass(frozen=True, slots=True)
class EvaluationRunDetail:
    """Worker/详情页可直接消费的轻量评估聚合结果。

    默认读取成本为 ``evaluation.json + metrics.json + stat(predictions)``，
    不读取 prediction records，也不加载 source artifact。
    """

    run: EvaluationRunInfo
    report: EvaluationReportInfo | None
    predictions: EvaluationPredictionFileInfo
    diagnostics: tuple[Diagnostic, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "run": self.run.to_dict(),
            "report": self.report.to_dict() if self.report is not None else None,
            "predictions": self.predictions.to_dict(),
            "diagnostics": [item.to_dict() for item in self.diagnostics],
        }


def inspect_evaluation_prediction_file(run: EvaluationRunInfo) -> EvaluationPredictionFileInfo:
    """按 ``evaluation.json`` 声明的文件名做 stat，不打开 prediction 内容。"""
    if run.predictions_file is None:
        return EvaluationPredictionFileInfo(path=None, exists=False, size_bytes=None)

    path = Path(run.directory) / run.predictions_file
    if not path.is_file():
        return EvaluationPredictionFileInfo(
            path=path.as_posix(),
            exists=False,
            size_bytes=None,
        )
    return EvaluationPredictionFileInfo(
        path=path.as_posix(),
        exists=True,
        size_bytes=path.stat().st_size,
    )


def inspect_evaluation_run_detail(path: Path | str) -> EvaluationRunDetail:
    """聚合 evaluation metadata、metrics 与 prediction stat，不读预测明细。"""
    run = load_evaluation_run_info(path)
    run_dir = Path(run.directory)
    predictions = inspect_evaluation_prediction_file(run)
    diagnostics: list[Diagnostic] = []

    try:
        report = inspect_evaluation_report(run_dir)
    except (FileNotFoundError, NotADirectoryError, ValueError) as exc:
        report = None
        diagnostics.append(
            Diagnostic(
                severity="warning",
                code="evaluation_report_unavailable",
                message=str(exc),
                stage="evaluation_run_detail",
                path=(run_dir / run.metrics_file).as_posix(),
                details={"error_type": type(exc).__name__},
            )
        )

    if run.predictions_file is not None and not predictions.exists:
        diagnostics.append(
            Diagnostic(
                severity="warning",
                code="evaluation_predictions_unavailable",
                message=f"评估 predictions 文件不存在: {predictions.path}",
                stage="evaluation_run_detail",
                path=predictions.path,
            )
        )

    return EvaluationRunDetail(
        run=run,
        report=report,
        predictions=predictions,
        diagnostics=tuple(diagnostics),
    )


__all__ = [
    "EvaluationPredictionFileInfo",
    "EvaluationRunDetail",
    "inspect_evaluation_prediction_file",
    "inspect_evaluation_run_detail",
]
