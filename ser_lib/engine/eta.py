"""训练/评估进度使用的有界 ETA 估计器。"""

from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class EtaSnapshot:
    """某一阶段的稳定 ETA/吞吐快照。"""

    phase: str
    ready: bool
    samples_seen: int
    batches_seen: int
    average_batch_seconds: float | None
    batches_per_second: float | None
    samples_per_second: float | None
    phase_remaining_seconds: float | None
    global_remaining_seconds: float | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "phase": self.phase,
            "ready": self.ready,
            "samples_seen": self.samples_seen,
            "batches_seen": self.batches_seen,
            "average_batch_seconds": self.average_batch_seconds,
            "batches_per_second": self.batches_per_second,
            "samples_per_second": self.samples_per_second,
            "phase_remaining_seconds": self.phase_remaining_seconds,
            "global_remaining_seconds": self.global_remaining_seconds,
        }


@dataclass(frozen=True, slots=True)
class _BatchTiming:
    duration_seconds: float
    samples: int


class EtaEstimator:
    """按 phase 维护固定 recent-N 窗口的 ETA 状态。

    只接收调用方已有的 batch duration/sample count，不读取系统时钟、不 sleep、
    不知道 DataLoader/模型/optimizer，实现与训练关键路径解耦。
    """

    def __init__(self, *, window_size: int = 20, warmup_batches: int = 3) -> None:
        if window_size < 1:
            raise ValueError("window_size 必须 >= 1")
        if warmup_batches < 1:
            raise ValueError("warmup_batches 必须 >= 1")
        if warmup_batches > window_size:
            raise ValueError("warmup_batches 不能大于 window_size")
        self.window_size = window_size
        self.warmup_batches = warmup_batches
        self._windows: dict[str, deque[_BatchTiming]] = defaultdict(
            lambda: deque(maxlen=self.window_size)
        )
        self._counts: dict[str, int] = defaultdict(int)
        self._samples: dict[str, int] = defaultdict(int)

    def reset(self, phase: str | None = None) -> None:
        if phase is None:
            self._windows.clear()
            self._counts.clear()
            self._samples.clear()
            return
        self._windows.pop(phase, None)
        self._counts.pop(phase, None)
        self._samples.pop(phase, None)

    def record_batch(
        self,
        duration_seconds: float,
        samples: int = 0,
        *,
        phase: str = "train",
    ) -> None:
        if not phase.strip():
            raise ValueError("phase 不能为空")
        if duration_seconds < 0:
            raise ValueError("duration_seconds 必须 >= 0")
        if samples < 0:
            raise ValueError("samples 必须 >= 0")
        self._windows[phase].append(_BatchTiming(float(duration_seconds), int(samples)))
        self._counts[phase] += 1
        self._samples[phase] += int(samples)

    def snapshot(
        self,
        *,
        phase: str = "train",
        completed_batches: int,
        total_batches: int | None,
        future_batches: int = 0,
    ) -> EtaSnapshot:
        if completed_batches < 0:
            raise ValueError("completed_batches 必须 >= 0")
        if total_batches is not None and total_batches < completed_batches:
            raise ValueError("total_batches 不能小于 completed_batches")
        if future_batches < 0:
            raise ValueError("future_batches 必须 >= 0")

        window = self._windows.get(phase)
        batches_seen = self._counts.get(phase, 0)
        samples_seen = self._samples.get(phase, 0)
        ready = bool(window) and batches_seen >= self.warmup_batches
        if not ready or total_batches is None:
            return EtaSnapshot(
                phase=phase,
                ready=ready,
                samples_seen=samples_seen,
                batches_seen=batches_seen,
                average_batch_seconds=None,
                batches_per_second=None,
                samples_per_second=None,
                phase_remaining_seconds=None,
                global_remaining_seconds=None,
            )

        assert window is not None
        duration = sum(item.duration_seconds for item in window)
        samples = sum(item.samples for item in window)
        average_batch_seconds = duration / len(window)
        batches_per_second = len(window) / duration if duration > 0 else 0.0
        samples_per_second = samples / duration if duration > 0 else 0.0
        remaining = max(total_batches - completed_batches, 0)
        return EtaSnapshot(
            phase=phase,
            ready=True,
            samples_seen=samples_seen,
            batches_seen=batches_seen,
            average_batch_seconds=average_batch_seconds,
            batches_per_second=batches_per_second,
            samples_per_second=samples_per_second,
            phase_remaining_seconds=remaining * average_batch_seconds,
            global_remaining_seconds=(remaining + future_batches) * average_batch_seconds,
        )


__all__ = ["EtaSnapshot", "EtaEstimator"]
