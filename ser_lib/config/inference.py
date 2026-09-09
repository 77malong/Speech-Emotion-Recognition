"""推理相关用户配置；保持现有 StreamingConfig dataclass 语义。"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class StreamingConfig:
    input_sample_rate: int = 16000
    window_ms: int = 2000
    hop_ms: int = 500
    silence_rms_threshold: float = 0.0
    suppress_silence: bool = True
    smoothing_alpha: float = 1.0
    max_chunk_ms: int = 10000

    def __post_init__(self) -> None:
        if self.input_sample_rate <= 0:
            raise ValueError("input_sample_rate 必须 > 0")
        if self.window_ms <= 0 or self.hop_ms <= 0:
            raise ValueError("window_ms 和 hop_ms 必须 > 0")
        if self.hop_ms > self.window_ms:
            raise ValueError("hop_ms 不能大于 window_ms")
        if self.silence_rms_threshold < 0:
            raise ValueError("silence_rms_threshold 必须 >= 0")
        if not 0 < self.smoothing_alpha <= 1:
            raise ValueError("smoothing_alpha 必须在 (0, 1] 内")
        if self.max_chunk_ms <= 0:
            raise ValueError("max_chunk_ms 必须 > 0")


__all__ = ["StreamingConfig"]
