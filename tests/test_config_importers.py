from pathlib import Path

import pytest
from pydantic import ValidationError

from ser_lib.config import StrictConfig
from ser_lib.config.importers import (
    DEFAULT_AUDIO_EXTENSIONS,
    CasiaImportConfig,
    CremaDImportConfig,
    CsemotionsImportConfig,
    CsvImportConfig,
    EmotionTalkImportConfig,
    EsdImportConfig,
    FolderImportConfig,
    JsonlImportConfig,
    RavdessImportConfig,
)
from ser_lib.data.importers.casia import CasiaImportConfig as LegacyCasiaImportConfig
from ser_lib.data.importers.crema_d import CremaDImportConfig as LegacyCremaDImportConfig
from ser_lib.data.importers.csemotions import (
    CsemotionsImportConfig as LegacyCsemotionsImportConfig,
)
from ser_lib.data.importers.csv_importer import CsvImportConfig as LegacyCsvImportConfig
from ser_lib.data.importers.emotiontalk import (
    EmotionTalkImportConfig as LegacyEmotionTalkImportConfig,
)
from ser_lib.data.importers.esd import EsdImportConfig as LegacyEsdImportConfig
from ser_lib.data.importers.folder import (
    DEFAULT_AUDIO_EXTENSIONS as LEGACY_DEFAULT_AUDIO_EXTENSIONS,
)
from ser_lib.data.importers.folder import FolderImportConfig as LegacyFolderImportConfig
from ser_lib.data.importers.jsonl_importer import (
    JsonlImportConfig as LegacyJsonlImportConfig,
)
from ser_lib.data.importers.ravdess import RavdessImportConfig as LegacyRavdessImportConfig


IMPORTER_CONFIG_TYPES = (
    CasiaImportConfig,
    CsvImportConfig,
    CsemotionsImportConfig,
    CremaDImportConfig,
    EmotionTalkImportConfig,
    EsdImportConfig,
    FolderImportConfig,
    JsonlImportConfig,
    RavdessImportConfig,
)


def test_importer_config_legacy_paths_are_identity_aliases():
    pairs = [
        (CasiaImportConfig, LegacyCasiaImportConfig),
        (CsvImportConfig, LegacyCsvImportConfig),
        (CsemotionsImportConfig, LegacyCsemotionsImportConfig),
        (CremaDImportConfig, LegacyCremaDImportConfig),
        (EmotionTalkImportConfig, LegacyEmotionTalkImportConfig),
        (EsdImportConfig, LegacyEsdImportConfig),
        (FolderImportConfig, LegacyFolderImportConfig),
        (JsonlImportConfig, LegacyJsonlImportConfig),
        (RavdessImportConfig, LegacyRavdessImportConfig),
    ]
    assert all(current is legacy for current, legacy in pairs)
    assert DEFAULT_AUDIO_EXTENSIONS is LEGACY_DEFAULT_AUDIO_EXTENSIONS


def test_folder_import_config_preserves_defaults_and_normalization():
    config = FolderImportConfig(audio_extensions=["WAV", ".FlAc"])
    assert config.audio_extensions == [".wav", ".flac"]
    assert FolderImportConfig().audio_extensions == list(DEFAULT_AUDIO_EXTENSIONS)


def test_importer_configs_share_strict_config_contract():
    for config_type in IMPORTER_CONFIG_TYPES:
        assert issubclass(config_type, StrictConfig)
        with pytest.raises(ValidationError):
            config_type(unknown_field=True)


def test_csv_and_jsonl_config_preserve_path_roundtrip():
    csv_config = CsvImportConfig(root=Path("audio"))
    jsonl_config = JsonlImportConfig(root=Path("records"))
    assert csv_config.model_dump()["root"] == Path("audio")
    assert jsonl_config.model_dump()["root"] == Path("records")


def test_importer_configs_are_frozen_like_other_public_configs():
    config = CsvImportConfig()
    with pytest.raises(ValidationError):
        config.uid_prefix = "changed"
    assert config.uid_prefix == "audio"


def test_esd_default_languages_do_not_share_mutable_default():
    first = EsdImportConfig()
    second = EsdImportConfig()
    first.languages.append("zh")
    assert second.languages == ["zh", "en"]


def test_literal_constraints_remain_unchanged():
    with pytest.raises(ValidationError):
        EmotionTalkImportConfig(split_strategy="random")
    with pytest.raises(ValidationError):
        EsdImportConfig(languages=["fr"])
    with pytest.raises(ValidationError):
        RavdessImportConfig(vocal_channel="video")
