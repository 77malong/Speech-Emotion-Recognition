"""面向 Web/CLI/Desktop 的稳定 Python Application Service facade。"""

from ser_lib.services.artifacts import ArtifactService
from ser_lib.services.catalog import CatalogService
from ser_lib.services.datasets import DatasetService
from ser_lib.services.evaluation import EvaluationService
from ser_lib.services.inference import InferenceService
from ser_lib.services.runtime import RuntimeService
from ser_lib.services.training import TrainingService

__all__ = [
    "DatasetService",
    "TrainingService",
    "EvaluationService",
    "InferenceService",
    "ArtifactService",
    "CatalogService",
    "RuntimeService",
]
