from __future__ import annotations

import io
import logging
from pathlib import Path

import pytest
from pydantic import Field, ValidationError

from ser_lib.config.base import StrictConfig
from ser_lib.config.loader import (
    load_yaml_mapping,
    resolve_config_path,
)
from ser_lib.foundation.errors import ManifestError, SERDataError
from ser_lib.foundation.errors import OperationCancelled, SERError
from ser_lib.foundation.events import CancellationToken, ProgressEvent
from ser_lib.foundation.logging import configure_library_logging, get_logger


class ExampleConfig(StrictConfig):
    name: str = Field(min_length=1)


def test_strict_config_rejects_unknown_fields_and_is_frozen():
    with pytest.raises(ValidationError):
        ExampleConfig(name="demo", typo=True)
    config = ExampleConfig(name="demo")
    with pytest.raises(ValidationError):
        config.name = "changed"


def test_resolve_config_path_does_not_depend_on_cwd(tmp_path: Path):
    assert resolve_config_path("nested/config.yaml", base_dir=tmp_path) == (
        tmp_path / "nested/config.yaml"
    ).resolve()


def test_load_yaml_mapping_and_validate_current_config(tmp_path: Path):
    path = tmp_path / "配置.yaml"
    path.write_text("name: example\n", encoding="utf-8")
    raw, source = load_yaml_mapping(path)
    assert raw["name"] == "example"
    assert source == path.resolve()
    assert ExampleConfig.model_validate(raw).name == "example"


def test_ser_error_has_stable_structured_form():
    error = SERError("failed", code="example_error", details={"item": 2})
    assert error.to_dict() == {
        "code": "example_error",
        "message": "failed",
        "details": {"item": 2},
    }
    data_error = ManifestError("bad manifest", uid="a")
    assert isinstance(data_error, SERDataError)
    assert isinstance(data_error, SERError)
    assert data_error.details["uid"] == "a"


def test_progress_event_validates_counts_and_calculates_fraction():
    assert ProgressEvent("decode", completed=2, total=4).fraction == 0.5
    assert ProgressEvent("scan", completed=0).fraction is None
    with pytest.raises(ValueError, match="大于"):
        ProgressEvent("decode", completed=5, total=4)


def test_cancellation_token_is_idempotent_and_raises_domain_error():
    token = CancellationToken()
    assert token.is_cancelled is False
    token.cancel()
    token.cancel()
    assert token.is_cancelled is True
    with pytest.raises(OperationCancelled):
        token.raise_if_cancelled()


def test_logging_configuration_does_not_change_root_logger():
    root = logging.getLogger()
    previous_level = root.level
    stream = io.StringIO()
    handler = configure_library_logging("INFO", stream=stream)
    try:
        get_logger("test").info("hello")
        assert "ser_lib.test" in stream.getvalue()
        assert "hello" in stream.getvalue()
        assert root.level == previous_level
    finally:
        logging.getLogger("ser_lib").removeHandler(handler)
