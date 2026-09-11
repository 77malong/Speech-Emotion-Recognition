"""SER-lib 跨领域共享的稳定异常类型。"""

from ser_lib.foundation.errors.base import OperationCancelled, RegistryError, SERError
from ser_lib.foundation.errors.config import ConfigurationError
from ser_lib.foundation.errors.data import (
    AudioDecodeError,
    AudioNotFoundError,
    CollationError,
    InvalidAudioSegmentError,
    ManifestError,
    RepresentationError,
    SERDataError,
    TransformError,
    wrap_error,
)
from ser_lib.foundation.errors.engine import CompatibilityError

__all__ = [
    "SERError",
    "OperationCancelled",
    "RegistryError",
    "ConfigurationError",
    "SERDataError",
    "ManifestError",
    "AudioNotFoundError",
    "AudioDecodeError",
    "InvalidAudioSegmentError",
    "RepresentationError",
    "TransformError",
    "CollationError",
    "wrap_error",
    "CompatibilityError",
]
