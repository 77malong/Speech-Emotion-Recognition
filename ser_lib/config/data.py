"""SER 数据流水线的中央用户配置 schema。"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from pydantic import Field, field_validator

from ser_lib.config.base import StrictConfig
from ser_lib.config.loader import load_yaml_mapping, resolve_config_path

BatchingType = Literal["dynamic", "fixed", "sliding"]
AudioBackend = Literal["soundfile", "torchaudio"]


class ComponentConfig(StrictConfig):
    """通用组件引用：``{type, params, probability}``。"""

    type: str = Field(..., min_length=1, description="注册表中的组件名")
    params: dict[str, Any] = Field(default_factory=dict, description="组件参数")
    probability: float | None = Field(
        default=None, ge=0.0, le=1.0, description="随机 transform 的触发概率"
    )


class AudioConfig(StrictConfig):
    """音频解码与标准化的唯一正式用户配置。"""

    target_sample_rate: int = Field(default=16000, ge=1000, le=192000)
    mono: bool = True
    normalize_peak: bool = False
    backend: AudioBackend = "soundfile"


class CacheConfig(StrictConfig):
    """确定性 Representation 磁盘缓存配置。"""

    enabled: bool = False
    directory: Path = Path(".ser-cache/features")


class FixedBatching(StrictConfig):
    """固定长度批处理参数：按 key 配置最大长度。"""

    max_lengths: dict[str, int] = Field(..., min_length=1)

    @field_validator("max_lengths")
    @classmethod
    def _positive(cls, value: dict[str, int]) -> dict[str, int]:
        for key, length in value.items():
            if length < 1:
                raise ValueError(f"max_lengths['{key}'] 必须 >= 1，实际: {length}")
        return value


class SlidingBatching(StrictConfig):
    """滑动窗口批处理参数。"""

    window_size: int = Field(..., ge=1)
    stride: int = Field(..., ge=1)

    @field_validator("stride")
    @classmethod
    def _stride_le_window(cls, value: int, info) -> int:
        window = info.data.get("window_size")
        if window is not None and value > window:
            raise ValueError(f"stride ({value}) 不能大于 window_size ({window})")
        return value


class BatchingConfig(StrictConfig):
    """dynamic/fixed/sliding 三种批处理策略的用户配置。"""

    type: BatchingType = "dynamic"
    fixed: FixedBatching | None = None
    sliding: SlidingBatching | None = None
    primary_key: str | None = None

    @field_validator("fixed", "sliding", mode="before")
    @classmethod
    def _none_to_missing(cls, value: Any) -> Any:
        return value

    @property
    def is_dynamic(self) -> bool:
        return self.type == "dynamic"

    def validate_completeness(self) -> None:
        """校验策略与参数节点的一致性，在任务启动前失败。"""
        if self.type == "fixed" and self.fixed is None:
            raise ValueError(
                "batching.type='fixed' 时必须提供 fixed.max_lengths "
                "（例如 {features: 300}）"
            )
        if self.type == "sliding" and self.sliding is None:
            raise ValueError(
                "batching.type='sliding' 时必须提供 sliding.window_size 与 sliding.stride"
            )
        if self.type != "fixed" and self.fixed is not None:
            raise ValueError("仅 batching.type='fixed' 允许提供 fixed 节点")
        if self.type != "sliding" and self.sliding is not None:
            raise ValueError("仅 batching.type='sliding' 允许提供 sliding 节点")


class DataConfig(StrictConfig):
    """数据模块顶层配置；manifest 相对配置文件目录解析。"""

    schema_version: int = 1
    manifest: Path
    dataset_id: str | None = None
    labels: dict[int, dict[str, Any]] | None = None
    audio: AudioConfig = Field(default_factory=AudioConfig)
    cache: CacheConfig = Field(default_factory=CacheConfig)
    representation: ComponentConfig
    waveform_transforms: list[ComponentConfig] = Field(default_factory=list)
    feature_transforms: list[ComponentConfig] = Field(default_factory=list)
    batching: BatchingConfig = Field(default_factory=BatchingConfig)

    @field_validator("batching")
    @classmethod
    def _validate_batching(cls, value: BatchingConfig) -> BatchingConfig:
        value.validate_completeness()
        return value

    @field_validator("labels")
    @classmethod
    def _validate_labels(
        cls, value: dict[int, dict[str, Any]] | None
    ) -> dict[int, dict[str, Any]] | None:
        if value is None:
            return None
        keys = sorted(value.keys())
        if keys != list(range(len(keys))):
            raise ValueError(f"labels 的 key 必须从 0 开始连续，实际: {keys}")
        return value

    @property
    def num_classes(self) -> int | None:
        return len(self.labels) if self.labels is not None else None


def load_data_config(path: Path | str) -> DataConfig:
    """加载 DataConfig，并保持 manifest 相对配置文件目录的旧解释语义。"""
    raw, source = load_yaml_mapping(path)
    if "manifest" in raw and raw["manifest"] is not None:
        raw["manifest"] = resolve_config_path(raw["manifest"], base_dir=source.parent)
    return DataConfig.model_validate(raw)


# 0.2.x 读兼容：旧名称只指向同一正式 schema，不再维护独立定义。
AudioSettings = AudioConfig
CacheSettings = CacheConfig


__all__ = [
    "AudioBackend",
    "BatchingType",
    "ComponentConfig",
    "AudioConfig",
    "CacheConfig",
    "FixedBatching",
    "SlidingBatching",
    "BatchingConfig",
    "DataConfig",
    "load_data_config",
    "AudioSettings",
    "CacheSettings",
]
