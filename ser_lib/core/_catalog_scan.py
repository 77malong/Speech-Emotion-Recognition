"""Catalog 扫描器共享控制流；领域 candidate、DTO 与排序规则保持独立。"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from pathlib import Path
from typing import TypeVar

from ser_lib.core.events import CancellationCheck, EventCallback, ProgressEvent

ItemT = TypeVar("ItemT")
FailureT = TypeVar("FailureT")


def scan_catalog_candidates(
    candidates: Sequence[Path],
    *,
    inspect_candidate: Callable[[Path], ItemT | None],
    failure_factory: Callable[[Path, Exception], FailureT],
    stage: str,
    candidate_detail_key: str | None,
    fail_fast: bool = False,
    event_callback: EventCallback | None = None,
    cancellation: CancellationCheck | None = None,
) -> tuple[list[ItemT], list[FailureT]]:
    """统一 Catalog 的取消、失败策略和 progress 事件。

    ``inspect_candidate`` 返回 ``None`` 表示 candidate 合法但被领域规则过滤，
    例如 Dataset revision 属于其他 dataset_id。候选发现、结果排序和领域 DTO
    构造仍由调用模块负责。
    """
    items: list[ItemT] = []
    failures: list[FailureT] = []
    total = len(candidates)

    for index, candidate in enumerate(candidates, start=1):
        if cancellation is not None:
            cancellation.raise_if_cancelled()
        try:
            item = inspect_candidate(candidate)
            if item is not None:
                items.append(item)
        except Exception as exc:
            if fail_fast:
                raise
            failures.append(failure_factory(candidate, exc))

        if event_callback is not None:
            details: dict[str, object] = {
                "valid": len(items),
                "failed": len(failures),
            }
            if candidate_detail_key is not None:
                details[candidate_detail_key] = candidate
            event_callback(
                ProgressEvent(
                    stage=stage,
                    completed=index,
                    total=total,
                    details=details,
                )
            )

    return items, failures


__all__ = ["scan_catalog_candidates"]
