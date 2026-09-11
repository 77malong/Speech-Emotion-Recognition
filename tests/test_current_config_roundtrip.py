from pathlib import Path

import pytest
from pydantic import ValidationError

from ser_lib.config import AudioConfig, load_data_config


def test_audio_config_round_trip_unknown_field_and_config_relative_path(tmp_path: Path):
    payload = AudioConfig().model_dump(mode="json")
    assert payload == {
        "target_sample_rate": 16000,
        "mono": True,
        "normalize_peak": False,
        "backend": "soundfile",
    }
    assert AudioConfig.model_validate(payload).model_dump(mode="json") == payload

    with pytest.raises(ValidationError):
        AudioConfig.model_validate({**payload, "target_sample_rate_typo": 8000})

    config_dir = tmp_path / "configs"
    config_dir.mkdir()
    config_path = config_dir / "demo.yaml"
    config_path.write_text(
        "manifest: ../data/dataset.yaml\nrepresentation:\n  type: waveform\n",
        encoding="utf-8",
    )
    loaded = load_data_config(config_path)
    assert loaded.manifest == (config_dir / "../data/dataset.yaml").resolve()
