"""可移植模型 artifact 的当前 manifest。"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import Field, field_validator

from ser_lib.config.base import StrictConfig


class ModelCard(StrictConfig):
    """最小模型卡；未知信息允许留空，但字段不可隐式发明。"""

    description: str = ""
    intended_use: str = ""
    dataset: str = ""
    language: list[str] = Field(default_factory=list)
    license: str = ""
    limitations: list[str] = Field(default_factory=list)


class ModelArtifactManifest(StrictConfig):
    library_version: str
    model_name: str
    model_params: dict[str, Any]
    input_specs: dict[str, dict[str, Any]] = Field(default_factory=dict)
    weights_file: Literal["weights.safetensors"] = "weights.safetensors"
    weights_sha256: str
    files_sha256: dict[str, str]
    preprocessing: dict[str, Any]
    processor: dict[str, Any] | None = None
    labels: dict[int, str]
    metrics: dict[str, float] = Field(default_factory=dict)
    model_card: ModelCard = Field(default_factory=ModelCard)
    metadata: dict[str, Any] = Field(default_factory=dict)


    @field_validator("weights_sha256")
    @classmethod
    def _valid_sha256(cls, value: str) -> str:
        if len(value) != 64 or any(char not in "0123456789abcdef" for char in value.lower()):
            raise ValueError("weights_sha256 必须是 64 位十六进制 SHA-256")
        return value.lower()

    @field_validator("labels")
    @classmethod
    def _contiguous_labels(cls, value: dict[int, str]) -> dict[int, str]:
        if sorted(value) != list(range(len(value))):
            raise ValueError("artifact labels 必须从 0 开始连续")
        if len(value) < 2 or any(not name for name in value.values()):
            raise ValueError("artifact 至少需要两个非空标签")
        return value


__all__ = ["ModelCard", "ModelArtifactManifest"]
