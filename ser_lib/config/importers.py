"""内置数据 importer 的用户配置 schema；不依赖 importer 执行实现。"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator

from ser_lib.config.base import StrictConfig

DEFAULT_AUDIO_EXTENSIONS = (
    ".wav",
    ".flac",
    ".mp3",
    ".ogg",
    ".m4a",
    ".wv",
    ".aiff",
)


class CasiaImportConfig(StrictConfig):
    audio_extensions: list[str] = Field(default_factory=lambda: list(DEFAULT_AUDIO_EXTENSIONS))
    label_mapping: dict[str, int] | None = None


class CsvImportConfig(StrictConfig):
    audio_path_column: str = Field(default="audio_path", min_length=1)
    label_column: str | None = Field(default="label")
    label_mapping: dict[str, int] | None = None
    speaker_column: str | None = None
    metadata_columns: list[str] = Field(default_factory=list)
    uid_column: str | None = None
    uid_prefix: str = Field(default="audio", min_length=1)
    delimiter: str = Field(default=",", min_length=1, max_length=1)
    encoding: str = "utf-8-sig"
    root: Path | None = None


class CsemotionsImportConfig(StrictConfig):
    metadata_file: str = "csemotions_metadata.csv"
    audio_directory: str = "wav_data"
    encoding: str = "utf-8-sig"
    label_mapping: dict[str, int] | None = None
    speaker_splits: dict[str, list[str]] | None = None


class CremaDImportConfig(StrictConfig):
    audio_directory: str = "AudioWAV"
    demographics_file: str | None = "VideoDemographics.csv"
    encoding: str = "utf-8-sig"
    label_mapping: dict[str, int] | None = None
    speaker_splits: dict[str, list[str]] | None = None


class EmotionTalkImportConfig(StrictConfig):
    json_directory: str = "json"
    audio_directory: str = "wav"
    encoding: str = "utf-8"
    label_mapping: dict[str, int] | None = None
    split_strategy: Literal["speaker_independent", "official_dialogue"] = "speaker_independent"
    speaker_splits: dict[str, list[str]] | None = None


def _default_esd_languages() -> list[Literal["zh", "en"]]:
    return ["zh", "en"]


class EsdImportConfig(StrictConfig):
    languages: list[Literal["zh", "en"]] = Field(default_factory=_default_esd_languages)
    encoding: str = "utf-8-sig"
    label_mapping: dict[str, int] | None = None
    speaker_splits: dict[str, list[str]] | None = None


class FolderImportConfig(StrictConfig):
    audio_extensions: list[str] = Field(default_factory=lambda: list(DEFAULT_AUDIO_EXTENSIONS))
    label_dir_level: int = Field(default=0, ge=0, le=2)
    speaker_dir_level: int | None = Field(default=None, ge=0, le=3)
    label_mapping: dict[str, int] | None = None
    uid_prefix: str = Field(default="audio", min_length=1)
    relative_paths: bool = True

    @field_validator("audio_extensions")
    @classmethod
    def _normalize_ext(cls, value: list[str]) -> list[str]:
        result = []
        for ext in value:
            ext = ext.lower()
            if not ext.startswith("."):
                ext = "." + ext
            result.append(ext)
        return result


class JsonlImportConfig(StrictConfig):
    uid_prefix: str = Field(default="audio", min_length=1)
    root: Path | None = None


class RavdessImportConfig(StrictConfig):
    vocal_channel: Literal["speech", "song", "all"] = "speech"
    relative_paths: bool = True


__all__ = [
    "DEFAULT_AUDIO_EXTENSIONS",
    "CasiaImportConfig",
    "CsvImportConfig",
    "CsemotionsImportConfig",
    "CremaDImportConfig",
    "EmotionTalkImportConfig",
    "EsdImportConfig",
    "FolderImportConfig",
    "JsonlImportConfig",
    "RavdessImportConfig",
]
