"""ser_lib.data：数据加载与表示系统（新核心）。

数据集只描述样本集合；Representation 描述输入形式；TensorSpec 描述形状契约；
Collator 根据规格批处理。import 本包即完成轻量组件注册。
"""

from ser_lib.data.audio import AudioLoader, AudioLoaderConfig
from ser_lib.data.cache import CachedRepresentation
from ser_lib.data.collate import CollateStrategy, SERCollator, build_collator
from ser_lib.data.config import AudioSettings, BatchingConfig, CacheSettings, ComponentConfig, DataConfig, load_data_config
from ser_lib.data.dataset import SERDataset
from ser_lib.data.editor import DatasetEditor
from ser_lib.data.errors import (
    AudioDecodeError, AudioNotFoundError, CollationError, CompatibilityError,
    DatasetEditConflictError, DatasetEditError, DatasetTransactionError,
    InvalidAudioSegmentError, ManifestError, RegistryError, RepresentationError,
    SERDataError, TransformError,
)
from ser_lib.data.fingerprint import DatasetFingerprint, fingerprint_manifest
from ser_lib.data.history import (
    DATASET_REVISION_SCHEMA_VERSION, DatasetRevisionCatalog, DatasetRevisionInfo,
    DatasetRevisionScanFailure, create_dataset_revision, inspect_dataset_revision,
    restore_dataset_revision, scan_dataset_revisions,
)
from ser_lib.data.importers import (
    CasiaImporter, CsvImporter, FolderImporter, ImportPreview, JsonlImporter,
    RavdessImporter, register_importers,
)
from ser_lib.data.manifest import DatasetManifest, ManifestMeta, read_jsonl, write_jsonl
from ser_lib.data.pipeline import SamplePipeline, build_components, build_pipeline
from ser_lib.data.profiling import (
    AudioProbeFailure, DatasetAudioProfile, DatasetProfile, DatasetSummary,
    DurationHistogramBin, profile_dataset, profile_manifest_audio, summarize_manifest,
)
from ser_lib.data.query import iter_records
from ser_lib.data.registry import ComponentDescriptor, Registry, default_registry
from ser_lib.data.representations import register_representations
from ser_lib.data.transforms import register_transforms
from ser_lib.data.types import (
    AudioData, AudioRecord, RepresentationOutput, SERBatch, SERSample, TensorSpec,
    validate_sample_contract,
)

register_importers()
register_representations()
register_transforms()

__all__ = [
    "AudioRecord", "AudioData", "TensorSpec", "RepresentationOutput", "SERSample", "SERBatch",
    "validate_sample_contract",
    "SERDataError", "ManifestError", "DatasetEditError", "DatasetEditConflictError",
    "DatasetTransactionError", "AudioNotFoundError", "AudioDecodeError", "InvalidAudioSegmentError",
    "RepresentationError", "TransformError", "CollationError", "CompatibilityError", "RegistryError",
    "DatasetManifest", "ManifestMeta", "read_jsonl", "write_jsonl", "DatasetEditor",
    "DATASET_REVISION_SCHEMA_VERSION", "DatasetRevisionInfo", "DatasetRevisionScanFailure",
    "DatasetRevisionCatalog", "create_dataset_revision", "inspect_dataset_revision",
    "scan_dataset_revisions", "restore_dataset_revision",
    "AudioLoader", "AudioLoaderConfig",
    "FolderImporter", "CsvImporter", "JsonlImporter", "CasiaImporter", "ImportPreview",
    "RavdessImporter", "register_importers",
    "SamplePipeline", "SERDataset", "build_pipeline", "build_components",
    "SERCollator", "CollateStrategy", "build_collator", "CachedRepresentation",
    "Registry", "default_registry", "ComponentDescriptor", "register_representations", "register_transforms",
    "DataConfig", "ComponentConfig", "AudioSettings", "CacheSettings", "BatchingConfig", "load_data_config",
    "AudioProbeFailure", "DurationHistogramBin", "DatasetAudioProfile", "DatasetSummary", "DatasetProfile",
    "profile_manifest_audio", "summarize_manifest", "profile_dataset",
    "iter_records", "DatasetFingerprint", "fingerprint_manifest",
]
