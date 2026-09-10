# SER-lib 核心库边界审计：完整证据附录

对应 [审计与瘦身计划正文](SER_LIB_CORE_BOUNDARY_AUDIT.md)。基线 `main@77ce0edc7b2cf714fb506db1d4d8639e8dbc286d`；2026-09-09。全部清单从 Git 跟踪的源码解析，不受 `.gitignore` 漏检影响。

范围：98 个库 Python 文件、19755 行源码（含空行注释）、70 个 tests Python 文件；993 条库内 import 符号边；638 项显式 `__all__` 导出位置（同一符号可重导出多次，不是独立 API 数）。

方法：逐文件 AST 清单 + 重点实现、调用方、测试和文档阅读。静态边含局部/条件导入；直接调用解析按文件 import 名映射，不能证明实例方法或动态 factory 的完整运行时调用图。源码行号只对基线有效。本文的逐文件处理是设计决策，不是已实施状态。

## A. 完整模块审计与文件迁移表

| 模块 | 当前职责/公开定义 | 属于 SER Core | 当前问题/理由 | 最终处理 | 目标 |
| --- | --- | --- | --- | --- | --- |
| [ser_lib/__init__.py](D:/projects/Speech-Emotion-Recognition/ser_lib/__init__.py) | ser_lib：语音情感识别库。； | 部分（混合） | 聚合导出过多、版本回引；收缩根 API 并惰性解析重型导出 | 瘦身 | ser_lib/__init__.py + ser_lib/_version.py |
| [ser_lib/artifacts/__init__.py](D:/projects/Speech-Emotion-Recognition/ser_lib/artifacts/__init__.py) | 公开导出/注册入口； | 部分（混合） | 更新 config/退役包装导出及内置注册顺序，不改变算法 | 瘦身 | 原路径 |
| [ser_lib/artifacts/catalog.py](D:/projects/Speech-Emotion-Recognition/ser_lib/artifacts/catalog.py) | 无需加载/Hash 权重的本地 Artifact Catalog 扫描。；ArtifactInfo, ArtifactScanFailure, ArtifactCatalog, scan_model_artifacts | 部分（混合） | 保留扫描，ArtifactInfo 扁平复制改最小 entry+manifest | 瘦身 | 原路径 |
| [ser_lib/artifacts/exporter.py](D:/projects/Speech-Emotion-Recognition/ser_lib/artifacts/exporter.py) | 将模型、预处理和标签原子导出为安全 artifact。；export_model_artifact | 部分（混合） | 接回通用 provenance，版本不回引根包；hash 私有重复收敛 | 瘦身 | 原路径 |
| [ser_lib/artifacts/loader.py](D:/projects/Speech-Emotion-Recognition/ser_lib/artifacts/loader.py) | 快速检查、完整校验并加载模型 artifact。；LoadedArtifact, inspect_model_artifact, verify_model_artifact, load_model_artifact | 部分（混合） | 保留 inspect/verify/load 分层、legacy 门禁；旧 hash 壳按引用清理 | 瘦身 | 原路径 + ser_lib/artifacts/migrations.py |
| [ser_lib/artifacts/manifest.py](D:/projects/Speech-Emotion-Recognition/ser_lib/artifacts/manifest.py) | 可移植模型 artifact 的版本化 manifest。；ModelCard, ModelArtifactManifest | 是 | ModelCard/Manifest 是 metadata，不迁 config；去 StrictConfig 继承误导 | 保留 | 原路径 |
| [ser_lib/benchmark.py](D:/projects/Speech-Emotion-Recognition/ser_lib/benchmark.py) | 可序列化的微基准结果与回归比较工具。；BenchmarkResult, BenchmarkComparison, run_benchmark, compare_benchmarks, write_benchmark_result, load_benchmark_result | 是 | SER 性能测量与比较可用于脚本；归执行辅助 | 迁移 | ser_lib/engine/benchmark.py |
| [ser_lib/catalog.py](D:/projects/Speech-Emotion-Recognition/ser_lib/catalog.py) | 供 Web/CLI 查询的统一组件目录。；ComponentCatalog, get_component_catalog, list_component_descriptors | 否（应用包装） | 跨领域描述重复包装；CLI 改原生 introspection | 删除 | 各领域 registry + config schema |
| [ser_lib/cli/__init__.py](D:/projects/Speech-Emotion-Recognition/ser_lib/cli/__init__.py) | SER 基础库命令行入口。； | 部分（混合） | 更新 config/退役包装导出及内置注册顺序，不改变算法 | 瘦身 | 原路径 |
| [ser_lib/cli/__main__.py](D:/projects/Speech-Emotion-Recognition/ser_lib/cli/__main__.py) | 模块入口/领域实现； | 是 | 实际为 SER 数据/执行基础，无确认的页面专属职责；更新被迁移 import | 保留 | 原路径 |
| [ser_lib/cli/main.py](D:/projects/Speech-Emotion-Recognition/ser_lib/cli/main.py) | 不复制领域逻辑的 ``ser`` 命令行界面。；main | 部分（混合） | 参数/配置/输出适配；组件列表直接 registry | 瘦身 | 原路径 |
| [ser_lib/cli/workflows.py](D:/projects/Speech-Emotion-Recognition/ser_lib/cli/workflows.py) | CLI 的薄编排层；领域行为统一通过 Service facade。；train_experiment, evaluate_artifact, predict_artifact, export_checkpoint_artifact, inspect_artifact | 部分（混合） | 移出可复用训练编排；直接 public API；验证集不再重复构造模型 | 拆分 | 原路径 + ser_lib/engine/experiment.py |
| [ser_lib/core/__init__.py](D:/projects/Speech-Emotion-Recognition/ser_lib/core/__init__.py) | SER 基础库的轻量公共基础设施。； | 旧入口 | 旧包导出全部迁移后删除 | 删除 | foundation/config/各领域公共入口 |
| [ser_lib/core/_catalog_scan.py](D:/projects/Speech-Emotion-Recognition/ser_lib/core/_catalog_scan.py) | Catalog 扫描器共享控制流；领域 candidate、DTO 与排序规则保持独立。；scan_catalog_candidates | 部分（混合） | 去跨领域 Catalog 协议，保留取消/失败隔离 | 拆分 | data/history.py; engine/*catalog.py/runs.py; artifacts/catalog.py 内私有循环 |
| [ser_lib/core/config.py](D:/projects/Speech-Emotion-Recognition/ser_lib/core/config.py) | 基础配置、版本检查和确定性路径解析。；StrictConfig, resolve_config_path, require_schema_version, load_yaml_mapping, load_versioned_config | 部分（混合） | 用户配置和读取器不属于 foundation | 拆分 | ser_lib/config/base.py; ser_lib/config/loader.py |
| [ser_lib/core/diagnostics.py](D:/projects/Speech-Emotion-Recognition/ser_lib/core/diagnostics.py) | 面向 CLI/Web 的结构化诊断协议。；Diagnostic | 是 | 结构化诊断保留，去 UI 专属措辞 | 迁移 | ser_lib/foundation/diagnostics.py |
| [ser_lib/core/events.py](D:/projects/Speech-Emotion-Recognition/ser_lib/core/events.py) | 与传输方式无关的进度、指标、日志、生命周期和取消协议。；EventContext, ProgressEvent, MetricEvent, LogEvent, LifecycleEvent, CheckpointEvent, PredictionEvent, CancellationCheck, CancellationToken | 部分（混合） | 通用事件/取消与 checkpoint/prediction 事件分属不同层 | 拆分 | ser_lib/foundation/events.py; ser_lib/engine/events.py; ser_lib/inference/events.py |
| [ser_lib/core/exceptions.py](D:/projects/Speech-Emotion-Recognition/ser_lib/core/exceptions.py) | 整个 SER 基础库共享的异常类型。；SERError, ConfigurationError, SchemaMigrationError, OperationCancelled | 是 | 公共异常基础，不携带领域执行逻辑 | 迁移 | ser_lib/foundation/errors.py |
| [ser_lib/core/logging.py](D:/projects/Speech-Emotion-Recognition/ser_lib/core/logging.py) | 不会擅自配置宿主应用 root logger 的日志工具。；get_logger, configure_library_logging | 是 | 显式库日志 helper 保留 | 迁移 | ser_lib/foundation/logging.py |
| [ser_lib/core/migrations.py](D:/projects/Speech-Emotion-Recognition/ser_lib/core/migrations.py) | 集中、显式的持久化 schema migration 基础设施。；SchemaMigration, MigrationRegistry, validate_schema_version, register_schema_migration, list_schema_migrations, migrate_schema_payload | 部分（混合） | 全局格式注册回归领域，禁止 foundation migrations | 拆分 | ser_lib/{config,data,engine,artifacts}/migrations.py |
| [ser_lib/data/__init__.py](D:/projects/Speech-Emotion-Recognition/ser_lib/data/__init__.py) | ser_lib.data：数据加载与表示系统（新核心）。； | 部分（混合） | 更新 config/退役包装导出及内置注册顺序，不改变算法 | 瘦身 | 原路径 |
| [ser_lib/data/audio.py](D:/projects/Speech-Emotion-Recognition/ser_lib/data/audio.py) | AudioLoader：音频解码、片段读取、声道转换与重采样（设计文档 §7）。；AudioFileInfo, probe_audio, decode_audio, AudioLoaderConfig, AudioLoader | 部分（混合） | AudioLoaderConfig 与 AudioSettings 四字段重复 | 拆分 | ser_lib/data/audio.py + ser_lib/config/data.py |
| [ser_lib/data/cache.py](D:/projects/Speech-Emotion-Recognition/ser_lib/data/cache.py) | 确定性 Representation 的磁盘缓存装饰器。；CachedRepresentation | 是 | 实际为 SER 数据/执行基础，无确认的页面专属职责；更新被迁移 import | 保留 | 原路径 |
| [ser_lib/data/collate.py](D:/projects/Speech-Emotion-Recognition/ser_lib/data/collate.py) | 通用 Collator：根据 TensorSpec 批处理，不根据 Dataset 类型分支（§11）。；CollateStrategy, SERCollator, build_collator | 是 | 实际为 SER 数据/执行基础，无确认的页面专属职责；更新被迁移 import | 保留 | 原路径 |
| [ser_lib/data/config.py](D:/projects/Speech-Emotion-Recognition/ser_lib/data/config.py) | 数据模块强类型配置（设计文档 §12.1）。；ComponentConfig, AudioSettings, CacheSettings, FixedBatching, SlidingBatching, BatchingConfig, DataConfig, load_data_config | 是 | 所有用户 schema 中央定义；Audio 两套配置合并 | 迁移 | ser_lib/config/data.py |
| [ser_lib/data/dataset.py](D:/projects/Speech-Emotion-Recognition/ser_lib/data/dataset.py) | SERDataset：唯一的核心 Dataset（设计文档 §10）。；SERDataset | 是 | 实际为 SER 数据/执行基础，无确认的页面专属职责；更新被迁移 import | 保留 | 原路径 |
| [ser_lib/data/editor.py](D:/projects/Speech-Emotion-Recognition/ser_lib/data/editor.py) | 面向 Web/CLI 的 Dataset 编辑器与多文件事务提交。；DatasetEditor | 是 | 事务编辑、乐观并发、回滚保留 | 保留 | 原路径 |
| [ser_lib/data/errors.py](D:/projects/Speech-Emotion-Recognition/ser_lib/data/errors.py) | SER 数据模块异常层级。；SERDataError, ManifestError, DatasetEditError, DatasetEditConflictError, DatasetTransactionError, AudioNotFoundError, AudioDecodeError, InvalidAudioSegmentError, RepresentationError, TransformError, CollationError, CompatibilityError, RegistryError, wrap_error | 部分（混合） | RegistryError 跨模型/数据共用；CompatibilityError 跨域归位 | 拆分 | 原路径 + foundation/errors.py + engine/compatibility.py |
| [ser_lib/data/fingerprint.py](D:/projects/Speech-Emotion-Recognition/ser_lib/data/fingerprint.py) | 标准 manifest 的轻量数据版本指纹。；DatasetFingerprint, fingerprint_manifest | 是 | 清单文件指纹保留，不把它描述为音频内容指纹 | 保留 | 原路径 |
| [ser_lib/data/history.py](D:/projects/Speech-Emotion-Recognition/ser_lib/data/history.py) | 标准 Dataset 的轻量 manifest 版本快照、历史扫描与安全恢复。；DatasetRevisionInfo, DatasetRevisionScanFailure, DatasetRevisionCatalog, create_dataset_revision, inspect_dataset_revision, scan_dataset_revisions, restore_dataset_revision | 是 | manifest 修订/事务恢复真实价值；不备份音频 | 保留 | 原路径 + ser_lib/data/migrations.py |
| [ser_lib/data/importers/__init__.py](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/__init__.py) | Importer 子包：注册全部 importer 到默认注册表。；register_importers | 部分（混合） | 更新 config/退役包装导出及内置注册顺序，不改变算法 | 瘦身 | 原路径 |
| [ser_lib/data/importers/_conversion.py](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/_conversion.py) | Importer convert 阶段共享编排；只处理通用写盘，不包含数据集解析规则。；run_manifest_conversion, run_single_manifest_conversion, write_partitioned_manifest | 是 | 实际为 SER 数据/执行基础，无确认的页面专属职责；更新被迁移 import | 保留 | 原路径 |
| [ser_lib/data/importers/base.py](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/base.py) | Importer 公共协议、预览结构与长任务可观察性工具。；ImportPreview, ImportTask, DatasetImporter | 是 | 实际为 SER 数据/执行基础，无确认的页面专属职责；更新被迁移 import | 保留 | 原路径 |
| [ser_lib/data/importers/casia.py](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/casia.py) | CASIA 说话人/情感目录导入器。；CasiaImportConfig, CasiaImporter | 部分（混合） | 算法/组件注册保留，内嵌用户 schema 中央化 | 拆分 | 原路径 + ser_lib/config/importers.py |
| [ser_lib/data/importers/crema_d.py](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/crema_d.py) | CREMA-D AudioWAV filename and demographic metadata importer.；CremaDImportConfig, CremaDImporter | 部分（混合） | 算法/组件注册保留，内嵌用户 schema 中央化 | 拆分 | 原路径 + ser_lib/config/importers.py |
| [ser_lib/data/importers/csemotions.py](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/csemotions.py) | CSEMOTIONS metadata importer with speaker-independent splits.；CsemotionsImportConfig, CsemotionsImporter | 部分（混合） | 算法/组件注册保留，内嵌用户 schema 中央化 | 拆分 | 原路径 + ser_lib/config/importers.py |
| [ser_lib/data/importers/csv_importer.py](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/csv_importer.py) | CSV importer：映射音频路径列、标签列与可选元数据列。；CsvImportConfig, CsvImporter | 部分（混合） | 算法/组件注册保留，内嵌用户 schema 中央化 | 拆分 | 原路径 + ser_lib/config/importers.py |
| [ser_lib/data/importers/emotiontalk.py](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/emotiontalk.py) | BAAI EmotionTalk JSON/WAV importer.；EmotionTalkImportConfig, EmotionTalkImporter | 部分（混合） | 算法/组件注册保留，内嵌用户 schema 中央化 | 拆分 | 原路径 + ser_lib/config/importers.py |
| [ser_lib/data/importers/esd.py](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/esd.py) | Emotional Speech Dataset (ESD) directory importer.；EsdImportConfig, EsdImporter | 部分（混合） | 算法/组件注册保留，内嵌用户 schema 中央化 | 拆分 | 原路径 + ser_lib/config/importers.py |
| [ser_lib/data/importers/folder.py](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/folder.py) | 目录扫描 importer：按目录结构与文件名规则导入。；FolderImportConfig, FolderImporter | 部分（混合） | 算法/组件注册保留，内嵌用户 schema 中央化 | 拆分 | 原路径 + ser_lib/config/importers.py |
| [ser_lib/data/importers/jsonl_importer.py](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/jsonl_importer.py) | JSONL importer：校验标准或近似标准 manifest。；JsonlImportConfig, normalize_raw_record, normalize_raw_records, JsonlImporter | 部分（混合） | 算法/组件注册保留，内嵌用户 schema 中央化 | 拆分 | 原路径 + ser_lib/config/importers.py |
| [ser_lib/data/importers/ravdess.py](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/ravdess.py) | RAVDESS 官方七段文件名格式适配器。；RavdessImportConfig, RavdessImporter | 部分（混合） | 算法/组件注册保留，内嵌用户 schema 中央化 | 拆分 | 原路径 + ser_lib/config/importers.py |
| [ser_lib/data/manifest.py](D:/projects/Speech-Emotion-Recognition/ser_lib/data/manifest.py) | 标准 Manifest：JSONL 记录 + dataset.yaml 元信息（设计文档 §6）。；ManifestMeta, parse_record, write_jsonl, read_jsonl, load_meta, DatasetManifest | 部分（混合） | 持久化元数据保留，迁移逻辑按领域 | 瘦身 | 原路径 + ser_lib/data/migrations.py |
| [ser_lib/data/pipeline.py](D:/projects/Speech-Emotion-Recognition/ser_lib/data/pipeline.py) | SamplePipeline：串联波形 transform → Representation → 特征 transform。；SamplePipeline, build_representation, build_pipeline, build_components | 是 | 实际为 SER 数据/执行基础，无确认的页面专属职责；更新被迁移 import | 保留 | 原路径 |
| [ser_lib/data/profiling.py](D:/projects/Speech-Emotion-Recognition/ser_lib/data/profiling.py) | 标准 manifest 的轻量摘要与可视化详细 profiling。；AudioProbeFailure, DurationHistogramBin, DatasetAudioProfile, DatasetSummary, DatasetProfile, profile_manifest_audio, summarize_manifest, profile_dataset | 部分（混合） | 保留分布/时长统计，合并 summary/profile 重复，去展示派生字段 | 瘦身 | ser_lib/data/profiling.py |
| [ser_lib/data/query.py](D:/projects/Speech-Emotion-Recognition/ser_lib/data/query.py) | 面向数据浏览器的稳定查询与分页 DTO。；RecordView, RecordPage, query_records | 部分（混合） | 删除 RecordView/RecordPage/_to_view，保留记录过滤 | 重构 | ser_lib/data/query.py:iter_records |
| [ser_lib/data/registry.py](D:/projects/Speech-Emotion-Recognition/ser_lib/data/registry.py) | 组件注册表与组件描述符（设计文档 §12.2、§12.3）。；ComponentDescriptor, ComponentEntry, Registry | 是 | 实际为 SER 数据/执行基础，无确认的页面专属职责；更新被迁移 import | 保留 | 原路径 |
| [ser_lib/data/representations/__init__.py](D:/projects/Speech-Emotion-Recognition/ser_lib/data/representations/__init__.py) | Representation 子包：全部表示组件与注册入口。；register_representations | 部分（混合） | 更新 config/退役包装导出及内置注册顺序，不改变算法 | 瘦身 | 原路径 |
| [ser_lib/data/representations/acoustic.py](D:/projects/Speech-Emotion-Recognition/ser_lib/data/representations/acoustic.py) | 声学帧级特征表示：F0、RMS、ZCR、谱特征与全局音质向量。；AcousticFeaturesConfig, AcousticFeatures | 部分（混合） | 算法/组件注册保留，内嵌用户 schema 中央化 | 拆分 | 原路径 + ser_lib/config/representations.py |
| [ser_lib/data/representations/base.py](D:/projects/Speech-Emotion-Recognition/ser_lib/data/representations/base.py) | Representation 基类（设计文档 §9.1）。；Representation | 是 | 实际为 SER 数据/执行基础，无确认的页面专属职责；更新被迁移 import | 保留 | 原路径 |
| [ser_lib/data/representations/composite.py](D:/projects/Speech-Emotion-Recognition/ser_lib/data/representations/composite.py) | CompositeRepresentation：组合多个子表示，支持不等长时间轴（设计文档 §9.4）。；CompositeConfig, CompositeRepresentation | 部分（混合） | 算法/组件注册保留，内嵌用户 schema 中央化 | 拆分 | 原路径 + ser_lib/config/representations.py |
| [ser_lib/data/representations/spectral.py](D:/projects/Speech-Emotion-Recognition/ser_lib/data/representations/spectral.py) | 谱图类表示：Spectrogram、MelSpectrogram、LogMel、MFCC（设计文档 §9.2）。；SpectralConfigBase, SpectrogramConfig, MelConfig, LogMelConfig, MFCCConfig, SpectrogramRepresentation, MelSpectrogramRepresentation, LogMelRepresentation, MFCCRepresentation | 部分（混合） | 算法/组件注册保留，内嵌用户 schema 中央化 | 拆分 | 原路径 + ser_lib/config/representations.py |
| [ser_lib/data/representations/waveform.py](D:/projects/Speech-Emotion-Recognition/ser_lib/data/representations/waveform.py) | RawWaveform 表示：输出原始波形 ``[T]``（设计文档 §9.2）。；RawWaveformConfig, RawWaveform | 部分（混合） | 算法/组件注册保留，内嵌用户 schema 中央化 | 拆分 | 原路径 + ser_lib/config/representations.py |
| [ser_lib/data/transforms/__init__.py](D:/projects/Speech-Emotion-Recognition/ser_lib/data/transforms/__init__.py) | Transform 子包：注册全部 transform 到默认注册表。；register_transforms | 部分（混合） | 更新 config/退役包装导出及内置注册顺序，不改变算法 | 瘦身 | 原路径 |
| [ser_lib/data/transforms/base.py](D:/projects/Speech-Emotion-Recognition/ser_lib/data/transforms/base.py) | Transform 公共设施：RandomApply 概率包装器与流水线（设计文档 §8.2）。；RandomApply, WaveformTransformPipeline, FeatureTransformPipeline, validate_feature_transform_layouts | 是 | 实际为 SER 数据/执行基础，无确认的页面专属职责；更新被迁移 import | 保留 | 原路径 |
| [ser_lib/data/transforms/feature.py](D:/projects/Speech-Emotion-Recognition/ser_lib/data/transforms/feature.py) | 特征级 transform（设计文档 §8.1、T3.3）。；SpecMaskingConfig, SpecMasking | 部分（混合） | 算法/组件注册保留，内嵌用户 schema 中央化 | 拆分 | 原路径 + ser_lib/config/transforms.py |
| [ser_lib/data/transforms/waveform.py](D:/projects/Speech-Emotion-Recognition/ser_lib/data/transforms/waveform.py) | 波形级 transform（设计文档 §8.1、T3.3）。；NormalizeConfig, GaussianNoiseConfig, TimeShiftConfig, VolumeScaleConfig, PitchShiftConfig, TimeStretchConfig, Normalize, AddGaussianNoise, TimeShift, VolumeScale, PitchShift, TimeStretch | 部分（混合） | 算法/组件注册保留，内嵌用户 schema 中央化 | 拆分 | 原路径 + ser_lib/config/transforms.py |
| [ser_lib/data/types.py](D:/projects/Speech-Emotion-Recognition/ser_lib/data/types.py) | SER 数据模块核心公开类型（设计文档 §5，契约冻结）。；time_axis_of, is_temporal, AudioRecord, AudioData, TensorSpec, validate_representation_output, RepresentationOutput, SERSample, SERBatch, validate_sample_contract | 是 | 实际为 SER 数据/执行基础，无确认的页面专属职责；更新被迁移 import | 保留 | 原路径 |
| [ser_lib/data/validation.py](D:/projects/Speech-Emotion-Recognition/ser_lib/data/validation.py) | 模型兼容性契约（设计文档 §13）。；ModelSpec, CompatibilityReport, inspect_compatibility, validate_compatibility | 部分（混合） | ModelSpec 与跨域兼容检查归位，data 不回引 engine | 拆分 | ser_lib/models/specs.py + ser_lib/engine/compatibility.py |
| [ser_lib/engine/__init__.py](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/__init__.py) | 公开导出/注册入口； | 部分（混合） | 更新 config/退役包装导出及内置注册顺序，不改变算法 | 瘦身 | 原路径 |
| [ser_lib/engine/_trainer_core.py](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/_trainer_core.py) | 表示无关、可观测且可取消的 SER 分类训练内部核心。；EpochResult, TrainingResult, seed_everything, move_batch_to_device, Trainer | 是 | 只有一套循环；保留全部 resume/AMP/状态，batch helper 回 data | 合并 | ser_lib/engine/trainer.py + ser_lib/engine/state.py + data/types.py:move_batch_to_device |
| [ser_lib/engine/checkpoint.py](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/checkpoint.py) | 可信本地训练 checkpoint 的原子保存与完整恢复。；save_checkpoint, load_checkpoint | 是 | v1/v2 保存恢复保留；Adapter 键/配置兼容需新增验收 | 保留 | 原路径 |
| [ser_lib/engine/checkpoint_catalog.py](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/checkpoint_catalog.py) | 训练 checkpoint 的轻量文件系统检查与 Catalog 扫描。；CheckpointInfo, CheckpointScanFailure, CheckpointCatalog, inspect_checkpoint_file, scan_checkpoints | 是 | stat 级扫描保留；文件名 epoch 不是 payload epoch | 保留 | 原路径 |
| [ser_lib/engine/config.py](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/config.py) | 版本化实验配置。；ModelConfig, ObservabilityConfig, TrainerConfig, ExperimentConfig, ExperimentComponents, build_experiment_components, load_experiment_config | 部分（混合） | config schema 与 ExperimentComponents/build 分离 | 拆分 | ser_lib/config/{experiment,model,training,loader}.py + ser_lib/engine/experiment.py |
| [ser_lib/engine/eta.py](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/eta.py) | 训练/评估进度使用的有界 ETA 估计器。；EtaSnapshot, EtaEstimator | 是 | 长任务估时有 CLI/SDK 价值 | 保留 | 原路径 |
| [ser_lib/engine/evaluation_catalog.py](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/evaluation_catalog.py) | 已落盘 evaluation.json 的轻量 Catalog 扫描。；EvaluationRunScanFailure, EvaluationRunCatalog, scan_evaluation_runs | 是 | 真实 evaluation.json 扫描，不扩展页面组合 | 保留 | 原路径 |
| [ser_lib/engine/evaluation_detail.py](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/evaluation_detail.py) | 评估运行的轻量详情聚合 DTO 与 prediction 文件元数据。；EvaluationPredictionFileInfo, EvaluationRunDetail, inspect_evaluation_prediction_file | 部分（混合） | 删除 EvaluationRunDetail；prediction stat metadata 合并到 reports | 拆分 | ser_lib/engine/evaluation_reports.py |
| [ser_lib/engine/evaluation_reports.py](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/evaluation_reports.py) | 已落盘评估报告的轻量检查与预测分页查询接口。；EvaluationReportInfo, EvaluationPredictionPage, inspect_evaluation_report, query_evaluation_predictions | 部分（混合） | 删除 Page，保留严格 JSONL 校验与过滤 | 拆分 | 原路径:iter_evaluation_predictions + report inspection |
| [ser_lib/engine/evaluation_runs.py](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/evaluation_runs.py) | 评估运行的稳定 lineage、终态记录与原子持久化。；EvaluationRunMetadata, EvaluationRunInfo, build_evaluation_run_metadata, write_evaluation_run_info, load_evaluation_run_info | 是 | 真实评估记录，library_version 默认回归 metadata builder | 保留 | 原路径 + ser_lib/engine/migrations.py |
| [ser_lib/engine/evaluator.py](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/evaluator.py) | SER 分类模型评估、样本预测和机器可读报告。；ClassMetrics, PredictionRecord, PredictionSink, JsonlPredictionSink, EvaluationResult, evaluate, write_evaluation_report | 部分（混合） | 保留 evaluate/metrics/sink/report，消除对 Trainer helper 的依赖 | 瘦身 | 原路径；batch helper 改从 data/types.py 导入 |
| [ser_lib/engine/lineage.py](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/lineage.py) | 训练运行的可追踪元数据。；TrainingRunMetadata, build_training_run_metadata | 是 | 可复现来源/配置指纹，不是页面对象 | 保留 | 原路径 |
| [ser_lib/engine/objectives.py](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/objectives.py) | Classification losses and imbalance-aware sampling.；LossConfig, SamplingConfig, ClassificationLoss, build_weighted_sampler | 部分（混合） | LossConfig/SamplingConfig 中央化，计算不搬 | 拆分 | 原路径 + ser_lib/config/training.py |
| [ser_lib/engine/optim.py](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/optim.py) | 白名单优化器和学习率调度器配置。；AdamWConfig, AdamConfig, SGDConfig, StepSchedulerConfig, CosineSchedulerConfig, parse_optimizer_config, build_optimizer, parse_scheduler_config, build_scheduler | 部分（混合） | schema/parse 与 torch build 分离，消除 config 回引 | 拆分 | 原路径 + ser_lib/config/{optimizer,scheduler}.py |
| [ser_lib/engine/presets.py](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/presets.py) | 稳定实验预设目录；所有预设最终都构造现有 ExperimentConfig。；ExperimentPresetInfo, ExperimentPresetCatalog, list_experiment_presets, get_experiment_preset, build_experiment_config | 是 | 模板保留，去 ExperimentPresetCatalog 聚合壳 | 迁移 | ser_lib/config/presets.py |
| [ser_lib/engine/runs.py](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/runs.py) | 训练运行记录的原子持久化、轻量 Catalog 扫描与详情聚合 DTO。；TrainingRunInfo, TrainingRunDetail, TrainingRunScanFailure, TrainingRunCatalog, write_training_run_info, load_training_run_info, scan_training_runs | 部分（混合） | 删除 TrainingRunDetail；run.json/read/write/scan 保留 | 拆分 | 原路径 + ser_lib/engine/migrations.py |
| [ser_lib/engine/trainer.py](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/trainer.py) | 统一 Trainer 公开实现：训练循环、optimizer 和 lineage 只保留一条正式路径。；Trainer | 是 | 合并公开/内部继承包装；fit 直接返回 TrainingResult | 合并 | ser_lib/engine/trainer.py + ser_lib/engine/state.py |
| [ser_lib/engine/training_history.py](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/training_history.py) | 已完成训练的 history.json 严格读取与曲线 DTO。；TrainingHistoryInfo, load_training_history | 是 | epoch 历史和校验保留 | 保留 | 原路径 |
| [ser_lib/engine/validation.py](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/validation.py) | 实验启动前的无副作用 dry-run 校验。；ExperimentValidationResult, validate_experiment | 部分（混合） | 预检保留，summary 去重复，补 adapter capability | 瘦身 | 原路径 + ser_lib/engine/compatibility.py |
| [ser_lib/inference/__init__.py](D:/projects/Speech-Emotion-Recognition/ser_lib/inference/__init__.py) | 公开导出/注册入口； | 部分（混合） | 更新 config/退役包装导出及内置注册顺序，不改变算法 | 瘦身 | 原路径 |
| [ser_lib/inference/batch.py](D:/projects/Speech-Emotion-Recognition/ser_lib/inference/batch.py) | 批量离线推理、增量结果 sink 与 JSONL/CSV 结果导出。；PredictionFailure, BatchPredictionSink, JsonlBatchPredictionSink, BatchPredictionResult, BatchEmotionPredictor, write_batch_predictions | 是 | 批量与 sink/有限内存保留，Service 改直接调用 | 保留 | 原路径 |
| [ser_lib/inference/offline.py](D:/projects/Speech-Emotion-Recognition/ser_lib/inference/offline.py) | 复用训练 Pipeline 的离线推理入口。；PredictionResult, EmotionPredictor | 部分（混合） | 预测核心保留，接回 from_loaded_artifact 便利构造 | 重构 | 原路径 |
| [ser_lib/inference/streaming.py](D:/projects/Speech-Emotion-Recognition/ser_lib/inference/streaming.py) | 与设备和 UI 无关的纯 PCM 流式 SER 核心。；StreamingConfig, StreamingPrediction, StreamingLatency, StreamingEmotionRecognizer | 部分（混合） | PCM 流式核心保留，StreamingConfig 中央化 | 拆分 | 原路径 + ser_lib/config/inference.py |
| [ser_lib/models/__init__.py](D:/projects/Speech-Emotion-Recognition/ser_lib/models/__init__.py) | 公开导出/注册入口； | 部分（混合） | 更新 config/退役包装导出及内置注册顺序，不改变算法 | 瘦身 | 原路径 |
| [ser_lib/models/base.py](D:/projects/Speech-Emotion-Recognition/ser_lib/models/base.py) | SER 模型公共契约。；ModelOutput, SERModel | 是 | 统一输出已有；不建立第二套执行契约 | 保留 | 原路径 + ser_lib/models/specs.py |
| [ser_lib/models/cnn_models.py](D:/projects/Speech-Emotion-Recognition/ser_lib/models/cnn_models.py) | 适用于 MFCC/Mel/Log-Mel 的轻量卷积基线。；CNNBaselineConfig, CNNBaseline | 部分（混合） | 原生模型保留，仅配置定义中央化 | 拆分 | 原路径 + ser_lib/config/model.py |
| [ser_lib/models/pretrained.py](D:/projects/Speech-Emotion-Recognition/ser_lib/models/pretrained.py) | 可选的 Hugging Face 预训练语音编码器适配。；HFAudioClassifierConfig, HFAudioClassifier | 部分（混合） | 保留注册 ID/旧重建语义，补 processor/真实长度映射 | 拆分 | ser_lib/models/adapters/huggingface.py + ser_lib/config/model.py |
| [ser_lib/models/registry.py](D:/projects/Speech-Emotion-Recognition/ser_lib/models/registry.py) | 模型注册表。；ModelDescriptor, ModelRegistry | 部分（混合） | 唯一模型注册；补 capability/plugin metadata，配置引用中央化 | 重构 | 原路径 |
| [ser_lib/models/rnn_models.py](D:/projects/Speech-Emotion-Recognition/ser_lib/models/rnn_models.py) | 适用于帧级声学表示的循环神经网络基线。；GRUBaselineConfig, GRUBaseline | 部分（混合） | 原生模型保留，仅配置定义中央化 | 拆分 | 原路径 + ser_lib/config/model.py |
| [ser_lib/models/transformer_models.py](D:/projects/Speech-Emotion-Recognition/ser_lib/models/transformer_models.py) | 适用于帧级声学特征的轻量 Transformer 编码器。；TransformerBaselineConfig, TransformerBaseline | 部分（混合） | 原生模型保留，仅配置定义中央化 | 拆分 | 原路径 + ser_lib/config/model.py |
| [ser_lib/runtime.py](D:/projects/Speech-Emotion-Recognition/ser_lib/runtime.py) | 面向 CLI/Web 的轻量运行环境能力与资源快照。；RuntimeDevice, RuntimeCapabilities, RuntimeMetrics, get_runtime_capabilities, get_runtime_metrics | 是 | 按需设备/host metrics 保留，不创建监控产品 | 迁移 | ser_lib/engine/runtime.py |
| [ser_lib/services/__init__.py](D:/projects/Speech-Emotion-Recognition/ser_lib/services/__init__.py) | 面向 Web/CLI/Desktop 的稳定 Python Application Service facade。； | 否（应用包装） | 先迁真实行为/消费者/测试，再退役 facade | 删除 | 相应 data/engine/inference/artifacts/config public API |
| [ser_lib/services/artifacts.py](D:/projects/Speech-Emotion-Recognition/ser_lib/services/artifacts.py) | 模型 Artifact 应用服务。；ArtifactService | 否（应用包装） | 先迁真实行为/消费者/测试，再退役 facade | 删除 | 相应 data/engine/inference/artifacts/config public API |
| [ser_lib/services/catalog.py](D:/projects/Speech-Emotion-Recognition/ser_lib/services/catalog.py) | 统一组件 Catalog 与实验 Preset 的应用服务。；CatalogService | 否（应用包装） | 先迁真实行为/消费者/测试，再退役 facade | 删除 | 相应 data/engine/inference/artifacts/config public API |
| [ser_lib/services/datasets.py](D:/projects/Speech-Emotion-Recognition/ser_lib/services/datasets.py) | 数据集应用服务：为 Web/CLI 提供稳定的领域入口。；DatasetService | 否（应用包装） | 先迁真实行为/消费者/测试，再退役 facade | 删除 | 相应 data/engine/inference/artifacts/config public API |
| [ser_lib/services/evaluation.py](D:/projects/Speech-Emotion-Recognition/ser_lib/services/evaluation.py) | 评估应用服务。；EvaluationService | 否（应用包装） | 先迁真实行为/消费者/测试，再退役 facade | 删除 | 相应 data/engine/inference/artifacts/config public API |
| [ser_lib/services/inference.py](D:/projects/Speech-Emotion-Recognition/ser_lib/services/inference.py) | 离线、批量与流式推理应用服务。；InferenceService | 否（应用包装） | 先迁真实行为/消费者/测试，再退役 facade | 删除 | 相应 data/engine/inference/artifacts/config public API |
| [ser_lib/services/runtime.py](D:/projects/Speech-Emotion-Recognition/ser_lib/services/runtime.py) | 运行环境能力与资源快照应用服务。；RuntimeService | 否（应用包装） | 先迁真实行为/消费者/测试，再退役 facade | 删除 | 相应 data/engine/inference/artifacts/config public API |
| [ser_lib/services/training.py](D:/projects/Speech-Emotion-Recognition/ser_lib/services/training.py) | 训练应用服务：稳定 dry-run、Trainer 构造、lineage、历史记录和终态结果入口。；TrainingService | 否（应用包装） | 先迁真实行为/消费者/测试，再退役 facade | 删除 | 相应 data/engine/inference/artifacts/config public API |

## B. 完整配置定义清单

| 当前类型 | 定义 | 用户配置 | 目标位置 | 当前直接字段 |
| --- | --- | --- | --- | --- |
| `StrictConfig` | [ser_lib/core/config.py:14](D:/projects/Speech-Emotion-Recognition/ser_lib/core/config.py:14) | 配置基类 | ser_lib/config/base.py | 继承字段/无参数严格 schema |
| `AudioLoaderConfig` | [ser_lib/data/audio.py:159](D:/projects/Speech-Emotion-Recognition/ser_lib/data/audio.py:159) | 是 | ser_lib/config/data.py | target_sample_rate, mono, normalize_peak, backend |
| `_StrictModel` | [ser_lib/data/config.py:21](D:/projects/Speech-Emotion-Recognition/ser_lib/data/config.py:21) | 配置基类 | ser_lib/config/data.py | 继承字段/无参数严格 schema |
| `ComponentConfig` | [ser_lib/data/config.py:25](D:/projects/Speech-Emotion-Recognition/ser_lib/data/config.py:25) | 是 | ser_lib/config/data.py | type, params, probability |
| `AudioSettings` | [ser_lib/data/config.py:39](D:/projects/Speech-Emotion-Recognition/ser_lib/data/config.py:39) | 是 | ser_lib/config/data.py | target_sample_rate, mono, normalize_peak, backend |
| `CacheSettings` | [ser_lib/data/config.py:50](D:/projects/Speech-Emotion-Recognition/ser_lib/data/config.py:50) | 是 | ser_lib/config/data.py | enabled, directory |
| `FixedBatching` | [ser_lib/data/config.py:57](D:/projects/Speech-Emotion-Recognition/ser_lib/data/config.py:57) | 是 | ser_lib/config/data.py | max_lengths |
| `SlidingBatching` | [ser_lib/data/config.py:71](D:/projects/Speech-Emotion-Recognition/ser_lib/data/config.py:71) | 是 | ser_lib/config/data.py | window_size, stride |
| `BatchingConfig` | [ser_lib/data/config.py:86](D:/projects/Speech-Emotion-Recognition/ser_lib/data/config.py:86) | 是 | ser_lib/config/data.py | type, fixed, sliding, primary_key |
| `DataConfig` | [ser_lib/data/config.py:126](D:/projects/Speech-Emotion-Recognition/ser_lib/data/config.py:126) | 是 | ser_lib/config/data.py | schema_version, manifest, dataset_id, labels, audio, cache, representation, waveform_transforms, feature_transforms, batching |
| `CasiaImportConfig` | [ser_lib/data/importers/casia.py:37](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/casia.py:37) | 是 | ser_lib/config/importers.py | audio_extensions, label_mapping |
| `CremaDImportConfig` | [ser_lib/data/importers/crema_d.py:39](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/crema_d.py:39) | 是 | ser_lib/config/importers.py | audio_directory, demographics_file, encoding, label_mapping, speaker_splits |
| `CsemotionsImportConfig` | [ser_lib/data/importers/csemotions.py:34](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/csemotions.py:34) | 是 | ser_lib/config/importers.py | metadata_file, audio_directory, encoding, label_mapping, speaker_splits |
| `CsvImportConfig` | [ser_lib/data/importers/csv_importer.py:20](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/csv_importer.py:20) | 是 | ser_lib/config/importers.py | audio_path_column, label_column, label_mapping, speaker_column, metadata_columns, uid_column, uid_prefix, delimiter, encoding, root |
| `EmotionTalkImportConfig` | [ser_lib/data/importers/emotiontalk.py:31](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/emotiontalk.py:31) | 是 | ser_lib/config/importers.py | json_directory, audio_directory, encoding, label_mapping, split_strategy, speaker_splits |
| `EsdImportConfig` | [ser_lib/data/importers/esd.py:23](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/esd.py:23) | 是 | ser_lib/config/importers.py | languages, encoding, label_mapping, speaker_splits |
| `FolderImportConfig` | [ser_lib/data/importers/folder.py:21](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/folder.py:21) | 是 | ser_lib/config/importers.py | audio_extensions, label_dir_level, speaker_dir_level, label_mapping, uid_prefix, relative_paths |
| `JsonlImportConfig` | [ser_lib/data/importers/jsonl_importer.py:31](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/jsonl_importer.py:31) | 是 | ser_lib/config/importers.py | uid_prefix, root |
| `RavdessImportConfig` | [ser_lib/data/importers/ravdess.py:30](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/ravdess.py:30) | 是 | ser_lib/config/importers.py | vocal_channel, relative_paths |
| `AcousticFeaturesConfig` | [ser_lib/data/representations/acoustic.py:57](D:/projects/Speech-Emotion-Recognition/ser_lib/data/representations/acoustic.py:57) | 是 | ser_lib/config/representations.py | features, sample_rate, hop_length, win_length, n_fft, roll_percent, delta_win_length |
| `CompositeConfig` | [ser_lib/data/representations/composite.py:25](D:/projects/Speech-Emotion-Recognition/ser_lib/data/representations/composite.py:25) | 是 | ser_lib/config/representations.py | outputs |
| `SpectralConfigBase` | [ser_lib/data/representations/spectral.py:25](D:/projects/Speech-Emotion-Recognition/ser_lib/data/representations/spectral.py:25) | 配置基类 | ser_lib/config/representations.py | sample_rate, n_fft, win_length, hop_length, f_min, f_max, center, pad_mode |
| `SpectrogramConfig` | [ser_lib/data/representations/spectral.py:49](D:/projects/Speech-Emotion-Recognition/ser_lib/data/representations/spectral.py:49) | 是 | ser_lib/config/representations.py | power |
| `MelConfig` | [ser_lib/data/representations/spectral.py:55](D:/projects/Speech-Emotion-Recognition/ser_lib/data/representations/spectral.py:55) | 是 | ser_lib/config/representations.py | n_mels, power |
| `LogMelConfig` | [ser_lib/data/representations/spectral.py:62](D:/projects/Speech-Emotion-Recognition/ser_lib/data/representations/spectral.py:62) | 是 | ser_lib/config/representations.py | top_db |
| `MFCCConfig` | [ser_lib/data/representations/spectral.py:68](D:/projects/Speech-Emotion-Recognition/ser_lib/data/representations/spectral.py:68) | 是 | ser_lib/config/representations.py | n_mels, n_mfcc, dct_norm, mel_norm, mel_scale |
| `RawWaveformConfig` | [ser_lib/data/representations/waveform.py:17](D:/projects/Speech-Emotion-Recognition/ser_lib/data/representations/waveform.py:17) | 是 | ser_lib/config/representations.py | 继承字段/无参数严格 schema |
| `SpecMaskingConfig` | [ser_lib/data/transforms/feature.py:17](D:/projects/Speech-Emotion-Recognition/ser_lib/data/transforms/feature.py:17) | 是 | ser_lib/config/transforms.py | time_mask_param, freq_mask_param |
| `NormalizeConfig` | [ser_lib/data/transforms/waveform.py:25](D:/projects/Speech-Emotion-Recognition/ser_lib/data/transforms/waveform.py:25) | 是 | ser_lib/config/transforms.py | 继承字段/无参数严格 schema |
| `GaussianNoiseConfig` | [ser_lib/data/transforms/waveform.py:31](D:/projects/Speech-Emotion-Recognition/ser_lib/data/transforms/waveform.py:31) | 是 | ser_lib/config/transforms.py | snr_db |
| `TimeShiftConfig` | [ser_lib/data/transforms/waveform.py:39](D:/projects/Speech-Emotion-Recognition/ser_lib/data/transforms/waveform.py:39) | 是 | ser_lib/config/transforms.py | max_ratio |
| `VolumeScaleConfig` | [ser_lib/data/transforms/waveform.py:47](D:/projects/Speech-Emotion-Recognition/ser_lib/data/transforms/waveform.py:47) | 是 | ser_lib/config/transforms.py | gain_min, gain_max |
| `PitchShiftConfig` | [ser_lib/data/transforms/waveform.py:62](D:/projects/Speech-Emotion-Recognition/ser_lib/data/transforms/waveform.py:62) | 是 | ser_lib/config/transforms.py | sample_rate, n_steps |
| `TimeStretchConfig` | [ser_lib/data/transforms/waveform.py:71](D:/projects/Speech-Emotion-Recognition/ser_lib/data/transforms/waveform.py:71) | 是 | ser_lib/config/transforms.py | rate |
| `ModelConfig` | [ser_lib/engine/config.py:22](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/config.py:22) | 是 | ser_lib/config/model.py | type, params |
| `ObservabilityConfig` | [ser_lib/engine/config.py:29](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/config.py:29) | 是 | ser_lib/config/training.py | progress_interval_batches, metric_interval_batches, eta_window_batches, eta_warmup_batches |
| `TrainerConfig` | [ser_lib/engine/config.py:44](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/config.py:44) | 是 | ser_lib/config/training.py | epochs, device, seed, deterministic, amp, gradient_clip_norm, gradient_accumulation_steps, checkpoint_dir, validation_interval, monitor, early_stopping_patience, early_stopping_min_delta, save_best, save_last |
| `ExperimentConfig` | [ser_lib/engine/config.py:65](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/config.py:65) | 是 | ser_lib/config/experiment.py | schema_version, data, model, trainer, optimizer, scheduler, loss, sampling, output_dir |
| `LossConfig` | [ser_lib/engine/objectives.py:16](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/objectives.py:16) | 是 | ser_lib/config/training.py | type, class_weights, label_smoothing, focal_gamma |
| `SamplingConfig` | [ser_lib/engine/objectives.py:31](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/objectives.py:31) | 是 | ser_lib/config/training.py | type, class_weights, replacement, num_samples |
| `AdamWConfig` | [ser_lib/engine/optim.py:13](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/optim.py:13) | 是 | ser_lib/config/optimizer.py | type, learning_rate, weight_decay, beta1, beta2, eps |
| `AdamConfig` | [ser_lib/engine/optim.py:22](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/optim.py:22) | 是 | ser_lib/config/optimizer.py | type, learning_rate, weight_decay, beta1, beta2, eps |
| `SGDConfig` | [ser_lib/engine/optim.py:31](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/optim.py:31) | 是 | ser_lib/config/optimizer.py | type, learning_rate, weight_decay, momentum, nesterov |
| `OptimizerConfig` | [ser_lib/engine/optim.py:45](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/optim.py:45) | 用户配置联合类型 | ser_lib/config/optimizer.py | AdamWConfig \| AdamConfig \| SGDConfig |
| `StepSchedulerConfig` | [ser_lib/engine/optim.py:48](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/optim.py:48) | 是 | ser_lib/config/scheduler.py | type, step_size, gamma |
| `CosineSchedulerConfig` | [ser_lib/engine/optim.py:54](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/optim.py:54) | 是 | ser_lib/config/scheduler.py | type, t_max, eta_min |
| `SchedulerConfig` | [ser_lib/engine/optim.py:60](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/optim.py:60) | 用户配置联合类型 | ser_lib/config/scheduler.py | StepSchedulerConfig \| CosineSchedulerConfig |
| `StreamingConfig` | [ser_lib/inference/streaming.py:16](D:/projects/Speech-Emotion-Recognition/ser_lib/inference/streaming.py:16) | 是 | ser_lib/config/inference.py | input_sample_rate, window_ms, hop_ms, silence_rms_threshold, suppress_silence, smoothing_alpha, max_chunk_ms |
| `CNNBaselineConfig` | [ser_lib/models/cnn_models.py:18](D:/projects/Speech-Emotion-Recognition/ser_lib/models/cnn_models.py:18) | 是 | ser_lib/config/model.py | feature_dim, num_classes, hidden_dim, dropout |
| `HFAudioClassifierConfig` | [ser_lib/models/pretrained.py:20](D:/projects/Speech-Emotion-Recognition/ser_lib/models/pretrained.py:20) | 是 | ser_lib/config/model.py | num_classes, pretrained_model_name_or_path, encoder_config, local_files_only, revision, freeze_encoder, dropout, pooling, expected_sample_rate |
| `GRUBaselineConfig` | [ser_lib/models/rnn_models.py:19](D:/projects/Speech-Emotion-Recognition/ser_lib/models/rnn_models.py:19) | 是 | ser_lib/config/model.py | feature_dim, num_classes, hidden_dim, num_layers, bidirectional, dropout |
| `TransformerBaselineConfig` | [ser_lib/models/transformer_models.py:19](D:/projects/Speech-Emotion-Recognition/ser_lib/models/transformer_models.py:19) | 是 | ser_lib/config/model.py | feature_dim, num_classes, d_model, num_heads, num_layers, feedforward_dim, dropout, activation, norm_first |

AudioSettings 与 AudioLoaderConfig 合并为 AudioConfig；CacheSettings 可规范为 CacheConfig。其它类型优先保持名称和序列化字段，以降低兼容成本。所有列为配置的 runtime 命名对象也中央化。

### B.1 非用户配置的结构化对象

| 对象 | 路径 | 分类 |
| --- | --- | --- |
| `ArtifactInfo` | [ser_lib/artifacts/catalog.py:16](D:/projects/Speech-Emotion-Recognition/ser_lib/artifacts/catalog.py:16) | 领域分析/metadata 与展示混合，瘦身；不进 config |
| `ArtifactScanFailure` | [ser_lib/artifacts/catalog.py:62](D:/projects/Speech-Emotion-Recognition/ser_lib/artifacts/catalog.py:62) | 领域 Model/Result/Spec/Metadata/State；不进 config |
| `ArtifactCatalog` | [ser_lib/artifacts/catalog.py:76](D:/projects/Speech-Emotion-Recognition/ser_lib/artifacts/catalog.py:76) | 领域 Model/Result/Spec/Metadata/State；不进 config |
| `LoadedArtifact` | [ser_lib/artifacts/loader.py:35](D:/projects/Speech-Emotion-Recognition/ser_lib/artifacts/loader.py:35) | 领域 Model/Result/Spec/Metadata/State；不进 config |
| `ModelCard` | [ser_lib/artifacts/manifest.py:13](D:/projects/Speech-Emotion-Recognition/ser_lib/artifacts/manifest.py:13) | 领域 Model/Result/Spec/Metadata/State；不进 config |
| `ModelArtifactManifest` | [ser_lib/artifacts/manifest.py:24](D:/projects/Speech-Emotion-Recognition/ser_lib/artifacts/manifest.py:24) | 领域 Model/Result/Spec/Metadata/State；不进 config |
| `BenchmarkResult` | [ser_lib/benchmark.py:18](D:/projects/Speech-Emotion-Recognition/ser_lib/benchmark.py:18) | 领域 Model/Result/Spec/Metadata/State；不进 config |
| `BenchmarkComparison` | [ser_lib/benchmark.py:34](D:/projects/Speech-Emotion-Recognition/ser_lib/benchmark.py:34) | 领域 Model/Result/Spec/Metadata/State；不进 config |
| `ComponentCatalog` | [ser_lib/catalog.py:205](D:/projects/Speech-Emotion-Recognition/ser_lib/catalog.py:205) | 上层包装，退役；不进 config |
| `Diagnostic` | [ser_lib/core/diagnostics.py:44](D:/projects/Speech-Emotion-Recognition/ser_lib/core/diagnostics.py:44) | 领域 Model/Result/Spec/Metadata/State；不进 config |
| `EventContext` | [ser_lib/core/events.py:74](D:/projects/Speech-Emotion-Recognition/ser_lib/core/events.py:74) | 领域 Model/Result/Spec/Metadata/State；不进 config |
| `ProgressEvent` | [ser_lib/core/events.py:98](D:/projects/Speech-Emotion-Recognition/ser_lib/core/events.py:98) | 领域 Model/Result/Spec/Metadata/State；不进 config |
| `MetricEvent` | [ser_lib/core/events.py:143](D:/projects/Speech-Emotion-Recognition/ser_lib/core/events.py:143) | 领域 Model/Result/Spec/Metadata/State；不进 config |
| `LogEvent` | [ser_lib/core/events.py:181](D:/projects/Speech-Emotion-Recognition/ser_lib/core/events.py:181) | 领域 Model/Result/Spec/Metadata/State；不进 config |
| `LifecycleEvent` | [ser_lib/core/events.py:216](D:/projects/Speech-Emotion-Recognition/ser_lib/core/events.py:216) | 领域 Model/Result/Spec/Metadata/State；不进 config |
| `CheckpointEvent` | [ser_lib/core/events.py:254](D:/projects/Speech-Emotion-Recognition/ser_lib/core/events.py:254) | 领域 Model/Result/Spec/Metadata/State；不进 config |
| `PredictionEvent` | [ser_lib/core/events.py:304](D:/projects/Speech-Emotion-Recognition/ser_lib/core/events.py:304) | 领域 Model/Result/Spec/Metadata/State；不进 config |
| `SchemaMigration` | [ser_lib/core/migrations.py:16](D:/projects/Speech-Emotion-Recognition/ser_lib/core/migrations.py:16) | 领域 Model/Result/Spec/Metadata/State；不进 config |
| `AudioFileInfo` | [ser_lib/data/audio.py:41](D:/projects/Speech-Emotion-Recognition/ser_lib/data/audio.py:41) | 领域 Model/Result/Spec/Metadata/State；不进 config |
| `DatasetFingerprint` | [ser_lib/data/fingerprint.py:17](D:/projects/Speech-Emotion-Recognition/ser_lib/data/fingerprint.py:17) | 领域 Model/Result/Spec/Metadata/State；不进 config |
| `_RevisionFileModel` | [ser_lib/data/history.py:40](D:/projects/Speech-Emotion-Recognition/ser_lib/data/history.py:40) | 领域 Model/Result/Spec/Metadata/State；不进 config |
| `_RevisionRecordModel` | [ser_lib/data/history.py:69](D:/projects/Speech-Emotion-Recognition/ser_lib/data/history.py:69) | 领域 Model/Result/Spec/Metadata/State；不进 config |
| `DatasetRevisionInfo` | [ser_lib/data/history.py:118](D:/projects/Speech-Emotion-Recognition/ser_lib/data/history.py:118) | 领域 Model/Result/Spec/Metadata/State；不进 config |
| `DatasetRevisionScanFailure` | [ser_lib/data/history.py:144](D:/projects/Speech-Emotion-Recognition/ser_lib/data/history.py:144) | 领域 Model/Result/Spec/Metadata/State；不进 config |
| `DatasetRevisionCatalog` | [ser_lib/data/history.py:158](D:/projects/Speech-Emotion-Recognition/ser_lib/data/history.py:158) | 领域 Model/Result/Spec/Metadata/State；不进 config |
| `ImportPreview` | [ser_lib/data/importers/base.py:32](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/base.py:32) | 领域 Model/Result/Spec/Metadata/State；不进 config |
| `ManifestMeta` | [ser_lib/data/manifest.py:31](D:/projects/Speech-Emotion-Recognition/ser_lib/data/manifest.py:31) | 领域 Model/Result/Spec/Metadata/State；不进 config |
| `AudioProbeFailure` | [ser_lib/data/profiling.py:15](D:/projects/Speech-Emotion-Recognition/ser_lib/data/profiling.py:15) | 领域 Model/Result/Spec/Metadata/State；不进 config |
| `DurationHistogramBin` | [ser_lib/data/profiling.py:23](D:/projects/Speech-Emotion-Recognition/ser_lib/data/profiling.py:23) | 领域 Model/Result/Spec/Metadata/State；不进 config |
| `DatasetAudioProfile` | [ser_lib/data/profiling.py:33](D:/projects/Speech-Emotion-Recognition/ser_lib/data/profiling.py:33) | 领域 Model/Result/Spec/Metadata/State；不进 config |
| `DatasetSummary` | [ser_lib/data/profiling.py:57](D:/projects/Speech-Emotion-Recognition/ser_lib/data/profiling.py:57) | 领域分析/metadata 与展示混合，瘦身；不进 config |
| `DatasetProfile` | [ser_lib/data/profiling.py:83](D:/projects/Speech-Emotion-Recognition/ser_lib/data/profiling.py:83) | 领域分析/metadata 与展示混合，瘦身；不进 config |
| `RecordView` | [ser_lib/data/query.py:16](D:/projects/Speech-Emotion-Recognition/ser_lib/data/query.py:16) | 上层包装，退役；不进 config |
| `RecordPage` | [ser_lib/data/query.py:34](D:/projects/Speech-Emotion-Recognition/ser_lib/data/query.py:34) | 上层包装，退役；不进 config |
| `ComponentDescriptor` | [ser_lib/data/registry.py:32](D:/projects/Speech-Emotion-Recognition/ser_lib/data/registry.py:32) | 领域 Model/Result/Spec/Metadata/State；不进 config |
| `ComponentEntry` | [ser_lib/data/registry.py:99](D:/projects/Speech-Emotion-Recognition/ser_lib/data/registry.py:99) | 领域 Model/Result/Spec/Metadata/State；不进 config |
| `AudioRecord` | [ser_lib/data/types.py:69](D:/projects/Speech-Emotion-Recognition/ser_lib/data/types.py:69) | 领域 Model/Result/Spec/Metadata/State；不进 config |
| `AudioData` | [ser_lib/data/types.py:120](D:/projects/Speech-Emotion-Recognition/ser_lib/data/types.py:120) | 领域 Model/Result/Spec/Metadata/State；不进 config |
| `TensorSpec` | [ser_lib/data/types.py:160](D:/projects/Speech-Emotion-Recognition/ser_lib/data/types.py:160) | 领域 Model/Result/Spec/Metadata/State；不进 config |
| `RepresentationOutput` | [ser_lib/data/types.py:311](D:/projects/Speech-Emotion-Recognition/ser_lib/data/types.py:311) | 领域 Model/Result/Spec/Metadata/State；不进 config |
| `SERSample` | [ser_lib/data/types.py:326](D:/projects/Speech-Emotion-Recognition/ser_lib/data/types.py:326) | 领域 Model/Result/Spec/Metadata/State；不进 config |
| `SERBatch` | [ser_lib/data/types.py:346](D:/projects/Speech-Emotion-Recognition/ser_lib/data/types.py:346) | 领域 Model/Result/Spec/Metadata/State；不进 config |
| `ModelSpec` | [ser_lib/data/validation.py:20](D:/projects/Speech-Emotion-Recognition/ser_lib/data/validation.py:20) | 领域 Model/Result/Spec/Metadata/State；不进 config |
| `CompatibilityReport` | [ser_lib/data/validation.py:32](D:/projects/Speech-Emotion-Recognition/ser_lib/data/validation.py:32) | 领域 Model/Result/Spec/Metadata/State；不进 config |
| `EpochResult` | [ser_lib/engine/_trainer_core.py:47](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/_trainer_core.py:47) | 领域 Model/Result/Spec/Metadata/State；不进 config |
| `TrainingResult` | [ser_lib/engine/_trainer_core.py:68](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/_trainer_core.py:68) | 领域 Model/Result/Spec/Metadata/State；不进 config |
| `CheckpointInfo` | [ser_lib/engine/checkpoint_catalog.py:19](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/checkpoint_catalog.py:19) | 领域 Model/Result/Spec/Metadata/State；不进 config |
| `CheckpointScanFailure` | [ser_lib/engine/checkpoint_catalog.py:41](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/checkpoint_catalog.py:41) | 领域 Model/Result/Spec/Metadata/State；不进 config |
| `CheckpointCatalog` | [ser_lib/engine/checkpoint_catalog.py:55](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/checkpoint_catalog.py:55) | 领域 Model/Result/Spec/Metadata/State；不进 config |
| `ExperimentComponents` | [ser_lib/engine/config.py:98](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/config.py:98) | 领域 Model/Result/Spec/Metadata/State；不进 config |
| `EtaSnapshot` | [ser_lib/engine/eta.py:11](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/eta.py:11) | 领域 Model/Result/Spec/Metadata/State；不进 config |
| `_BatchTiming` | [ser_lib/engine/eta.py:39](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/eta.py:39) | 领域 Model/Result/Spec/Metadata/State；不进 config |
| `EvaluationRunScanFailure` | [ser_lib/engine/evaluation_catalog.py:17](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/evaluation_catalog.py:17) | 领域 Model/Result/Spec/Metadata/State；不进 config |
| `EvaluationRunCatalog` | [ser_lib/engine/evaluation_catalog.py:31](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/evaluation_catalog.py:31) | 领域 Model/Result/Spec/Metadata/State；不进 config |
| `EvaluationPredictionFileInfo` | [ser_lib/engine/evaluation_detail.py:15](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/evaluation_detail.py:15) | 领域 Model/Result/Spec/Metadata/State；不进 config |
| `EvaluationRunDetail` | [ser_lib/engine/evaluation_detail.py:31](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/evaluation_detail.py:31) | 上层包装，退役；不进 config |
| `_ClassMetricsModel` | [ser_lib/engine/evaluation_reports.py:16](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/evaluation_reports.py:16) | 领域 Model/Result/Spec/Metadata/State；不进 config |
| `_EvaluationMetricsModel` | [ser_lib/engine/evaluation_reports.py:27](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/evaluation_reports.py:27) | 领域 Model/Result/Spec/Metadata/State；不进 config |
| `_PredictionRecordModel` | [ser_lib/engine/evaluation_reports.py:63](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/evaluation_reports.py:63) | 领域 Model/Result/Spec/Metadata/State；不进 config |
| `EvaluationReportInfo` | [ser_lib/engine/evaluation_reports.py:85](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/evaluation_reports.py:85) | 领域 Model/Result/Spec/Metadata/State；不进 config |
| `EvaluationPredictionPage` | [ser_lib/engine/evaluation_reports.py:129](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/evaluation_reports.py:129) | 上层包装，退役；不进 config |
| `_EvaluationRunRecordModel` | [ser_lib/engine/evaluation_runs.py:34](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/evaluation_runs.py:34) | 领域 Model/Result/Spec/Metadata/State；不进 config |
| `EvaluationRunMetadata` | [ser_lib/engine/evaluation_runs.py:99](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/evaluation_runs.py:99) | 领域 Model/Result/Spec/Metadata/State；不进 config |
| `EvaluationRunInfo` | [ser_lib/engine/evaluation_runs.py:148](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/evaluation_runs.py:148) | 领域 Model/Result/Spec/Metadata/State；不进 config |
| `ClassMetrics` | [ser_lib/engine/evaluator.py:29](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/evaluator.py:29) | 领域 Model/Result/Spec/Metadata/State；不进 config |
| `PredictionRecord` | [ser_lib/engine/evaluator.py:50](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/evaluator.py:50) | 领域 Model/Result/Spec/Metadata/State；不进 config |
| `EvaluationResult` | [ser_lib/engine/evaluator.py:119](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/evaluator.py:119) | 领域 Model/Result/Spec/Metadata/State；不进 config |
| `TrainingRunMetadata` | [ser_lib/engine/lineage.py:11](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/lineage.py:11) | 领域 Model/Result/Spec/Metadata/State；不进 config |
| `ExperimentPresetInfo` | [ser_lib/engine/presets.py:222](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/presets.py:222) | 领域 Model/Result/Spec/Metadata/State；不进 config |
| `ExperimentPresetCatalog` | [ser_lib/engine/presets.py:242](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/presets.py:242) | 上层包装，退役；不进 config |
| `_RunRecordModel` | [ser_lib/engine/runs.py:26](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/runs.py:26) | 领域 Model/Result/Spec/Metadata/State；不进 config |
| `TrainingRunInfo` | [ser_lib/engine/runs.py:64](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/runs.py:64) | 领域 Model/Result/Spec/Metadata/State；不进 config |
| `TrainingRunDetail` | [ser_lib/engine/runs.py:163](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/runs.py:163) | 上层包装，退役；不进 config |
| `TrainingRunScanFailure` | [ser_lib/engine/runs.py:185](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/runs.py:185) | 领域 Model/Result/Spec/Metadata/State；不进 config |
| `TrainingRunCatalog` | [ser_lib/engine/runs.py:199](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/runs.py:199) | 领域 Model/Result/Spec/Metadata/State；不进 config |
| `_EpochResultModel` | [ser_lib/engine/training_history.py:18](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/training_history.py:18) | 领域 Model/Result/Spec/Metadata/State；不进 config |
| `TrainingHistoryInfo` | [ser_lib/engine/training_history.py:46](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/training_history.py:46) | 领域 Model/Result/Spec/Metadata/State；不进 config |
| `ExperimentValidationResult` | [ser_lib/engine/validation.py:21](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/validation.py:21) | 领域 Model/Result/Spec/Metadata/State；不进 config |
| `PredictionFailure` | [ser_lib/inference/batch.py:29](D:/projects/Speech-Emotion-Recognition/ser_lib/inference/batch.py:29) | 领域 Model/Result/Spec/Metadata/State；不进 config |
| `BatchPredictionResult` | [ser_lib/inference/batch.py:97](D:/projects/Speech-Emotion-Recognition/ser_lib/inference/batch.py:97) | 领域 Model/Result/Spec/Metadata/State；不进 config |
| `PredictionResult` | [ser_lib/inference/offline.py:16](D:/projects/Speech-Emotion-Recognition/ser_lib/inference/offline.py:16) | 领域 Model/Result/Spec/Metadata/State；不进 config |
| `StreamingPrediction` | [ser_lib/inference/streaming.py:41](D:/projects/Speech-Emotion-Recognition/ser_lib/inference/streaming.py:41) | 领域 Model/Result/Spec/Metadata/State；不进 config |
| `StreamingLatency` | [ser_lib/inference/streaming.py:51](D:/projects/Speech-Emotion-Recognition/ser_lib/inference/streaming.py:51) | 领域 Model/Result/Spec/Metadata/State；不进 config |
| `ModelOutput` | [ser_lib/models/base.py:13](D:/projects/Speech-Emotion-Recognition/ser_lib/models/base.py:13) | 领域 Model/Result/Spec/Metadata/State；不进 config |
| `ModelDescriptor` | [ser_lib/models/registry.py:19](D:/projects/Speech-Emotion-Recognition/ser_lib/models/registry.py:19) | 领域 Model/Result/Spec/Metadata/State；不进 config |
| `_ModelEntry` | [ser_lib/models/registry.py:38](D:/projects/Speech-Emotion-Recognition/ser_lib/models/registry.py:38) | 领域 Model/Result/Spec/Metadata/State；不进 config |
| `RuntimeDevice` | [ser_lib/runtime.py:15](D:/projects/Speech-Emotion-Recognition/ser_lib/runtime.py:15) | 领域 Model/Result/Spec/Metadata/State；不进 config |
| `RuntimeCapabilities` | [ser_lib/runtime.py:29](D:/projects/Speech-Emotion-Recognition/ser_lib/runtime.py:29) | 领域 Model/Result/Spec/Metadata/State；不进 config |
| `RuntimeMetrics` | [ser_lib/runtime.py:47](D:/projects/Speech-Emotion-Recognition/ser_lib/runtime.py:47) | 领域 Model/Result/Spec/Metadata/State；不进 config |
| `_HostRuntimeMetrics` | [ser_lib/runtime.py:85](D:/projects/Speech-Emotion-Recognition/ser_lib/runtime.py:85) | 领域 Model/Result/Spec/Metadata/State；不进 config |

### B.2 仓库其它 Config 定义及配置相关文件

| 路径 | 符号 | 判断 |
| --- | --- | --- |
| [tests/test_core.py:27](D:/projects/Speech-Emotion-Recognition/tests/test_core.py:27) | ExampleConfig | 测试 fake/local fixture，非生产配置 |
| [tests/test_pretrained_adapter.py:25](D:/projects/Speech-Emotion-Recognition/tests/test_pretrained_adapter.py:25) | FakeConfig | 测试 fake/local fixture，非生产配置 |
| [tests/test_pretrained_adapter.py:52](D:/projects/Speech-Emotion-Recognition/tests/test_pretrained_adapter.py:52) | AutoConfig | 测试 fake/local fixture，非生产配置 |
| [tests/test_registry_config.py:8](D:/projects/Speech-Emotion-Recognition/tests/test_registry_config.py:8) | StrictConfig | 测试 fake/local fixture，非生产配置 |

以下为 Git 跟踪的配置文件/工具配置及 configuration/settings/options 文本命中的文件清单。工具设置不迁入 Python SDK config；configs 下 YAML 是配置实例，引用中央 schema，不搬进包作为类型定义。

| 匹配文件 | 处理边界 |
| --- | --- |
| [configs/README.md](D:/projects/Speech-Emotion-Recognition/configs/README.md) | 实验配置实例 |
| [configs/casia_cnn_logmel.yaml](D:/projects/Speech-Emotion-Recognition/configs/casia_cnn_logmel.yaml) | 实验配置实例 |
| [configs/casia_model_card.yaml](D:/projects/Speech-Emotion-Recognition/configs/casia_model_card.yaml) | 实验配置实例 |
| [configs/cnn_logmel.yaml](D:/projects/Speech-Emotion-Recognition/configs/cnn_logmel.yaml) | 实验配置实例 |
| [configs/crema_d_cnn_logmel.yaml](D:/projects/Speech-Emotion-Recognition/configs/crema_d_cnn_logmel.yaml) | 实验配置实例 |
| [configs/crema_d_model_card.yaml](D:/projects/Speech-Emotion-Recognition/configs/crema_d_model_card.yaml) | 实验配置实例 |
| [configs/csemotions_cnn_logmel.yaml](D:/projects/Speech-Emotion-Recognition/configs/csemotions_cnn_logmel.yaml) | 实验配置实例 |
| [configs/csemotions_model_card.yaml](D:/projects/Speech-Emotion-Recognition/configs/csemotions_model_card.yaml) | 实验配置实例 |
| [configs/emotiontalk_cnn_logmel.yaml](D:/projects/Speech-Emotion-Recognition/configs/emotiontalk_cnn_logmel.yaml) | 实验配置实例 |
| [configs/emotiontalk_model_card.yaml](D:/projects/Speech-Emotion-Recognition/configs/emotiontalk_model_card.yaml) | 实验配置实例 |
| [configs/esd_cnn_logmel.yaml](D:/projects/Speech-Emotion-Recognition/configs/esd_cnn_logmel.yaml) | 实验配置实例 |
| [configs/esd_model_card.yaml](D:/projects/Speech-Emotion-Recognition/configs/esd_model_card.yaml) | 实验配置实例 |
| [configs/gru_mfcc.yaml](D:/projects/Speech-Emotion-Recognition/configs/gru_mfcc.yaml) | 实验配置实例 |
| [configs/transformer_logmel.yaml](D:/projects/Speech-Emotion-Recognition/configs/transformer_logmel.yaml) | 实验配置实例 |
| [docs/development/ser-lib-roadmap/08-service-api-audit.md](D:/projects/Speech-Emotion-Recognition/docs/development/ser-lib-roadmap/08-service-api-audit.md) | 测试/文档/示例/工具设置，迁引用，非库配置定义 |
| [ser_lib/core/config.py](D:/projects/Speech-Emotion-Recognition/ser_lib/core/config.py) | 库源码：定义见 B/对象见 B.1 |
| [ser_lib/data/config.py](D:/projects/Speech-Emotion-Recognition/ser_lib/data/config.py) | 库源码：定义见 B/对象见 B.1 |
| [ser_lib/engine/config.py](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/config.py) | 库源码：定义见 B/对象见 B.1 |
| [tests/test_engine_config.py](D:/projects/Speech-Emotion-Recognition/tests/test_engine_config.py) | 测试/文档/示例/工具设置，迁引用，非库配置定义 |
| [tests/test_pretrained_adapter.py](D:/projects/Speech-Emotion-Recognition/tests/test_pretrained_adapter.py) | 测试/文档/示例/工具设置，迁引用，非库配置定义 |
| [tests/test_registry_config.py](D:/projects/Speech-Emotion-Recognition/tests/test_registry_config.py) | 测试/文档/示例/工具设置，迁引用，非库配置定义 |

## C. Public API 完整 __all__ 审计

每行包含导出所在模块、import 绑定来源与未来规范入口。来源是直接重导出关系，可能继续指向另一公开包；具体定义见 E。根包冗余 alias 最终收缩，表内“保留”指领域符号能力保留，不承诺所有旧路径保留。

| Public API | __all__ 位置 | 当前来源 | 是否保留 | 新规范 API/替代 |
| --- | --- | --- | --- | --- |
| `ser_lib.Diagnostic` | [ser_lib/__init__.py:120](D:/projects/Speech-Emotion-Recognition/ser_lib/__init__.py:120) | `ser_lib.core.Diagnostic` | 是（迁移） | `ser_lib/foundation/diagnostics.py:Diagnostic` |
| `ser_lib.DiagnosticSeverity` | [ser_lib/__init__.py:120](D:/projects/Speech-Emotion-Recognition/ser_lib/__init__.py:120) | `ser_lib.core.DiagnosticSeverity` | 是（迁移） | `ser_lib/foundation/diagnostics.py:DiagnosticSeverity` |
| `ser_lib.CompatibilityReport` | [ser_lib/__init__.py:120](D:/projects/Speech-Emotion-Recognition/ser_lib/__init__.py:120) | `ser_lib.data.CompatibilityReport` | 是（迁移） | `ser_lib.engine.compatibility.CompatibilityReport` |
| `ser_lib.inspect_compatibility` | [ser_lib/__init__.py:120](D:/projects/Speech-Emotion-Recognition/ser_lib/__init__.py:120) | `ser_lib.data.inspect_compatibility` | 是（迁移） | `ser_lib.engine.compatibility.inspect_compatibility` |
| `ser_lib.CATALOG_SCHEMA_VERSION` | [ser_lib/__init__.py:120](D:/projects/Speech-Emotion-Recognition/ser_lib/__init__.py:120) | `ser_lib.catalog.CATALOG_SCHEMA_VERSION` | 否 | `移除包装；见正文替代 API` |
| `ser_lib.CATALOG_CATEGORIES` | [ser_lib/__init__.py:120](D:/projects/Speech-Emotion-Recognition/ser_lib/__init__.py:120) | `ser_lib.catalog.CATALOG_CATEGORIES` | 否 | `移除包装；见正文替代 API` |
| `ser_lib.ComponentDescriptor` | [ser_lib/__init__.py:120](D:/projects/Speech-Emotion-Recognition/ser_lib/__init__.py:120) | `ser_lib.catalog.ComponentDescriptor` | 是（领域规范入口） | `ser_lib.data.registry.ComponentDescriptor` |
| `ser_lib.ComponentCatalog` | [ser_lib/__init__.py:120](D:/projects/Speech-Emotion-Recognition/ser_lib/__init__.py:120) | `ser_lib.catalog.ComponentCatalog` | 否 | `移除包装；见正文替代 API` |
| `ser_lib.get_component_catalog` | [ser_lib/__init__.py:120](D:/projects/Speech-Emotion-Recognition/ser_lib/__init__.py:120) | `ser_lib.catalog.get_component_catalog` | 否 | `移除包装；见正文替代 API` |
| `ser_lib.list_component_descriptors` | [ser_lib/__init__.py:120](D:/projects/Speech-Emotion-Recognition/ser_lib/__init__.py:120) | `ser_lib.catalog.list_component_descriptors` | 否 | `移除包装；见正文替代 API` |
| `ser_lib.RuntimeDevice` | [ser_lib/__init__.py:120](D:/projects/Speech-Emotion-Recognition/ser_lib/__init__.py:120) | `ser_lib.runtime.RuntimeDevice` | 是（迁移） | `ser_lib/engine/runtime.py:RuntimeDevice` |
| `ser_lib.RuntimeCapabilities` | [ser_lib/__init__.py:120](D:/projects/Speech-Emotion-Recognition/ser_lib/__init__.py:120) | `ser_lib.runtime.RuntimeCapabilities` | 是（迁移） | `ser_lib/engine/runtime.py:RuntimeCapabilities` |
| `ser_lib.RuntimeMetrics` | [ser_lib/__init__.py:120](D:/projects/Speech-Emotion-Recognition/ser_lib/__init__.py:120) | `ser_lib.runtime.RuntimeMetrics` | 是（迁移） | `ser_lib/engine/runtime.py:RuntimeMetrics` |
| `ser_lib.get_runtime_capabilities` | [ser_lib/__init__.py:120](D:/projects/Speech-Emotion-Recognition/ser_lib/__init__.py:120) | `ser_lib.runtime.get_runtime_capabilities` | 是（迁移） | `ser_lib/engine/runtime.py:get_runtime_capabilities` |
| `ser_lib.get_runtime_metrics` | [ser_lib/__init__.py:120](D:/projects/Speech-Emotion-Recognition/ser_lib/__init__.py:120) | `ser_lib.runtime.get_runtime_metrics` | 是（迁移） | `ser_lib/engine/runtime.py:get_runtime_metrics` |
| `ser_lib.SERDataset` | [ser_lib/__init__.py:120](D:/projects/Speech-Emotion-Recognition/ser_lib/__init__.py:120) | `ser_lib.data.SERDataset` | 是（领域规范入口） | `ser_lib.data.dataset.SERDataset` |
| `ser_lib.SERSample` | [ser_lib/__init__.py:120](D:/projects/Speech-Emotion-Recognition/ser_lib/__init__.py:120) | `ser_lib.data.SERSample` | 是（领域规范入口） | `ser_lib.data.types.SERSample` |
| `ser_lib.SERBatch` | [ser_lib/__init__.py:120](D:/projects/Speech-Emotion-Recognition/ser_lib/__init__.py:120) | `ser_lib.data.SERBatch` | 是（领域规范入口） | `ser_lib.data.types.SERBatch` |
| `ser_lib.TensorSpec` | [ser_lib/__init__.py:120](D:/projects/Speech-Emotion-Recognition/ser_lib/__init__.py:120) | `ser_lib.data.TensorSpec` | 是（领域规范入口） | `ser_lib.data.types.TensorSpec` |
| `ser_lib.ModelCard` | [ser_lib/__init__.py:120](D:/projects/Speech-Emotion-Recognition/ser_lib/__init__.py:120) | `ser_lib.artifacts.ModelCard` | 是（领域规范入口） | `ser_lib.artifacts.manifest.ModelCard` |
| `ser_lib.ModelArtifactManifest` | [ser_lib/__init__.py:120](D:/projects/Speech-Emotion-Recognition/ser_lib/__init__.py:120) | `ser_lib.artifacts.ModelArtifactManifest` | 是（领域规范入口） | `ser_lib.artifacts.manifest.ModelArtifactManifest` |
| `ser_lib.ArtifactInfo` | [ser_lib/__init__.py:120](D:/projects/Speech-Emotion-Recognition/ser_lib/__init__.py:120) | `ser_lib.artifacts.ArtifactInfo` | 替换 | `ser_lib.artifacts.ArtifactEntry（拟议）` |
| `ser_lib.ArtifactScanFailure` | [ser_lib/__init__.py:120](D:/projects/Speech-Emotion-Recognition/ser_lib/__init__.py:120) | `ser_lib.artifacts.ArtifactScanFailure` | 是（领域规范入口） | `ser_lib.artifacts.catalog.ArtifactScanFailure` |
| `ser_lib.ArtifactCatalog` | [ser_lib/__init__.py:120](D:/projects/Speech-Emotion-Recognition/ser_lib/__init__.py:120) | `ser_lib.artifacts.ArtifactCatalog` | 是（领域规范入口） | `ser_lib.artifacts.catalog.ArtifactCatalog` |
| `ser_lib.scan_model_artifacts` | [ser_lib/__init__.py:120](D:/projects/Speech-Emotion-Recognition/ser_lib/__init__.py:120) | `ser_lib.artifacts.scan_model_artifacts` | 是（领域规范入口） | `ser_lib.artifacts.catalog.scan_model_artifacts` |
| `ser_lib.export_model_artifact` | [ser_lib/__init__.py:120](D:/projects/Speech-Emotion-Recognition/ser_lib/__init__.py:120) | `ser_lib.artifacts.export_model_artifact` | 是（领域规范入口） | `ser_lib.artifacts.exporter.export_model_artifact` |
| `ser_lib.inspect_model_artifact` | [ser_lib/__init__.py:120](D:/projects/Speech-Emotion-Recognition/ser_lib/__init__.py:120) | `ser_lib.artifacts.inspect_model_artifact` | 是（领域规范入口） | `ser_lib.artifacts.loader.inspect_model_artifact` |
| `ser_lib.verify_model_artifact` | [ser_lib/__init__.py:120](D:/projects/Speech-Emotion-Recognition/ser_lib/__init__.py:120) | `ser_lib.artifacts.verify_model_artifact` | 是（领域规范入口） | `ser_lib.artifacts.loader.verify_model_artifact` |
| `ser_lib.load_model_artifact` | [ser_lib/__init__.py:120](D:/projects/Speech-Emotion-Recognition/ser_lib/__init__.py:120) | `ser_lib.artifacts.load_model_artifact` | 是（领域规范入口） | `ser_lib.artifacts.loader.load_model_artifact` |
| `ser_lib.SERModel` | [ser_lib/__init__.py:120](D:/projects/Speech-Emotion-Recognition/ser_lib/__init__.py:120) | `ser_lib.models.SERModel` | 是（领域规范入口） | `ser_lib.models.base.SERModel` |
| `ser_lib.ModelOutput` | [ser_lib/__init__.py:120](D:/projects/Speech-Emotion-Recognition/ser_lib/__init__.py:120) | `ser_lib.models.ModelOutput` | 是（领域规范入口） | `ser_lib.models.base.ModelOutput` |
| `ser_lib.CNNBaseline` | [ser_lib/__init__.py:120](D:/projects/Speech-Emotion-Recognition/ser_lib/__init__.py:120) | `ser_lib.models.CNNBaseline` | 是（领域规范入口） | `ser_lib.models.cnn_models.CNNBaseline` |
| `ser_lib.GRUBaseline` | [ser_lib/__init__.py:120](D:/projects/Speech-Emotion-Recognition/ser_lib/__init__.py:120) | `ser_lib.models.GRUBaseline` | 是（领域规范入口） | `ser_lib.models.rnn_models.GRUBaseline` |
| `ser_lib.TransformerBaseline` | [ser_lib/__init__.py:120](D:/projects/Speech-Emotion-Recognition/ser_lib/__init__.py:120) | `ser_lib.models.TransformerBaseline` | 是（领域规范入口） | `ser_lib.models.transformer_models.TransformerBaseline` |
| `ser_lib.HFAudioClassifier` | [ser_lib/__init__.py:120](D:/projects/Speech-Emotion-Recognition/ser_lib/__init__.py:120) | `ser_lib.models.HFAudioClassifier` | 是（领域规范入口） | `ser_lib.models.pretrained.HFAudioClassifier` |
| `ser_lib.Trainer` | [ser_lib/__init__.py:120](D:/projects/Speech-Emotion-Recognition/ser_lib/__init__.py:120) | `ser_lib.engine.Trainer` | 是 | `ser_lib.engine.Trainer；fit -> TrainingResult` |
| `ser_lib.TrainerConfig` | [ser_lib/__init__.py:120](D:/projects/Speech-Emotion-Recognition/ser_lib/__init__.py:120) | `ser_lib.engine.TrainerConfig` | 是（迁移/合并） | `ser_lib/config/training.py:TrainerConfig` |
| `ser_lib.ObservabilityConfig` | [ser_lib/__init__.py:120](D:/projects/Speech-Emotion-Recognition/ser_lib/__init__.py:120) | `ser_lib.engine.ObservabilityConfig` | 是（迁移/合并） | `ser_lib/config/training.py:ObservabilityConfig` |
| `ser_lib.TrainingResult` | [ser_lib/__init__.py:120](D:/projects/Speech-Emotion-Recognition/ser_lib/__init__.py:120) | `ser_lib.engine.TrainingResult` | 是（领域规范入口） | `ser_lib.engine._trainer_core.TrainingResult` |
| `ser_lib.TrainingStatus` | [ser_lib/__init__.py:120](D:/projects/Speech-Emotion-Recognition/ser_lib/__init__.py:120) | `ser_lib.engine.TrainingStatus` | 是（领域规范入口） | `ser_lib.engine._trainer_core.TrainingStatus` |
| `ser_lib.EtaSnapshot` | [ser_lib/__init__.py:120](D:/projects/Speech-Emotion-Recognition/ser_lib/__init__.py:120) | `ser_lib.engine.EtaSnapshot` | 是（领域规范入口） | `ser_lib.engine.eta.EtaSnapshot` |
| `ser_lib.EtaEstimator` | [ser_lib/__init__.py:120](D:/projects/Speech-Emotion-Recognition/ser_lib/__init__.py:120) | `ser_lib.engine.EtaEstimator` | 是（领域规范入口） | `ser_lib.engine.eta.EtaEstimator` |
| `ser_lib.TrainingRunMetadata` | [ser_lib/__init__.py:120](D:/projects/Speech-Emotion-Recognition/ser_lib/__init__.py:120) | `ser_lib.engine.TrainingRunMetadata` | 是（领域规范入口） | `ser_lib.engine.lineage.TrainingRunMetadata` |
| `ser_lib.build_training_run_metadata` | [ser_lib/__init__.py:120](D:/projects/Speech-Emotion-Recognition/ser_lib/__init__.py:120) | `ser_lib.engine.build_training_run_metadata` | 是（领域规范入口） | `ser_lib.engine.lineage.build_training_run_metadata` |
| `ser_lib.RUN_RECORD_SCHEMA_VERSION` | [ser_lib/__init__.py:120](D:/projects/Speech-Emotion-Recognition/ser_lib/__init__.py:120) | `ser_lib.engine.RUN_RECORD_SCHEMA_VERSION` | 是（领域规范入口） | `ser_lib.engine.runs.RUN_RECORD_SCHEMA_VERSION` |
| `ser_lib.TrainingRunInfo` | [ser_lib/__init__.py:120](D:/projects/Speech-Emotion-Recognition/ser_lib/__init__.py:120) | `ser_lib.engine.TrainingRunInfo` | 是（领域规范入口） | `ser_lib.engine.runs.TrainingRunInfo` |
| `ser_lib.TrainingRunDetail` | [ser_lib/__init__.py:120](D:/projects/Speech-Emotion-Recognition/ser_lib/__init__.py:120) | `ser_lib.engine.TrainingRunDetail` | 否 | `移除包装；见正文替代 API` |
| `ser_lib.TrainingRunScanFailure` | [ser_lib/__init__.py:120](D:/projects/Speech-Emotion-Recognition/ser_lib/__init__.py:120) | `ser_lib.engine.TrainingRunScanFailure` | 是（领域规范入口） | `ser_lib.engine.runs.TrainingRunScanFailure` |
| `ser_lib.TrainingRunCatalog` | [ser_lib/__init__.py:120](D:/projects/Speech-Emotion-Recognition/ser_lib/__init__.py:120) | `ser_lib.engine.TrainingRunCatalog` | 是（领域规范入口） | `ser_lib.engine.runs.TrainingRunCatalog` |
| `ser_lib.write_training_run_info` | [ser_lib/__init__.py:120](D:/projects/Speech-Emotion-Recognition/ser_lib/__init__.py:120) | `ser_lib.engine.write_training_run_info` | 是（领域规范入口） | `ser_lib.engine.runs.write_training_run_info` |
| `ser_lib.load_training_run_info` | [ser_lib/__init__.py:120](D:/projects/Speech-Emotion-Recognition/ser_lib/__init__.py:120) | `ser_lib.engine.load_training_run_info` | 是（领域规范入口） | `ser_lib.engine.runs.load_training_run_info` |
| `ser_lib.scan_training_runs` | [ser_lib/__init__.py:120](D:/projects/Speech-Emotion-Recognition/ser_lib/__init__.py:120) | `ser_lib.engine.scan_training_runs` | 是（领域规范入口） | `ser_lib.engine.runs.scan_training_runs` |
| `ser_lib.TrainingHistoryInfo` | [ser_lib/__init__.py:120](D:/projects/Speech-Emotion-Recognition/ser_lib/__init__.py:120) | `ser_lib.engine.TrainingHistoryInfo` | 是（领域规范入口） | `ser_lib.engine.training_history.TrainingHistoryInfo` |
| `ser_lib.load_training_history` | [ser_lib/__init__.py:120](D:/projects/Speech-Emotion-Recognition/ser_lib/__init__.py:120) | `ser_lib.engine.load_training_history` | 是（领域规范入口） | `ser_lib.engine.training_history.load_training_history` |
| `ser_lib.CheckpointKind` | [ser_lib/__init__.py:120](D:/projects/Speech-Emotion-Recognition/ser_lib/__init__.py:120) | `ser_lib.engine.CheckpointKind` | 是（领域规范入口） | `ser_lib.engine.checkpoint_catalog.CheckpointKind` |
| `ser_lib.CheckpointInfo` | [ser_lib/__init__.py:120](D:/projects/Speech-Emotion-Recognition/ser_lib/__init__.py:120) | `ser_lib.engine.CheckpointInfo` | 是（领域规范入口） | `ser_lib.engine.checkpoint_catalog.CheckpointInfo` |
| `ser_lib.CheckpointScanFailure` | [ser_lib/__init__.py:120](D:/projects/Speech-Emotion-Recognition/ser_lib/__init__.py:120) | `ser_lib.engine.CheckpointScanFailure` | 是（领域规范入口） | `ser_lib.engine.checkpoint_catalog.CheckpointScanFailure` |
| `ser_lib.CheckpointCatalog` | [ser_lib/__init__.py:120](D:/projects/Speech-Emotion-Recognition/ser_lib/__init__.py:120) | `ser_lib.engine.CheckpointCatalog` | 是（领域规范入口） | `ser_lib.engine.checkpoint_catalog.CheckpointCatalog` |
| `ser_lib.inspect_checkpoint_file` | [ser_lib/__init__.py:120](D:/projects/Speech-Emotion-Recognition/ser_lib/__init__.py:120) | `ser_lib.engine.inspect_checkpoint_file` | 是（领域规范入口） | `ser_lib.engine.checkpoint_catalog.inspect_checkpoint_file` |
| `ser_lib.scan_checkpoints` | [ser_lib/__init__.py:120](D:/projects/Speech-Emotion-Recognition/ser_lib/__init__.py:120) | `ser_lib.engine.scan_checkpoints` | 是（领域规范入口） | `ser_lib.engine.checkpoint_catalog.scan_checkpoints` |
| `ser_lib.EVALUATION_RUN_SCHEMA_VERSION` | [ser_lib/__init__.py:120](D:/projects/Speech-Emotion-Recognition/ser_lib/__init__.py:120) | `ser_lib.engine.EVALUATION_RUN_SCHEMA_VERSION` | 是（领域规范入口） | `ser_lib.engine.evaluation_runs.EVALUATION_RUN_SCHEMA_VERSION` |
| `ser_lib.EvaluationRunMetadata` | [ser_lib/__init__.py:120](D:/projects/Speech-Emotion-Recognition/ser_lib/__init__.py:120) | `ser_lib.engine.EvaluationRunMetadata` | 是（领域规范入口） | `ser_lib.engine.evaluation_runs.EvaluationRunMetadata` |
| `ser_lib.EvaluationRunInfo` | [ser_lib/__init__.py:120](D:/projects/Speech-Emotion-Recognition/ser_lib/__init__.py:120) | `ser_lib.engine.EvaluationRunInfo` | 是（领域规范入口） | `ser_lib.engine.evaluation_runs.EvaluationRunInfo` |
| `ser_lib.EvaluationPredictionFileInfo` | [ser_lib/__init__.py:120](D:/projects/Speech-Emotion-Recognition/ser_lib/__init__.py:120) | `ser_lib.engine.EvaluationPredictionFileInfo` | 是（合并） | `ser_lib.engine.evaluation_reports.EvaluationPredictionFileInfo` |
| `ser_lib.EvaluationRunDetail` | [ser_lib/__init__.py:120](D:/projects/Speech-Emotion-Recognition/ser_lib/__init__.py:120) | `ser_lib.engine.EvaluationRunDetail` | 否 | `移除包装；见正文替代 API` |
| `ser_lib.inspect_evaluation_prediction_file` | [ser_lib/__init__.py:120](D:/projects/Speech-Emotion-Recognition/ser_lib/__init__.py:120) | `ser_lib.engine.inspect_evaluation_prediction_file` | 是（合并） | `ser_lib.engine.evaluation_reports.inspect_evaluation_prediction_file` |
| `ser_lib.build_evaluation_run_metadata` | [ser_lib/__init__.py:120](D:/projects/Speech-Emotion-Recognition/ser_lib/__init__.py:120) | `ser_lib.engine.build_evaluation_run_metadata` | 是（领域规范入口） | `ser_lib.engine.evaluation_runs.build_evaluation_run_metadata` |
| `ser_lib.write_evaluation_run_info` | [ser_lib/__init__.py:120](D:/projects/Speech-Emotion-Recognition/ser_lib/__init__.py:120) | `ser_lib.engine.write_evaluation_run_info` | 是（领域规范入口） | `ser_lib.engine.evaluation_runs.write_evaluation_run_info` |
| `ser_lib.load_evaluation_run_info` | [ser_lib/__init__.py:120](D:/projects/Speech-Emotion-Recognition/ser_lib/__init__.py:120) | `ser_lib.engine.load_evaluation_run_info` | 是（领域规范入口） | `ser_lib.engine.evaluation_runs.load_evaluation_run_info` |
| `ser_lib.EvaluationRunScanFailure` | [ser_lib/__init__.py:120](D:/projects/Speech-Emotion-Recognition/ser_lib/__init__.py:120) | `ser_lib.engine.EvaluationRunScanFailure` | 是（领域规范入口） | `ser_lib.engine.evaluation_catalog.EvaluationRunScanFailure` |
| `ser_lib.EvaluationRunCatalog` | [ser_lib/__init__.py:120](D:/projects/Speech-Emotion-Recognition/ser_lib/__init__.py:120) | `ser_lib.engine.EvaluationRunCatalog` | 是（领域规范入口） | `ser_lib.engine.evaluation_catalog.EvaluationRunCatalog` |
| `ser_lib.scan_evaluation_runs` | [ser_lib/__init__.py:120](D:/projects/Speech-Emotion-Recognition/ser_lib/__init__.py:120) | `ser_lib.engine.scan_evaluation_runs` | 是（领域规范入口） | `ser_lib.engine.evaluation_catalog.scan_evaluation_runs` |
| `ser_lib.EvaluationReportInfo` | [ser_lib/__init__.py:120](D:/projects/Speech-Emotion-Recognition/ser_lib/__init__.py:120) | `ser_lib.engine.EvaluationReportInfo` | 是（领域规范入口） | `ser_lib.engine.evaluation_reports.EvaluationReportInfo` |
| `ser_lib.EvaluationPredictionPage` | [ser_lib/__init__.py:120](D:/projects/Speech-Emotion-Recognition/ser_lib/__init__.py:120) | `ser_lib.engine.EvaluationPredictionPage` | 否 | `移除包装；见正文替代 API` |
| `ser_lib.inspect_evaluation_report` | [ser_lib/__init__.py:120](D:/projects/Speech-Emotion-Recognition/ser_lib/__init__.py:120) | `ser_lib.engine.inspect_evaluation_report` | 是（领域规范入口） | `ser_lib.engine.evaluation_reports.inspect_evaluation_report` |
| `ser_lib.query_evaluation_predictions` | [ser_lib/__init__.py:120](D:/projects/Speech-Emotion-Recognition/ser_lib/__init__.py:120) | `ser_lib.engine.query_evaluation_predictions` | 替换 | `ser_lib.engine.iter_evaluation_predictions` |
| `ser_lib.evaluate` | [ser_lib/__init__.py:120](D:/projects/Speech-Emotion-Recognition/ser_lib/__init__.py:120) | `ser_lib.engine.evaluate` | 是（领域规范入口） | `ser_lib.engine.evaluator.evaluate` |
| `ser_lib.write_evaluation_report` | [ser_lib/__init__.py:120](D:/projects/Speech-Emotion-Recognition/ser_lib/__init__.py:120) | `ser_lib.engine.write_evaluation_report` | 是（领域规范入口） | `ser_lib.engine.evaluator.write_evaluation_report` |
| `ser_lib.ExperimentConfig` | [ser_lib/__init__.py:120](D:/projects/Speech-Emotion-Recognition/ser_lib/__init__.py:120) | `ser_lib.engine.ExperimentConfig` | 是（迁移/合并） | `ser_lib/config/experiment.py:ExperimentConfig` |
| `ser_lib.ExperimentPresetInfo` | [ser_lib/__init__.py:120](D:/projects/Speech-Emotion-Recognition/ser_lib/__init__.py:120) | `ser_lib.engine.ExperimentPresetInfo` | 是（迁移） | `ser_lib.config.presets.ExperimentPresetInfo` |
| `ser_lib.ExperimentPresetCatalog` | [ser_lib/__init__.py:120](D:/projects/Speech-Emotion-Recognition/ser_lib/__init__.py:120) | `ser_lib.engine.ExperimentPresetCatalog` | 否 | `移除包装；见正文替代 API` |
| `ser_lib.PresetStatus` | [ser_lib/__init__.py:120](D:/projects/Speech-Emotion-Recognition/ser_lib/__init__.py:120) | `ser_lib.engine.PresetStatus` | 是（迁移） | `ser_lib.config.presets.PresetStatus` |
| `ser_lib.list_experiment_presets` | [ser_lib/__init__.py:120](D:/projects/Speech-Emotion-Recognition/ser_lib/__init__.py:120) | `ser_lib.engine.list_experiment_presets` | 是（迁移） | `ser_lib.config.presets.list_experiment_presets` |
| `ser_lib.get_experiment_preset` | [ser_lib/__init__.py:120](D:/projects/Speech-Emotion-Recognition/ser_lib/__init__.py:120) | `ser_lib.engine.get_experiment_preset` | 是（迁移） | `ser_lib.config.presets.get_experiment_preset` |
| `ser_lib.build_experiment_config` | [ser_lib/__init__.py:120](D:/projects/Speech-Emotion-Recognition/ser_lib/__init__.py:120) | `ser_lib.engine.build_experiment_config` | 是（迁移） | `ser_lib.config.presets.build_experiment_config` |
| `ser_lib.ExperimentValidationResult` | [ser_lib/__init__.py:120](D:/projects/Speech-Emotion-Recognition/ser_lib/__init__.py:120) | `ser_lib.engine.ExperimentValidationResult` | 是（领域规范入口） | `ser_lib.engine.validation.ExperimentValidationResult` |
| `ser_lib.validate_experiment` | [ser_lib/__init__.py:120](D:/projects/Speech-Emotion-Recognition/ser_lib/__init__.py:120) | `ser_lib.engine.validate_experiment` | 是（领域规范入口） | `ser_lib.engine.validation.validate_experiment` |
| `ser_lib.ModelConfig` | [ser_lib/__init__.py:120](D:/projects/Speech-Emotion-Recognition/ser_lib/__init__.py:120) | `ser_lib.engine.ModelConfig` | 是（迁移/合并） | `ser_lib/config/model.py:ModelConfig` |
| `ser_lib.build_experiment_components` | [ser_lib/__init__.py:120](D:/projects/Speech-Emotion-Recognition/ser_lib/__init__.py:120) | `ser_lib.engine.build_experiment_components` | 是（迁移） | `ser_lib.engine.experiment.build_experiment_components` |
| `ser_lib.EmotionPredictor` | [ser_lib/__init__.py:120](D:/projects/Speech-Emotion-Recognition/ser_lib/__init__.py:120) | `ser_lib.inference.EmotionPredictor` | 是（领域规范入口） | `ser_lib.inference.offline.EmotionPredictor` |
| `ser_lib.PredictionResult` | [ser_lib/__init__.py:120](D:/projects/Speech-Emotion-Recognition/ser_lib/__init__.py:120) | `ser_lib.inference.PredictionResult` | 是（领域规范入口） | `ser_lib.inference.offline.PredictionResult` |
| `ser_lib.PredictionFailure` | [ser_lib/__init__.py:120](D:/projects/Speech-Emotion-Recognition/ser_lib/__init__.py:120) | `ser_lib.inference.PredictionFailure` | 是（领域规范入口） | `ser_lib.inference.batch.PredictionFailure` |
| `ser_lib.BatchPredictionSink` | [ser_lib/__init__.py:120](D:/projects/Speech-Emotion-Recognition/ser_lib/__init__.py:120) | `ser_lib.inference.BatchPredictionSink` | 是（领域规范入口） | `ser_lib.inference.batch.BatchPredictionSink` |
| `ser_lib.JsonlBatchPredictionSink` | [ser_lib/__init__.py:120](D:/projects/Speech-Emotion-Recognition/ser_lib/__init__.py:120) | `ser_lib.inference.JsonlBatchPredictionSink` | 是（领域规范入口） | `ser_lib.inference.batch.JsonlBatchPredictionSink` |
| `ser_lib.BatchPredictionResult` | [ser_lib/__init__.py:120](D:/projects/Speech-Emotion-Recognition/ser_lib/__init__.py:120) | `ser_lib.inference.BatchPredictionResult` | 是（领域规范入口） | `ser_lib.inference.batch.BatchPredictionResult` |
| `ser_lib.BatchEmotionPredictor` | [ser_lib/__init__.py:120](D:/projects/Speech-Emotion-Recognition/ser_lib/__init__.py:120) | `ser_lib.inference.BatchEmotionPredictor` | 是（领域规范入口） | `ser_lib.inference.batch.BatchEmotionPredictor` |
| `ser_lib.write_batch_predictions` | [ser_lib/__init__.py:120](D:/projects/Speech-Emotion-Recognition/ser_lib/__init__.py:120) | `ser_lib.inference.write_batch_predictions` | 是（领域规范入口） | `ser_lib.inference.batch.write_batch_predictions` |
| `ser_lib.StreamingConfig` | [ser_lib/__init__.py:120](D:/projects/Speech-Emotion-Recognition/ser_lib/__init__.py:120) | `ser_lib.inference.StreamingConfig` | 是（迁移/合并） | `ser_lib/config/inference.py:StreamingConfig` |
| `ser_lib.StreamingPrediction` | [ser_lib/__init__.py:120](D:/projects/Speech-Emotion-Recognition/ser_lib/__init__.py:120) | `ser_lib.inference.StreamingPrediction` | 是（领域规范入口） | `ser_lib.inference.streaming.StreamingPrediction` |
| `ser_lib.StreamingLatency` | [ser_lib/__init__.py:120](D:/projects/Speech-Emotion-Recognition/ser_lib/__init__.py:120) | `ser_lib.inference.StreamingLatency` | 是（领域规范入口） | `ser_lib.inference.streaming.StreamingLatency` |
| `ser_lib.StreamingEmotionRecognizer` | [ser_lib/__init__.py:120](D:/projects/Speech-Emotion-Recognition/ser_lib/__init__.py:120) | `ser_lib.inference.StreamingEmotionRecognizer` | 是（领域规范入口） | `ser_lib.inference.streaming.StreamingEmotionRecognizer` |
| `ser_lib.artifacts.ModelCard` | [ser_lib/artifacts/__init__.py:16](D:/projects/Speech-Emotion-Recognition/ser_lib/artifacts/__init__.py:16) | `ser_lib.artifacts.manifest.ModelCard` | 是（领域规范入口） | `ser_lib.artifacts.manifest.ModelCard` |
| `ser_lib.artifacts.ModelArtifactManifest` | [ser_lib/artifacts/__init__.py:16](D:/projects/Speech-Emotion-Recognition/ser_lib/artifacts/__init__.py:16) | `ser_lib.artifacts.manifest.ModelArtifactManifest` | 是（领域规范入口） | `ser_lib.artifacts.manifest.ModelArtifactManifest` |
| `ser_lib.artifacts.LoadedArtifact` | [ser_lib/artifacts/__init__.py:16](D:/projects/Speech-Emotion-Recognition/ser_lib/artifacts/__init__.py:16) | `ser_lib.artifacts.loader.LoadedArtifact` | 是（领域规范入口） | `ser_lib.artifacts.loader.LoadedArtifact` |
| `ser_lib.artifacts.ArtifactInfo` | [ser_lib/artifacts/__init__.py:16](D:/projects/Speech-Emotion-Recognition/ser_lib/artifacts/__init__.py:16) | `ser_lib.artifacts.catalog.ArtifactInfo` | 替换 | `ser_lib.artifacts.ArtifactEntry（拟议）` |
| `ser_lib.artifacts.ArtifactScanFailure` | [ser_lib/artifacts/__init__.py:16](D:/projects/Speech-Emotion-Recognition/ser_lib/artifacts/__init__.py:16) | `ser_lib.artifacts.catalog.ArtifactScanFailure` | 是（领域规范入口） | `ser_lib.artifacts.catalog.ArtifactScanFailure` |
| `ser_lib.artifacts.ArtifactCatalog` | [ser_lib/artifacts/__init__.py:16](D:/projects/Speech-Emotion-Recognition/ser_lib/artifacts/__init__.py:16) | `ser_lib.artifacts.catalog.ArtifactCatalog` | 是（领域规范入口） | `ser_lib.artifacts.catalog.ArtifactCatalog` |
| `ser_lib.artifacts.scan_model_artifacts` | [ser_lib/artifacts/__init__.py:16](D:/projects/Speech-Emotion-Recognition/ser_lib/artifacts/__init__.py:16) | `ser_lib.artifacts.catalog.scan_model_artifacts` | 是（领域规范入口） | `ser_lib.artifacts.catalog.scan_model_artifacts` |
| `ser_lib.artifacts.export_model_artifact` | [ser_lib/artifacts/__init__.py:16](D:/projects/Speech-Emotion-Recognition/ser_lib/artifacts/__init__.py:16) | `ser_lib.artifacts.exporter.export_model_artifact` | 是（领域规范入口） | `ser_lib.artifacts.exporter.export_model_artifact` |
| `ser_lib.artifacts.inspect_model_artifact` | [ser_lib/artifacts/__init__.py:16](D:/projects/Speech-Emotion-Recognition/ser_lib/artifacts/__init__.py:16) | `ser_lib.artifacts.loader.inspect_model_artifact` | 是（领域规范入口） | `ser_lib.artifacts.loader.inspect_model_artifact` |
| `ser_lib.artifacts.verify_model_artifact` | [ser_lib/artifacts/__init__.py:16](D:/projects/Speech-Emotion-Recognition/ser_lib/artifacts/__init__.py:16) | `ser_lib.artifacts.loader.verify_model_artifact` | 是（领域规范入口） | `ser_lib.artifacts.loader.verify_model_artifact` |
| `ser_lib.artifacts.load_model_artifact` | [ser_lib/artifacts/__init__.py:16](D:/projects/Speech-Emotion-Recognition/ser_lib/artifacts/__init__.py:16) | `ser_lib.artifacts.loader.load_model_artifact` | 是（领域规范入口） | `ser_lib.artifacts.loader.load_model_artifact` |
| `ser_lib.artifacts.catalog.ArtifactInfo` | [ser_lib/artifacts/catalog.py:206](D:/projects/Speech-Emotion-Recognition/ser_lib/artifacts/catalog.py:206) | `ser_lib.artifacts.catalog.ArtifactInfo` | 替换 | `ser_lib.artifacts.ArtifactEntry（拟议）` |
| `ser_lib.artifacts.catalog.ArtifactScanFailure` | [ser_lib/artifacts/catalog.py:206](D:/projects/Speech-Emotion-Recognition/ser_lib/artifacts/catalog.py:206) | `ser_lib.artifacts.catalog.ArtifactScanFailure` | 是（领域规范入口） | `ser_lib.artifacts.catalog.ArtifactScanFailure` |
| `ser_lib.artifacts.catalog.ArtifactCatalog` | [ser_lib/artifacts/catalog.py:206](D:/projects/Speech-Emotion-Recognition/ser_lib/artifacts/catalog.py:206) | `ser_lib.artifacts.catalog.ArtifactCatalog` | 是（领域规范入口） | `ser_lib.artifacts.catalog.ArtifactCatalog` |
| `ser_lib.artifacts.catalog.scan_model_artifacts` | [ser_lib/artifacts/catalog.py:206](D:/projects/Speech-Emotion-Recognition/ser_lib/artifacts/catalog.py:206) | `ser_lib.artifacts.catalog.scan_model_artifacts` | 是（领域规范入口） | `ser_lib.artifacts.catalog.scan_model_artifacts` |
| `ser_lib.artifacts.exporter.export_model_artifact` | [ser_lib/artifacts/exporter.py:356](D:/projects/Speech-Emotion-Recognition/ser_lib/artifacts/exporter.py:356) | `ser_lib.artifacts.exporter.export_model_artifact` | 是（领域规范入口） | `ser_lib.artifacts.exporter.export_model_artifact` |
| `ser_lib.artifacts.loader.LoadedArtifact` | [ser_lib/artifacts/loader.py:321](D:/projects/Speech-Emotion-Recognition/ser_lib/artifacts/loader.py:321) | `ser_lib.artifacts.loader.LoadedArtifact` | 是（领域规范入口） | `ser_lib.artifacts.loader.LoadedArtifact` |
| `ser_lib.artifacts.loader.inspect_model_artifact` | [ser_lib/artifacts/loader.py:321](D:/projects/Speech-Emotion-Recognition/ser_lib/artifacts/loader.py:321) | `ser_lib.artifacts.loader.inspect_model_artifact` | 是（领域规范入口） | `ser_lib.artifacts.loader.inspect_model_artifact` |
| `ser_lib.artifacts.loader.verify_model_artifact` | [ser_lib/artifacts/loader.py:321](D:/projects/Speech-Emotion-Recognition/ser_lib/artifacts/loader.py:321) | `ser_lib.artifacts.loader.verify_model_artifact` | 是（领域规范入口） | `ser_lib.artifacts.loader.verify_model_artifact` |
| `ser_lib.artifacts.loader.load_model_artifact` | [ser_lib/artifacts/loader.py:321](D:/projects/Speech-Emotion-Recognition/ser_lib/artifacts/loader.py:321) | `ser_lib.artifacts.loader.load_model_artifact` | 是（领域规范入口） | `ser_lib.artifacts.loader.load_model_artifact` |
| `ser_lib.artifacts.manifest.ModelCard` | [ser_lib/artifacts/manifest.py:92](D:/projects/Speech-Emotion-Recognition/ser_lib/artifacts/manifest.py:92) | `ser_lib.artifacts.manifest.ModelCard` | 是（领域规范入口） | `ser_lib.artifacts.manifest.ModelCard` |
| `ser_lib.artifacts.manifest.ModelArtifactManifest` | [ser_lib/artifacts/manifest.py:92](D:/projects/Speech-Emotion-Recognition/ser_lib/artifacts/manifest.py:92) | `ser_lib.artifacts.manifest.ModelArtifactManifest` | 是（领域规范入口） | `ser_lib.artifacts.manifest.ModelArtifactManifest` |
| `ser_lib.benchmark.BenchmarkResult` | [ser_lib/benchmark.py:137](D:/projects/Speech-Emotion-Recognition/ser_lib/benchmark.py:137) | `ser_lib.benchmark.BenchmarkResult` | 是（迁移） | `ser_lib/engine/benchmark.py:BenchmarkResult` |
| `ser_lib.benchmark.BenchmarkComparison` | [ser_lib/benchmark.py:137](D:/projects/Speech-Emotion-Recognition/ser_lib/benchmark.py:137) | `ser_lib.benchmark.BenchmarkComparison` | 是（迁移） | `ser_lib/engine/benchmark.py:BenchmarkComparison` |
| `ser_lib.benchmark.run_benchmark` | [ser_lib/benchmark.py:137](D:/projects/Speech-Emotion-Recognition/ser_lib/benchmark.py:137) | `ser_lib.benchmark.run_benchmark` | 是（迁移） | `ser_lib/engine/benchmark.py:run_benchmark` |
| `ser_lib.benchmark.compare_benchmarks` | [ser_lib/benchmark.py:137](D:/projects/Speech-Emotion-Recognition/ser_lib/benchmark.py:137) | `ser_lib.benchmark.compare_benchmarks` | 是（迁移） | `ser_lib/engine/benchmark.py:compare_benchmarks` |
| `ser_lib.benchmark.write_benchmark_result` | [ser_lib/benchmark.py:137](D:/projects/Speech-Emotion-Recognition/ser_lib/benchmark.py:137) | `ser_lib.benchmark.write_benchmark_result` | 是（迁移） | `ser_lib/engine/benchmark.py:write_benchmark_result` |
| `ser_lib.benchmark.load_benchmark_result` | [ser_lib/benchmark.py:137](D:/projects/Speech-Emotion-Recognition/ser_lib/benchmark.py:137) | `ser_lib.benchmark.load_benchmark_result` | 是（迁移） | `ser_lib/engine/benchmark.py:load_benchmark_result` |
| `ser_lib.catalog.CATALOG_SCHEMA_VERSION` | [ser_lib/catalog.py:280](D:/projects/Speech-Emotion-Recognition/ser_lib/catalog.py:280) | `ser_lib.catalog.CATALOG_SCHEMA_VERSION` | 否 | `移除包装；见正文替代 API` |
| `ser_lib.catalog.CATALOG_CATEGORIES` | [ser_lib/catalog.py:280](D:/projects/Speech-Emotion-Recognition/ser_lib/catalog.py:280) | `ser_lib.catalog.CATALOG_CATEGORIES` | 否 | `移除包装；见正文替代 API` |
| `ser_lib.catalog.ComponentDescriptor` | [ser_lib/catalog.py:280](D:/projects/Speech-Emotion-Recognition/ser_lib/catalog.py:280) | `ser_lib.data.registry.ComponentDescriptor` | 是（领域规范入口） | `ser_lib.data.registry.ComponentDescriptor` |
| `ser_lib.catalog.ComponentCatalog` | [ser_lib/catalog.py:280](D:/projects/Speech-Emotion-Recognition/ser_lib/catalog.py:280) | `ser_lib.catalog.ComponentCatalog` | 否 | `移除包装；见正文替代 API` |
| `ser_lib.catalog.get_component_catalog` | [ser_lib/catalog.py:280](D:/projects/Speech-Emotion-Recognition/ser_lib/catalog.py:280) | `ser_lib.catalog.get_component_catalog` | 否 | `移除包装；见正文替代 API` |
| `ser_lib.catalog.list_component_descriptors` | [ser_lib/catalog.py:280](D:/projects/Speech-Emotion-Recognition/ser_lib/catalog.py:280) | `ser_lib.catalog.list_component_descriptors` | 否 | `移除包装；见正文替代 API` |
| `ser_lib.cli.main` | [ser_lib/cli/__init__.py:5](D:/projects/Speech-Emotion-Recognition/ser_lib/cli/__init__.py:5) | `ser_lib.cli.main.main` | 是（领域规范入口） | `ser_lib.cli.main.main` |
| `ser_lib.cli.workflows.train_experiment` | [ser_lib/cli/workflows.py:342](D:/projects/Speech-Emotion-Recognition/ser_lib/cli/workflows.py:342) | `ser_lib.cli.workflows.train_experiment` | 是（领域规范入口） | `ser_lib.cli.workflows.train_experiment` |
| `ser_lib.cli.workflows.evaluate_artifact` | [ser_lib/cli/workflows.py:342](D:/projects/Speech-Emotion-Recognition/ser_lib/cli/workflows.py:342) | `ser_lib.cli.workflows.evaluate_artifact` | 是（领域规范入口） | `ser_lib.cli.workflows.evaluate_artifact` |
| `ser_lib.cli.workflows.predict_artifact` | [ser_lib/cli/workflows.py:342](D:/projects/Speech-Emotion-Recognition/ser_lib/cli/workflows.py:342) | `ser_lib.cli.workflows.predict_artifact` | 是（领域规范入口） | `ser_lib.cli.workflows.predict_artifact` |
| `ser_lib.cli.workflows.export_checkpoint_artifact` | [ser_lib/cli/workflows.py:342](D:/projects/Speech-Emotion-Recognition/ser_lib/cli/workflows.py:342) | `ser_lib.cli.workflows.export_checkpoint_artifact` | 是（领域规范入口） | `ser_lib.cli.workflows.export_checkpoint_artifact` |
| `ser_lib.cli.workflows.inspect_artifact` | [ser_lib/cli/workflows.py:342](D:/projects/Speech-Emotion-Recognition/ser_lib/cli/workflows.py:342) | `ser_lib.cli.workflows.inspect_artifact` | 是（领域规范入口） | `ser_lib.cli.workflows.inspect_artifact` |
| `ser_lib.core.SERError` | [ser_lib/core/__init__.py:42](D:/projects/Speech-Emotion-Recognition/ser_lib/core/__init__.py:42) | `ser_lib.core.exceptions.SERError` | 是（迁移） | `ser_lib/foundation/errors.py:SERError` |
| `ser_lib.core.ConfigurationError` | [ser_lib/core/__init__.py:42](D:/projects/Speech-Emotion-Recognition/ser_lib/core/__init__.py:42) | `ser_lib.core.exceptions.ConfigurationError` | 是（迁移） | `ser_lib/foundation/errors.py:ConfigurationError` |
| `ser_lib.core.SchemaMigrationError` | [ser_lib/core/__init__.py:42](D:/projects/Speech-Emotion-Recognition/ser_lib/core/__init__.py:42) | `ser_lib.core.exceptions.SchemaMigrationError` | 是（迁移） | `ser_lib/foundation/errors.py:SchemaMigrationError` |
| `ser_lib.core.OperationCancelled` | [ser_lib/core/__init__.py:42](D:/projects/Speech-Emotion-Recognition/ser_lib/core/__init__.py:42) | `ser_lib.core.exceptions.OperationCancelled` | 是（迁移） | `ser_lib/foundation/errors.py:OperationCancelled` |
| `ser_lib.core.Diagnostic` | [ser_lib/core/__init__.py:42](D:/projects/Speech-Emotion-Recognition/ser_lib/core/__init__.py:42) | `ser_lib.core.diagnostics.Diagnostic` | 是（迁移） | `ser_lib/foundation/diagnostics.py:Diagnostic` |
| `ser_lib.core.DiagnosticSeverity` | [ser_lib/core/__init__.py:42](D:/projects/Speech-Emotion-Recognition/ser_lib/core/__init__.py:42) | `ser_lib.core.diagnostics.DiagnosticSeverity` | 是（迁移） | `ser_lib/foundation/diagnostics.py:DiagnosticSeverity` |
| `ser_lib.core.StrictConfig` | [ser_lib/core/__init__.py:42](D:/projects/Speech-Emotion-Recognition/ser_lib/core/__init__.py:42) | `ser_lib.core.config.StrictConfig` | 是（迁移/合并） | `ser_lib/config/base.py:StrictConfig` |
| `ser_lib.core.load_yaml_mapping` | [ser_lib/core/__init__.py:42](D:/projects/Speech-Emotion-Recognition/ser_lib/core/__init__.py:42) | `ser_lib.core.config.load_yaml_mapping` | 是（迁移） | `ser_lib.config.load_yaml_mapping` |
| `ser_lib.core.load_versioned_config` | [ser_lib/core/__init__.py:42](D:/projects/Speech-Emotion-Recognition/ser_lib/core/__init__.py:42) | `ser_lib.core.config.load_versioned_config` | 是（迁移） | `ser_lib.config.load_versioned_config` |
| `ser_lib.core.require_schema_version` | [ser_lib/core/__init__.py:42](D:/projects/Speech-Emotion-Recognition/ser_lib/core/__init__.py:42) | `ser_lib.core.config.require_schema_version` | 是（迁移） | `ser_lib.config.require_schema_version` |
| `ser_lib.core.resolve_config_path` | [ser_lib/core/__init__.py:42](D:/projects/Speech-Emotion-Recognition/ser_lib/core/__init__.py:42) | `ser_lib.core.config.resolve_config_path` | 是（迁移） | `ser_lib.config.resolve_config_path` |
| `ser_lib.core.MigrationFunction` | [ser_lib/core/__init__.py:42](D:/projects/Speech-Emotion-Recognition/ser_lib/core/__init__.py:42) | `ser_lib.core.migrations.MigrationFunction` | 替换 | `领域 migrations；不保留全局注册 facade` |
| `ser_lib.core.SchemaMigration` | [ser_lib/core/__init__.py:42](D:/projects/Speech-Emotion-Recognition/ser_lib/core/__init__.py:42) | `ser_lib.core.migrations.SchemaMigration` | 替换 | `领域 migrations；不保留全局注册 facade` |
| `ser_lib.core.MigrationRegistry` | [ser_lib/core/__init__.py:42](D:/projects/Speech-Emotion-Recognition/ser_lib/core/__init__.py:42) | `ser_lib.core.migrations.MigrationRegistry` | 替换 | `领域 migrations；不保留全局注册 facade` |
| `ser_lib.core.validate_schema_version` | [ser_lib/core/__init__.py:42](D:/projects/Speech-Emotion-Recognition/ser_lib/core/__init__.py:42) | `ser_lib.core.migrations.validate_schema_version` | 替换 | `领域 migrations；不保留全局注册 facade` |
| `ser_lib.core.register_schema_migration` | [ser_lib/core/__init__.py:42](D:/projects/Speech-Emotion-Recognition/ser_lib/core/__init__.py:42) | `ser_lib.core.migrations.register_schema_migration` | 替换 | `领域 migrations；不保留全局注册 facade` |
| `ser_lib.core.list_schema_migrations` | [ser_lib/core/__init__.py:42](D:/projects/Speech-Emotion-Recognition/ser_lib/core/__init__.py:42) | `ser_lib.core.migrations.list_schema_migrations` | 替换 | `领域 migrations；不保留全局注册 facade` |
| `ser_lib.core.migrate_schema_payload` | [ser_lib/core/__init__.py:42](D:/projects/Speech-Emotion-Recognition/ser_lib/core/__init__.py:42) | `ser_lib.core.migrations.migrate_schema_payload` | 替换 | `领域 migrations；不保留全局注册 facade` |
| `ser_lib.core.EVENT_SCHEMA_VERSION` | [ser_lib/core/__init__.py:42](D:/projects/Speech-Emotion-Recognition/ser_lib/core/__init__.py:42) | `ser_lib.core.events.EVENT_SCHEMA_VERSION` | 是（迁移） | `ser_lib/foundation/events.py; ser_lib/engine/events.py; ser_lib/inference/events.py:EVENT_SCHEMA_VERSION` |
| `ser_lib.core.EventContext` | [ser_lib/core/__init__.py:42](D:/projects/Speech-Emotion-Recognition/ser_lib/core/__init__.py:42) | `ser_lib.core.events.EventContext` | 是（迁移） | `ser_lib/foundation/events.py; ser_lib/engine/events.py; ser_lib/inference/events.py:EventContext` |
| `ser_lib.core.ProgressEvent` | [ser_lib/core/__init__.py:42](D:/projects/Speech-Emotion-Recognition/ser_lib/core/__init__.py:42) | `ser_lib.core.events.ProgressEvent` | 是（迁移） | `ser_lib/foundation/events.py; ser_lib/engine/events.py; ser_lib/inference/events.py:ProgressEvent` |
| `ser_lib.core.MetricEvent` | [ser_lib/core/__init__.py:42](D:/projects/Speech-Emotion-Recognition/ser_lib/core/__init__.py:42) | `ser_lib.core.events.MetricEvent` | 是（迁移） | `ser_lib/foundation/events.py; ser_lib/engine/events.py; ser_lib/inference/events.py:MetricEvent` |
| `ser_lib.core.LogEvent` | [ser_lib/core/__init__.py:42](D:/projects/Speech-Emotion-Recognition/ser_lib/core/__init__.py:42) | `ser_lib.core.events.LogEvent` | 是（迁移） | `ser_lib/foundation/events.py; ser_lib/engine/events.py; ser_lib/inference/events.py:LogEvent` |
| `ser_lib.core.LifecycleEvent` | [ser_lib/core/__init__.py:42](D:/projects/Speech-Emotion-Recognition/ser_lib/core/__init__.py:42) | `ser_lib.core.events.LifecycleEvent` | 是（迁移） | `ser_lib/foundation/events.py; ser_lib/engine/events.py; ser_lib/inference/events.py:LifecycleEvent` |
| `ser_lib.core.CheckpointEvent` | [ser_lib/core/__init__.py:42](D:/projects/Speech-Emotion-Recognition/ser_lib/core/__init__.py:42) | `ser_lib.core.events.CheckpointEvent` | 是（迁移） | `ser_lib.engine.events.CheckpointEvent` |
| `ser_lib.core.PredictionEvent` | [ser_lib/core/__init__.py:42](D:/projects/Speech-Emotion-Recognition/ser_lib/core/__init__.py:42) | `ser_lib.core.events.PredictionEvent` | 是（迁移） | `ser_lib.inference.events.PredictionEvent` |
| `ser_lib.core.LibraryEvent` | [ser_lib/core/__init__.py:42](D:/projects/Speech-Emotion-Recognition/ser_lib/core/__init__.py:42) | `ser_lib.core.events.LibraryEvent` | 是（迁移） | `ser_lib/foundation/events.py; ser_lib/engine/events.py; ser_lib/inference/events.py:LibraryEvent` |
| `ser_lib.core.EventCallback` | [ser_lib/core/__init__.py:42](D:/projects/Speech-Emotion-Recognition/ser_lib/core/__init__.py:42) | `ser_lib.core.events.EventCallback` | 是（迁移） | `ser_lib/foundation/events.py; ser_lib/engine/events.py; ser_lib/inference/events.py:EventCallback` |
| `ser_lib.core.CancellationCheck` | [ser_lib/core/__init__.py:42](D:/projects/Speech-Emotion-Recognition/ser_lib/core/__init__.py:42) | `ser_lib.core.events.CancellationCheck` | 是（迁移） | `ser_lib/foundation/events.py; ser_lib/engine/events.py; ser_lib/inference/events.py:CancellationCheck` |
| `ser_lib.core.CancellationToken` | [ser_lib/core/__init__.py:42](D:/projects/Speech-Emotion-Recognition/ser_lib/core/__init__.py:42) | `ser_lib.core.events.CancellationToken` | 是（迁移） | `ser_lib/foundation/events.py; ser_lib/engine/events.py; ser_lib/inference/events.py:CancellationToken` |
| `ser_lib.core.get_logger` | [ser_lib/core/__init__.py:42](D:/projects/Speech-Emotion-Recognition/ser_lib/core/__init__.py:42) | `ser_lib.core.logging.get_logger` | 是（迁移） | `ser_lib/foundation/logging.py:get_logger` |
| `ser_lib.core.configure_library_logging` | [ser_lib/core/__init__.py:42](D:/projects/Speech-Emotion-Recognition/ser_lib/core/__init__.py:42) | `ser_lib.core.logging.configure_library_logging` | 是（迁移） | `ser_lib/foundation/logging.py:configure_library_logging` |
| `ser_lib.core._catalog_scan.scan_catalog_candidates` | [ser_lib/core/_catalog_scan.py:67](D:/projects/Speech-Emotion-Recognition/ser_lib/core/_catalog_scan.py:67) | `ser_lib.core._catalog_scan.scan_catalog_candidates` | 是（迁移） | `data/history.py; engine/*catalog.py/runs.py; artifacts/catalog.py 内私有循环:scan_catalog_candidates` |
| `ser_lib.core.diagnostics.Diagnostic` | [ser_lib/core/diagnostics.py:119](D:/projects/Speech-Emotion-Recognition/ser_lib/core/diagnostics.py:119) | `ser_lib.core.diagnostics.Diagnostic` | 是（迁移） | `ser_lib/foundation/diagnostics.py:Diagnostic` |
| `ser_lib.core.diagnostics.DiagnosticSeverity` | [ser_lib/core/diagnostics.py:119](D:/projects/Speech-Emotion-Recognition/ser_lib/core/diagnostics.py:119) | `ser_lib.core.diagnostics.DiagnosticSeverity` | 是（迁移） | `ser_lib/foundation/diagnostics.py:DiagnosticSeverity` |
| `ser_lib.core.migrations.MigrationFunction` | [ser_lib/core/migrations.py:192](D:/projects/Speech-Emotion-Recognition/ser_lib/core/migrations.py:192) | `ser_lib.core.migrations.MigrationFunction` | 替换 | `领域 migrations；不保留全局注册 facade` |
| `ser_lib.core.migrations.SchemaMigration` | [ser_lib/core/migrations.py:192](D:/projects/Speech-Emotion-Recognition/ser_lib/core/migrations.py:192) | `ser_lib.core.migrations.SchemaMigration` | 替换 | `领域 migrations；不保留全局注册 facade` |
| `ser_lib.core.migrations.MigrationRegistry` | [ser_lib/core/migrations.py:192](D:/projects/Speech-Emotion-Recognition/ser_lib/core/migrations.py:192) | `ser_lib.core.migrations.MigrationRegistry` | 替换 | `领域 migrations；不保留全局注册 facade` |
| `ser_lib.core.migrations.validate_schema_version` | [ser_lib/core/migrations.py:192](D:/projects/Speech-Emotion-Recognition/ser_lib/core/migrations.py:192) | `ser_lib.core.migrations.validate_schema_version` | 替换 | `领域 migrations；不保留全局注册 facade` |
| `ser_lib.core.migrations.register_schema_migration` | [ser_lib/core/migrations.py:192](D:/projects/Speech-Emotion-Recognition/ser_lib/core/migrations.py:192) | `ser_lib.core.migrations.register_schema_migration` | 替换 | `领域 migrations；不保留全局注册 facade` |
| `ser_lib.core.migrations.list_schema_migrations` | [ser_lib/core/migrations.py:192](D:/projects/Speech-Emotion-Recognition/ser_lib/core/migrations.py:192) | `ser_lib.core.migrations.list_schema_migrations` | 替换 | `领域 migrations；不保留全局注册 facade` |
| `ser_lib.core.migrations.migrate_schema_payload` | [ser_lib/core/migrations.py:192](D:/projects/Speech-Emotion-Recognition/ser_lib/core/migrations.py:192) | `ser_lib.core.migrations.migrate_schema_payload` | 替换 | `领域 migrations；不保留全局注册 facade` |
| `ser_lib.data.AudioRecord` | [ser_lib/data/__init__.py:49](D:/projects/Speech-Emotion-Recognition/ser_lib/data/__init__.py:49) | `ser_lib.data.types.AudioRecord` | 是（领域规范入口） | `ser_lib.data.types.AudioRecord` |
| `ser_lib.data.AudioData` | [ser_lib/data/__init__.py:49](D:/projects/Speech-Emotion-Recognition/ser_lib/data/__init__.py:49) | `ser_lib.data.types.AudioData` | 是（领域规范入口） | `ser_lib.data.types.AudioData` |
| `ser_lib.data.TensorSpec` | [ser_lib/data/__init__.py:49](D:/projects/Speech-Emotion-Recognition/ser_lib/data/__init__.py:49) | `ser_lib.data.types.TensorSpec` | 是（领域规范入口） | `ser_lib.data.types.TensorSpec` |
| `ser_lib.data.RepresentationOutput` | [ser_lib/data/__init__.py:49](D:/projects/Speech-Emotion-Recognition/ser_lib/data/__init__.py:49) | `ser_lib.data.types.RepresentationOutput` | 是（领域规范入口） | `ser_lib.data.types.RepresentationOutput` |
| `ser_lib.data.SERSample` | [ser_lib/data/__init__.py:49](D:/projects/Speech-Emotion-Recognition/ser_lib/data/__init__.py:49) | `ser_lib.data.types.SERSample` | 是（领域规范入口） | `ser_lib.data.types.SERSample` |
| `ser_lib.data.SERBatch` | [ser_lib/data/__init__.py:49](D:/projects/Speech-Emotion-Recognition/ser_lib/data/__init__.py:49) | `ser_lib.data.types.SERBatch` | 是（领域规范入口） | `ser_lib.data.types.SERBatch` |
| `ser_lib.data.validate_sample_contract` | [ser_lib/data/__init__.py:49](D:/projects/Speech-Emotion-Recognition/ser_lib/data/__init__.py:49) | `ser_lib.data.types.validate_sample_contract` | 是（领域规范入口） | `ser_lib.data.types.validate_sample_contract` |
| `ser_lib.data.SERDataError` | [ser_lib/data/__init__.py:49](D:/projects/Speech-Emotion-Recognition/ser_lib/data/__init__.py:49) | `ser_lib.data.errors.SERDataError` | 是（领域规范入口） | `ser_lib.data.errors.SERDataError` |
| `ser_lib.data.ManifestError` | [ser_lib/data/__init__.py:49](D:/projects/Speech-Emotion-Recognition/ser_lib/data/__init__.py:49) | `ser_lib.data.errors.ManifestError` | 是（领域规范入口） | `ser_lib.data.errors.ManifestError` |
| `ser_lib.data.DatasetEditError` | [ser_lib/data/__init__.py:49](D:/projects/Speech-Emotion-Recognition/ser_lib/data/__init__.py:49) | `ser_lib.data.errors.DatasetEditError` | 是（领域规范入口） | `ser_lib.data.errors.DatasetEditError` |
| `ser_lib.data.DatasetEditConflictError` | [ser_lib/data/__init__.py:49](D:/projects/Speech-Emotion-Recognition/ser_lib/data/__init__.py:49) | `ser_lib.data.errors.DatasetEditConflictError` | 是（领域规范入口） | `ser_lib.data.errors.DatasetEditConflictError` |
| `ser_lib.data.DatasetTransactionError` | [ser_lib/data/__init__.py:49](D:/projects/Speech-Emotion-Recognition/ser_lib/data/__init__.py:49) | `ser_lib.data.errors.DatasetTransactionError` | 是（领域规范入口） | `ser_lib.data.errors.DatasetTransactionError` |
| `ser_lib.data.AudioNotFoundError` | [ser_lib/data/__init__.py:49](D:/projects/Speech-Emotion-Recognition/ser_lib/data/__init__.py:49) | `ser_lib.data.errors.AudioNotFoundError` | 是（领域规范入口） | `ser_lib.data.errors.AudioNotFoundError` |
| `ser_lib.data.AudioDecodeError` | [ser_lib/data/__init__.py:49](D:/projects/Speech-Emotion-Recognition/ser_lib/data/__init__.py:49) | `ser_lib.data.errors.AudioDecodeError` | 是（领域规范入口） | `ser_lib.data.errors.AudioDecodeError` |
| `ser_lib.data.InvalidAudioSegmentError` | [ser_lib/data/__init__.py:49](D:/projects/Speech-Emotion-Recognition/ser_lib/data/__init__.py:49) | `ser_lib.data.errors.InvalidAudioSegmentError` | 是（领域规范入口） | `ser_lib.data.errors.InvalidAudioSegmentError` |
| `ser_lib.data.RepresentationError` | [ser_lib/data/__init__.py:49](D:/projects/Speech-Emotion-Recognition/ser_lib/data/__init__.py:49) | `ser_lib.data.errors.RepresentationError` | 是（领域规范入口） | `ser_lib.data.errors.RepresentationError` |
| `ser_lib.data.TransformError` | [ser_lib/data/__init__.py:49](D:/projects/Speech-Emotion-Recognition/ser_lib/data/__init__.py:49) | `ser_lib.data.errors.TransformError` | 是（领域规范入口） | `ser_lib.data.errors.TransformError` |
| `ser_lib.data.CollationError` | [ser_lib/data/__init__.py:49](D:/projects/Speech-Emotion-Recognition/ser_lib/data/__init__.py:49) | `ser_lib.data.errors.CollationError` | 是（领域规范入口） | `ser_lib.data.errors.CollationError` |
| `ser_lib.data.CompatibilityError` | [ser_lib/data/__init__.py:49](D:/projects/Speech-Emotion-Recognition/ser_lib/data/__init__.py:49) | `ser_lib.data.errors.CompatibilityError` | 是（迁移） | `ser_lib.engine.compatibility.CompatibilityError` |
| `ser_lib.data.RegistryError` | [ser_lib/data/__init__.py:49](D:/projects/Speech-Emotion-Recognition/ser_lib/data/__init__.py:49) | `ser_lib.data.errors.RegistryError` | 是（迁移） | `ser_lib.foundation.errors.RegistryError` |
| `ser_lib.data.DatasetManifest` | [ser_lib/data/__init__.py:49](D:/projects/Speech-Emotion-Recognition/ser_lib/data/__init__.py:49) | `ser_lib.data.manifest.DatasetManifest` | 是（领域规范入口） | `ser_lib.data.manifest.DatasetManifest` |
| `ser_lib.data.ManifestMeta` | [ser_lib/data/__init__.py:49](D:/projects/Speech-Emotion-Recognition/ser_lib/data/__init__.py:49) | `ser_lib.data.manifest.ManifestMeta` | 是（领域规范入口） | `ser_lib.data.manifest.ManifestMeta` |
| `ser_lib.data.read_jsonl` | [ser_lib/data/__init__.py:49](D:/projects/Speech-Emotion-Recognition/ser_lib/data/__init__.py:49) | `ser_lib.data.manifest.read_jsonl` | 是（领域规范入口） | `ser_lib.data.manifest.read_jsonl` |
| `ser_lib.data.write_jsonl` | [ser_lib/data/__init__.py:49](D:/projects/Speech-Emotion-Recognition/ser_lib/data/__init__.py:49) | `ser_lib.data.manifest.write_jsonl` | 是（领域规范入口） | `ser_lib.data.manifest.write_jsonl` |
| `ser_lib.data.DatasetEditor` | [ser_lib/data/__init__.py:49](D:/projects/Speech-Emotion-Recognition/ser_lib/data/__init__.py:49) | `ser_lib.data.editor.DatasetEditor` | 是（领域规范入口） | `ser_lib.data.editor.DatasetEditor` |
| `ser_lib.data.DATASET_REVISION_SCHEMA_VERSION` | [ser_lib/data/__init__.py:49](D:/projects/Speech-Emotion-Recognition/ser_lib/data/__init__.py:49) | `ser_lib.data.history.DATASET_REVISION_SCHEMA_VERSION` | 是（领域规范入口） | `ser_lib.data.history.DATASET_REVISION_SCHEMA_VERSION` |
| `ser_lib.data.DatasetRevisionInfo` | [ser_lib/data/__init__.py:49](D:/projects/Speech-Emotion-Recognition/ser_lib/data/__init__.py:49) | `ser_lib.data.history.DatasetRevisionInfo` | 是（领域规范入口） | `ser_lib.data.history.DatasetRevisionInfo` |
| `ser_lib.data.DatasetRevisionScanFailure` | [ser_lib/data/__init__.py:49](D:/projects/Speech-Emotion-Recognition/ser_lib/data/__init__.py:49) | `ser_lib.data.history.DatasetRevisionScanFailure` | 是（领域规范入口） | `ser_lib.data.history.DatasetRevisionScanFailure` |
| `ser_lib.data.DatasetRevisionCatalog` | [ser_lib/data/__init__.py:49](D:/projects/Speech-Emotion-Recognition/ser_lib/data/__init__.py:49) | `ser_lib.data.history.DatasetRevisionCatalog` | 是（领域规范入口） | `ser_lib.data.history.DatasetRevisionCatalog` |
| `ser_lib.data.create_dataset_revision` | [ser_lib/data/__init__.py:49](D:/projects/Speech-Emotion-Recognition/ser_lib/data/__init__.py:49) | `ser_lib.data.history.create_dataset_revision` | 是（领域规范入口） | `ser_lib.data.history.create_dataset_revision` |
| `ser_lib.data.inspect_dataset_revision` | [ser_lib/data/__init__.py:49](D:/projects/Speech-Emotion-Recognition/ser_lib/data/__init__.py:49) | `ser_lib.data.history.inspect_dataset_revision` | 是（领域规范入口） | `ser_lib.data.history.inspect_dataset_revision` |
| `ser_lib.data.scan_dataset_revisions` | [ser_lib/data/__init__.py:49](D:/projects/Speech-Emotion-Recognition/ser_lib/data/__init__.py:49) | `ser_lib.data.history.scan_dataset_revisions` | 是（领域规范入口） | `ser_lib.data.history.scan_dataset_revisions` |
| `ser_lib.data.restore_dataset_revision` | [ser_lib/data/__init__.py:49](D:/projects/Speech-Emotion-Recognition/ser_lib/data/__init__.py:49) | `ser_lib.data.history.restore_dataset_revision` | 是（领域规范入口） | `ser_lib.data.history.restore_dataset_revision` |
| `ser_lib.data.AudioLoader` | [ser_lib/data/__init__.py:49](D:/projects/Speech-Emotion-Recognition/ser_lib/data/__init__.py:49) | `ser_lib.data.audio.AudioLoader` | 是（领域规范入口） | `ser_lib.data.audio.AudioLoader` |
| `ser_lib.data.AudioLoaderConfig` | [ser_lib/data/__init__.py:49](D:/projects/Speech-Emotion-Recognition/ser_lib/data/__init__.py:49) | `ser_lib.data.audio.AudioLoaderConfig` | 是（迁移/合并） | `ser_lib/config/data.py:AudioConfig` |
| `ser_lib.data.FolderImporter` | [ser_lib/data/__init__.py:49](D:/projects/Speech-Emotion-Recognition/ser_lib/data/__init__.py:49) | `ser_lib.data.importers.FolderImporter` | 是（领域规范入口） | `ser_lib.data.importers.folder.FolderImporter` |
| `ser_lib.data.CsvImporter` | [ser_lib/data/__init__.py:49](D:/projects/Speech-Emotion-Recognition/ser_lib/data/__init__.py:49) | `ser_lib.data.importers.CsvImporter` | 是（领域规范入口） | `ser_lib.data.importers.csv_importer.CsvImporter` |
| `ser_lib.data.JsonlImporter` | [ser_lib/data/__init__.py:49](D:/projects/Speech-Emotion-Recognition/ser_lib/data/__init__.py:49) | `ser_lib.data.importers.JsonlImporter` | 是（领域规范入口） | `ser_lib.data.importers.jsonl_importer.JsonlImporter` |
| `ser_lib.data.CasiaImporter` | [ser_lib/data/__init__.py:49](D:/projects/Speech-Emotion-Recognition/ser_lib/data/__init__.py:49) | `ser_lib.data.importers.CasiaImporter` | 是（领域规范入口） | `ser_lib.data.importers.casia.CasiaImporter` |
| `ser_lib.data.ImportPreview` | [ser_lib/data/__init__.py:49](D:/projects/Speech-Emotion-Recognition/ser_lib/data/__init__.py:49) | `ser_lib.data.importers.ImportPreview` | 是（领域规范入口） | `ser_lib.data.importers.base.ImportPreview` |
| `ser_lib.data.RavdessImporter` | [ser_lib/data/__init__.py:49](D:/projects/Speech-Emotion-Recognition/ser_lib/data/__init__.py:49) | `ser_lib.data.importers.RavdessImporter` | 是（领域规范入口） | `ser_lib.data.importers.ravdess.RavdessImporter` |
| `ser_lib.data.register_importers` | [ser_lib/data/__init__.py:49](D:/projects/Speech-Emotion-Recognition/ser_lib/data/__init__.py:49) | `ser_lib.data.importers.register_importers` | 是（领域规范入口） | `ser_lib.data.importers.register_importers` |
| `ser_lib.data.SamplePipeline` | [ser_lib/data/__init__.py:49](D:/projects/Speech-Emotion-Recognition/ser_lib/data/__init__.py:49) | `ser_lib.data.pipeline.SamplePipeline` | 是（领域规范入口） | `ser_lib.data.pipeline.SamplePipeline` |
| `ser_lib.data.SERDataset` | [ser_lib/data/__init__.py:49](D:/projects/Speech-Emotion-Recognition/ser_lib/data/__init__.py:49) | `ser_lib.data.dataset.SERDataset` | 是（领域规范入口） | `ser_lib.data.dataset.SERDataset` |
| `ser_lib.data.build_pipeline` | [ser_lib/data/__init__.py:49](D:/projects/Speech-Emotion-Recognition/ser_lib/data/__init__.py:49) | `ser_lib.data.pipeline.build_pipeline` | 是（领域规范入口） | `ser_lib.data.pipeline.build_pipeline` |
| `ser_lib.data.build_components` | [ser_lib/data/__init__.py:49](D:/projects/Speech-Emotion-Recognition/ser_lib/data/__init__.py:49) | `ser_lib.data.pipeline.build_components` | 是（领域规范入口） | `ser_lib.data.pipeline.build_components` |
| `ser_lib.data.SERCollator` | [ser_lib/data/__init__.py:49](D:/projects/Speech-Emotion-Recognition/ser_lib/data/__init__.py:49) | `ser_lib.data.collate.SERCollator` | 是（领域规范入口） | `ser_lib.data.collate.SERCollator` |
| `ser_lib.data.CollateStrategy` | [ser_lib/data/__init__.py:49](D:/projects/Speech-Emotion-Recognition/ser_lib/data/__init__.py:49) | `ser_lib.data.collate.CollateStrategy` | 是（领域规范入口） | `ser_lib.data.collate.CollateStrategy` |
| `ser_lib.data.build_collator` | [ser_lib/data/__init__.py:49](D:/projects/Speech-Emotion-Recognition/ser_lib/data/__init__.py:49) | `ser_lib.data.collate.build_collator` | 是（领域规范入口） | `ser_lib.data.collate.build_collator` |
| `ser_lib.data.CachedRepresentation` | [ser_lib/data/__init__.py:49](D:/projects/Speech-Emotion-Recognition/ser_lib/data/__init__.py:49) | `ser_lib.data.cache.CachedRepresentation` | 是（领域规范入口） | `ser_lib.data.cache.CachedRepresentation` |
| `ser_lib.data.Registry` | [ser_lib/data/__init__.py:49](D:/projects/Speech-Emotion-Recognition/ser_lib/data/__init__.py:49) | `ser_lib.data.registry.Registry` | 是（领域规范入口） | `ser_lib.data.registry.Registry` |
| `ser_lib.data.default_registry` | [ser_lib/data/__init__.py:49](D:/projects/Speech-Emotion-Recognition/ser_lib/data/__init__.py:49) | `ser_lib.data.registry.default_registry` | 是（领域规范入口） | `ser_lib.data.registry.default_registry` |
| `ser_lib.data.ComponentDescriptor` | [ser_lib/data/__init__.py:49](D:/projects/Speech-Emotion-Recognition/ser_lib/data/__init__.py:49) | `ser_lib.data.registry.ComponentDescriptor` | 是（领域规范入口） | `ser_lib.data.registry.ComponentDescriptor` |
| `ser_lib.data.register_representations` | [ser_lib/data/__init__.py:49](D:/projects/Speech-Emotion-Recognition/ser_lib/data/__init__.py:49) | `ser_lib.data.representations.register_representations` | 是（领域规范入口） | `ser_lib.data.representations.register_representations` |
| `ser_lib.data.register_transforms` | [ser_lib/data/__init__.py:49](D:/projects/Speech-Emotion-Recognition/ser_lib/data/__init__.py:49) | `ser_lib.data.transforms.register_transforms` | 是（领域规范入口） | `ser_lib.data.transforms.register_transforms` |
| `ser_lib.data.DataConfig` | [ser_lib/data/__init__.py:49](D:/projects/Speech-Emotion-Recognition/ser_lib/data/__init__.py:49) | `ser_lib.data.config.DataConfig` | 是（迁移/合并） | `ser_lib/config/data.py:DataConfig` |
| `ser_lib.data.ComponentConfig` | [ser_lib/data/__init__.py:49](D:/projects/Speech-Emotion-Recognition/ser_lib/data/__init__.py:49) | `ser_lib.data.config.ComponentConfig` | 是（迁移/合并） | `ser_lib/config/data.py:ComponentConfig` |
| `ser_lib.data.AudioSettings` | [ser_lib/data/__init__.py:49](D:/projects/Speech-Emotion-Recognition/ser_lib/data/__init__.py:49) | `ser_lib.data.config.AudioSettings` | 是（迁移/合并） | `ser_lib/config/data.py:AudioConfig` |
| `ser_lib.data.CacheSettings` | [ser_lib/data/__init__.py:49](D:/projects/Speech-Emotion-Recognition/ser_lib/data/__init__.py:49) | `ser_lib.data.config.CacheSettings` | 是（迁移/合并） | `ser_lib/config/data.py:CacheConfig` |
| `ser_lib.data.BatchingConfig` | [ser_lib/data/__init__.py:49](D:/projects/Speech-Emotion-Recognition/ser_lib/data/__init__.py:49) | `ser_lib.data.config.BatchingConfig` | 是（迁移/合并） | `ser_lib/config/data.py:BatchingConfig` |
| `ser_lib.data.load_data_config` | [ser_lib/data/__init__.py:49](D:/projects/Speech-Emotion-Recognition/ser_lib/data/__init__.py:49) | `ser_lib.data.config.load_data_config` | 是（迁移） | `ser_lib.config.load_data_config` |
| `ser_lib.data.ModelSpec` | [ser_lib/data/__init__.py:49](D:/projects/Speech-Emotion-Recognition/ser_lib/data/__init__.py:49) | `ser_lib.data.validation.ModelSpec` | 是（迁移） | `ser_lib.models.ModelSpec` |
| `ser_lib.data.CompatibilityReport` | [ser_lib/data/__init__.py:49](D:/projects/Speech-Emotion-Recognition/ser_lib/data/__init__.py:49) | `ser_lib.data.validation.CompatibilityReport` | 是（迁移） | `ser_lib.engine.compatibility.CompatibilityReport` |
| `ser_lib.data.inspect_compatibility` | [ser_lib/data/__init__.py:49](D:/projects/Speech-Emotion-Recognition/ser_lib/data/__init__.py:49) | `ser_lib.data.validation.inspect_compatibility` | 是（迁移） | `ser_lib.engine.compatibility.inspect_compatibility` |
| `ser_lib.data.validate_compatibility` | [ser_lib/data/__init__.py:49](D:/projects/Speech-Emotion-Recognition/ser_lib/data/__init__.py:49) | `ser_lib.data.validation.validate_compatibility` | 是（迁移） | `ser_lib.engine.compatibility.validate_compatibility` |
| `ser_lib.data.AudioProbeFailure` | [ser_lib/data/__init__.py:49](D:/projects/Speech-Emotion-Recognition/ser_lib/data/__init__.py:49) | `ser_lib.data.profiling.AudioProbeFailure` | 是（领域规范入口） | `ser_lib.data.profiling.AudioProbeFailure` |
| `ser_lib.data.DurationHistogramBin` | [ser_lib/data/__init__.py:49](D:/projects/Speech-Emotion-Recognition/ser_lib/data/__init__.py:49) | `ser_lib.data.profiling.DurationHistogramBin` | 是（领域规范入口） | `ser_lib.data.profiling.DurationHistogramBin` |
| `ser_lib.data.DatasetAudioProfile` | [ser_lib/data/__init__.py:49](D:/projects/Speech-Emotion-Recognition/ser_lib/data/__init__.py:49) | `ser_lib.data.profiling.DatasetAudioProfile` | 是（领域规范入口） | `ser_lib.data.profiling.DatasetAudioProfile` |
| `ser_lib.data.DatasetSummary` | [ser_lib/data/__init__.py:49](D:/projects/Speech-Emotion-Recognition/ser_lib/data/__init__.py:49) | `ser_lib.data.profiling.DatasetSummary` | 是（领域规范入口） | `ser_lib.data.profiling.DatasetSummary` |
| `ser_lib.data.DatasetProfile` | [ser_lib/data/__init__.py:49](D:/projects/Speech-Emotion-Recognition/ser_lib/data/__init__.py:49) | `ser_lib.data.profiling.DatasetProfile` | 是（领域规范入口） | `ser_lib.data.profiling.DatasetProfile` |
| `ser_lib.data.profile_manifest_audio` | [ser_lib/data/__init__.py:49](D:/projects/Speech-Emotion-Recognition/ser_lib/data/__init__.py:49) | `ser_lib.data.profiling.profile_manifest_audio` | 是（领域规范入口） | `ser_lib.data.profiling.profile_manifest_audio` |
| `ser_lib.data.summarize_manifest` | [ser_lib/data/__init__.py:49](D:/projects/Speech-Emotion-Recognition/ser_lib/data/__init__.py:49) | `ser_lib.data.profiling.summarize_manifest` | 是（领域规范入口） | `ser_lib.data.profiling.summarize_manifest` |
| `ser_lib.data.profile_dataset` | [ser_lib/data/__init__.py:49](D:/projects/Speech-Emotion-Recognition/ser_lib/data/__init__.py:49) | `ser_lib.data.profiling.profile_dataset` | 是（领域规范入口） | `ser_lib.data.profiling.profile_dataset` |
| `ser_lib.data.RecordView` | [ser_lib/data/__init__.py:49](D:/projects/Speech-Emotion-Recognition/ser_lib/data/__init__.py:49) | `ser_lib.data.query.RecordView` | 否 | `移除包装；见正文替代 API` |
| `ser_lib.data.RecordPage` | [ser_lib/data/__init__.py:49](D:/projects/Speech-Emotion-Recognition/ser_lib/data/__init__.py:49) | `ser_lib.data.query.RecordPage` | 否 | `移除包装；见正文替代 API` |
| `ser_lib.data.query_records` | [ser_lib/data/__init__.py:49](D:/projects/Speech-Emotion-Recognition/ser_lib/data/__init__.py:49) | `ser_lib.data.query.query_records` | 替换 | `ser_lib.data.iter_records` |
| `ser_lib.data.DatasetFingerprint` | [ser_lib/data/__init__.py:49](D:/projects/Speech-Emotion-Recognition/ser_lib/data/__init__.py:49) | `ser_lib.data.fingerprint.DatasetFingerprint` | 是（领域规范入口） | `ser_lib.data.fingerprint.DatasetFingerprint` |
| `ser_lib.data.fingerprint_manifest` | [ser_lib/data/__init__.py:49](D:/projects/Speech-Emotion-Recognition/ser_lib/data/__init__.py:49) | `ser_lib.data.fingerprint.fingerprint_manifest` | 是（领域规范入口） | `ser_lib.data.fingerprint.fingerprint_manifest` |
| `ser_lib.data.audio.AudioBackend` | [ser_lib/data/audio.py:360](D:/projects/Speech-Emotion-Recognition/ser_lib/data/audio.py:360) | `ser_lib.data.audio.AudioBackend` | 是（领域规范入口） | `ser_lib.data.audio.AudioBackend` |
| `ser_lib.data.audio.AudioFileInfo` | [ser_lib/data/audio.py:360](D:/projects/Speech-Emotion-Recognition/ser_lib/data/audio.py:360) | `ser_lib.data.audio.AudioFileInfo` | 是（领域规范入口） | `ser_lib.data.audio.AudioFileInfo` |
| `ser_lib.data.audio.AudioLoaderConfig` | [ser_lib/data/audio.py:360](D:/projects/Speech-Emotion-Recognition/ser_lib/data/audio.py:360) | `ser_lib.data.audio.AudioLoaderConfig` | 是（迁移/合并） | `ser_lib/config/data.py:AudioConfig` |
| `ser_lib.data.audio.AudioLoader` | [ser_lib/data/audio.py:360](D:/projects/Speech-Emotion-Recognition/ser_lib/data/audio.py:360) | `ser_lib.data.audio.AudioLoader` | 是（领域规范入口） | `ser_lib.data.audio.AudioLoader` |
| `ser_lib.data.audio.probe_audio` | [ser_lib/data/audio.py:360](D:/projects/Speech-Emotion-Recognition/ser_lib/data/audio.py:360) | `ser_lib.data.audio.probe_audio` | 是（领域规范入口） | `ser_lib.data.audio.probe_audio` |
| `ser_lib.data.audio.decode_audio` | [ser_lib/data/audio.py:360](D:/projects/Speech-Emotion-Recognition/ser_lib/data/audio.py:360) | `ser_lib.data.audio.decode_audio` | 是（领域规范入口） | `ser_lib.data.audio.decode_audio` |
| `ser_lib.data.editor.DatasetEditor` | [ser_lib/data/editor.py:447](D:/projects/Speech-Emotion-Recognition/ser_lib/data/editor.py:447) | `ser_lib.data.editor.DatasetEditor` | 是（领域规范入口） | `ser_lib.data.editor.DatasetEditor` |
| `ser_lib.data.fingerprint.DatasetFingerprint` | [ser_lib/data/fingerprint.py:96](D:/projects/Speech-Emotion-Recognition/ser_lib/data/fingerprint.py:96) | `ser_lib.data.fingerprint.DatasetFingerprint` | 是（领域规范入口） | `ser_lib.data.fingerprint.DatasetFingerprint` |
| `ser_lib.data.fingerprint.fingerprint_manifest` | [ser_lib/data/fingerprint.py:96](D:/projects/Speech-Emotion-Recognition/ser_lib/data/fingerprint.py:96) | `ser_lib.data.fingerprint.fingerprint_manifest` | 是（领域规范入口） | `ser_lib.data.fingerprint.fingerprint_manifest` |
| `ser_lib.data.history.DATASET_REVISION_SCHEMA_VERSION` | [ser_lib/data/history.py:632](D:/projects/Speech-Emotion-Recognition/ser_lib/data/history.py:632) | `ser_lib.data.history.DATASET_REVISION_SCHEMA_VERSION` | 是（领域规范入口） | `ser_lib.data.history.DATASET_REVISION_SCHEMA_VERSION` |
| `ser_lib.data.history.DatasetRevisionInfo` | [ser_lib/data/history.py:632](D:/projects/Speech-Emotion-Recognition/ser_lib/data/history.py:632) | `ser_lib.data.history.DatasetRevisionInfo` | 是（领域规范入口） | `ser_lib.data.history.DatasetRevisionInfo` |
| `ser_lib.data.history.DatasetRevisionScanFailure` | [ser_lib/data/history.py:632](D:/projects/Speech-Emotion-Recognition/ser_lib/data/history.py:632) | `ser_lib.data.history.DatasetRevisionScanFailure` | 是（领域规范入口） | `ser_lib.data.history.DatasetRevisionScanFailure` |
| `ser_lib.data.history.DatasetRevisionCatalog` | [ser_lib/data/history.py:632](D:/projects/Speech-Emotion-Recognition/ser_lib/data/history.py:632) | `ser_lib.data.history.DatasetRevisionCatalog` | 是（领域规范入口） | `ser_lib.data.history.DatasetRevisionCatalog` |
| `ser_lib.data.history.create_dataset_revision` | [ser_lib/data/history.py:632](D:/projects/Speech-Emotion-Recognition/ser_lib/data/history.py:632) | `ser_lib.data.history.create_dataset_revision` | 是（领域规范入口） | `ser_lib.data.history.create_dataset_revision` |
| `ser_lib.data.history.inspect_dataset_revision` | [ser_lib/data/history.py:632](D:/projects/Speech-Emotion-Recognition/ser_lib/data/history.py:632) | `ser_lib.data.history.inspect_dataset_revision` | 是（领域规范入口） | `ser_lib.data.history.inspect_dataset_revision` |
| `ser_lib.data.history.scan_dataset_revisions` | [ser_lib/data/history.py:632](D:/projects/Speech-Emotion-Recognition/ser_lib/data/history.py:632) | `ser_lib.data.history.scan_dataset_revisions` | 是（领域规范入口） | `ser_lib.data.history.scan_dataset_revisions` |
| `ser_lib.data.history.restore_dataset_revision` | [ser_lib/data/history.py:632](D:/projects/Speech-Emotion-Recognition/ser_lib/data/history.py:632) | `ser_lib.data.history.restore_dataset_revision` | 是（领域规范入口） | `ser_lib.data.history.restore_dataset_revision` |
| `ser_lib.data.importers.DatasetImporter` | [ser_lib/data/importers/__init__.py:17](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/__init__.py:17) | `ser_lib.data.importers.base.DatasetImporter` | 是（领域规范入口） | `ser_lib.data.importers.base.DatasetImporter` |
| `ser_lib.data.importers.ImportPreview` | [ser_lib/data/importers/__init__.py:17](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/__init__.py:17) | `ser_lib.data.importers.base.ImportPreview` | 是（领域规范入口） | `ser_lib.data.importers.base.ImportPreview` |
| `ser_lib.data.importers.CasiaImporter` | [ser_lib/data/importers/__init__.py:17](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/__init__.py:17) | `ser_lib.data.importers.casia.CasiaImporter` | 是（领域规范入口） | `ser_lib.data.importers.casia.CasiaImporter` |
| `ser_lib.data.importers.CasiaImportConfig` | [ser_lib/data/importers/__init__.py:17](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/__init__.py:17) | `ser_lib.data.importers.casia.CasiaImportConfig` | 是（迁移/合并） | `ser_lib/config/importers.py:CasiaImportConfig` |
| `ser_lib.data.importers.CsvImporter` | [ser_lib/data/importers/__init__.py:17](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/__init__.py:17) | `ser_lib.data.importers.csv_importer.CsvImporter` | 是（领域规范入口） | `ser_lib.data.importers.csv_importer.CsvImporter` |
| `ser_lib.data.importers.CsvImportConfig` | [ser_lib/data/importers/__init__.py:17](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/__init__.py:17) | `ser_lib.data.importers.csv_importer.CsvImportConfig` | 是（迁移/合并） | `ser_lib/config/importers.py:CsvImportConfig` |
| `ser_lib.data.importers.CsemotionsImporter` | [ser_lib/data/importers/__init__.py:17](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/__init__.py:17) | `ser_lib.data.importers.csemotions.CsemotionsImporter` | 是（领域规范入口） | `ser_lib.data.importers.csemotions.CsemotionsImporter` |
| `ser_lib.data.importers.CsemotionsImportConfig` | [ser_lib/data/importers/__init__.py:17](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/__init__.py:17) | `ser_lib.data.importers.csemotions.CsemotionsImportConfig` | 是（迁移/合并） | `ser_lib/config/importers.py:CsemotionsImportConfig` |
| `ser_lib.data.importers.CremaDImporter` | [ser_lib/data/importers/__init__.py:17](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/__init__.py:17) | `ser_lib.data.importers.crema_d.CremaDImporter` | 是（领域规范入口） | `ser_lib.data.importers.crema_d.CremaDImporter` |
| `ser_lib.data.importers.CremaDImportConfig` | [ser_lib/data/importers/__init__.py:17](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/__init__.py:17) | `ser_lib.data.importers.crema_d.CremaDImportConfig` | 是（迁移/合并） | `ser_lib/config/importers.py:CremaDImportConfig` |
| `ser_lib.data.importers.EsdImporter` | [ser_lib/data/importers/__init__.py:17](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/__init__.py:17) | `ser_lib.data.importers.esd.EsdImporter` | 是（领域规范入口） | `ser_lib.data.importers.esd.EsdImporter` |
| `ser_lib.data.importers.EsdImportConfig` | [ser_lib/data/importers/__init__.py:17](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/__init__.py:17) | `ser_lib.data.importers.esd.EsdImportConfig` | 是（迁移/合并） | `ser_lib/config/importers.py:EsdImportConfig` |
| `ser_lib.data.importers.EmotionTalkImporter` | [ser_lib/data/importers/__init__.py:17](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/__init__.py:17) | `ser_lib.data.importers.emotiontalk.EmotionTalkImporter` | 是（领域规范入口） | `ser_lib.data.importers.emotiontalk.EmotionTalkImporter` |
| `ser_lib.data.importers.EmotionTalkImportConfig` | [ser_lib/data/importers/__init__.py:17](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/__init__.py:17) | `ser_lib.data.importers.emotiontalk.EmotionTalkImportConfig` | 是（迁移/合并） | `ser_lib/config/importers.py:EmotionTalkImportConfig` |
| `ser_lib.data.importers.FolderImporter` | [ser_lib/data/importers/__init__.py:17](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/__init__.py:17) | `ser_lib.data.importers.folder.FolderImporter` | 是（领域规范入口） | `ser_lib.data.importers.folder.FolderImporter` |
| `ser_lib.data.importers.FolderImportConfig` | [ser_lib/data/importers/__init__.py:17](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/__init__.py:17) | `ser_lib.data.importers.folder.FolderImportConfig` | 是（迁移/合并） | `ser_lib/config/importers.py:FolderImportConfig` |
| `ser_lib.data.importers.JsonlImporter` | [ser_lib/data/importers/__init__.py:17](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/__init__.py:17) | `ser_lib.data.importers.jsonl_importer.JsonlImporter` | 是（领域规范入口） | `ser_lib.data.importers.jsonl_importer.JsonlImporter` |
| `ser_lib.data.importers.JsonlImportConfig` | [ser_lib/data/importers/__init__.py:17](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/__init__.py:17) | `ser_lib.data.importers.jsonl_importer.JsonlImportConfig` | 是（迁移/合并） | `ser_lib/config/importers.py:JsonlImportConfig` |
| `ser_lib.data.importers.RavdessImporter` | [ser_lib/data/importers/__init__.py:17](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/__init__.py:17) | `ser_lib.data.importers.ravdess.RavdessImporter` | 是（领域规范入口） | `ser_lib.data.importers.ravdess.RavdessImporter` |
| `ser_lib.data.importers.RavdessImportConfig` | [ser_lib/data/importers/__init__.py:17](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/__init__.py:17) | `ser_lib.data.importers.ravdess.RavdessImportConfig` | 是（迁移/合并） | `ser_lib/config/importers.py:RavdessImportConfig` |
| `ser_lib.data.importers.normalize_raw_record` | [ser_lib/data/importers/__init__.py:17](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/__init__.py:17) | `ser_lib.data.importers.jsonl_importer.normalize_raw_record` | 是（领域规范入口） | `ser_lib.data.importers.jsonl_importer.normalize_raw_record` |
| `ser_lib.data.importers.normalize_raw_records` | [ser_lib/data/importers/__init__.py:17](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/__init__.py:17) | `ser_lib.data.importers.jsonl_importer.normalize_raw_records` | 是（领域规范入口） | `ser_lib.data.importers.jsonl_importer.normalize_raw_records` |
| `ser_lib.data.importers.register_importers` | [ser_lib/data/importers/__init__.py:17](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/__init__.py:17) | `ser_lib.data.importers.register_importers` | 是（领域规范入口） | `ser_lib.data.importers.register_importers` |
| `ser_lib.data.importers._conversion.run_manifest_conversion` | [ser_lib/data/importers/_conversion.py:168](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/_conversion.py:168) | `ser_lib.data.importers._conversion.run_manifest_conversion` | 是（领域规范入口） | `ser_lib.data.importers._conversion.run_manifest_conversion` |
| `ser_lib.data.importers._conversion.run_single_manifest_conversion` | [ser_lib/data/importers/_conversion.py:168](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/_conversion.py:168) | `ser_lib.data.importers._conversion.run_single_manifest_conversion` | 是（领域规范入口） | `ser_lib.data.importers._conversion.run_single_manifest_conversion` |
| `ser_lib.data.importers._conversion.write_partitioned_manifest` | [ser_lib/data/importers/_conversion.py:168](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/_conversion.py:168) | `ser_lib.data.importers._conversion.write_partitioned_manifest` | 是（领域规范入口） | `ser_lib.data.importers._conversion.write_partitioned_manifest` |
| `ser_lib.data.importers.base.DatasetImporter` | [ser_lib/data/importers/base.py:223](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/base.py:223) | `ser_lib.data.importers.base.DatasetImporter` | 是（领域规范入口） | `ser_lib.data.importers.base.DatasetImporter` |
| `ser_lib.data.importers.base.ImportPreview` | [ser_lib/data/importers/base.py:223](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/base.py:223) | `ser_lib.data.importers.base.ImportPreview` | 是（领域规范入口） | `ser_lib.data.importers.base.ImportPreview` |
| `ser_lib.data.importers.base.ImportTask` | [ser_lib/data/importers/base.py:223](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/base.py:223) | `ser_lib.data.importers.base.ImportTask` | 是（领域规范入口） | `ser_lib.data.importers.base.ImportTask` |
| `ser_lib.data.importers.base.ImportOperation` | [ser_lib/data/importers/base.py:223](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/base.py:223) | `ser_lib.data.importers.base.ImportOperation` | 是（领域规范入口） | `ser_lib.data.importers.base.ImportOperation` |
| `ser_lib.data.importers.casia.CasiaImportConfig` | [ser_lib/data/importers/casia.py:168](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/casia.py:168) | `ser_lib.data.importers.casia.CasiaImportConfig` | 是（迁移/合并） | `ser_lib/config/importers.py:CasiaImportConfig` |
| `ser_lib.data.importers.casia.CasiaImporter` | [ser_lib/data/importers/casia.py:168](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/casia.py:168) | `ser_lib.data.importers.casia.CasiaImporter` | 是（领域规范入口） | `ser_lib.data.importers.casia.CasiaImporter` |
| `ser_lib.data.importers.casia.CASIA_EMOTION_MAPPING` | [ser_lib/data/importers/casia.py:168](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/casia.py:168) | `ser_lib.data.importers.casia.CASIA_EMOTION_MAPPING` | 是（领域规范入口） | `ser_lib.data.importers.casia.CASIA_EMOTION_MAPPING` |
| `ser_lib.data.importers.casia.CASIA_EMOTION_ZH` | [ser_lib/data/importers/casia.py:168](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/casia.py:168) | `ser_lib.data.importers.casia.CASIA_EMOTION_ZH` | 是（领域规范入口） | `ser_lib.data.importers.casia.CASIA_EMOTION_ZH` |
| `ser_lib.data.importers.crema_d.CREMA_D_EMOTIONS` | [ser_lib/data/importers/crema_d.py:292](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/crema_d.py:292) | `ser_lib.data.importers.crema_d.CREMA_D_EMOTIONS` | 是（领域规范入口） | `ser_lib.data.importers.crema_d.CREMA_D_EMOTIONS` |
| `ser_lib.data.importers.crema_d.CremaDImportConfig` | [ser_lib/data/importers/crema_d.py:292](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/crema_d.py:292) | `ser_lib.data.importers.crema_d.CremaDImportConfig` | 是（迁移/合并） | `ser_lib/config/importers.py:CremaDImportConfig` |
| `ser_lib.data.importers.crema_d.CremaDImporter` | [ser_lib/data/importers/crema_d.py:292](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/crema_d.py:292) | `ser_lib.data.importers.crema_d.CremaDImporter` | 是（领域规范入口） | `ser_lib.data.importers.crema_d.CremaDImporter` |
| `ser_lib.data.importers.csemotions.CSEMOTIONS_LABELS` | [ser_lib/data/importers/csemotions.py:292](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/csemotions.py:292) | `ser_lib.data.importers.csemotions.CSEMOTIONS_LABELS` | 是（领域规范入口） | `ser_lib.data.importers.csemotions.CSEMOTIONS_LABELS` |
| `ser_lib.data.importers.csemotions.CSEMOTIONS_ZH` | [ser_lib/data/importers/csemotions.py:292](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/csemotions.py:292) | `ser_lib.data.importers.csemotions.CSEMOTIONS_ZH` | 是（领域规范入口） | `ser_lib.data.importers.csemotions.CSEMOTIONS_ZH` |
| `ser_lib.data.importers.csemotions.CsemotionsImportConfig` | [ser_lib/data/importers/csemotions.py:292](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/csemotions.py:292) | `ser_lib.data.importers.csemotions.CsemotionsImportConfig` | 是（迁移/合并） | `ser_lib/config/importers.py:CsemotionsImportConfig` |
| `ser_lib.data.importers.csemotions.CsemotionsImporter` | [ser_lib/data/importers/csemotions.py:292](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/csemotions.py:292) | `ser_lib.data.importers.csemotions.CsemotionsImporter` | 是（领域规范入口） | `ser_lib.data.importers.csemotions.CsemotionsImporter` |
| `ser_lib.data.importers.csv_importer.CsvImportConfig` | [ser_lib/data/importers/csv_importer.py:243](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/csv_importer.py:243) | `ser_lib.data.importers.csv_importer.CsvImportConfig` | 是（迁移/合并） | `ser_lib/config/importers.py:CsvImportConfig` |
| `ser_lib.data.importers.csv_importer.CsvImporter` | [ser_lib/data/importers/csv_importer.py:243](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/csv_importer.py:243) | `ser_lib.data.importers.csv_importer.CsvImporter` | 是（领域规范入口） | `ser_lib.data.importers.csv_importer.CsvImporter` |
| `ser_lib.data.importers.emotiontalk.EMOTIONTALK_LABELS` | [ser_lib/data/importers/emotiontalk.py:286](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/emotiontalk.py:286) | `ser_lib.data.importers.emotiontalk.EMOTIONTALK_LABELS` | 是（领域规范入口） | `ser_lib.data.importers.emotiontalk.EMOTIONTALK_LABELS` |
| `ser_lib.data.importers.emotiontalk.EmotionTalkImportConfig` | [ser_lib/data/importers/emotiontalk.py:286](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/emotiontalk.py:286) | `ser_lib.data.importers.emotiontalk.EmotionTalkImportConfig` | 是（迁移/合并） | `ser_lib/config/importers.py:EmotionTalkImportConfig` |
| `ser_lib.data.importers.emotiontalk.EmotionTalkImporter` | [ser_lib/data/importers/emotiontalk.py:286](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/emotiontalk.py:286) | `ser_lib.data.importers.emotiontalk.EmotionTalkImporter` | 是（领域规范入口） | `ser_lib.data.importers.emotiontalk.EmotionTalkImporter` |
| `ser_lib.data.importers.esd.ESD_LABELS` | [ser_lib/data/importers/esd.py:262](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/esd.py:262) | `ser_lib.data.importers.esd.ESD_LABELS` | 是（领域规范入口） | `ser_lib.data.importers.esd.ESD_LABELS` |
| `ser_lib.data.importers.esd.ESD_ZH` | [ser_lib/data/importers/esd.py:262](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/esd.py:262) | `ser_lib.data.importers.esd.ESD_ZH` | 是（领域规范入口） | `ser_lib.data.importers.esd.ESD_ZH` |
| `ser_lib.data.importers.esd.EsdImportConfig` | [ser_lib/data/importers/esd.py:262](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/esd.py:262) | `ser_lib.data.importers.esd.EsdImportConfig` | 是（迁移/合并） | `ser_lib/config/importers.py:EsdImportConfig` |
| `ser_lib.data.importers.esd.EsdImporter` | [ser_lib/data/importers/esd.py:262](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/esd.py:262) | `ser_lib.data.importers.esd.EsdImporter` | 是（领域规范入口） | `ser_lib.data.importers.esd.EsdImporter` |
| `ser_lib.data.importers.folder.FolderImportConfig` | [ser_lib/data/importers/folder.py:225](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/folder.py:225) | `ser_lib.data.importers.folder.FolderImportConfig` | 是（迁移/合并） | `ser_lib/config/importers.py:FolderImportConfig` |
| `ser_lib.data.importers.folder.FolderImporter` | [ser_lib/data/importers/folder.py:225](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/folder.py:225) | `ser_lib.data.importers.folder.FolderImporter` | 是（领域规范入口） | `ser_lib.data.importers.folder.FolderImporter` |
| `ser_lib.data.importers.folder.DEFAULT_AUDIO_EXTENSIONS` | [ser_lib/data/importers/folder.py:225](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/folder.py:225) | `ser_lib.data.importers.folder.DEFAULT_AUDIO_EXTENSIONS` | 是（领域规范入口） | `ser_lib.data.importers.folder.DEFAULT_AUDIO_EXTENSIONS` |
| `ser_lib.data.importers.jsonl_importer.JsonlImportConfig` | [ser_lib/data/importers/jsonl_importer.py:207](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/jsonl_importer.py:207) | `ser_lib.data.importers.jsonl_importer.JsonlImportConfig` | 是（迁移/合并） | `ser_lib/config/importers.py:JsonlImportConfig` |
| `ser_lib.data.importers.jsonl_importer.JsonlImporter` | [ser_lib/data/importers/jsonl_importer.py:207](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/jsonl_importer.py:207) | `ser_lib.data.importers.jsonl_importer.JsonlImporter` | 是（领域规范入口） | `ser_lib.data.importers.jsonl_importer.JsonlImporter` |
| `ser_lib.data.importers.jsonl_importer.normalize_raw_record` | [ser_lib/data/importers/jsonl_importer.py:207](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/jsonl_importer.py:207) | `ser_lib.data.importers.jsonl_importer.normalize_raw_record` | 是（领域规范入口） | `ser_lib.data.importers.jsonl_importer.normalize_raw_record` |
| `ser_lib.data.importers.jsonl_importer.normalize_raw_records` | [ser_lib/data/importers/jsonl_importer.py:207](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/jsonl_importer.py:207) | `ser_lib.data.importers.jsonl_importer.normalize_raw_records` | 是（领域规范入口） | `ser_lib.data.importers.jsonl_importer.normalize_raw_records` |
| `ser_lib.data.importers.jsonl_importer.STANDARD_FIELDS` | [ser_lib/data/importers/jsonl_importer.py:207](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/jsonl_importer.py:207) | `ser_lib.data.importers.jsonl_importer.STANDARD_FIELDS` | 是（领域规范入口） | `ser_lib.data.importers.jsonl_importer.STANDARD_FIELDS` |
| `ser_lib.data.importers.ravdess.RavdessImporter` | [ser_lib/data/importers/ravdess.py:214](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/ravdess.py:214) | `ser_lib.data.importers.ravdess.RavdessImporter` | 是（领域规范入口） | `ser_lib.data.importers.ravdess.RavdessImporter` |
| `ser_lib.data.importers.ravdess.RavdessImportConfig` | [ser_lib/data/importers/ravdess.py:214](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/ravdess.py:214) | `ser_lib.data.importers.ravdess.RavdessImportConfig` | 是（迁移/合并） | `ser_lib/config/importers.py:RavdessImportConfig` |
| `ser_lib.data.importers.ravdess.RAVDESS_EMOTIONS` | [ser_lib/data/importers/ravdess.py:214](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/ravdess.py:214) | `ser_lib.data.importers.ravdess.RAVDESS_EMOTIONS` | 是（领域规范入口） | `ser_lib.data.importers.ravdess.RAVDESS_EMOTIONS` |
| `ser_lib.data.profiling.AudioProbeFailure` | [ser_lib/data/profiling.py:447](D:/projects/Speech-Emotion-Recognition/ser_lib/data/profiling.py:447) | `ser_lib.data.profiling.AudioProbeFailure` | 是（领域规范入口） | `ser_lib.data.profiling.AudioProbeFailure` |
| `ser_lib.data.profiling.DurationHistogramBin` | [ser_lib/data/profiling.py:447](D:/projects/Speech-Emotion-Recognition/ser_lib/data/profiling.py:447) | `ser_lib.data.profiling.DurationHistogramBin` | 是（领域规范入口） | `ser_lib.data.profiling.DurationHistogramBin` |
| `ser_lib.data.profiling.DatasetAudioProfile` | [ser_lib/data/profiling.py:447](D:/projects/Speech-Emotion-Recognition/ser_lib/data/profiling.py:447) | `ser_lib.data.profiling.DatasetAudioProfile` | 是（领域规范入口） | `ser_lib.data.profiling.DatasetAudioProfile` |
| `ser_lib.data.profiling.DatasetSummary` | [ser_lib/data/profiling.py:447](D:/projects/Speech-Emotion-Recognition/ser_lib/data/profiling.py:447) | `ser_lib.data.profiling.DatasetSummary` | 是（领域规范入口） | `ser_lib.data.profiling.DatasetSummary` |
| `ser_lib.data.profiling.DatasetProfile` | [ser_lib/data/profiling.py:447](D:/projects/Speech-Emotion-Recognition/ser_lib/data/profiling.py:447) | `ser_lib.data.profiling.DatasetProfile` | 是（领域规范入口） | `ser_lib.data.profiling.DatasetProfile` |
| `ser_lib.data.profiling.profile_manifest_audio` | [ser_lib/data/profiling.py:447](D:/projects/Speech-Emotion-Recognition/ser_lib/data/profiling.py:447) | `ser_lib.data.profiling.profile_manifest_audio` | 是（领域规范入口） | `ser_lib.data.profiling.profile_manifest_audio` |
| `ser_lib.data.profiling.summarize_manifest` | [ser_lib/data/profiling.py:447](D:/projects/Speech-Emotion-Recognition/ser_lib/data/profiling.py:447) | `ser_lib.data.profiling.summarize_manifest` | 是（领域规范入口） | `ser_lib.data.profiling.summarize_manifest` |
| `ser_lib.data.profiling.profile_dataset` | [ser_lib/data/profiling.py:447](D:/projects/Speech-Emotion-Recognition/ser_lib/data/profiling.py:447) | `ser_lib.data.profiling.profile_dataset` | 是（领域规范入口） | `ser_lib.data.profiling.profile_dataset` |
| `ser_lib.data.query.RecordPage` | [ser_lib/data/query.py:161](D:/projects/Speech-Emotion-Recognition/ser_lib/data/query.py:161) | `ser_lib.data.query.RecordPage` | 否 | `移除包装；见正文替代 API` |
| `ser_lib.data.query.RecordView` | [ser_lib/data/query.py:161](D:/projects/Speech-Emotion-Recognition/ser_lib/data/query.py:161) | `ser_lib.data.query.RecordView` | 否 | `移除包装；见正文替代 API` |
| `ser_lib.data.query.query_records` | [ser_lib/data/query.py:161](D:/projects/Speech-Emotion-Recognition/ser_lib/data/query.py:161) | `ser_lib.data.query.query_records` | 替换 | `ser_lib.data.iter_records` |
| `ser_lib.data.representations.Representation` | [ser_lib/data/representations/__init__.py:27](D:/projects/Speech-Emotion-Recognition/ser_lib/data/representations/__init__.py:27) | `ser_lib.data.representations.base.Representation` | 是（领域规范入口） | `ser_lib.data.representations.base.Representation` |
| `ser_lib.data.representations.RawWaveform` | [ser_lib/data/representations/__init__.py:27](D:/projects/Speech-Emotion-Recognition/ser_lib/data/representations/__init__.py:27) | `ser_lib.data.representations.waveform.RawWaveform` | 是（领域规范入口） | `ser_lib.data.representations.waveform.RawWaveform` |
| `ser_lib.data.representations.RawWaveformConfig` | [ser_lib/data/representations/__init__.py:27](D:/projects/Speech-Emotion-Recognition/ser_lib/data/representations/__init__.py:27) | `ser_lib.data.representations.waveform.RawWaveformConfig` | 是（迁移/合并） | `ser_lib/config/representations.py:RawWaveformConfig` |
| `ser_lib.data.representations.SpectrogramRepresentation` | [ser_lib/data/representations/__init__.py:27](D:/projects/Speech-Emotion-Recognition/ser_lib/data/representations/__init__.py:27) | `ser_lib.data.representations.spectral.SpectrogramRepresentation` | 是（领域规范入口） | `ser_lib.data.representations.spectral.SpectrogramRepresentation` |
| `ser_lib.data.representations.SpectrogramConfig` | [ser_lib/data/representations/__init__.py:27](D:/projects/Speech-Emotion-Recognition/ser_lib/data/representations/__init__.py:27) | `ser_lib.data.representations.spectral.SpectrogramConfig` | 是（迁移/合并） | `ser_lib/config/representations.py:SpectrogramConfig` |
| `ser_lib.data.representations.MelSpectrogramRepresentation` | [ser_lib/data/representations/__init__.py:27](D:/projects/Speech-Emotion-Recognition/ser_lib/data/representations/__init__.py:27) | `ser_lib.data.representations.spectral.MelSpectrogramRepresentation` | 是（领域规范入口） | `ser_lib.data.representations.spectral.MelSpectrogramRepresentation` |
| `ser_lib.data.representations.MelConfig` | [ser_lib/data/representations/__init__.py:27](D:/projects/Speech-Emotion-Recognition/ser_lib/data/representations/__init__.py:27) | `ser_lib.data.representations.spectral.MelConfig` | 是（迁移/合并） | `ser_lib/config/representations.py:MelConfig` |
| `ser_lib.data.representations.LogMelRepresentation` | [ser_lib/data/representations/__init__.py:27](D:/projects/Speech-Emotion-Recognition/ser_lib/data/representations/__init__.py:27) | `ser_lib.data.representations.spectral.LogMelRepresentation` | 是（领域规范入口） | `ser_lib.data.representations.spectral.LogMelRepresentation` |
| `ser_lib.data.representations.LogMelConfig` | [ser_lib/data/representations/__init__.py:27](D:/projects/Speech-Emotion-Recognition/ser_lib/data/representations/__init__.py:27) | `ser_lib.data.representations.spectral.LogMelConfig` | 是（迁移/合并） | `ser_lib/config/representations.py:LogMelConfig` |
| `ser_lib.data.representations.MFCCRepresentation` | [ser_lib/data/representations/__init__.py:27](D:/projects/Speech-Emotion-Recognition/ser_lib/data/representations/__init__.py:27) | `ser_lib.data.representations.spectral.MFCCRepresentation` | 是（领域规范入口） | `ser_lib.data.representations.spectral.MFCCRepresentation` |
| `ser_lib.data.representations.MFCCConfig` | [ser_lib/data/representations/__init__.py:27](D:/projects/Speech-Emotion-Recognition/ser_lib/data/representations/__init__.py:27) | `ser_lib.data.representations.spectral.MFCCConfig` | 是（迁移/合并） | `ser_lib/config/representations.py:MFCCConfig` |
| `ser_lib.data.representations.AcousticFeatures` | [ser_lib/data/representations/__init__.py:27](D:/projects/Speech-Emotion-Recognition/ser_lib/data/representations/__init__.py:27) | `ser_lib.data.representations.acoustic.AcousticFeatures` | 是（领域规范入口） | `ser_lib.data.representations.acoustic.AcousticFeatures` |
| `ser_lib.data.representations.AcousticFeaturesConfig` | [ser_lib/data/representations/__init__.py:27](D:/projects/Speech-Emotion-Recognition/ser_lib/data/representations/__init__.py:27) | `ser_lib.data.representations.acoustic.AcousticFeaturesConfig` | 是（迁移/合并） | `ser_lib/config/representations.py:AcousticFeaturesConfig` |
| `ser_lib.data.representations.CompositeRepresentation` | [ser_lib/data/representations/__init__.py:27](D:/projects/Speech-Emotion-Recognition/ser_lib/data/representations/__init__.py:27) | `ser_lib.data.representations.composite.CompositeRepresentation` | 是（领域规范入口） | `ser_lib.data.representations.composite.CompositeRepresentation` |
| `ser_lib.data.representations.CompositeConfig` | [ser_lib/data/representations/__init__.py:27](D:/projects/Speech-Emotion-Recognition/ser_lib/data/representations/__init__.py:27) | `ser_lib.data.representations.composite.CompositeConfig` | 是（迁移/合并） | `ser_lib/config/representations.py:CompositeConfig` |
| `ser_lib.data.representations.register_representations` | [ser_lib/data/representations/__init__.py:27](D:/projects/Speech-Emotion-Recognition/ser_lib/data/representations/__init__.py:27) | `ser_lib.data.representations.register_representations` | 是（领域规范入口） | `ser_lib.data.representations.register_representations` |
| `ser_lib.data.representations.spectral.SpectrogramConfig` | [ser_lib/data/representations/spectral.py:276](D:/projects/Speech-Emotion-Recognition/ser_lib/data/representations/spectral.py:276) | `ser_lib.data.representations.spectral.SpectrogramConfig` | 是（迁移/合并） | `ser_lib/config/representations.py:SpectrogramConfig` |
| `ser_lib.data.representations.spectral.MelConfig` | [ser_lib/data/representations/spectral.py:276](D:/projects/Speech-Emotion-Recognition/ser_lib/data/representations/spectral.py:276) | `ser_lib.data.representations.spectral.MelConfig` | 是（迁移/合并） | `ser_lib/config/representations.py:MelConfig` |
| `ser_lib.data.representations.spectral.LogMelConfig` | [ser_lib/data/representations/spectral.py:276](D:/projects/Speech-Emotion-Recognition/ser_lib/data/representations/spectral.py:276) | `ser_lib.data.representations.spectral.LogMelConfig` | 是（迁移/合并） | `ser_lib/config/representations.py:LogMelConfig` |
| `ser_lib.data.representations.spectral.MFCCConfig` | [ser_lib/data/representations/spectral.py:276](D:/projects/Speech-Emotion-Recognition/ser_lib/data/representations/spectral.py:276) | `ser_lib.data.representations.spectral.MFCCConfig` | 是（迁移/合并） | `ser_lib/config/representations.py:MFCCConfig` |
| `ser_lib.data.representations.spectral.SpectrogramRepresentation` | [ser_lib/data/representations/spectral.py:276](D:/projects/Speech-Emotion-Recognition/ser_lib/data/representations/spectral.py:276) | `ser_lib.data.representations.spectral.SpectrogramRepresentation` | 是（领域规范入口） | `ser_lib.data.representations.spectral.SpectrogramRepresentation` |
| `ser_lib.data.representations.spectral.MelSpectrogramRepresentation` | [ser_lib/data/representations/spectral.py:276](D:/projects/Speech-Emotion-Recognition/ser_lib/data/representations/spectral.py:276) | `ser_lib.data.representations.spectral.MelSpectrogramRepresentation` | 是（领域规范入口） | `ser_lib.data.representations.spectral.MelSpectrogramRepresentation` |
| `ser_lib.data.representations.spectral.LogMelRepresentation` | [ser_lib/data/representations/spectral.py:276](D:/projects/Speech-Emotion-Recognition/ser_lib/data/representations/spectral.py:276) | `ser_lib.data.representations.spectral.LogMelRepresentation` | 是（领域规范入口） | `ser_lib.data.representations.spectral.LogMelRepresentation` |
| `ser_lib.data.representations.spectral.MFCCRepresentation` | [ser_lib/data/representations/spectral.py:276](D:/projects/Speech-Emotion-Recognition/ser_lib/data/representations/spectral.py:276) | `ser_lib.data.representations.spectral.MFCCRepresentation` | 是（领域规范入口） | `ser_lib.data.representations.spectral.MFCCRepresentation` |
| `ser_lib.data.transforms.RandomApply` | [ser_lib/data/transforms/__init__.py:19](D:/projects/Speech-Emotion-Recognition/ser_lib/data/transforms/__init__.py:19) | `ser_lib.data.transforms.base.RandomApply` | 是（领域规范入口） | `ser_lib.data.transforms.base.RandomApply` |
| `ser_lib.data.transforms.WaveformTransformPipeline` | [ser_lib/data/transforms/__init__.py:19](D:/projects/Speech-Emotion-Recognition/ser_lib/data/transforms/__init__.py:19) | `ser_lib.data.transforms.base.WaveformTransformPipeline` | 是（领域规范入口） | `ser_lib.data.transforms.base.WaveformTransformPipeline` |
| `ser_lib.data.transforms.FeatureTransformPipeline` | [ser_lib/data/transforms/__init__.py:19](D:/projects/Speech-Emotion-Recognition/ser_lib/data/transforms/__init__.py:19) | `ser_lib.data.transforms.base.FeatureTransformPipeline` | 是（领域规范入口） | `ser_lib.data.transforms.base.FeatureTransformPipeline` |
| `ser_lib.data.transforms.validate_feature_transform_layouts` | [ser_lib/data/transforms/__init__.py:19](D:/projects/Speech-Emotion-Recognition/ser_lib/data/transforms/__init__.py:19) | `ser_lib.data.transforms.base.validate_feature_transform_layouts` | 是（领域规范入口） | `ser_lib.data.transforms.base.validate_feature_transform_layouts` |
| `ser_lib.data.transforms.SpecMasking` | [ser_lib/data/transforms/__init__.py:19](D:/projects/Speech-Emotion-Recognition/ser_lib/data/transforms/__init__.py:19) | `ser_lib.data.transforms.feature.SpecMasking` | 是（领域规范入口） | `ser_lib.data.transforms.feature.SpecMasking` |
| `ser_lib.data.transforms.SpecMaskingConfig` | [ser_lib/data/transforms/__init__.py:19](D:/projects/Speech-Emotion-Recognition/ser_lib/data/transforms/__init__.py:19) | `ser_lib.data.transforms.feature.SpecMaskingConfig` | 是（迁移/合并） | `ser_lib/config/transforms.py:SpecMaskingConfig` |
| `ser_lib.data.transforms.SPEC_MASKING_DESCRIPTOR` | [ser_lib/data/transforms/__init__.py:19](D:/projects/Speech-Emotion-Recognition/ser_lib/data/transforms/__init__.py:19) | `ser_lib.data.transforms.feature.SPEC_MASKING_DESCRIPTOR` | 是（领域规范入口） | `ser_lib.data.transforms.feature.SPEC_MASKING_DESCRIPTOR` |
| `ser_lib.data.transforms.register_transforms` | [ser_lib/data/transforms/__init__.py:19](D:/projects/Speech-Emotion-Recognition/ser_lib/data/transforms/__init__.py:19) | `ser_lib.data.transforms.register_transforms` | 是（领域规范入口） | `ser_lib.data.transforms.register_transforms` |
| `ser_lib.data.transforms.feature.SpecMasking` | [ser_lib/data/transforms/feature.py:50](D:/projects/Speech-Emotion-Recognition/ser_lib/data/transforms/feature.py:50) | `ser_lib.data.transforms.feature.SpecMasking` | 是（领域规范入口） | `ser_lib.data.transforms.feature.SpecMasking` |
| `ser_lib.data.transforms.feature.SpecMaskingConfig` | [ser_lib/data/transforms/feature.py:50](D:/projects/Speech-Emotion-Recognition/ser_lib/data/transforms/feature.py:50) | `ser_lib.data.transforms.feature.SpecMaskingConfig` | 是（迁移/合并） | `ser_lib/config/transforms.py:SpecMaskingConfig` |
| `ser_lib.data.transforms.feature.SPEC_MASKING_DESCRIPTOR` | [ser_lib/data/transforms/feature.py:50](D:/projects/Speech-Emotion-Recognition/ser_lib/data/transforms/feature.py:50) | `ser_lib.data.transforms.feature.SPEC_MASKING_DESCRIPTOR` | 是（领域规范入口） | `ser_lib.data.transforms.feature.SPEC_MASKING_DESCRIPTOR` |
| `ser_lib.data.transforms.waveform.Normalize` | [ser_lib/data/transforms/waveform.py:235](D:/projects/Speech-Emotion-Recognition/ser_lib/data/transforms/waveform.py:235) | `ser_lib.data.transforms.waveform.Normalize` | 是（领域规范入口） | `ser_lib.data.transforms.waveform.Normalize` |
| `ser_lib.data.transforms.waveform.NormalizeConfig` | [ser_lib/data/transforms/waveform.py:235](D:/projects/Speech-Emotion-Recognition/ser_lib/data/transforms/waveform.py:235) | `ser_lib.data.transforms.waveform.NormalizeConfig` | 是（迁移/合并） | `ser_lib/config/transforms.py:NormalizeConfig` |
| `ser_lib.data.transforms.waveform.AddGaussianNoise` | [ser_lib/data/transforms/waveform.py:235](D:/projects/Speech-Emotion-Recognition/ser_lib/data/transforms/waveform.py:235) | `ser_lib.data.transforms.waveform.AddGaussianNoise` | 是（领域规范入口） | `ser_lib.data.transforms.waveform.AddGaussianNoise` |
| `ser_lib.data.transforms.waveform.GaussianNoiseConfig` | [ser_lib/data/transforms/waveform.py:235](D:/projects/Speech-Emotion-Recognition/ser_lib/data/transforms/waveform.py:235) | `ser_lib.data.transforms.waveform.GaussianNoiseConfig` | 是（迁移/合并） | `ser_lib/config/transforms.py:GaussianNoiseConfig` |
| `ser_lib.data.transforms.waveform.TimeShift` | [ser_lib/data/transforms/waveform.py:235](D:/projects/Speech-Emotion-Recognition/ser_lib/data/transforms/waveform.py:235) | `ser_lib.data.transforms.waveform.TimeShift` | 是（领域规范入口） | `ser_lib.data.transforms.waveform.TimeShift` |
| `ser_lib.data.transforms.waveform.TimeShiftConfig` | [ser_lib/data/transforms/waveform.py:235](D:/projects/Speech-Emotion-Recognition/ser_lib/data/transforms/waveform.py:235) | `ser_lib.data.transforms.waveform.TimeShiftConfig` | 是（迁移/合并） | `ser_lib/config/transforms.py:TimeShiftConfig` |
| `ser_lib.data.transforms.waveform.VolumeScale` | [ser_lib/data/transforms/waveform.py:235](D:/projects/Speech-Emotion-Recognition/ser_lib/data/transforms/waveform.py:235) | `ser_lib.data.transforms.waveform.VolumeScale` | 是（领域规范入口） | `ser_lib.data.transforms.waveform.VolumeScale` |
| `ser_lib.data.transforms.waveform.VolumeScaleConfig` | [ser_lib/data/transforms/waveform.py:235](D:/projects/Speech-Emotion-Recognition/ser_lib/data/transforms/waveform.py:235) | `ser_lib.data.transforms.waveform.VolumeScaleConfig` | 是（迁移/合并） | `ser_lib/config/transforms.py:VolumeScaleConfig` |
| `ser_lib.data.transforms.waveform.PitchShift` | [ser_lib/data/transforms/waveform.py:235](D:/projects/Speech-Emotion-Recognition/ser_lib/data/transforms/waveform.py:235) | `ser_lib.data.transforms.waveform.PitchShift` | 是（领域规范入口） | `ser_lib.data.transforms.waveform.PitchShift` |
| `ser_lib.data.transforms.waveform.PitchShiftConfig` | [ser_lib/data/transforms/waveform.py:235](D:/projects/Speech-Emotion-Recognition/ser_lib/data/transforms/waveform.py:235) | `ser_lib.data.transforms.waveform.PitchShiftConfig` | 是（迁移/合并） | `ser_lib/config/transforms.py:PitchShiftConfig` |
| `ser_lib.data.transforms.waveform.TimeStretch` | [ser_lib/data/transforms/waveform.py:235](D:/projects/Speech-Emotion-Recognition/ser_lib/data/transforms/waveform.py:235) | `ser_lib.data.transforms.waveform.TimeStretch` | 是（领域规范入口） | `ser_lib.data.transforms.waveform.TimeStretch` |
| `ser_lib.data.transforms.waveform.TimeStretchConfig` | [ser_lib/data/transforms/waveform.py:235](D:/projects/Speech-Emotion-Recognition/ser_lib/data/transforms/waveform.py:235) | `ser_lib.data.transforms.waveform.TimeStretchConfig` | 是（迁移/合并） | `ser_lib/config/transforms.py:TimeStretchConfig` |
| `ser_lib.data.transforms.waveform.RandomApply` | [ser_lib/data/transforms/waveform.py:235](D:/projects/Speech-Emotion-Recognition/ser_lib/data/transforms/waveform.py:235) | `ser_lib.data.transforms.base.RandomApply` | 是（领域规范入口） | `ser_lib.data.transforms.base.RandomApply` |
| `ser_lib.data.transforms.waveform.WAVEFORM_TRANSFORM_SPECS` | [ser_lib/data/transforms/waveform.py:235](D:/projects/Speech-Emotion-Recognition/ser_lib/data/transforms/waveform.py:235) | `ser_lib.data.transforms.waveform.WAVEFORM_TRANSFORM_SPECS` | 是（领域规范入口） | `ser_lib.data.transforms.waveform.WAVEFORM_TRANSFORM_SPECS` |
| `ser_lib.data.validation.ModelSpec` | [ser_lib/data/validation.py:277](D:/projects/Speech-Emotion-Recognition/ser_lib/data/validation.py:277) | `ser_lib.data.validation.ModelSpec` | 是（迁移） | `ser_lib.models.ModelSpec` |
| `ser_lib.data.validation.CompatibilityReport` | [ser_lib/data/validation.py:277](D:/projects/Speech-Emotion-Recognition/ser_lib/data/validation.py:277) | `ser_lib.data.validation.CompatibilityReport` | 是（迁移） | `ser_lib.engine.compatibility.CompatibilityReport` |
| `ser_lib.data.validation.inspect_compatibility` | [ser_lib/data/validation.py:277](D:/projects/Speech-Emotion-Recognition/ser_lib/data/validation.py:277) | `ser_lib.data.validation.inspect_compatibility` | 是（迁移） | `ser_lib.engine.compatibility.inspect_compatibility` |
| `ser_lib.data.validation.validate_compatibility` | [ser_lib/data/validation.py:277](D:/projects/Speech-Emotion-Recognition/ser_lib/data/validation.py:277) | `ser_lib.data.validation.validate_compatibility` | 是（迁移） | `ser_lib.engine.compatibility.validate_compatibility` |
| `ser_lib.engine.ModelConfig` | [ser_lib/engine/__init__.py:99](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/__init__.py:99) | `ser_lib.engine.config.ModelConfig` | 是（迁移/合并） | `ser_lib/config/model.py:ModelConfig` |
| `ser_lib.engine.ObservabilityConfig` | [ser_lib/engine/__init__.py:99](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/__init__.py:99) | `ser_lib.engine.config.ObservabilityConfig` | 是（迁移/合并） | `ser_lib/config/training.py:ObservabilityConfig` |
| `ser_lib.engine.TrainerConfig` | [ser_lib/engine/__init__.py:99](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/__init__.py:99) | `ser_lib.engine.config.TrainerConfig` | 是（迁移/合并） | `ser_lib/config/training.py:TrainerConfig` |
| `ser_lib.engine.ExperimentConfig` | [ser_lib/engine/__init__.py:99](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/__init__.py:99) | `ser_lib.engine.config.ExperimentConfig` | 是（迁移/合并） | `ser_lib/config/experiment.py:ExperimentConfig` |
| `ser_lib.engine.ExperimentComponents` | [ser_lib/engine/__init__.py:99](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/__init__.py:99) | `ser_lib.engine.config.ExperimentComponents` | 是（迁移） | `ser_lib.engine.experiment.ExperimentComponents` |
| `ser_lib.engine.load_experiment_config` | [ser_lib/engine/__init__.py:99](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/__init__.py:99) | `ser_lib.engine.config.load_experiment_config` | 是（迁移） | `ser_lib.config.load_experiment_config` |
| `ser_lib.engine.build_experiment_components` | [ser_lib/engine/__init__.py:99](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/__init__.py:99) | `ser_lib.engine.config.build_experiment_components` | 是（迁移） | `ser_lib.engine.experiment.build_experiment_components` |
| `ser_lib.engine.EtaSnapshot` | [ser_lib/engine/__init__.py:99](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/__init__.py:99) | `ser_lib.engine.eta.EtaSnapshot` | 是（领域规范入口） | `ser_lib.engine.eta.EtaSnapshot` |
| `ser_lib.engine.EtaEstimator` | [ser_lib/engine/__init__.py:99](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/__init__.py:99) | `ser_lib.engine.eta.EtaEstimator` | 是（领域规范入口） | `ser_lib.engine.eta.EtaEstimator` |
| `ser_lib.engine.PresetStatus` | [ser_lib/engine/__init__.py:99](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/__init__.py:99) | `ser_lib.engine.presets.PresetStatus` | 是（迁移） | `ser_lib.config.presets.PresetStatus` |
| `ser_lib.engine.ExperimentPresetInfo` | [ser_lib/engine/__init__.py:99](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/__init__.py:99) | `ser_lib.engine.presets.ExperimentPresetInfo` | 是（迁移） | `ser_lib.config.presets.ExperimentPresetInfo` |
| `ser_lib.engine.ExperimentPresetCatalog` | [ser_lib/engine/__init__.py:99](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/__init__.py:99) | `ser_lib.engine.presets.ExperimentPresetCatalog` | 否 | `移除包装；见正文替代 API` |
| `ser_lib.engine.list_experiment_presets` | [ser_lib/engine/__init__.py:99](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/__init__.py:99) | `ser_lib.engine.presets.list_experiment_presets` | 是（迁移） | `ser_lib.config.presets.list_experiment_presets` |
| `ser_lib.engine.get_experiment_preset` | [ser_lib/engine/__init__.py:99](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/__init__.py:99) | `ser_lib.engine.presets.get_experiment_preset` | 是（迁移） | `ser_lib.config.presets.get_experiment_preset` |
| `ser_lib.engine.build_experiment_config` | [ser_lib/engine/__init__.py:99](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/__init__.py:99) | `ser_lib.engine.presets.build_experiment_config` | 是（迁移） | `ser_lib.config.presets.build_experiment_config` |
| `ser_lib.engine.ExperimentValidationResult` | [ser_lib/engine/__init__.py:99](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/__init__.py:99) | `ser_lib.engine.validation.ExperimentValidationResult` | 是（领域规范入口） | `ser_lib.engine.validation.ExperimentValidationResult` |
| `ser_lib.engine.validate_experiment` | [ser_lib/engine/__init__.py:99](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/__init__.py:99) | `ser_lib.engine.validation.validate_experiment` | 是（领域规范入口） | `ser_lib.engine.validation.validate_experiment` |
| `ser_lib.engine.TrainingRunMetadata` | [ser_lib/engine/__init__.py:99](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/__init__.py:99) | `ser_lib.engine.lineage.TrainingRunMetadata` | 是（领域规范入口） | `ser_lib.engine.lineage.TrainingRunMetadata` |
| `ser_lib.engine.build_training_run_metadata` | [ser_lib/engine/__init__.py:99](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/__init__.py:99) | `ser_lib.engine.lineage.build_training_run_metadata` | 是（领域规范入口） | `ser_lib.engine.lineage.build_training_run_metadata` |
| `ser_lib.engine.RUN_RECORD_SCHEMA_VERSION` | [ser_lib/engine/__init__.py:99](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/__init__.py:99) | `ser_lib.engine.runs.RUN_RECORD_SCHEMA_VERSION` | 是（领域规范入口） | `ser_lib.engine.runs.RUN_RECORD_SCHEMA_VERSION` |
| `ser_lib.engine.TrainingRunInfo` | [ser_lib/engine/__init__.py:99](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/__init__.py:99) | `ser_lib.engine.runs.TrainingRunInfo` | 是（领域规范入口） | `ser_lib.engine.runs.TrainingRunInfo` |
| `ser_lib.engine.TrainingRunDetail` | [ser_lib/engine/__init__.py:99](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/__init__.py:99) | `ser_lib.engine.runs.TrainingRunDetail` | 否 | `移除包装；见正文替代 API` |
| `ser_lib.engine.TrainingRunScanFailure` | [ser_lib/engine/__init__.py:99](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/__init__.py:99) | `ser_lib.engine.runs.TrainingRunScanFailure` | 是（领域规范入口） | `ser_lib.engine.runs.TrainingRunScanFailure` |
| `ser_lib.engine.TrainingRunCatalog` | [ser_lib/engine/__init__.py:99](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/__init__.py:99) | `ser_lib.engine.runs.TrainingRunCatalog` | 是（领域规范入口） | `ser_lib.engine.runs.TrainingRunCatalog` |
| `ser_lib.engine.write_training_run_info` | [ser_lib/engine/__init__.py:99](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/__init__.py:99) | `ser_lib.engine.runs.write_training_run_info` | 是（领域规范入口） | `ser_lib.engine.runs.write_training_run_info` |
| `ser_lib.engine.load_training_run_info` | [ser_lib/engine/__init__.py:99](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/__init__.py:99) | `ser_lib.engine.runs.load_training_run_info` | 是（领域规范入口） | `ser_lib.engine.runs.load_training_run_info` |
| `ser_lib.engine.scan_training_runs` | [ser_lib/engine/__init__.py:99](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/__init__.py:99) | `ser_lib.engine.runs.scan_training_runs` | 是（领域规范入口） | `ser_lib.engine.runs.scan_training_runs` |
| `ser_lib.engine.TrainingHistoryInfo` | [ser_lib/engine/__init__.py:99](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/__init__.py:99) | `ser_lib.engine.training_history.TrainingHistoryInfo` | 是（领域规范入口） | `ser_lib.engine.training_history.TrainingHistoryInfo` |
| `ser_lib.engine.load_training_history` | [ser_lib/engine/__init__.py:99](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/__init__.py:99) | `ser_lib.engine.training_history.load_training_history` | 是（领域规范入口） | `ser_lib.engine.training_history.load_training_history` |
| `ser_lib.engine.EVALUATION_RUN_SCHEMA_VERSION` | [ser_lib/engine/__init__.py:99](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/__init__.py:99) | `ser_lib.engine.evaluation_runs.EVALUATION_RUN_SCHEMA_VERSION` | 是（领域规范入口） | `ser_lib.engine.evaluation_runs.EVALUATION_RUN_SCHEMA_VERSION` |
| `ser_lib.engine.EvaluationRunMetadata` | [ser_lib/engine/__init__.py:99](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/__init__.py:99) | `ser_lib.engine.evaluation_runs.EvaluationRunMetadata` | 是（领域规范入口） | `ser_lib.engine.evaluation_runs.EvaluationRunMetadata` |
| `ser_lib.engine.EvaluationRunInfo` | [ser_lib/engine/__init__.py:99](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/__init__.py:99) | `ser_lib.engine.evaluation_runs.EvaluationRunInfo` | 是（领域规范入口） | `ser_lib.engine.evaluation_runs.EvaluationRunInfo` |
| `ser_lib.engine.EvaluationPredictionFileInfo` | [ser_lib/engine/__init__.py:99](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/__init__.py:99) | `ser_lib.engine.evaluation_detail.EvaluationPredictionFileInfo` | 是（合并） | `ser_lib.engine.evaluation_reports.EvaluationPredictionFileInfo` |
| `ser_lib.engine.EvaluationRunDetail` | [ser_lib/engine/__init__.py:99](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/__init__.py:99) | `ser_lib.engine.evaluation_detail.EvaluationRunDetail` | 否 | `移除包装；见正文替代 API` |
| `ser_lib.engine.inspect_evaluation_prediction_file` | [ser_lib/engine/__init__.py:99](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/__init__.py:99) | `ser_lib.engine.evaluation_detail.inspect_evaluation_prediction_file` | 是（合并） | `ser_lib.engine.evaluation_reports.inspect_evaluation_prediction_file` |
| `ser_lib.engine.build_evaluation_run_metadata` | [ser_lib/engine/__init__.py:99](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/__init__.py:99) | `ser_lib.engine.evaluation_runs.build_evaluation_run_metadata` | 是（领域规范入口） | `ser_lib.engine.evaluation_runs.build_evaluation_run_metadata` |
| `ser_lib.engine.write_evaluation_run_info` | [ser_lib/engine/__init__.py:99](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/__init__.py:99) | `ser_lib.engine.evaluation_runs.write_evaluation_run_info` | 是（领域规范入口） | `ser_lib.engine.evaluation_runs.write_evaluation_run_info` |
| `ser_lib.engine.load_evaluation_run_info` | [ser_lib/engine/__init__.py:99](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/__init__.py:99) | `ser_lib.engine.evaluation_runs.load_evaluation_run_info` | 是（领域规范入口） | `ser_lib.engine.evaluation_runs.load_evaluation_run_info` |
| `ser_lib.engine.EvaluationRunScanFailure` | [ser_lib/engine/__init__.py:99](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/__init__.py:99) | `ser_lib.engine.evaluation_catalog.EvaluationRunScanFailure` | 是（领域规范入口） | `ser_lib.engine.evaluation_catalog.EvaluationRunScanFailure` |
| `ser_lib.engine.EvaluationRunCatalog` | [ser_lib/engine/__init__.py:99](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/__init__.py:99) | `ser_lib.engine.evaluation_catalog.EvaluationRunCatalog` | 是（领域规范入口） | `ser_lib.engine.evaluation_catalog.EvaluationRunCatalog` |
| `ser_lib.engine.scan_evaluation_runs` | [ser_lib/engine/__init__.py:99](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/__init__.py:99) | `ser_lib.engine.evaluation_catalog.scan_evaluation_runs` | 是（领域规范入口） | `ser_lib.engine.evaluation_catalog.scan_evaluation_runs` |
| `ser_lib.engine.AdamWConfig` | [ser_lib/engine/__init__.py:99](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/__init__.py:99) | `ser_lib.engine.optim.AdamWConfig` | 是（迁移/合并） | `ser_lib/config/optimizer.py:AdamWConfig` |
| `ser_lib.engine.AdamConfig` | [ser_lib/engine/__init__.py:99](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/__init__.py:99) | `ser_lib.engine.optim.AdamConfig` | 是（迁移/合并） | `ser_lib/config/optimizer.py:AdamConfig` |
| `ser_lib.engine.SGDConfig` | [ser_lib/engine/__init__.py:99](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/__init__.py:99) | `ser_lib.engine.optim.SGDConfig` | 是（迁移/合并） | `ser_lib/config/optimizer.py:SGDConfig` |
| `ser_lib.engine.StepSchedulerConfig` | [ser_lib/engine/__init__.py:99](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/__init__.py:99) | `ser_lib.engine.optim.StepSchedulerConfig` | 是（迁移/合并） | `ser_lib/config/scheduler.py:StepSchedulerConfig` |
| `ser_lib.engine.CosineSchedulerConfig` | [ser_lib/engine/__init__.py:99](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/__init__.py:99) | `ser_lib.engine.optim.CosineSchedulerConfig` | 是（迁移/合并） | `ser_lib/config/scheduler.py:CosineSchedulerConfig` |
| `ser_lib.engine.parse_optimizer_config` | [ser_lib/engine/__init__.py:99](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/__init__.py:99) | `ser_lib.engine.optim.parse_optimizer_config` | 是（迁移） | `ser_lib.config.optimizer.parse_optimizer_config` |
| `ser_lib.engine.build_optimizer` | [ser_lib/engine/__init__.py:99](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/__init__.py:99) | `ser_lib.engine.optim.build_optimizer` | 是（领域规范入口） | `ser_lib.engine.optim.build_optimizer` |
| `ser_lib.engine.parse_scheduler_config` | [ser_lib/engine/__init__.py:99](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/__init__.py:99) | `ser_lib.engine.optim.parse_scheduler_config` | 是（迁移） | `ser_lib.config.scheduler.parse_scheduler_config` |
| `ser_lib.engine.build_scheduler` | [ser_lib/engine/__init__.py:99](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/__init__.py:99) | `ser_lib.engine.optim.build_scheduler` | 是（领域规范入口） | `ser_lib.engine.optim.build_scheduler` |
| `ser_lib.engine.LossConfig` | [ser_lib/engine/__init__.py:99](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/__init__.py:99) | `ser_lib.engine.objectives.LossConfig` | 是（迁移/合并） | `ser_lib/config/training.py:LossConfig` |
| `ser_lib.engine.SamplingConfig` | [ser_lib/engine/__init__.py:99](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/__init__.py:99) | `ser_lib.engine.objectives.SamplingConfig` | 是（迁移/合并） | `ser_lib/config/training.py:SamplingConfig` |
| `ser_lib.engine.ClassificationLoss` | [ser_lib/engine/__init__.py:99](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/__init__.py:99) | `ser_lib.engine.objectives.ClassificationLoss` | 是（领域规范入口） | `ser_lib.engine.objectives.ClassificationLoss` |
| `ser_lib.engine.build_weighted_sampler` | [ser_lib/engine/__init__.py:99](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/__init__.py:99) | `ser_lib.engine.objectives.build_weighted_sampler` | 是（领域规范入口） | `ser_lib.engine.objectives.build_weighted_sampler` |
| `ser_lib.engine.Trainer` | [ser_lib/engine/__init__.py:99](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/__init__.py:99) | `ser_lib.engine.trainer.Trainer` | 是 | `ser_lib.engine.Trainer；fit -> TrainingResult` |
| `ser_lib.engine.EpochResult` | [ser_lib/engine/__init__.py:99](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/__init__.py:99) | `ser_lib.engine.trainer.EpochResult` | 是（领域规范入口） | `ser_lib.engine._trainer_core.EpochResult` |
| `ser_lib.engine.TrainingResult` | [ser_lib/engine/__init__.py:99](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/__init__.py:99) | `ser_lib.engine.trainer.TrainingResult` | 是（领域规范入口） | `ser_lib.engine._trainer_core.TrainingResult` |
| `ser_lib.engine.TrainingStatus` | [ser_lib/engine/__init__.py:99](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/__init__.py:99) | `ser_lib.engine.trainer.TrainingStatus` | 是（领域规范入口） | `ser_lib.engine._trainer_core.TrainingStatus` |
| `ser_lib.engine.seed_everything` | [ser_lib/engine/__init__.py:99](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/__init__.py:99) | `ser_lib.engine.trainer.seed_everything` | 是（领域规范入口） | `ser_lib.engine._trainer_core.seed_everything` |
| `ser_lib.engine.ClassMetrics` | [ser_lib/engine/__init__.py:99](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/__init__.py:99) | `ser_lib.engine.evaluator.ClassMetrics` | 是（领域规范入口） | `ser_lib.engine.evaluator.ClassMetrics` |
| `ser_lib.engine.PredictionRecord` | [ser_lib/engine/__init__.py:99](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/__init__.py:99) | `ser_lib.engine.evaluator.PredictionRecord` | 是（领域规范入口） | `ser_lib.engine.evaluator.PredictionRecord` |
| `ser_lib.engine.PredictionSink` | [ser_lib/engine/__init__.py:99](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/__init__.py:99) | `ser_lib.engine.evaluator.PredictionSink` | 是（领域规范入口） | `ser_lib.engine.evaluator.PredictionSink` |
| `ser_lib.engine.JsonlPredictionSink` | [ser_lib/engine/__init__.py:99](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/__init__.py:99) | `ser_lib.engine.evaluator.JsonlPredictionSink` | 是（领域规范入口） | `ser_lib.engine.evaluator.JsonlPredictionSink` |
| `ser_lib.engine.EvaluationResult` | [ser_lib/engine/__init__.py:99](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/__init__.py:99) | `ser_lib.engine.evaluator.EvaluationResult` | 是（领域规范入口） | `ser_lib.engine.evaluator.EvaluationResult` |
| `ser_lib.engine.EvaluationReportInfo` | [ser_lib/engine/__init__.py:99](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/__init__.py:99) | `ser_lib.engine.evaluation_reports.EvaluationReportInfo` | 是（领域规范入口） | `ser_lib.engine.evaluation_reports.EvaluationReportInfo` |
| `ser_lib.engine.EvaluationPredictionPage` | [ser_lib/engine/__init__.py:99](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/__init__.py:99) | `ser_lib.engine.evaluation_reports.EvaluationPredictionPage` | 否 | `移除包装；见正文替代 API` |
| `ser_lib.engine.inspect_evaluation_report` | [ser_lib/engine/__init__.py:99](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/__init__.py:99) | `ser_lib.engine.evaluation_reports.inspect_evaluation_report` | 是（领域规范入口） | `ser_lib.engine.evaluation_reports.inspect_evaluation_report` |
| `ser_lib.engine.query_evaluation_predictions` | [ser_lib/engine/__init__.py:99](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/__init__.py:99) | `ser_lib.engine.evaluation_reports.query_evaluation_predictions` | 替换 | `ser_lib.engine.iter_evaluation_predictions` |
| `ser_lib.engine.evaluate` | [ser_lib/engine/__init__.py:99](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/__init__.py:99) | `ser_lib.engine.evaluator.evaluate` | 是（领域规范入口） | `ser_lib.engine.evaluator.evaluate` |
| `ser_lib.engine.write_evaluation_report` | [ser_lib/engine/__init__.py:99](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/__init__.py:99) | `ser_lib.engine.evaluator.write_evaluation_report` | 是（领域规范入口） | `ser_lib.engine.evaluator.write_evaluation_report` |
| `ser_lib.engine.CheckpointKind` | [ser_lib/engine/__init__.py:99](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/__init__.py:99) | `ser_lib.engine.checkpoint_catalog.CheckpointKind` | 是（领域规范入口） | `ser_lib.engine.checkpoint_catalog.CheckpointKind` |
| `ser_lib.engine.CheckpointInfo` | [ser_lib/engine/__init__.py:99](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/__init__.py:99) | `ser_lib.engine.checkpoint_catalog.CheckpointInfo` | 是（领域规范入口） | `ser_lib.engine.checkpoint_catalog.CheckpointInfo` |
| `ser_lib.engine.CheckpointScanFailure` | [ser_lib/engine/__init__.py:99](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/__init__.py:99) | `ser_lib.engine.checkpoint_catalog.CheckpointScanFailure` | 是（领域规范入口） | `ser_lib.engine.checkpoint_catalog.CheckpointScanFailure` |
| `ser_lib.engine.CheckpointCatalog` | [ser_lib/engine/__init__.py:99](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/__init__.py:99) | `ser_lib.engine.checkpoint_catalog.CheckpointCatalog` | 是（领域规范入口） | `ser_lib.engine.checkpoint_catalog.CheckpointCatalog` |
| `ser_lib.engine.inspect_checkpoint_file` | [ser_lib/engine/__init__.py:99](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/__init__.py:99) | `ser_lib.engine.checkpoint_catalog.inspect_checkpoint_file` | 是（领域规范入口） | `ser_lib.engine.checkpoint_catalog.inspect_checkpoint_file` |
| `ser_lib.engine.scan_checkpoints` | [ser_lib/engine/__init__.py:99](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/__init__.py:99) | `ser_lib.engine.checkpoint_catalog.scan_checkpoints` | 是（领域规范入口） | `ser_lib.engine.checkpoint_catalog.scan_checkpoints` |
| `ser_lib.engine.save_checkpoint` | [ser_lib/engine/__init__.py:99](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/__init__.py:99) | `ser_lib.engine.checkpoint.save_checkpoint` | 是（领域规范入口） | `ser_lib.engine.checkpoint.save_checkpoint` |
| `ser_lib.engine.load_checkpoint` | [ser_lib/engine/__init__.py:99](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/__init__.py:99) | `ser_lib.engine.checkpoint.load_checkpoint` | 是（领域规范入口） | `ser_lib.engine.checkpoint.load_checkpoint` |
| `ser_lib.engine._trainer_core.TrainerConfig` | [ser_lib/engine/_trainer_core.py:1011](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/_trainer_core.py:1011) | `ser_lib.engine.config.TrainerConfig` | 是（迁移/合并） | `ser_lib/config/training.py:TrainerConfig` |
| `ser_lib.engine._trainer_core.ObservabilityConfig` | [ser_lib/engine/_trainer_core.py:1011](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/_trainer_core.py:1011) | `ser_lib.engine.config.ObservabilityConfig` | 是（迁移/合并） | `ser_lib/config/training.py:ObservabilityConfig` |
| `ser_lib.engine._trainer_core.EpochResult` | [ser_lib/engine/_trainer_core.py:1011](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/_trainer_core.py:1011) | `ser_lib.engine._trainer_core.EpochResult` | 是（领域规范入口） | `ser_lib.engine._trainer_core.EpochResult` |
| `ser_lib.engine._trainer_core.TrainingResult` | [ser_lib/engine/_trainer_core.py:1011](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/_trainer_core.py:1011) | `ser_lib.engine._trainer_core.TrainingResult` | 是（领域规范入口） | `ser_lib.engine._trainer_core.TrainingResult` |
| `ser_lib.engine._trainer_core.TrainingStatus` | [ser_lib/engine/_trainer_core.py:1011](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/_trainer_core.py:1011) | `ser_lib.engine._trainer_core.TrainingStatus` | 是（领域规范入口） | `ser_lib.engine._trainer_core.TrainingStatus` |
| `ser_lib.engine._trainer_core.Trainer` | [ser_lib/engine/_trainer_core.py:1011](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/_trainer_core.py:1011) | `ser_lib.engine._trainer_core.Trainer` | 是 | `ser_lib.engine.Trainer；fit -> TrainingResult` |
| `ser_lib.engine._trainer_core.move_batch_to_device` | [ser_lib/engine/_trainer_core.py:1011](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/_trainer_core.py:1011) | `ser_lib.engine._trainer_core.move_batch_to_device` | 是（迁移） | `ser_lib.data.types.move_batch_to_device` |
| `ser_lib.engine._trainer_core.seed_everything` | [ser_lib/engine/_trainer_core.py:1011](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/_trainer_core.py:1011) | `ser_lib.engine._trainer_core.seed_everything` | 是（领域规范入口） | `ser_lib.engine._trainer_core.seed_everything` |
| `ser_lib.engine.checkpoint.CHECKPOINT_FORMAT_VERSION` | [ser_lib/engine/checkpoint.py:126](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/checkpoint.py:126) | `ser_lib.engine.checkpoint.CHECKPOINT_FORMAT_VERSION` | 是（领域规范入口） | `ser_lib.engine.checkpoint.CHECKPOINT_FORMAT_VERSION` |
| `ser_lib.engine.checkpoint.save_checkpoint` | [ser_lib/engine/checkpoint.py:126](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/checkpoint.py:126) | `ser_lib.engine.checkpoint.save_checkpoint` | 是（领域规范入口） | `ser_lib.engine.checkpoint.save_checkpoint` |
| `ser_lib.engine.checkpoint.load_checkpoint` | [ser_lib/engine/checkpoint.py:126](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/checkpoint.py:126) | `ser_lib.engine.checkpoint.load_checkpoint` | 是（领域规范入口） | `ser_lib.engine.checkpoint.load_checkpoint` |
| `ser_lib.engine.checkpoint_catalog.CheckpointKind` | [ser_lib/engine/checkpoint_catalog.py:151](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/checkpoint_catalog.py:151) | `ser_lib.engine.checkpoint_catalog.CheckpointKind` | 是（领域规范入口） | `ser_lib.engine.checkpoint_catalog.CheckpointKind` |
| `ser_lib.engine.checkpoint_catalog.CheckpointInfo` | [ser_lib/engine/checkpoint_catalog.py:151](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/checkpoint_catalog.py:151) | `ser_lib.engine.checkpoint_catalog.CheckpointInfo` | 是（领域规范入口） | `ser_lib.engine.checkpoint_catalog.CheckpointInfo` |
| `ser_lib.engine.checkpoint_catalog.CheckpointScanFailure` | [ser_lib/engine/checkpoint_catalog.py:151](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/checkpoint_catalog.py:151) | `ser_lib.engine.checkpoint_catalog.CheckpointScanFailure` | 是（领域规范入口） | `ser_lib.engine.checkpoint_catalog.CheckpointScanFailure` |
| `ser_lib.engine.checkpoint_catalog.CheckpointCatalog` | [ser_lib/engine/checkpoint_catalog.py:151](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/checkpoint_catalog.py:151) | `ser_lib.engine.checkpoint_catalog.CheckpointCatalog` | 是（领域规范入口） | `ser_lib.engine.checkpoint_catalog.CheckpointCatalog` |
| `ser_lib.engine.checkpoint_catalog.inspect_checkpoint_file` | [ser_lib/engine/checkpoint_catalog.py:151](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/checkpoint_catalog.py:151) | `ser_lib.engine.checkpoint_catalog.inspect_checkpoint_file` | 是（领域规范入口） | `ser_lib.engine.checkpoint_catalog.inspect_checkpoint_file` |
| `ser_lib.engine.checkpoint_catalog.scan_checkpoints` | [ser_lib/engine/checkpoint_catalog.py:151](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/checkpoint_catalog.py:151) | `ser_lib.engine.checkpoint_catalog.scan_checkpoints` | 是（领域规范入口） | `ser_lib.engine.checkpoint_catalog.scan_checkpoints` |
| `ser_lib.engine.config.ModelConfig` | [ser_lib/engine/config.py:157](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/config.py:157) | `ser_lib.engine.config.ModelConfig` | 是（迁移/合并） | `ser_lib/config/model.py:ModelConfig` |
| `ser_lib.engine.config.ObservabilityConfig` | [ser_lib/engine/config.py:157](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/config.py:157) | `ser_lib.engine.config.ObservabilityConfig` | 是（迁移/合并） | `ser_lib/config/training.py:ObservabilityConfig` |
| `ser_lib.engine.config.TrainerConfig` | [ser_lib/engine/config.py:157](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/config.py:157) | `ser_lib.engine.config.TrainerConfig` | 是（迁移/合并） | `ser_lib/config/training.py:TrainerConfig` |
| `ser_lib.engine.config.ExperimentConfig` | [ser_lib/engine/config.py:157](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/config.py:157) | `ser_lib.engine.config.ExperimentConfig` | 是（迁移/合并） | `ser_lib/config/experiment.py:ExperimentConfig` |
| `ser_lib.engine.config.ExperimentComponents` | [ser_lib/engine/config.py:157](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/config.py:157) | `ser_lib.engine.config.ExperimentComponents` | 是（迁移） | `ser_lib.engine.experiment.ExperimentComponents` |
| `ser_lib.engine.config.load_experiment_config` | [ser_lib/engine/config.py:157](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/config.py:157) | `ser_lib.engine.config.load_experiment_config` | 是（迁移） | `ser_lib.config.load_experiment_config` |
| `ser_lib.engine.config.build_experiment_components` | [ser_lib/engine/config.py:157](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/config.py:157) | `ser_lib.engine.config.build_experiment_components` | 是（迁移） | `ser_lib.engine.experiment.build_experiment_components` |
| `ser_lib.engine.eta.EtaSnapshot` | [ser_lib/engine/eta.py:145](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/eta.py:145) | `ser_lib.engine.eta.EtaSnapshot` | 是（领域规范入口） | `ser_lib.engine.eta.EtaSnapshot` |
| `ser_lib.engine.eta.EtaEstimator` | [ser_lib/engine/eta.py:145](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/eta.py:145) | `ser_lib.engine.eta.EtaEstimator` | 是（领域规范入口） | `ser_lib.engine.eta.EtaEstimator` |
| `ser_lib.engine.evaluation_catalog.EvaluationRunScanFailure` | [ser_lib/engine/evaluation_catalog.py:101](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/evaluation_catalog.py:101) | `ser_lib.engine.evaluation_catalog.EvaluationRunScanFailure` | 是（领域规范入口） | `ser_lib.engine.evaluation_catalog.EvaluationRunScanFailure` |
| `ser_lib.engine.evaluation_catalog.EvaluationRunCatalog` | [ser_lib/engine/evaluation_catalog.py:101](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/evaluation_catalog.py:101) | `ser_lib.engine.evaluation_catalog.EvaluationRunCatalog` | 是（领域规范入口） | `ser_lib.engine.evaluation_catalog.EvaluationRunCatalog` |
| `ser_lib.engine.evaluation_catalog.scan_evaluation_runs` | [ser_lib/engine/evaluation_catalog.py:101](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/evaluation_catalog.py:101) | `ser_lib.engine.evaluation_catalog.scan_evaluation_runs` | 是（领域规范入口） | `ser_lib.engine.evaluation_catalog.scan_evaluation_runs` |
| `ser_lib.engine.evaluation_detail.EvaluationPredictionFileInfo` | [ser_lib/engine/evaluation_detail.py:71](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/evaluation_detail.py:71) | `ser_lib.engine.evaluation_detail.EvaluationPredictionFileInfo` | 是（合并） | `ser_lib.engine.evaluation_reports.EvaluationPredictionFileInfo` |
| `ser_lib.engine.evaluation_detail.EvaluationRunDetail` | [ser_lib/engine/evaluation_detail.py:71](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/evaluation_detail.py:71) | `ser_lib.engine.evaluation_detail.EvaluationRunDetail` | 否 | `移除包装；见正文替代 API` |
| `ser_lib.engine.evaluation_detail.inspect_evaluation_prediction_file` | [ser_lib/engine/evaluation_detail.py:71](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/evaluation_detail.py:71) | `ser_lib.engine.evaluation_detail.inspect_evaluation_prediction_file` | 是（合并） | `ser_lib.engine.evaluation_reports.inspect_evaluation_prediction_file` |
| `ser_lib.engine.evaluation_reports.EvaluationReportInfo` | [ser_lib/engine/evaluation_reports.py:278](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/evaluation_reports.py:278) | `ser_lib.engine.evaluation_reports.EvaluationReportInfo` | 是（领域规范入口） | `ser_lib.engine.evaluation_reports.EvaluationReportInfo` |
| `ser_lib.engine.evaluation_reports.EvaluationPredictionPage` | [ser_lib/engine/evaluation_reports.py:278](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/evaluation_reports.py:278) | `ser_lib.engine.evaluation_reports.EvaluationPredictionPage` | 否 | `移除包装；见正文替代 API` |
| `ser_lib.engine.evaluation_reports.inspect_evaluation_report` | [ser_lib/engine/evaluation_reports.py:278](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/evaluation_reports.py:278) | `ser_lib.engine.evaluation_reports.inspect_evaluation_report` | 是（领域规范入口） | `ser_lib.engine.evaluation_reports.inspect_evaluation_report` |
| `ser_lib.engine.evaluation_reports.query_evaluation_predictions` | [ser_lib/engine/evaluation_reports.py:278](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/evaluation_reports.py:278) | `ser_lib.engine.evaluation_reports.query_evaluation_predictions` | 替换 | `ser_lib.engine.iter_evaluation_predictions` |
| `ser_lib.engine.evaluation_runs.EVALUATION_RUN_SCHEMA_VERSION` | [ser_lib/engine/evaluation_runs.py:308](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/evaluation_runs.py:308) | `ser_lib.engine.evaluation_runs.EVALUATION_RUN_SCHEMA_VERSION` | 是（领域规范入口） | `ser_lib.engine.evaluation_runs.EVALUATION_RUN_SCHEMA_VERSION` |
| `ser_lib.engine.evaluation_runs.EvaluationRunMetadata` | [ser_lib/engine/evaluation_runs.py:308](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/evaluation_runs.py:308) | `ser_lib.engine.evaluation_runs.EvaluationRunMetadata` | 是（领域规范入口） | `ser_lib.engine.evaluation_runs.EvaluationRunMetadata` |
| `ser_lib.engine.evaluation_runs.EvaluationRunInfo` | [ser_lib/engine/evaluation_runs.py:308](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/evaluation_runs.py:308) | `ser_lib.engine.evaluation_runs.EvaluationRunInfo` | 是（领域规范入口） | `ser_lib.engine.evaluation_runs.EvaluationRunInfo` |
| `ser_lib.engine.evaluation_runs.build_evaluation_run_metadata` | [ser_lib/engine/evaluation_runs.py:308](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/evaluation_runs.py:308) | `ser_lib.engine.evaluation_runs.build_evaluation_run_metadata` | 是（领域规范入口） | `ser_lib.engine.evaluation_runs.build_evaluation_run_metadata` |
| `ser_lib.engine.evaluation_runs.write_evaluation_run_info` | [ser_lib/engine/evaluation_runs.py:308](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/evaluation_runs.py:308) | `ser_lib.engine.evaluation_runs.write_evaluation_run_info` | 是（领域规范入口） | `ser_lib.engine.evaluation_runs.write_evaluation_run_info` |
| `ser_lib.engine.evaluation_runs.load_evaluation_run_info` | [ser_lib/engine/evaluation_runs.py:308](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/evaluation_runs.py:308) | `ser_lib.engine.evaluation_runs.load_evaluation_run_info` | 是（领域规范入口） | `ser_lib.engine.evaluation_runs.load_evaluation_run_info` |
| `ser_lib.engine.evaluator.ClassMetrics` | [ser_lib/engine/evaluator.py:514](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/evaluator.py:514) | `ser_lib.engine.evaluator.ClassMetrics` | 是（领域规范入口） | `ser_lib.engine.evaluator.ClassMetrics` |
| `ser_lib.engine.evaluator.PredictionRecord` | [ser_lib/engine/evaluator.py:514](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/evaluator.py:514) | `ser_lib.engine.evaluator.PredictionRecord` | 是（领域规范入口） | `ser_lib.engine.evaluator.PredictionRecord` |
| `ser_lib.engine.evaluator.PredictionSink` | [ser_lib/engine/evaluator.py:514](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/evaluator.py:514) | `ser_lib.engine.evaluator.PredictionSink` | 是（领域规范入口） | `ser_lib.engine.evaluator.PredictionSink` |
| `ser_lib.engine.evaluator.JsonlPredictionSink` | [ser_lib/engine/evaluator.py:514](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/evaluator.py:514) | `ser_lib.engine.evaluator.JsonlPredictionSink` | 是（领域规范入口） | `ser_lib.engine.evaluator.JsonlPredictionSink` |
| `ser_lib.engine.evaluator.EvaluationResult` | [ser_lib/engine/evaluator.py:514](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/evaluator.py:514) | `ser_lib.engine.evaluator.EvaluationResult` | 是（领域规范入口） | `ser_lib.engine.evaluator.EvaluationResult` |
| `ser_lib.engine.evaluator.evaluate` | [ser_lib/engine/evaluator.py:514](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/evaluator.py:514) | `ser_lib.engine.evaluator.evaluate` | 是（领域规范入口） | `ser_lib.engine.evaluator.evaluate` |
| `ser_lib.engine.evaluator.write_evaluation_report` | [ser_lib/engine/evaluator.py:514](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/evaluator.py:514) | `ser_lib.engine.evaluator.write_evaluation_report` | 是（领域规范入口） | `ser_lib.engine.evaluator.write_evaluation_report` |
| `ser_lib.engine.lineage.TrainingRunMetadata` | [ser_lib/engine/lineage.py:120](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/lineage.py:120) | `ser_lib.engine.lineage.TrainingRunMetadata` | 是（领域规范入口） | `ser_lib.engine.lineage.TrainingRunMetadata` |
| `ser_lib.engine.lineage.build_training_run_metadata` | [ser_lib/engine/lineage.py:120](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/lineage.py:120) | `ser_lib.engine.lineage.build_training_run_metadata` | 是（领域规范入口） | `ser_lib.engine.lineage.build_training_run_metadata` |
| `ser_lib.engine.objectives.LossConfig` | [ser_lib/engine/objectives.py:116](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/objectives.py:116) | `ser_lib.engine.objectives.LossConfig` | 是（迁移/合并） | `ser_lib/config/training.py:LossConfig` |
| `ser_lib.engine.objectives.SamplingConfig` | [ser_lib/engine/objectives.py:116](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/objectives.py:116) | `ser_lib.engine.objectives.SamplingConfig` | 是（迁移/合并） | `ser_lib/config/training.py:SamplingConfig` |
| `ser_lib.engine.objectives.ClassificationLoss` | [ser_lib/engine/objectives.py:116](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/objectives.py:116) | `ser_lib.engine.objectives.ClassificationLoss` | 是（领域规范入口） | `ser_lib.engine.objectives.ClassificationLoss` |
| `ser_lib.engine.objectives.build_weighted_sampler` | [ser_lib/engine/objectives.py:116](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/objectives.py:116) | `ser_lib.engine.objectives.build_weighted_sampler` | 是（领域规范入口） | `ser_lib.engine.objectives.build_weighted_sampler` |
| `ser_lib.engine.optim.AdamWConfig` | [ser_lib/engine/optim.py:129](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/optim.py:129) | `ser_lib.engine.optim.AdamWConfig` | 是（迁移/合并） | `ser_lib/config/optimizer.py:AdamWConfig` |
| `ser_lib.engine.optim.AdamConfig` | [ser_lib/engine/optim.py:129](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/optim.py:129) | `ser_lib.engine.optim.AdamConfig` | 是（迁移/合并） | `ser_lib/config/optimizer.py:AdamConfig` |
| `ser_lib.engine.optim.SGDConfig` | [ser_lib/engine/optim.py:129](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/optim.py:129) | `ser_lib.engine.optim.SGDConfig` | 是（迁移/合并） | `ser_lib/config/optimizer.py:SGDConfig` |
| `ser_lib.engine.optim.OptimizerConfig` | [ser_lib/engine/optim.py:129](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/optim.py:129) | `ser_lib.engine.optim.OptimizerConfig` | 是（迁移/合并） | `ser_lib/config/optimizer.py:OptimizerConfig` |
| `ser_lib.engine.optim.StepSchedulerConfig` | [ser_lib/engine/optim.py:129](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/optim.py:129) | `ser_lib.engine.optim.StepSchedulerConfig` | 是（迁移/合并） | `ser_lib/config/scheduler.py:StepSchedulerConfig` |
| `ser_lib.engine.optim.CosineSchedulerConfig` | [ser_lib/engine/optim.py:129](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/optim.py:129) | `ser_lib.engine.optim.CosineSchedulerConfig` | 是（迁移/合并） | `ser_lib/config/scheduler.py:CosineSchedulerConfig` |
| `ser_lib.engine.optim.SchedulerConfig` | [ser_lib/engine/optim.py:129](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/optim.py:129) | `ser_lib.engine.optim.SchedulerConfig` | 是（迁移/合并） | `ser_lib/config/scheduler.py:SchedulerConfig` |
| `ser_lib.engine.optim.parse_optimizer_config` | [ser_lib/engine/optim.py:129](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/optim.py:129) | `ser_lib.engine.optim.parse_optimizer_config` | 是（迁移） | `ser_lib.config.optimizer.parse_optimizer_config` |
| `ser_lib.engine.optim.build_optimizer` | [ser_lib/engine/optim.py:129](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/optim.py:129) | `ser_lib.engine.optim.build_optimizer` | 是（领域规范入口） | `ser_lib.engine.optim.build_optimizer` |
| `ser_lib.engine.optim.parse_scheduler_config` | [ser_lib/engine/optim.py:129](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/optim.py:129) | `ser_lib.engine.optim.parse_scheduler_config` | 是（迁移） | `ser_lib.config.scheduler.parse_scheduler_config` |
| `ser_lib.engine.optim.build_scheduler` | [ser_lib/engine/optim.py:129](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/optim.py:129) | `ser_lib.engine.optim.build_scheduler` | 是（领域规范入口） | `ser_lib.engine.optim.build_scheduler` |
| `ser_lib.engine.presets.PresetStatus` | [ser_lib/engine/presets.py:308](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/presets.py:308) | `ser_lib.engine.presets.PresetStatus` | 是（迁移） | `ser_lib.config.presets.PresetStatus` |
| `ser_lib.engine.presets.ExperimentPresetInfo` | [ser_lib/engine/presets.py:308](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/presets.py:308) | `ser_lib.engine.presets.ExperimentPresetInfo` | 是（迁移） | `ser_lib.config.presets.ExperimentPresetInfo` |
| `ser_lib.engine.presets.ExperimentPresetCatalog` | [ser_lib/engine/presets.py:308](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/presets.py:308) | `ser_lib.engine.presets.ExperimentPresetCatalog` | 否 | `移除包装；见正文替代 API` |
| `ser_lib.engine.presets.list_experiment_presets` | [ser_lib/engine/presets.py:308](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/presets.py:308) | `ser_lib.engine.presets.list_experiment_presets` | 是（迁移） | `ser_lib.config.presets.list_experiment_presets` |
| `ser_lib.engine.presets.get_experiment_preset` | [ser_lib/engine/presets.py:308](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/presets.py:308) | `ser_lib.engine.presets.get_experiment_preset` | 是（迁移） | `ser_lib.config.presets.get_experiment_preset` |
| `ser_lib.engine.presets.build_experiment_config` | [ser_lib/engine/presets.py:308](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/presets.py:308) | `ser_lib.engine.presets.build_experiment_config` | 是（迁移） | `ser_lib.config.presets.build_experiment_config` |
| `ser_lib.engine.runs.RUN_RECORD_SCHEMA_VERSION` | [ser_lib/engine/runs.py:302](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/runs.py:302) | `ser_lib.engine.runs.RUN_RECORD_SCHEMA_VERSION` | 是（领域规范入口） | `ser_lib.engine.runs.RUN_RECORD_SCHEMA_VERSION` |
| `ser_lib.engine.runs.TrainingRunInfo` | [ser_lib/engine/runs.py:302](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/runs.py:302) | `ser_lib.engine.runs.TrainingRunInfo` | 是（领域规范入口） | `ser_lib.engine.runs.TrainingRunInfo` |
| `ser_lib.engine.runs.TrainingRunDetail` | [ser_lib/engine/runs.py:302](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/runs.py:302) | `ser_lib.engine.runs.TrainingRunDetail` | 否 | `移除包装；见正文替代 API` |
| `ser_lib.engine.runs.TrainingRunScanFailure` | [ser_lib/engine/runs.py:302](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/runs.py:302) | `ser_lib.engine.runs.TrainingRunScanFailure` | 是（领域规范入口） | `ser_lib.engine.runs.TrainingRunScanFailure` |
| `ser_lib.engine.runs.TrainingRunCatalog` | [ser_lib/engine/runs.py:302](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/runs.py:302) | `ser_lib.engine.runs.TrainingRunCatalog` | 是（领域规范入口） | `ser_lib.engine.runs.TrainingRunCatalog` |
| `ser_lib.engine.runs.write_training_run_info` | [ser_lib/engine/runs.py:302](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/runs.py:302) | `ser_lib.engine.runs.write_training_run_info` | 是（领域规范入口） | `ser_lib.engine.runs.write_training_run_info` |
| `ser_lib.engine.runs.load_training_run_info` | [ser_lib/engine/runs.py:302](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/runs.py:302) | `ser_lib.engine.runs.load_training_run_info` | 是（领域规范入口） | `ser_lib.engine.runs.load_training_run_info` |
| `ser_lib.engine.runs.scan_training_runs` | [ser_lib/engine/runs.py:302](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/runs.py:302) | `ser_lib.engine.runs.scan_training_runs` | 是（领域规范入口） | `ser_lib.engine.runs.scan_training_runs` |
| `ser_lib.engine.trainer.TrainerConfig` | [ser_lib/engine/trainer.py:132](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/trainer.py:132) | `ser_lib.engine._trainer_core.TrainerConfig` | 是（迁移/合并） | `ser_lib/config/training.py:TrainerConfig` |
| `ser_lib.engine.trainer.ObservabilityConfig` | [ser_lib/engine/trainer.py:132](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/trainer.py:132) | `ser_lib.engine._trainer_core.ObservabilityConfig` | 是（迁移/合并） | `ser_lib/config/training.py:ObservabilityConfig` |
| `ser_lib.engine.trainer.EpochResult` | [ser_lib/engine/trainer.py:132](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/trainer.py:132) | `ser_lib.engine._trainer_core.EpochResult` | 是（领域规范入口） | `ser_lib.engine._trainer_core.EpochResult` |
| `ser_lib.engine.trainer.TrainingResult` | [ser_lib/engine/trainer.py:132](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/trainer.py:132) | `ser_lib.engine._trainer_core.TrainingResult` | 是（领域规范入口） | `ser_lib.engine._trainer_core.TrainingResult` |
| `ser_lib.engine.trainer.TrainingStatus` | [ser_lib/engine/trainer.py:132](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/trainer.py:132) | `ser_lib.engine._trainer_core.TrainingStatus` | 是（领域规范入口） | `ser_lib.engine._trainer_core.TrainingStatus` |
| `ser_lib.engine.trainer.Trainer` | [ser_lib/engine/trainer.py:132](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/trainer.py:132) | `ser_lib.engine.trainer.Trainer` | 是 | `ser_lib.engine.Trainer；fit -> TrainingResult` |
| `ser_lib.engine.trainer.move_batch_to_device` | [ser_lib/engine/trainer.py:132](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/trainer.py:132) | `ser_lib.engine._trainer_core.move_batch_to_device` | 是（迁移） | `ser_lib.data.types.move_batch_to_device` |
| `ser_lib.engine.trainer.seed_everything` | [ser_lib/engine/trainer.py:132](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/trainer.py:132) | `ser_lib.engine._trainer_core.seed_everything` | 是（领域规范入口） | `ser_lib.engine._trainer_core.seed_everything` |
| `ser_lib.engine.training_history.TrainingHistoryInfo` | [ser_lib/engine/training_history.py:96](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/training_history.py:96) | `ser_lib.engine.training_history.TrainingHistoryInfo` | 是（领域规范入口） | `ser_lib.engine.training_history.TrainingHistoryInfo` |
| `ser_lib.engine.training_history.load_training_history` | [ser_lib/engine/training_history.py:96](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/training_history.py:96) | `ser_lib.engine.training_history.load_training_history` | 是（领域规范入口） | `ser_lib.engine.training_history.load_training_history` |
| `ser_lib.engine.validation.ExperimentValidationResult` | [ser_lib/engine/validation.py:441](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/validation.py:441) | `ser_lib.engine.validation.ExperimentValidationResult` | 是（领域规范入口） | `ser_lib.engine.validation.ExperimentValidationResult` |
| `ser_lib.engine.validation.validate_experiment` | [ser_lib/engine/validation.py:441](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/validation.py:441) | `ser_lib.engine.validation.validate_experiment` | 是（领域规范入口） | `ser_lib.engine.validation.validate_experiment` |
| `ser_lib.inference.EmotionPredictor` | [ser_lib/inference/__init__.py:17](D:/projects/Speech-Emotion-Recognition/ser_lib/inference/__init__.py:17) | `ser_lib.inference.offline.EmotionPredictor` | 是（领域规范入口） | `ser_lib.inference.offline.EmotionPredictor` |
| `ser_lib.inference.PredictionResult` | [ser_lib/inference/__init__.py:17](D:/projects/Speech-Emotion-Recognition/ser_lib/inference/__init__.py:17) | `ser_lib.inference.offline.PredictionResult` | 是（领域规范入口） | `ser_lib.inference.offline.PredictionResult` |
| `ser_lib.inference.PredictionFailure` | [ser_lib/inference/__init__.py:17](D:/projects/Speech-Emotion-Recognition/ser_lib/inference/__init__.py:17) | `ser_lib.inference.batch.PredictionFailure` | 是（领域规范入口） | `ser_lib.inference.batch.PredictionFailure` |
| `ser_lib.inference.BatchPredictionSink` | [ser_lib/inference/__init__.py:17](D:/projects/Speech-Emotion-Recognition/ser_lib/inference/__init__.py:17) | `ser_lib.inference.batch.BatchPredictionSink` | 是（领域规范入口） | `ser_lib.inference.batch.BatchPredictionSink` |
| `ser_lib.inference.JsonlBatchPredictionSink` | [ser_lib/inference/__init__.py:17](D:/projects/Speech-Emotion-Recognition/ser_lib/inference/__init__.py:17) | `ser_lib.inference.batch.JsonlBatchPredictionSink` | 是（领域规范入口） | `ser_lib.inference.batch.JsonlBatchPredictionSink` |
| `ser_lib.inference.BatchPredictionResult` | [ser_lib/inference/__init__.py:17](D:/projects/Speech-Emotion-Recognition/ser_lib/inference/__init__.py:17) | `ser_lib.inference.batch.BatchPredictionResult` | 是（领域规范入口） | `ser_lib.inference.batch.BatchPredictionResult` |
| `ser_lib.inference.BatchEmotionPredictor` | [ser_lib/inference/__init__.py:17](D:/projects/Speech-Emotion-Recognition/ser_lib/inference/__init__.py:17) | `ser_lib.inference.batch.BatchEmotionPredictor` | 是（领域规范入口） | `ser_lib.inference.batch.BatchEmotionPredictor` |
| `ser_lib.inference.write_batch_predictions` | [ser_lib/inference/__init__.py:17](D:/projects/Speech-Emotion-Recognition/ser_lib/inference/__init__.py:17) | `ser_lib.inference.batch.write_batch_predictions` | 是（领域规范入口） | `ser_lib.inference.batch.write_batch_predictions` |
| `ser_lib.inference.StreamingConfig` | [ser_lib/inference/__init__.py:17](D:/projects/Speech-Emotion-Recognition/ser_lib/inference/__init__.py:17) | `ser_lib.inference.streaming.StreamingConfig` | 是（迁移/合并） | `ser_lib/config/inference.py:StreamingConfig` |
| `ser_lib.inference.StreamingPrediction` | [ser_lib/inference/__init__.py:17](D:/projects/Speech-Emotion-Recognition/ser_lib/inference/__init__.py:17) | `ser_lib.inference.streaming.StreamingPrediction` | 是（领域规范入口） | `ser_lib.inference.streaming.StreamingPrediction` |
| `ser_lib.inference.StreamingLatency` | [ser_lib/inference/__init__.py:17](D:/projects/Speech-Emotion-Recognition/ser_lib/inference/__init__.py:17) | `ser_lib.inference.streaming.StreamingLatency` | 是（领域规范入口） | `ser_lib.inference.streaming.StreamingLatency` |
| `ser_lib.inference.StreamingEmotionRecognizer` | [ser_lib/inference/__init__.py:17](D:/projects/Speech-Emotion-Recognition/ser_lib/inference/__init__.py:17) | `ser_lib.inference.streaming.StreamingEmotionRecognizer` | 是（领域规范入口） | `ser_lib.inference.streaming.StreamingEmotionRecognizer` |
| `ser_lib.inference.batch.PredictionFailure` | [ser_lib/inference/batch.py:413](D:/projects/Speech-Emotion-Recognition/ser_lib/inference/batch.py:413) | `ser_lib.inference.batch.PredictionFailure` | 是（领域规范入口） | `ser_lib.inference.batch.PredictionFailure` |
| `ser_lib.inference.batch.BatchPredictionSink` | [ser_lib/inference/batch.py:413](D:/projects/Speech-Emotion-Recognition/ser_lib/inference/batch.py:413) | `ser_lib.inference.batch.BatchPredictionSink` | 是（领域规范入口） | `ser_lib.inference.batch.BatchPredictionSink` |
| `ser_lib.inference.batch.JsonlBatchPredictionSink` | [ser_lib/inference/batch.py:413](D:/projects/Speech-Emotion-Recognition/ser_lib/inference/batch.py:413) | `ser_lib.inference.batch.JsonlBatchPredictionSink` | 是（领域规范入口） | `ser_lib.inference.batch.JsonlBatchPredictionSink` |
| `ser_lib.inference.batch.BatchPredictionResult` | [ser_lib/inference/batch.py:413](D:/projects/Speech-Emotion-Recognition/ser_lib/inference/batch.py:413) | `ser_lib.inference.batch.BatchPredictionResult` | 是（领域规范入口） | `ser_lib.inference.batch.BatchPredictionResult` |
| `ser_lib.inference.batch.BatchEmotionPredictor` | [ser_lib/inference/batch.py:413](D:/projects/Speech-Emotion-Recognition/ser_lib/inference/batch.py:413) | `ser_lib.inference.batch.BatchEmotionPredictor` | 是（领域规范入口） | `ser_lib.inference.batch.BatchEmotionPredictor` |
| `ser_lib.inference.batch.write_batch_predictions` | [ser_lib/inference/batch.py:413](D:/projects/Speech-Emotion-Recognition/ser_lib/inference/batch.py:413) | `ser_lib.inference.batch.write_batch_predictions` | 是（领域规范入口） | `ser_lib.inference.batch.write_batch_predictions` |
| `ser_lib.inference.offline.EmotionPredictor` | [ser_lib/inference/offline.py:112](D:/projects/Speech-Emotion-Recognition/ser_lib/inference/offline.py:112) | `ser_lib.inference.offline.EmotionPredictor` | 是（领域规范入口） | `ser_lib.inference.offline.EmotionPredictor` |
| `ser_lib.inference.offline.PredictionResult` | [ser_lib/inference/offline.py:112](D:/projects/Speech-Emotion-Recognition/ser_lib/inference/offline.py:112) | `ser_lib.inference.offline.PredictionResult` | 是（领域规范入口） | `ser_lib.inference.offline.PredictionResult` |
| `ser_lib.inference.streaming.StreamingConfig` | [ser_lib/inference/streaming.py:233](D:/projects/Speech-Emotion-Recognition/ser_lib/inference/streaming.py:233) | `ser_lib.inference.streaming.StreamingConfig` | 是（迁移/合并） | `ser_lib/config/inference.py:StreamingConfig` |
| `ser_lib.inference.streaming.StreamingPrediction` | [ser_lib/inference/streaming.py:233](D:/projects/Speech-Emotion-Recognition/ser_lib/inference/streaming.py:233) | `ser_lib.inference.streaming.StreamingPrediction` | 是（领域规范入口） | `ser_lib.inference.streaming.StreamingPrediction` |
| `ser_lib.inference.streaming.StreamingLatency` | [ser_lib/inference/streaming.py:233](D:/projects/Speech-Emotion-Recognition/ser_lib/inference/streaming.py:233) | `ser_lib.inference.streaming.StreamingLatency` | 是（领域规范入口） | `ser_lib.inference.streaming.StreamingLatency` |
| `ser_lib.inference.streaming.StreamingEmotionRecognizer` | [ser_lib/inference/streaming.py:233](D:/projects/Speech-Emotion-Recognition/ser_lib/inference/streaming.py:233) | `ser_lib.inference.streaming.StreamingEmotionRecognizer` | 是（领域规范入口） | `ser_lib.inference.streaming.StreamingEmotionRecognizer` |
| `ser_lib.models.SERModel` | [ser_lib/models/__init__.py:7](D:/projects/Speech-Emotion-Recognition/ser_lib/models/__init__.py:7) | `ser_lib.models.base.SERModel` | 是（领域规范入口） | `ser_lib.models.base.SERModel` |
| `ser_lib.models.ModelOutput` | [ser_lib/models/__init__.py:7](D:/projects/Speech-Emotion-Recognition/ser_lib/models/__init__.py:7) | `ser_lib.models.base.ModelOutput` | 是（领域规范入口） | `ser_lib.models.base.ModelOutput` |
| `ser_lib.models.CNNBaseline` | [ser_lib/models/__init__.py:7](D:/projects/Speech-Emotion-Recognition/ser_lib/models/__init__.py:7) | `ser_lib.models.cnn_models.CNNBaseline` | 是（领域规范入口） | `ser_lib.models.cnn_models.CNNBaseline` |
| `ser_lib.models.CNNBaselineConfig` | [ser_lib/models/__init__.py:7](D:/projects/Speech-Emotion-Recognition/ser_lib/models/__init__.py:7) | `ser_lib.models.cnn_models.CNNBaselineConfig` | 是（迁移/合并） | `ser_lib/config/model.py:CNNBaselineConfig` |
| `ser_lib.models.GRUBaseline` | [ser_lib/models/__init__.py:7](D:/projects/Speech-Emotion-Recognition/ser_lib/models/__init__.py:7) | `ser_lib.models.rnn_models.GRUBaseline` | 是（领域规范入口） | `ser_lib.models.rnn_models.GRUBaseline` |
| `ser_lib.models.GRUBaselineConfig` | [ser_lib/models/__init__.py:7](D:/projects/Speech-Emotion-Recognition/ser_lib/models/__init__.py:7) | `ser_lib.models.rnn_models.GRUBaselineConfig` | 是（迁移/合并） | `ser_lib/config/model.py:GRUBaselineConfig` |
| `ser_lib.models.TransformerBaseline` | [ser_lib/models/__init__.py:7](D:/projects/Speech-Emotion-Recognition/ser_lib/models/__init__.py:7) | `ser_lib.models.transformer_models.TransformerBaseline` | 是（领域规范入口） | `ser_lib.models.transformer_models.TransformerBaseline` |
| `ser_lib.models.TransformerBaselineConfig` | [ser_lib/models/__init__.py:7](D:/projects/Speech-Emotion-Recognition/ser_lib/models/__init__.py:7) | `ser_lib.models.transformer_models.TransformerBaselineConfig` | 是（迁移/合并） | `ser_lib/config/model.py:TransformerBaselineConfig` |
| `ser_lib.models.HFAudioClassifier` | [ser_lib/models/__init__.py:7](D:/projects/Speech-Emotion-Recognition/ser_lib/models/__init__.py:7) | `ser_lib.models.pretrained.HFAudioClassifier` | 是（领域规范入口） | `ser_lib.models.pretrained.HFAudioClassifier` |
| `ser_lib.models.HFAudioClassifierConfig` | [ser_lib/models/__init__.py:7](D:/projects/Speech-Emotion-Recognition/ser_lib/models/__init__.py:7) | `ser_lib.models.pretrained.HFAudioClassifierConfig` | 是（迁移/合并） | `ser_lib/config/model.py:HFAudioClassifierConfig` |
| `ser_lib.models.ModelDescriptor` | [ser_lib/models/__init__.py:7](D:/projects/Speech-Emotion-Recognition/ser_lib/models/__init__.py:7) | `ser_lib.models.registry.ModelDescriptor` | 是（领域规范入口） | `ser_lib.models.registry.ModelDescriptor` |
| `ser_lib.models.ModelRegistry` | [ser_lib/models/__init__.py:7](D:/projects/Speech-Emotion-Recognition/ser_lib/models/__init__.py:7) | `ser_lib.models.registry.ModelRegistry` | 是（领域规范入口） | `ser_lib.models.registry.ModelRegistry` |
| `ser_lib.models.model_registry` | [ser_lib/models/__init__.py:7](D:/projects/Speech-Emotion-Recognition/ser_lib/models/__init__.py:7) | `ser_lib.models.registry.model_registry` | 是（领域规范入口） | `ser_lib.models.registry.model_registry` |
| `ser_lib.models.cnn_models.CNNBaseline` | [ser_lib/models/cnn_models.py:125](D:/projects/Speech-Emotion-Recognition/ser_lib/models/cnn_models.py:125) | `ser_lib.models.cnn_models.CNNBaseline` | 是（领域规范入口） | `ser_lib.models.cnn_models.CNNBaseline` |
| `ser_lib.models.cnn_models.CNNBaselineConfig` | [ser_lib/models/cnn_models.py:125](D:/projects/Speech-Emotion-Recognition/ser_lib/models/cnn_models.py:125) | `ser_lib.models.cnn_models.CNNBaselineConfig` | 是（迁移/合并） | `ser_lib/config/model.py:CNNBaselineConfig` |
| `ser_lib.models.pretrained.HFAudioClassifier` | [ser_lib/models/pretrained.py:226](D:/projects/Speech-Emotion-Recognition/ser_lib/models/pretrained.py:226) | `ser_lib.models.pretrained.HFAudioClassifier` | 是（领域规范入口） | `ser_lib.models.pretrained.HFAudioClassifier` |
| `ser_lib.models.pretrained.HFAudioClassifierConfig` | [ser_lib/models/pretrained.py:226](D:/projects/Speech-Emotion-Recognition/ser_lib/models/pretrained.py:226) | `ser_lib.models.pretrained.HFAudioClassifierConfig` | 是（迁移/合并） | `ser_lib/config/model.py:HFAudioClassifierConfig` |
| `ser_lib.models.rnn_models.GRUBaseline` | [ser_lib/models/rnn_models.py:163](D:/projects/Speech-Emotion-Recognition/ser_lib/models/rnn_models.py:163) | `ser_lib.models.rnn_models.GRUBaseline` | 是（领域规范入口） | `ser_lib.models.rnn_models.GRUBaseline` |
| `ser_lib.models.rnn_models.GRUBaselineConfig` | [ser_lib/models/rnn_models.py:163](D:/projects/Speech-Emotion-Recognition/ser_lib/models/rnn_models.py:163) | `ser_lib.models.rnn_models.GRUBaselineConfig` | 是（迁移/合并） | `ser_lib/config/model.py:GRUBaselineConfig` |
| `ser_lib.models.transformer_models.TransformerBaseline` | [ser_lib/models/transformer_models.py:193](D:/projects/Speech-Emotion-Recognition/ser_lib/models/transformer_models.py:193) | `ser_lib.models.transformer_models.TransformerBaseline` | 是（领域规范入口） | `ser_lib.models.transformer_models.TransformerBaseline` |
| `ser_lib.models.transformer_models.TransformerBaselineConfig` | [ser_lib/models/transformer_models.py:193](D:/projects/Speech-Emotion-Recognition/ser_lib/models/transformer_models.py:193) | `ser_lib.models.transformer_models.TransformerBaselineConfig` | 是（迁移/合并） | `ser_lib/config/model.py:TransformerBaselineConfig` |
| `ser_lib.runtime.RuntimeDevice` | [ser_lib/runtime.py:231](D:/projects/Speech-Emotion-Recognition/ser_lib/runtime.py:231) | `ser_lib.runtime.RuntimeDevice` | 是（迁移） | `ser_lib/engine/runtime.py:RuntimeDevice` |
| `ser_lib.runtime.RuntimeCapabilities` | [ser_lib/runtime.py:231](D:/projects/Speech-Emotion-Recognition/ser_lib/runtime.py:231) | `ser_lib.runtime.RuntimeCapabilities` | 是（迁移） | `ser_lib/engine/runtime.py:RuntimeCapabilities` |
| `ser_lib.runtime.RuntimeMetrics` | [ser_lib/runtime.py:231](D:/projects/Speech-Emotion-Recognition/ser_lib/runtime.py:231) | `ser_lib.runtime.RuntimeMetrics` | 是（迁移） | `ser_lib/engine/runtime.py:RuntimeMetrics` |
| `ser_lib.runtime.get_runtime_capabilities` | [ser_lib/runtime.py:231](D:/projects/Speech-Emotion-Recognition/ser_lib/runtime.py:231) | `ser_lib.runtime.get_runtime_capabilities` | 是（迁移） | `ser_lib/engine/runtime.py:get_runtime_capabilities` |
| `ser_lib.runtime.get_runtime_metrics` | [ser_lib/runtime.py:231](D:/projects/Speech-Emotion-Recognition/ser_lib/runtime.py:231) | `ser_lib.runtime.get_runtime_metrics` | 是（迁移） | `ser_lib/engine/runtime.py:get_runtime_metrics` |
| `ser_lib.services.DatasetService` | [ser_lib/services/__init__.py:11](D:/projects/Speech-Emotion-Recognition/ser_lib/services/__init__.py:11) | `ser_lib.services.datasets.DatasetService` | 否 | `第7节对应领域 API` |
| `ser_lib.services.TrainingService` | [ser_lib/services/__init__.py:11](D:/projects/Speech-Emotion-Recognition/ser_lib/services/__init__.py:11) | `ser_lib.services.training.TrainingService` | 否 | `第7节对应领域 API` |
| `ser_lib.services.EvaluationService` | [ser_lib/services/__init__.py:11](D:/projects/Speech-Emotion-Recognition/ser_lib/services/__init__.py:11) | `ser_lib.services.evaluation.EvaluationService` | 否 | `第7节对应领域 API` |
| `ser_lib.services.InferenceService` | [ser_lib/services/__init__.py:11](D:/projects/Speech-Emotion-Recognition/ser_lib/services/__init__.py:11) | `ser_lib.services.inference.InferenceService` | 否 | `第7节对应领域 API` |
| `ser_lib.services.ArtifactService` | [ser_lib/services/__init__.py:11](D:/projects/Speech-Emotion-Recognition/ser_lib/services/__init__.py:11) | `ser_lib.services.artifacts.ArtifactService` | 否 | `第7节对应领域 API` |
| `ser_lib.services.CatalogService` | [ser_lib/services/__init__.py:11](D:/projects/Speech-Emotion-Recognition/ser_lib/services/__init__.py:11) | `ser_lib.services.catalog.CatalogService` | 否 | `第7节对应领域 API` |
| `ser_lib.services.RuntimeService` | [ser_lib/services/__init__.py:11](D:/projects/Speech-Emotion-Recognition/ser_lib/services/__init__.py:11) | `ser_lib.services.runtime.RuntimeService` | 否 | `第7节对应领域 API` |
| `ser_lib.services.artifacts.ArtifactService` | [ser_lib/services/artifacts.py:122](D:/projects/Speech-Emotion-Recognition/ser_lib/services/artifacts.py:122) | `ser_lib.services.artifacts.ArtifactService` | 否 | `第7节对应领域 API` |
| `ser_lib.services.catalog.CatalogService` | [ser_lib/services/catalog.py:61](D:/projects/Speech-Emotion-Recognition/ser_lib/services/catalog.py:61) | `ser_lib.services.catalog.CatalogService` | 否 | `第7节对应领域 API` |
| `ser_lib.services.datasets.DatasetService` | [ser_lib/services/datasets.py:198](D:/projects/Speech-Emotion-Recognition/ser_lib/services/datasets.py:198) | `ser_lib.services.datasets.DatasetService` | 否 | `第7节对应领域 API` |
| `ser_lib.services.evaluation.EvaluationService` | [ser_lib/services/evaluation.py:215](D:/projects/Speech-Emotion-Recognition/ser_lib/services/evaluation.py:215) | `ser_lib.services.evaluation.EvaluationService` | 否 | `第7节对应领域 API` |
| `ser_lib.services.inference.InferenceService` | [ser_lib/services/inference.py:180](D:/projects/Speech-Emotion-Recognition/ser_lib/services/inference.py:180) | `ser_lib.services.inference.InferenceService` | 否 | `第7节对应领域 API` |
| `ser_lib.services.inference.WindowAggregation` | [ser_lib/services/inference.py:180](D:/projects/Speech-Emotion-Recognition/ser_lib/services/inference.py:180) | `ser_lib.services.inference.WindowAggregation` | 是（领域规范入口） | `ser_lib.services.inference.WindowAggregation` |
| `ser_lib.services.runtime.RuntimeService` | [ser_lib/services/runtime.py:27](D:/projects/Speech-Emotion-Recognition/ser_lib/services/runtime.py:27) | `ser_lib.services.runtime.RuntimeService` | 否 | `第7节对应领域 API` |
| `ser_lib.services.training.TrainingService` | [ser_lib/services/training.py:231](D:/projects/Speech-Emotion-Recognition/ser_lib/services/training.py:231) | `ser_lib.services.training.TrainingService` | 否 | `第7节对应领域 API` |

## D. 完整静态 import 关系

“作用域”中的 local 表示函数调用时才发生 import；TYPE_CHECKING 不等于运行时边。下面先列库内依赖，再列库外消费者的 import。from 包 import 子模块时按子模块存在性解析，普通符号边保留其声明来源。

### D.1 库内 import

| 调用/导入方 | 来源模块 | 符号 | 本地名 | 作用域 |
| --- | --- | --- | --- | --- |
| [ser_lib/__init__.py:5](D:/projects/Speech-Emotion-Recognition/ser_lib/__init__.py:5) | `ser_lib.core` | `Diagnostic` | `Diagnostic` | top-level |
| [ser_lib/__init__.py:5](D:/projects/Speech-Emotion-Recognition/ser_lib/__init__.py:5) | `ser_lib.core` | `DiagnosticSeverity` | `DiagnosticSeverity` | top-level |
| [ser_lib/__init__.py:6](D:/projects/Speech-Emotion-Recognition/ser_lib/__init__.py:6) | `ser_lib.data` | `CompatibilityReport` | `CompatibilityReport` | top-level |
| [ser_lib/__init__.py:6](D:/projects/Speech-Emotion-Recognition/ser_lib/__init__.py:6) | `ser_lib.data` | `SERBatch` | `SERBatch` | top-level |
| [ser_lib/__init__.py:6](D:/projects/Speech-Emotion-Recognition/ser_lib/__init__.py:6) | `ser_lib.data` | `SERDataset` | `SERDataset` | top-level |
| [ser_lib/__init__.py:6](D:/projects/Speech-Emotion-Recognition/ser_lib/__init__.py:6) | `ser_lib.data` | `SERSample` | `SERSample` | top-level |
| [ser_lib/__init__.py:6](D:/projects/Speech-Emotion-Recognition/ser_lib/__init__.py:6) | `ser_lib.data` | `TensorSpec` | `TensorSpec` | top-level |
| [ser_lib/__init__.py:6](D:/projects/Speech-Emotion-Recognition/ser_lib/__init__.py:6) | `ser_lib.data` | `inspect_compatibility` | `inspect_compatibility` | top-level |
| [ser_lib/__init__.py:14](D:/projects/Speech-Emotion-Recognition/ser_lib/__init__.py:14) | `ser_lib.artifacts` | `ArtifactCatalog` | `ArtifactCatalog` | top-level |
| [ser_lib/__init__.py:14](D:/projects/Speech-Emotion-Recognition/ser_lib/__init__.py:14) | `ser_lib.artifacts` | `ArtifactInfo` | `ArtifactInfo` | top-level |
| [ser_lib/__init__.py:14](D:/projects/Speech-Emotion-Recognition/ser_lib/__init__.py:14) | `ser_lib.artifacts` | `ArtifactScanFailure` | `ArtifactScanFailure` | top-level |
| [ser_lib/__init__.py:14](D:/projects/Speech-Emotion-Recognition/ser_lib/__init__.py:14) | `ser_lib.artifacts` | `ModelArtifactManifest` | `ModelArtifactManifest` | top-level |
| [ser_lib/__init__.py:14](D:/projects/Speech-Emotion-Recognition/ser_lib/__init__.py:14) | `ser_lib.artifacts` | `ModelCard` | `ModelCard` | top-level |
| [ser_lib/__init__.py:14](D:/projects/Speech-Emotion-Recognition/ser_lib/__init__.py:14) | `ser_lib.artifacts` | `export_model_artifact` | `export_model_artifact` | top-level |
| [ser_lib/__init__.py:14](D:/projects/Speech-Emotion-Recognition/ser_lib/__init__.py:14) | `ser_lib.artifacts` | `inspect_model_artifact` | `inspect_model_artifact` | top-level |
| [ser_lib/__init__.py:14](D:/projects/Speech-Emotion-Recognition/ser_lib/__init__.py:14) | `ser_lib.artifacts` | `load_model_artifact` | `load_model_artifact` | top-level |
| [ser_lib/__init__.py:14](D:/projects/Speech-Emotion-Recognition/ser_lib/__init__.py:14) | `ser_lib.artifacts` | `scan_model_artifacts` | `scan_model_artifacts` | top-level |
| [ser_lib/__init__.py:14](D:/projects/Speech-Emotion-Recognition/ser_lib/__init__.py:14) | `ser_lib.artifacts` | `verify_model_artifact` | `verify_model_artifact` | top-level |
| [ser_lib/__init__.py:26](D:/projects/Speech-Emotion-Recognition/ser_lib/__init__.py:26) | `ser_lib.engine` | `EVALUATION_RUN_SCHEMA_VERSION` | `EVALUATION_RUN_SCHEMA_VERSION` | top-level |
| [ser_lib/__init__.py:26](D:/projects/Speech-Emotion-Recognition/ser_lib/__init__.py:26) | `ser_lib.engine` | `RUN_RECORD_SCHEMA_VERSION` | `RUN_RECORD_SCHEMA_VERSION` | top-level |
| [ser_lib/__init__.py:26](D:/projects/Speech-Emotion-Recognition/ser_lib/__init__.py:26) | `ser_lib.engine` | `CheckpointCatalog` | `CheckpointCatalog` | top-level |
| [ser_lib/__init__.py:26](D:/projects/Speech-Emotion-Recognition/ser_lib/__init__.py:26) | `ser_lib.engine` | `CheckpointInfo` | `CheckpointInfo` | top-level |
| [ser_lib/__init__.py:26](D:/projects/Speech-Emotion-Recognition/ser_lib/__init__.py:26) | `ser_lib.engine` | `CheckpointKind` | `CheckpointKind` | top-level |
| [ser_lib/__init__.py:26](D:/projects/Speech-Emotion-Recognition/ser_lib/__init__.py:26) | `ser_lib.engine` | `CheckpointScanFailure` | `CheckpointScanFailure` | top-level |
| [ser_lib/__init__.py:26](D:/projects/Speech-Emotion-Recognition/ser_lib/__init__.py:26) | `ser_lib.engine` | `EtaEstimator` | `EtaEstimator` | top-level |
| [ser_lib/__init__.py:26](D:/projects/Speech-Emotion-Recognition/ser_lib/__init__.py:26) | `ser_lib.engine` | `EtaSnapshot` | `EtaSnapshot` | top-level |
| [ser_lib/__init__.py:26](D:/projects/Speech-Emotion-Recognition/ser_lib/__init__.py:26) | `ser_lib.engine` | `EvaluationPredictionFileInfo` | `EvaluationPredictionFileInfo` | top-level |
| [ser_lib/__init__.py:26](D:/projects/Speech-Emotion-Recognition/ser_lib/__init__.py:26) | `ser_lib.engine` | `EvaluationPredictionPage` | `EvaluationPredictionPage` | top-level |
| [ser_lib/__init__.py:26](D:/projects/Speech-Emotion-Recognition/ser_lib/__init__.py:26) | `ser_lib.engine` | `EvaluationReportInfo` | `EvaluationReportInfo` | top-level |
| [ser_lib/__init__.py:26](D:/projects/Speech-Emotion-Recognition/ser_lib/__init__.py:26) | `ser_lib.engine` | `EvaluationRunCatalog` | `EvaluationRunCatalog` | top-level |
| [ser_lib/__init__.py:26](D:/projects/Speech-Emotion-Recognition/ser_lib/__init__.py:26) | `ser_lib.engine` | `EvaluationRunDetail` | `EvaluationRunDetail` | top-level |
| [ser_lib/__init__.py:26](D:/projects/Speech-Emotion-Recognition/ser_lib/__init__.py:26) | `ser_lib.engine` | `EvaluationRunInfo` | `EvaluationRunInfo` | top-level |
| [ser_lib/__init__.py:26](D:/projects/Speech-Emotion-Recognition/ser_lib/__init__.py:26) | `ser_lib.engine` | `EvaluationRunMetadata` | `EvaluationRunMetadata` | top-level |
| [ser_lib/__init__.py:26](D:/projects/Speech-Emotion-Recognition/ser_lib/__init__.py:26) | `ser_lib.engine` | `EvaluationRunScanFailure` | `EvaluationRunScanFailure` | top-level |
| [ser_lib/__init__.py:26](D:/projects/Speech-Emotion-Recognition/ser_lib/__init__.py:26) | `ser_lib.engine` | `ExperimentConfig` | `ExperimentConfig` | top-level |
| [ser_lib/__init__.py:26](D:/projects/Speech-Emotion-Recognition/ser_lib/__init__.py:26) | `ser_lib.engine` | `ExperimentPresetCatalog` | `ExperimentPresetCatalog` | top-level |
| [ser_lib/__init__.py:26](D:/projects/Speech-Emotion-Recognition/ser_lib/__init__.py:26) | `ser_lib.engine` | `ExperimentPresetInfo` | `ExperimentPresetInfo` | top-level |
| [ser_lib/__init__.py:26](D:/projects/Speech-Emotion-Recognition/ser_lib/__init__.py:26) | `ser_lib.engine` | `ExperimentValidationResult` | `ExperimentValidationResult` | top-level |
| [ser_lib/__init__.py:26](D:/projects/Speech-Emotion-Recognition/ser_lib/__init__.py:26) | `ser_lib.engine` | `ModelConfig` | `ModelConfig` | top-level |
| [ser_lib/__init__.py:26](D:/projects/Speech-Emotion-Recognition/ser_lib/__init__.py:26) | `ser_lib.engine` | `ObservabilityConfig` | `ObservabilityConfig` | top-level |
| [ser_lib/__init__.py:26](D:/projects/Speech-Emotion-Recognition/ser_lib/__init__.py:26) | `ser_lib.engine` | `PresetStatus` | `PresetStatus` | top-level |
| [ser_lib/__init__.py:26](D:/projects/Speech-Emotion-Recognition/ser_lib/__init__.py:26) | `ser_lib.engine` | `Trainer` | `Trainer` | top-level |
| [ser_lib/__init__.py:26](D:/projects/Speech-Emotion-Recognition/ser_lib/__init__.py:26) | `ser_lib.engine` | `TrainerConfig` | `TrainerConfig` | top-level |
| [ser_lib/__init__.py:26](D:/projects/Speech-Emotion-Recognition/ser_lib/__init__.py:26) | `ser_lib.engine` | `TrainingHistoryInfo` | `TrainingHistoryInfo` | top-level |
| [ser_lib/__init__.py:26](D:/projects/Speech-Emotion-Recognition/ser_lib/__init__.py:26) | `ser_lib.engine` | `TrainingResult` | `TrainingResult` | top-level |
| [ser_lib/__init__.py:26](D:/projects/Speech-Emotion-Recognition/ser_lib/__init__.py:26) | `ser_lib.engine` | `TrainingRunCatalog` | `TrainingRunCatalog` | top-level |
| [ser_lib/__init__.py:26](D:/projects/Speech-Emotion-Recognition/ser_lib/__init__.py:26) | `ser_lib.engine` | `TrainingRunDetail` | `TrainingRunDetail` | top-level |
| [ser_lib/__init__.py:26](D:/projects/Speech-Emotion-Recognition/ser_lib/__init__.py:26) | `ser_lib.engine` | `TrainingRunInfo` | `TrainingRunInfo` | top-level |
| [ser_lib/__init__.py:26](D:/projects/Speech-Emotion-Recognition/ser_lib/__init__.py:26) | `ser_lib.engine` | `TrainingRunMetadata` | `TrainingRunMetadata` | top-level |
| [ser_lib/__init__.py:26](D:/projects/Speech-Emotion-Recognition/ser_lib/__init__.py:26) | `ser_lib.engine` | `TrainingRunScanFailure` | `TrainingRunScanFailure` | top-level |
| [ser_lib/__init__.py:26](D:/projects/Speech-Emotion-Recognition/ser_lib/__init__.py:26) | `ser_lib.engine` | `TrainingStatus` | `TrainingStatus` | top-level |
| [ser_lib/__init__.py:26](D:/projects/Speech-Emotion-Recognition/ser_lib/__init__.py:26) | `ser_lib.engine` | `build_evaluation_run_metadata` | `build_evaluation_run_metadata` | top-level |
| [ser_lib/__init__.py:26](D:/projects/Speech-Emotion-Recognition/ser_lib/__init__.py:26) | `ser_lib.engine` | `build_experiment_components` | `build_experiment_components` | top-level |
| [ser_lib/__init__.py:26](D:/projects/Speech-Emotion-Recognition/ser_lib/__init__.py:26) | `ser_lib.engine` | `build_experiment_config` | `build_experiment_config` | top-level |
| [ser_lib/__init__.py:26](D:/projects/Speech-Emotion-Recognition/ser_lib/__init__.py:26) | `ser_lib.engine` | `build_training_run_metadata` | `build_training_run_metadata` | top-level |
| [ser_lib/__init__.py:26](D:/projects/Speech-Emotion-Recognition/ser_lib/__init__.py:26) | `ser_lib.engine` | `evaluate` | `evaluate` | top-level |
| [ser_lib/__init__.py:26](D:/projects/Speech-Emotion-Recognition/ser_lib/__init__.py:26) | `ser_lib.engine` | `get_experiment_preset` | `get_experiment_preset` | top-level |
| [ser_lib/__init__.py:26](D:/projects/Speech-Emotion-Recognition/ser_lib/__init__.py:26) | `ser_lib.engine` | `inspect_checkpoint_file` | `inspect_checkpoint_file` | top-level |
| [ser_lib/__init__.py:26](D:/projects/Speech-Emotion-Recognition/ser_lib/__init__.py:26) | `ser_lib.engine` | `inspect_evaluation_prediction_file` | `inspect_evaluation_prediction_file` | top-level |
| [ser_lib/__init__.py:26](D:/projects/Speech-Emotion-Recognition/ser_lib/__init__.py:26) | `ser_lib.engine` | `inspect_evaluation_report` | `inspect_evaluation_report` | top-level |
| [ser_lib/__init__.py:26](D:/projects/Speech-Emotion-Recognition/ser_lib/__init__.py:26) | `ser_lib.engine` | `list_experiment_presets` | `list_experiment_presets` | top-level |
| [ser_lib/__init__.py:26](D:/projects/Speech-Emotion-Recognition/ser_lib/__init__.py:26) | `ser_lib.engine` | `load_evaluation_run_info` | `load_evaluation_run_info` | top-level |
| [ser_lib/__init__.py:26](D:/projects/Speech-Emotion-Recognition/ser_lib/__init__.py:26) | `ser_lib.engine` | `load_training_history` | `load_training_history` | top-level |
| [ser_lib/__init__.py:26](D:/projects/Speech-Emotion-Recognition/ser_lib/__init__.py:26) | `ser_lib.engine` | `load_training_run_info` | `load_training_run_info` | top-level |
| [ser_lib/__init__.py:26](D:/projects/Speech-Emotion-Recognition/ser_lib/__init__.py:26) | `ser_lib.engine` | `query_evaluation_predictions` | `query_evaluation_predictions` | top-level |
| [ser_lib/__init__.py:26](D:/projects/Speech-Emotion-Recognition/ser_lib/__init__.py:26) | `ser_lib.engine` | `scan_checkpoints` | `scan_checkpoints` | top-level |
| [ser_lib/__init__.py:26](D:/projects/Speech-Emotion-Recognition/ser_lib/__init__.py:26) | `ser_lib.engine` | `scan_evaluation_runs` | `scan_evaluation_runs` | top-level |
| [ser_lib/__init__.py:26](D:/projects/Speech-Emotion-Recognition/ser_lib/__init__.py:26) | `ser_lib.engine` | `scan_training_runs` | `scan_training_runs` | top-level |
| [ser_lib/__init__.py:26](D:/projects/Speech-Emotion-Recognition/ser_lib/__init__.py:26) | `ser_lib.engine` | `validate_experiment` | `validate_experiment` | top-level |
| [ser_lib/__init__.py:26](D:/projects/Speech-Emotion-Recognition/ser_lib/__init__.py:26) | `ser_lib.engine` | `write_evaluation_report` | `write_evaluation_report` | top-level |
| [ser_lib/__init__.py:26](D:/projects/Speech-Emotion-Recognition/ser_lib/__init__.py:26) | `ser_lib.engine` | `write_evaluation_run_info` | `write_evaluation_run_info` | top-level |
| [ser_lib/__init__.py:26](D:/projects/Speech-Emotion-Recognition/ser_lib/__init__.py:26) | `ser_lib.engine` | `write_training_run_info` | `write_training_run_info` | top-level |
| [ser_lib/__init__.py:82](D:/projects/Speech-Emotion-Recognition/ser_lib/__init__.py:82) | `ser_lib.inference` | `BatchEmotionPredictor` | `BatchEmotionPredictor` | top-level |
| [ser_lib/__init__.py:82](D:/projects/Speech-Emotion-Recognition/ser_lib/__init__.py:82) | `ser_lib.inference` | `BatchPredictionResult` | `BatchPredictionResult` | top-level |
| [ser_lib/__init__.py:82](D:/projects/Speech-Emotion-Recognition/ser_lib/__init__.py:82) | `ser_lib.inference` | `BatchPredictionSink` | `BatchPredictionSink` | top-level |
| [ser_lib/__init__.py:82](D:/projects/Speech-Emotion-Recognition/ser_lib/__init__.py:82) | `ser_lib.inference` | `EmotionPredictor` | `EmotionPredictor` | top-level |
| [ser_lib/__init__.py:82](D:/projects/Speech-Emotion-Recognition/ser_lib/__init__.py:82) | `ser_lib.inference` | `JsonlBatchPredictionSink` | `JsonlBatchPredictionSink` | top-level |
| [ser_lib/__init__.py:82](D:/projects/Speech-Emotion-Recognition/ser_lib/__init__.py:82) | `ser_lib.inference` | `PredictionFailure` | `PredictionFailure` | top-level |
| [ser_lib/__init__.py:82](D:/projects/Speech-Emotion-Recognition/ser_lib/__init__.py:82) | `ser_lib.inference` | `PredictionResult` | `PredictionResult` | top-level |
| [ser_lib/__init__.py:82](D:/projects/Speech-Emotion-Recognition/ser_lib/__init__.py:82) | `ser_lib.inference` | `StreamingConfig` | `StreamingConfig` | top-level |
| [ser_lib/__init__.py:82](D:/projects/Speech-Emotion-Recognition/ser_lib/__init__.py:82) | `ser_lib.inference` | `StreamingEmotionRecognizer` | `StreamingEmotionRecognizer` | top-level |
| [ser_lib/__init__.py:82](D:/projects/Speech-Emotion-Recognition/ser_lib/__init__.py:82) | `ser_lib.inference` | `StreamingLatency` | `StreamingLatency` | top-level |
| [ser_lib/__init__.py:82](D:/projects/Speech-Emotion-Recognition/ser_lib/__init__.py:82) | `ser_lib.inference` | `StreamingPrediction` | `StreamingPrediction` | top-level |
| [ser_lib/__init__.py:82](D:/projects/Speech-Emotion-Recognition/ser_lib/__init__.py:82) | `ser_lib.inference` | `write_batch_predictions` | `write_batch_predictions` | top-level |
| [ser_lib/__init__.py:96](D:/projects/Speech-Emotion-Recognition/ser_lib/__init__.py:96) | `ser_lib.models` | `CNNBaseline` | `CNNBaseline` | top-level |
| [ser_lib/__init__.py:96](D:/projects/Speech-Emotion-Recognition/ser_lib/__init__.py:96) | `ser_lib.models` | `GRUBaseline` | `GRUBaseline` | top-level |
| [ser_lib/__init__.py:96](D:/projects/Speech-Emotion-Recognition/ser_lib/__init__.py:96) | `ser_lib.models` | `HFAudioClassifier` | `HFAudioClassifier` | top-level |
| [ser_lib/__init__.py:96](D:/projects/Speech-Emotion-Recognition/ser_lib/__init__.py:96) | `ser_lib.models` | `ModelOutput` | `ModelOutput` | top-level |
| [ser_lib/__init__.py:96](D:/projects/Speech-Emotion-Recognition/ser_lib/__init__.py:96) | `ser_lib.models` | `SERModel` | `SERModel` | top-level |
| [ser_lib/__init__.py:96](D:/projects/Speech-Emotion-Recognition/ser_lib/__init__.py:96) | `ser_lib.models` | `TransformerBaseline` | `TransformerBaseline` | top-level |
| [ser_lib/__init__.py:104](D:/projects/Speech-Emotion-Recognition/ser_lib/__init__.py:104) | `ser_lib.catalog` | `CATALOG_CATEGORIES` | `CATALOG_CATEGORIES` | top-level |
| [ser_lib/__init__.py:104](D:/projects/Speech-Emotion-Recognition/ser_lib/__init__.py:104) | `ser_lib.catalog` | `CATALOG_SCHEMA_VERSION` | `CATALOG_SCHEMA_VERSION` | top-level |
| [ser_lib/__init__.py:104](D:/projects/Speech-Emotion-Recognition/ser_lib/__init__.py:104) | `ser_lib.catalog` | `ComponentCatalog` | `ComponentCatalog` | top-level |
| [ser_lib/__init__.py:104](D:/projects/Speech-Emotion-Recognition/ser_lib/__init__.py:104) | `ser_lib.catalog` | `ComponentDescriptor` | `ComponentDescriptor` | top-level |
| [ser_lib/__init__.py:104](D:/projects/Speech-Emotion-Recognition/ser_lib/__init__.py:104) | `ser_lib.catalog` | `get_component_catalog` | `get_component_catalog` | top-level |
| [ser_lib/__init__.py:104](D:/projects/Speech-Emotion-Recognition/ser_lib/__init__.py:104) | `ser_lib.catalog` | `list_component_descriptors` | `list_component_descriptors` | top-level |
| [ser_lib/__init__.py:112](D:/projects/Speech-Emotion-Recognition/ser_lib/__init__.py:112) | `ser_lib.runtime` | `RuntimeCapabilities` | `RuntimeCapabilities` | top-level |
| [ser_lib/__init__.py:112](D:/projects/Speech-Emotion-Recognition/ser_lib/__init__.py:112) | `ser_lib.runtime` | `RuntimeDevice` | `RuntimeDevice` | top-level |
| [ser_lib/__init__.py:112](D:/projects/Speech-Emotion-Recognition/ser_lib/__init__.py:112) | `ser_lib.runtime` | `RuntimeMetrics` | `RuntimeMetrics` | top-level |
| [ser_lib/__init__.py:112](D:/projects/Speech-Emotion-Recognition/ser_lib/__init__.py:112) | `ser_lib.runtime` | `get_runtime_capabilities` | `get_runtime_capabilities` | top-level |
| [ser_lib/__init__.py:112](D:/projects/Speech-Emotion-Recognition/ser_lib/__init__.py:112) | `ser_lib.runtime` | `get_runtime_metrics` | `get_runtime_metrics` | top-level |
| [ser_lib/artifacts/__init__.py:1](D:/projects/Speech-Emotion-Recognition/ser_lib/artifacts/__init__.py:1) | `ser_lib.artifacts.catalog` | `ArtifactCatalog` | `ArtifactCatalog` | top-level |
| [ser_lib/artifacts/__init__.py:1](D:/projects/Speech-Emotion-Recognition/ser_lib/artifacts/__init__.py:1) | `ser_lib.artifacts.catalog` | `ArtifactInfo` | `ArtifactInfo` | top-level |
| [ser_lib/artifacts/__init__.py:1](D:/projects/Speech-Emotion-Recognition/ser_lib/artifacts/__init__.py:1) | `ser_lib.artifacts.catalog` | `ArtifactScanFailure` | `ArtifactScanFailure` | top-level |
| [ser_lib/artifacts/__init__.py:1](D:/projects/Speech-Emotion-Recognition/ser_lib/artifacts/__init__.py:1) | `ser_lib.artifacts.catalog` | `scan_model_artifacts` | `scan_model_artifacts` | top-level |
| [ser_lib/artifacts/__init__.py:7](D:/projects/Speech-Emotion-Recognition/ser_lib/artifacts/__init__.py:7) | `ser_lib.artifacts.exporter` | `export_model_artifact` | `export_model_artifact` | top-level |
| [ser_lib/artifacts/__init__.py:8](D:/projects/Speech-Emotion-Recognition/ser_lib/artifacts/__init__.py:8) | `ser_lib.artifacts.loader` | `LoadedArtifact` | `LoadedArtifact` | top-level |
| [ser_lib/artifacts/__init__.py:8](D:/projects/Speech-Emotion-Recognition/ser_lib/artifacts/__init__.py:8) | `ser_lib.artifacts.loader` | `inspect_model_artifact` | `inspect_model_artifact` | top-level |
| [ser_lib/artifacts/__init__.py:8](D:/projects/Speech-Emotion-Recognition/ser_lib/artifacts/__init__.py:8) | `ser_lib.artifacts.loader` | `load_model_artifact` | `load_model_artifact` | top-level |
| [ser_lib/artifacts/__init__.py:8](D:/projects/Speech-Emotion-Recognition/ser_lib/artifacts/__init__.py:8) | `ser_lib.artifacts.loader` | `verify_model_artifact` | `verify_model_artifact` | top-level |
| [ser_lib/artifacts/__init__.py:14](D:/projects/Speech-Emotion-Recognition/ser_lib/artifacts/__init__.py:14) | `ser_lib.artifacts.manifest` | `ModelArtifactManifest` | `ModelArtifactManifest` | top-level |
| [ser_lib/artifacts/__init__.py:14](D:/projects/Speech-Emotion-Recognition/ser_lib/artifacts/__init__.py:14) | `ser_lib.artifacts.manifest` | `ModelCard` | `ModelCard` | top-level |
| [ser_lib/artifacts/catalog.py:9](D:/projects/Speech-Emotion-Recognition/ser_lib/artifacts/catalog.py:9) | `ser_lib.artifacts.loader` | `inspect_model_artifact` | `inspect_model_artifact` | top-level |
| [ser_lib/artifacts/catalog.py:10](D:/projects/Speech-Emotion-Recognition/ser_lib/artifacts/catalog.py:10) | `ser_lib.artifacts.manifest` | `ModelArtifactManifest` | `ModelArtifactManifest` | top-level |
| [ser_lib/artifacts/catalog.py:11](D:/projects/Speech-Emotion-Recognition/ser_lib/artifacts/catalog.py:11) | `ser_lib.core._catalog_scan` | `scan_catalog_candidates` | `scan_catalog_candidates` | top-level |
| [ser_lib/artifacts/catalog.py:12](D:/projects/Speech-Emotion-Recognition/ser_lib/artifacts/catalog.py:12) | `ser_lib.core.events` | `CancellationCheck` | `CancellationCheck` | top-level |
| [ser_lib/artifacts/catalog.py:12](D:/projects/Speech-Emotion-Recognition/ser_lib/artifacts/catalog.py:12) | `ser_lib.core.events` | `EventCallback` | `EventCallback` | top-level |
| [ser_lib/artifacts/exporter.py:16](D:/projects/Speech-Emotion-Recognition/ser_lib/artifacts/exporter.py:16) | `ser_lib` | `__version__` | `__version__` | top-level |
| [ser_lib/artifacts/exporter.py:17](D:/projects/Speech-Emotion-Recognition/ser_lib/artifacts/exporter.py:17) | `ser_lib.artifacts.manifest` | `ModelArtifactManifest` | `ModelArtifactManifest` | top-level |
| [ser_lib/artifacts/exporter.py:17](D:/projects/Speech-Emotion-Recognition/ser_lib/artifacts/exporter.py:17) | `ser_lib.artifacts.manifest` | `ModelCard` | `ModelCard` | top-level |
| [ser_lib/artifacts/exporter.py:18](D:/projects/Speech-Emotion-Recognition/ser_lib/artifacts/exporter.py:18) | `ser_lib.core.events` | `CancellationCheck` | `CancellationCheck` | top-level |
| [ser_lib/artifacts/exporter.py:18](D:/projects/Speech-Emotion-Recognition/ser_lib/artifacts/exporter.py:18) | `ser_lib.core.events` | `EventCallback` | `EventCallback` | top-level |
| [ser_lib/artifacts/exporter.py:18](D:/projects/Speech-Emotion-Recognition/ser_lib/artifacts/exporter.py:18) | `ser_lib.core.events` | `EventContext` | `EventContext` | top-level |
| [ser_lib/artifacts/exporter.py:18](D:/projects/Speech-Emotion-Recognition/ser_lib/artifacts/exporter.py:18) | `ser_lib.core.events` | `LifecycleEvent` | `LifecycleEvent` | top-level |
| [ser_lib/artifacts/exporter.py:18](D:/projects/Speech-Emotion-Recognition/ser_lib/artifacts/exporter.py:18) | `ser_lib.core.events` | `ProgressEvent` | `ProgressEvent` | top-level |
| [ser_lib/artifacts/exporter.py:25](D:/projects/Speech-Emotion-Recognition/ser_lib/artifacts/exporter.py:25) | `ser_lib.core.exceptions` | `OperationCancelled` | `OperationCancelled` | top-level |
| [ser_lib/artifacts/exporter.py:26](D:/projects/Speech-Emotion-Recognition/ser_lib/artifacts/exporter.py:26) | `ser_lib.data.config` | `DataConfig` | `DataConfig` | top-level |
| [ser_lib/artifacts/exporter.py:27](D:/projects/Speech-Emotion-Recognition/ser_lib/artifacts/exporter.py:27) | `ser_lib.models.base` | `SERModel` | `SERModel` | top-level |
| [ser_lib/artifacts/exporter.py:28](D:/projects/Speech-Emotion-Recognition/ser_lib/artifacts/exporter.py:28) | `ser_lib.models.registry` | `model_registry` | `model_registry` | top-level |
| [ser_lib/artifacts/loader.py:14](D:/projects/Speech-Emotion-Recognition/ser_lib/artifacts/loader.py:14) | `ser_lib` | `__version__` | `__version__` | top-level |
| [ser_lib/artifacts/loader.py:15](D:/projects/Speech-Emotion-Recognition/ser_lib/artifacts/loader.py:15) | `ser_lib.artifacts.manifest` | `ModelArtifactManifest` | `ModelArtifactManifest` | top-level |
| [ser_lib/artifacts/loader.py:16](D:/projects/Speech-Emotion-Recognition/ser_lib/artifacts/loader.py:16) | `ser_lib.core.events` | `CancellationCheck` | `CancellationCheck` | top-level |
| [ser_lib/artifacts/loader.py:16](D:/projects/Speech-Emotion-Recognition/ser_lib/artifacts/loader.py:16) | `ser_lib.core.events` | `EventCallback` | `EventCallback` | top-level |
| [ser_lib/artifacts/loader.py:16](D:/projects/Speech-Emotion-Recognition/ser_lib/artifacts/loader.py:16) | `ser_lib.core.events` | `EventContext` | `EventContext` | top-level |
| [ser_lib/artifacts/loader.py:16](D:/projects/Speech-Emotion-Recognition/ser_lib/artifacts/loader.py:16) | `ser_lib.core.events` | `LifecycleEvent` | `LifecycleEvent` | top-level |
| [ser_lib/artifacts/loader.py:16](D:/projects/Speech-Emotion-Recognition/ser_lib/artifacts/loader.py:16) | `ser_lib.core.events` | `ProgressEvent` | `ProgressEvent` | top-level |
| [ser_lib/artifacts/loader.py:23](D:/projects/Speech-Emotion-Recognition/ser_lib/artifacts/loader.py:23) | `ser_lib.core.exceptions` | `OperationCancelled` | `OperationCancelled` | top-level |
| [ser_lib/artifacts/loader.py:24](D:/projects/Speech-Emotion-Recognition/ser_lib/artifacts/loader.py:24) | `ser_lib.core.migrations` | `validate_schema_version` | `validate_schema_version` | top-level |
| [ser_lib/artifacts/loader.py:25](D:/projects/Speech-Emotion-Recognition/ser_lib/artifacts/loader.py:25) | `ser_lib.data.audio` | `AudioLoader` | `AudioLoader` | top-level |
| [ser_lib/artifacts/loader.py:26](D:/projects/Speech-Emotion-Recognition/ser_lib/artifacts/loader.py:26) | `ser_lib.data.collate` | `SERCollator` | `SERCollator` | top-level |
| [ser_lib/artifacts/loader.py:26](D:/projects/Speech-Emotion-Recognition/ser_lib/artifacts/loader.py:26) | `ser_lib.data.collate` | `build_collator` | `build_collator` | top-level |
| [ser_lib/artifacts/loader.py:27](D:/projects/Speech-Emotion-Recognition/ser_lib/artifacts/loader.py:27) | `ser_lib.data.config` | `DataConfig` | `DataConfig` | top-level |
| [ser_lib/artifacts/loader.py:28](D:/projects/Speech-Emotion-Recognition/ser_lib/artifacts/loader.py:28) | `ser_lib.data.pipeline` | `SamplePipeline` | `SamplePipeline` | top-level |
| [ser_lib/artifacts/loader.py:28](D:/projects/Speech-Emotion-Recognition/ser_lib/artifacts/loader.py:28) | `ser_lib.data.pipeline` | `build_components` | `build_components` | top-level |
| [ser_lib/artifacts/loader.py:29](D:/projects/Speech-Emotion-Recognition/ser_lib/artifacts/loader.py:29) | `ser_lib.data.validation` | `validate_compatibility` | `validate_compatibility` | top-level |
| [ser_lib/artifacts/loader.py:30](D:/projects/Speech-Emotion-Recognition/ser_lib/artifacts/loader.py:30) | `ser_lib.models.base` | `SERModel` | `SERModel` | top-level |
| [ser_lib/artifacts/loader.py:31](D:/projects/Speech-Emotion-Recognition/ser_lib/artifacts/loader.py:31) | `ser_lib.models.registry` | `model_registry` | `model_registry` | top-level |
| [ser_lib/artifacts/manifest.py:10](D:/projects/Speech-Emotion-Recognition/ser_lib/artifacts/manifest.py:10) | `ser_lib.core.config` | `StrictConfig` | `StrictConfig` | top-level |
| [ser_lib/catalog.py:16](D:/projects/Speech-Emotion-Recognition/ser_lib/catalog.py:16) | `ser_lib` | `data` | `_data_package` | top-level |
| [ser_lib/catalog.py:17](D:/projects/Speech-Emotion-Recognition/ser_lib/catalog.py:17) | `ser_lib` | `models` | `_models_package` | top-level |
| [ser_lib/catalog.py:18](D:/projects/Speech-Emotion-Recognition/ser_lib/catalog.py:18) | `ser_lib.data.errors` | `RegistryError` | `RegistryError` | top-level |
| [ser_lib/catalog.py:19](D:/projects/Speech-Emotion-Recognition/ser_lib/catalog.py:19) | `ser_lib.data.registry` | `ComponentDescriptor` | `ComponentDescriptor` | top-level |
| [ser_lib/catalog.py:19](D:/projects/Speech-Emotion-Recognition/ser_lib/catalog.py:19) | `ser_lib.data.registry` | `default_registry` | `default_registry` | top-level |
| [ser_lib/catalog.py:20](D:/projects/Speech-Emotion-Recognition/ser_lib/catalog.py:20) | `ser_lib.engine.objectives` | `LossConfig` | `LossConfig` | top-level |
| [ser_lib/catalog.py:20](D:/projects/Speech-Emotion-Recognition/ser_lib/catalog.py:20) | `ser_lib.engine.objectives` | `SamplingConfig` | `SamplingConfig` | top-level |
| [ser_lib/catalog.py:21](D:/projects/Speech-Emotion-Recognition/ser_lib/catalog.py:21) | `ser_lib.engine.optim` | `AdamConfig` | `AdamConfig` | top-level |
| [ser_lib/catalog.py:21](D:/projects/Speech-Emotion-Recognition/ser_lib/catalog.py:21) | `ser_lib.engine.optim` | `AdamWConfig` | `AdamWConfig` | top-level |
| [ser_lib/catalog.py:21](D:/projects/Speech-Emotion-Recognition/ser_lib/catalog.py:21) | `ser_lib.engine.optim` | `CosineSchedulerConfig` | `CosineSchedulerConfig` | top-level |
| [ser_lib/catalog.py:21](D:/projects/Speech-Emotion-Recognition/ser_lib/catalog.py:21) | `ser_lib.engine.optim` | `SGDConfig` | `SGDConfig` | top-level |
| [ser_lib/catalog.py:21](D:/projects/Speech-Emotion-Recognition/ser_lib/catalog.py:21) | `ser_lib.engine.optim` | `StepSchedulerConfig` | `StepSchedulerConfig` | top-level |
| [ser_lib/catalog.py:28](D:/projects/Speech-Emotion-Recognition/ser_lib/catalog.py:28) | `ser_lib.models.registry` | `model_registry` | `model_registry` | top-level |
| [ser_lib/cli/__init__.py:3](D:/projects/Speech-Emotion-Recognition/ser_lib/cli/__init__.py:3) | `ser_lib.cli.main` | `main` | `main` | top-level |
| [ser_lib/cli/__main__.py:1](D:/projects/Speech-Emotion-Recognition/ser_lib/cli/__main__.py:1) | `ser_lib.cli.main` | `main` | `main` | top-level |
| [ser_lib/cli/main.py:15](D:/projects/Speech-Emotion-Recognition/ser_lib/cli/main.py:15) | `ser_lib` | `__version__` | `__version__` | top-level |
| [ser_lib/cli/main.py:16](D:/projects/Speech-Emotion-Recognition/ser_lib/cli/main.py:16) | `ser_lib.core` | `ConfigurationError` | `ConfigurationError` | top-level |
| [ser_lib/cli/main.py:16](D:/projects/Speech-Emotion-Recognition/ser_lib/cli/main.py:16) | `ser_lib.core` | `SERError` | `SERError` | top-level |
| [ser_lib/cli/main.py:17](D:/projects/Speech-Emotion-Recognition/ser_lib/cli/main.py:17) | `ser_lib.data` | `DatasetManifest` | `DatasetManifest` | top-level |
| [ser_lib/cli/main.py:17](D:/projects/Speech-Emotion-Recognition/ser_lib/cli/main.py:17) | `ser_lib.data` | `ManifestError` | `ManifestError` | top-level |
| [ser_lib/cli/main.py:17](D:/projects/Speech-Emotion-Recognition/ser_lib/cli/main.py:17) | `ser_lib.data` | `default_registry` | `default_registry` | top-level |
| [ser_lib/cli/main.py:17](D:/projects/Speech-Emotion-Recognition/ser_lib/cli/main.py:17) | `ser_lib.data` | `profile_manifest_audio` | `profile_manifest_audio` | top-level |
| [ser_lib/cli/main.py:23](D:/projects/Speech-Emotion-Recognition/ser_lib/cli/main.py:23) | `ser_lib.models` | `model_registry` | `model_registry` | top-level |
| [ser_lib/cli/main.py:24](D:/projects/Speech-Emotion-Recognition/ser_lib/cli/main.py:24) | `ser_lib.cli.workflows` | `evaluate_artifact` | `evaluate_artifact` | top-level |
| [ser_lib/cli/main.py:24](D:/projects/Speech-Emotion-Recognition/ser_lib/cli/main.py:24) | `ser_lib.cli.workflows` | `export_checkpoint_artifact` | `export_checkpoint_artifact` | top-level |
| [ser_lib/cli/main.py:24](D:/projects/Speech-Emotion-Recognition/ser_lib/cli/main.py:24) | `ser_lib.cli.workflows` | `inspect_artifact` | `inspect_artifact` | top-level |
| [ser_lib/cli/main.py:24](D:/projects/Speech-Emotion-Recognition/ser_lib/cli/main.py:24) | `ser_lib.cli.workflows` | `predict_artifact` | `predict_artifact` | top-level |
| [ser_lib/cli/main.py:24](D:/projects/Speech-Emotion-Recognition/ser_lib/cli/main.py:24) | `ser_lib.cli.workflows` | `train_experiment` | `train_experiment` | top-level |
| [ser_lib/cli/workflows.py:14](D:/projects/Speech-Emotion-Recognition/ser_lib/cli/workflows.py:14) | `ser_lib.artifacts` | `ModelCard` | `ModelCard` | top-level |
| [ser_lib/cli/workflows.py:15](D:/projects/Speech-Emotion-Recognition/ser_lib/cli/workflows.py:15) | `ser_lib.core` | `EventContext` | `EventContext` | top-level |
| [ser_lib/cli/workflows.py:16](D:/projects/Speech-Emotion-Recognition/ser_lib/cli/workflows.py:16) | `ser_lib.data` | `DatasetManifest` | `DatasetManifest` | top-level |
| [ser_lib/cli/workflows.py:16](D:/projects/Speech-Emotion-Recognition/ser_lib/cli/workflows.py:16) | `ser_lib.data` | `SERDataset` | `SERDataset` | top-level |
| [ser_lib/cli/workflows.py:16](D:/projects/Speech-Emotion-Recognition/ser_lib/cli/workflows.py:16) | `ser_lib.data` | `fingerprint_manifest` | `fingerprint_manifest` | top-level |
| [ser_lib/cli/workflows.py:17](D:/projects/Speech-Emotion-Recognition/ser_lib/cli/workflows.py:17) | `ser_lib.engine` | `TrainingRunMetadata` | `TrainingRunMetadata` | top-level |
| [ser_lib/cli/workflows.py:17](D:/projects/Speech-Emotion-Recognition/ser_lib/cli/workflows.py:17) | `ser_lib.engine` | `build_experiment_components` | `build_experiment_components` | top-level |
| [ser_lib/cli/workflows.py:17](D:/projects/Speech-Emotion-Recognition/ser_lib/cli/workflows.py:17) | `ser_lib.engine` | `build_weighted_sampler` | `build_weighted_sampler` | top-level |
| [ser_lib/cli/workflows.py:17](D:/projects/Speech-Emotion-Recognition/ser_lib/cli/workflows.py:17) | `ser_lib.engine` | `load_checkpoint` | `load_checkpoint` | top-level |
| [ser_lib/cli/workflows.py:17](D:/projects/Speech-Emotion-Recognition/ser_lib/cli/workflows.py:17) | `ser_lib.engine` | `load_experiment_config` | `load_experiment_config` | top-level |
| [ser_lib/cli/workflows.py:24](D:/projects/Speech-Emotion-Recognition/ser_lib/cli/workflows.py:24) | `ser_lib.services` | `ArtifactService` | `ArtifactService` | top-level |
| [ser_lib/cli/workflows.py:24](D:/projects/Speech-Emotion-Recognition/ser_lib/cli/workflows.py:24) | `ser_lib.services` | `EvaluationService` | `EvaluationService` | top-level |
| [ser_lib/cli/workflows.py:24](D:/projects/Speech-Emotion-Recognition/ser_lib/cli/workflows.py:24) | `ser_lib.services` | `InferenceService` | `InferenceService` | top-level |
| [ser_lib/cli/workflows.py:24](D:/projects/Speech-Emotion-Recognition/ser_lib/cli/workflows.py:24) | `ser_lib.services` | `TrainingService` | `TrainingService` | top-level |
| [ser_lib/core/__init__.py:3](D:/projects/Speech-Emotion-Recognition/ser_lib/core/__init__.py:3) | `ser_lib.core.config` | `StrictConfig` | `StrictConfig` | top-level |
| [ser_lib/core/__init__.py:3](D:/projects/Speech-Emotion-Recognition/ser_lib/core/__init__.py:3) | `ser_lib.core.config` | `load_versioned_config` | `load_versioned_config` | top-level |
| [ser_lib/core/__init__.py:3](D:/projects/Speech-Emotion-Recognition/ser_lib/core/__init__.py:3) | `ser_lib.core.config` | `load_yaml_mapping` | `load_yaml_mapping` | top-level |
| [ser_lib/core/__init__.py:3](D:/projects/Speech-Emotion-Recognition/ser_lib/core/__init__.py:3) | `ser_lib.core.config` | `require_schema_version` | `require_schema_version` | top-level |
| [ser_lib/core/__init__.py:3](D:/projects/Speech-Emotion-Recognition/ser_lib/core/__init__.py:3) | `ser_lib.core.config` | `resolve_config_path` | `resolve_config_path` | top-level |
| [ser_lib/core/__init__.py:10](D:/projects/Speech-Emotion-Recognition/ser_lib/core/__init__.py:10) | `ser_lib.core.diagnostics` | `Diagnostic` | `Diagnostic` | top-level |
| [ser_lib/core/__init__.py:10](D:/projects/Speech-Emotion-Recognition/ser_lib/core/__init__.py:10) | `ser_lib.core.diagnostics` | `DiagnosticSeverity` | `DiagnosticSeverity` | top-level |
| [ser_lib/core/__init__.py:11](D:/projects/Speech-Emotion-Recognition/ser_lib/core/__init__.py:11) | `ser_lib.core.events` | `EVENT_SCHEMA_VERSION` | `EVENT_SCHEMA_VERSION` | top-level |
| [ser_lib/core/__init__.py:11](D:/projects/Speech-Emotion-Recognition/ser_lib/core/__init__.py:11) | `ser_lib.core.events` | `CancellationCheck` | `CancellationCheck` | top-level |
| [ser_lib/core/__init__.py:11](D:/projects/Speech-Emotion-Recognition/ser_lib/core/__init__.py:11) | `ser_lib.core.events` | `CancellationToken` | `CancellationToken` | top-level |
| [ser_lib/core/__init__.py:11](D:/projects/Speech-Emotion-Recognition/ser_lib/core/__init__.py:11) | `ser_lib.core.events` | `CheckpointEvent` | `CheckpointEvent` | top-level |
| [ser_lib/core/__init__.py:11](D:/projects/Speech-Emotion-Recognition/ser_lib/core/__init__.py:11) | `ser_lib.core.events` | `EventCallback` | `EventCallback` | top-level |
| [ser_lib/core/__init__.py:11](D:/projects/Speech-Emotion-Recognition/ser_lib/core/__init__.py:11) | `ser_lib.core.events` | `EventContext` | `EventContext` | top-level |
| [ser_lib/core/__init__.py:11](D:/projects/Speech-Emotion-Recognition/ser_lib/core/__init__.py:11) | `ser_lib.core.events` | `LibraryEvent` | `LibraryEvent` | top-level |
| [ser_lib/core/__init__.py:11](D:/projects/Speech-Emotion-Recognition/ser_lib/core/__init__.py:11) | `ser_lib.core.events` | `LifecycleEvent` | `LifecycleEvent` | top-level |
| [ser_lib/core/__init__.py:11](D:/projects/Speech-Emotion-Recognition/ser_lib/core/__init__.py:11) | `ser_lib.core.events` | `LogEvent` | `LogEvent` | top-level |
| [ser_lib/core/__init__.py:11](D:/projects/Speech-Emotion-Recognition/ser_lib/core/__init__.py:11) | `ser_lib.core.events` | `MetricEvent` | `MetricEvent` | top-level |
| [ser_lib/core/__init__.py:11](D:/projects/Speech-Emotion-Recognition/ser_lib/core/__init__.py:11) | `ser_lib.core.events` | `PredictionEvent` | `PredictionEvent` | top-level |
| [ser_lib/core/__init__.py:11](D:/projects/Speech-Emotion-Recognition/ser_lib/core/__init__.py:11) | `ser_lib.core.events` | `ProgressEvent` | `ProgressEvent` | top-level |
| [ser_lib/core/__init__.py:25](D:/projects/Speech-Emotion-Recognition/ser_lib/core/__init__.py:25) | `ser_lib.core.exceptions` | `ConfigurationError` | `ConfigurationError` | top-level |
| [ser_lib/core/__init__.py:25](D:/projects/Speech-Emotion-Recognition/ser_lib/core/__init__.py:25) | `ser_lib.core.exceptions` | `OperationCancelled` | `OperationCancelled` | top-level |
| [ser_lib/core/__init__.py:25](D:/projects/Speech-Emotion-Recognition/ser_lib/core/__init__.py:25) | `ser_lib.core.exceptions` | `SchemaMigrationError` | `SchemaMigrationError` | top-level |
| [ser_lib/core/__init__.py:25](D:/projects/Speech-Emotion-Recognition/ser_lib/core/__init__.py:25) | `ser_lib.core.exceptions` | `SERError` | `SERError` | top-level |
| [ser_lib/core/__init__.py:31](D:/projects/Speech-Emotion-Recognition/ser_lib/core/__init__.py:31) | `ser_lib.core.logging` | `configure_library_logging` | `configure_library_logging` | top-level |
| [ser_lib/core/__init__.py:31](D:/projects/Speech-Emotion-Recognition/ser_lib/core/__init__.py:31) | `ser_lib.core.logging` | `get_logger` | `get_logger` | top-level |
| [ser_lib/core/__init__.py:32](D:/projects/Speech-Emotion-Recognition/ser_lib/core/__init__.py:32) | `ser_lib.core.migrations` | `MigrationFunction` | `MigrationFunction` | top-level |
| [ser_lib/core/__init__.py:32](D:/projects/Speech-Emotion-Recognition/ser_lib/core/__init__.py:32) | `ser_lib.core.migrations` | `MigrationRegistry` | `MigrationRegistry` | top-level |
| [ser_lib/core/__init__.py:32](D:/projects/Speech-Emotion-Recognition/ser_lib/core/__init__.py:32) | `ser_lib.core.migrations` | `SchemaMigration` | `SchemaMigration` | top-level |
| [ser_lib/core/__init__.py:32](D:/projects/Speech-Emotion-Recognition/ser_lib/core/__init__.py:32) | `ser_lib.core.migrations` | `list_schema_migrations` | `list_schema_migrations` | top-level |
| [ser_lib/core/__init__.py:32](D:/projects/Speech-Emotion-Recognition/ser_lib/core/__init__.py:32) | `ser_lib.core.migrations` | `migrate_schema_payload` | `migrate_schema_payload` | top-level |
| [ser_lib/core/__init__.py:32](D:/projects/Speech-Emotion-Recognition/ser_lib/core/__init__.py:32) | `ser_lib.core.migrations` | `register_schema_migration` | `register_schema_migration` | top-level |
| [ser_lib/core/__init__.py:32](D:/projects/Speech-Emotion-Recognition/ser_lib/core/__init__.py:32) | `ser_lib.core.migrations` | `validate_schema_version` | `validate_schema_version` | top-level |
| [ser_lib/core/_catalog_scan.py:9](D:/projects/Speech-Emotion-Recognition/ser_lib/core/_catalog_scan.py:9) | `ser_lib.core.events` | `CancellationCheck` | `CancellationCheck` | top-level |
| [ser_lib/core/_catalog_scan.py:9](D:/projects/Speech-Emotion-Recognition/ser_lib/core/_catalog_scan.py:9) | `ser_lib.core.events` | `EventCallback` | `EventCallback` | top-level |
| [ser_lib/core/_catalog_scan.py:9](D:/projects/Speech-Emotion-Recognition/ser_lib/core/_catalog_scan.py:9) | `ser_lib.core.events` | `ProgressEvent` | `ProgressEvent` | top-level |
| [ser_lib/core/config.py:11](D:/projects/Speech-Emotion-Recognition/ser_lib/core/config.py:11) | `ser_lib.core.exceptions` | `ConfigurationError` | `ConfigurationError` | top-level |
| [ser_lib/core/config.py:11](D:/projects/Speech-Emotion-Recognition/ser_lib/core/config.py:11) | `ser_lib.core.exceptions` | `SchemaMigrationError` | `SchemaMigrationError` | top-level |
| [ser_lib/core/config.py:82](D:/projects/Speech-Emotion-Recognition/ser_lib/core/config.py:82) | `ser_lib.core.migrations` | `migrate_schema_payload` | `migrate_schema_payload` | local:load_versioned_config,conditional |
| [ser_lib/core/diagnostics.py:91](D:/projects/Speech-Emotion-Recognition/ser_lib/core/diagnostics.py:91) | `ser_lib.core.exceptions` | `SERError` | `SERError` | local:from_error |
| [ser_lib/core/events.py:14](D:/projects/Speech-Emotion-Recognition/ser_lib/core/events.py:14) | `ser_lib.core.exceptions` | `OperationCancelled` | `OperationCancelled` | top-level |
| [ser_lib/core/migrations.py:10](D:/projects/Speech-Emotion-Recognition/ser_lib/core/migrations.py:10) | `ser_lib.core.exceptions` | `SchemaMigrationError` | `SchemaMigrationError` | top-level |
| [ser_lib/data/__init__.py:7](D:/projects/Speech-Emotion-Recognition/ser_lib/data/__init__.py:7) | `ser_lib.data.audio` | `AudioLoader` | `AudioLoader` | top-level |
| [ser_lib/data/__init__.py:7](D:/projects/Speech-Emotion-Recognition/ser_lib/data/__init__.py:7) | `ser_lib.data.audio` | `AudioLoaderConfig` | `AudioLoaderConfig` | top-level |
| [ser_lib/data/__init__.py:8](D:/projects/Speech-Emotion-Recognition/ser_lib/data/__init__.py:8) | `ser_lib.data.cache` | `CachedRepresentation` | `CachedRepresentation` | top-level |
| [ser_lib/data/__init__.py:9](D:/projects/Speech-Emotion-Recognition/ser_lib/data/__init__.py:9) | `ser_lib.data.collate` | `CollateStrategy` | `CollateStrategy` | top-level |
| [ser_lib/data/__init__.py:9](D:/projects/Speech-Emotion-Recognition/ser_lib/data/__init__.py:9) | `ser_lib.data.collate` | `SERCollator` | `SERCollator` | top-level |
| [ser_lib/data/__init__.py:9](D:/projects/Speech-Emotion-Recognition/ser_lib/data/__init__.py:9) | `ser_lib.data.collate` | `build_collator` | `build_collator` | top-level |
| [ser_lib/data/__init__.py:10](D:/projects/Speech-Emotion-Recognition/ser_lib/data/__init__.py:10) | `ser_lib.data.config` | `AudioSettings` | `AudioSettings` | top-level |
| [ser_lib/data/__init__.py:10](D:/projects/Speech-Emotion-Recognition/ser_lib/data/__init__.py:10) | `ser_lib.data.config` | `BatchingConfig` | `BatchingConfig` | top-level |
| [ser_lib/data/__init__.py:10](D:/projects/Speech-Emotion-Recognition/ser_lib/data/__init__.py:10) | `ser_lib.data.config` | `CacheSettings` | `CacheSettings` | top-level |
| [ser_lib/data/__init__.py:10](D:/projects/Speech-Emotion-Recognition/ser_lib/data/__init__.py:10) | `ser_lib.data.config` | `ComponentConfig` | `ComponentConfig` | top-level |
| [ser_lib/data/__init__.py:10](D:/projects/Speech-Emotion-Recognition/ser_lib/data/__init__.py:10) | `ser_lib.data.config` | `DataConfig` | `DataConfig` | top-level |
| [ser_lib/data/__init__.py:10](D:/projects/Speech-Emotion-Recognition/ser_lib/data/__init__.py:10) | `ser_lib.data.config` | `load_data_config` | `load_data_config` | top-level |
| [ser_lib/data/__init__.py:11](D:/projects/Speech-Emotion-Recognition/ser_lib/data/__init__.py:11) | `ser_lib.data.dataset` | `SERDataset` | `SERDataset` | top-level |
| [ser_lib/data/__init__.py:12](D:/projects/Speech-Emotion-Recognition/ser_lib/data/__init__.py:12) | `ser_lib.data.editor` | `DatasetEditor` | `DatasetEditor` | top-level |
| [ser_lib/data/__init__.py:13](D:/projects/Speech-Emotion-Recognition/ser_lib/data/__init__.py:13) | `ser_lib.data.errors` | `AudioDecodeError` | `AudioDecodeError` | top-level |
| [ser_lib/data/__init__.py:13](D:/projects/Speech-Emotion-Recognition/ser_lib/data/__init__.py:13) | `ser_lib.data.errors` | `AudioNotFoundError` | `AudioNotFoundError` | top-level |
| [ser_lib/data/__init__.py:13](D:/projects/Speech-Emotion-Recognition/ser_lib/data/__init__.py:13) | `ser_lib.data.errors` | `CollationError` | `CollationError` | top-level |
| [ser_lib/data/__init__.py:13](D:/projects/Speech-Emotion-Recognition/ser_lib/data/__init__.py:13) | `ser_lib.data.errors` | `CompatibilityError` | `CompatibilityError` | top-level |
| [ser_lib/data/__init__.py:13](D:/projects/Speech-Emotion-Recognition/ser_lib/data/__init__.py:13) | `ser_lib.data.errors` | `DatasetEditConflictError` | `DatasetEditConflictError` | top-level |
| [ser_lib/data/__init__.py:13](D:/projects/Speech-Emotion-Recognition/ser_lib/data/__init__.py:13) | `ser_lib.data.errors` | `DatasetEditError` | `DatasetEditError` | top-level |
| [ser_lib/data/__init__.py:13](D:/projects/Speech-Emotion-Recognition/ser_lib/data/__init__.py:13) | `ser_lib.data.errors` | `DatasetTransactionError` | `DatasetTransactionError` | top-level |
| [ser_lib/data/__init__.py:13](D:/projects/Speech-Emotion-Recognition/ser_lib/data/__init__.py:13) | `ser_lib.data.errors` | `InvalidAudioSegmentError` | `InvalidAudioSegmentError` | top-level |
| [ser_lib/data/__init__.py:13](D:/projects/Speech-Emotion-Recognition/ser_lib/data/__init__.py:13) | `ser_lib.data.errors` | `ManifestError` | `ManifestError` | top-level |
| [ser_lib/data/__init__.py:13](D:/projects/Speech-Emotion-Recognition/ser_lib/data/__init__.py:13) | `ser_lib.data.errors` | `RegistryError` | `RegistryError` | top-level |
| [ser_lib/data/__init__.py:13](D:/projects/Speech-Emotion-Recognition/ser_lib/data/__init__.py:13) | `ser_lib.data.errors` | `RepresentationError` | `RepresentationError` | top-level |
| [ser_lib/data/__init__.py:13](D:/projects/Speech-Emotion-Recognition/ser_lib/data/__init__.py:13) | `ser_lib.data.errors` | `SERDataError` | `SERDataError` | top-level |
| [ser_lib/data/__init__.py:13](D:/projects/Speech-Emotion-Recognition/ser_lib/data/__init__.py:13) | `ser_lib.data.errors` | `TransformError` | `TransformError` | top-level |
| [ser_lib/data/__init__.py:19](D:/projects/Speech-Emotion-Recognition/ser_lib/data/__init__.py:19) | `ser_lib.data.fingerprint` | `DatasetFingerprint` | `DatasetFingerprint` | top-level |
| [ser_lib/data/__init__.py:19](D:/projects/Speech-Emotion-Recognition/ser_lib/data/__init__.py:19) | `ser_lib.data.fingerprint` | `fingerprint_manifest` | `fingerprint_manifest` | top-level |
| [ser_lib/data/__init__.py:20](D:/projects/Speech-Emotion-Recognition/ser_lib/data/__init__.py:20) | `ser_lib.data.history` | `DATASET_REVISION_SCHEMA_VERSION` | `DATASET_REVISION_SCHEMA_VERSION` | top-level |
| [ser_lib/data/__init__.py:20](D:/projects/Speech-Emotion-Recognition/ser_lib/data/__init__.py:20) | `ser_lib.data.history` | `DatasetRevisionCatalog` | `DatasetRevisionCatalog` | top-level |
| [ser_lib/data/__init__.py:20](D:/projects/Speech-Emotion-Recognition/ser_lib/data/__init__.py:20) | `ser_lib.data.history` | `DatasetRevisionInfo` | `DatasetRevisionInfo` | top-level |
| [ser_lib/data/__init__.py:20](D:/projects/Speech-Emotion-Recognition/ser_lib/data/__init__.py:20) | `ser_lib.data.history` | `DatasetRevisionScanFailure` | `DatasetRevisionScanFailure` | top-level |
| [ser_lib/data/__init__.py:20](D:/projects/Speech-Emotion-Recognition/ser_lib/data/__init__.py:20) | `ser_lib.data.history` | `create_dataset_revision` | `create_dataset_revision` | top-level |
| [ser_lib/data/__init__.py:20](D:/projects/Speech-Emotion-Recognition/ser_lib/data/__init__.py:20) | `ser_lib.data.history` | `inspect_dataset_revision` | `inspect_dataset_revision` | top-level |
| [ser_lib/data/__init__.py:20](D:/projects/Speech-Emotion-Recognition/ser_lib/data/__init__.py:20) | `ser_lib.data.history` | `restore_dataset_revision` | `restore_dataset_revision` | top-level |
| [ser_lib/data/__init__.py:20](D:/projects/Speech-Emotion-Recognition/ser_lib/data/__init__.py:20) | `ser_lib.data.history` | `scan_dataset_revisions` | `scan_dataset_revisions` | top-level |
| [ser_lib/data/__init__.py:25](D:/projects/Speech-Emotion-Recognition/ser_lib/data/__init__.py:25) | `ser_lib.data.importers` | `CasiaImporter` | `CasiaImporter` | top-level |
| [ser_lib/data/__init__.py:25](D:/projects/Speech-Emotion-Recognition/ser_lib/data/__init__.py:25) | `ser_lib.data.importers` | `CsvImporter` | `CsvImporter` | top-level |
| [ser_lib/data/__init__.py:25](D:/projects/Speech-Emotion-Recognition/ser_lib/data/__init__.py:25) | `ser_lib.data.importers` | `FolderImporter` | `FolderImporter` | top-level |
| [ser_lib/data/__init__.py:25](D:/projects/Speech-Emotion-Recognition/ser_lib/data/__init__.py:25) | `ser_lib.data.importers` | `ImportPreview` | `ImportPreview` | top-level |
| [ser_lib/data/__init__.py:25](D:/projects/Speech-Emotion-Recognition/ser_lib/data/__init__.py:25) | `ser_lib.data.importers` | `JsonlImporter` | `JsonlImporter` | top-level |
| [ser_lib/data/__init__.py:25](D:/projects/Speech-Emotion-Recognition/ser_lib/data/__init__.py:25) | `ser_lib.data.importers` | `RavdessImporter` | `RavdessImporter` | top-level |
| [ser_lib/data/__init__.py:25](D:/projects/Speech-Emotion-Recognition/ser_lib/data/__init__.py:25) | `ser_lib.data.importers` | `register_importers` | `register_importers` | top-level |
| [ser_lib/data/__init__.py:29](D:/projects/Speech-Emotion-Recognition/ser_lib/data/__init__.py:29) | `ser_lib.data.manifest` | `DatasetManifest` | `DatasetManifest` | top-level |
| [ser_lib/data/__init__.py:29](D:/projects/Speech-Emotion-Recognition/ser_lib/data/__init__.py:29) | `ser_lib.data.manifest` | `ManifestMeta` | `ManifestMeta` | top-level |
| [ser_lib/data/__init__.py:29](D:/projects/Speech-Emotion-Recognition/ser_lib/data/__init__.py:29) | `ser_lib.data.manifest` | `read_jsonl` | `read_jsonl` | top-level |
| [ser_lib/data/__init__.py:29](D:/projects/Speech-Emotion-Recognition/ser_lib/data/__init__.py:29) | `ser_lib.data.manifest` | `write_jsonl` | `write_jsonl` | top-level |
| [ser_lib/data/__init__.py:30](D:/projects/Speech-Emotion-Recognition/ser_lib/data/__init__.py:30) | `ser_lib.data.pipeline` | `SamplePipeline` | `SamplePipeline` | top-level |
| [ser_lib/data/__init__.py:30](D:/projects/Speech-Emotion-Recognition/ser_lib/data/__init__.py:30) | `ser_lib.data.pipeline` | `build_components` | `build_components` | top-level |
| [ser_lib/data/__init__.py:30](D:/projects/Speech-Emotion-Recognition/ser_lib/data/__init__.py:30) | `ser_lib.data.pipeline` | `build_pipeline` | `build_pipeline` | top-level |
| [ser_lib/data/__init__.py:31](D:/projects/Speech-Emotion-Recognition/ser_lib/data/__init__.py:31) | `ser_lib.data.profiling` | `AudioProbeFailure` | `AudioProbeFailure` | top-level |
| [ser_lib/data/__init__.py:31](D:/projects/Speech-Emotion-Recognition/ser_lib/data/__init__.py:31) | `ser_lib.data.profiling` | `DatasetAudioProfile` | `DatasetAudioProfile` | top-level |
| [ser_lib/data/__init__.py:31](D:/projects/Speech-Emotion-Recognition/ser_lib/data/__init__.py:31) | `ser_lib.data.profiling` | `DatasetProfile` | `DatasetProfile` | top-level |
| [ser_lib/data/__init__.py:31](D:/projects/Speech-Emotion-Recognition/ser_lib/data/__init__.py:31) | `ser_lib.data.profiling` | `DatasetSummary` | `DatasetSummary` | top-level |
| [ser_lib/data/__init__.py:31](D:/projects/Speech-Emotion-Recognition/ser_lib/data/__init__.py:31) | `ser_lib.data.profiling` | `DurationHistogramBin` | `DurationHistogramBin` | top-level |
| [ser_lib/data/__init__.py:31](D:/projects/Speech-Emotion-Recognition/ser_lib/data/__init__.py:31) | `ser_lib.data.profiling` | `profile_dataset` | `profile_dataset` | top-level |
| [ser_lib/data/__init__.py:31](D:/projects/Speech-Emotion-Recognition/ser_lib/data/__init__.py:31) | `ser_lib.data.profiling` | `profile_manifest_audio` | `profile_manifest_audio` | top-level |
| [ser_lib/data/__init__.py:31](D:/projects/Speech-Emotion-Recognition/ser_lib/data/__init__.py:31) | `ser_lib.data.profiling` | `summarize_manifest` | `summarize_manifest` | top-level |
| [ser_lib/data/__init__.py:35](D:/projects/Speech-Emotion-Recognition/ser_lib/data/__init__.py:35) | `ser_lib.data.query` | `RecordPage` | `RecordPage` | top-level |
| [ser_lib/data/__init__.py:35](D:/projects/Speech-Emotion-Recognition/ser_lib/data/__init__.py:35) | `ser_lib.data.query` | `RecordView` | `RecordView` | top-level |
| [ser_lib/data/__init__.py:35](D:/projects/Speech-Emotion-Recognition/ser_lib/data/__init__.py:35) | `ser_lib.data.query` | `query_records` | `query_records` | top-level |
| [ser_lib/data/__init__.py:36](D:/projects/Speech-Emotion-Recognition/ser_lib/data/__init__.py:36) | `ser_lib.data.registry` | `ComponentDescriptor` | `ComponentDescriptor` | top-level |
| [ser_lib/data/__init__.py:36](D:/projects/Speech-Emotion-Recognition/ser_lib/data/__init__.py:36) | `ser_lib.data.registry` | `Registry` | `Registry` | top-level |
| [ser_lib/data/__init__.py:36](D:/projects/Speech-Emotion-Recognition/ser_lib/data/__init__.py:36) | `ser_lib.data.registry` | `default_registry` | `default_registry` | top-level |
| [ser_lib/data/__init__.py:37](D:/projects/Speech-Emotion-Recognition/ser_lib/data/__init__.py:37) | `ser_lib.data.representations` | `register_representations` | `register_representations` | top-level |
| [ser_lib/data/__init__.py:38](D:/projects/Speech-Emotion-Recognition/ser_lib/data/__init__.py:38) | `ser_lib.data.transforms` | `register_transforms` | `register_transforms` | top-level |
| [ser_lib/data/__init__.py:39](D:/projects/Speech-Emotion-Recognition/ser_lib/data/__init__.py:39) | `ser_lib.data.types` | `AudioData` | `AudioData` | top-level |
| [ser_lib/data/__init__.py:39](D:/projects/Speech-Emotion-Recognition/ser_lib/data/__init__.py:39) | `ser_lib.data.types` | `AudioRecord` | `AudioRecord` | top-level |
| [ser_lib/data/__init__.py:39](D:/projects/Speech-Emotion-Recognition/ser_lib/data/__init__.py:39) | `ser_lib.data.types` | `RepresentationOutput` | `RepresentationOutput` | top-level |
| [ser_lib/data/__init__.py:39](D:/projects/Speech-Emotion-Recognition/ser_lib/data/__init__.py:39) | `ser_lib.data.types` | `SERBatch` | `SERBatch` | top-level |
| [ser_lib/data/__init__.py:39](D:/projects/Speech-Emotion-Recognition/ser_lib/data/__init__.py:39) | `ser_lib.data.types` | `SERSample` | `SERSample` | top-level |
| [ser_lib/data/__init__.py:39](D:/projects/Speech-Emotion-Recognition/ser_lib/data/__init__.py:39) | `ser_lib.data.types` | `TensorSpec` | `TensorSpec` | top-level |
| [ser_lib/data/__init__.py:39](D:/projects/Speech-Emotion-Recognition/ser_lib/data/__init__.py:39) | `ser_lib.data.types` | `validate_sample_contract` | `validate_sample_contract` | top-level |
| [ser_lib/data/__init__.py:43](D:/projects/Speech-Emotion-Recognition/ser_lib/data/__init__.py:43) | `ser_lib.data.validation` | `CompatibilityReport` | `CompatibilityReport` | top-level |
| [ser_lib/data/__init__.py:43](D:/projects/Speech-Emotion-Recognition/ser_lib/data/__init__.py:43) | `ser_lib.data.validation` | `ModelSpec` | `ModelSpec` | top-level |
| [ser_lib/data/__init__.py:43](D:/projects/Speech-Emotion-Recognition/ser_lib/data/__init__.py:43) | `ser_lib.data.validation` | `inspect_compatibility` | `inspect_compatibility` | top-level |
| [ser_lib/data/__init__.py:43](D:/projects/Speech-Emotion-Recognition/ser_lib/data/__init__.py:43) | `ser_lib.data.validation` | `validate_compatibility` | `validate_compatibility` | top-level |
| [ser_lib/data/audio.py:27](D:/projects/Speech-Emotion-Recognition/ser_lib/data/audio.py:27) | `ser_lib.data.errors` | `AudioDecodeError` | `AudioDecodeError` | top-level |
| [ser_lib/data/audio.py:27](D:/projects/Speech-Emotion-Recognition/ser_lib/data/audio.py:27) | `ser_lib.data.errors` | `AudioNotFoundError` | `AudioNotFoundError` | top-level |
| [ser_lib/data/audio.py:27](D:/projects/Speech-Emotion-Recognition/ser_lib/data/audio.py:27) | `ser_lib.data.errors` | `InvalidAudioSegmentError` | `InvalidAudioSegmentError` | top-level |
| [ser_lib/data/audio.py:27](D:/projects/Speech-Emotion-Recognition/ser_lib/data/audio.py:27) | `ser_lib.data.errors` | `SERDataError` | `SERDataError` | top-level |
| [ser_lib/data/audio.py:33](D:/projects/Speech-Emotion-Recognition/ser_lib/data/audio.py:33) | `ser_lib.data.types` | `AudioData` | `AudioData` | top-level |
| [ser_lib/data/audio.py:33](D:/projects/Speech-Emotion-Recognition/ser_lib/data/audio.py:33) | `ser_lib.data.types` | `AudioRecord` | `AudioRecord` | top-level |
| [ser_lib/data/cache.py:11](D:/projects/Speech-Emotion-Recognition/ser_lib/data/cache.py:11) | `ser_lib.data.registry` | `ComponentDescriptor` | `ComponentDescriptor` | top-level |
| [ser_lib/data/cache.py:12](D:/projects/Speech-Emotion-Recognition/ser_lib/data/cache.py:12) | `ser_lib.data.representations.base` | `Representation` | `Representation` | top-level |
| [ser_lib/data/cache.py:13](D:/projects/Speech-Emotion-Recognition/ser_lib/data/cache.py:13) | `ser_lib.data.types` | `AudioData` | `AudioData` | top-level |
| [ser_lib/data/cache.py:13](D:/projects/Speech-Emotion-Recognition/ser_lib/data/cache.py:13) | `ser_lib.data.types` | `RepresentationOutput` | `RepresentationOutput` | top-level |
| [ser_lib/data/cache.py:13](D:/projects/Speech-Emotion-Recognition/ser_lib/data/cache.py:13) | `ser_lib.data.types` | `TensorSpec` | `TensorSpec` | top-level |
| [ser_lib/data/cache.py:13](D:/projects/Speech-Emotion-Recognition/ser_lib/data/cache.py:13) | `ser_lib.data.types` | `validate_representation_output` | `validate_representation_output` | top-level |
| [ser_lib/data/collate.py:25](D:/projects/Speech-Emotion-Recognition/ser_lib/data/collate.py:25) | `ser_lib.data.config` | `BatchingConfig` | `BatchingConfig` | top-level |
| [ser_lib/data/collate.py:26](D:/projects/Speech-Emotion-Recognition/ser_lib/data/collate.py:26) | `ser_lib.data.errors` | `CollationError` | `CollationError` | top-level |
| [ser_lib/data/collate.py:27](D:/projects/Speech-Emotion-Recognition/ser_lib/data/collate.py:27) | `ser_lib.data.types` | `LAYOUT_TD` | `LAYOUT_TD` | top-level |
| [ser_lib/data/collate.py:27](D:/projects/Speech-Emotion-Recognition/ser_lib/data/collate.py:27) | `ser_lib.data.types` | `SERBatch` | `SERBatch` | top-level |
| [ser_lib/data/collate.py:27](D:/projects/Speech-Emotion-Recognition/ser_lib/data/collate.py:27) | `ser_lib.data.types` | `SERSample` | `SERSample` | top-level |
| [ser_lib/data/collate.py:27](D:/projects/Speech-Emotion-Recognition/ser_lib/data/collate.py:27) | `ser_lib.data.types` | `TensorSpec` | `TensorSpec` | top-level |
| [ser_lib/data/collate.py:27](D:/projects/Speech-Emotion-Recognition/ser_lib/data/collate.py:27) | `ser_lib.data.types` | `time_axis_of` | `time_axis_of` | top-level |
| [ser_lib/data/config.py:15](D:/projects/Speech-Emotion-Recognition/ser_lib/data/config.py:15) | `ser_lib.core.config` | `StrictConfig` | `StrictConfig` | top-level |
| [ser_lib/data/dataset.py:16](D:/projects/Speech-Emotion-Recognition/ser_lib/data/dataset.py:16) | `ser_lib.data.audio` | `AudioLoader` | `AudioLoader` | top-level |
| [ser_lib/data/dataset.py:17](D:/projects/Speech-Emotion-Recognition/ser_lib/data/dataset.py:17) | `ser_lib.data.errors` | `SERDataError` | `SERDataError` | top-level |
| [ser_lib/data/dataset.py:18](D:/projects/Speech-Emotion-Recognition/ser_lib/data/dataset.py:18) | `ser_lib.data.pipeline` | `SamplePipeline` | `SamplePipeline` | top-level |
| [ser_lib/data/dataset.py:19](D:/projects/Speech-Emotion-Recognition/ser_lib/data/dataset.py:19) | `ser_lib.data.types` | `AudioRecord` | `AudioRecord` | top-level |
| [ser_lib/data/dataset.py:19](D:/projects/Speech-Emotion-Recognition/ser_lib/data/dataset.py:19) | `ser_lib.data.types` | `SERSample` | `SERSample` | top-level |
| [ser_lib/data/editor.py:15](D:/projects/Speech-Emotion-Recognition/ser_lib/data/editor.py:15) | `ser_lib.data.errors` | `DatasetEditConflictError` | `DatasetEditConflictError` | top-level |
| [ser_lib/data/editor.py:15](D:/projects/Speech-Emotion-Recognition/ser_lib/data/editor.py:15) | `ser_lib.data.errors` | `DatasetEditError` | `DatasetEditError` | top-level |
| [ser_lib/data/editor.py:15](D:/projects/Speech-Emotion-Recognition/ser_lib/data/editor.py:15) | `ser_lib.data.errors` | `DatasetTransactionError` | `DatasetTransactionError` | top-level |
| [ser_lib/data/editor.py:20](D:/projects/Speech-Emotion-Recognition/ser_lib/data/editor.py:20) | `ser_lib.data.fingerprint` | `fingerprint_manifest` | `fingerprint_manifest` | top-level |
| [ser_lib/data/editor.py:21](D:/projects/Speech-Emotion-Recognition/ser_lib/data/editor.py:21) | `ser_lib.data.manifest` | `DatasetManifest` | `DatasetManifest` | top-level |
| [ser_lib/data/editor.py:21](D:/projects/Speech-Emotion-Recognition/ser_lib/data/editor.py:21) | `ser_lib.data.manifest` | `write_jsonl` | `write_jsonl` | top-level |
| [ser_lib/data/editor.py:22](D:/projects/Speech-Emotion-Recognition/ser_lib/data/editor.py:22) | `ser_lib.data.types` | `AudioRecord` | `AudioRecord` | top-level |
| [ser_lib/data/errors.py:27](D:/projects/Speech-Emotion-Recognition/ser_lib/data/errors.py:27) | `ser_lib.core.exceptions` | `SERError` | `SERError` | top-level |
| [ser_lib/data/fingerprint.py:10](D:/projects/Speech-Emotion-Recognition/ser_lib/data/fingerprint.py:10) | `ser_lib.core.events` | `CancellationCheck` | `CancellationCheck` | top-level |
| [ser_lib/data/fingerprint.py:10](D:/projects/Speech-Emotion-Recognition/ser_lib/data/fingerprint.py:10) | `ser_lib.core.events` | `EventCallback` | `EventCallback` | top-level |
| [ser_lib/data/fingerprint.py:10](D:/projects/Speech-Emotion-Recognition/ser_lib/data/fingerprint.py:10) | `ser_lib.core.events` | `ProgressEvent` | `ProgressEvent` | top-level |
| [ser_lib/data/fingerprint.py:11](D:/projects/Speech-Emotion-Recognition/ser_lib/data/fingerprint.py:11) | `ser_lib.data.manifest` | `DatasetManifest` | `DatasetManifest` | top-level |
| [ser_lib/data/history.py:20](D:/projects/Speech-Emotion-Recognition/ser_lib/data/history.py:20) | `ser_lib.core._catalog_scan` | `scan_catalog_candidates` | `scan_catalog_candidates` | top-level |
| [ser_lib/data/history.py:21](D:/projects/Speech-Emotion-Recognition/ser_lib/data/history.py:21) | `ser_lib.core.events` | `CancellationCheck` | `CancellationCheck` | top-level |
| [ser_lib/data/history.py:21](D:/projects/Speech-Emotion-Recognition/ser_lib/data/history.py:21) | `ser_lib.core.events` | `EventCallback` | `EventCallback` | top-level |
| [ser_lib/data/history.py:21](D:/projects/Speech-Emotion-Recognition/ser_lib/data/history.py:21) | `ser_lib.core.events` | `ProgressEvent` | `ProgressEvent` | top-level |
| [ser_lib/data/history.py:22](D:/projects/Speech-Emotion-Recognition/ser_lib/data/history.py:22) | `ser_lib.core.migrations` | `migrate_schema_payload` | `migrate_schema_payload` | top-level |
| [ser_lib/data/history.py:23](D:/projects/Speech-Emotion-Recognition/ser_lib/data/history.py:23) | `ser_lib.data.errors` | `DatasetEditConflictError` | `DatasetEditConflictError` | top-level |
| [ser_lib/data/history.py:23](D:/projects/Speech-Emotion-Recognition/ser_lib/data/history.py:23) | `ser_lib.data.errors` | `DatasetTransactionError` | `DatasetTransactionError` | top-level |
| [ser_lib/data/history.py:24](D:/projects/Speech-Emotion-Recognition/ser_lib/data/history.py:24) | `ser_lib.data.fingerprint` | `fingerprint_manifest` | `fingerprint_manifest` | top-level |
| [ser_lib/data/history.py:25](D:/projects/Speech-Emotion-Recognition/ser_lib/data/history.py:25) | `ser_lib.data.manifest` | `DatasetManifest` | `DatasetManifest` | top-level |
| [ser_lib/data/importers/__init__.py:5](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/__init__.py:5) | `ser_lib.data.importers.base` | `DatasetImporter` | `DatasetImporter` | top-level |
| [ser_lib/data/importers/__init__.py:5](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/__init__.py:5) | `ser_lib.data.importers.base` | `ImportPreview` | `ImportPreview` | top-level |
| [ser_lib/data/importers/__init__.py:6](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/__init__.py:6) | `ser_lib.data.importers.casia` | `CasiaImportConfig` | `CasiaImportConfig` | top-level |
| [ser_lib/data/importers/__init__.py:6](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/__init__.py:6) | `ser_lib.data.importers.casia` | `CasiaImporter` | `CasiaImporter` | top-level |
| [ser_lib/data/importers/__init__.py:7](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/__init__.py:7) | `ser_lib.data.importers.csv_importer` | `CsvImportConfig` | `CsvImportConfig` | top-level |
| [ser_lib/data/importers/__init__.py:7](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/__init__.py:7) | `ser_lib.data.importers.csv_importer` | `CsvImporter` | `CsvImporter` | top-level |
| [ser_lib/data/importers/__init__.py:8](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/__init__.py:8) | `ser_lib.data.importers.csemotions` | `CsemotionsImportConfig` | `CsemotionsImportConfig` | top-level |
| [ser_lib/data/importers/__init__.py:8](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/__init__.py:8) | `ser_lib.data.importers.csemotions` | `CsemotionsImporter` | `CsemotionsImporter` | top-level |
| [ser_lib/data/importers/__init__.py:9](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/__init__.py:9) | `ser_lib.data.importers.crema_d` | `CremaDImportConfig` | `CremaDImportConfig` | top-level |
| [ser_lib/data/importers/__init__.py:9](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/__init__.py:9) | `ser_lib.data.importers.crema_d` | `CremaDImporter` | `CremaDImporter` | top-level |
| [ser_lib/data/importers/__init__.py:10](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/__init__.py:10) | `ser_lib.data.importers.esd` | `EsdImportConfig` | `EsdImportConfig` | top-level |
| [ser_lib/data/importers/__init__.py:10](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/__init__.py:10) | `ser_lib.data.importers.esd` | `EsdImporter` | `EsdImporter` | top-level |
| [ser_lib/data/importers/__init__.py:11](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/__init__.py:11) | `ser_lib.data.importers.emotiontalk` | `EmotionTalkImportConfig` | `EmotionTalkImportConfig` | top-level |
| [ser_lib/data/importers/__init__.py:11](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/__init__.py:11) | `ser_lib.data.importers.emotiontalk` | `EmotionTalkImporter` | `EmotionTalkImporter` | top-level |
| [ser_lib/data/importers/__init__.py:12](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/__init__.py:12) | `ser_lib.data.importers.folder` | `FolderImportConfig` | `FolderImportConfig` | top-level |
| [ser_lib/data/importers/__init__.py:12](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/__init__.py:12) | `ser_lib.data.importers.folder` | `FolderImporter` | `FolderImporter` | top-level |
| [ser_lib/data/importers/__init__.py:13](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/__init__.py:13) | `ser_lib.data.importers.jsonl_importer` | `JsonlImportConfig` | `JsonlImportConfig` | top-level |
| [ser_lib/data/importers/__init__.py:13](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/__init__.py:13) | `ser_lib.data.importers.jsonl_importer` | `JsonlImporter` | `JsonlImporter` | top-level |
| [ser_lib/data/importers/__init__.py:13](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/__init__.py:13) | `ser_lib.data.importers.jsonl_importer` | `normalize_raw_record` | `normalize_raw_record` | top-level |
| [ser_lib/data/importers/__init__.py:13](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/__init__.py:13) | `ser_lib.data.importers.jsonl_importer` | `normalize_raw_records` | `normalize_raw_records` | top-level |
| [ser_lib/data/importers/__init__.py:14](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/__init__.py:14) | `ser_lib.data.importers.ravdess` | `RavdessImportConfig` | `RavdessImportConfig` | top-level |
| [ser_lib/data/importers/__init__.py:14](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/__init__.py:14) | `ser_lib.data.importers.ravdess` | `RavdessImporter` | `RavdessImporter` | top-level |
| [ser_lib/data/importers/__init__.py:15](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/__init__.py:15) | `ser_lib.data.registry` | `default_registry` | `default_registry` | top-level |
| [ser_lib/data/importers/_conversion.py:11](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/_conversion.py:11) | `ser_lib.core.events` | `CancellationCheck` | `CancellationCheck` | top-level |
| [ser_lib/data/importers/_conversion.py:11](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/_conversion.py:11) | `ser_lib.core.events` | `EventCallback` | `EventCallback` | top-level |
| [ser_lib/data/importers/_conversion.py:11](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/_conversion.py:11) | `ser_lib.core.events` | `EventContext` | `EventContext` | top-level |
| [ser_lib/data/importers/_conversion.py:12](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/_conversion.py:12) | `ser_lib.data.importers.base` | `ImportPreview` | `ImportPreview` | top-level |
| [ser_lib/data/importers/_conversion.py:12](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/_conversion.py:12) | `ser_lib.data.importers.base` | `ImportTask` | `ImportTask` | top-level |
| [ser_lib/data/importers/_conversion.py:13](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/_conversion.py:13) | `ser_lib.data.manifest` | `DatasetManifest` | `DatasetManifest` | top-level |
| [ser_lib/data/importers/_conversion.py:13](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/_conversion.py:13) | `ser_lib.data.manifest` | `ManifestMeta` | `ManifestMeta` | top-level |
| [ser_lib/data/importers/_conversion.py:13](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/_conversion.py:13) | `ser_lib.data.manifest` | `write_jsonl` | `write_jsonl` | top-level |
| [ser_lib/data/importers/_conversion.py:14](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/_conversion.py:14) | `ser_lib.data.types` | `AudioRecord` | `AudioRecord` | top-level |
| [ser_lib/data/importers/base.py:15](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/base.py:15) | `ser_lib.core.diagnostics` | `Diagnostic` | `Diagnostic` | top-level |
| [ser_lib/data/importers/base.py:16](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/base.py:16) | `ser_lib.core.events` | `CancellationCheck` | `CancellationCheck` | top-level |
| [ser_lib/data/importers/base.py:16](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/base.py:16) | `ser_lib.core.events` | `EventCallback` | `EventCallback` | top-level |
| [ser_lib/data/importers/base.py:16](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/base.py:16) | `ser_lib.core.events` | `EventContext` | `EventContext` | top-level |
| [ser_lib/data/importers/base.py:16](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/base.py:16) | `ser_lib.core.events` | `LifecycleEvent` | `LifecycleEvent` | top-level |
| [ser_lib/data/importers/base.py:16](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/base.py:16) | `ser_lib.core.events` | `ProgressEvent` | `ProgressEvent` | top-level |
| [ser_lib/data/importers/base.py:23](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/base.py:23) | `ser_lib.core.exceptions` | `OperationCancelled` | `OperationCancelled` | top-level |
| [ser_lib/data/importers/base.py:24](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/base.py:24) | `ser_lib.data.manifest` | `DatasetManifest` | `DatasetManifest` | top-level |
| [ser_lib/data/importers/base.py:25](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/base.py:25) | `ser_lib.data.registry` | `ComponentDescriptor` | `ComponentDescriptor` | top-level |
| [ser_lib/data/importers/base.py:26](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/base.py:26) | `ser_lib.data.types` | `AudioRecord` | `AudioRecord` | top-level |
| [ser_lib/data/importers/casia.py:10](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/casia.py:10) | `ser_lib.core.diagnostics` | `Diagnostic` | `Diagnostic` | top-level |
| [ser_lib/data/importers/casia.py:11](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/casia.py:11) | `ser_lib.core.events` | `CancellationCheck` | `CancellationCheck` | top-level |
| [ser_lib/data/importers/casia.py:11](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/casia.py:11) | `ser_lib.core.events` | `EventCallback` | `EventCallback` | top-level |
| [ser_lib/data/importers/casia.py:11](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/casia.py:11) | `ser_lib.core.events` | `EventContext` | `EventContext` | top-level |
| [ser_lib/data/importers/casia.py:12](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/casia.py:12) | `ser_lib.data.importers._conversion` | `run_single_manifest_conversion` | `run_single_manifest_conversion` | top-level |
| [ser_lib/data/importers/casia.py:13](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/casia.py:13) | `ser_lib.data.importers.base` | `ImportPreview` | `ImportPreview` | top-level |
| [ser_lib/data/importers/casia.py:13](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/casia.py:13) | `ser_lib.data.importers.base` | `ImportTask` | `ImportTask` | top-level |
| [ser_lib/data/importers/casia.py:14](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/casia.py:14) | `ser_lib.data.importers.folder` | `DEFAULT_AUDIO_EXTENSIONS` | `DEFAULT_AUDIO_EXTENSIONS` | top-level |
| [ser_lib/data/importers/casia.py:15](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/casia.py:15) | `ser_lib.data.manifest` | `DatasetManifest` | `DatasetManifest` | top-level |
| [ser_lib/data/importers/casia.py:16](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/casia.py:16) | `ser_lib.data.registry` | `ComponentDescriptor` | `ComponentDescriptor` | top-level |
| [ser_lib/data/importers/casia.py:17](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/casia.py:17) | `ser_lib.data.types` | `AudioRecord` | `AudioRecord` | top-level |
| [ser_lib/data/importers/crema_d.py:11](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/crema_d.py:11) | `ser_lib.core.diagnostics` | `Diagnostic` | `Diagnostic` | top-level |
| [ser_lib/data/importers/crema_d.py:12](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/crema_d.py:12) | `ser_lib.core.events` | `CancellationCheck` | `CancellationCheck` | top-level |
| [ser_lib/data/importers/crema_d.py:12](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/crema_d.py:12) | `ser_lib.core.events` | `EventCallback` | `EventCallback` | top-level |
| [ser_lib/data/importers/crema_d.py:12](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/crema_d.py:12) | `ser_lib.core.events` | `EventContext` | `EventContext` | top-level |
| [ser_lib/data/importers/crema_d.py:13](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/crema_d.py:13) | `ser_lib.data.importers._conversion` | `run_manifest_conversion` | `run_manifest_conversion` | top-level |
| [ser_lib/data/importers/crema_d.py:13](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/crema_d.py:13) | `ser_lib.data.importers._conversion` | `write_partitioned_manifest` | `write_partitioned_manifest` | top-level |
| [ser_lib/data/importers/crema_d.py:14](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/crema_d.py:14) | `ser_lib.data.importers.base` | `ImportPreview` | `ImportPreview` | top-level |
| [ser_lib/data/importers/crema_d.py:14](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/crema_d.py:14) | `ser_lib.data.importers.base` | `ImportTask` | `ImportTask` | top-level |
| [ser_lib/data/importers/crema_d.py:15](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/crema_d.py:15) | `ser_lib.data.importers.csemotions` | `_automatic_speaker_splits` | `_automatic_speaker_splits` | top-level |
| [ser_lib/data/importers/crema_d.py:15](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/crema_d.py:15) | `ser_lib.data.importers.csemotions` | `_validate_speaker_splits` | `_validate_speaker_splits` | top-level |
| [ser_lib/data/importers/crema_d.py:16](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/crema_d.py:16) | `ser_lib.data.manifest` | `DatasetManifest` | `DatasetManifest` | top-level |
| [ser_lib/data/importers/crema_d.py:17](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/crema_d.py:17) | `ser_lib.data.registry` | `ComponentDescriptor` | `ComponentDescriptor` | top-level |
| [ser_lib/data/importers/crema_d.py:18](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/crema_d.py:18) | `ser_lib.data.types` | `AudioRecord` | `AudioRecord` | top-level |
| [ser_lib/data/importers/csemotions.py:11](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/csemotions.py:11) | `ser_lib.core.diagnostics` | `Diagnostic` | `Diagnostic` | top-level |
| [ser_lib/data/importers/csemotions.py:12](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/csemotions.py:12) | `ser_lib.core.events` | `CancellationCheck` | `CancellationCheck` | top-level |
| [ser_lib/data/importers/csemotions.py:12](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/csemotions.py:12) | `ser_lib.core.events` | `EventCallback` | `EventCallback` | top-level |
| [ser_lib/data/importers/csemotions.py:12](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/csemotions.py:12) | `ser_lib.core.events` | `EventContext` | `EventContext` | top-level |
| [ser_lib/data/importers/csemotions.py:13](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/csemotions.py:13) | `ser_lib.data.importers._conversion` | `run_manifest_conversion` | `run_manifest_conversion` | top-level |
| [ser_lib/data/importers/csemotions.py:13](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/csemotions.py:13) | `ser_lib.data.importers._conversion` | `write_partitioned_manifest` | `write_partitioned_manifest` | top-level |
| [ser_lib/data/importers/csemotions.py:14](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/csemotions.py:14) | `ser_lib.data.importers.base` | `ImportPreview` | `ImportPreview` | top-level |
| [ser_lib/data/importers/csemotions.py:14](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/csemotions.py:14) | `ser_lib.data.importers.base` | `ImportTask` | `ImportTask` | top-level |
| [ser_lib/data/importers/csemotions.py:15](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/csemotions.py:15) | `ser_lib.data.manifest` | `DatasetManifest` | `DatasetManifest` | top-level |
| [ser_lib/data/importers/csemotions.py:16](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/csemotions.py:16) | `ser_lib.data.registry` | `ComponentDescriptor` | `ComponentDescriptor` | top-level |
| [ser_lib/data/importers/csemotions.py:17](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/csemotions.py:17) | `ser_lib.data.types` | `AudioRecord` | `AudioRecord` | top-level |
| [ser_lib/data/importers/csv_importer.py:11](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/csv_importer.py:11) | `ser_lib.core.diagnostics` | `Diagnostic` | `Diagnostic` | top-level |
| [ser_lib/data/importers/csv_importer.py:12](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/csv_importer.py:12) | `ser_lib.core.events` | `CancellationCheck` | `CancellationCheck` | top-level |
| [ser_lib/data/importers/csv_importer.py:12](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/csv_importer.py:12) | `ser_lib.core.events` | `EventCallback` | `EventCallback` | top-level |
| [ser_lib/data/importers/csv_importer.py:12](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/csv_importer.py:12) | `ser_lib.core.events` | `EventContext` | `EventContext` | top-level |
| [ser_lib/data/importers/csv_importer.py:13](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/csv_importer.py:13) | `ser_lib.data.importers._conversion` | `run_single_manifest_conversion` | `run_single_manifest_conversion` | top-level |
| [ser_lib/data/importers/csv_importer.py:14](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/csv_importer.py:14) | `ser_lib.data.importers.base` | `ImportPreview` | `ImportPreview` | top-level |
| [ser_lib/data/importers/csv_importer.py:14](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/csv_importer.py:14) | `ser_lib.data.importers.base` | `ImportTask` | `ImportTask` | top-level |
| [ser_lib/data/importers/csv_importer.py:15](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/csv_importer.py:15) | `ser_lib.data.manifest` | `DatasetManifest` | `DatasetManifest` | top-level |
| [ser_lib/data/importers/csv_importer.py:16](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/csv_importer.py:16) | `ser_lib.data.registry` | `ComponentDescriptor` | `ComponentDescriptor` | top-level |
| [ser_lib/data/importers/csv_importer.py:17](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/csv_importer.py:17) | `ser_lib.data.types` | `AudioRecord` | `AudioRecord` | top-level |
| [ser_lib/data/importers/emotiontalk.py:11](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/emotiontalk.py:11) | `ser_lib.core.diagnostics` | `Diagnostic` | `Diagnostic` | top-level |
| [ser_lib/data/importers/emotiontalk.py:12](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/emotiontalk.py:12) | `ser_lib.core.events` | `CancellationCheck` | `CancellationCheck` | top-level |
| [ser_lib/data/importers/emotiontalk.py:12](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/emotiontalk.py:12) | `ser_lib.core.events` | `EventCallback` | `EventCallback` | top-level |
| [ser_lib/data/importers/emotiontalk.py:12](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/emotiontalk.py:12) | `ser_lib.core.events` | `EventContext` | `EventContext` | top-level |
| [ser_lib/data/importers/emotiontalk.py:13](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/emotiontalk.py:13) | `ser_lib.data.importers._conversion` | `run_manifest_conversion` | `run_manifest_conversion` | top-level |
| [ser_lib/data/importers/emotiontalk.py:13](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/emotiontalk.py:13) | `ser_lib.data.importers._conversion` | `write_partitioned_manifest` | `write_partitioned_manifest` | top-level |
| [ser_lib/data/importers/emotiontalk.py:14](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/emotiontalk.py:14) | `ser_lib.data.importers.base` | `ImportPreview` | `ImportPreview` | top-level |
| [ser_lib/data/importers/emotiontalk.py:14](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/emotiontalk.py:14) | `ser_lib.data.importers.base` | `ImportTask` | `ImportTask` | top-level |
| [ser_lib/data/importers/emotiontalk.py:15](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/emotiontalk.py:15) | `ser_lib.data.importers.csemotions` | `_validate_speaker_splits` | `_validate_speaker_splits` | top-level |
| [ser_lib/data/importers/emotiontalk.py:16](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/emotiontalk.py:16) | `ser_lib.data.manifest` | `DatasetManifest` | `DatasetManifest` | top-level |
| [ser_lib/data/importers/emotiontalk.py:17](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/emotiontalk.py:17) | `ser_lib.data.registry` | `ComponentDescriptor` | `ComponentDescriptor` | top-level |
| [ser_lib/data/importers/emotiontalk.py:18](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/emotiontalk.py:18) | `ser_lib.data.types` | `AudioRecord` | `AudioRecord` | top-level |
| [ser_lib/data/importers/esd.py:10](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/esd.py:10) | `ser_lib.core.diagnostics` | `Diagnostic` | `Diagnostic` | top-level |
| [ser_lib/data/importers/esd.py:11](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/esd.py:11) | `ser_lib.core.events` | `CancellationCheck` | `CancellationCheck` | top-level |
| [ser_lib/data/importers/esd.py:11](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/esd.py:11) | `ser_lib.core.events` | `EventCallback` | `EventCallback` | top-level |
| [ser_lib/data/importers/esd.py:11](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/esd.py:11) | `ser_lib.core.events` | `EventContext` | `EventContext` | top-level |
| [ser_lib/data/importers/esd.py:12](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/esd.py:12) | `ser_lib.data.importers._conversion` | `run_manifest_conversion` | `run_manifest_conversion` | top-level |
| [ser_lib/data/importers/esd.py:12](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/esd.py:12) | `ser_lib.data.importers._conversion` | `write_partitioned_manifest` | `write_partitioned_manifest` | top-level |
| [ser_lib/data/importers/esd.py:13](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/esd.py:13) | `ser_lib.data.importers.base` | `ImportPreview` | `ImportPreview` | top-level |
| [ser_lib/data/importers/esd.py:13](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/esd.py:13) | `ser_lib.data.importers.base` | `ImportTask` | `ImportTask` | top-level |
| [ser_lib/data/importers/esd.py:14](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/esd.py:14) | `ser_lib.data.importers.csemotions` | `_automatic_speaker_splits` | `_automatic_speaker_splits` | top-level |
| [ser_lib/data/importers/esd.py:14](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/esd.py:14) | `ser_lib.data.importers.csemotions` | `_validate_speaker_splits` | `_validate_speaker_splits` | top-level |
| [ser_lib/data/importers/esd.py:15](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/esd.py:15) | `ser_lib.data.manifest` | `DatasetManifest` | `DatasetManifest` | top-level |
| [ser_lib/data/importers/esd.py:16](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/esd.py:16) | `ser_lib.data.registry` | `ComponentDescriptor` | `ComponentDescriptor` | top-level |
| [ser_lib/data/importers/esd.py:17](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/esd.py:17) | `ser_lib.data.types` | `AudioRecord` | `AudioRecord` | top-level |
| [ser_lib/data/importers/folder.py:10](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/folder.py:10) | `ser_lib.core.diagnostics` | `Diagnostic` | `Diagnostic` | top-level |
| [ser_lib/data/importers/folder.py:11](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/folder.py:11) | `ser_lib.core.events` | `CancellationCheck` | `CancellationCheck` | top-level |
| [ser_lib/data/importers/folder.py:11](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/folder.py:11) | `ser_lib.core.events` | `EventCallback` | `EventCallback` | top-level |
| [ser_lib/data/importers/folder.py:11](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/folder.py:11) | `ser_lib.core.events` | `EventContext` | `EventContext` | top-level |
| [ser_lib/data/importers/folder.py:12](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/folder.py:12) | `ser_lib.data.importers._conversion` | `run_single_manifest_conversion` | `run_single_manifest_conversion` | top-level |
| [ser_lib/data/importers/folder.py:13](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/folder.py:13) | `ser_lib.data.importers.base` | `ImportPreview` | `ImportPreview` | top-level |
| [ser_lib/data/importers/folder.py:13](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/folder.py:13) | `ser_lib.data.importers.base` | `ImportTask` | `ImportTask` | top-level |
| [ser_lib/data/importers/folder.py:14](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/folder.py:14) | `ser_lib.data.manifest` | `DatasetManifest` | `DatasetManifest` | top-level |
| [ser_lib/data/importers/folder.py:15](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/folder.py:15) | `ser_lib.data.registry` | `ComponentDescriptor` | `ComponentDescriptor` | top-level |
| [ser_lib/data/importers/folder.py:16](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/folder.py:16) | `ser_lib.data.types` | `AudioRecord` | `AudioRecord` | top-level |
| [ser_lib/data/importers/jsonl_importer.py:11](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/jsonl_importer.py:11) | `ser_lib.core.diagnostics` | `Diagnostic` | `Diagnostic` | top-level |
| [ser_lib/data/importers/jsonl_importer.py:12](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/jsonl_importer.py:12) | `ser_lib.core.events` | `CancellationCheck` | `CancellationCheck` | top-level |
| [ser_lib/data/importers/jsonl_importer.py:12](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/jsonl_importer.py:12) | `ser_lib.core.events` | `EventCallback` | `EventCallback` | top-level |
| [ser_lib/data/importers/jsonl_importer.py:12](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/jsonl_importer.py:12) | `ser_lib.core.events` | `EventContext` | `EventContext` | top-level |
| [ser_lib/data/importers/jsonl_importer.py:13](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/jsonl_importer.py:13) | `ser_lib.data.errors` | `ManifestError` | `ManifestError` | top-level |
| [ser_lib/data/importers/jsonl_importer.py:14](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/jsonl_importer.py:14) | `ser_lib.data.importers._conversion` | `run_single_manifest_conversion` | `run_single_manifest_conversion` | top-level |
| [ser_lib/data/importers/jsonl_importer.py:15](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/jsonl_importer.py:15) | `ser_lib.data.importers.base` | `ImportPreview` | `ImportPreview` | top-level |
| [ser_lib/data/importers/jsonl_importer.py:15](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/jsonl_importer.py:15) | `ser_lib.data.importers.base` | `ImportTask` | `ImportTask` | top-level |
| [ser_lib/data/importers/jsonl_importer.py:16](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/jsonl_importer.py:16) | `ser_lib.data.manifest` | `DatasetManifest` | `DatasetManifest` | top-level |
| [ser_lib/data/importers/jsonl_importer.py:16](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/jsonl_importer.py:16) | `ser_lib.data.manifest` | `parse_record` | `parse_record` | top-level |
| [ser_lib/data/importers/jsonl_importer.py:17](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/jsonl_importer.py:17) | `ser_lib.data.registry` | `ComponentDescriptor` | `ComponentDescriptor` | top-level |
| [ser_lib/data/importers/jsonl_importer.py:18](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/jsonl_importer.py:18) | `ser_lib.data.types` | `AudioRecord` | `AudioRecord` | top-level |
| [ser_lib/data/importers/ravdess.py:10](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/ravdess.py:10) | `ser_lib.core.diagnostics` | `Diagnostic` | `Diagnostic` | top-level |
| [ser_lib/data/importers/ravdess.py:11](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/ravdess.py:11) | `ser_lib.core.events` | `CancellationCheck` | `CancellationCheck` | top-level |
| [ser_lib/data/importers/ravdess.py:11](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/ravdess.py:11) | `ser_lib.core.events` | `EventCallback` | `EventCallback` | top-level |
| [ser_lib/data/importers/ravdess.py:11](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/ravdess.py:11) | `ser_lib.core.events` | `EventContext` | `EventContext` | top-level |
| [ser_lib/data/importers/ravdess.py:12](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/ravdess.py:12) | `ser_lib.data.importers._conversion` | `run_single_manifest_conversion` | `run_single_manifest_conversion` | top-level |
| [ser_lib/data/importers/ravdess.py:13](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/ravdess.py:13) | `ser_lib.data.importers.base` | `ImportPreview` | `ImportPreview` | top-level |
| [ser_lib/data/importers/ravdess.py:13](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/ravdess.py:13) | `ser_lib.data.importers.base` | `ImportTask` | `ImportTask` | top-level |
| [ser_lib/data/importers/ravdess.py:14](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/ravdess.py:14) | `ser_lib.data.manifest` | `DatasetManifest` | `DatasetManifest` | top-level |
| [ser_lib/data/importers/ravdess.py:15](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/ravdess.py:15) | `ser_lib.data.registry` | `ComponentDescriptor` | `ComponentDescriptor` | top-level |
| [ser_lib/data/importers/ravdess.py:16](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/ravdess.py:16) | `ser_lib.data.types` | `AudioRecord` | `AudioRecord` | top-level |
| [ser_lib/data/manifest.py:20](D:/projects/Speech-Emotion-Recognition/ser_lib/data/manifest.py:20) | `ser_lib.core.exceptions` | `SchemaMigrationError` | `SchemaMigrationError` | top-level |
| [ser_lib/data/manifest.py:21](D:/projects/Speech-Emotion-Recognition/ser_lib/data/manifest.py:21) | `ser_lib.core.migrations` | `migrate_schema_payload` | `migrate_schema_payload` | top-level |
| [ser_lib/data/manifest.py:22](D:/projects/Speech-Emotion-Recognition/ser_lib/data/manifest.py:22) | `ser_lib.data.errors` | `ManifestError` | `ManifestError` | top-level |
| [ser_lib/data/manifest.py:23](D:/projects/Speech-Emotion-Recognition/ser_lib/data/manifest.py:23) | `ser_lib.data.types` | `AudioRecord` | `AudioRecord` | top-level |
| [ser_lib/data/pipeline.py:16](D:/projects/Speech-Emotion-Recognition/ser_lib/data/pipeline.py:16) | `ser_lib.data.audio` | `AudioLoader` | `AudioLoader` | TYPE_CHECKING |
| [ser_lib/data/pipeline.py:18](D:/projects/Speech-Emotion-Recognition/ser_lib/data/pipeline.py:18) | `ser_lib.data.config` | `ComponentConfig` | `ComponentConfig` | top-level |
| [ser_lib/data/pipeline.py:18](D:/projects/Speech-Emotion-Recognition/ser_lib/data/pipeline.py:18) | `ser_lib.data.config` | `DataConfig` | `DataConfig` | top-level |
| [ser_lib/data/pipeline.py:19](D:/projects/Speech-Emotion-Recognition/ser_lib/data/pipeline.py:19) | `ser_lib.data.errors` | `RepresentationError` | `RepresentationError` | top-level |
| [ser_lib/data/pipeline.py:19](D:/projects/Speech-Emotion-Recognition/ser_lib/data/pipeline.py:19) | `ser_lib.data.errors` | `TransformError` | `TransformError` | top-level |
| [ser_lib/data/pipeline.py:20](D:/projects/Speech-Emotion-Recognition/ser_lib/data/pipeline.py:20) | `ser_lib.data.registry` | `default_registry` | `default_registry` | top-level |
| [ser_lib/data/pipeline.py:21](D:/projects/Speech-Emotion-Recognition/ser_lib/data/pipeline.py:21) | `ser_lib.data.representations.base` | `Representation` | `Representation` | top-level |
| [ser_lib/data/pipeline.py:22](D:/projects/Speech-Emotion-Recognition/ser_lib/data/pipeline.py:22) | `ser_lib.data.transforms.base` | `FeatureTransformPipeline` | `FeatureTransformPipeline` | top-level |
| [ser_lib/data/pipeline.py:22](D:/projects/Speech-Emotion-Recognition/ser_lib/data/pipeline.py:22) | `ser_lib.data.transforms.base` | `RandomApply` | `RandomApply` | top-level |
| [ser_lib/data/pipeline.py:22](D:/projects/Speech-Emotion-Recognition/ser_lib/data/pipeline.py:22) | `ser_lib.data.transforms.base` | `WaveformTransformPipeline` | `WaveformTransformPipeline` | top-level |
| [ser_lib/data/pipeline.py:22](D:/projects/Speech-Emotion-Recognition/ser_lib/data/pipeline.py:22) | `ser_lib.data.transforms.base` | `validate_feature_transform_layouts` | `validate_feature_transform_layouts` | top-level |
| [ser_lib/data/pipeline.py:28](D:/projects/Speech-Emotion-Recognition/ser_lib/data/pipeline.py:28) | `ser_lib.data.types` | `AudioData` | `AudioData` | top-level |
| [ser_lib/data/pipeline.py:28](D:/projects/Speech-Emotion-Recognition/ser_lib/data/pipeline.py:28) | `ser_lib.data.types` | `AudioRecord` | `AudioRecord` | top-level |
| [ser_lib/data/pipeline.py:28](D:/projects/Speech-Emotion-Recognition/ser_lib/data/pipeline.py:28) | `ser_lib.data.types` | `RepresentationOutput` | `RepresentationOutput` | top-level |
| [ser_lib/data/pipeline.py:28](D:/projects/Speech-Emotion-Recognition/ser_lib/data/pipeline.py:28) | `ser_lib.data.types` | `SERSample` | `SERSample` | top-level |
| [ser_lib/data/pipeline.py:28](D:/projects/Speech-Emotion-Recognition/ser_lib/data/pipeline.py:28) | `ser_lib.data.types` | `TensorSpec` | `TensorSpec` | top-level |
| [ser_lib/data/pipeline.py:28](D:/projects/Speech-Emotion-Recognition/ser_lib/data/pipeline.py:28) | `ser_lib.data.types` | `validate_representation_output` | `validate_representation_output` | top-level |
| [ser_lib/data/pipeline.py:201](D:/projects/Speech-Emotion-Recognition/ser_lib/data/pipeline.py:201) | `ser_lib.data.transforms.waveform` | `WAVEFORM_TRANSFORM_SPECS` | `WAVEFORM_TRANSFORM_SPECS` | local:_waveform_transform_entry |
| [ser_lib/data/pipeline.py:206](D:/projects/Speech-Emotion-Recognition/ser_lib/data/pipeline.py:206) | `ser_lib.data.errors` | `RegistryError` | `RegistryError` | local:_waveform_transform_entry |
| [ser_lib/data/pipeline.py:223](D:/projects/Speech-Emotion-Recognition/ser_lib/data/pipeline.py:223) | `ser_lib.data.errors` | `RegistryError` | `RegistryError` | local:_build_feature_transforms,conditional |
| [ser_lib/data/pipeline.py:262](D:/projects/Speech-Emotion-Recognition/ser_lib/data/pipeline.py:262) | `ser_lib.data.cache` | `CachedRepresentation` | `CachedRepresentation` | local:build_pipeline,conditional |
| [ser_lib/data/pipeline.py:292](D:/projects/Speech-Emotion-Recognition/ser_lib/data/pipeline.py:292) | `ser_lib.data.audio` | `AudioLoader` | `AudioLoader` | local:build_components |
| [ser_lib/data/pipeline.py:292](D:/projects/Speech-Emotion-Recognition/ser_lib/data/pipeline.py:292) | `ser_lib.data.audio` | `AudioLoaderConfig` | `AudioLoaderConfig` | local:build_components |
| [ser_lib/data/profiling.py:9](D:/projects/Speech-Emotion-Recognition/ser_lib/data/profiling.py:9) | `ser_lib.core.events` | `CancellationCheck` | `CancellationCheck` | top-level |
| [ser_lib/data/profiling.py:9](D:/projects/Speech-Emotion-Recognition/ser_lib/data/profiling.py:9) | `ser_lib.core.events` | `EventCallback` | `EventCallback` | top-level |
| [ser_lib/data/profiling.py:9](D:/projects/Speech-Emotion-Recognition/ser_lib/data/profiling.py:9) | `ser_lib.core.events` | `ProgressEvent` | `ProgressEvent` | top-level |
| [ser_lib/data/profiling.py:10](D:/projects/Speech-Emotion-Recognition/ser_lib/data/profiling.py:10) | `ser_lib.data.audio` | `probe_audio` | `probe_audio` | top-level |
| [ser_lib/data/profiling.py:11](D:/projects/Speech-Emotion-Recognition/ser_lib/data/profiling.py:11) | `ser_lib.data.manifest` | `DatasetManifest` | `DatasetManifest` | top-level |
| [ser_lib/data/query.py:11](D:/projects/Speech-Emotion-Recognition/ser_lib/data/query.py:11) | `ser_lib.data.manifest` | `DatasetManifest` | `DatasetManifest` | top-level |
| [ser_lib/data/query.py:12](D:/projects/Speech-Emotion-Recognition/ser_lib/data/query.py:12) | `ser_lib.data.types` | `AudioRecord` | `AudioRecord` | top-level |
| [ser_lib/data/registry.py:18](D:/projects/Speech-Emotion-Recognition/ser_lib/data/registry.py:18) | `ser_lib.data.errors` | `RegistryError` | `RegistryError` | top-level |
| [ser_lib/data/registry.py:19](D:/projects/Speech-Emotion-Recognition/ser_lib/data/registry.py:19) | `ser_lib.data.types` | `TensorSpec` | `TensorSpec` | top-level |
| [ser_lib/data/representations/__init__.py:5](D:/projects/Speech-Emotion-Recognition/ser_lib/data/representations/__init__.py:5) | `ser_lib.data.registry` | `Registry` | `Registry` | top-level |
| [ser_lib/data/representations/__init__.py:5](D:/projects/Speech-Emotion-Recognition/ser_lib/data/representations/__init__.py:5) | `ser_lib.data.registry` | `default_registry` | `default_registry` | top-level |
| [ser_lib/data/representations/__init__.py:6](D:/projects/Speech-Emotion-Recognition/ser_lib/data/representations/__init__.py:6) | `ser_lib.data.representations.acoustic` | `AcousticFeatures` | `AcousticFeatures` | top-level |
| [ser_lib/data/representations/__init__.py:6](D:/projects/Speech-Emotion-Recognition/ser_lib/data/representations/__init__.py:6) | `ser_lib.data.representations.acoustic` | `AcousticFeaturesConfig` | `AcousticFeaturesConfig` | top-level |
| [ser_lib/data/representations/__init__.py:10](D:/projects/Speech-Emotion-Recognition/ser_lib/data/representations/__init__.py:10) | `ser_lib.data.representations.base` | `Representation` | `Representation` | top-level |
| [ser_lib/data/representations/__init__.py:11](D:/projects/Speech-Emotion-Recognition/ser_lib/data/representations/__init__.py:11) | `ser_lib.data.representations.composite` | `CompositeConfig` | `CompositeConfig` | top-level |
| [ser_lib/data/representations/__init__.py:11](D:/projects/Speech-Emotion-Recognition/ser_lib/data/representations/__init__.py:11) | `ser_lib.data.representations.composite` | `CompositeRepresentation` | `CompositeRepresentation` | top-level |
| [ser_lib/data/representations/__init__.py:15](D:/projects/Speech-Emotion-Recognition/ser_lib/data/representations/__init__.py:15) | `ser_lib.data.representations.spectral` | `LogMelConfig` | `LogMelConfig` | top-level |
| [ser_lib/data/representations/__init__.py:15](D:/projects/Speech-Emotion-Recognition/ser_lib/data/representations/__init__.py:15) | `ser_lib.data.representations.spectral` | `LogMelRepresentation` | `LogMelRepresentation` | top-level |
| [ser_lib/data/representations/__init__.py:15](D:/projects/Speech-Emotion-Recognition/ser_lib/data/representations/__init__.py:15) | `ser_lib.data.representations.spectral` | `MFCCConfig` | `MFCCConfig` | top-level |
| [ser_lib/data/representations/__init__.py:15](D:/projects/Speech-Emotion-Recognition/ser_lib/data/representations/__init__.py:15) | `ser_lib.data.representations.spectral` | `MFCCRepresentation` | `MFCCRepresentation` | top-level |
| [ser_lib/data/representations/__init__.py:15](D:/projects/Speech-Emotion-Recognition/ser_lib/data/representations/__init__.py:15) | `ser_lib.data.representations.spectral` | `MelConfig` | `MelConfig` | top-level |
| [ser_lib/data/representations/__init__.py:15](D:/projects/Speech-Emotion-Recognition/ser_lib/data/representations/__init__.py:15) | `ser_lib.data.representations.spectral` | `MelSpectrogramRepresentation` | `MelSpectrogramRepresentation` | top-level |
| [ser_lib/data/representations/__init__.py:15](D:/projects/Speech-Emotion-Recognition/ser_lib/data/representations/__init__.py:15) | `ser_lib.data.representations.spectral` | `SpectrogramConfig` | `SpectrogramConfig` | top-level |
| [ser_lib/data/representations/__init__.py:15](D:/projects/Speech-Emotion-Recognition/ser_lib/data/representations/__init__.py:15) | `ser_lib.data.representations.spectral` | `SpectrogramRepresentation` | `SpectrogramRepresentation` | top-level |
| [ser_lib/data/representations/__init__.py:25](D:/projects/Speech-Emotion-Recognition/ser_lib/data/representations/__init__.py:25) | `ser_lib.data.representations.waveform` | `RawWaveform` | `RawWaveform` | top-level |
| [ser_lib/data/representations/__init__.py:25](D:/projects/Speech-Emotion-Recognition/ser_lib/data/representations/__init__.py:25) | `ser_lib.data.representations.waveform` | `RawWaveformConfig` | `RawWaveformConfig` | top-level |
| [ser_lib/data/representations/acoustic.py:25](D:/projects/Speech-Emotion-Recognition/ser_lib/data/representations/acoustic.py:25) | `ser_lib.data.errors` | `RepresentationError` | `RepresentationError` | top-level |
| [ser_lib/data/representations/acoustic.py:26](D:/projects/Speech-Emotion-Recognition/ser_lib/data/representations/acoustic.py:26) | `ser_lib.data.registry` | `ComponentDescriptor` | `ComponentDescriptor` | top-level |
| [ser_lib/data/representations/acoustic.py:27](D:/projects/Speech-Emotion-Recognition/ser_lib/data/representations/acoustic.py:27) | `ser_lib.data.representations.base` | `Representation` | `Representation` | top-level |
| [ser_lib/data/representations/acoustic.py:28](D:/projects/Speech-Emotion-Recognition/ser_lib/data/representations/acoustic.py:28) | `ser_lib.data.types` | `LAYOUT_D` | `LAYOUT_D` | top-level |
| [ser_lib/data/representations/acoustic.py:28](D:/projects/Speech-Emotion-Recognition/ser_lib/data/representations/acoustic.py:28) | `ser_lib.data.types` | `LAYOUT_TD` | `LAYOUT_TD` | top-level |
| [ser_lib/data/representations/acoustic.py:28](D:/projects/Speech-Emotion-Recognition/ser_lib/data/representations/acoustic.py:28) | `ser_lib.data.types` | `AudioData` | `AudioData` | top-level |
| [ser_lib/data/representations/acoustic.py:28](D:/projects/Speech-Emotion-Recognition/ser_lib/data/representations/acoustic.py:28) | `ser_lib.data.types` | `RepresentationOutput` | `RepresentationOutput` | top-level |
| [ser_lib/data/representations/acoustic.py:28](D:/projects/Speech-Emotion-Recognition/ser_lib/data/representations/acoustic.py:28) | `ser_lib.data.types` | `TensorSpec` | `TensorSpec` | top-level |
| [ser_lib/data/representations/base.py:14](D:/projects/Speech-Emotion-Recognition/ser_lib/data/representations/base.py:14) | `ser_lib.data.errors` | `RepresentationError` | `RepresentationError` | top-level |
| [ser_lib/data/representations/base.py:15](D:/projects/Speech-Emotion-Recognition/ser_lib/data/representations/base.py:15) | `ser_lib.data.registry` | `ComponentDescriptor` | `ComponentDescriptor` | top-level |
| [ser_lib/data/representations/base.py:16](D:/projects/Speech-Emotion-Recognition/ser_lib/data/representations/base.py:16) | `ser_lib.data.types` | `AudioData` | `AudioData` | top-level |
| [ser_lib/data/representations/base.py:16](D:/projects/Speech-Emotion-Recognition/ser_lib/data/representations/base.py:16) | `ser_lib.data.types` | `RepresentationOutput` | `RepresentationOutput` | top-level |
| [ser_lib/data/representations/base.py:16](D:/projects/Speech-Emotion-Recognition/ser_lib/data/representations/base.py:16) | `ser_lib.data.types` | `TensorSpec` | `TensorSpec` | top-level |
| [ser_lib/data/representations/composite.py:15](D:/projects/Speech-Emotion-Recognition/ser_lib/data/representations/composite.py:15) | `ser_lib.data.errors` | `RepresentationError` | `RepresentationError` | top-level |
| [ser_lib/data/representations/composite.py:16](D:/projects/Speech-Emotion-Recognition/ser_lib/data/representations/composite.py:16) | `ser_lib.data.registry` | `ComponentDescriptor` | `ComponentDescriptor` | top-level |
| [ser_lib/data/representations/composite.py:16](D:/projects/Speech-Emotion-Recognition/ser_lib/data/representations/composite.py:16) | `ser_lib.data.registry` | `default_registry` | `default_registry` | top-level |
| [ser_lib/data/representations/composite.py:17](D:/projects/Speech-Emotion-Recognition/ser_lib/data/representations/composite.py:17) | `ser_lib.data.representations.base` | `Representation` | `Representation` | top-level |
| [ser_lib/data/representations/composite.py:18](D:/projects/Speech-Emotion-Recognition/ser_lib/data/representations/composite.py:18) | `ser_lib.data.types` | `AudioData` | `AudioData` | top-level |
| [ser_lib/data/representations/composite.py:18](D:/projects/Speech-Emotion-Recognition/ser_lib/data/representations/composite.py:18) | `ser_lib.data.types` | `RepresentationOutput` | `RepresentationOutput` | top-level |
| [ser_lib/data/representations/composite.py:18](D:/projects/Speech-Emotion-Recognition/ser_lib/data/representations/composite.py:18) | `ser_lib.data.types` | `TensorSpec` | `TensorSpec` | top-level |
| [ser_lib/data/representations/spectral.py:14](D:/projects/Speech-Emotion-Recognition/ser_lib/data/representations/spectral.py:14) | `ser_lib.data.errors` | `RepresentationError` | `RepresentationError` | top-level |
| [ser_lib/data/representations/spectral.py:15](D:/projects/Speech-Emotion-Recognition/ser_lib/data/representations/spectral.py:15) | `ser_lib.data.registry` | `ComponentDescriptor` | `ComponentDescriptor` | top-level |
| [ser_lib/data/representations/spectral.py:16](D:/projects/Speech-Emotion-Recognition/ser_lib/data/representations/spectral.py:16) | `ser_lib.data.representations.base` | `Representation` | `Representation` | top-level |
| [ser_lib/data/representations/spectral.py:17](D:/projects/Speech-Emotion-Recognition/ser_lib/data/representations/spectral.py:17) | `ser_lib.data.types` | `LAYOUT_FT` | `LAYOUT_FT` | top-level |
| [ser_lib/data/representations/spectral.py:17](D:/projects/Speech-Emotion-Recognition/ser_lib/data/representations/spectral.py:17) | `ser_lib.data.types` | `AudioData` | `AudioData` | top-level |
| [ser_lib/data/representations/spectral.py:17](D:/projects/Speech-Emotion-Recognition/ser_lib/data/representations/spectral.py:17) | `ser_lib.data.types` | `RepresentationOutput` | `RepresentationOutput` | top-level |
| [ser_lib/data/representations/spectral.py:17](D:/projects/Speech-Emotion-Recognition/ser_lib/data/representations/spectral.py:17) | `ser_lib.data.types` | `TensorSpec` | `TensorSpec` | top-level |
| [ser_lib/data/representations/waveform.py:7](D:/projects/Speech-Emotion-Recognition/ser_lib/data/representations/waveform.py:7) | `ser_lib.data.registry` | `ComponentDescriptor` | `ComponentDescriptor` | top-level |
| [ser_lib/data/representations/waveform.py:8](D:/projects/Speech-Emotion-Recognition/ser_lib/data/representations/waveform.py:8) | `ser_lib.data.representations.base` | `Representation` | `Representation` | top-level |
| [ser_lib/data/representations/waveform.py:9](D:/projects/Speech-Emotion-Recognition/ser_lib/data/representations/waveform.py:9) | `ser_lib.data.types` | `LAYOUT_T` | `LAYOUT_T` | top-level |
| [ser_lib/data/representations/waveform.py:9](D:/projects/Speech-Emotion-Recognition/ser_lib/data/representations/waveform.py:9) | `ser_lib.data.types` | `AudioData` | `AudioData` | top-level |
| [ser_lib/data/representations/waveform.py:9](D:/projects/Speech-Emotion-Recognition/ser_lib/data/representations/waveform.py:9) | `ser_lib.data.types` | `RepresentationOutput` | `RepresentationOutput` | top-level |
| [ser_lib/data/representations/waveform.py:9](D:/projects/Speech-Emotion-Recognition/ser_lib/data/representations/waveform.py:9) | `ser_lib.data.types` | `TensorSpec` | `TensorSpec` | top-level |
| [ser_lib/data/transforms/__init__.py:5](D:/projects/Speech-Emotion-Recognition/ser_lib/data/transforms/__init__.py:5) | `ser_lib.data.registry` | `Registry` | `Registry` | top-level |
| [ser_lib/data/transforms/__init__.py:5](D:/projects/Speech-Emotion-Recognition/ser_lib/data/transforms/__init__.py:5) | `ser_lib.data.registry` | `default_registry` | `default_registry` | top-level |
| [ser_lib/data/transforms/__init__.py:6](D:/projects/Speech-Emotion-Recognition/ser_lib/data/transforms/__init__.py:6) | `ser_lib.data.transforms.base` | `FeatureTransformPipeline` | `FeatureTransformPipeline` | top-level |
| [ser_lib/data/transforms/__init__.py:6](D:/projects/Speech-Emotion-Recognition/ser_lib/data/transforms/__init__.py:6) | `ser_lib.data.transforms.base` | `RandomApply` | `RandomApply` | top-level |
| [ser_lib/data/transforms/__init__.py:6](D:/projects/Speech-Emotion-Recognition/ser_lib/data/transforms/__init__.py:6) | `ser_lib.data.transforms.base` | `WaveformTransformPipeline` | `WaveformTransformPipeline` | top-level |
| [ser_lib/data/transforms/__init__.py:6](D:/projects/Speech-Emotion-Recognition/ser_lib/data/transforms/__init__.py:6) | `ser_lib.data.transforms.base` | `validate_feature_transform_layouts` | `validate_feature_transform_layouts` | top-level |
| [ser_lib/data/transforms/__init__.py:12](D:/projects/Speech-Emotion-Recognition/ser_lib/data/transforms/__init__.py:12) | `ser_lib.data.transforms.feature` | `SPEC_MASKING_DESCRIPTOR` | `SPEC_MASKING_DESCRIPTOR` | top-level |
| [ser_lib/data/transforms/__init__.py:12](D:/projects/Speech-Emotion-Recognition/ser_lib/data/transforms/__init__.py:12) | `ser_lib.data.transforms.feature` | `SpecMasking` | `SpecMasking` | top-level |
| [ser_lib/data/transforms/__init__.py:12](D:/projects/Speech-Emotion-Recognition/ser_lib/data/transforms/__init__.py:12) | `ser_lib.data.transforms.feature` | `SpecMaskingConfig` | `SpecMaskingConfig` | top-level |
| [ser_lib/data/transforms/__init__.py:17](D:/projects/Speech-Emotion-Recognition/ser_lib/data/transforms/__init__.py:17) | `ser_lib.data.transforms.waveform` | `WAVEFORM_TRANSFORM_SPECS` | `WAVEFORM_TRANSFORM_SPECS` | top-level |
| [ser_lib/data/transforms/base.py:14](D:/projects/Speech-Emotion-Recognition/ser_lib/data/transforms/base.py:14) | `ser_lib.data.errors` | `TransformError` | `TransformError` | top-level |
| [ser_lib/data/transforms/base.py:15](D:/projects/Speech-Emotion-Recognition/ser_lib/data/transforms/base.py:15) | `ser_lib.data.types` | `TensorSpec` | `TensorSpec` | top-level |
| [ser_lib/data/transforms/feature.py:14](D:/projects/Speech-Emotion-Recognition/ser_lib/data/transforms/feature.py:14) | `ser_lib.data.registry` | `ComponentDescriptor` | `ComponentDescriptor` | top-level |
| [ser_lib/data/transforms/waveform.py:21](D:/projects/Speech-Emotion-Recognition/ser_lib/data/transforms/waveform.py:21) | `ser_lib.data.registry` | `ComponentDescriptor` | `ComponentDescriptor` | top-level |
| [ser_lib/data/transforms/waveform.py:22](D:/projects/Speech-Emotion-Recognition/ser_lib/data/transforms/waveform.py:22) | `ser_lib.data.transforms.base` | `RandomApply` | `RandomApply` | top-level |
| [ser_lib/data/types.py:20](D:/projects/Speech-Emotion-Recognition/ser_lib/data/types.py:20) | `ser_lib.data.errors` | `RepresentationError` | `RepresentationError` | top-level |
| [ser_lib/data/types.py:20](D:/projects/Speech-Emotion-Recognition/ser_lib/data/types.py:20) | `ser_lib.data.errors` | `SERDataError` | `SERDataError` | top-level |
| [ser_lib/data/validation.py:13](D:/projects/Speech-Emotion-Recognition/ser_lib/data/validation.py:13) | `ser_lib.core.diagnostics` | `Diagnostic` | `Diagnostic` | top-level |
| [ser_lib/data/validation.py:14](D:/projects/Speech-Emotion-Recognition/ser_lib/data/validation.py:14) | `ser_lib.data.config` | `BatchingConfig` | `BatchingConfig` | top-level |
| [ser_lib/data/validation.py:15](D:/projects/Speech-Emotion-Recognition/ser_lib/data/validation.py:15) | `ser_lib.data.errors` | `CompatibilityError` | `CompatibilityError` | top-level |
| [ser_lib/data/validation.py:16](D:/projects/Speech-Emotion-Recognition/ser_lib/data/validation.py:16) | `ser_lib.data.types` | `TensorSpec` | `TensorSpec` | top-level |
| [ser_lib/engine/__init__.py:1](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/__init__.py:1) | `ser_lib.engine.checkpoint` | `load_checkpoint` | `load_checkpoint` | top-level |
| [ser_lib/engine/__init__.py:1](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/__init__.py:1) | `ser_lib.engine.checkpoint` | `save_checkpoint` | `save_checkpoint` | top-level |
| [ser_lib/engine/__init__.py:2](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/__init__.py:2) | `ser_lib.engine.checkpoint_catalog` | `CheckpointCatalog` | `CheckpointCatalog` | top-level |
| [ser_lib/engine/__init__.py:2](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/__init__.py:2) | `ser_lib.engine.checkpoint_catalog` | `CheckpointInfo` | `CheckpointInfo` | top-level |
| [ser_lib/engine/__init__.py:2](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/__init__.py:2) | `ser_lib.engine.checkpoint_catalog` | `CheckpointKind` | `CheckpointKind` | top-level |
| [ser_lib/engine/__init__.py:2](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/__init__.py:2) | `ser_lib.engine.checkpoint_catalog` | `CheckpointScanFailure` | `CheckpointScanFailure` | top-level |
| [ser_lib/engine/__init__.py:2](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/__init__.py:2) | `ser_lib.engine.checkpoint_catalog` | `inspect_checkpoint_file` | `inspect_checkpoint_file` | top-level |
| [ser_lib/engine/__init__.py:2](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/__init__.py:2) | `ser_lib.engine.checkpoint_catalog` | `scan_checkpoints` | `scan_checkpoints` | top-level |
| [ser_lib/engine/__init__.py:10](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/__init__.py:10) | `ser_lib.engine.config` | `ExperimentConfig` | `ExperimentConfig` | top-level |
| [ser_lib/engine/__init__.py:10](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/__init__.py:10) | `ser_lib.engine.config` | `ExperimentComponents` | `ExperimentComponents` | top-level |
| [ser_lib/engine/__init__.py:10](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/__init__.py:10) | `ser_lib.engine.config` | `ModelConfig` | `ModelConfig` | top-level |
| [ser_lib/engine/__init__.py:10](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/__init__.py:10) | `ser_lib.engine.config` | `ObservabilityConfig` | `ObservabilityConfig` | top-level |
| [ser_lib/engine/__init__.py:10](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/__init__.py:10) | `ser_lib.engine.config` | `TrainerConfig` | `TrainerConfig` | top-level |
| [ser_lib/engine/__init__.py:10](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/__init__.py:10) | `ser_lib.engine.config` | `build_experiment_components` | `build_experiment_components` | top-level |
| [ser_lib/engine/__init__.py:10](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/__init__.py:10) | `ser_lib.engine.config` | `load_experiment_config` | `load_experiment_config` | top-level |
| [ser_lib/engine/__init__.py:19](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/__init__.py:19) | `ser_lib.engine.eta` | `EtaEstimator` | `EtaEstimator` | top-level |
| [ser_lib/engine/__init__.py:19](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/__init__.py:19) | `ser_lib.engine.eta` | `EtaSnapshot` | `EtaSnapshot` | top-level |
| [ser_lib/engine/__init__.py:20](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/__init__.py:20) | `ser_lib.engine.evaluation_catalog` | `EvaluationRunCatalog` | `EvaluationRunCatalog` | top-level |
| [ser_lib/engine/__init__.py:20](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/__init__.py:20) | `ser_lib.engine.evaluation_catalog` | `EvaluationRunScanFailure` | `EvaluationRunScanFailure` | top-level |
| [ser_lib/engine/__init__.py:20](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/__init__.py:20) | `ser_lib.engine.evaluation_catalog` | `scan_evaluation_runs` | `scan_evaluation_runs` | top-level |
| [ser_lib/engine/__init__.py:25](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/__init__.py:25) | `ser_lib.engine.evaluation_detail` | `EvaluationPredictionFileInfo` | `EvaluationPredictionFileInfo` | top-level |
| [ser_lib/engine/__init__.py:25](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/__init__.py:25) | `ser_lib.engine.evaluation_detail` | `EvaluationRunDetail` | `EvaluationRunDetail` | top-level |
| [ser_lib/engine/__init__.py:25](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/__init__.py:25) | `ser_lib.engine.evaluation_detail` | `inspect_evaluation_prediction_file` | `inspect_evaluation_prediction_file` | top-level |
| [ser_lib/engine/__init__.py:30](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/__init__.py:30) | `ser_lib.engine.evaluation_reports` | `EvaluationPredictionPage` | `EvaluationPredictionPage` | top-level |
| [ser_lib/engine/__init__.py:30](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/__init__.py:30) | `ser_lib.engine.evaluation_reports` | `EvaluationReportInfo` | `EvaluationReportInfo` | top-level |
| [ser_lib/engine/__init__.py:30](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/__init__.py:30) | `ser_lib.engine.evaluation_reports` | `inspect_evaluation_report` | `inspect_evaluation_report` | top-level |
| [ser_lib/engine/__init__.py:30](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/__init__.py:30) | `ser_lib.engine.evaluation_reports` | `query_evaluation_predictions` | `query_evaluation_predictions` | top-level |
| [ser_lib/engine/__init__.py:36](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/__init__.py:36) | `ser_lib.engine.evaluation_runs` | `EVALUATION_RUN_SCHEMA_VERSION` | `EVALUATION_RUN_SCHEMA_VERSION` | top-level |
| [ser_lib/engine/__init__.py:36](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/__init__.py:36) | `ser_lib.engine.evaluation_runs` | `EvaluationRunInfo` | `EvaluationRunInfo` | top-level |
| [ser_lib/engine/__init__.py:36](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/__init__.py:36) | `ser_lib.engine.evaluation_runs` | `EvaluationRunMetadata` | `EvaluationRunMetadata` | top-level |
| [ser_lib/engine/__init__.py:36](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/__init__.py:36) | `ser_lib.engine.evaluation_runs` | `build_evaluation_run_metadata` | `build_evaluation_run_metadata` | top-level |
| [ser_lib/engine/__init__.py:36](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/__init__.py:36) | `ser_lib.engine.evaluation_runs` | `load_evaluation_run_info` | `load_evaluation_run_info` | top-level |
| [ser_lib/engine/__init__.py:36](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/__init__.py:36) | `ser_lib.engine.evaluation_runs` | `write_evaluation_run_info` | `write_evaluation_run_info` | top-level |
| [ser_lib/engine/__init__.py:44](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/__init__.py:44) | `ser_lib.engine.evaluator` | `ClassMetrics` | `ClassMetrics` | top-level |
| [ser_lib/engine/__init__.py:44](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/__init__.py:44) | `ser_lib.engine.evaluator` | `EvaluationResult` | `EvaluationResult` | top-level |
| [ser_lib/engine/__init__.py:44](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/__init__.py:44) | `ser_lib.engine.evaluator` | `JsonlPredictionSink` | `JsonlPredictionSink` | top-level |
| [ser_lib/engine/__init__.py:44](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/__init__.py:44) | `ser_lib.engine.evaluator` | `PredictionRecord` | `PredictionRecord` | top-level |
| [ser_lib/engine/__init__.py:44](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/__init__.py:44) | `ser_lib.engine.evaluator` | `PredictionSink` | `PredictionSink` | top-level |
| [ser_lib/engine/__init__.py:44](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/__init__.py:44) | `ser_lib.engine.evaluator` | `evaluate` | `evaluate` | top-level |
| [ser_lib/engine/__init__.py:44](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/__init__.py:44) | `ser_lib.engine.evaluator` | `write_evaluation_report` | `write_evaluation_report` | top-level |
| [ser_lib/engine/__init__.py:53](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/__init__.py:53) | `ser_lib.engine.lineage` | `TrainingRunMetadata` | `TrainingRunMetadata` | top-level |
| [ser_lib/engine/__init__.py:53](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/__init__.py:53) | `ser_lib.engine.lineage` | `build_training_run_metadata` | `build_training_run_metadata` | top-level |
| [ser_lib/engine/__init__.py:54](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/__init__.py:54) | `ser_lib.engine.optim` | `AdamConfig` | `AdamConfig` | top-level |
| [ser_lib/engine/__init__.py:54](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/__init__.py:54) | `ser_lib.engine.optim` | `AdamWConfig` | `AdamWConfig` | top-level |
| [ser_lib/engine/__init__.py:54](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/__init__.py:54) | `ser_lib.engine.optim` | `CosineSchedulerConfig` | `CosineSchedulerConfig` | top-level |
| [ser_lib/engine/__init__.py:54](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/__init__.py:54) | `ser_lib.engine.optim` | `SGDConfig` | `SGDConfig` | top-level |
| [ser_lib/engine/__init__.py:54](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/__init__.py:54) | `ser_lib.engine.optim` | `StepSchedulerConfig` | `StepSchedulerConfig` | top-level |
| [ser_lib/engine/__init__.py:54](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/__init__.py:54) | `ser_lib.engine.optim` | `build_optimizer` | `build_optimizer` | top-level |
| [ser_lib/engine/__init__.py:54](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/__init__.py:54) | `ser_lib.engine.optim` | `build_scheduler` | `build_scheduler` | top-level |
| [ser_lib/engine/__init__.py:54](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/__init__.py:54) | `ser_lib.engine.optim` | `parse_optimizer_config` | `parse_optimizer_config` | top-level |
| [ser_lib/engine/__init__.py:54](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/__init__.py:54) | `ser_lib.engine.optim` | `parse_scheduler_config` | `parse_scheduler_config` | top-level |
| [ser_lib/engine/__init__.py:65](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/__init__.py:65) | `ser_lib.engine.objectives` | `ClassificationLoss` | `ClassificationLoss` | top-level |
| [ser_lib/engine/__init__.py:65](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/__init__.py:65) | `ser_lib.engine.objectives` | `LossConfig` | `LossConfig` | top-level |
| [ser_lib/engine/__init__.py:65](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/__init__.py:65) | `ser_lib.engine.objectives` | `SamplingConfig` | `SamplingConfig` | top-level |
| [ser_lib/engine/__init__.py:65](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/__init__.py:65) | `ser_lib.engine.objectives` | `build_weighted_sampler` | `build_weighted_sampler` | top-level |
| [ser_lib/engine/__init__.py:71](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/__init__.py:71) | `ser_lib.engine.presets` | `ExperimentPresetCatalog` | `ExperimentPresetCatalog` | top-level |
| [ser_lib/engine/__init__.py:71](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/__init__.py:71) | `ser_lib.engine.presets` | `ExperimentPresetInfo` | `ExperimentPresetInfo` | top-level |
| [ser_lib/engine/__init__.py:71](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/__init__.py:71) | `ser_lib.engine.presets` | `PresetStatus` | `PresetStatus` | top-level |
| [ser_lib/engine/__init__.py:71](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/__init__.py:71) | `ser_lib.engine.presets` | `build_experiment_config` | `build_experiment_config` | top-level |
| [ser_lib/engine/__init__.py:71](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/__init__.py:71) | `ser_lib.engine.presets` | `get_experiment_preset` | `get_experiment_preset` | top-level |
| [ser_lib/engine/__init__.py:71](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/__init__.py:71) | `ser_lib.engine.presets` | `list_experiment_presets` | `list_experiment_presets` | top-level |
| [ser_lib/engine/__init__.py:79](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/__init__.py:79) | `ser_lib.engine.runs` | `RUN_RECORD_SCHEMA_VERSION` | `RUN_RECORD_SCHEMA_VERSION` | top-level |
| [ser_lib/engine/__init__.py:79](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/__init__.py:79) | `ser_lib.engine.runs` | `TrainingRunCatalog` | `TrainingRunCatalog` | top-level |
| [ser_lib/engine/__init__.py:79](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/__init__.py:79) | `ser_lib.engine.runs` | `TrainingRunDetail` | `TrainingRunDetail` | top-level |
| [ser_lib/engine/__init__.py:79](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/__init__.py:79) | `ser_lib.engine.runs` | `TrainingRunInfo` | `TrainingRunInfo` | top-level |
| [ser_lib/engine/__init__.py:79](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/__init__.py:79) | `ser_lib.engine.runs` | `TrainingRunScanFailure` | `TrainingRunScanFailure` | top-level |
| [ser_lib/engine/__init__.py:79](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/__init__.py:79) | `ser_lib.engine.runs` | `load_training_run_info` | `load_training_run_info` | top-level |
| [ser_lib/engine/__init__.py:79](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/__init__.py:79) | `ser_lib.engine.runs` | `scan_training_runs` | `scan_training_runs` | top-level |
| [ser_lib/engine/__init__.py:79](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/__init__.py:79) | `ser_lib.engine.runs` | `write_training_run_info` | `write_training_run_info` | top-level |
| [ser_lib/engine/__init__.py:89](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/__init__.py:89) | `ser_lib.engine.training_history` | `TrainingHistoryInfo` | `TrainingHistoryInfo` | top-level |
| [ser_lib/engine/__init__.py:89](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/__init__.py:89) | `ser_lib.engine.training_history` | `load_training_history` | `load_training_history` | top-level |
| [ser_lib/engine/__init__.py:90](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/__init__.py:90) | `ser_lib.engine.trainer` | `EpochResult` | `EpochResult` | top-level |
| [ser_lib/engine/__init__.py:90](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/__init__.py:90) | `ser_lib.engine.trainer` | `Trainer` | `Trainer` | top-level |
| [ser_lib/engine/__init__.py:90](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/__init__.py:90) | `ser_lib.engine.trainer` | `TrainingResult` | `TrainingResult` | top-level |
| [ser_lib/engine/__init__.py:90](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/__init__.py:90) | `ser_lib.engine.trainer` | `TrainingStatus` | `TrainingStatus` | top-level |
| [ser_lib/engine/__init__.py:90](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/__init__.py:90) | `ser_lib.engine.trainer` | `seed_everything` | `seed_everything` | top-level |
| [ser_lib/engine/__init__.py:97](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/__init__.py:97) | `ser_lib.engine.validation` | `ExperimentValidationResult` | `ExperimentValidationResult` | top-level |
| [ser_lib/engine/__init__.py:97](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/__init__.py:97) | `ser_lib.engine.validation` | `validate_experiment` | `validate_experiment` | top-level |
| [ser_lib/engine/_trainer_core.py:18](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/_trainer_core.py:18) | `ser_lib.core.events` | `CancellationCheck` | `CancellationCheck` | top-level |
| [ser_lib/engine/_trainer_core.py:18](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/_trainer_core.py:18) | `ser_lib.core.events` | `CheckpointEvent` | `CheckpointEvent` | top-level |
| [ser_lib/engine/_trainer_core.py:18](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/_trainer_core.py:18) | `ser_lib.core.events` | `EventCallback` | `EventCallback` | top-level |
| [ser_lib/engine/_trainer_core.py:18](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/_trainer_core.py:18) | `ser_lib.core.events` | `EventContext` | `EventContext` | top-level |
| [ser_lib/engine/_trainer_core.py:18](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/_trainer_core.py:18) | `ser_lib.core.events` | `LibraryEvent` | `LibraryEvent` | top-level |
| [ser_lib/engine/_trainer_core.py:18](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/_trainer_core.py:18) | `ser_lib.core.events` | `LifecycleEvent` | `LifecycleEvent` | top-level |
| [ser_lib/engine/_trainer_core.py:18](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/_trainer_core.py:18) | `ser_lib.core.events` | `MetricEvent` | `MetricEvent` | top-level |
| [ser_lib/engine/_trainer_core.py:18](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/_trainer_core.py:18) | `ser_lib.core.events` | `ProgressEvent` | `ProgressEvent` | top-level |
| [ser_lib/engine/_trainer_core.py:28](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/_trainer_core.py:28) | `ser_lib.core.exceptions` | `OperationCancelled` | `OperationCancelled` | top-level |
| [ser_lib/engine/_trainer_core.py:29](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/_trainer_core.py:29) | `ser_lib.data.types` | `SERBatch` | `SERBatch` | top-level |
| [ser_lib/engine/_trainer_core.py:30](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/_trainer_core.py:30) | `ser_lib.engine.config` | `ExperimentConfig` | `ExperimentConfig` | top-level |
| [ser_lib/engine/_trainer_core.py:30](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/_trainer_core.py:30) | `ser_lib.engine.config` | `ObservabilityConfig` | `ObservabilityConfig` | top-level |
| [ser_lib/engine/_trainer_core.py:30](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/_trainer_core.py:30) | `ser_lib.engine.config` | `TrainerConfig` | `TrainerConfig` | top-level |
| [ser_lib/engine/_trainer_core.py:31](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/_trainer_core.py:31) | `ser_lib.engine.eta` | `EtaEstimator` | `EtaEstimator` | top-level |
| [ser_lib/engine/_trainer_core.py:32](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/_trainer_core.py:32) | `ser_lib.engine.optim` | `SchedulerConfig` | `SchedulerConfig` | top-level |
| [ser_lib/engine/_trainer_core.py:32](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/_trainer_core.py:32) | `ser_lib.engine.optim` | `build_optimizer` | `build_optimizer` | top-level |
| [ser_lib/engine/_trainer_core.py:32](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/_trainer_core.py:32) | `ser_lib.engine.optim` | `build_scheduler` | `build_scheduler` | top-level |
| [ser_lib/engine/_trainer_core.py:32](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/_trainer_core.py:32) | `ser_lib.engine.optim` | `parse_optimizer_config` | `parse_optimizer_config` | top-level |
| [ser_lib/engine/_trainer_core.py:32](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/_trainer_core.py:32) | `ser_lib.engine.optim` | `parse_scheduler_config` | `parse_scheduler_config` | top-level |
| [ser_lib/engine/_trainer_core.py:39](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/_trainer_core.py:39) | `ser_lib.models.base` | `SERModel` | `SERModel` | top-level |
| [ser_lib/engine/_trainer_core.py:219](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/_trainer_core.py:219) | `ser_lib.models.registry` | `model_registry` | `model_registry` | local:from_experiment |
| [ser_lib/engine/_trainer_core.py:235](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/_trainer_core.py:235) | `ser_lib.engine.objectives` | `ClassificationLoss` | `ClassificationLoss` | local:from_experiment |
| [ser_lib/engine/_trainer_core.py:566](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/_trainer_core.py:566) | `ser_lib.engine.checkpoint` | `save_checkpoint` | `save_checkpoint` | local:_save_checkpoint_with_event |
| [ser_lib/engine/_trainer_core.py:722](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/_trainer_core.py:722) | `ser_lib.engine.evaluator` | `evaluate` | `evaluate` | local:fit,conditional |
| [ser_lib/engine/_trainer_core.py:974](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/_trainer_core.py:974) | `ser_lib.engine.checkpoint` | `load_checkpoint` | `load_checkpoint` | local:resume_from |
| [ser_lib/engine/checkpoint.py:11](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/checkpoint.py:11) | `ser_lib.models.base` | `SERModel` | `SERModel` | top-level |
| [ser_lib/engine/checkpoint_catalog.py:11](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/checkpoint_catalog.py:11) | `ser_lib.core._catalog_scan` | `scan_catalog_candidates` | `scan_catalog_candidates` | top-level |
| [ser_lib/engine/checkpoint_catalog.py:12](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/checkpoint_catalog.py:12) | `ser_lib.core.events` | `CancellationCheck` | `CancellationCheck` | top-level |
| [ser_lib/engine/checkpoint_catalog.py:12](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/checkpoint_catalog.py:12) | `ser_lib.core.events` | `EventCallback` | `EventCallback` | top-level |
| [ser_lib/engine/config.py:11](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/config.py:11) | `ser_lib.core.config` | `StrictConfig` | `StrictConfig` | top-level |
| [ser_lib/engine/config.py:11](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/config.py:11) | `ser_lib.core.config` | `load_versioned_config` | `load_versioned_config` | top-level |
| [ser_lib/engine/config.py:12](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/config.py:12) | `ser_lib.data.config` | `DataConfig` | `DataConfig` | top-level |
| [ser_lib/engine/config.py:13](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/config.py:13) | `ser_lib.engine.objectives` | `LossConfig` | `LossConfig` | top-level |
| [ser_lib/engine/config.py:13](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/config.py:13) | `ser_lib.engine.objectives` | `SamplingConfig` | `SamplingConfig` | top-level |
| [ser_lib/engine/config.py:16](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/config.py:16) | `ser_lib.data.audio` | `AudioLoader` | `AudioLoader` | TYPE_CHECKING |
| [ser_lib/engine/config.py:17](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/config.py:17) | `ser_lib.data.collate` | `SERCollator` | `SERCollator` | TYPE_CHECKING |
| [ser_lib/engine/config.py:18](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/config.py:18) | `ser_lib.data.pipeline` | `SamplePipeline` | `SamplePipeline` | TYPE_CHECKING |
| [ser_lib/engine/config.py:19](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/config.py:19) | `ser_lib.models.base` | `SERModel` | `SERModel` | TYPE_CHECKING |
| [ser_lib/engine/config.py:83](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/config.py:83) | `ser_lib.engine.optim` | `parse_optimizer_config` | `parse_optimizer_config` | local:_validate_optimizer |
| [ser_lib/engine/config.py:91](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/config.py:91) | `ser_lib.engine.optim` | `parse_scheduler_config` | `parse_scheduler_config` | local:_validate_scheduler |
| [ser_lib/engine/config.py:113](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/config.py:113) | `ser_lib.data.collate` | `build_collator` | `build_collator` | local:build_experiment_components |
| [ser_lib/engine/config.py:114](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/config.py:114) | `ser_lib.data.pipeline` | `build_components` | `build_components` | local:build_experiment_components |
| [ser_lib/engine/config.py:115](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/config.py:115) | `ser_lib.data.validation` | `validate_compatibility` | `validate_compatibility` | local:build_experiment_components |
| [ser_lib/engine/config.py:116](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/config.py:116) | `ser_lib.models.registry` | `model_registry` | `model_registry` | local:build_experiment_components |
| [ser_lib/engine/evaluation_catalog.py:9](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/evaluation_catalog.py:9) | `ser_lib.core._catalog_scan` | `scan_catalog_candidates` | `scan_catalog_candidates` | top-level |
| [ser_lib/engine/evaluation_catalog.py:10](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/evaluation_catalog.py:10) | `ser_lib.core.events` | `CancellationCheck` | `CancellationCheck` | top-level |
| [ser_lib/engine/evaluation_catalog.py:10](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/evaluation_catalog.py:10) | `ser_lib.core.events` | `EventCallback` | `EventCallback` | top-level |
| [ser_lib/engine/evaluation_catalog.py:11](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/evaluation_catalog.py:11) | `ser_lib.engine.evaluation_runs` | `EvaluationRunInfo` | `EvaluationRunInfo` | top-level |
| [ser_lib/engine/evaluation_catalog.py:11](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/evaluation_catalog.py:11) | `ser_lib.engine.evaluation_runs` | `load_evaluation_run_info` | `load_evaluation_run_info` | top-level |
| [ser_lib/engine/evaluation_detail.py:9](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/evaluation_detail.py:9) | `ser_lib.core.diagnostics` | `Diagnostic` | `Diagnostic` | top-level |
| [ser_lib/engine/evaluation_detail.py:10](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/evaluation_detail.py:10) | `ser_lib.engine.evaluation_reports` | `EvaluationReportInfo` | `EvaluationReportInfo` | top-level |
| [ser_lib/engine/evaluation_detail.py:11](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/evaluation_detail.py:11) | `ser_lib.engine.evaluation_runs` | `EvaluationRunInfo` | `EvaluationRunInfo` | top-level |
| [ser_lib/engine/evaluation_reports.py:12](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/evaluation_reports.py:12) | `ser_lib.core.events` | `CancellationCheck` | `CancellationCheck` | top-level |
| [ser_lib/engine/evaluation_reports.py:13](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/evaluation_reports.py:13) | `ser_lib.engine.evaluator` | `ClassMetrics` | `ClassMetrics` | top-level |
| [ser_lib/engine/evaluation_reports.py:13](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/evaluation_reports.py:13) | `ser_lib.engine.evaluator` | `PredictionRecord` | `PredictionRecord` | top-level |
| [ser_lib/engine/evaluation_runs.py:14](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/evaluation_runs.py:14) | `ser_lib.core.migrations` | `migrate_schema_payload` | `migrate_schema_payload` | top-level |
| [ser_lib/engine/evaluation_runs.py:15](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/evaluation_runs.py:15) | `ser_lib.engine.evaluator` | `EvaluationResult` | `EvaluationResult` | top-level |
| [ser_lib/engine/evaluator.py:15](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/evaluator.py:15) | `ser_lib.core.events` | `CancellationCheck` | `CancellationCheck` | top-level |
| [ser_lib/engine/evaluator.py:15](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/evaluator.py:15) | `ser_lib.core.events` | `EventCallback` | `EventCallback` | top-level |
| [ser_lib/engine/evaluator.py:15](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/evaluator.py:15) | `ser_lib.core.events` | `EventContext` | `EventContext` | top-level |
| [ser_lib/engine/evaluator.py:15](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/evaluator.py:15) | `ser_lib.core.events` | `LifecycleEvent` | `LifecycleEvent` | top-level |
| [ser_lib/engine/evaluator.py:15](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/evaluator.py:15) | `ser_lib.core.events` | `ProgressEvent` | `ProgressEvent` | top-level |
| [ser_lib/engine/evaluator.py:22](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/evaluator.py:22) | `ser_lib.core.exceptions` | `OperationCancelled` | `OperationCancelled` | top-level |
| [ser_lib/engine/evaluator.py:23](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/evaluator.py:23) | `ser_lib.data.types` | `SERBatch` | `SERBatch` | top-level |
| [ser_lib/engine/evaluator.py:24](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/evaluator.py:24) | `ser_lib.engine.trainer` | `move_batch_to_device` | `move_batch_to_device` | top-level |
| [ser_lib/engine/evaluator.py:25](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/evaluator.py:25) | `ser_lib.models.base` | `SERModel` | `SERModel` | top-level |
| [ser_lib/engine/objectives.py:13](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/objectives.py:13) | `ser_lib.core.config` | `StrictConfig` | `StrictConfig` | top-level |
| [ser_lib/engine/optim.py:10](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/optim.py:10) | `ser_lib.core.config` | `StrictConfig` | `StrictConfig` | top-level |
| [ser_lib/engine/presets.py:9](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/presets.py:9) | `ser_lib.engine.config` | `ExperimentConfig` | `ExperimentConfig` | top-level |
| [ser_lib/engine/runs.py:13](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/runs.py:13) | `ser_lib.core._catalog_scan` | `scan_catalog_candidates` | `scan_catalog_candidates` | top-level |
| [ser_lib/engine/runs.py:14](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/runs.py:14) | `ser_lib.core.diagnostics` | `Diagnostic` | `Diagnostic` | top-level |
| [ser_lib/engine/runs.py:15](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/runs.py:15) | `ser_lib.core.events` | `CancellationCheck` | `CancellationCheck` | top-level |
| [ser_lib/engine/runs.py:15](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/runs.py:15) | `ser_lib.core.events` | `EventCallback` | `EventCallback` | top-level |
| [ser_lib/engine/runs.py:16](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/runs.py:16) | `ser_lib.core.migrations` | `migrate_schema_payload` | `migrate_schema_payload` | top-level |
| [ser_lib/engine/runs.py:17](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/runs.py:17) | `ser_lib.engine.checkpoint_catalog` | `CheckpointCatalog` | `CheckpointCatalog` | top-level |
| [ser_lib/engine/runs.py:18](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/runs.py:18) | `ser_lib.engine.lineage` | `TrainingRunMetadata` | `TrainingRunMetadata` | top-level |
| [ser_lib/engine/runs.py:19](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/runs.py:19) | `ser_lib.engine.training_history` | `TrainingHistoryInfo` | `TrainingHistoryInfo` | top-level |
| [ser_lib/engine/runs.py:20](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/runs.py:20) | `ser_lib.engine.trainer` | `TrainingResult` | `TrainingResult` | top-level |
| [ser_lib/engine/runs.py:20](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/runs.py:20) | `ser_lib.engine.trainer` | `TrainingStatus` | `TrainingStatus` | top-level |
| [ser_lib/engine/trainer.py:11](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/trainer.py:11) | `ser_lib.core.events` | `CancellationCheck` | `CancellationCheck` | top-level |
| [ser_lib/engine/trainer.py:11](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/trainer.py:11) | `ser_lib.core.events` | `EventCallback` | `EventCallback` | top-level |
| [ser_lib/engine/trainer.py:12](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/trainer.py:12) | `ser_lib.engine._trainer_core` | `EpochResult` | `EpochResult` | top-level |
| [ser_lib/engine/trainer.py:12](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/trainer.py:12) | `ser_lib.engine._trainer_core` | `ObservabilityConfig` | `ObservabilityConfig` | top-level |
| [ser_lib/engine/trainer.py:12](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/trainer.py:12) | `ser_lib.engine._trainer_core` | `Trainer` | `_TrainerCore` | top-level |
| [ser_lib/engine/trainer.py:12](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/trainer.py:12) | `ser_lib.engine._trainer_core` | `TrainerConfig` | `TrainerConfig` | top-level |
| [ser_lib/engine/trainer.py:12](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/trainer.py:12) | `ser_lib.engine._trainer_core` | `TrainingResult` | `TrainingResult` | top-level |
| [ser_lib/engine/trainer.py:12](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/trainer.py:12) | `ser_lib.engine._trainer_core` | `TrainingStatus` | `TrainingStatus` | top-level |
| [ser_lib/engine/trainer.py:12](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/trainer.py:12) | `ser_lib.engine._trainer_core` | `move_batch_to_device` | `move_batch_to_device` | top-level |
| [ser_lib/engine/trainer.py:12](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/trainer.py:12) | `ser_lib.engine._trainer_core` | `seed_everything` | `seed_everything` | top-level |
| [ser_lib/engine/trainer.py:22](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/trainer.py:22) | `ser_lib.engine.config` | `ExperimentConfig` | `ExperimentConfig` | top-level |
| [ser_lib/engine/trainer.py:23](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/trainer.py:23) | `ser_lib.engine.lineage` | `TrainingRunMetadata` | `TrainingRunMetadata` | top-level |
| [ser_lib/engine/trainer.py:24](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/trainer.py:24) | `ser_lib.engine.optim` | `AdamWConfig` | `AdamWConfig` | top-level |
| [ser_lib/engine/trainer.py:24](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/trainer.py:24) | `ser_lib.engine.optim` | `build_optimizer` | `build_optimizer` | top-level |
| [ser_lib/engine/trainer.py:25](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/trainer.py:25) | `ser_lib.models.base` | `SERModel` | `SERModel` | top-level |
| [ser_lib/engine/training_history.py:13](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/training_history.py:13) | `ser_lib.engine.trainer` | `EpochResult` | `EpochResult` | top-level |
| [ser_lib/engine/validation.py:11](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/validation.py:11) | `ser_lib.core.diagnostics` | `Diagnostic` | `Diagnostic` | top-level |
| [ser_lib/engine/validation.py:12](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/validation.py:12) | `ser_lib.data.manifest` | `ManifestMeta` | `ManifestMeta` | top-level |
| [ser_lib/engine/validation.py:12](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/validation.py:12) | `ser_lib.data.manifest` | `load_meta` | `load_meta` | top-level |
| [ser_lib/engine/validation.py:13](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/validation.py:13) | `ser_lib.data.pipeline` | `SamplePipeline` | `SamplePipeline` | top-level |
| [ser_lib/engine/validation.py:13](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/validation.py:13) | `ser_lib.data.pipeline` | `build_pipeline` | `build_pipeline` | top-level |
| [ser_lib/engine/validation.py:14](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/validation.py:14) | `ser_lib.data.validation` | `ModelSpec` | `ModelSpec` | top-level |
| [ser_lib/engine/validation.py:14](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/validation.py:14) | `ser_lib.data.validation` | `inspect_compatibility` | `inspect_compatibility` | top-level |
| [ser_lib/engine/validation.py:15](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/validation.py:15) | `ser_lib.engine.config` | `ExperimentConfig` | `ExperimentConfig` | top-level |
| [ser_lib/engine/validation.py:15](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/validation.py:15) | `ser_lib.engine.config` | `load_experiment_config` | `load_experiment_config` | top-level |
| [ser_lib/engine/validation.py:16](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/validation.py:16) | `ser_lib.engine.optim` | `parse_optimizer_config` | `parse_optimizer_config` | top-level |
| [ser_lib/engine/validation.py:16](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/validation.py:16) | `ser_lib.engine.optim` | `parse_scheduler_config` | `parse_scheduler_config` | top-level |
| [ser_lib/engine/validation.py:17](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/validation.py:17) | `ser_lib.models.registry` | `model_registry` | `model_registry` | top-level |
| [ser_lib/inference/__init__.py:1](D:/projects/Speech-Emotion-Recognition/ser_lib/inference/__init__.py:1) | `ser_lib.inference.batch` | `BatchEmotionPredictor` | `BatchEmotionPredictor` | top-level |
| [ser_lib/inference/__init__.py:1](D:/projects/Speech-Emotion-Recognition/ser_lib/inference/__init__.py:1) | `ser_lib.inference.batch` | `BatchPredictionResult` | `BatchPredictionResult` | top-level |
| [ser_lib/inference/__init__.py:1](D:/projects/Speech-Emotion-Recognition/ser_lib/inference/__init__.py:1) | `ser_lib.inference.batch` | `BatchPredictionSink` | `BatchPredictionSink` | top-level |
| [ser_lib/inference/__init__.py:1](D:/projects/Speech-Emotion-Recognition/ser_lib/inference/__init__.py:1) | `ser_lib.inference.batch` | `JsonlBatchPredictionSink` | `JsonlBatchPredictionSink` | top-level |
| [ser_lib/inference/__init__.py:1](D:/projects/Speech-Emotion-Recognition/ser_lib/inference/__init__.py:1) | `ser_lib.inference.batch` | `PredictionFailure` | `PredictionFailure` | top-level |
| [ser_lib/inference/__init__.py:1](D:/projects/Speech-Emotion-Recognition/ser_lib/inference/__init__.py:1) | `ser_lib.inference.batch` | `write_batch_predictions` | `write_batch_predictions` | top-level |
| [ser_lib/inference/__init__.py:9](D:/projects/Speech-Emotion-Recognition/ser_lib/inference/__init__.py:9) | `ser_lib.inference.offline` | `EmotionPredictor` | `EmotionPredictor` | top-level |
| [ser_lib/inference/__init__.py:9](D:/projects/Speech-Emotion-Recognition/ser_lib/inference/__init__.py:9) | `ser_lib.inference.offline` | `PredictionResult` | `PredictionResult` | top-level |
| [ser_lib/inference/__init__.py:10](D:/projects/Speech-Emotion-Recognition/ser_lib/inference/__init__.py:10) | `ser_lib.inference.streaming` | `StreamingConfig` | `StreamingConfig` | top-level |
| [ser_lib/inference/__init__.py:10](D:/projects/Speech-Emotion-Recognition/ser_lib/inference/__init__.py:10) | `ser_lib.inference.streaming` | `StreamingEmotionRecognizer` | `StreamingEmotionRecognizer` | top-level |
| [ser_lib/inference/__init__.py:10](D:/projects/Speech-Emotion-Recognition/ser_lib/inference/__init__.py:10) | `ser_lib.inference.streaming` | `StreamingLatency` | `StreamingLatency` | top-level |
| [ser_lib/inference/__init__.py:10](D:/projects/Speech-Emotion-Recognition/ser_lib/inference/__init__.py:10) | `ser_lib.inference.streaming` | `StreamingPrediction` | `StreamingPrediction` | top-level |
| [ser_lib/inference/batch.py:13](D:/projects/Speech-Emotion-Recognition/ser_lib/inference/batch.py:13) | `ser_lib.core.events` | `CancellationCheck` | `CancellationCheck` | top-level |
| [ser_lib/inference/batch.py:13](D:/projects/Speech-Emotion-Recognition/ser_lib/inference/batch.py:13) | `ser_lib.core.events` | `EventCallback` | `EventCallback` | top-level |
| [ser_lib/inference/batch.py:13](D:/projects/Speech-Emotion-Recognition/ser_lib/inference/batch.py:13) | `ser_lib.core.events` | `EventContext` | `EventContext` | top-level |
| [ser_lib/inference/batch.py:13](D:/projects/Speech-Emotion-Recognition/ser_lib/inference/batch.py:13) | `ser_lib.core.events` | `PredictionEvent` | `PredictionEvent` | top-level |
| [ser_lib/inference/batch.py:13](D:/projects/Speech-Emotion-Recognition/ser_lib/inference/batch.py:13) | `ser_lib.core.events` | `ProgressEvent` | `ProgressEvent` | top-level |
| [ser_lib/inference/batch.py:20](D:/projects/Speech-Emotion-Recognition/ser_lib/inference/batch.py:20) | `ser_lib.data.manifest` | `DatasetManifest` | `DatasetManifest` | top-level |
| [ser_lib/inference/batch.py:21](D:/projects/Speech-Emotion-Recognition/ser_lib/inference/batch.py:21) | `ser_lib.data.types` | `AudioRecord` | `AudioRecord` | top-level |
| [ser_lib/inference/batch.py:22](D:/projects/Speech-Emotion-Recognition/ser_lib/inference/batch.py:22) | `ser_lib.inference.offline` | `EmotionPredictor` | `EmotionPredictor` | top-level |
| [ser_lib/inference/batch.py:22](D:/projects/Speech-Emotion-Recognition/ser_lib/inference/batch.py:22) | `ser_lib.inference.offline` | `PredictionResult` | `PredictionResult` | top-level |
| [ser_lib/inference/offline.py:8](D:/projects/Speech-Emotion-Recognition/ser_lib/inference/offline.py:8) | `ser_lib.data.audio` | `AudioLoader` | `AudioLoader` | top-level |
| [ser_lib/inference/offline.py:9](D:/projects/Speech-Emotion-Recognition/ser_lib/inference/offline.py:9) | `ser_lib.data.collate` | `SERCollator` | `SERCollator` | top-level |
| [ser_lib/inference/offline.py:10](D:/projects/Speech-Emotion-Recognition/ser_lib/inference/offline.py:10) | `ser_lib.data.pipeline` | `SamplePipeline` | `SamplePipeline` | top-level |
| [ser_lib/inference/offline.py:11](D:/projects/Speech-Emotion-Recognition/ser_lib/inference/offline.py:11) | `ser_lib.data.types` | `AudioData` | `AudioData` | top-level |
| [ser_lib/inference/offline.py:11](D:/projects/Speech-Emotion-Recognition/ser_lib/inference/offline.py:11) | `ser_lib.data.types` | `AudioRecord` | `AudioRecord` | top-level |
| [ser_lib/inference/offline.py:12](D:/projects/Speech-Emotion-Recognition/ser_lib/inference/offline.py:12) | `ser_lib.engine.trainer` | `move_batch_to_device` | `move_batch_to_device` | top-level |
| [ser_lib/inference/offline.py:13](D:/projects/Speech-Emotion-Recognition/ser_lib/inference/offline.py:13) | `ser_lib.models.base` | `SERModel` | `SERModel` | top-level |
| [ser_lib/inference/streaming.py:11](D:/projects/Speech-Emotion-Recognition/ser_lib/inference/streaming.py:11) | `ser_lib.data.types` | `AudioData` | `AudioData` | top-level |
| [ser_lib/inference/streaming.py:12](D:/projects/Speech-Emotion-Recognition/ser_lib/inference/streaming.py:12) | `ser_lib.inference.offline` | `EmotionPredictor` | `EmotionPredictor` | top-level |
| [ser_lib/inference/streaming.py:12](D:/projects/Speech-Emotion-Recognition/ser_lib/inference/streaming.py:12) | `ser_lib.inference.offline` | `PredictionResult` | `PredictionResult` | top-level |
| [ser_lib/models/__init__.py:1](D:/projects/Speech-Emotion-Recognition/ser_lib/models/__init__.py:1) | `ser_lib.models.base` | `ModelOutput` | `ModelOutput` | top-level |
| [ser_lib/models/__init__.py:1](D:/projects/Speech-Emotion-Recognition/ser_lib/models/__init__.py:1) | `ser_lib.models.base` | `SERModel` | `SERModel` | top-level |
| [ser_lib/models/__init__.py:2](D:/projects/Speech-Emotion-Recognition/ser_lib/models/__init__.py:2) | `ser_lib.models.cnn_models` | `CNNBaseline` | `CNNBaseline` | top-level |
| [ser_lib/models/__init__.py:2](D:/projects/Speech-Emotion-Recognition/ser_lib/models/__init__.py:2) | `ser_lib.models.cnn_models` | `CNNBaselineConfig` | `CNNBaselineConfig` | top-level |
| [ser_lib/models/__init__.py:3](D:/projects/Speech-Emotion-Recognition/ser_lib/models/__init__.py:3) | `ser_lib.models.rnn_models` | `GRUBaseline` | `GRUBaseline` | top-level |
| [ser_lib/models/__init__.py:3](D:/projects/Speech-Emotion-Recognition/ser_lib/models/__init__.py:3) | `ser_lib.models.rnn_models` | `GRUBaselineConfig` | `GRUBaselineConfig` | top-level |
| [ser_lib/models/__init__.py:4](D:/projects/Speech-Emotion-Recognition/ser_lib/models/__init__.py:4) | `ser_lib.models.transformer_models` | `TransformerBaseline` | `TransformerBaseline` | top-level |
| [ser_lib/models/__init__.py:4](D:/projects/Speech-Emotion-Recognition/ser_lib/models/__init__.py:4) | `ser_lib.models.transformer_models` | `TransformerBaselineConfig` | `TransformerBaselineConfig` | top-level |
| [ser_lib/models/__init__.py:5](D:/projects/Speech-Emotion-Recognition/ser_lib/models/__init__.py:5) | `ser_lib.models.pretrained` | `HFAudioClassifier` | `HFAudioClassifier` | top-level |
| [ser_lib/models/__init__.py:5](D:/projects/Speech-Emotion-Recognition/ser_lib/models/__init__.py:5) | `ser_lib.models.pretrained` | `HFAudioClassifierConfig` | `HFAudioClassifierConfig` | top-level |
| [ser_lib/models/__init__.py:6](D:/projects/Speech-Emotion-Recognition/ser_lib/models/__init__.py:6) | `ser_lib.models.registry` | `ModelDescriptor` | `ModelDescriptor` | top-level |
| [ser_lib/models/__init__.py:6](D:/projects/Speech-Emotion-Recognition/ser_lib/models/__init__.py:6) | `ser_lib.models.registry` | `ModelRegistry` | `ModelRegistry` | top-level |
| [ser_lib/models/__init__.py:6](D:/projects/Speech-Emotion-Recognition/ser_lib/models/__init__.py:6) | `ser_lib.models.registry` | `model_registry` | `model_registry` | top-level |
| [ser_lib/models/base.py:9](D:/projects/Speech-Emotion-Recognition/ser_lib/models/base.py:9) | `ser_lib.data.types` | `SERBatch` | `SERBatch` | top-level |
| [ser_lib/models/base.py:10](D:/projects/Speech-Emotion-Recognition/ser_lib/models/base.py:10) | `ser_lib.data.validation` | `ModelSpec` | `ModelSpec` | top-level |
| [ser_lib/models/cnn_models.py:11](D:/projects/Speech-Emotion-Recognition/ser_lib/models/cnn_models.py:11) | `ser_lib.core.config` | `StrictConfig` | `StrictConfig` | top-level |
| [ser_lib/models/cnn_models.py:12](D:/projects/Speech-Emotion-Recognition/ser_lib/models/cnn_models.py:12) | `ser_lib.data.types` | `SERBatch` | `SERBatch` | top-level |
| [ser_lib/models/cnn_models.py:12](D:/projects/Speech-Emotion-Recognition/ser_lib/models/cnn_models.py:12) | `ser_lib.data.types` | `TensorSpec` | `TensorSpec` | top-level |
| [ser_lib/models/cnn_models.py:13](D:/projects/Speech-Emotion-Recognition/ser_lib/models/cnn_models.py:13) | `ser_lib.data.validation` | `ModelSpec` | `ModelSpec` | top-level |
| [ser_lib/models/cnn_models.py:14](D:/projects/Speech-Emotion-Recognition/ser_lib/models/cnn_models.py:14) | `ser_lib.models.base` | `ModelOutput` | `ModelOutput` | top-level |
| [ser_lib/models/cnn_models.py:14](D:/projects/Speech-Emotion-Recognition/ser_lib/models/cnn_models.py:14) | `ser_lib.models.base` | `SERModel` | `SERModel` | top-level |
| [ser_lib/models/cnn_models.py:15](D:/projects/Speech-Emotion-Recognition/ser_lib/models/cnn_models.py:15) | `ser_lib.models.registry` | `ModelDescriptor` | `ModelDescriptor` | top-level |
| [ser_lib/models/cnn_models.py:15](D:/projects/Speech-Emotion-Recognition/ser_lib/models/cnn_models.py:15) | `ser_lib.models.registry` | `model_registry` | `model_registry` | top-level |
| [ser_lib/models/pretrained.py:13](D:/projects/Speech-Emotion-Recognition/ser_lib/models/pretrained.py:13) | `ser_lib.core.config` | `StrictConfig` | `StrictConfig` | top-level |
| [ser_lib/models/pretrained.py:14](D:/projects/Speech-Emotion-Recognition/ser_lib/models/pretrained.py:14) | `ser_lib.data.types` | `SERBatch` | `SERBatch` | top-level |
| [ser_lib/models/pretrained.py:14](D:/projects/Speech-Emotion-Recognition/ser_lib/models/pretrained.py:14) | `ser_lib.data.types` | `TensorSpec` | `TensorSpec` | top-level |
| [ser_lib/models/pretrained.py:15](D:/projects/Speech-Emotion-Recognition/ser_lib/models/pretrained.py:15) | `ser_lib.data.validation` | `ModelSpec` | `ModelSpec` | top-level |
| [ser_lib/models/pretrained.py:16](D:/projects/Speech-Emotion-Recognition/ser_lib/models/pretrained.py:16) | `ser_lib.models.base` | `ModelOutput` | `ModelOutput` | top-level |
| [ser_lib/models/pretrained.py:16](D:/projects/Speech-Emotion-Recognition/ser_lib/models/pretrained.py:16) | `ser_lib.models.base` | `SERModel` | `SERModel` | top-level |
| [ser_lib/models/pretrained.py:17](D:/projects/Speech-Emotion-Recognition/ser_lib/models/pretrained.py:17) | `ser_lib.models.registry` | `ModelDescriptor` | `ModelDescriptor` | top-level |
| [ser_lib/models/pretrained.py:17](D:/projects/Speech-Emotion-Recognition/ser_lib/models/pretrained.py:17) | `ser_lib.models.registry` | `model_registry` | `model_registry` | top-level |
| [ser_lib/models/registry.py:9](D:/projects/Speech-Emotion-Recognition/ser_lib/models/registry.py:9) | `ser_lib.data.errors` | `RegistryError` | `RegistryError` | top-level |
| [ser_lib/models/registry.py:10](D:/projects/Speech-Emotion-Recognition/ser_lib/models/registry.py:10) | `ser_lib.models.base` | `SERModel` | `SERModel` | top-level |
| [ser_lib/models/registry.py:13](D:/projects/Speech-Emotion-Recognition/ser_lib/models/registry.py:13) | `ser_lib.data.validation` | `ModelSpec` | `ModelSpec` | TYPE_CHECKING |
| [ser_lib/models/registry.py:108](D:/projects/Speech-Emotion-Recognition/ser_lib/models/registry.py:108) | `ser_lib.data.validation` | `ModelSpec` | `ModelSpec` | local:inspect_spec |
| [ser_lib/models/rnn_models.py:12](D:/projects/Speech-Emotion-Recognition/ser_lib/models/rnn_models.py:12) | `ser_lib.core.config` | `StrictConfig` | `StrictConfig` | top-level |
| [ser_lib/models/rnn_models.py:13](D:/projects/Speech-Emotion-Recognition/ser_lib/models/rnn_models.py:13) | `ser_lib.data.types` | `SERBatch` | `SERBatch` | top-level |
| [ser_lib/models/rnn_models.py:13](D:/projects/Speech-Emotion-Recognition/ser_lib/models/rnn_models.py:13) | `ser_lib.data.types` | `TensorSpec` | `TensorSpec` | top-level |
| [ser_lib/models/rnn_models.py:14](D:/projects/Speech-Emotion-Recognition/ser_lib/models/rnn_models.py:14) | `ser_lib.data.validation` | `ModelSpec` | `ModelSpec` | top-level |
| [ser_lib/models/rnn_models.py:15](D:/projects/Speech-Emotion-Recognition/ser_lib/models/rnn_models.py:15) | `ser_lib.models.base` | `ModelOutput` | `ModelOutput` | top-level |
| [ser_lib/models/rnn_models.py:15](D:/projects/Speech-Emotion-Recognition/ser_lib/models/rnn_models.py:15) | `ser_lib.models.base` | `SERModel` | `SERModel` | top-level |
| [ser_lib/models/rnn_models.py:16](D:/projects/Speech-Emotion-Recognition/ser_lib/models/rnn_models.py:16) | `ser_lib.models.registry` | `ModelDescriptor` | `ModelDescriptor` | top-level |
| [ser_lib/models/rnn_models.py:16](D:/projects/Speech-Emotion-Recognition/ser_lib/models/rnn_models.py:16) | `ser_lib.models.registry` | `model_registry` | `model_registry` | top-level |
| [ser_lib/models/transformer_models.py:12](D:/projects/Speech-Emotion-Recognition/ser_lib/models/transformer_models.py:12) | `ser_lib.core.config` | `StrictConfig` | `StrictConfig` | top-level |
| [ser_lib/models/transformer_models.py:13](D:/projects/Speech-Emotion-Recognition/ser_lib/models/transformer_models.py:13) | `ser_lib.data.types` | `SERBatch` | `SERBatch` | top-level |
| [ser_lib/models/transformer_models.py:13](D:/projects/Speech-Emotion-Recognition/ser_lib/models/transformer_models.py:13) | `ser_lib.data.types` | `TensorSpec` | `TensorSpec` | top-level |
| [ser_lib/models/transformer_models.py:14](D:/projects/Speech-Emotion-Recognition/ser_lib/models/transformer_models.py:14) | `ser_lib.data.validation` | `ModelSpec` | `ModelSpec` | top-level |
| [ser_lib/models/transformer_models.py:15](D:/projects/Speech-Emotion-Recognition/ser_lib/models/transformer_models.py:15) | `ser_lib.models.base` | `ModelOutput` | `ModelOutput` | top-level |
| [ser_lib/models/transformer_models.py:15](D:/projects/Speech-Emotion-Recognition/ser_lib/models/transformer_models.py:15) | `ser_lib.models.base` | `SERModel` | `SERModel` | top-level |
| [ser_lib/models/transformer_models.py:16](D:/projects/Speech-Emotion-Recognition/ser_lib/models/transformer_models.py:16) | `ser_lib.models.registry` | `ModelDescriptor` | `ModelDescriptor` | top-level |
| [ser_lib/models/transformer_models.py:16](D:/projects/Speech-Emotion-Recognition/ser_lib/models/transformer_models.py:16) | `ser_lib.models.registry` | `model_registry` | `model_registry` | top-level |
| [ser_lib/services/__init__.py:3](D:/projects/Speech-Emotion-Recognition/ser_lib/services/__init__.py:3) | `ser_lib.services.artifacts` | `ArtifactService` | `ArtifactService` | top-level |
| [ser_lib/services/__init__.py:4](D:/projects/Speech-Emotion-Recognition/ser_lib/services/__init__.py:4) | `ser_lib.services.catalog` | `CatalogService` | `CatalogService` | top-level |
| [ser_lib/services/__init__.py:5](D:/projects/Speech-Emotion-Recognition/ser_lib/services/__init__.py:5) | `ser_lib.services.datasets` | `DatasetService` | `DatasetService` | top-level |
| [ser_lib/services/__init__.py:6](D:/projects/Speech-Emotion-Recognition/ser_lib/services/__init__.py:6) | `ser_lib.services.evaluation` | `EvaluationService` | `EvaluationService` | top-level |
| [ser_lib/services/__init__.py:7](D:/projects/Speech-Emotion-Recognition/ser_lib/services/__init__.py:7) | `ser_lib.services.inference` | `InferenceService` | `InferenceService` | top-level |
| [ser_lib/services/__init__.py:8](D:/projects/Speech-Emotion-Recognition/ser_lib/services/__init__.py:8) | `ser_lib.services.runtime` | `RuntimeService` | `RuntimeService` | top-level |
| [ser_lib/services/__init__.py:9](D:/projects/Speech-Emotion-Recognition/ser_lib/services/__init__.py:9) | `ser_lib.services.training` | `TrainingService` | `TrainingService` | top-level |
| [ser_lib/services/artifacts.py:11](D:/projects/Speech-Emotion-Recognition/ser_lib/services/artifacts.py:11) | `ser_lib.artifacts` | `ArtifactCatalog` | `ArtifactCatalog` | top-level |
| [ser_lib/services/artifacts.py:11](D:/projects/Speech-Emotion-Recognition/ser_lib/services/artifacts.py:11) | `ser_lib.artifacts` | `LoadedArtifact` | `LoadedArtifact` | top-level |
| [ser_lib/services/artifacts.py:11](D:/projects/Speech-Emotion-Recognition/ser_lib/services/artifacts.py:11) | `ser_lib.artifacts` | `ModelArtifactManifest` | `ModelArtifactManifest` | top-level |
| [ser_lib/services/artifacts.py:11](D:/projects/Speech-Emotion-Recognition/ser_lib/services/artifacts.py:11) | `ser_lib.artifacts` | `ModelCard` | `ModelCard` | top-level |
| [ser_lib/services/artifacts.py:11](D:/projects/Speech-Emotion-Recognition/ser_lib/services/artifacts.py:11) | `ser_lib.artifacts` | `export_model_artifact` | `export_model_artifact` | top-level |
| [ser_lib/services/artifacts.py:11](D:/projects/Speech-Emotion-Recognition/ser_lib/services/artifacts.py:11) | `ser_lib.artifacts` | `inspect_model_artifact` | `inspect_model_artifact` | top-level |
| [ser_lib/services/artifacts.py:11](D:/projects/Speech-Emotion-Recognition/ser_lib/services/artifacts.py:11) | `ser_lib.artifacts` | `load_model_artifact` | `load_model_artifact` | top-level |
| [ser_lib/services/artifacts.py:11](D:/projects/Speech-Emotion-Recognition/ser_lib/services/artifacts.py:11) | `ser_lib.artifacts` | `scan_model_artifacts` | `scan_model_artifacts` | top-level |
| [ser_lib/services/artifacts.py:11](D:/projects/Speech-Emotion-Recognition/ser_lib/services/artifacts.py:11) | `ser_lib.artifacts` | `verify_model_artifact` | `verify_model_artifact` | top-level |
| [ser_lib/services/artifacts.py:22](D:/projects/Speech-Emotion-Recognition/ser_lib/services/artifacts.py:22) | `ser_lib.core.events` | `CancellationCheck` | `CancellationCheck` | top-level |
| [ser_lib/services/artifacts.py:22](D:/projects/Speech-Emotion-Recognition/ser_lib/services/artifacts.py:22) | `ser_lib.core.events` | `EventCallback` | `EventCallback` | top-level |
| [ser_lib/services/artifacts.py:22](D:/projects/Speech-Emotion-Recognition/ser_lib/services/artifacts.py:22) | `ser_lib.core.events` | `EventContext` | `EventContext` | top-level |
| [ser_lib/services/artifacts.py:23](D:/projects/Speech-Emotion-Recognition/ser_lib/services/artifacts.py:23) | `ser_lib.data.config` | `DataConfig` | `DataConfig` | top-level |
| [ser_lib/services/artifacts.py:24](D:/projects/Speech-Emotion-Recognition/ser_lib/services/artifacts.py:24) | `ser_lib.engine.lineage` | `TrainingRunMetadata` | `TrainingRunMetadata` | top-level |
| [ser_lib/services/artifacts.py:25](D:/projects/Speech-Emotion-Recognition/ser_lib/services/artifacts.py:25) | `ser_lib.models.base` | `SERModel` | `SERModel` | top-level |
| [ser_lib/services/catalog.py:7](D:/projects/Speech-Emotion-Recognition/ser_lib/services/catalog.py:7) | `ser_lib.catalog` | `ComponentCatalog` | `ComponentCatalog` | top-level |
| [ser_lib/services/catalog.py:7](D:/projects/Speech-Emotion-Recognition/ser_lib/services/catalog.py:7) | `ser_lib.catalog` | `ComponentDescriptor` | `ComponentDescriptor` | top-level |
| [ser_lib/services/catalog.py:7](D:/projects/Speech-Emotion-Recognition/ser_lib/services/catalog.py:7) | `ser_lib.catalog` | `get_component_catalog` | `get_component_catalog` | top-level |
| [ser_lib/services/catalog.py:7](D:/projects/Speech-Emotion-Recognition/ser_lib/services/catalog.py:7) | `ser_lib.catalog` | `list_component_descriptors` | `list_component_descriptors` | top-level |
| [ser_lib/services/catalog.py:13](D:/projects/Speech-Emotion-Recognition/ser_lib/services/catalog.py:13) | `ser_lib.engine.config` | `ExperimentConfig` | `ExperimentConfig` | top-level |
| [ser_lib/services/catalog.py:14](D:/projects/Speech-Emotion-Recognition/ser_lib/services/catalog.py:14) | `ser_lib.engine.presets` | `ExperimentPresetCatalog` | `ExperimentPresetCatalog` | top-level |
| [ser_lib/services/catalog.py:14](D:/projects/Speech-Emotion-Recognition/ser_lib/services/catalog.py:14) | `ser_lib.engine.presets` | `ExperimentPresetInfo` | `ExperimentPresetInfo` | top-level |
| [ser_lib/services/catalog.py:14](D:/projects/Speech-Emotion-Recognition/ser_lib/services/catalog.py:14) | `ser_lib.engine.presets` | `build_experiment_config` | `build_experiment_config` | top-level |
| [ser_lib/services/catalog.py:14](D:/projects/Speech-Emotion-Recognition/ser_lib/services/catalog.py:14) | `ser_lib.engine.presets` | `get_experiment_preset` | `get_experiment_preset` | top-level |
| [ser_lib/services/catalog.py:14](D:/projects/Speech-Emotion-Recognition/ser_lib/services/catalog.py:14) | `ser_lib.engine.presets` | `list_experiment_presets` | `list_experiment_presets` | top-level |
| [ser_lib/services/datasets.py:8](D:/projects/Speech-Emotion-Recognition/ser_lib/services/datasets.py:8) | `ser_lib.core.events` | `CancellationCheck` | `CancellationCheck` | top-level |
| [ser_lib/services/datasets.py:8](D:/projects/Speech-Emotion-Recognition/ser_lib/services/datasets.py:8) | `ser_lib.core.events` | `EventCallback` | `EventCallback` | top-level |
| [ser_lib/services/datasets.py:9](D:/projects/Speech-Emotion-Recognition/ser_lib/services/datasets.py:9) | `ser_lib.data.editor` | `DatasetEditor` | `DatasetEditor` | top-level |
| [ser_lib/services/datasets.py:10](D:/projects/Speech-Emotion-Recognition/ser_lib/services/datasets.py:10) | `ser_lib.data.fingerprint` | `DatasetFingerprint` | `DatasetFingerprint` | top-level |
| [ser_lib/services/datasets.py:10](D:/projects/Speech-Emotion-Recognition/ser_lib/services/datasets.py:10) | `ser_lib.data.fingerprint` | `fingerprint_manifest` | `fingerprint_manifest` | top-level |
| [ser_lib/services/datasets.py:11](D:/projects/Speech-Emotion-Recognition/ser_lib/services/datasets.py:11) | `ser_lib.data.history` | `DatasetRevisionCatalog` | `DatasetRevisionCatalog` | top-level |
| [ser_lib/services/datasets.py:11](D:/projects/Speech-Emotion-Recognition/ser_lib/services/datasets.py:11) | `ser_lib.data.history` | `DatasetRevisionInfo` | `DatasetRevisionInfo` | top-level |
| [ser_lib/services/datasets.py:11](D:/projects/Speech-Emotion-Recognition/ser_lib/services/datasets.py:11) | `ser_lib.data.history` | `create_dataset_revision` | `create_dataset_revision` | top-level |
| [ser_lib/services/datasets.py:11](D:/projects/Speech-Emotion-Recognition/ser_lib/services/datasets.py:11) | `ser_lib.data.history` | `inspect_dataset_revision` | `inspect_dataset_revision` | top-level |
| [ser_lib/services/datasets.py:11](D:/projects/Speech-Emotion-Recognition/ser_lib/services/datasets.py:11) | `ser_lib.data.history` | `restore_dataset_revision` | `restore_dataset_revision` | top-level |
| [ser_lib/services/datasets.py:11](D:/projects/Speech-Emotion-Recognition/ser_lib/services/datasets.py:11) | `ser_lib.data.history` | `scan_dataset_revisions` | `scan_dataset_revisions` | top-level |
| [ser_lib/services/datasets.py:19](D:/projects/Speech-Emotion-Recognition/ser_lib/services/datasets.py:19) | `ser_lib.data.manifest` | `DatasetManifest` | `DatasetManifest` | top-level |
| [ser_lib/services/datasets.py:20](D:/projects/Speech-Emotion-Recognition/ser_lib/services/datasets.py:20) | `ser_lib.data.profiling` | `DatasetAudioProfile` | `DatasetAudioProfile` | top-level |
| [ser_lib/services/datasets.py:20](D:/projects/Speech-Emotion-Recognition/ser_lib/services/datasets.py:20) | `ser_lib.data.profiling` | `DatasetProfile` | `DatasetProfile` | top-level |
| [ser_lib/services/datasets.py:20](D:/projects/Speech-Emotion-Recognition/ser_lib/services/datasets.py:20) | `ser_lib.data.profiling` | `DatasetSummary` | `DatasetSummary` | top-level |
| [ser_lib/services/datasets.py:20](D:/projects/Speech-Emotion-Recognition/ser_lib/services/datasets.py:20) | `ser_lib.data.profiling` | `profile_dataset` | `profile_dataset` | top-level |
| [ser_lib/services/datasets.py:20](D:/projects/Speech-Emotion-Recognition/ser_lib/services/datasets.py:20) | `ser_lib.data.profiling` | `profile_manifest_audio` | `profile_manifest_audio` | top-level |
| [ser_lib/services/datasets.py:20](D:/projects/Speech-Emotion-Recognition/ser_lib/services/datasets.py:20) | `ser_lib.data.profiling` | `summarize_manifest` | `summarize_manifest` | top-level |
| [ser_lib/services/datasets.py:28](D:/projects/Speech-Emotion-Recognition/ser_lib/services/datasets.py:28) | `ser_lib.data.query` | `RecordPage` | `RecordPage` | top-level |
| [ser_lib/services/datasets.py:28](D:/projects/Speech-Emotion-Recognition/ser_lib/services/datasets.py:28) | `ser_lib.data.query` | `query_records` | `query_records` | top-level |
| [ser_lib/services/evaluation.py:11](D:/projects/Speech-Emotion-Recognition/ser_lib/services/evaluation.py:11) | `ser_lib.core.diagnostics` | `Diagnostic` | `Diagnostic` | top-level |
| [ser_lib/services/evaluation.py:12](D:/projects/Speech-Emotion-Recognition/ser_lib/services/evaluation.py:12) | `ser_lib.core.events` | `CancellationCheck` | `CancellationCheck` | top-level |
| [ser_lib/services/evaluation.py:12](D:/projects/Speech-Emotion-Recognition/ser_lib/services/evaluation.py:12) | `ser_lib.core.events` | `EventCallback` | `EventCallback` | top-level |
| [ser_lib/services/evaluation.py:12](D:/projects/Speech-Emotion-Recognition/ser_lib/services/evaluation.py:12) | `ser_lib.core.events` | `EventContext` | `EventContext` | top-level |
| [ser_lib/services/evaluation.py:13](D:/projects/Speech-Emotion-Recognition/ser_lib/services/evaluation.py:13) | `ser_lib.data.types` | `SERBatch` | `SERBatch` | top-level |
| [ser_lib/services/evaluation.py:14](D:/projects/Speech-Emotion-Recognition/ser_lib/services/evaluation.py:14) | `ser_lib.engine.evaluation_catalog` | `EvaluationRunCatalog` | `EvaluationRunCatalog` | top-level |
| [ser_lib/services/evaluation.py:14](D:/projects/Speech-Emotion-Recognition/ser_lib/services/evaluation.py:14) | `ser_lib.engine.evaluation_catalog` | `scan_evaluation_runs` | `scan_evaluation_runs` | top-level |
| [ser_lib/services/evaluation.py:15](D:/projects/Speech-Emotion-Recognition/ser_lib/services/evaluation.py:15) | `ser_lib.engine.evaluation_detail` | `EvaluationRunDetail` | `EvaluationRunDetail` | top-level |
| [ser_lib/services/evaluation.py:15](D:/projects/Speech-Emotion-Recognition/ser_lib/services/evaluation.py:15) | `ser_lib.engine.evaluation_detail` | `inspect_evaluation_prediction_file` | `inspect_evaluation_prediction_file` | top-level |
| [ser_lib/services/evaluation.py:19](D:/projects/Speech-Emotion-Recognition/ser_lib/services/evaluation.py:19) | `ser_lib.engine.evaluation_reports` | `EvaluationPredictionPage` | `EvaluationPredictionPage` | top-level |
| [ser_lib/services/evaluation.py:19](D:/projects/Speech-Emotion-Recognition/ser_lib/services/evaluation.py:19) | `ser_lib.engine.evaluation_reports` | `EvaluationReportInfo` | `EvaluationReportInfo` | top-level |
| [ser_lib/services/evaluation.py:19](D:/projects/Speech-Emotion-Recognition/ser_lib/services/evaluation.py:19) | `ser_lib.engine.evaluation_reports` | `inspect_evaluation_report` | `inspect_evaluation_report` | top-level |
| [ser_lib/services/evaluation.py:19](D:/projects/Speech-Emotion-Recognition/ser_lib/services/evaluation.py:19) | `ser_lib.engine.evaluation_reports` | `query_evaluation_predictions` | `query_evaluation_predictions` | top-level |
| [ser_lib/services/evaluation.py:25](D:/projects/Speech-Emotion-Recognition/ser_lib/services/evaluation.py:25) | `ser_lib.engine.evaluation_runs` | `EvaluationRunInfo` | `EvaluationRunInfo` | top-level |
| [ser_lib/services/evaluation.py:25](D:/projects/Speech-Emotion-Recognition/ser_lib/services/evaluation.py:25) | `ser_lib.engine.evaluation_runs` | `EvaluationRunMetadata` | `EvaluationRunMetadata` | top-level |
| [ser_lib/services/evaluation.py:25](D:/projects/Speech-Emotion-Recognition/ser_lib/services/evaluation.py:25) | `ser_lib.engine.evaluation_runs` | `build_evaluation_run_metadata` | `build_evaluation_run_metadata` | top-level |
| [ser_lib/services/evaluation.py:25](D:/projects/Speech-Emotion-Recognition/ser_lib/services/evaluation.py:25) | `ser_lib.engine.evaluation_runs` | `load_evaluation_run_info` | `load_evaluation_run_info` | top-level |
| [ser_lib/services/evaluation.py:25](D:/projects/Speech-Emotion-Recognition/ser_lib/services/evaluation.py:25) | `ser_lib.engine.evaluation_runs` | `write_evaluation_run_info` | `write_evaluation_run_info` | top-level |
| [ser_lib/services/evaluation.py:32](D:/projects/Speech-Emotion-Recognition/ser_lib/services/evaluation.py:32) | `ser_lib.engine.evaluator` | `EvaluationResult` | `EvaluationResult` | top-level |
| [ser_lib/services/evaluation.py:32](D:/projects/Speech-Emotion-Recognition/ser_lib/services/evaluation.py:32) | `ser_lib.engine.evaluator` | `PredictionSink` | `PredictionSink` | top-level |
| [ser_lib/services/evaluation.py:32](D:/projects/Speech-Emotion-Recognition/ser_lib/services/evaluation.py:32) | `ser_lib.engine.evaluator` | `evaluate` | `evaluate` | top-level |
| [ser_lib/services/evaluation.py:32](D:/projects/Speech-Emotion-Recognition/ser_lib/services/evaluation.py:32) | `ser_lib.engine.evaluator` | `write_evaluation_report` | `write_evaluation_report` | top-level |
| [ser_lib/services/evaluation.py:38](D:/projects/Speech-Emotion-Recognition/ser_lib/services/evaluation.py:38) | `ser_lib.models.base` | `SERModel` | `SERModel` | top-level |
| [ser_lib/services/evaluation.py:57](D:/projects/Speech-Emotion-Recognition/ser_lib/services/evaluation.py:57) | `ser_lib` | `__version__` | `__version__` | local:create_run_metadata |
| [ser_lib/services/inference.py:9](D:/projects/Speech-Emotion-Recognition/ser_lib/services/inference.py:9) | `ser_lib.core.events` | `CancellationCheck` | `CancellationCheck` | top-level |
| [ser_lib/services/inference.py:9](D:/projects/Speech-Emotion-Recognition/ser_lib/services/inference.py:9) | `ser_lib.core.events` | `EventCallback` | `EventCallback` | top-level |
| [ser_lib/services/inference.py:10](D:/projects/Speech-Emotion-Recognition/ser_lib/services/inference.py:10) | `ser_lib.data.manifest` | `DatasetManifest` | `DatasetManifest` | top-level |
| [ser_lib/services/inference.py:11](D:/projects/Speech-Emotion-Recognition/ser_lib/services/inference.py:11) | `ser_lib.data.types` | `AudioRecord` | `AudioRecord` | top-level |
| [ser_lib/services/inference.py:12](D:/projects/Speech-Emotion-Recognition/ser_lib/services/inference.py:12) | `ser_lib.inference.batch` | `BatchEmotionPredictor` | `BatchEmotionPredictor` | top-level |
| [ser_lib/services/inference.py:12](D:/projects/Speech-Emotion-Recognition/ser_lib/services/inference.py:12) | `ser_lib.inference.batch` | `BatchPredictionResult` | `BatchPredictionResult` | top-level |
| [ser_lib/services/inference.py:12](D:/projects/Speech-Emotion-Recognition/ser_lib/services/inference.py:12) | `ser_lib.inference.batch` | `BatchPredictionSink` | `BatchPredictionSink` | top-level |
| [ser_lib/services/inference.py:12](D:/projects/Speech-Emotion-Recognition/ser_lib/services/inference.py:12) | `ser_lib.inference.batch` | `write_batch_predictions` | `_write_batch_predictions` | top-level |
| [ser_lib/services/inference.py:18](D:/projects/Speech-Emotion-Recognition/ser_lib/services/inference.py:18) | `ser_lib.inference.offline` | `EmotionPredictor` | `EmotionPredictor` | top-level |
| [ser_lib/services/inference.py:18](D:/projects/Speech-Emotion-Recognition/ser_lib/services/inference.py:18) | `ser_lib.inference.offline` | `PredictionResult` | `PredictionResult` | top-level |
| [ser_lib/services/inference.py:19](D:/projects/Speech-Emotion-Recognition/ser_lib/services/inference.py:19) | `ser_lib.inference.streaming` | `StreamingConfig` | `StreamingConfig` | top-level |
| [ser_lib/services/inference.py:19](D:/projects/Speech-Emotion-Recognition/ser_lib/services/inference.py:19) | `ser_lib.inference.streaming` | `StreamingEmotionRecognizer` | `StreamingEmotionRecognizer` | top-level |
| [ser_lib/services/inference.py:22](D:/projects/Speech-Emotion-Recognition/ser_lib/services/inference.py:22) | `ser_lib.artifacts` | `LoadedArtifact` | `LoadedArtifact` | TYPE_CHECKING |
| [ser_lib/services/runtime.py:7](D:/projects/Speech-Emotion-Recognition/ser_lib/services/runtime.py:7) | `ser_lib.runtime` | `RuntimeCapabilities` | `RuntimeCapabilities` | top-level |
| [ser_lib/services/runtime.py:7](D:/projects/Speech-Emotion-Recognition/ser_lib/services/runtime.py:7) | `ser_lib.runtime` | `RuntimeMetrics` | `RuntimeMetrics` | top-level |
| [ser_lib/services/runtime.py:7](D:/projects/Speech-Emotion-Recognition/ser_lib/services/runtime.py:7) | `ser_lib.runtime` | `get_runtime_capabilities` | `get_runtime_capabilities` | top-level |
| [ser_lib/services/runtime.py:7](D:/projects/Speech-Emotion-Recognition/ser_lib/services/runtime.py:7) | `ser_lib.runtime` | `get_runtime_metrics` | `get_runtime_metrics` | top-level |
| [ser_lib/services/training.py:8](D:/projects/Speech-Emotion-Recognition/ser_lib/services/training.py:8) | `ser_lib.core.diagnostics` | `Diagnostic` | `Diagnostic` | top-level |
| [ser_lib/services/training.py:9](D:/projects/Speech-Emotion-Recognition/ser_lib/services/training.py:9) | `ser_lib.core.events` | `CancellationCheck` | `CancellationCheck` | top-level |
| [ser_lib/services/training.py:9](D:/projects/Speech-Emotion-Recognition/ser_lib/services/training.py:9) | `ser_lib.core.events` | `EventCallback` | `EventCallback` | top-level |
| [ser_lib/services/training.py:10](D:/projects/Speech-Emotion-Recognition/ser_lib/services/training.py:10) | `ser_lib.data.types` | `SERBatch` | `SERBatch` | top-level |
| [ser_lib/services/training.py:11](D:/projects/Speech-Emotion-Recognition/ser_lib/services/training.py:11) | `ser_lib.engine.checkpoint_catalog` | `CheckpointCatalog` | `CheckpointCatalog` | top-level |
| [ser_lib/services/training.py:11](D:/projects/Speech-Emotion-Recognition/ser_lib/services/training.py:11) | `ser_lib.engine.checkpoint_catalog` | `CheckpointInfo` | `CheckpointInfo` | top-level |
| [ser_lib/services/training.py:11](D:/projects/Speech-Emotion-Recognition/ser_lib/services/training.py:11) | `ser_lib.engine.checkpoint_catalog` | `inspect_checkpoint_file` | `inspect_checkpoint_file` | top-level |
| [ser_lib/services/training.py:11](D:/projects/Speech-Emotion-Recognition/ser_lib/services/training.py:11) | `ser_lib.engine.checkpoint_catalog` | `scan_checkpoints` | `scan_checkpoint_files` | top-level |
| [ser_lib/services/training.py:17](D:/projects/Speech-Emotion-Recognition/ser_lib/services/training.py:17) | `ser_lib.engine.config` | `ExperimentConfig` | `ExperimentConfig` | top-level |
| [ser_lib/services/training.py:17](D:/projects/Speech-Emotion-Recognition/ser_lib/services/training.py:17) | `ser_lib.engine.config` | `ObservabilityConfig` | `ObservabilityConfig` | top-level |
| [ser_lib/services/training.py:18](D:/projects/Speech-Emotion-Recognition/ser_lib/services/training.py:18) | `ser_lib.engine.lineage` | `TrainingRunMetadata` | `TrainingRunMetadata` | top-level |
| [ser_lib/services/training.py:18](D:/projects/Speech-Emotion-Recognition/ser_lib/services/training.py:18) | `ser_lib.engine.lineage` | `build_training_run_metadata` | `build_training_run_metadata` | top-level |
| [ser_lib/services/training.py:19](D:/projects/Speech-Emotion-Recognition/ser_lib/services/training.py:19) | `ser_lib.engine.runs` | `TrainingRunCatalog` | `TrainingRunCatalog` | top-level |
| [ser_lib/services/training.py:19](D:/projects/Speech-Emotion-Recognition/ser_lib/services/training.py:19) | `ser_lib.engine.runs` | `TrainingRunDetail` | `TrainingRunDetail` | top-level |
| [ser_lib/services/training.py:19](D:/projects/Speech-Emotion-Recognition/ser_lib/services/training.py:19) | `ser_lib.engine.runs` | `TrainingRunInfo` | `TrainingRunInfo` | top-level |
| [ser_lib/services/training.py:19](D:/projects/Speech-Emotion-Recognition/ser_lib/services/training.py:19) | `ser_lib.engine.runs` | `load_training_run_info` | `load_training_run_info` | top-level |
| [ser_lib/services/training.py:19](D:/projects/Speech-Emotion-Recognition/ser_lib/services/training.py:19) | `ser_lib.engine.runs` | `scan_training_runs` | `scan_training_runs` | top-level |
| [ser_lib/services/training.py:19](D:/projects/Speech-Emotion-Recognition/ser_lib/services/training.py:19) | `ser_lib.engine.runs` | `write_training_run_info` | `write_training_run_info` | top-level |
| [ser_lib/services/training.py:27](D:/projects/Speech-Emotion-Recognition/ser_lib/services/training.py:27) | `ser_lib.engine.training_history` | `TrainingHistoryInfo` | `TrainingHistoryInfo` | top-level |
| [ser_lib/services/training.py:27](D:/projects/Speech-Emotion-Recognition/ser_lib/services/training.py:27) | `ser_lib.engine.training_history` | `load_training_history` | `load_training_history` | top-level |
| [ser_lib/services/training.py:28](D:/projects/Speech-Emotion-Recognition/ser_lib/services/training.py:28) | `ser_lib.engine.trainer` | `EpochResult` | `EpochResult` | top-level |
| [ser_lib/services/training.py:28](D:/projects/Speech-Emotion-Recognition/ser_lib/services/training.py:28) | `ser_lib.engine.trainer` | `Trainer` | `Trainer` | top-level |
| [ser_lib/services/training.py:28](D:/projects/Speech-Emotion-Recognition/ser_lib/services/training.py:28) | `ser_lib.engine.trainer` | `TrainingResult` | `TrainingResult` | top-level |
| [ser_lib/services/training.py:29](D:/projects/Speech-Emotion-Recognition/ser_lib/services/training.py:29) | `ser_lib.engine.validation` | `ExperimentValidationResult` | `ExperimentValidationResult` | top-level |
| [ser_lib/services/training.py:29](D:/projects/Speech-Emotion-Recognition/ser_lib/services/training.py:29) | `ser_lib.engine.validation` | `validate_experiment` | `validate_experiment` | top-level |
| [ser_lib/services/training.py:30](D:/projects/Speech-Emotion-Recognition/ser_lib/services/training.py:30) | `ser_lib.models.base` | `SERModel` | `SERModel` | top-level |
| [ser_lib/services/training.py:68](D:/projects/Speech-Emotion-Recognition/ser_lib/services/training.py:68) | `ser_lib` | `__version__` | `__version__` | local:create_trainer |

### D.2 测试/脚本/示例直接消费者

| 调用/导入方 | 来源模块 | 符号 | 本地名 | 作用域 |
| --- | --- | --- | --- | --- |
| [benchmarks/benchmark_data_pipeline.py:11](D:/projects/Speech-Emotion-Recognition/benchmarks/benchmark_data_pipeline.py:11) | `ser_lib.data` | `DatasetManifest` | `DatasetManifest` | top-level |
| [benchmarks/benchmark_data_pipeline.py:11](D:/projects/Speech-Emotion-Recognition/benchmarks/benchmark_data_pipeline.py:11) | `ser_lib.data` | `SERDataset` | `SERDataset` | top-level |
| [benchmarks/benchmark_data_pipeline.py:11](D:/projects/Speech-Emotion-Recognition/benchmarks/benchmark_data_pipeline.py:11) | `ser_lib.data` | `build_collator` | `build_collator` | top-level |
| [benchmarks/benchmark_data_pipeline.py:11](D:/projects/Speech-Emotion-Recognition/benchmarks/benchmark_data_pipeline.py:11) | `ser_lib.data` | `build_components` | `build_components` | top-level |
| [benchmarks/benchmark_data_pipeline.py:11](D:/projects/Speech-Emotion-Recognition/benchmarks/benchmark_data_pipeline.py:11) | `ser_lib.data` | `load_data_config` | `load_data_config` | top-level |
| [examples/inspect_runs_and_presets.py:12](D:/projects/Speech-Emotion-Recognition/examples/inspect_runs_and_presets.py:12) | `ser_lib.services` | `CatalogService` | `CatalogService` | top-level |
| [examples/inspect_runs_and_presets.py:12](D:/projects/Speech-Emotion-Recognition/examples/inspect_runs_and_presets.py:12) | `ser_lib.services` | `EvaluationService` | `EvaluationService` | top-level |
| [examples/inspect_runs_and_presets.py:12](D:/projects/Speech-Emotion-Recognition/examples/inspect_runs_and_presets.py:12) | `ser_lib.services` | `RuntimeService` | `RuntimeService` | top-level |
| [examples/inspect_runs_and_presets.py:12](D:/projects/Speech-Emotion-Recognition/examples/inspect_runs_and_presets.py:12) | `ser_lib.services` | `TrainingService` | `TrainingService` | top-level |
| [examples/predict_artifact.py:8](D:/projects/Speech-Emotion-Recognition/examples/predict_artifact.py:8) | `ser_lib.artifacts` | `load_model_artifact` | `load_model_artifact` | top-level |
| [examples/predict_artifact.py:9](D:/projects/Speech-Emotion-Recognition/examples/predict_artifact.py:9) | `ser_lib.inference` | `EmotionPredictor` | `EmotionPredictor` | top-level |
| [examples/train_from_python.py:10](D:/projects/Speech-Emotion-Recognition/examples/train_from_python.py:10) | `ser_lib.data` | `DatasetManifest` | `DatasetManifest` | top-level |
| [examples/train_from_python.py:10](D:/projects/Speech-Emotion-Recognition/examples/train_from_python.py:10) | `ser_lib.data` | `SERDataset` | `SERDataset` | top-level |
| [examples/train_from_python.py:11](D:/projects/Speech-Emotion-Recognition/examples/train_from_python.py:11) | `ser_lib.engine` | `Trainer` | `Trainer` | top-level |
| [examples/train_from_python.py:11](D:/projects/Speech-Emotion-Recognition/examples/train_from_python.py:11) | `ser_lib.engine` | `build_experiment_components` | `build_experiment_components` | top-level |
| [examples/train_from_python.py:11](D:/projects/Speech-Emotion-Recognition/examples/train_from_python.py:11) | `ser_lib.engine` | `load_experiment_config` | `load_experiment_config` | top-level |
| [scripts/prepare_casia.py:8](D:/projects/Speech-Emotion-Recognition/scripts/prepare_casia.py:8) | `ser_lib.data.importers.casia` | `CASIA_EMOTION_MAPPING` | `CASIA_EMOTION_MAPPING` | top-level |
| [scripts/prepare_casia.py:8](D:/projects/Speech-Emotion-Recognition/scripts/prepare_casia.py:8) | `ser_lib.data.importers.casia` | `CASIA_EMOTION_ZH` | `CASIA_EMOTION_ZH` | top-level |
| [scripts/prepare_casia.py:8](D:/projects/Speech-Emotion-Recognition/scripts/prepare_casia.py:8) | `ser_lib.data.importers.casia` | `CasiaImporter` | `CasiaImporter` | top-level |
| [scripts/prepare_casia.py:13](D:/projects/Speech-Emotion-Recognition/scripts/prepare_casia.py:13) | `ser_lib.data.manifest` | `DatasetManifest` | `DatasetManifest` | top-level |
| [scripts/prepare_casia.py:13](D:/projects/Speech-Emotion-Recognition/scripts/prepare_casia.py:13) | `ser_lib.data.manifest` | `ManifestMeta` | `ManifestMeta` | top-level |
| [scripts/smoke_train_epoch.py:20](D:/projects/Speech-Emotion-Recognition/scripts/smoke_train_epoch.py:20) | `ser_lib.data.audio` | `AudioLoader` | `AudioLoader` | top-level |
| [scripts/smoke_train_epoch.py:20](D:/projects/Speech-Emotion-Recognition/scripts/smoke_train_epoch.py:20) | `ser_lib.data.audio` | `AudioLoaderConfig` | `AudioLoaderConfig` | top-level |
| [scripts/smoke_train_epoch.py:21](D:/projects/Speech-Emotion-Recognition/scripts/smoke_train_epoch.py:21) | `ser_lib.data.collate` | `SERCollator` | `SERCollator` | top-level |
| [scripts/smoke_train_epoch.py:22](D:/projects/Speech-Emotion-Recognition/scripts/smoke_train_epoch.py:22) | `ser_lib.data.config` | `BatchingConfig` | `BatchingConfig` | top-level |
| [scripts/smoke_train_epoch.py:23](D:/projects/Speech-Emotion-Recognition/scripts/smoke_train_epoch.py:23) | `ser_lib.data.dataset` | `SERDataset` | `SERDataset` | top-level |
| [scripts/smoke_train_epoch.py:24](D:/projects/Speech-Emotion-Recognition/scripts/smoke_train_epoch.py:24) | `ser_lib.data.pipeline` | `SamplePipeline` | `SamplePipeline` | top-level |
| [scripts/smoke_train_epoch.py:25](D:/projects/Speech-Emotion-Recognition/scripts/smoke_train_epoch.py:25) | `ser_lib.data.representations.spectral` | `LogMelRepresentation` | `LogMelRepresentation` | top-level |
| [scripts/smoke_train_epoch.py:26](D:/projects/Speech-Emotion-Recognition/scripts/smoke_train_epoch.py:26) | `ser_lib.data.types` | `AudioRecord` | `AudioRecord` | top-level |
| [scripts/smoke_train_epoch.py:27](D:/projects/Speech-Emotion-Recognition/scripts/smoke_train_epoch.py:27) | `ser_lib.engine.trainer` | `Trainer` | `Trainer` | top-level |
| [scripts/smoke_train_epoch.py:27](D:/projects/Speech-Emotion-Recognition/scripts/smoke_train_epoch.py:27) | `ser_lib.engine.trainer` | `TrainerConfig` | `TrainerConfig` | top-level |
| [scripts/smoke_train_epoch.py:28](D:/projects/Speech-Emotion-Recognition/scripts/smoke_train_epoch.py:28) | `ser_lib.models.cnn_models` | `CNNBaseline` | `CNNBaseline` | top-level |
| [tests/test_artifact_catalog.py:4](D:/projects/Speech-Emotion-Recognition/tests/test_artifact_catalog.py:4) | `ser_lib.artifacts` | `scan_model_artifacts` | `scan_model_artifacts` | top-level |
| [tests/test_artifact_catalog.py:5](D:/projects/Speech-Emotion-Recognition/tests/test_artifact_catalog.py:5) | `ser_lib.core` | `ProgressEvent` | `ProgressEvent` | top-level |
| [tests/test_artifact_catalog.py:6](D:/projects/Speech-Emotion-Recognition/tests/test_artifact_catalog.py:6) | `ser_lib.data.config` | `AudioSettings` | `AudioSettings` | top-level |
| [tests/test_artifact_catalog.py:6](D:/projects/Speech-Emotion-Recognition/tests/test_artifact_catalog.py:6) | `ser_lib.data.config` | `BatchingConfig` | `BatchingConfig` | top-level |
| [tests/test_artifact_catalog.py:6](D:/projects/Speech-Emotion-Recognition/tests/test_artifact_catalog.py:6) | `ser_lib.data.config` | `ComponentConfig` | `ComponentConfig` | top-level |
| [tests/test_artifact_catalog.py:6](D:/projects/Speech-Emotion-Recognition/tests/test_artifact_catalog.py:6) | `ser_lib.data.config` | `DataConfig` | `DataConfig` | top-level |
| [tests/test_artifact_catalog.py:7](D:/projects/Speech-Emotion-Recognition/tests/test_artifact_catalog.py:7) | `ser_lib.models` | `CNNBaseline` | `CNNBaseline` | top-level |
| [tests/test_artifact_catalog.py:8](D:/projects/Speech-Emotion-Recognition/tests/test_artifact_catalog.py:8) | `ser_lib.services` | `ArtifactService` | `ArtifactService` | top-level |
| [tests/test_artifact_catalog.py:55](D:/projects/Speech-Emotion-Recognition/tests/test_artifact_catalog.py:55) | `ser_lib.artifacts.loader` | `(module)` | `loader_module` | local:test_artifact_catalog_scans_without_hashing_and_exposes_management_metadata |
| [tests/test_artifact_inspect.py:5](D:/projects/Speech-Emotion-Recognition/tests/test_artifact_inspect.py:5) | `ser_lib.artifacts.loader` | `(module)` | `loader_module` | top-level |
| [tests/test_artifact_inspect.py:6](D:/projects/Speech-Emotion-Recognition/tests/test_artifact_inspect.py:6) | `ser_lib.artifacts` | `export_model_artifact` | `export_model_artifact` | top-level |
| [tests/test_artifact_inspect.py:6](D:/projects/Speech-Emotion-Recognition/tests/test_artifact_inspect.py:6) | `ser_lib.artifacts` | `inspect_model_artifact` | `inspect_model_artifact` | top-level |
| [tests/test_artifact_inspect.py:6](D:/projects/Speech-Emotion-Recognition/tests/test_artifact_inspect.py:6) | `ser_lib.artifacts` | `verify_model_artifact` | `verify_model_artifact` | top-level |
| [tests/test_artifact_inspect.py:11](D:/projects/Speech-Emotion-Recognition/tests/test_artifact_inspect.py:11) | `ser_lib.data.config` | `AudioSettings` | `AudioSettings` | top-level |
| [tests/test_artifact_inspect.py:11](D:/projects/Speech-Emotion-Recognition/tests/test_artifact_inspect.py:11) | `ser_lib.data.config` | `BatchingConfig` | `BatchingConfig` | top-level |
| [tests/test_artifact_inspect.py:11](D:/projects/Speech-Emotion-Recognition/tests/test_artifact_inspect.py:11) | `ser_lib.data.config` | `ComponentConfig` | `ComponentConfig` | top-level |
| [tests/test_artifact_inspect.py:11](D:/projects/Speech-Emotion-Recognition/tests/test_artifact_inspect.py:11) | `ser_lib.data.config` | `DataConfig` | `DataConfig` | top-level |
| [tests/test_artifact_inspect.py:12](D:/projects/Speech-Emotion-Recognition/tests/test_artifact_inspect.py:12) | `ser_lib.models` | `CNNBaseline` | `CNNBaseline` | top-level |
| [tests/test_artifact_progress.py:5](D:/projects/Speech-Emotion-Recognition/tests/test_artifact_progress.py:5) | `ser_lib.artifacts` | `export_model_artifact` | `export_model_artifact` | top-level |
| [tests/test_artifact_progress.py:5](D:/projects/Speech-Emotion-Recognition/tests/test_artifact_progress.py:5) | `ser_lib.artifacts` | `verify_model_artifact` | `verify_model_artifact` | top-level |
| [tests/test_artifact_progress.py:6](D:/projects/Speech-Emotion-Recognition/tests/test_artifact_progress.py:6) | `ser_lib.core` | `CancellationToken` | `CancellationToken` | top-level |
| [tests/test_artifact_progress.py:6](D:/projects/Speech-Emotion-Recognition/tests/test_artifact_progress.py:6) | `ser_lib.core` | `LifecycleEvent` | `LifecycleEvent` | top-level |
| [tests/test_artifact_progress.py:6](D:/projects/Speech-Emotion-Recognition/tests/test_artifact_progress.py:6) | `ser_lib.core` | `OperationCancelled` | `OperationCancelled` | top-level |
| [tests/test_artifact_progress.py:6](D:/projects/Speech-Emotion-Recognition/tests/test_artifact_progress.py:6) | `ser_lib.core` | `ProgressEvent` | `ProgressEvent` | top-level |
| [tests/test_artifact_progress.py:12](D:/projects/Speech-Emotion-Recognition/tests/test_artifact_progress.py:12) | `ser_lib.data.config` | `AudioSettings` | `AudioSettings` | top-level |
| [tests/test_artifact_progress.py:12](D:/projects/Speech-Emotion-Recognition/tests/test_artifact_progress.py:12) | `ser_lib.data.config` | `BatchingConfig` | `BatchingConfig` | top-level |
| [tests/test_artifact_progress.py:12](D:/projects/Speech-Emotion-Recognition/tests/test_artifact_progress.py:12) | `ser_lib.data.config` | `ComponentConfig` | `ComponentConfig` | top-level |
| [tests/test_artifact_progress.py:12](D:/projects/Speech-Emotion-Recognition/tests/test_artifact_progress.py:12) | `ser_lib.data.config` | `DataConfig` | `DataConfig` | top-level |
| [tests/test_artifact_progress.py:13](D:/projects/Speech-Emotion-Recognition/tests/test_artifact_progress.py:13) | `ser_lib.models` | `CNNBaseline` | `CNNBaseline` | top-level |
| [tests/test_artifacts.py:8](D:/projects/Speech-Emotion-Recognition/tests/test_artifacts.py:8) | `ser_lib` | `__version__` | `__version__` | top-level |
| [tests/test_artifacts.py:9](D:/projects/Speech-Emotion-Recognition/tests/test_artifacts.py:9) | `ser_lib.artifacts` | `ModelCard` | `ModelCard` | top-level |
| [tests/test_artifacts.py:9](D:/projects/Speech-Emotion-Recognition/tests/test_artifacts.py:9) | `ser_lib.artifacts` | `export_model_artifact` | `export_model_artifact` | top-level |
| [tests/test_artifacts.py:9](D:/projects/Speech-Emotion-Recognition/tests/test_artifacts.py:9) | `ser_lib.artifacts` | `load_model_artifact` | `load_model_artifact` | top-level |
| [tests/test_artifacts.py:9](D:/projects/Speech-Emotion-Recognition/tests/test_artifacts.py:9) | `ser_lib.artifacts` | `verify_model_artifact` | `verify_model_artifact` | top-level |
| [tests/test_artifacts.py:15](D:/projects/Speech-Emotion-Recognition/tests/test_artifacts.py:15) | `ser_lib.data.config` | `AudioSettings` | `AudioSettings` | top-level |
| [tests/test_artifacts.py:15](D:/projects/Speech-Emotion-Recognition/tests/test_artifacts.py:15) | `ser_lib.data.config` | `BatchingConfig` | `BatchingConfig` | top-level |
| [tests/test_artifacts.py:15](D:/projects/Speech-Emotion-Recognition/tests/test_artifacts.py:15) | `ser_lib.data.config` | `ComponentConfig` | `ComponentConfig` | top-level |
| [tests/test_artifacts.py:15](D:/projects/Speech-Emotion-Recognition/tests/test_artifacts.py:15) | `ser_lib.data.config` | `DataConfig` | `DataConfig` | top-level |
| [tests/test_artifacts.py:16](D:/projects/Speech-Emotion-Recognition/tests/test_artifacts.py:16) | `ser_lib.models` | `CNNBaseline` | `CNNBaseline` | top-level |
| [tests/test_audio_pipeline.py:9](D:/projects/Speech-Emotion-Recognition/tests/test_audio_pipeline.py:9) | `ser_lib.data.audio` | `AudioLoader` | `AudioLoader` | top-level |
| [tests/test_audio_pipeline.py:9](D:/projects/Speech-Emotion-Recognition/tests/test_audio_pipeline.py:9) | `ser_lib.data.audio` | `AudioLoaderConfig` | `AudioLoaderConfig` | top-level |
| [tests/test_audio_pipeline.py:10](D:/projects/Speech-Emotion-Recognition/tests/test_audio_pipeline.py:10) | `ser_lib.data.collate` | `SERCollator` | `SERCollator` | top-level |
| [tests/test_audio_pipeline.py:11](D:/projects/Speech-Emotion-Recognition/tests/test_audio_pipeline.py:11) | `ser_lib.data.config` | `BatchingConfig` | `BatchingConfig` | top-level |
| [tests/test_audio_pipeline.py:12](D:/projects/Speech-Emotion-Recognition/tests/test_audio_pipeline.py:12) | `ser_lib.data.dataset` | `SERDataset` | `SERDataset` | top-level |
| [tests/test_audio_pipeline.py:13](D:/projects/Speech-Emotion-Recognition/tests/test_audio_pipeline.py:13) | `ser_lib.data.errors` | `AudioNotFoundError` | `AudioNotFoundError` | top-level |
| [tests/test_audio_pipeline.py:13](D:/projects/Speech-Emotion-Recognition/tests/test_audio_pipeline.py:13) | `ser_lib.data.errors` | `InvalidAudioSegmentError` | `InvalidAudioSegmentError` | top-level |
| [tests/test_audio_pipeline.py:14](D:/projects/Speech-Emotion-Recognition/tests/test_audio_pipeline.py:14) | `ser_lib.data.pipeline` | `SamplePipeline` | `SamplePipeline` | top-level |
| [tests/test_audio_pipeline.py:15](D:/projects/Speech-Emotion-Recognition/tests/test_audio_pipeline.py:15) | `ser_lib.data.representations.spectral` | `MFCCRepresentation` | `MFCCRepresentation` | top-level |
| [tests/test_audio_pipeline.py:16](D:/projects/Speech-Emotion-Recognition/tests/test_audio_pipeline.py:16) | `ser_lib.data.representations.waveform` | `RawWaveform` | `RawWaveform` | top-level |
| [tests/test_audio_pipeline.py:17](D:/projects/Speech-Emotion-Recognition/tests/test_audio_pipeline.py:17) | `ser_lib.data.types` | `AudioRecord` | `AudioRecord` | top-level |
| [tests/test_batch_inference.py:10](D:/projects/Speech-Emotion-Recognition/tests/test_batch_inference.py:10) | `ser_lib.core` | `CancellationToken` | `CancellationToken` | top-level |
| [tests/test_batch_inference.py:10](D:/projects/Speech-Emotion-Recognition/tests/test_batch_inference.py:10) | `ser_lib.core` | `OperationCancelled` | `OperationCancelled` | top-level |
| [tests/test_batch_inference.py:10](D:/projects/Speech-Emotion-Recognition/tests/test_batch_inference.py:10) | `ser_lib.core` | `ProgressEvent` | `ProgressEvent` | top-level |
| [tests/test_batch_inference.py:11](D:/projects/Speech-Emotion-Recognition/tests/test_batch_inference.py:11) | `ser_lib.data` | `AudioRecord` | `AudioRecord` | top-level |
| [tests/test_batch_inference.py:11](D:/projects/Speech-Emotion-Recognition/tests/test_batch_inference.py:11) | `ser_lib.data` | `BatchingConfig` | `BatchingConfig` | top-level |
| [tests/test_batch_inference.py:11](D:/projects/Speech-Emotion-Recognition/tests/test_batch_inference.py:11) | `ser_lib.data` | `DatasetManifest` | `DatasetManifest` | top-level |
| [tests/test_batch_inference.py:11](D:/projects/Speech-Emotion-Recognition/tests/test_batch_inference.py:11) | `ser_lib.data` | `ManifestMeta` | `ManifestMeta` | top-level |
| [tests/test_batch_inference.py:11](D:/projects/Speech-Emotion-Recognition/tests/test_batch_inference.py:11) | `ser_lib.data` | `SERCollator` | `SERCollator` | top-level |
| [tests/test_batch_inference.py:11](D:/projects/Speech-Emotion-Recognition/tests/test_batch_inference.py:11) | `ser_lib.data` | `SERSample` | `SERSample` | top-level |
| [tests/test_batch_inference.py:11](D:/projects/Speech-Emotion-Recognition/tests/test_batch_inference.py:11) | `ser_lib.data` | `TensorSpec` | `TensorSpec` | top-level |
| [tests/test_batch_inference.py:20](D:/projects/Speech-Emotion-Recognition/tests/test_batch_inference.py:20) | `ser_lib.data.validation` | `ModelSpec` | `ModelSpec` | top-level |
| [tests/test_batch_inference.py:21](D:/projects/Speech-Emotion-Recognition/tests/test_batch_inference.py:21) | `ser_lib.inference` | `BatchEmotionPredictor` | `BatchEmotionPredictor` | top-level |
| [tests/test_batch_inference.py:21](D:/projects/Speech-Emotion-Recognition/tests/test_batch_inference.py:21) | `ser_lib.inference` | `EmotionPredictor` | `EmotionPredictor` | top-level |
| [tests/test_batch_inference.py:21](D:/projects/Speech-Emotion-Recognition/tests/test_batch_inference.py:21) | `ser_lib.inference` | `PredictionResult` | `PredictionResult` | top-level |
| [tests/test_batch_inference.py:21](D:/projects/Speech-Emotion-Recognition/tests/test_batch_inference.py:21) | `ser_lib.inference` | `write_batch_predictions` | `write_batch_predictions` | top-level |
| [tests/test_batch_inference.py:27](D:/projects/Speech-Emotion-Recognition/tests/test_batch_inference.py:27) | `ser_lib.models` | `ModelOutput` | `ModelOutput` | top-level |
| [tests/test_batch_inference.py:27](D:/projects/Speech-Emotion-Recognition/tests/test_batch_inference.py:27) | `ser_lib.models` | `SERModel` | `SERModel` | top-level |
| [tests/test_batch_prediction_events.py:4](D:/projects/Speech-Emotion-Recognition/tests/test_batch_prediction_events.py:4) | `ser_lib.core` | `EventContext` | `EventContext` | top-level |
| [tests/test_batch_prediction_events.py:4](D:/projects/Speech-Emotion-Recognition/tests/test_batch_prediction_events.py:4) | `ser_lib.core` | `PredictionEvent` | `PredictionEvent` | top-level |
| [tests/test_batch_prediction_events.py:4](D:/projects/Speech-Emotion-Recognition/tests/test_batch_prediction_events.py:4) | `ser_lib.core` | `ProgressEvent` | `ProgressEvent` | top-level |
| [tests/test_batch_prediction_events.py:5](D:/projects/Speech-Emotion-Recognition/tests/test_batch_prediction_events.py:5) | `ser_lib.data` | `AudioRecord` | `AudioRecord` | top-level |
| [tests/test_batch_prediction_events.py:6](D:/projects/Speech-Emotion-Recognition/tests/test_batch_prediction_events.py:6) | `ser_lib.inference` | `BatchEmotionPredictor` | `BatchEmotionPredictor` | top-level |
| [tests/test_batch_prediction_events.py:6](D:/projects/Speech-Emotion-Recognition/tests/test_batch_prediction_events.py:6) | `ser_lib.inference` | `PredictionResult` | `PredictionResult` | top-level |
| [tests/test_batch_prediction_sink.py:8](D:/projects/Speech-Emotion-Recognition/tests/test_batch_prediction_sink.py:8) | `ser_lib.data` | `AudioRecord` | `AudioRecord` | top-level |
| [tests/test_batch_prediction_sink.py:9](D:/projects/Speech-Emotion-Recognition/tests/test_batch_prediction_sink.py:9) | `ser_lib.inference` | `BatchEmotionPredictor` | `BatchEmotionPredictor` | top-level |
| [tests/test_batch_prediction_sink.py:9](D:/projects/Speech-Emotion-Recognition/tests/test_batch_prediction_sink.py:9) | `ser_lib.inference` | `JsonlBatchPredictionSink` | `JsonlBatchPredictionSink` | top-level |
| [tests/test_batch_prediction_sink.py:9](D:/projects/Speech-Emotion-Recognition/tests/test_batch_prediction_sink.py:9) | `ser_lib.inference` | `PredictionResult` | `PredictionResult` | top-level |
| [tests/test_batch_prediction_sink.py:9](D:/projects/Speech-Emotion-Recognition/tests/test_batch_prediction_sink.py:9) | `ser_lib.inference` | `write_batch_predictions` | `write_batch_predictions` | top-level |
| [tests/test_batch_prediction_sink.py:15](D:/projects/Speech-Emotion-Recognition/tests/test_batch_prediction_sink.py:15) | `ser_lib.services` | `InferenceService` | `InferenceService` | top-level |
| [tests/test_cache.py:5](D:/projects/Speech-Emotion-Recognition/tests/test_cache.py:5) | `ser_lib.data.cache` | `CachedRepresentation` | `CachedRepresentation` | top-level |
| [tests/test_cache.py:6](D:/projects/Speech-Emotion-Recognition/tests/test_cache.py:6) | `ser_lib.data.config` | `AudioSettings` | `AudioSettings` | top-level |
| [tests/test_cache.py:6](D:/projects/Speech-Emotion-Recognition/tests/test_cache.py:6) | `ser_lib.data.config` | `BatchingConfig` | `BatchingConfig` | top-level |
| [tests/test_cache.py:6](D:/projects/Speech-Emotion-Recognition/tests/test_cache.py:6) | `ser_lib.data.config` | `CacheSettings` | `CacheSettings` | top-level |
| [tests/test_cache.py:6](D:/projects/Speech-Emotion-Recognition/tests/test_cache.py:6) | `ser_lib.data.config` | `ComponentConfig` | `ComponentConfig` | top-level |
| [tests/test_cache.py:6](D:/projects/Speech-Emotion-Recognition/tests/test_cache.py:6) | `ser_lib.data.config` | `DataConfig` | `DataConfig` | top-level |
| [tests/test_cache.py:9](D:/projects/Speech-Emotion-Recognition/tests/test_cache.py:9) | `ser_lib.data.pipeline` | `build_pipeline` | `build_pipeline` | top-level |
| [tests/test_cache.py:10](D:/projects/Speech-Emotion-Recognition/tests/test_cache.py:10) | `ser_lib.data.registry` | `ComponentDescriptor` | `ComponentDescriptor` | top-level |
| [tests/test_cache.py:11](D:/projects/Speech-Emotion-Recognition/tests/test_cache.py:11) | `ser_lib.data.representations.base` | `Representation` | `Representation` | top-level |
| [tests/test_cache.py:12](D:/projects/Speech-Emotion-Recognition/tests/test_cache.py:12) | `ser_lib.data.types` | `AudioData` | `AudioData` | top-level |
| [tests/test_cache.py:12](D:/projects/Speech-Emotion-Recognition/tests/test_cache.py:12) | `ser_lib.data.types` | `RepresentationOutput` | `RepresentationOutput` | top-level |
| [tests/test_cache.py:12](D:/projects/Speech-Emotion-Recognition/tests/test_cache.py:12) | `ser_lib.data.types` | `TensorSpec` | `TensorSpec` | top-level |
| [tests/test_checkpoint_catalog.py:8](D:/projects/Speech-Emotion-Recognition/tests/test_checkpoint_catalog.py:8) | `ser_lib.core` | `CancellationToken` | `CancellationToken` | top-level |
| [tests/test_checkpoint_catalog.py:8](D:/projects/Speech-Emotion-Recognition/tests/test_checkpoint_catalog.py:8) | `ser_lib.core` | `OperationCancelled` | `OperationCancelled` | top-level |
| [tests/test_checkpoint_catalog.py:8](D:/projects/Speech-Emotion-Recognition/tests/test_checkpoint_catalog.py:8) | `ser_lib.core` | `ProgressEvent` | `ProgressEvent` | top-level |
| [tests/test_checkpoint_catalog.py:9](D:/projects/Speech-Emotion-Recognition/tests/test_checkpoint_catalog.py:9) | `ser_lib.engine` | `inspect_checkpoint_file` | `inspect_checkpoint_file` | top-level |
| [tests/test_checkpoint_catalog.py:9](D:/projects/Speech-Emotion-Recognition/tests/test_checkpoint_catalog.py:9) | `ser_lib.engine` | `scan_checkpoints` | `scan_checkpoints` | top-level |
| [tests/test_checkpoint_catalog.py:10](D:/projects/Speech-Emotion-Recognition/tests/test_checkpoint_catalog.py:10) | `ser_lib.services` | `TrainingService` | `TrainingService` | top-level |
| [tests/test_checkpoint_resume.py:9](D:/projects/Speech-Emotion-Recognition/tests/test_checkpoint_resume.py:9) | `ser_lib.core` | `CancellationToken` | `CancellationToken` | top-level |
| [tests/test_checkpoint_resume.py:9](D:/projects/Speech-Emotion-Recognition/tests/test_checkpoint_resume.py:9) | `ser_lib.core` | `OperationCancelled` | `OperationCancelled` | top-level |
| [tests/test_checkpoint_resume.py:10](D:/projects/Speech-Emotion-Recognition/tests/test_checkpoint_resume.py:10) | `ser_lib.data` | `BatchingConfig` | `BatchingConfig` | top-level |
| [tests/test_checkpoint_resume.py:10](D:/projects/Speech-Emotion-Recognition/tests/test_checkpoint_resume.py:10) | `ser_lib.data` | `SERCollator` | `SERCollator` | top-level |
| [tests/test_checkpoint_resume.py:10](D:/projects/Speech-Emotion-Recognition/tests/test_checkpoint_resume.py:10) | `ser_lib.data` | `SERSample` | `SERSample` | top-level |
| [tests/test_checkpoint_resume.py:10](D:/projects/Speech-Emotion-Recognition/tests/test_checkpoint_resume.py:10) | `ser_lib.data` | `TensorSpec` | `TensorSpec` | top-level |
| [tests/test_checkpoint_resume.py:11](D:/projects/Speech-Emotion-Recognition/tests/test_checkpoint_resume.py:11) | `ser_lib.data.config` | `AudioSettings` | `AudioSettings` | top-level |
| [tests/test_checkpoint_resume.py:11](D:/projects/Speech-Emotion-Recognition/tests/test_checkpoint_resume.py:11) | `ser_lib.data.config` | `ComponentConfig` | `ComponentConfig` | top-level |
| [tests/test_checkpoint_resume.py:11](D:/projects/Speech-Emotion-Recognition/tests/test_checkpoint_resume.py:11) | `ser_lib.data.config` | `DataConfig` | `DataConfig` | top-level |
| [tests/test_checkpoint_resume.py:12](D:/projects/Speech-Emotion-Recognition/tests/test_checkpoint_resume.py:12) | `ser_lib.engine` | `ExperimentConfig` | `ExperimentConfig` | top-level |
| [tests/test_checkpoint_resume.py:12](D:/projects/Speech-Emotion-Recognition/tests/test_checkpoint_resume.py:12) | `ser_lib.engine` | `ModelConfig` | `ModelConfig` | top-level |
| [tests/test_checkpoint_resume.py:12](D:/projects/Speech-Emotion-Recognition/tests/test_checkpoint_resume.py:12) | `ser_lib.engine` | `Trainer` | `Trainer` | top-level |
| [tests/test_checkpoint_resume.py:12](D:/projects/Speech-Emotion-Recognition/tests/test_checkpoint_resume.py:12) | `ser_lib.engine` | `TrainerConfig` | `TrainerConfig` | top-level |
| [tests/test_checkpoint_resume.py:12](D:/projects/Speech-Emotion-Recognition/tests/test_checkpoint_resume.py:12) | `ser_lib.engine` | `load_checkpoint` | `load_checkpoint` | top-level |
| [tests/test_checkpoint_resume.py:12](D:/projects/Speech-Emotion-Recognition/tests/test_checkpoint_resume.py:12) | `ser_lib.engine` | `save_checkpoint` | `save_checkpoint` | top-level |
| [tests/test_checkpoint_resume.py:20](D:/projects/Speech-Emotion-Recognition/tests/test_checkpoint_resume.py:20) | `ser_lib.models` | `CNNBaseline` | `CNNBaseline` | top-level |
| [tests/test_cli.py:12](D:/projects/Speech-Emotion-Recognition/tests/test_cli.py:12) | `ser_lib.cli.main` | `EXIT_CONFIG` | `EXIT_CONFIG` | top-level |
| [tests/test_cli.py:12](D:/projects/Speech-Emotion-Recognition/tests/test_cli.py:12) | `ser_lib.cli.main` | `EXIT_DATA` | `EXIT_DATA` | top-level |
| [tests/test_cli.py:12](D:/projects/Speech-Emotion-Recognition/tests/test_cli.py:12) | `ser_lib.cli.main` | `EXIT_OK` | `EXIT_OK` | top-level |
| [tests/test_cli.py:12](D:/projects/Speech-Emotion-Recognition/tests/test_cli.py:12) | `ser_lib.cli.main` | `main` | `main` | top-level |
| [tests/test_cli_lineage.py:11](D:/projects/Speech-Emotion-Recognition/tests/test_cli_lineage.py:11) | `ser_lib.artifacts` | `inspect_model_artifact` | `inspect_model_artifact` | top-level |
| [tests/test_cli_lineage.py:12](D:/projects/Speech-Emotion-Recognition/tests/test_cli_lineage.py:12) | `ser_lib.cli.workflows` | `evaluate_artifact` | `evaluate_artifact` | top-level |
| [tests/test_cli_lineage.py:12](D:/projects/Speech-Emotion-Recognition/tests/test_cli_lineage.py:12) | `ser_lib.cli.workflows` | `export_checkpoint_artifact` | `export_checkpoint_artifact` | top-level |
| [tests/test_cli_lineage.py:12](D:/projects/Speech-Emotion-Recognition/tests/test_cli_lineage.py:12) | `ser_lib.cli.workflows` | `train_experiment` | `train_experiment` | top-level |
| [tests/test_cli_lineage.py:17](D:/projects/Speech-Emotion-Recognition/tests/test_cli_lineage.py:17) | `ser_lib.services` | `TrainingService` | `TrainingService` | top-level |
| [tests/test_compatibility_report.py:7](D:/projects/Speech-Emotion-Recognition/tests/test_compatibility_report.py:7) | `ser_lib` | `CompatibilityReport` | `RootCompatibilityReport` | top-level |
| [tests/test_compatibility_report.py:8](D:/projects/Speech-Emotion-Recognition/tests/test_compatibility_report.py:8) | `ser_lib` | `inspect_compatibility` | `root_inspect_compatibility` | top-level |
| [tests/test_compatibility_report.py:9](D:/projects/Speech-Emotion-Recognition/tests/test_compatibility_report.py:9) | `ser_lib.data` | `BatchingConfig` | `BatchingConfig` | top-level |
| [tests/test_compatibility_report.py:9](D:/projects/Speech-Emotion-Recognition/tests/test_compatibility_report.py:9) | `ser_lib.data` | `CompatibilityReport` | `CompatibilityReport` | top-level |
| [tests/test_compatibility_report.py:9](D:/projects/Speech-Emotion-Recognition/tests/test_compatibility_report.py:9) | `ser_lib.data` | `ModelSpec` | `ModelSpec` | top-level |
| [tests/test_compatibility_report.py:9](D:/projects/Speech-Emotion-Recognition/tests/test_compatibility_report.py:9) | `ser_lib.data` | `TensorSpec` | `TensorSpec` | top-level |
| [tests/test_compatibility_report.py:10](D:/projects/Speech-Emotion-Recognition/tests/test_compatibility_report.py:10) | `ser_lib.data.errors` | `CompatibilityError` | `CompatibilityError` | top-level |
| [tests/test_compatibility_report.py:11](D:/projects/Speech-Emotion-Recognition/tests/test_compatibility_report.py:11) | `ser_lib.data.validation` | `inspect_compatibility` | `inspect_compatibility` | top-level |
| [tests/test_compatibility_report.py:11](D:/projects/Speech-Emotion-Recognition/tests/test_compatibility_report.py:11) | `ser_lib.data.validation` | `validate_compatibility` | `validate_compatibility` | top-level |
| [tests/test_component_catalog.py:7](D:/projects/Speech-Emotion-Recognition/tests/test_component_catalog.py:7) | `ser_lib` | `CATALOG_CATEGORIES` | `CATALOG_CATEGORIES` | top-level |
| [tests/test_component_catalog.py:7](D:/projects/Speech-Emotion-Recognition/tests/test_component_catalog.py:7) | `ser_lib` | `CATALOG_SCHEMA_VERSION` | `CATALOG_SCHEMA_VERSION` | top-level |
| [tests/test_component_catalog.py:7](D:/projects/Speech-Emotion-Recognition/tests/test_component_catalog.py:7) | `ser_lib` | `ComponentCatalog` | `RootComponentCatalog` | top-level |
| [tests/test_component_catalog.py:7](D:/projects/Speech-Emotion-Recognition/tests/test_component_catalog.py:7) | `ser_lib` | `ComponentDescriptor` | `RootComponentDescriptor` | top-level |
| [tests/test_component_catalog.py:7](D:/projects/Speech-Emotion-Recognition/tests/test_component_catalog.py:7) | `ser_lib` | `get_component_catalog` | `root_get_component_catalog` | top-level |
| [tests/test_component_catalog.py:14](D:/projects/Speech-Emotion-Recognition/tests/test_component_catalog.py:14) | `ser_lib.catalog` | `ComponentCatalog` | `ComponentCatalog` | top-level |
| [tests/test_component_catalog.py:14](D:/projects/Speech-Emotion-Recognition/tests/test_component_catalog.py:14) | `ser_lib.catalog` | `ComponentDescriptor` | `ComponentDescriptor` | top-level |
| [tests/test_component_catalog.py:14](D:/projects/Speech-Emotion-Recognition/tests/test_component_catalog.py:14) | `ser_lib.catalog` | `get_component_catalog` | `get_component_catalog` | top-level |
| [tests/test_component_catalog.py:14](D:/projects/Speech-Emotion-Recognition/tests/test_component_catalog.py:14) | `ser_lib.catalog` | `list_component_descriptors` | `list_component_descriptors` | top-level |
| [tests/test_component_catalog.py:20](D:/projects/Speech-Emotion-Recognition/tests/test_component_catalog.py:20) | `ser_lib.data.errors` | `RegistryError` | `RegistryError` | top-level |
| [tests/test_component_catalog.py:21](D:/projects/Speech-Emotion-Recognition/tests/test_component_catalog.py:21) | `ser_lib.models.registry` | `model_registry` | `model_registry` | top-level |
| [tests/test_core.py:10](D:/projects/Speech-Emotion-Recognition/tests/test_core.py:10) | `ser_lib.core` | `CancellationToken` | `CancellationToken` | top-level |
| [tests/test_core.py:10](D:/projects/Speech-Emotion-Recognition/tests/test_core.py:10) | `ser_lib.core` | `ConfigurationError` | `ConfigurationError` | top-level |
| [tests/test_core.py:10](D:/projects/Speech-Emotion-Recognition/tests/test_core.py:10) | `ser_lib.core` | `OperationCancelled` | `OperationCancelled` | top-level |
| [tests/test_core.py:10](D:/projects/Speech-Emotion-Recognition/tests/test_core.py:10) | `ser_lib.core` | `ProgressEvent` | `ProgressEvent` | top-level |
| [tests/test_core.py:10](D:/projects/Speech-Emotion-Recognition/tests/test_core.py:10) | `ser_lib.core` | `SERError` | `SERError` | top-level |
| [tests/test_core.py:10](D:/projects/Speech-Emotion-Recognition/tests/test_core.py:10) | `ser_lib.core` | `StrictConfig` | `StrictConfig` | top-level |
| [tests/test_core.py:10](D:/projects/Speech-Emotion-Recognition/tests/test_core.py:10) | `ser_lib.core` | `configure_library_logging` | `configure_library_logging` | top-level |
| [tests/test_core.py:10](D:/projects/Speech-Emotion-Recognition/tests/test_core.py:10) | `ser_lib.core` | `get_logger` | `get_logger` | top-level |
| [tests/test_core.py:10](D:/projects/Speech-Emotion-Recognition/tests/test_core.py:10) | `ser_lib.core` | `load_versioned_config` | `load_versioned_config` | top-level |
| [tests/test_core.py:10](D:/projects/Speech-Emotion-Recognition/tests/test_core.py:10) | `ser_lib.core` | `load_yaml_mapping` | `load_yaml_mapping` | top-level |
| [tests/test_core.py:10](D:/projects/Speech-Emotion-Recognition/tests/test_core.py:10) | `ser_lib.core` | `require_schema_version` | `require_schema_version` | top-level |
| [tests/test_core.py:10](D:/projects/Speech-Emotion-Recognition/tests/test_core.py:10) | `ser_lib.core` | `resolve_config_path` | `resolve_config_path` | top-level |
| [tests/test_core.py:24](D:/projects/Speech-Emotion-Recognition/tests/test_core.py:24) | `ser_lib.data.errors` | `ManifestError` | `ManifestError` | top-level |
| [tests/test_core.py:24](D:/projects/Speech-Emotion-Recognition/tests/test_core.py:24) | `ser_lib.data.errors` | `SERDataError` | `SERDataError` | top-level |
| [tests/test_crema_d_importer.py:9](D:/projects/Speech-Emotion-Recognition/tests/test_crema_d_importer.py:9) | `ser_lib.data.importers.crema_d` | `CREMA_D_EMOTIONS` | `CREMA_D_EMOTIONS` | top-level |
| [tests/test_crema_d_importer.py:9](D:/projects/Speech-Emotion-Recognition/tests/test_crema_d_importer.py:9) | `ser_lib.data.importers.crema_d` | `CremaDImporter` | `CremaDImporter` | top-level |
| [tests/test_csemotions_importer.py:9](D:/projects/Speech-Emotion-Recognition/tests/test_csemotions_importer.py:9) | `ser_lib.data.importers.csemotions` | `CsemotionsImporter` | `CsemotionsImporter` | top-level |
| [tests/test_data_types.py:4](D:/projects/Speech-Emotion-Recognition/tests/test_data_types.py:4) | `ser_lib.data.types` | `AudioRecord` | `AudioRecord` | top-level |
| [tests/test_data_types.py:4](D:/projects/Speech-Emotion-Recognition/tests/test_data_types.py:4) | `ser_lib.data.types` | `SERBatch` | `SERBatch` | top-level |
| [tests/test_data_types.py:4](D:/projects/Speech-Emotion-Recognition/tests/test_data_types.py:4) | `ser_lib.data.types` | `TensorSpec` | `TensorSpec` | top-level |
| [tests/test_dataset_editor.py:5](D:/projects/Speech-Emotion-Recognition/tests/test_dataset_editor.py:5) | `ser_lib.data.editor` | `(module)` | `editor_module` | top-level |
| [tests/test_dataset_editor.py:6](D:/projects/Speech-Emotion-Recognition/tests/test_dataset_editor.py:6) | `ser_lib.data` | `DatasetEditConflictError` | `DatasetEditConflictError` | top-level |
| [tests/test_dataset_editor.py:6](D:/projects/Speech-Emotion-Recognition/tests/test_dataset_editor.py:6) | `ser_lib.data` | `DatasetEditError` | `DatasetEditError` | top-level |
| [tests/test_dataset_editor.py:6](D:/projects/Speech-Emotion-Recognition/tests/test_dataset_editor.py:6) | `ser_lib.data` | `DatasetEditor` | `DatasetEditor` | top-level |
| [tests/test_dataset_editor.py:6](D:/projects/Speech-Emotion-Recognition/tests/test_dataset_editor.py:6) | `ser_lib.data` | `DatasetManifest` | `DatasetManifest` | top-level |
| [tests/test_dataset_editor.py:6](D:/projects/Speech-Emotion-Recognition/tests/test_dataset_editor.py:6) | `ser_lib.data` | `DatasetTransactionError` | `DatasetTransactionError` | top-level |
| [tests/test_dataset_fingerprint.py:4](D:/projects/Speech-Emotion-Recognition/tests/test_dataset_fingerprint.py:4) | `ser_lib.data` | `DatasetFingerprint` | `DatasetFingerprint` | top-level |
| [tests/test_dataset_fingerprint.py:4](D:/projects/Speech-Emotion-Recognition/tests/test_dataset_fingerprint.py:4) | `ser_lib.data` | `fingerprint_manifest` | `fingerprint_manifest` | top-level |
| [tests/test_dataset_history.py:9](D:/projects/Speech-Emotion-Recognition/tests/test_dataset_history.py:9) | `ser_lib.core` | `CancellationToken` | `CancellationToken` | top-level |
| [tests/test_dataset_history.py:9](D:/projects/Speech-Emotion-Recognition/tests/test_dataset_history.py:9) | `ser_lib.core` | `OperationCancelled` | `OperationCancelled` | top-level |
| [tests/test_dataset_history.py:9](D:/projects/Speech-Emotion-Recognition/tests/test_dataset_history.py:9) | `ser_lib.core` | `ProgressEvent` | `ProgressEvent` | top-level |
| [tests/test_dataset_history.py:10](D:/projects/Speech-Emotion-Recognition/tests/test_dataset_history.py:10) | `ser_lib.data` | `DatasetEditConflictError` | `DatasetEditConflictError` | top-level |
| [tests/test_dataset_history.py:10](D:/projects/Speech-Emotion-Recognition/tests/test_dataset_history.py:10) | `ser_lib.data` | `DatasetEditor` | `DatasetEditor` | top-level |
| [tests/test_dataset_history.py:10](D:/projects/Speech-Emotion-Recognition/tests/test_dataset_history.py:10) | `ser_lib.data` | `DatasetManifest` | `DatasetManifest` | top-level |
| [tests/test_dataset_history.py:10](D:/projects/Speech-Emotion-Recognition/tests/test_dataset_history.py:10) | `ser_lib.data` | `create_dataset_revision` | `create_dataset_revision` | top-level |
| [tests/test_dataset_history.py:10](D:/projects/Speech-Emotion-Recognition/tests/test_dataset_history.py:10) | `ser_lib.data` | `fingerprint_manifest` | `fingerprint_manifest` | top-level |
| [tests/test_dataset_history.py:10](D:/projects/Speech-Emotion-Recognition/tests/test_dataset_history.py:10) | `ser_lib.data` | `inspect_dataset_revision` | `inspect_dataset_revision` | top-level |
| [tests/test_dataset_history.py:10](D:/projects/Speech-Emotion-Recognition/tests/test_dataset_history.py:10) | `ser_lib.data` | `restore_dataset_revision` | `restore_dataset_revision` | top-level |
| [tests/test_dataset_history.py:10](D:/projects/Speech-Emotion-Recognition/tests/test_dataset_history.py:10) | `ser_lib.data` | `scan_dataset_revisions` | `scan_dataset_revisions` | top-level |
| [tests/test_dataset_history.py:20](D:/projects/Speech-Emotion-Recognition/tests/test_dataset_history.py:20) | `ser_lib.services` | `DatasetService` | `DatasetService` | top-level |
| [tests/test_dataset_profile.py:7](D:/projects/Speech-Emotion-Recognition/tests/test_dataset_profile.py:7) | `ser_lib.core.events` | `CancellationToken` | `CancellationToken` | top-level |
| [tests/test_dataset_profile.py:8](D:/projects/Speech-Emotion-Recognition/tests/test_dataset_profile.py:8) | `ser_lib.core.exceptions` | `OperationCancelled` | `OperationCancelled` | top-level |
| [tests/test_dataset_profile.py:9](D:/projects/Speech-Emotion-Recognition/tests/test_dataset_profile.py:9) | `ser_lib.data` | `DatasetProfile` | `DatasetProfile` | top-level |
| [tests/test_dataset_profile.py:9](D:/projects/Speech-Emotion-Recognition/tests/test_dataset_profile.py:9) | `ser_lib.data` | `profile_dataset` | `profile_dataset` | top-level |
| [tests/test_dataset_profile.py:9](D:/projects/Speech-Emotion-Recognition/tests/test_dataset_profile.py:9) | `ser_lib.data` | `profile_manifest_audio` | `profile_manifest_audio` | top-level |
| [tests/test_dataset_profile.py:10](D:/projects/Speech-Emotion-Recognition/tests/test_dataset_profile.py:10) | `ser_lib.services` | `DatasetService` | `DatasetService` | top-level |
| [tests/test_dataset_query.py:6](D:/projects/Speech-Emotion-Recognition/tests/test_dataset_query.py:6) | `ser_lib.data` | `RecordPage` | `RecordPage` | top-level |
| [tests/test_dataset_query.py:6](D:/projects/Speech-Emotion-Recognition/tests/test_dataset_query.py:6) | `ser_lib.data` | `query_records` | `query_records` | top-level |
| [tests/test_dataset_summary.py:7](D:/projects/Speech-Emotion-Recognition/tests/test_dataset_summary.py:7) | `ser_lib.data` | `DatasetSummary` | `DatasetSummary` | top-level |
| [tests/test_dataset_summary.py:7](D:/projects/Speech-Emotion-Recognition/tests/test_dataset_summary.py:7) | `ser_lib.data` | `summarize_manifest` | `summarize_manifest` | top-level |
| [tests/test_diagnostics.py:9](D:/projects/Speech-Emotion-Recognition/tests/test_diagnostics.py:9) | `ser_lib.core` | `Diagnostic` | `Diagnostic` | top-level |
| [tests/test_diagnostics.py:10](D:/projects/Speech-Emotion-Recognition/tests/test_diagnostics.py:10) | `ser_lib.data.errors` | `AudioDecodeError` | `AudioDecodeError` | top-level |
| [tests/test_diagnostics.py:10](D:/projects/Speech-Emotion-Recognition/tests/test_diagnostics.py:10) | `ser_lib.data.errors` | `AudioNotFoundError` | `AudioNotFoundError` | top-level |
| [tests/test_diagnostics.py:10](D:/projects/Speech-Emotion-Recognition/tests/test_diagnostics.py:10) | `ser_lib.data.errors` | `CollationError` | `CollationError` | top-level |
| [tests/test_diagnostics.py:10](D:/projects/Speech-Emotion-Recognition/tests/test_diagnostics.py:10) | `ser_lib.data.errors` | `CompatibilityError` | `CompatibilityError` | top-level |
| [tests/test_diagnostics.py:10](D:/projects/Speech-Emotion-Recognition/tests/test_diagnostics.py:10) | `ser_lib.data.errors` | `InvalidAudioSegmentError` | `InvalidAudioSegmentError` | top-level |
| [tests/test_diagnostics.py:10](D:/projects/Speech-Emotion-Recognition/tests/test_diagnostics.py:10) | `ser_lib.data.errors` | `ManifestError` | `ManifestError` | top-level |
| [tests/test_diagnostics.py:10](D:/projects/Speech-Emotion-Recognition/tests/test_diagnostics.py:10) | `ser_lib.data.errors` | `RegistryError` | `RegistryError` | top-level |
| [tests/test_diagnostics.py:10](D:/projects/Speech-Emotion-Recognition/tests/test_diagnostics.py:10) | `ser_lib.data.errors` | `RepresentationError` | `RepresentationError` | top-level |
| [tests/test_diagnostics.py:10](D:/projects/Speech-Emotion-Recognition/tests/test_diagnostics.py:10) | `ser_lib.data.errors` | `TransformError` | `TransformError` | top-level |
| [tests/test_diagnostics.py:14](D:/projects/Speech-Emotion-Recognition/tests/test_diagnostics.py:14) | `ser_lib.data.importers` | `ImportPreview` | `ImportPreview` | top-level |
| [tests/test_emotiontalk_importer.py:9](D:/projects/Speech-Emotion-Recognition/tests/test_emotiontalk_importer.py:9) | `ser_lib.data.importers.emotiontalk` | `EmotionTalkImporter` | `EmotionTalkImporter` | top-level |
| [tests/test_engine_config.py:9](D:/projects/Speech-Emotion-Recognition/tests/test_engine_config.py:9) | `ser_lib.core` | `CancellationToken` | `CancellationToken` | top-level |
| [tests/test_engine_config.py:9](D:/projects/Speech-Emotion-Recognition/tests/test_engine_config.py:9) | `ser_lib.core` | `MetricEvent` | `MetricEvent` | top-level |
| [tests/test_engine_config.py:9](D:/projects/Speech-Emotion-Recognition/tests/test_engine_config.py:9) | `ser_lib.core` | `OperationCancelled` | `OperationCancelled` | top-level |
| [tests/test_engine_config.py:9](D:/projects/Speech-Emotion-Recognition/tests/test_engine_config.py:9) | `ser_lib.core` | `ProgressEvent` | `ProgressEvent` | top-level |
| [tests/test_engine_config.py:10](D:/projects/Speech-Emotion-Recognition/tests/test_engine_config.py:10) | `ser_lib.data` | `BatchingConfig` | `BatchingConfig` | top-level |
| [tests/test_engine_config.py:10](D:/projects/Speech-Emotion-Recognition/tests/test_engine_config.py:10) | `ser_lib.data` | `SERCollator` | `SERCollator` | top-level |
| [tests/test_engine_config.py:10](D:/projects/Speech-Emotion-Recognition/tests/test_engine_config.py:10) | `ser_lib.data` | `SERSample` | `SERSample` | top-level |
| [tests/test_engine_config.py:10](D:/projects/Speech-Emotion-Recognition/tests/test_engine_config.py:10) | `ser_lib.data` | `TensorSpec` | `TensorSpec` | top-level |
| [tests/test_engine_config.py:11](D:/projects/Speech-Emotion-Recognition/tests/test_engine_config.py:11) | `ser_lib.data.config` | `AudioSettings` | `AudioSettings` | top-level |
| [tests/test_engine_config.py:11](D:/projects/Speech-Emotion-Recognition/tests/test_engine_config.py:11) | `ser_lib.data.config` | `ComponentConfig` | `ComponentConfig` | top-level |
| [tests/test_engine_config.py:11](D:/projects/Speech-Emotion-Recognition/tests/test_engine_config.py:11) | `ser_lib.data.config` | `DataConfig` | `DataConfig` | top-level |
| [tests/test_engine_config.py:12](D:/projects/Speech-Emotion-Recognition/tests/test_engine_config.py:12) | `ser_lib.data.errors` | `CompatibilityError` | `CompatibilityError` | top-level |
| [tests/test_engine_config.py:13](D:/projects/Speech-Emotion-Recognition/tests/test_engine_config.py:13) | `ser_lib.engine` | `ExperimentConfig` | `ExperimentConfig` | top-level |
| [tests/test_engine_config.py:13](D:/projects/Speech-Emotion-Recognition/tests/test_engine_config.py:13) | `ser_lib.engine` | `ModelConfig` | `ModelConfig` | top-level |
| [tests/test_engine_config.py:13](D:/projects/Speech-Emotion-Recognition/tests/test_engine_config.py:13) | `ser_lib.engine` | `Trainer` | `Trainer` | top-level |
| [tests/test_engine_config.py:13](D:/projects/Speech-Emotion-Recognition/tests/test_engine_config.py:13) | `ser_lib.engine` | `TrainerConfig` | `TrainerConfig` | top-level |
| [tests/test_engine_config.py:13](D:/projects/Speech-Emotion-Recognition/tests/test_engine_config.py:13) | `ser_lib.engine` | `build_experiment_components` | `build_experiment_components` | top-level |
| [tests/test_engine_config.py:13](D:/projects/Speech-Emotion-Recognition/tests/test_engine_config.py:13) | `ser_lib.engine` | `load_experiment_config` | `load_experiment_config` | top-level |
| [tests/test_engine_config.py:13](D:/projects/Speech-Emotion-Recognition/tests/test_engine_config.py:13) | `ser_lib.engine` | `parse_optimizer_config` | `parse_optimizer_config` | top-level |
| [tests/test_engine_config.py:13](D:/projects/Speech-Emotion-Recognition/tests/test_engine_config.py:13) | `ser_lib.engine` | `parse_scheduler_config` | `parse_scheduler_config` | top-level |
| [tests/test_engine_config.py:23](D:/projects/Speech-Emotion-Recognition/tests/test_engine_config.py:23) | `ser_lib.models` | `CNNBaseline` | `CNNBaseline` | top-level |
| [tests/test_esd_importer.py:8](D:/projects/Speech-Emotion-Recognition/tests/test_esd_importer.py:8) | `ser_lib.data.importers.esd` | `ESD_LABELS` | `ESD_LABELS` | top-level |
| [tests/test_esd_importer.py:8](D:/projects/Speech-Emotion-Recognition/tests/test_esd_importer.py:8) | `ser_lib.data.importers.esd` | `EsdImporter` | `EsdImporter` | top-level |
| [tests/test_eta.py:5](D:/projects/Speech-Emotion-Recognition/tests/test_eta.py:5) | `ser_lib.engine.eta` | `EtaEstimator` | `EtaEstimator` | top-level |
| [tests/test_evaluation_prediction_query.py:8](D:/projects/Speech-Emotion-Recognition/tests/test_evaluation_prediction_query.py:8) | `ser_lib.core` | `CancellationToken` | `CancellationToken` | top-level |
| [tests/test_evaluation_prediction_query.py:8](D:/projects/Speech-Emotion-Recognition/tests/test_evaluation_prediction_query.py:8) | `ser_lib.core` | `OperationCancelled` | `OperationCancelled` | top-level |
| [tests/test_evaluation_prediction_query.py:9](D:/projects/Speech-Emotion-Recognition/tests/test_evaluation_prediction_query.py:9) | `ser_lib.engine` | `EvaluationPredictionPage` | `EvaluationPredictionPage` | top-level |
| [tests/test_evaluation_prediction_query.py:9](D:/projects/Speech-Emotion-Recognition/tests/test_evaluation_prediction_query.py:9) | `ser_lib.engine` | `query_evaluation_predictions` | `query_evaluation_predictions` | top-level |
| [tests/test_evaluation_prediction_query.py:10](D:/projects/Speech-Emotion-Recognition/tests/test_evaluation_prediction_query.py:10) | `ser_lib.services` | `EvaluationService` | `EvaluationService` | top-level |
| [tests/test_evaluation_prediction_sink.py:7](D:/projects/Speech-Emotion-Recognition/tests/test_evaluation_prediction_sink.py:7) | `ser_lib.data` | `SERBatch` | `SERBatch` | top-level |
| [tests/test_evaluation_prediction_sink.py:7](D:/projects/Speech-Emotion-Recognition/tests/test_evaluation_prediction_sink.py:7) | `ser_lib.data` | `TensorSpec` | `TensorSpec` | top-level |
| [tests/test_evaluation_prediction_sink.py:8](D:/projects/Speech-Emotion-Recognition/tests/test_evaluation_prediction_sink.py:8) | `ser_lib.data.validation` | `ModelSpec` | `ModelSpec` | top-level |
| [tests/test_evaluation_prediction_sink.py:9](D:/projects/Speech-Emotion-Recognition/tests/test_evaluation_prediction_sink.py:9) | `ser_lib.engine` | `JsonlPredictionSink` | `JsonlPredictionSink` | top-level |
| [tests/test_evaluation_prediction_sink.py:9](D:/projects/Speech-Emotion-Recognition/tests/test_evaluation_prediction_sink.py:9) | `ser_lib.engine` | `PredictionRecord` | `PredictionRecord` | top-level |
| [tests/test_evaluation_prediction_sink.py:9](D:/projects/Speech-Emotion-Recognition/tests/test_evaluation_prediction_sink.py:9) | `ser_lib.engine` | `evaluate` | `evaluate` | top-level |
| [tests/test_evaluation_prediction_sink.py:10](D:/projects/Speech-Emotion-Recognition/tests/test_evaluation_prediction_sink.py:10) | `ser_lib.models` | `ModelOutput` | `ModelOutput` | top-level |
| [tests/test_evaluation_prediction_sink.py:10](D:/projects/Speech-Emotion-Recognition/tests/test_evaluation_prediction_sink.py:10) | `ser_lib.models` | `SERModel` | `SERModel` | top-level |
| [tests/test_evaluation_report_inspect.py:9](D:/projects/Speech-Emotion-Recognition/tests/test_evaluation_report_inspect.py:9) | `ser_lib.engine` | `EvaluationReportInfo` | `EvaluationReportInfo` | top-level |
| [tests/test_evaluation_report_inspect.py:9](D:/projects/Speech-Emotion-Recognition/tests/test_evaluation_report_inspect.py:9) | `ser_lib.engine` | `inspect_evaluation_report` | `inspect_evaluation_report` | top-level |
| [tests/test_evaluation_report_inspect.py:10](D:/projects/Speech-Emotion-Recognition/tests/test_evaluation_report_inspect.py:10) | `ser_lib.services` | `EvaluationService` | `EvaluationService` | top-level |
| [tests/test_evaluation_run_catalog.py:10](D:/projects/Speech-Emotion-Recognition/tests/test_evaluation_run_catalog.py:10) | `ser_lib.core` | `CancellationToken` | `CancellationToken` | top-level |
| [tests/test_evaluation_run_catalog.py:10](D:/projects/Speech-Emotion-Recognition/tests/test_evaluation_run_catalog.py:10) | `ser_lib.core` | `OperationCancelled` | `OperationCancelled` | top-level |
| [tests/test_evaluation_run_catalog.py:10](D:/projects/Speech-Emotion-Recognition/tests/test_evaluation_run_catalog.py:10) | `ser_lib.core` | `ProgressEvent` | `ProgressEvent` | top-level |
| [tests/test_evaluation_run_catalog.py:11](D:/projects/Speech-Emotion-Recognition/tests/test_evaluation_run_catalog.py:11) | `ser_lib.engine` | `EvaluationRunCatalog` | `EvaluationRunCatalog` | top-level |
| [tests/test_evaluation_run_catalog.py:11](D:/projects/Speech-Emotion-Recognition/tests/test_evaluation_run_catalog.py:11) | `ser_lib.engine` | `scan_evaluation_runs` | `scan_evaluation_runs` | top-level |
| [tests/test_evaluation_run_catalog.py:12](D:/projects/Speech-Emotion-Recognition/tests/test_evaluation_run_catalog.py:12) | `ser_lib.services` | `EvaluationService` | `EvaluationService` | top-level |
| [tests/test_evaluation_run_detail.py:7](D:/projects/Speech-Emotion-Recognition/tests/test_evaluation_run_detail.py:7) | `ser_lib.engine` | `EvaluationRunDetail` | `EvaluationRunDetail` | top-level |
| [tests/test_evaluation_run_detail.py:7](D:/projects/Speech-Emotion-Recognition/tests/test_evaluation_run_detail.py:7) | `ser_lib.engine` | `EvaluationRunInfo` | `EvaluationRunInfo` | top-level |
| [tests/test_evaluation_run_detail.py:8](D:/projects/Speech-Emotion-Recognition/tests/test_evaluation_run_detail.py:8) | `ser_lib.services` | `EvaluationService` | `EvaluationService` | top-level |
| [tests/test_evaluation_run_metadata.py:11](D:/projects/Speech-Emotion-Recognition/tests/test_evaluation_run_metadata.py:11) | `ser_lib.engine` | `EVALUATION_RUN_SCHEMA_VERSION` | `EVALUATION_RUN_SCHEMA_VERSION` | top-level |
| [tests/test_evaluation_run_metadata.py:11](D:/projects/Speech-Emotion-Recognition/tests/test_evaluation_run_metadata.py:11) | `ser_lib.engine` | `ClassMetrics` | `ClassMetrics` | top-level |
| [tests/test_evaluation_run_metadata.py:11](D:/projects/Speech-Emotion-Recognition/tests/test_evaluation_run_metadata.py:11) | `ser_lib.engine` | `EvaluationResult` | `EvaluationResult` | top-level |
| [tests/test_evaluation_run_metadata.py:11](D:/projects/Speech-Emotion-Recognition/tests/test_evaluation_run_metadata.py:11) | `ser_lib.engine` | `EvaluationRunInfo` | `EvaluationRunInfo` | top-level |
| [tests/test_evaluation_run_metadata.py:11](D:/projects/Speech-Emotion-Recognition/tests/test_evaluation_run_metadata.py:11) | `ser_lib.engine` | `build_evaluation_run_metadata` | `build_evaluation_run_metadata` | top-level |
| [tests/test_evaluation_run_metadata.py:11](D:/projects/Speech-Emotion-Recognition/tests/test_evaluation_run_metadata.py:11) | `ser_lib.engine` | `load_evaluation_run_info` | `load_evaluation_run_info` | top-level |
| [tests/test_evaluation_run_metadata.py:11](D:/projects/Speech-Emotion-Recognition/tests/test_evaluation_run_metadata.py:11) | `ser_lib.engine` | `write_evaluation_run_info` | `write_evaluation_run_info` | top-level |
| [tests/test_evaluation_run_metadata.py:20](D:/projects/Speech-Emotion-Recognition/tests/test_evaluation_run_metadata.py:20) | `ser_lib.services` | `EvaluationService` | `EvaluationService` | top-level |
| [tests/test_evaluator_observability.py:10](D:/projects/Speech-Emotion-Recognition/tests/test_evaluator_observability.py:10) | `ser_lib.core` | `CancellationToken` | `CancellationToken` | top-level |
| [tests/test_evaluator_observability.py:10](D:/projects/Speech-Emotion-Recognition/tests/test_evaluator_observability.py:10) | `ser_lib.core` | `EventContext` | `EventContext` | top-level |
| [tests/test_evaluator_observability.py:10](D:/projects/Speech-Emotion-Recognition/tests/test_evaluator_observability.py:10) | `ser_lib.core` | `LifecycleEvent` | `LifecycleEvent` | top-level |
| [tests/test_evaluator_observability.py:10](D:/projects/Speech-Emotion-Recognition/tests/test_evaluator_observability.py:10) | `ser_lib.core` | `OperationCancelled` | `OperationCancelled` | top-level |
| [tests/test_evaluator_observability.py:10](D:/projects/Speech-Emotion-Recognition/tests/test_evaluator_observability.py:10) | `ser_lib.core` | `ProgressEvent` | `ProgressEvent` | top-level |
| [tests/test_evaluator_observability.py:17](D:/projects/Speech-Emotion-Recognition/tests/test_evaluator_observability.py:17) | `ser_lib.data` | `BatchingConfig` | `BatchingConfig` | top-level |
| [tests/test_evaluator_observability.py:17](D:/projects/Speech-Emotion-Recognition/tests/test_evaluator_observability.py:17) | `ser_lib.data` | `SERCollator` | `SERCollator` | top-level |
| [tests/test_evaluator_observability.py:17](D:/projects/Speech-Emotion-Recognition/tests/test_evaluator_observability.py:17) | `ser_lib.data` | `SERSample` | `SERSample` | top-level |
| [tests/test_evaluator_observability.py:17](D:/projects/Speech-Emotion-Recognition/tests/test_evaluator_observability.py:17) | `ser_lib.data` | `TensorSpec` | `TensorSpec` | top-level |
| [tests/test_evaluator_observability.py:18](D:/projects/Speech-Emotion-Recognition/tests/test_evaluator_observability.py:18) | `ser_lib.engine` | `evaluate` | `evaluate` | top-level |
| [tests/test_evaluator_observability.py:18](D:/projects/Speech-Emotion-Recognition/tests/test_evaluator_observability.py:18) | `ser_lib.engine` | `write_evaluation_report` | `write_evaluation_report` | top-level |
| [tests/test_evaluator_observability.py:19](D:/projects/Speech-Emotion-Recognition/tests/test_evaluator_observability.py:19) | `ser_lib.models` | `CNNBaseline` | `CNNBaseline` | top-level |
| [tests/test_evaluator_reports.py:9](D:/projects/Speech-Emotion-Recognition/tests/test_evaluator_reports.py:9) | `ser_lib.core` | `CancellationToken` | `CancellationToken` | top-level |
| [tests/test_evaluator_reports.py:9](D:/projects/Speech-Emotion-Recognition/tests/test_evaluator_reports.py:9) | `ser_lib.core` | `LifecycleEvent` | `LifecycleEvent` | top-level |
| [tests/test_evaluator_reports.py:9](D:/projects/Speech-Emotion-Recognition/tests/test_evaluator_reports.py:9) | `ser_lib.core` | `OperationCancelled` | `OperationCancelled` | top-level |
| [tests/test_evaluator_reports.py:9](D:/projects/Speech-Emotion-Recognition/tests/test_evaluator_reports.py:9) | `ser_lib.core` | `ProgressEvent` | `ProgressEvent` | top-level |
| [tests/test_evaluator_reports.py:15](D:/projects/Speech-Emotion-Recognition/tests/test_evaluator_reports.py:15) | `ser_lib.data` | `SERBatch` | `SERBatch` | top-level |
| [tests/test_evaluator_reports.py:15](D:/projects/Speech-Emotion-Recognition/tests/test_evaluator_reports.py:15) | `ser_lib.data` | `TensorSpec` | `TensorSpec` | top-level |
| [tests/test_evaluator_reports.py:16](D:/projects/Speech-Emotion-Recognition/tests/test_evaluator_reports.py:16) | `ser_lib.data.validation` | `ModelSpec` | `ModelSpec` | top-level |
| [tests/test_evaluator_reports.py:17](D:/projects/Speech-Emotion-Recognition/tests/test_evaluator_reports.py:17) | `ser_lib.engine` | `evaluate` | `evaluate` | top-level |
| [tests/test_evaluator_reports.py:17](D:/projects/Speech-Emotion-Recognition/tests/test_evaluator_reports.py:17) | `ser_lib.engine` | `write_evaluation_report` | `write_evaluation_report` | top-level |
| [tests/test_evaluator_reports.py:18](D:/projects/Speech-Emotion-Recognition/tests/test_evaluator_reports.py:18) | `ser_lib.models` | `ModelOutput` | `ModelOutput` | top-level |
| [tests/test_evaluator_reports.py:18](D:/projects/Speech-Emotion-Recognition/tests/test_evaluator_reports.py:18) | `ser_lib.models` | `SERModel` | `SERModel` | top-level |
| [tests/test_events.py:9](D:/projects/Speech-Emotion-Recognition/tests/test_events.py:9) | `ser_lib.core` | `EVENT_SCHEMA_VERSION` | `EVENT_SCHEMA_VERSION` | top-level |
| [tests/test_events.py:9](D:/projects/Speech-Emotion-Recognition/tests/test_events.py:9) | `ser_lib.core` | `CheckpointEvent` | `CheckpointEvent` | top-level |
| [tests/test_events.py:9](D:/projects/Speech-Emotion-Recognition/tests/test_events.py:9) | `ser_lib.core` | `EventContext` | `EventContext` | top-level |
| [tests/test_events.py:9](D:/projects/Speech-Emotion-Recognition/tests/test_events.py:9) | `ser_lib.core` | `LifecycleEvent` | `LifecycleEvent` | top-level |
| [tests/test_events.py:9](D:/projects/Speech-Emotion-Recognition/tests/test_events.py:9) | `ser_lib.core` | `LogEvent` | `LogEvent` | top-level |
| [tests/test_events.py:9](D:/projects/Speech-Emotion-Recognition/tests/test_events.py:9) | `ser_lib.core` | `MetricEvent` | `MetricEvent` | top-level |
| [tests/test_events.py:9](D:/projects/Speech-Emotion-Recognition/tests/test_events.py:9) | `ser_lib.core` | `ProgressEvent` | `ProgressEvent` | top-level |
| [tests/test_experiment_presets.py:9](D:/projects/Speech-Emotion-Recognition/tests/test_experiment_presets.py:9) | `ser_lib` | `get_component_catalog` | `get_component_catalog` | top-level |
| [tests/test_experiment_presets.py:10](D:/projects/Speech-Emotion-Recognition/tests/test_experiment_presets.py:10) | `ser_lib.engine` | `ExperimentConfig` | `ExperimentConfig` | top-level |
| [tests/test_experiment_presets.py:10](D:/projects/Speech-Emotion-Recognition/tests/test_experiment_presets.py:10) | `ser_lib.engine` | `build_experiment_config` | `build_experiment_config` | top-level |
| [tests/test_experiment_presets.py:10](D:/projects/Speech-Emotion-Recognition/tests/test_experiment_presets.py:10) | `ser_lib.engine` | `get_experiment_preset` | `get_experiment_preset` | top-level |
| [tests/test_experiment_presets.py:10](D:/projects/Speech-Emotion-Recognition/tests/test_experiment_presets.py:10) | `ser_lib.engine` | `list_experiment_presets` | `list_experiment_presets` | top-level |
| [tests/test_experiment_validation.py:6](D:/projects/Speech-Emotion-Recognition/tests/test_experiment_validation.py:6) | `ser_lib` | `ExperimentValidationResult` | `RootExperimentValidationResult` | top-level |
| [tests/test_experiment_validation.py:7](D:/projects/Speech-Emotion-Recognition/tests/test_experiment_validation.py:7) | `ser_lib` | `validate_experiment` | `root_validate_experiment` | top-level |
| [tests/test_experiment_validation.py:8](D:/projects/Speech-Emotion-Recognition/tests/test_experiment_validation.py:8) | `ser_lib.data` | `BatchingConfig` | `BatchingConfig` | top-level |
| [tests/test_experiment_validation.py:9](D:/projects/Speech-Emotion-Recognition/tests/test_experiment_validation.py:9) | `ser_lib.data.config` | `AudioSettings` | `AudioSettings` | top-level |
| [tests/test_experiment_validation.py:9](D:/projects/Speech-Emotion-Recognition/tests/test_experiment_validation.py:9) | `ser_lib.data.config` | `ComponentConfig` | `ComponentConfig` | top-level |
| [tests/test_experiment_validation.py:9](D:/projects/Speech-Emotion-Recognition/tests/test_experiment_validation.py:9) | `ser_lib.data.config` | `DataConfig` | `DataConfig` | top-level |
| [tests/test_experiment_validation.py:10](D:/projects/Speech-Emotion-Recognition/tests/test_experiment_validation.py:10) | `ser_lib.engine` | `ExperimentValidationResult` | `ExperimentValidationResult` | top-level |
| [tests/test_experiment_validation.py:10](D:/projects/Speech-Emotion-Recognition/tests/test_experiment_validation.py:10) | `ser_lib.engine` | `validate_experiment` | `validate_experiment` | top-level |
| [tests/test_experiment_validation.py:11](D:/projects/Speech-Emotion-Recognition/tests/test_experiment_validation.py:11) | `ser_lib.engine.config` | `ExperimentConfig` | `ExperimentConfig` | top-level |
| [tests/test_experiment_validation.py:11](D:/projects/Speech-Emotion-Recognition/tests/test_experiment_validation.py:11) | `ser_lib.engine.config` | `ModelConfig` | `ModelConfig` | top-level |
| [tests/test_experiment_validation.py:11](D:/projects/Speech-Emotion-Recognition/tests/test_experiment_validation.py:11) | `ser_lib.engine.config` | `TrainerConfig` | `TrainerConfig` | top-level |
| [tests/test_experiment_validation.py:12](D:/projects/Speech-Emotion-Recognition/tests/test_experiment_validation.py:12) | `ser_lib.models.registry` | `model_registry` | `model_registry` | top-level |
| [tests/test_importer_observability.py:8](D:/projects/Speech-Emotion-Recognition/tests/test_importer_observability.py:8) | `ser_lib.core` | `CancellationToken` | `CancellationToken` | top-level |
| [tests/test_importer_observability.py:8](D:/projects/Speech-Emotion-Recognition/tests/test_importer_observability.py:8) | `ser_lib.core` | `EventContext` | `EventContext` | top-level |
| [tests/test_importer_observability.py:8](D:/projects/Speech-Emotion-Recognition/tests/test_importer_observability.py:8) | `ser_lib.core` | `LifecycleEvent` | `LifecycleEvent` | top-level |
| [tests/test_importer_observability.py:8](D:/projects/Speech-Emotion-Recognition/tests/test_importer_observability.py:8) | `ser_lib.core` | `OperationCancelled` | `OperationCancelled` | top-level |
| [tests/test_importer_observability.py:8](D:/projects/Speech-Emotion-Recognition/tests/test_importer_observability.py:8) | `ser_lib.core` | `ProgressEvent` | `ProgressEvent` | top-level |
| [tests/test_importer_observability.py:15](D:/projects/Speech-Emotion-Recognition/tests/test_importer_observability.py:15) | `ser_lib.data.importers` | `CasiaImporter` | `CasiaImporter` | top-level |
| [tests/test_importer_observability.py:15](D:/projects/Speech-Emotion-Recognition/tests/test_importer_observability.py:15) | `ser_lib.data.importers` | `CremaDImporter` | `CremaDImporter` | top-level |
| [tests/test_importer_observability.py:15](D:/projects/Speech-Emotion-Recognition/tests/test_importer_observability.py:15) | `ser_lib.data.importers` | `CsemotionsImporter` | `CsemotionsImporter` | top-level |
| [tests/test_importer_observability.py:15](D:/projects/Speech-Emotion-Recognition/tests/test_importer_observability.py:15) | `ser_lib.data.importers` | `CsvImporter` | `CsvImporter` | top-level |
| [tests/test_importer_observability.py:15](D:/projects/Speech-Emotion-Recognition/tests/test_importer_observability.py:15) | `ser_lib.data.importers` | `EmotionTalkImporter` | `EmotionTalkImporter` | top-level |
| [tests/test_importer_observability.py:15](D:/projects/Speech-Emotion-Recognition/tests/test_importer_observability.py:15) | `ser_lib.data.importers` | `EsdImporter` | `EsdImporter` | top-level |
| [tests/test_importer_observability.py:15](D:/projects/Speech-Emotion-Recognition/tests/test_importer_observability.py:15) | `ser_lib.data.importers` | `FolderImporter` | `FolderImporter` | top-level |
| [tests/test_importer_observability.py:15](D:/projects/Speech-Emotion-Recognition/tests/test_importer_observability.py:15) | `ser_lib.data.importers` | `JsonlImporter` | `JsonlImporter` | top-level |
| [tests/test_importer_observability.py:15](D:/projects/Speech-Emotion-Recognition/tests/test_importer_observability.py:15) | `ser_lib.data.importers` | `RavdessImporter` | `RavdessImporter` | top-level |
| [tests/test_manifest.py:5](D:/projects/Speech-Emotion-Recognition/tests/test_manifest.py:5) | `ser_lib.data.errors` | `ManifestError` | `ManifestError` | top-level |
| [tests/test_manifest.py:6](D:/projects/Speech-Emotion-Recognition/tests/test_manifest.py:6) | `ser_lib.data.manifest` | `DatasetManifest` | `DatasetManifest` | top-level |
| [tests/test_manifest.py:6](D:/projects/Speech-Emotion-Recognition/tests/test_manifest.py:6) | `ser_lib.data.manifest` | `read_jsonl` | `read_jsonl` | top-level |
| [tests/test_manifest.py:6](D:/projects/Speech-Emotion-Recognition/tests/test_manifest.py:6) | `ser_lib.data.manifest` | `write_jsonl` | `write_jsonl` | top-level |
| [tests/test_manifest.py:7](D:/projects/Speech-Emotion-Recognition/tests/test_manifest.py:7) | `ser_lib.data.types` | `AudioRecord` | `AudioRecord` | top-level |
| [tests/test_model_engine.py:10](D:/projects/Speech-Emotion-Recognition/tests/test_model_engine.py:10) | `ser_lib.data.collate` | `SERCollator` | `SERCollator` | top-level |
| [tests/test_model_engine.py:11](D:/projects/Speech-Emotion-Recognition/tests/test_model_engine.py:11) | `ser_lib.data.audio` | `AudioLoader` | `AudioLoader` | top-level |
| [tests/test_model_engine.py:11](D:/projects/Speech-Emotion-Recognition/tests/test_model_engine.py:11) | `ser_lib.data.audio` | `AudioLoaderConfig` | `AudioLoaderConfig` | top-level |
| [tests/test_model_engine.py:12](D:/projects/Speech-Emotion-Recognition/tests/test_model_engine.py:12) | `ser_lib.data.config` | `BatchingConfig` | `BatchingConfig` | top-level |
| [tests/test_model_engine.py:13](D:/projects/Speech-Emotion-Recognition/tests/test_model_engine.py:13) | `ser_lib.data.pipeline` | `SamplePipeline` | `SamplePipeline` | top-level |
| [tests/test_model_engine.py:14](D:/projects/Speech-Emotion-Recognition/tests/test_model_engine.py:14) | `ser_lib.data.representations.spectral` | `LogMelRepresentation` | `LogMelRepresentation` | top-level |
| [tests/test_model_engine.py:15](D:/projects/Speech-Emotion-Recognition/tests/test_model_engine.py:15) | `ser_lib.data.types` | `SERSample` | `SERSample` | top-level |
| [tests/test_model_engine.py:15](D:/projects/Speech-Emotion-Recognition/tests/test_model_engine.py:15) | `ser_lib.data.types` | `TensorSpec` | `TensorSpec` | top-level |
| [tests/test_model_engine.py:16](D:/projects/Speech-Emotion-Recognition/tests/test_model_engine.py:16) | `ser_lib.data.validation` | `validate_compatibility` | `validate_compatibility` | top-level |
| [tests/test_model_engine.py:17](D:/projects/Speech-Emotion-Recognition/tests/test_model_engine.py:17) | `ser_lib.engine.checkpoint` | `load_checkpoint` | `load_checkpoint` | top-level |
| [tests/test_model_engine.py:17](D:/projects/Speech-Emotion-Recognition/tests/test_model_engine.py:17) | `ser_lib.engine.checkpoint` | `save_checkpoint` | `save_checkpoint` | top-level |
| [tests/test_model_engine.py:18](D:/projects/Speech-Emotion-Recognition/tests/test_model_engine.py:18) | `ser_lib.engine.evaluator` | `evaluate` | `evaluate` | top-level |
| [tests/test_model_engine.py:19](D:/projects/Speech-Emotion-Recognition/tests/test_model_engine.py:19) | `ser_lib.engine.trainer` | `Trainer` | `Trainer` | top-level |
| [tests/test_model_engine.py:19](D:/projects/Speech-Emotion-Recognition/tests/test_model_engine.py:19) | `ser_lib.engine.trainer` | `TrainerConfig` | `TrainerConfig` | top-level |
| [tests/test_model_engine.py:20](D:/projects/Speech-Emotion-Recognition/tests/test_model_engine.py:20) | `ser_lib.models.base` | `ModelOutput` | `ModelOutput` | top-level |
| [tests/test_model_engine.py:21](D:/projects/Speech-Emotion-Recognition/tests/test_model_engine.py:21) | `ser_lib.models.cnn_models` | `CNNBaseline` | `CNNBaseline` | top-level |
| [tests/test_model_engine.py:21](D:/projects/Speech-Emotion-Recognition/tests/test_model_engine.py:21) | `ser_lib.models.cnn_models` | `CNNBaselineConfig` | `CNNBaselineConfig` | top-level |
| [tests/test_model_engine.py:22](D:/projects/Speech-Emotion-Recognition/tests/test_model_engine.py:22) | `ser_lib.models.registry` | `model_registry` | `model_registry` | top-level |
| [tests/test_model_engine.py:23](D:/projects/Speech-Emotion-Recognition/tests/test_model_engine.py:23) | `ser_lib.inference.offline` | `EmotionPredictor` | `EmotionPredictor` | top-level |
| [tests/test_new_collate.py:4](D:/projects/Speech-Emotion-Recognition/tests/test_new_collate.py:4) | `ser_lib.data.collate` | `SERCollator` | `SERCollator` | top-level |
| [tests/test_new_collate.py:5](D:/projects/Speech-Emotion-Recognition/tests/test_new_collate.py:5) | `ser_lib.data.config` | `BatchingConfig` | `BatchingConfig` | top-level |
| [tests/test_new_collate.py:5](D:/projects/Speech-Emotion-Recognition/tests/test_new_collate.py:5) | `ser_lib.data.config` | `FixedBatching` | `FixedBatching` | top-level |
| [tests/test_new_collate.py:5](D:/projects/Speech-Emotion-Recognition/tests/test_new_collate.py:5) | `ser_lib.data.config` | `SlidingBatching` | `SlidingBatching` | top-level |
| [tests/test_new_collate.py:6](D:/projects/Speech-Emotion-Recognition/tests/test_new_collate.py:6) | `ser_lib.data.errors` | `CollationError` | `CollationError` | top-level |
| [tests/test_new_collate.py:7](D:/projects/Speech-Emotion-Recognition/tests/test_new_collate.py:7) | `ser_lib.data.types` | `SERSample` | `SERSample` | top-level |
| [tests/test_new_collate.py:7](D:/projects/Speech-Emotion-Recognition/tests/test_new_collate.py:7) | `ser_lib.data.types` | `TensorSpec` | `TensorSpec` | top-level |
| [tests/test_objectives.py:8](D:/projects/Speech-Emotion-Recognition/tests/test_objectives.py:8) | `ser_lib.engine` | `ClassificationLoss` | `ClassificationLoss` | top-level |
| [tests/test_objectives.py:8](D:/projects/Speech-Emotion-Recognition/tests/test_objectives.py:8) | `ser_lib.engine` | `LossConfig` | `LossConfig` | top-level |
| [tests/test_objectives.py:8](D:/projects/Speech-Emotion-Recognition/tests/test_objectives.py:8) | `ser_lib.engine` | `SamplingConfig` | `SamplingConfig` | top-level |
| [tests/test_objectives.py:8](D:/projects/Speech-Emotion-Recognition/tests/test_objectives.py:8) | `ser_lib.engine` | `build_weighted_sampler` | `build_weighted_sampler` | top-level |
| [tests/test_pretrained_adapter.py:11](D:/projects/Speech-Emotion-Recognition/tests/test_pretrained_adapter.py:11) | `ser_lib.artifacts` | `export_model_artifact` | `export_model_artifact` | top-level |
| [tests/test_pretrained_adapter.py:11](D:/projects/Speech-Emotion-Recognition/tests/test_pretrained_adapter.py:11) | `ser_lib.artifacts` | `load_model_artifact` | `load_model_artifact` | top-level |
| [tests/test_pretrained_adapter.py:12](D:/projects/Speech-Emotion-Recognition/tests/test_pretrained_adapter.py:12) | `ser_lib.data` | `BatchingConfig` | `BatchingConfig` | top-level |
| [tests/test_pretrained_adapter.py:12](D:/projects/Speech-Emotion-Recognition/tests/test_pretrained_adapter.py:12) | `ser_lib.data` | `CompatibilityError` | `CompatibilityError` | top-level |
| [tests/test_pretrained_adapter.py:12](D:/projects/Speech-Emotion-Recognition/tests/test_pretrained_adapter.py:12) | `ser_lib.data` | `SERCollator` | `SERCollator` | top-level |
| [tests/test_pretrained_adapter.py:12](D:/projects/Speech-Emotion-Recognition/tests/test_pretrained_adapter.py:12) | `ser_lib.data` | `SERSample` | `SERSample` | top-level |
| [tests/test_pretrained_adapter.py:12](D:/projects/Speech-Emotion-Recognition/tests/test_pretrained_adapter.py:12) | `ser_lib.data` | `TensorSpec` | `TensorSpec` | top-level |
| [tests/test_pretrained_adapter.py:12](D:/projects/Speech-Emotion-Recognition/tests/test_pretrained_adapter.py:12) | `ser_lib.data` | `validate_compatibility` | `validate_compatibility` | top-level |
| [tests/test_pretrained_adapter.py:20](D:/projects/Speech-Emotion-Recognition/tests/test_pretrained_adapter.py:20) | `ser_lib.data.config` | `AudioSettings` | `AudioSettings` | top-level |
| [tests/test_pretrained_adapter.py:20](D:/projects/Speech-Emotion-Recognition/tests/test_pretrained_adapter.py:20) | `ser_lib.data.config` | `ComponentConfig` | `ComponentConfig` | top-level |
| [tests/test_pretrained_adapter.py:20](D:/projects/Speech-Emotion-Recognition/tests/test_pretrained_adapter.py:20) | `ser_lib.data.config` | `DataConfig` | `DataConfig` | top-level |
| [tests/test_pretrained_adapter.py:21](D:/projects/Speech-Emotion-Recognition/tests/test_pretrained_adapter.py:21) | `ser_lib.engine` | `Trainer` | `Trainer` | top-level |
| [tests/test_pretrained_adapter.py:21](D:/projects/Speech-Emotion-Recognition/tests/test_pretrained_adapter.py:21) | `ser_lib.engine` | `TrainerConfig` | `TrainerConfig` | top-level |
| [tests/test_pretrained_adapter.py:22](D:/projects/Speech-Emotion-Recognition/tests/test_pretrained_adapter.py:22) | `ser_lib.models` | `HFAudioClassifier` | `HFAudioClassifier` | top-level |
| [tests/test_pretrained_adapter.py:22](D:/projects/Speech-Emotion-Recognition/tests/test_pretrained_adapter.py:22) | `ser_lib.models` | `HFAudioClassifierConfig` | `HFAudioClassifierConfig` | top-level |
| [tests/test_pretrained_adapter.py:22](D:/projects/Speech-Emotion-Recognition/tests/test_pretrained_adapter.py:22) | `ser_lib.models` | `model_registry` | `model_registry` | top-level |
| [tests/test_public_api.py:5](D:/projects/Speech-Emotion-Recognition/tests/test_public_api.py:5) | `ser_lib` | `(module)` | `ser_lib` | top-level |
| [tests/test_public_api.py:6](D:/projects/Speech-Emotion-Recognition/tests/test_public_api.py:6) | `ser_lib.artifacts` | `(module)` | `artifacts` | top-level |
| [tests/test_public_api.py:7](D:/projects/Speech-Emotion-Recognition/tests/test_public_api.py:7) | `ser_lib.core` | `(module)` | `core` | top-level |
| [tests/test_public_api.py:8](D:/projects/Speech-Emotion-Recognition/tests/test_public_api.py:8) | `ser_lib.data` | `(module)` | `data` | top-level |
| [tests/test_public_api.py:9](D:/projects/Speech-Emotion-Recognition/tests/test_public_api.py:9) | `ser_lib.engine` | `(module)` | `engine` | top-level |
| [tests/test_public_api.py:10](D:/projects/Speech-Emotion-Recognition/tests/test_public_api.py:10) | `ser_lib.inference` | `(module)` | `inference` | top-level |
| [tests/test_public_api.py:11](D:/projects/Speech-Emotion-Recognition/tests/test_public_api.py:11) | `ser_lib.models` | `(module)` | `models` | top-level |
| [tests/test_public_api.py:12](D:/projects/Speech-Emotion-Recognition/tests/test_public_api.py:12) | `ser_lib.services` | `(module)` | `services` | top-level |
| [tests/test_ravdess_and_benchmark.py:10](D:/projects/Speech-Emotion-Recognition/tests/test_ravdess_and_benchmark.py:10) | `ser_lib.benchmark` | `BenchmarkResult` | `BenchmarkResult` | top-level |
| [tests/test_ravdess_and_benchmark.py:10](D:/projects/Speech-Emotion-Recognition/tests/test_ravdess_and_benchmark.py:10) | `ser_lib.benchmark` | `compare_benchmarks` | `compare_benchmarks` | top-level |
| [tests/test_ravdess_and_benchmark.py:10](D:/projects/Speech-Emotion-Recognition/tests/test_ravdess_and_benchmark.py:10) | `ser_lib.benchmark` | `load_benchmark_result` | `load_benchmark_result` | top-level |
| [tests/test_ravdess_and_benchmark.py:10](D:/projects/Speech-Emotion-Recognition/tests/test_ravdess_and_benchmark.py:10) | `ser_lib.benchmark` | `run_benchmark` | `run_benchmark` | top-level |
| [tests/test_ravdess_and_benchmark.py:10](D:/projects/Speech-Emotion-Recognition/tests/test_ravdess_and_benchmark.py:10) | `ser_lib.benchmark` | `write_benchmark_result` | `write_benchmark_result` | top-level |
| [tests/test_ravdess_and_benchmark.py:11](D:/projects/Speech-Emotion-Recognition/tests/test_ravdess_and_benchmark.py:11) | `ser_lib.data` | `profile_manifest_audio` | `profile_manifest_audio` | top-level |
| [tests/test_ravdess_and_benchmark.py:12](D:/projects/Speech-Emotion-Recognition/tests/test_ravdess_and_benchmark.py:12) | `ser_lib.data.importers.ravdess` | `RavdessImporter` | `RavdessImporter` | top-level |
| [tests/test_registry_config.py:4](D:/projects/Speech-Emotion-Recognition/tests/test_registry_config.py:4) | `ser_lib.data.errors` | `RegistryError` | `RegistryError` | top-level |
| [tests/test_registry_config.py:5](D:/projects/Speech-Emotion-Recognition/tests/test_registry_config.py:5) | `ser_lib.data.registry` | `ComponentDescriptor` | `ComponentDescriptor` | top-level |
| [tests/test_registry_config.py:5](D:/projects/Speech-Emotion-Recognition/tests/test_registry_config.py:5) | `ser_lib.data.registry` | `Registry` | `Registry` | top-level |
| [tests/test_release_examples.py:5](D:/projects/Speech-Emotion-Recognition/tests/test_release_examples.py:5) | `ser_lib.engine` | `build_experiment_components` | `build_experiment_components` | top-level |
| [tests/test_release_examples.py:5](D:/projects/Speech-Emotion-Recognition/tests/test_release_examples.py:5) | `ser_lib.engine` | `load_experiment_config` | `load_experiment_config` | top-level |
| [tests/test_rnn_models.py:9](D:/projects/Speech-Emotion-Recognition/tests/test_rnn_models.py:9) | `ser_lib.artifacts` | `export_model_artifact` | `export_model_artifact` | top-level |
| [tests/test_rnn_models.py:9](D:/projects/Speech-Emotion-Recognition/tests/test_rnn_models.py:9) | `ser_lib.artifacts` | `load_model_artifact` | `load_model_artifact` | top-level |
| [tests/test_rnn_models.py:10](D:/projects/Speech-Emotion-Recognition/tests/test_rnn_models.py:10) | `ser_lib.data` | `BatchingConfig` | `BatchingConfig` | top-level |
| [tests/test_rnn_models.py:10](D:/projects/Speech-Emotion-Recognition/tests/test_rnn_models.py:10) | `ser_lib.data` | `SERCollator` | `SERCollator` | top-level |
| [tests/test_rnn_models.py:10](D:/projects/Speech-Emotion-Recognition/tests/test_rnn_models.py:10) | `ser_lib.data` | `SERSample` | `SERSample` | top-level |
| [tests/test_rnn_models.py:10](D:/projects/Speech-Emotion-Recognition/tests/test_rnn_models.py:10) | `ser_lib.data` | `TensorSpec` | `TensorSpec` | top-level |
| [tests/test_rnn_models.py:11](D:/projects/Speech-Emotion-Recognition/tests/test_rnn_models.py:11) | `ser_lib.data.config` | `AudioSettings` | `AudioSettings` | top-level |
| [tests/test_rnn_models.py:11](D:/projects/Speech-Emotion-Recognition/tests/test_rnn_models.py:11) | `ser_lib.data.config` | `ComponentConfig` | `ComponentConfig` | top-level |
| [tests/test_rnn_models.py:11](D:/projects/Speech-Emotion-Recognition/tests/test_rnn_models.py:11) | `ser_lib.data.config` | `DataConfig` | `DataConfig` | top-level |
| [tests/test_rnn_models.py:12](D:/projects/Speech-Emotion-Recognition/tests/test_rnn_models.py:12) | `ser_lib.engine` | `Trainer` | `Trainer` | top-level |
| [tests/test_rnn_models.py:12](D:/projects/Speech-Emotion-Recognition/tests/test_rnn_models.py:12) | `ser_lib.engine` | `TrainerConfig` | `TrainerConfig` | top-level |
| [tests/test_rnn_models.py:13](D:/projects/Speech-Emotion-Recognition/tests/test_rnn_models.py:13) | `ser_lib.models` | `GRUBaseline` | `GRUBaseline` | top-level |
| [tests/test_rnn_models.py:13](D:/projects/Speech-Emotion-Recognition/tests/test_rnn_models.py:13) | `ser_lib.models` | `GRUBaselineConfig` | `GRUBaselineConfig` | top-level |
| [tests/test_rnn_models.py:13](D:/projects/Speech-Emotion-Recognition/tests/test_rnn_models.py:13) | `ser_lib.models` | `model_registry` | `model_registry` | top-level |
| [tests/test_runtime_capabilities.py:6](D:/projects/Speech-Emotion-Recognition/tests/test_runtime_capabilities.py:6) | `ser_lib` | `RuntimeCapabilities` | `RuntimeCapabilities` | top-level |
| [tests/test_runtime_capabilities.py:6](D:/projects/Speech-Emotion-Recognition/tests/test_runtime_capabilities.py:6) | `ser_lib` | `get_runtime_capabilities` | `get_runtime_capabilities` | top-level |
| [tests/test_runtime_host_metrics.py:5](D:/projects/Speech-Emotion-Recognition/tests/test_runtime_host_metrics.py:5) | `ser_lib.runtime` | `get_runtime_metrics` | `get_runtime_metrics` | top-level |
| [tests/test_runtime_metrics.py:6](D:/projects/Speech-Emotion-Recognition/tests/test_runtime_metrics.py:6) | `ser_lib` | `RuntimeMetrics` | `RuntimeMetrics` | top-level |
| [tests/test_runtime_metrics.py:6](D:/projects/Speech-Emotion-Recognition/tests/test_runtime_metrics.py:6) | `ser_lib` | `get_runtime_metrics` | `get_runtime_metrics` | top-level |
| [tests/test_runtime_metrics.py:7](D:/projects/Speech-Emotion-Recognition/tests/test_runtime_metrics.py:7) | `ser_lib.services` | `RuntimeService` | `RuntimeService` | top-level |
| [tests/test_schema_migrations.py:5](D:/projects/Speech-Emotion-Recognition/tests/test_schema_migrations.py:5) | `ser_lib.core` | `MigrationRegistry` | `MigrationRegistry` | top-level |
| [tests/test_schema_migrations.py:5](D:/projects/Speech-Emotion-Recognition/tests/test_schema_migrations.py:5) | `ser_lib.core` | `SchemaMigrationError` | `SchemaMigrationError` | top-level |
| [tests/test_service_catalog_presets.py:5](D:/projects/Speech-Emotion-Recognition/tests/test_service_catalog_presets.py:5) | `ser_lib.engine` | `ExperimentConfig` | `ExperimentConfig` | top-level |
| [tests/test_service_catalog_presets.py:6](D:/projects/Speech-Emotion-Recognition/tests/test_service_catalog_presets.py:6) | `ser_lib.services` | `CatalogService` | `CatalogService` | top-level |
| [tests/test_services.py:6](D:/projects/Speech-Emotion-Recognition/tests/test_services.py:6) | `ser_lib.data` | `SERBatch` | `SERBatch` | top-level |
| [tests/test_services.py:6](D:/projects/Speech-Emotion-Recognition/tests/test_services.py:6) | `ser_lib.data` | `TensorSpec` | `TensorSpec` | top-level |
| [tests/test_services.py:7](D:/projects/Speech-Emotion-Recognition/tests/test_services.py:7) | `ser_lib.data.config` | `AudioSettings` | `AudioSettings` | top-level |
| [tests/test_services.py:7](D:/projects/Speech-Emotion-Recognition/tests/test_services.py:7) | `ser_lib.data.config` | `BatchingConfig` | `BatchingConfig` | top-level |
| [tests/test_services.py:7](D:/projects/Speech-Emotion-Recognition/tests/test_services.py:7) | `ser_lib.data.config` | `ComponentConfig` | `ComponentConfig` | top-level |
| [tests/test_services.py:7](D:/projects/Speech-Emotion-Recognition/tests/test_services.py:7) | `ser_lib.data.config` | `DataConfig` | `DataConfig` | top-level |
| [tests/test_services.py:8](D:/projects/Speech-Emotion-Recognition/tests/test_services.py:8) | `ser_lib.data.validation` | `ModelSpec` | `ModelSpec` | top-level |
| [tests/test_services.py:9](D:/projects/Speech-Emotion-Recognition/tests/test_services.py:9) | `ser_lib.engine` | `Trainer` | `Trainer` | top-level |
| [tests/test_services.py:9](D:/projects/Speech-Emotion-Recognition/tests/test_services.py:9) | `ser_lib.engine` | `TrainerConfig` | `TrainerConfig` | top-level |
| [tests/test_services.py:10](D:/projects/Speech-Emotion-Recognition/tests/test_services.py:10) | `ser_lib.models` | `CNNBaseline` | `CNNBaseline` | top-level |
| [tests/test_services.py:10](D:/projects/Speech-Emotion-Recognition/tests/test_services.py:10) | `ser_lib.models` | `ModelOutput` | `ModelOutput` | top-level |
| [tests/test_services.py:10](D:/projects/Speech-Emotion-Recognition/tests/test_services.py:10) | `ser_lib.models` | `SERModel` | `SERModel` | top-level |
| [tests/test_services.py:11](D:/projects/Speech-Emotion-Recognition/tests/test_services.py:11) | `ser_lib.services` | `ArtifactService` | `ArtifactService` | top-level |
| [tests/test_services.py:11](D:/projects/Speech-Emotion-Recognition/tests/test_services.py:11) | `ser_lib.services` | `CatalogService` | `CatalogService` | top-level |
| [tests/test_services.py:11](D:/projects/Speech-Emotion-Recognition/tests/test_services.py:11) | `ser_lib.services` | `DatasetService` | `DatasetService` | top-level |
| [tests/test_services.py:11](D:/projects/Speech-Emotion-Recognition/tests/test_services.py:11) | `ser_lib.services` | `EvaluationService` | `EvaluationService` | top-level |
| [tests/test_services.py:11](D:/projects/Speech-Emotion-Recognition/tests/test_services.py:11) | `ser_lib.services` | `RuntimeService` | `RuntimeService` | top-level |
| [tests/test_services.py:11](D:/projects/Speech-Emotion-Recognition/tests/test_services.py:11) | `ser_lib.services` | `TrainingService` | `TrainingService` | top-level |
| [tests/test_streaming_inference.py:8](D:/projects/Speech-Emotion-Recognition/tests/test_streaming_inference.py:8) | `ser_lib.inference` | `PredictionResult` | `PredictionResult` | top-level |
| [tests/test_streaming_inference.py:8](D:/projects/Speech-Emotion-Recognition/tests/test_streaming_inference.py:8) | `ser_lib.inference` | `StreamingConfig` | `StreamingConfig` | top-level |
| [tests/test_streaming_inference.py:8](D:/projects/Speech-Emotion-Recognition/tests/test_streaming_inference.py:8) | `ser_lib.inference` | `StreamingEmotionRecognizer` | `StreamingEmotionRecognizer` | top-level |
| [tests/test_trainer_observability.py:9](D:/projects/Speech-Emotion-Recognition/tests/test_trainer_observability.py:9) | `ser_lib.core` | `CancellationToken` | `CancellationToken` | top-level |
| [tests/test_trainer_observability.py:9](D:/projects/Speech-Emotion-Recognition/tests/test_trainer_observability.py:9) | `ser_lib.core` | `CheckpointEvent` | `CheckpointEvent` | top-level |
| [tests/test_trainer_observability.py:9](D:/projects/Speech-Emotion-Recognition/tests/test_trainer_observability.py:9) | `ser_lib.core` | `LifecycleEvent` | `LifecycleEvent` | top-level |
| [tests/test_trainer_observability.py:9](D:/projects/Speech-Emotion-Recognition/tests/test_trainer_observability.py:9) | `ser_lib.core` | `MetricEvent` | `MetricEvent` | top-level |
| [tests/test_trainer_observability.py:9](D:/projects/Speech-Emotion-Recognition/tests/test_trainer_observability.py:9) | `ser_lib.core` | `OperationCancelled` | `OperationCancelled` | top-level |
| [tests/test_trainer_observability.py:9](D:/projects/Speech-Emotion-Recognition/tests/test_trainer_observability.py:9) | `ser_lib.core` | `ProgressEvent` | `ProgressEvent` | top-level |
| [tests/test_trainer_observability.py:17](D:/projects/Speech-Emotion-Recognition/tests/test_trainer_observability.py:17) | `ser_lib.data` | `BatchingConfig` | `BatchingConfig` | top-level |
| [tests/test_trainer_observability.py:17](D:/projects/Speech-Emotion-Recognition/tests/test_trainer_observability.py:17) | `ser_lib.data` | `SERCollator` | `SERCollator` | top-level |
| [tests/test_trainer_observability.py:17](D:/projects/Speech-Emotion-Recognition/tests/test_trainer_observability.py:17) | `ser_lib.data` | `SERSample` | `SERSample` | top-level |
| [tests/test_trainer_observability.py:17](D:/projects/Speech-Emotion-Recognition/tests/test_trainer_observability.py:17) | `ser_lib.data` | `TensorSpec` | `TensorSpec` | top-level |
| [tests/test_trainer_observability.py:18](D:/projects/Speech-Emotion-Recognition/tests/test_trainer_observability.py:18) | `ser_lib.engine` | `ObservabilityConfig` | `ObservabilityConfig` | top-level |
| [tests/test_trainer_observability.py:18](D:/projects/Speech-Emotion-Recognition/tests/test_trainer_observability.py:18) | `ser_lib.engine` | `Trainer` | `Trainer` | top-level |
| [tests/test_trainer_observability.py:18](D:/projects/Speech-Emotion-Recognition/tests/test_trainer_observability.py:18) | `ser_lib.engine` | `TrainerConfig` | `TrainerConfig` | top-level |
| [tests/test_trainer_observability.py:19](D:/projects/Speech-Emotion-Recognition/tests/test_trainer_observability.py:19) | `ser_lib.models` | `CNNBaseline` | `CNNBaseline` | top-level |
| [tests/test_training_history.py:9](D:/projects/Speech-Emotion-Recognition/tests/test_training_history.py:9) | `ser_lib.engine` | `TrainingHistoryInfo` | `TrainingHistoryInfo` | top-level |
| [tests/test_training_history.py:9](D:/projects/Speech-Emotion-Recognition/tests/test_training_history.py:9) | `ser_lib.engine` | `load_training_history` | `load_training_history` | top-level |
| [tests/test_training_history.py:10](D:/projects/Speech-Emotion-Recognition/tests/test_training_history.py:10) | `ser_lib.services` | `TrainingService` | `TrainingService` | top-level |
| [tests/test_training_lineage.py:8](D:/projects/Speech-Emotion-Recognition/tests/test_training_lineage.py:8) | `ser_lib` | `TrainingRunMetadata` | `TrainingRunMetadata` | top-level |
| [tests/test_training_lineage.py:9](D:/projects/Speech-Emotion-Recognition/tests/test_training_lineage.py:9) | `ser_lib.data` | `BatchingConfig` | `BatchingConfig` | top-level |
| [tests/test_training_lineage.py:9](D:/projects/Speech-Emotion-Recognition/tests/test_training_lineage.py:9) | `ser_lib.data` | `SERCollator` | `SERCollator` | top-level |
| [tests/test_training_lineage.py:9](D:/projects/Speech-Emotion-Recognition/tests/test_training_lineage.py:9) | `ser_lib.data` | `SERSample` | `SERSample` | top-level |
| [tests/test_training_lineage.py:9](D:/projects/Speech-Emotion-Recognition/tests/test_training_lineage.py:9) | `ser_lib.data` | `TensorSpec` | `TensorSpec` | top-level |
| [tests/test_training_lineage.py:10](D:/projects/Speech-Emotion-Recognition/tests/test_training_lineage.py:10) | `ser_lib.data.config` | `AudioSettings` | `AudioSettings` | top-level |
| [tests/test_training_lineage.py:10](D:/projects/Speech-Emotion-Recognition/tests/test_training_lineage.py:10) | `ser_lib.data.config` | `ComponentConfig` | `ComponentConfig` | top-level |
| [tests/test_training_lineage.py:10](D:/projects/Speech-Emotion-Recognition/tests/test_training_lineage.py:10) | `ser_lib.data.config` | `DataConfig` | `DataConfig` | top-level |
| [tests/test_training_lineage.py:11](D:/projects/Speech-Emotion-Recognition/tests/test_training_lineage.py:11) | `ser_lib.engine` | `ExperimentConfig` | `ExperimentConfig` | top-level |
| [tests/test_training_lineage.py:11](D:/projects/Speech-Emotion-Recognition/tests/test_training_lineage.py:11) | `ser_lib.engine` | `ModelConfig` | `ModelConfig` | top-level |
| [tests/test_training_lineage.py:11](D:/projects/Speech-Emotion-Recognition/tests/test_training_lineage.py:11) | `ser_lib.engine` | `TrainerConfig` | `TrainerConfig` | top-level |
| [tests/test_training_lineage.py:12](D:/projects/Speech-Emotion-Recognition/tests/test_training_lineage.py:12) | `ser_lib.models` | `CNNBaseline` | `CNNBaseline` | top-level |
| [tests/test_training_lineage.py:13](D:/projects/Speech-Emotion-Recognition/tests/test_training_lineage.py:13) | `ser_lib.services` | `ArtifactService` | `ArtifactService` | top-level |
| [tests/test_training_lineage.py:13](D:/projects/Speech-Emotion-Recognition/tests/test_training_lineage.py:13) | `ser_lib.services` | `TrainingService` | `TrainingService` | top-level |
| [tests/test_training_result.py:9](D:/projects/Speech-Emotion-Recognition/tests/test_training_result.py:9) | `ser_lib` | `TrainingResult` | `RootTrainingResult` | top-level |
| [tests/test_training_result.py:10](D:/projects/Speech-Emotion-Recognition/tests/test_training_result.py:10) | `ser_lib.core` | `CancellationToken` | `CancellationToken` | top-level |
| [tests/test_training_result.py:10](D:/projects/Speech-Emotion-Recognition/tests/test_training_result.py:10) | `ser_lib.core` | `OperationCancelled` | `OperationCancelled` | top-level |
| [tests/test_training_result.py:11](D:/projects/Speech-Emotion-Recognition/tests/test_training_result.py:11) | `ser_lib.data` | `BatchingConfig` | `BatchingConfig` | top-level |
| [tests/test_training_result.py:11](D:/projects/Speech-Emotion-Recognition/tests/test_training_result.py:11) | `ser_lib.data` | `SERCollator` | `SERCollator` | top-level |
| [tests/test_training_result.py:11](D:/projects/Speech-Emotion-Recognition/tests/test_training_result.py:11) | `ser_lib.data` | `SERSample` | `SERSample` | top-level |
| [tests/test_training_result.py:11](D:/projects/Speech-Emotion-Recognition/tests/test_training_result.py:11) | `ser_lib.data` | `TensorSpec` | `TensorSpec` | top-level |
| [tests/test_training_result.py:12](D:/projects/Speech-Emotion-Recognition/tests/test_training_result.py:12) | `ser_lib.engine` | `Trainer` | `Trainer` | top-level |
| [tests/test_training_result.py:12](D:/projects/Speech-Emotion-Recognition/tests/test_training_result.py:12) | `ser_lib.engine` | `TrainerConfig` | `TrainerConfig` | top-level |
| [tests/test_training_result.py:12](D:/projects/Speech-Emotion-Recognition/tests/test_training_result.py:12) | `ser_lib.engine` | `TrainingResult` | `TrainingResult` | top-level |
| [tests/test_training_result.py:12](D:/projects/Speech-Emotion-Recognition/tests/test_training_result.py:12) | `ser_lib.engine` | `TrainingStatus` | `TrainingStatus` | top-level |
| [tests/test_training_result.py:13](D:/projects/Speech-Emotion-Recognition/tests/test_training_result.py:13) | `ser_lib.models` | `CNNBaseline` | `CNNBaseline` | top-level |
| [tests/test_training_run_catalog.py:11](D:/projects/Speech-Emotion-Recognition/tests/test_training_run_catalog.py:11) | `ser_lib.core` | `CancellationToken` | `CancellationToken` | top-level |
| [tests/test_training_run_catalog.py:11](D:/projects/Speech-Emotion-Recognition/tests/test_training_run_catalog.py:11) | `ser_lib.core` | `OperationCancelled` | `OperationCancelled` | top-level |
| [tests/test_training_run_catalog.py:11](D:/projects/Speech-Emotion-Recognition/tests/test_training_run_catalog.py:11) | `ser_lib.core` | `ProgressEvent` | `ProgressEvent` | top-level |
| [tests/test_training_run_catalog.py:12](D:/projects/Speech-Emotion-Recognition/tests/test_training_run_catalog.py:12) | `ser_lib.data` | `BatchingConfig` | `BatchingConfig` | top-level |
| [tests/test_training_run_catalog.py:12](D:/projects/Speech-Emotion-Recognition/tests/test_training_run_catalog.py:12) | `ser_lib.data` | `SERCollator` | `SERCollator` | top-level |
| [tests/test_training_run_catalog.py:12](D:/projects/Speech-Emotion-Recognition/tests/test_training_run_catalog.py:12) | `ser_lib.data` | `SERSample` | `SERSample` | top-level |
| [tests/test_training_run_catalog.py:12](D:/projects/Speech-Emotion-Recognition/tests/test_training_run_catalog.py:12) | `ser_lib.data` | `TensorSpec` | `TensorSpec` | top-level |
| [tests/test_training_run_catalog.py:13](D:/projects/Speech-Emotion-Recognition/tests/test_training_run_catalog.py:13) | `ser_lib.data.config` | `AudioSettings` | `AudioSettings` | top-level |
| [tests/test_training_run_catalog.py:13](D:/projects/Speech-Emotion-Recognition/tests/test_training_run_catalog.py:13) | `ser_lib.data.config` | `ComponentConfig` | `ComponentConfig` | top-level |
| [tests/test_training_run_catalog.py:13](D:/projects/Speech-Emotion-Recognition/tests/test_training_run_catalog.py:13) | `ser_lib.data.config` | `DataConfig` | `DataConfig` | top-level |
| [tests/test_training_run_catalog.py:14](D:/projects/Speech-Emotion-Recognition/tests/test_training_run_catalog.py:14) | `ser_lib.engine` | `ExperimentConfig` | `ExperimentConfig` | top-level |
| [tests/test_training_run_catalog.py:14](D:/projects/Speech-Emotion-Recognition/tests/test_training_run_catalog.py:14) | `ser_lib.engine` | `ModelConfig` | `ModelConfig` | top-level |
| [tests/test_training_run_catalog.py:14](D:/projects/Speech-Emotion-Recognition/tests/test_training_run_catalog.py:14) | `ser_lib.engine` | `Trainer` | `Trainer` | top-level |
| [tests/test_training_run_catalog.py:14](D:/projects/Speech-Emotion-Recognition/tests/test_training_run_catalog.py:14) | `ser_lib.engine` | `TrainerConfig` | `TrainerConfig` | top-level |
| [tests/test_training_run_catalog.py:14](D:/projects/Speech-Emotion-Recognition/tests/test_training_run_catalog.py:14) | `ser_lib.engine` | `TrainingRunInfo` | `TrainingRunInfo` | top-level |
| [tests/test_training_run_catalog.py:14](D:/projects/Speech-Emotion-Recognition/tests/test_training_run_catalog.py:14) | `ser_lib.engine` | `load_training_run_info` | `load_training_run_info` | top-level |
| [tests/test_training_run_catalog.py:14](D:/projects/Speech-Emotion-Recognition/tests/test_training_run_catalog.py:14) | `ser_lib.engine` | `scan_training_runs` | `scan_training_runs` | top-level |
| [tests/test_training_run_catalog.py:23](D:/projects/Speech-Emotion-Recognition/tests/test_training_run_catalog.py:23) | `ser_lib.models` | `CNNBaseline` | `CNNBaseline` | top-level |
| [tests/test_training_run_catalog.py:24](D:/projects/Speech-Emotion-Recognition/tests/test_training_run_catalog.py:24) | `ser_lib.services` | `TrainingService` | `TrainingService` | top-level |
| [tests/test_training_run_detail.py:9](D:/projects/Speech-Emotion-Recognition/tests/test_training_run_detail.py:9) | `ser_lib.engine` | `TrainingRunDetail` | `TrainingRunDetail` | top-level |
| [tests/test_training_run_detail.py:9](D:/projects/Speech-Emotion-Recognition/tests/test_training_run_detail.py:9) | `ser_lib.engine` | `TrainingRunInfo` | `TrainingRunInfo` | top-level |
| [tests/test_training_run_detail.py:10](D:/projects/Speech-Emotion-Recognition/tests/test_training_run_detail.py:10) | `ser_lib.services` | `TrainingService` | `TrainingService` | top-level |
| [tests/test_transformer_models.py:9](D:/projects/Speech-Emotion-Recognition/tests/test_transformer_models.py:9) | `ser_lib.artifacts` | `export_model_artifact` | `export_model_artifact` | top-level |
| [tests/test_transformer_models.py:9](D:/projects/Speech-Emotion-Recognition/tests/test_transformer_models.py:9) | `ser_lib.artifacts` | `load_model_artifact` | `load_model_artifact` | top-level |
| [tests/test_transformer_models.py:10](D:/projects/Speech-Emotion-Recognition/tests/test_transformer_models.py:10) | `ser_lib.data` | `BatchingConfig` | `BatchingConfig` | top-level |
| [tests/test_transformer_models.py:10](D:/projects/Speech-Emotion-Recognition/tests/test_transformer_models.py:10) | `ser_lib.data` | `SERCollator` | `SERCollator` | top-level |
| [tests/test_transformer_models.py:10](D:/projects/Speech-Emotion-Recognition/tests/test_transformer_models.py:10) | `ser_lib.data` | `SERSample` | `SERSample` | top-level |
| [tests/test_transformer_models.py:10](D:/projects/Speech-Emotion-Recognition/tests/test_transformer_models.py:10) | `ser_lib.data` | `TensorSpec` | `TensorSpec` | top-level |
| [tests/test_transformer_models.py:11](D:/projects/Speech-Emotion-Recognition/tests/test_transformer_models.py:11) | `ser_lib.data.config` | `AudioSettings` | `AudioSettings` | top-level |
| [tests/test_transformer_models.py:11](D:/projects/Speech-Emotion-Recognition/tests/test_transformer_models.py:11) | `ser_lib.data.config` | `ComponentConfig` | `ComponentConfig` | top-level |
| [tests/test_transformer_models.py:11](D:/projects/Speech-Emotion-Recognition/tests/test_transformer_models.py:11) | `ser_lib.data.config` | `DataConfig` | `DataConfig` | top-level |
| [tests/test_transformer_models.py:12](D:/projects/Speech-Emotion-Recognition/tests/test_transformer_models.py:12) | `ser_lib.engine` | `Trainer` | `Trainer` | top-level |
| [tests/test_transformer_models.py:12](D:/projects/Speech-Emotion-Recognition/tests/test_transformer_models.py:12) | `ser_lib.engine` | `TrainerConfig` | `TrainerConfig` | top-level |
| [tests/test_transformer_models.py:13](D:/projects/Speech-Emotion-Recognition/tests/test_transformer_models.py:13) | `ser_lib.models` | `TransformerBaseline` | `TransformerBaseline` | top-level |
| [tests/test_transformer_models.py:13](D:/projects/Speech-Emotion-Recognition/tests/test_transformer_models.py:13) | `ser_lib.models` | `TransformerBaselineConfig` | `TransformerBaselineConfig` | top-level |
| [tests/test_transformer_models.py:13](D:/projects/Speech-Emotion-Recognition/tests/test_transformer_models.py:13) | `ser_lib.models` | `model_registry` | `model_registry` | top-level |

## E. 每个模块的定义、消费者与测试影响

### ser_lib/__init__.py

处理：**瘦身**。目标：`ser_lib/__init__.py + ser_lib/_version.py`。理由：聚合导出过多、版本回引；收缩根 API 并惰性解析重型导出。

直接 import 消费者（含测试；从公共包重导入的间接消费者还需沿 D/C 展开）：

- [ser_lib/artifacts/exporter.py:16](D:/projects/Speech-Emotion-Recognition/ser_lib/artifacts/exporter.py:16)；行 16
- [ser_lib/artifacts/loader.py:14](D:/projects/Speech-Emotion-Recognition/ser_lib/artifacts/loader.py:14)；行 14
- [ser_lib/cli/main.py:15](D:/projects/Speech-Emotion-Recognition/ser_lib/cli/main.py:15)；行 15
- [ser_lib/services/evaluation.py:57](D:/projects/Speech-Emotion-Recognition/ser_lib/services/evaluation.py:57)；行 57
- [ser_lib/services/training.py:68](D:/projects/Speech-Emotion-Recognition/ser_lib/services/training.py:68)；行 68
- [tests/test_artifacts.py:8](D:/projects/Speech-Emotion-Recognition/tests/test_artifacts.py:8)；行 8
- [tests/test_compatibility_report.py:7](D:/projects/Speech-Emotion-Recognition/tests/test_compatibility_report.py:7)；行 7, 8
- [tests/test_component_catalog.py:7](D:/projects/Speech-Emotion-Recognition/tests/test_component_catalog.py:7)；行 7
- [tests/test_experiment_presets.py:9](D:/projects/Speech-Emotion-Recognition/tests/test_experiment_presets.py:9)；行 9
- [tests/test_experiment_validation.py:6](D:/projects/Speech-Emotion-Recognition/tests/test_experiment_validation.py:6)；行 6, 7
- [tests/test_public_api.py:5](D:/projects/Speech-Emotion-Recognition/tests/test_public_api.py:5)；行 5
- [tests/test_runtime_capabilities.py:6](D:/projects/Speech-Emotion-Recognition/tests/test_runtime_capabilities.py:6)；行 6
- [tests/test_runtime_metrics.py:6](D:/projects/Speech-Emotion-Recognition/tests/test_runtime_metrics.py:6)；行 6
- [tests/test_training_lineage.py:8](D:/projects/Speech-Emotion-Recognition/tests/test_training_lineage.py:8)；行 8
- [tests/test_training_result.py:9](D:/projects/Speech-Emotion-Recognition/tests/test_training_result.py:9)；行 9

| class/function/method | 定义行 | 职责说明（源码 docstring） |
| --- | --- | --- |

### ser_lib/artifacts/__init__.py

处理：**瘦身**。目标：`原路径`。理由：更新 config/退役包装导出及内置注册顺序，不改变算法。

直接 import 消费者（含测试；从公共包重导入的间接消费者还需沿 D/C 展开）：

- [examples/predict_artifact.py:8](D:/projects/Speech-Emotion-Recognition/examples/predict_artifact.py:8)；行 8
- [ser_lib/__init__.py:14](D:/projects/Speech-Emotion-Recognition/ser_lib/__init__.py:14)；行 14
- [ser_lib/cli/workflows.py:14](D:/projects/Speech-Emotion-Recognition/ser_lib/cli/workflows.py:14)；行 14
- [ser_lib/services/artifacts.py:11](D:/projects/Speech-Emotion-Recognition/ser_lib/services/artifacts.py:11)；行 11
- [ser_lib/services/inference.py:22](D:/projects/Speech-Emotion-Recognition/ser_lib/services/inference.py:22)；行 22
- [tests/test_artifact_catalog.py:4](D:/projects/Speech-Emotion-Recognition/tests/test_artifact_catalog.py:4)；行 4
- [tests/test_artifact_inspect.py:6](D:/projects/Speech-Emotion-Recognition/tests/test_artifact_inspect.py:6)；行 6
- [tests/test_artifact_progress.py:5](D:/projects/Speech-Emotion-Recognition/tests/test_artifact_progress.py:5)；行 5
- [tests/test_artifacts.py:9](D:/projects/Speech-Emotion-Recognition/tests/test_artifacts.py:9)；行 9
- [tests/test_cli_lineage.py:11](D:/projects/Speech-Emotion-Recognition/tests/test_cli_lineage.py:11)；行 11
- [tests/test_pretrained_adapter.py:11](D:/projects/Speech-Emotion-Recognition/tests/test_pretrained_adapter.py:11)；行 11
- [tests/test_public_api.py:6](D:/projects/Speech-Emotion-Recognition/tests/test_public_api.py:6)；行 6
- [tests/test_rnn_models.py:9](D:/projects/Speech-Emotion-Recognition/tests/test_rnn_models.py:9)；行 9
- [tests/test_transformer_models.py:9](D:/projects/Speech-Emotion-Recognition/tests/test_transformer_models.py:9)；行 9

| class/function/method | 定义行 | 职责说明（源码 docstring） |
| --- | --- | --- |

### ser_lib/artifacts/catalog.py

处理：**瘦身**。目标：`原路径`。理由：保留扫描，ArtifactInfo 扁平复制改最小 entry+manifest。

直接 import 消费者（含测试；从公共包重导入的间接消费者还需沿 D/C 展开）：

- [ser_lib/artifacts/__init__.py:1](D:/projects/Speech-Emotion-Recognition/ser_lib/artifacts/__init__.py:1)；行 1

| class/function/method | 定义行 | 职责说明（源码 docstring） |
| --- | --- | --- |
| `ArtifactInfo` | [ser_lib/artifacts/catalog.py:16](D:/projects/Speech-Emotion-Recognition/ser_lib/artifacts/catalog.py:16) | 模型管理列表所需的轻量、JSON-safe Artifact 信息。 |
| `ArtifactInfo.to_dict(self) -> dict[str, Any]` | [ser_lib/artifacts/catalog.py:38](D:/projects/Speech-Emotion-Recognition/ser_lib/artifacts/catalog.py:38) |  |
| `ArtifactScanFailure` | [ser_lib/artifacts/catalog.py:62](D:/projects/Speech-Emotion-Recognition/ser_lib/artifacts/catalog.py:62) | 领域/公开定义 |
| `ArtifactScanFailure.to_dict(self) -> dict[str, str]` | [ser_lib/artifacts/catalog.py:67](D:/projects/Speech-Emotion-Recognition/ser_lib/artifacts/catalog.py:67) |  |
| `ArtifactCatalog` | [ser_lib/artifacts/catalog.py:76](D:/projects/Speech-Emotion-Recognition/ser_lib/artifacts/catalog.py:76) | 领域/公开定义 |
| `ArtifactCatalog.total(self) -> int` | [ser_lib/artifacts/catalog.py:82](D:/projects/Speech-Emotion-Recognition/ser_lib/artifacts/catalog.py:82) |  |
| `ArtifactCatalog.to_dict(self) -> dict[str, Any]` | [ser_lib/artifacts/catalog.py:85](D:/projects/Speech-Emotion-Recognition/ser_lib/artifacts/catalog.py:85) |  |
| `_optional_str(value: Any) -> str \| None` | [ser_lib/artifacts/catalog.py:94](D:/projects/Speech-Emotion-Recognition/ser_lib/artifacts/catalog.py:94) | 见实现；私有辅助 |
| `_optional_nonnegative_int(value: Any) -> int \| None` | [ser_lib/artifacts/catalog.py:98](D:/projects/Speech-Emotion-Recognition/ser_lib/artifacts/catalog.py:98) | 见实现；私有辅助 |
| `_artifact_info(directory: Path, manifest: ModelArtifactManifest) -> ArtifactInfo` | [ser_lib/artifacts/catalog.py:102](D:/projects/Speech-Emotion-Recognition/ser_lib/artifacts/catalog.py:102) | 见实现；私有辅助 |
| `_candidate_directories(root: Path, *, recursive: bool) -> list[Path]` | [ser_lib/artifacts/catalog.py:145](D:/projects/Speech-Emotion-Recognition/ser_lib/artifacts/catalog.py:145) | 见实现；私有辅助 |
| `scan_model_artifacts(root: Path \| str, *, recursive: bool=False, fail_fast: bool=False, event_callback: EventCallback \| None=None, cancellation: CancellationCheck \| None=None) -> ArtifactCatalog` | [ser_lib/artifacts/catalog.py:164](D:/projects/Speech-Emotion-Recognition/ser_lib/artifacts/catalog.py:164) | 扫描 Artifact 根目录；只调用轻量 inspect，绝不计算文件 SHA256。 |

### ser_lib/artifacts/exporter.py

处理：**瘦身**。目标：`原路径`。理由：接回通用 provenance，版本不回引根包；hash 私有重复收敛。

直接 import 消费者（含测试；从公共包重导入的间接消费者还需沿 D/C 展开）：

- [ser_lib/artifacts/__init__.py:7](D:/projects/Speech-Emotion-Recognition/ser_lib/artifacts/__init__.py:7)；行 7

| class/function/method | 定义行 | 职责说明（源码 docstring） |
| --- | --- | --- |
| `_sha256(path: Path) -> str` | [ser_lib/artifacts/exporter.py:31](D:/projects/Speech-Emotion-Recognition/ser_lib/artifacts/exporter.py:31) | 见实现；私有辅助 |
| `_sha256_with_progress(path: Path, *, cancellation: CancellationCheck \| None=None, on_chunk: Callable[[int], None] \| None=None) -> str` | [ser_lib/artifacts/exporter.py:39](D:/projects/Speech-Emotion-Recognition/ser_lib/artifacts/exporter.py:39) | 见实现；私有辅助 |
| `_write_json(path: Path, value: Any) -> None` | [ser_lib/artifacts/exporter.py:61](D:/projects/Speech-Emotion-Recognition/ser_lib/artifacts/exporter.py:61) | 见实现；私有辅助 |
| `_model_card_markdown(card: ModelCard, model_name: str, labels: Mapping[int, str]) -> str` | [ser_lib/artifacts/exporter.py:65](D:/projects/Speech-Emotion-Recognition/ser_lib/artifacts/exporter.py:65) | 见实现；私有辅助 |
| `_standard_metadata(model: SERModel, data_config: DataConfig, supplied: Mapping[str, Any] \| None) -> dict[str, Any]` | [ser_lib/artifacts/exporter.py:80](D:/projects/Speech-Emotion-Recognition/ser_lib/artifacts/exporter.py:80) | 为新 artifact 补充稳定管理字段，同时尊重调用方显式值。 |
| `export_model_artifact(directory: Path \| str, model: SERModel, *, model_name: str, model_params: Mapping[str, Any] \| None=None, data_config: DataConfig, labels: Mapping[int, str], metrics: Mapping[str, float] \| None=None, metadata: Mapping[str, Any] \| None=None, model_card: ModelCard \| Mapping[str, Any] \| None=None, event_callback: EventCallback \| None=None, cancellation: CancellationCheck \| None=None, event_context: EventContext \| None=None) -> Path` | [ser_lib/artifacts/exporter.py:98](D:/projects/Speech-Emotion-Recognition/ser_lib/artifacts/exporter.py:98) | 导出 schema v2 artifact，并暴露阶段/字节级进度与协作式取消。 |

### ser_lib/artifacts/loader.py

处理：**瘦身**。目标：`原路径 + ser_lib/artifacts/migrations.py`。理由：保留 inspect/verify/load 分层、legacy 门禁；旧 hash 壳按引用清理。

直接 import 消费者（含测试；从公共包重导入的间接消费者还需沿 D/C 展开）：

- [ser_lib/artifacts/__init__.py:8](D:/projects/Speech-Emotion-Recognition/ser_lib/artifacts/__init__.py:8)；行 8
- [ser_lib/artifacts/catalog.py:9](D:/projects/Speech-Emotion-Recognition/ser_lib/artifacts/catalog.py:9)；行 9
- [tests/test_artifact_catalog.py:55](D:/projects/Speech-Emotion-Recognition/tests/test_artifact_catalog.py:55)；行 55
- [tests/test_artifact_inspect.py:5](D:/projects/Speech-Emotion-Recognition/tests/test_artifact_inspect.py:5)；行 5

| class/function/method | 定义行 | 职责说明（源码 docstring） |
| --- | --- | --- |
| `LoadedArtifact` | [ser_lib/artifacts/loader.py:35](D:/projects/Speech-Emotion-Recognition/ser_lib/artifacts/loader.py:35) | 领域/公开定义 |
| `_sha256(path: Path) -> str` | [ser_lib/artifacts/loader.py:43](D:/projects/Speech-Emotion-Recognition/ser_lib/artifacts/loader.py:43) | 兼容旧内部测试/调用的无观察 SHA256 helper。 |
| `_sha256_with_progress(path: Path, *, cancellation: CancellationCheck \| None=None, on_chunk: Callable[[int], None] \| None=None) -> str` | [ser_lib/artifacts/loader.py:52](D:/projects/Speech-Emotion-Recognition/ser_lib/artifacts/loader.py:52) | 见实现；私有辅助 |
| `_major(version: str) -> int` | [ser_lib/artifacts/loader.py:74](D:/projects/Speech-Emotion-Recognition/ser_lib/artifacts/loader.py:74) | 见实现；私有辅助 |
| `_safe_component_path(source: Path, name: str) -> Path` | [ser_lib/artifacts/loader.py:81](D:/projects/Speech-Emotion-Recognition/ser_lib/artifacts/loader.py:81) | 见实现；私有辅助 |
| `_read_manifest(source: Path) -> ModelArtifactManifest` | [ser_lib/artifacts/loader.py:88](D:/projects/Speech-Emotion-Recognition/ser_lib/artifacts/loader.py:88) | 见实现；私有辅助 |
| `_validate_manifest_compatibility(manifest: ModelArtifactManifest) -> None` | [ser_lib/artifacts/loader.py:107](D:/projects/Speech-Emotion-Recognition/ser_lib/artifacts/loader.py:107) | 见实现；私有辅助 |
| `_validate_external_metadata(source: Path, manifest: ModelArtifactManifest) -> None` | [ser_lib/artifacts/loader.py:118](D:/projects/Speech-Emotion-Recognition/ser_lib/artifacts/loader.py:118) | 见实现；私有辅助 |
| `inspect_model_artifact(directory: Path \| str) -> ModelArtifactManifest` | [ser_lib/artifacts/loader.py:139](D:/projects/Speech-Emotion-Recognition/ser_lib/artifacts/loader.py:139) | 快速检查 artifact 结构和轻量 metadata，不计算任何文件 SHA256。 |
| `verify_model_artifact(directory: Path \| str, *, event_callback: EventCallback \| None=None, cancellation: CancellationCheck \| None=None, event_context: EventContext \| None=None) -> ModelArtifactManifest` | [ser_lib/artifacts/loader.py:163](D:/projects/Speech-Emotion-Recognition/ser_lib/artifacts/loader.py:163) | 完整校验全部 SHA256，并以读取字节数暴露进度。 |
| `load_model_artifact(directory: Path \| str, *, map_location: str \| torch.device='cpu', allow_legacy_pickle: bool=False) -> LoadedArtifact` | [ser_lib/artifacts/loader.py:279](D:/projects/Speech-Emotion-Recognition/ser_lib/artifacts/loader.py:279) | 完整验证并加载 artifact；旧 v1 pickle 必须显式授权。 |

### ser_lib/artifacts/manifest.py

处理：**保留**。目标：`原路径`。理由：ModelCard/Manifest 是 metadata，不迁 config；去 StrictConfig 继承误导。

直接 import 消费者（含测试；从公共包重导入的间接消费者还需沿 D/C 展开）：

- [ser_lib/artifacts/__init__.py:14](D:/projects/Speech-Emotion-Recognition/ser_lib/artifacts/__init__.py:14)；行 14
- [ser_lib/artifacts/catalog.py:10](D:/projects/Speech-Emotion-Recognition/ser_lib/artifacts/catalog.py:10)；行 10
- [ser_lib/artifacts/exporter.py:17](D:/projects/Speech-Emotion-Recognition/ser_lib/artifacts/exporter.py:17)；行 17
- [ser_lib/artifacts/loader.py:15](D:/projects/Speech-Emotion-Recognition/ser_lib/artifacts/loader.py:15)；行 15

| class/function/method | 定义行 | 职责说明（源码 docstring） |
| --- | --- | --- |
| `ModelCard` | [ser_lib/artifacts/manifest.py:13](D:/projects/Speech-Emotion-Recognition/ser_lib/artifacts/manifest.py:13) | 最小模型卡；未知信息允许留空，但字段不可隐式发明。 |
| `ModelArtifactManifest` | [ser_lib/artifacts/manifest.py:24](D:/projects/Speech-Emotion-Recognition/ser_lib/artifacts/manifest.py:24) | 领域/公开定义 |
| `ModelArtifactManifest._legacy_defaults(cls, value: Any) -> Any` | [ser_lib/artifacts/manifest.py:42](D:/projects/Speech-Emotion-Recognition/ser_lib/artifacts/manifest.py:42) |  |
| `ModelArtifactManifest._supported_schema(cls, value: int) -> int` | [ser_lib/artifacts/manifest.py:52](D:/projects/Speech-Emotion-Recognition/ser_lib/artifacts/manifest.py:52) |  |
| `ModelArtifactManifest._safe_weights_name(cls, value: str) -> str` | [ser_lib/artifacts/manifest.py:59](D:/projects/Speech-Emotion-Recognition/ser_lib/artifacts/manifest.py:59) |  |
| `ModelArtifactManifest._valid_sha256(cls, value: str) -> str` | [ser_lib/artifacts/manifest.py:67](D:/projects/Speech-Emotion-Recognition/ser_lib/artifacts/manifest.py:67) |  |
| `ModelArtifactManifest._contiguous_labels(cls, value: dict[int, str]) -> dict[int, str]` | [ser_lib/artifacts/manifest.py:74](D:/projects/Speech-Emotion-Recognition/ser_lib/artifacts/manifest.py:74) |  |
| `ModelArtifactManifest._format_matches_file(self) -> 'ModelArtifactManifest'` | [ser_lib/artifacts/manifest.py:82](D:/projects/Speech-Emotion-Recognition/ser_lib/artifacts/manifest.py:82) |  |

### ser_lib/benchmark.py

处理：**迁移**。目标：`ser_lib/engine/benchmark.py`。理由：SER 性能测量与比较可用于脚本；归执行辅助。

直接 import 消费者（含测试；从公共包重导入的间接消费者还需沿 D/C 展开）：

- [tests/test_ravdess_and_benchmark.py:10](D:/projects/Speech-Emotion-Recognition/tests/test_ravdess_and_benchmark.py:10)；行 10

| class/function/method | 定义行 | 职责说明（源码 docstring） |
| --- | --- | --- |
| `BenchmarkResult` | [ser_lib/benchmark.py:18](D:/projects/Speech-Emotion-Recognition/ser_lib/benchmark.py:18) | 领域/公开定义 |
| `BenchmarkResult.to_dict(self) -> dict[str, Any]` | [ser_lib/benchmark.py:29](D:/projects/Speech-Emotion-Recognition/ser_lib/benchmark.py:29) |  |
| `BenchmarkComparison` | [ser_lib/benchmark.py:34](D:/projects/Speech-Emotion-Recognition/ser_lib/benchmark.py:34) | 领域/公开定义 |
| `BenchmarkComparison.to_dict(self) -> dict[str, Any]` | [ser_lib/benchmark.py:39](D:/projects/Speech-Emotion-Recognition/ser_lib/benchmark.py:39) |  |
| `run_benchmark(name: str, operation: Callable[[], Any], *, iterations: int=20, warmup_iterations: int=3, metadata: dict[str, Any] \| None=None) -> BenchmarkResult` | [ser_lib/benchmark.py:43](D:/projects/Speech-Emotion-Recognition/ser_lib/benchmark.py:43) | 在同一进程执行同步操作，报告中位数、p95 和 Python 峰值内存。 |
| `compare_benchmarks(current: BenchmarkResult, baseline: BenchmarkResult, *, threshold_percent: float=10.0) -> BenchmarkComparison` | [ser_lib/benchmark.py:88](D:/projects/Speech-Emotion-Recognition/ser_lib/benchmark.py:88) | 比较越低越好的延迟/内存指标，环境不同则拒绝误判为可比结果。 |
| `write_benchmark_result(path: Path \| str, result: BenchmarkResult) -> Path` | [ser_lib/benchmark.py:115](D:/projects/Speech-Emotion-Recognition/ser_lib/benchmark.py:115) | 领域/公开定义 |
| `load_benchmark_result(path: Path \| str) -> BenchmarkResult` | [ser_lib/benchmark.py:130](D:/projects/Speech-Emotion-Recognition/ser_lib/benchmark.py:130) | 领域/公开定义 |

### ser_lib/catalog.py

处理：**删除**。目标：`各领域 registry + config schema`。理由：跨领域描述重复包装；CLI 改原生 introspection。

直接 import 消费者（含测试；从公共包重导入的间接消费者还需沿 D/C 展开）：

- [ser_lib/__init__.py:104](D:/projects/Speech-Emotion-Recognition/ser_lib/__init__.py:104)；行 104
- [ser_lib/services/catalog.py:7](D:/projects/Speech-Emotion-Recognition/ser_lib/services/catalog.py:7)；行 7
- [tests/test_component_catalog.py:14](D:/projects/Speech-Emotion-Recognition/tests/test_component_catalog.py:14)；行 14

| class/function/method | 定义行 | 职责说明（源码 docstring） |
| --- | --- | --- |
| `_parameter_schema(model: type[BaseModel], *, fields: Iterable[str] \| None=None) -> dict[str, Any]` | [ser_lib/catalog.py:51](D:/projects/Speech-Emotion-Recognition/ser_lib/catalog.py:51) | 把完整 Pydantic 配置 Schema 裁剪为组件 ``params`` Schema。 |
| `_descriptor(component_id: str, display_name: str, category: str, description: str, config_model: type[BaseModel], *, fields: Iterable[str] \| None=None, capabilities: dict[str, Any] \| None=None) -> ComponentDescriptor` | [ser_lib/catalog.py:76](D:/projects/Speech-Emotion-Recognition/ser_lib/catalog.py:76) | 见实现；私有辅助 |
| `_data_descriptors() -> list[ComponentDescriptor]` | [ser_lib/catalog.py:96](D:/projects/Speech-Emotion-Recognition/ser_lib/catalog.py:96) | 见实现；私有辅助 |
| `_model_descriptors() -> list[ComponentDescriptor]` | [ser_lib/catalog.py:122](D:/projects/Speech-Emotion-Recognition/ser_lib/catalog.py:122) | 见实现；私有辅助 |
| `_training_descriptors() -> list[ComponentDescriptor]` | [ser_lib/catalog.py:144](D:/projects/Speech-Emotion-Recognition/ser_lib/catalog.py:144) | 见实现；私有辅助 |
| `ComponentCatalog` | [ser_lib/catalog.py:205](D:/projects/Speech-Emotion-Recognition/ser_lib/catalog.py:205) | 稳定、JSON-safe 的组件目录快照。 |
| `ComponentCatalog.__post_init__(self) -> None` | [ser_lib/catalog.py:210](D:/projects/Speech-Emotion-Recognition/ser_lib/catalog.py:210) |  |
| `ComponentCatalog.categories(self) -> tuple[str, ...]` | [ser_lib/catalog.py:223](D:/projects/Speech-Emotion-Recognition/ser_lib/catalog.py:223) |  |
| `ComponentCatalog.list(self, category: str \| None=None, *, statuses: tuple[str, ...] \| None=None) -> tuple[ComponentDescriptor, ...]` | [ser_lib/catalog.py:226](D:/projects/Speech-Emotion-Recognition/ser_lib/catalog.py:226) |  |
| `ComponentCatalog.get(self, category: str, component_id: str) -> ComponentDescriptor` | [ser_lib/catalog.py:242](D:/projects/Speech-Emotion-Recognition/ser_lib/catalog.py:242) |  |
| `ComponentCatalog.to_dict(self) -> dict[str, Any]` | [ser_lib/catalog.py:251](D:/projects/Speech-Emotion-Recognition/ser_lib/catalog.py:251) |  |
| `get_component_catalog() -> ComponentCatalog` | [ser_lib/catalog.py:259](D:/projects/Speech-Emotion-Recognition/ser_lib/catalog.py:259) | 创建当前进程已注册组件的只读 Catalog 快照。 |
| `list_component_descriptors(category: str \| None=None, *, statuses: tuple[str, ...] \| None=None) -> tuple[ComponentDescriptor, ...]` | [ser_lib/catalog.py:271](D:/projects/Speech-Emotion-Recognition/ser_lib/catalog.py:271) | 便捷查询函数；等价于 ``get_component_catalog().list(...)``。 |

### ser_lib/cli/__init__.py

处理：**瘦身**。目标：`原路径`。理由：更新 config/退役包装导出及内置注册顺序，不改变算法。

无直接模块 import 消费者，不能据此判为无用；检查包 re-export、factory 注册、CLI 入口和动态调用。

| class/function/method | 定义行 | 职责说明（源码 docstring） |
| --- | --- | --- |

### ser_lib/cli/__main__.py

处理：**保留**。目标：`原路径`。理由：实际为 SER 数据/执行基础，无确认的页面专属职责；更新被迁移 import。

无直接模块 import 消费者，不能据此判为无用；检查包 re-export、factory 注册、CLI 入口和动态调用。

| class/function/method | 定义行 | 职责说明（源码 docstring） |
| --- | --- | --- |

### ser_lib/cli/main.py

处理：**瘦身**。目标：`原路径`。理由：参数/配置/输出适配；组件列表直接 registry。

直接 import 消费者（含测试；从公共包重导入的间接消费者还需沿 D/C 展开）：

- [ser_lib/cli/__init__.py:3](D:/projects/Speech-Emotion-Recognition/ser_lib/cli/__init__.py:3)；行 3
- [ser_lib/cli/__main__.py:1](D:/projects/Speech-Emotion-Recognition/ser_lib/cli/__main__.py:1)；行 1
- [tests/test_cli.py:12](D:/projects/Speech-Emotion-Recognition/tests/test_cli.py:12)；行 12

| class/function/method | 定义行 | 职责说明（源码 docstring） |
| --- | --- | --- |
| `_parser() -> argparse.ArgumentParser` | [ser_lib/cli/main.py:42](D:/projects/Speech-Emotion-Recognition/ser_lib/cli/main.py:42) | 见实现；私有辅助 |
| `_add_importer_arguments(parser: argparse.ArgumentParser, *, destination: bool) -> None` | [ser_lib/cli/main.py:125](D:/projects/Speech-Emotion-Recognition/ser_lib/cli/main.py:125) | 见实现；私有辅助 |
| `_load_params(inline: str \| None, file: Path \| None) -> dict[str, Any]` | [ser_lib/cli/main.py:136](D:/projects/Speech-Emotion-Recognition/ser_lib/cli/main.py:136) | 见实现；私有辅助 |
| `_emit(value: Any, *, as_json: bool, stream: TextIO) -> None` | [ser_lib/cli/main.py:154](D:/projects/Speech-Emotion-Recognition/ser_lib/cli/main.py:154) | 见实现；私有辅助 |
| `_component_list(args, stream: TextIO) -> int` | [ser_lib/cli/main.py:169](D:/projects/Speech-Emotion-Recognition/ser_lib/cli/main.py:169) | 见实现；私有辅助 |
| `_importer(args)` | [ser_lib/cli/main.py:183](D:/projects/Speech-Emotion-Recognition/ser_lib/cli/main.py:183) | 见实现；私有辅助 |
| `_dataset_scan(args, stream: TextIO) -> int` | [ser_lib/cli/main.py:189](D:/projects/Speech-Emotion-Recognition/ser_lib/cli/main.py:189) | 见实现；私有辅助 |
| `_dataset_import(args, stream: TextIO) -> int` | [ser_lib/cli/main.py:197](D:/projects/Speech-Emotion-Recognition/ser_lib/cli/main.py:197) | 见实现；私有辅助 |
| `_split_stats(manifest: DatasetManifest, split: str \| None) -> dict[str, Any]` | [ser_lib/cli/main.py:209](D:/projects/Speech-Emotion-Recognition/ser_lib/cli/main.py:209) | 见实现；私有辅助 |
| `_dataset_validate(args, stream: TextIO) -> int` | [ser_lib/cli/main.py:231](D:/projects/Speech-Emotion-Recognition/ser_lib/cli/main.py:231) | 见实现；私有辅助 |
| `_dataset_stats(args, stream: TextIO) -> int` | [ser_lib/cli/main.py:251](D:/projects/Speech-Emotion-Recognition/ser_lib/cli/main.py:251) | 见实现；私有辅助 |
| `_validate_runtime_args(args) -> None` | [ser_lib/cli/main.py:266](D:/projects/Speech-Emotion-Recognition/ser_lib/cli/main.py:266) | 见实现；私有辅助 |
| `_load_mapping_file(path: Path \| None) -> dict[str, Any] \| None` | [ser_lib/cli/main.py:273](D:/projects/Speech-Emotion-Recognition/ser_lib/cli/main.py:273) | 见实现；私有辅助 |
| `_run_workflow(args, stream: TextIO) -> int` | [ser_lib/cli/main.py:279](D:/projects/Speech-Emotion-Recognition/ser_lib/cli/main.py:279) | 见实现；私有辅助 |
| `main(argv: Sequence[str] \| None=None) -> int` | [ser_lib/cli/main.py:312](D:/projects/Speech-Emotion-Recognition/ser_lib/cli/main.py:312) | 领域/公开定义 |

### ser_lib/cli/workflows.py

处理：**拆分**。目标：`原路径 + ser_lib/engine/experiment.py`。理由：移出可复用训练编排；直接 public API；验证集不再重复构造模型。

直接 import 消费者（含测试；从公共包重导入的间接消费者还需沿 D/C 展开）：

- [ser_lib/cli/main.py:24](D:/projects/Speech-Emotion-Recognition/ser_lib/cli/main.py:24)；行 24
- [tests/test_cli_lineage.py:12](D:/projects/Speech-Emotion-Recognition/tests/test_cli_lineage.py:12)；行 12

| class/function/method | 定义行 | 职责说明（源码 docstring） |
| --- | --- | --- |
| `_labels(meta_labels: dict[int, dict[str, Any]]) -> dict[int, str]` | [ser_lib/cli/workflows.py:32](D:/projects/Speech-Emotion-Recognition/ser_lib/cli/workflows.py:32) | 见实现；私有辅助 |
| `_loader(manifest, split, components, *, batch_size, workers, shuffle=False, sampling=None, seed=42, num_classes=None)` | [ser_lib/cli/workflows.py:39](D:/projects/Speech-Emotion-Recognition/ser_lib/cli/workflows.py:39) | 见实现；私有辅助 |
| `train_experiment(config_path: Path, *, split: str, batch_size: int, workers: int, resume: Path \| None) -> dict[str, Any]` | [ser_lib/cli/workflows.py:73](D:/projects/Speech-Emotion-Recognition/ser_lib/cli/workflows.py:73) | 领域/公开定义 |
| `evaluate_artifact(artifact: Path, *, manifest_path: Path \| None, split: str, batch_size: int, workers: int, device: str, output: Path) -> dict[str, Any]` | [ser_lib/cli/workflows.py:171](D:/projects/Speech-Emotion-Recognition/ser_lib/cli/workflows.py:171) | 领域/公开定义 |
| `predict_artifact(artifact: Path, *, source: Path, split: str \| None, batch_size: int, device: str, output: Path, keep_going: bool, recursive: bool, window_aggregation: Literal['mean_logits', 'mean_probabilities', 'max_confidence'] \| None) -> dict[str, Any]` | [ser_lib/cli/workflows.py:237](D:/projects/Speech-Emotion-Recognition/ser_lib/cli/workflows.py:237) | 领域/公开定义 |
| `export_checkpoint_artifact(config_path: Path, checkpoint: Path, destination: Path, *, model_card: dict[str, Any] \| None=None) -> dict[str, Any]` | [ser_lib/cli/workflows.py:289](D:/projects/Speech-Emotion-Recognition/ser_lib/cli/workflows.py:289) | 领域/公开定义 |
| `inspect_artifact(path: Path, *, verify: bool) -> dict[str, Any]` | [ser_lib/cli/workflows.py:337](D:/projects/Speech-Emotion-Recognition/ser_lib/cli/workflows.py:337) | 领域/公开定义 |

### ser_lib/core/__init__.py

处理：**删除**。目标：`foundation/config/各领域公共入口`。理由：旧包导出全部迁移后删除。

直接 import 消费者（含测试；从公共包重导入的间接消费者还需沿 D/C 展开）：

- [ser_lib/__init__.py:5](D:/projects/Speech-Emotion-Recognition/ser_lib/__init__.py:5)；行 5
- [ser_lib/cli/main.py:16](D:/projects/Speech-Emotion-Recognition/ser_lib/cli/main.py:16)；行 16
- [ser_lib/cli/workflows.py:15](D:/projects/Speech-Emotion-Recognition/ser_lib/cli/workflows.py:15)；行 15
- [tests/test_artifact_catalog.py:5](D:/projects/Speech-Emotion-Recognition/tests/test_artifact_catalog.py:5)；行 5
- [tests/test_artifact_progress.py:6](D:/projects/Speech-Emotion-Recognition/tests/test_artifact_progress.py:6)；行 6
- [tests/test_batch_inference.py:10](D:/projects/Speech-Emotion-Recognition/tests/test_batch_inference.py:10)；行 10
- [tests/test_batch_prediction_events.py:4](D:/projects/Speech-Emotion-Recognition/tests/test_batch_prediction_events.py:4)；行 4
- [tests/test_checkpoint_catalog.py:8](D:/projects/Speech-Emotion-Recognition/tests/test_checkpoint_catalog.py:8)；行 8
- [tests/test_checkpoint_resume.py:9](D:/projects/Speech-Emotion-Recognition/tests/test_checkpoint_resume.py:9)；行 9
- [tests/test_core.py:10](D:/projects/Speech-Emotion-Recognition/tests/test_core.py:10)；行 10
- [tests/test_dataset_history.py:9](D:/projects/Speech-Emotion-Recognition/tests/test_dataset_history.py:9)；行 9
- [tests/test_diagnostics.py:9](D:/projects/Speech-Emotion-Recognition/tests/test_diagnostics.py:9)；行 9
- [tests/test_engine_config.py:9](D:/projects/Speech-Emotion-Recognition/tests/test_engine_config.py:9)；行 9
- [tests/test_evaluation_prediction_query.py:8](D:/projects/Speech-Emotion-Recognition/tests/test_evaluation_prediction_query.py:8)；行 8
- [tests/test_evaluation_run_catalog.py:10](D:/projects/Speech-Emotion-Recognition/tests/test_evaluation_run_catalog.py:10)；行 10
- [tests/test_evaluator_observability.py:10](D:/projects/Speech-Emotion-Recognition/tests/test_evaluator_observability.py:10)；行 10
- [tests/test_evaluator_reports.py:9](D:/projects/Speech-Emotion-Recognition/tests/test_evaluator_reports.py:9)；行 9
- [tests/test_events.py:9](D:/projects/Speech-Emotion-Recognition/tests/test_events.py:9)；行 9
- [tests/test_importer_observability.py:8](D:/projects/Speech-Emotion-Recognition/tests/test_importer_observability.py:8)；行 8
- [tests/test_public_api.py:7](D:/projects/Speech-Emotion-Recognition/tests/test_public_api.py:7)；行 7
- [tests/test_schema_migrations.py:5](D:/projects/Speech-Emotion-Recognition/tests/test_schema_migrations.py:5)；行 5
- [tests/test_trainer_observability.py:9](D:/projects/Speech-Emotion-Recognition/tests/test_trainer_observability.py:9)；行 9
- [tests/test_training_result.py:10](D:/projects/Speech-Emotion-Recognition/tests/test_training_result.py:10)；行 10
- [tests/test_training_run_catalog.py:11](D:/projects/Speech-Emotion-Recognition/tests/test_training_run_catalog.py:11)；行 11

| class/function/method | 定义行 | 职责说明（源码 docstring） |
| --- | --- | --- |

### ser_lib/core/_catalog_scan.py

处理：**拆分**。目标：`data/history.py; engine/*catalog.py/runs.py; artifacts/catalog.py 内私有循环`。理由：去跨领域 Catalog 协议，保留取消/失败隔离。

直接 import 消费者（含测试；从公共包重导入的间接消费者还需沿 D/C 展开）：

- [ser_lib/artifacts/catalog.py:11](D:/projects/Speech-Emotion-Recognition/ser_lib/artifacts/catalog.py:11)；行 11
- [ser_lib/data/history.py:20](D:/projects/Speech-Emotion-Recognition/ser_lib/data/history.py:20)；行 20
- [ser_lib/engine/checkpoint_catalog.py:11](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/checkpoint_catalog.py:11)；行 11
- [ser_lib/engine/evaluation_catalog.py:9](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/evaluation_catalog.py:9)；行 9
- [ser_lib/engine/runs.py:13](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/runs.py:13)；行 13

| class/function/method | 定义行 | 职责说明（源码 docstring） |
| --- | --- | --- |
| `scan_catalog_candidates(candidates: Sequence[Path], *, inspect_candidate: Callable[[Path], ItemT \| None], failure_factory: Callable[[Path, Exception], FailureT], stage: str, candidate_detail_key: str \| None, fail_fast: bool=False, event_callback: EventCallback \| None=None, cancellation: CancellationCheck \| None=None) -> tuple[list[ItemT], list[FailureT]]` | [ser_lib/core/_catalog_scan.py:15](D:/projects/Speech-Emotion-Recognition/ser_lib/core/_catalog_scan.py:15) | 统一 Catalog 的取消、失败策略和 progress 事件。 |

### ser_lib/core/config.py

处理：**拆分**。目标：`ser_lib/config/base.py; ser_lib/config/loader.py`。理由：用户配置和读取器不属于 foundation。

直接 import 消费者（含测试；从公共包重导入的间接消费者还需沿 D/C 展开）：

- [ser_lib/artifacts/manifest.py:10](D:/projects/Speech-Emotion-Recognition/ser_lib/artifacts/manifest.py:10)；行 10
- [ser_lib/core/__init__.py:3](D:/projects/Speech-Emotion-Recognition/ser_lib/core/__init__.py:3)；行 3
- [ser_lib/data/config.py:15](D:/projects/Speech-Emotion-Recognition/ser_lib/data/config.py:15)；行 15
- [ser_lib/engine/config.py:11](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/config.py:11)；行 11
- [ser_lib/engine/objectives.py:13](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/objectives.py:13)；行 13
- [ser_lib/engine/optim.py:10](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/optim.py:10)；行 10
- [ser_lib/models/cnn_models.py:11](D:/projects/Speech-Emotion-Recognition/ser_lib/models/cnn_models.py:11)；行 11
- [ser_lib/models/pretrained.py:13](D:/projects/Speech-Emotion-Recognition/ser_lib/models/pretrained.py:13)；行 13
- [ser_lib/models/rnn_models.py:12](D:/projects/Speech-Emotion-Recognition/ser_lib/models/rnn_models.py:12)；行 12
- [ser_lib/models/transformer_models.py:12](D:/projects/Speech-Emotion-Recognition/ser_lib/models/transformer_models.py:12)；行 12

| class/function/method | 定义行 | 职责说明（源码 docstring） |
| --- | --- | --- |
| `StrictConfig` | [ser_lib/core/config.py:14](D:/projects/Speech-Emotion-Recognition/ser_lib/core/config.py:14) | 公共配置基类：拒绝未知字段，校验赋值并禁止意外修改。 |
| `resolve_config_path(value: Path \| str, *, base_dir: Path \| str) -> Path` | [ser_lib/core/config.py:23](D:/projects/Speech-Emotion-Recognition/ser_lib/core/config.py:23) | 相对 ``base_dir`` 解析路径，不依赖当前工作目录。 |
| `require_schema_version(raw: dict[str, Any], *, supported: set[int] \| frozenset[int] \| tuple[int, ...], source: Path \| str \| None=None) -> int` | [ser_lib/core/config.py:30](D:/projects/Speech-Emotion-Recognition/ser_lib/core/config.py:30) | 读取并验证配置 schema 版本，拒绝缺失、布尔值和未知版本。 |
| `load_yaml_mapping(path: Path \| str) -> tuple[dict[str, Any], Path]` | [ser_lib/core/config.py:51](D:/projects/Speech-Emotion-Recognition/ser_lib/core/config.py:51) | 安全读取 YAML 映射，并返回内容与规范化文件路径。 |
| `load_versioned_config(path: Path \| str, model: type[ConfigT], *, supported_versions: set[int] \| frozenset[int] \| tuple[int, ...]=(1,), schema_domain: str \| None=None, target_version: int \| None=None) -> ConfigT` | [ser_lib/core/config.py:64](D:/projects/Speech-Emotion-Recognition/ser_lib/core/config.py:64) | 读取版本化 YAML，按需迁移后用当前 Pydantic 模型严格校验。 |

### ser_lib/core/diagnostics.py

处理：**迁移**。目标：`ser_lib/foundation/diagnostics.py`。理由：结构化诊断保留，去 UI 专属措辞。

直接 import 消费者（含测试；从公共包重导入的间接消费者还需沿 D/C 展开）：

- [ser_lib/core/__init__.py:10](D:/projects/Speech-Emotion-Recognition/ser_lib/core/__init__.py:10)；行 10
- [ser_lib/data/importers/base.py:15](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/base.py:15)；行 15
- [ser_lib/data/importers/casia.py:10](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/casia.py:10)；行 10
- [ser_lib/data/importers/crema_d.py:11](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/crema_d.py:11)；行 11
- [ser_lib/data/importers/csemotions.py:11](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/csemotions.py:11)；行 11
- [ser_lib/data/importers/csv_importer.py:11](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/csv_importer.py:11)；行 11
- [ser_lib/data/importers/emotiontalk.py:11](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/emotiontalk.py:11)；行 11
- [ser_lib/data/importers/esd.py:10](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/esd.py:10)；行 10
- [ser_lib/data/importers/folder.py:10](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/folder.py:10)；行 10
- [ser_lib/data/importers/jsonl_importer.py:11](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/jsonl_importer.py:11)；行 11
- [ser_lib/data/importers/ravdess.py:10](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/ravdess.py:10)；行 10
- [ser_lib/data/validation.py:13](D:/projects/Speech-Emotion-Recognition/ser_lib/data/validation.py:13)；行 13
- [ser_lib/engine/evaluation_detail.py:9](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/evaluation_detail.py:9)；行 9
- [ser_lib/engine/runs.py:14](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/runs.py:14)；行 14
- [ser_lib/engine/validation.py:11](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/validation.py:11)；行 11
- [ser_lib/services/evaluation.py:11](D:/projects/Speech-Emotion-Recognition/ser_lib/services/evaluation.py:11)；行 11
- [ser_lib/services/training.py:8](D:/projects/Speech-Emotion-Recognition/ser_lib/services/training.py:8)；行 8

| class/function/method | 定义行 | 职责说明（源码 docstring） |
| --- | --- | --- |
| `_json_safe(value: Any) -> Any` | [ser_lib/core/diagnostics.py:20](D:/projects/Speech-Emotion-Recognition/ser_lib/core/diagnostics.py:20) | 见实现；私有辅助 |
| `_validate_code(code: str) -> None` | [ser_lib/core/diagnostics.py:38](D:/projects/Speech-Emotion-Recognition/ser_lib/core/diagnostics.py:38) | 见实现；私有辅助 |
| `Diagnostic` | [ser_lib/core/diagnostics.py:44](D:/projects/Speech-Emotion-Recognition/ser_lib/core/diagnostics.py:44) | 一个稳定、可 JSON 序列化、可由 UI 直接展示的诊断项。 |
| `Diagnostic.__post_init__(self) -> None` | [ser_lib/core/diagnostics.py:57](D:/projects/Speech-Emotion-Recognition/ser_lib/core/diagnostics.py:57) |  |
| `Diagnostic.to_dict(self) -> dict[str, Any]` | [ser_lib/core/diagnostics.py:69](D:/projects/Speech-Emotion-Recognition/ser_lib/core/diagnostics.py:69) |  |
| `Diagnostic.from_error(cls, error: Exception, *, severity: DiagnosticSeverity='error', suggestion: str \| None=None) -> 'Diagnostic'` | [ser_lib/core/diagnostics.py:83](D:/projects/Speech-Emotion-Recognition/ser_lib/core/diagnostics.py:83) | 把异常转换为展示用 Diagnostic，不改变原异常的控制流语义。 |
| `_optional_string(value: Any) -> str \| None` | [ser_lib/core/diagnostics.py:115](D:/projects/Speech-Emotion-Recognition/ser_lib/core/diagnostics.py:115) | 见实现；私有辅助 |

### ser_lib/core/events.py

处理：**拆分**。目标：`ser_lib/foundation/events.py; ser_lib/engine/events.py; ser_lib/inference/events.py`。理由：通用事件/取消与 checkpoint/prediction 事件分属不同层。

直接 import 消费者（含测试；从公共包重导入的间接消费者还需沿 D/C 展开）：

- [ser_lib/artifacts/catalog.py:12](D:/projects/Speech-Emotion-Recognition/ser_lib/artifacts/catalog.py:12)；行 12
- [ser_lib/artifacts/exporter.py:18](D:/projects/Speech-Emotion-Recognition/ser_lib/artifacts/exporter.py:18)；行 18
- [ser_lib/artifacts/loader.py:16](D:/projects/Speech-Emotion-Recognition/ser_lib/artifacts/loader.py:16)；行 16
- [ser_lib/core/__init__.py:11](D:/projects/Speech-Emotion-Recognition/ser_lib/core/__init__.py:11)；行 11
- [ser_lib/core/_catalog_scan.py:9](D:/projects/Speech-Emotion-Recognition/ser_lib/core/_catalog_scan.py:9)；行 9
- [ser_lib/data/fingerprint.py:10](D:/projects/Speech-Emotion-Recognition/ser_lib/data/fingerprint.py:10)；行 10
- [ser_lib/data/history.py:21](D:/projects/Speech-Emotion-Recognition/ser_lib/data/history.py:21)；行 21
- [ser_lib/data/importers/_conversion.py:11](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/_conversion.py:11)；行 11
- [ser_lib/data/importers/base.py:16](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/base.py:16)；行 16
- [ser_lib/data/importers/casia.py:11](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/casia.py:11)；行 11
- [ser_lib/data/importers/crema_d.py:12](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/crema_d.py:12)；行 12
- [ser_lib/data/importers/csemotions.py:12](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/csemotions.py:12)；行 12
- [ser_lib/data/importers/csv_importer.py:12](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/csv_importer.py:12)；行 12
- [ser_lib/data/importers/emotiontalk.py:12](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/emotiontalk.py:12)；行 12
- [ser_lib/data/importers/esd.py:11](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/esd.py:11)；行 11
- [ser_lib/data/importers/folder.py:11](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/folder.py:11)；行 11
- [ser_lib/data/importers/jsonl_importer.py:12](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/jsonl_importer.py:12)；行 12
- [ser_lib/data/importers/ravdess.py:11](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/ravdess.py:11)；行 11
- [ser_lib/data/profiling.py:9](D:/projects/Speech-Emotion-Recognition/ser_lib/data/profiling.py:9)；行 9
- [ser_lib/engine/_trainer_core.py:18](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/_trainer_core.py:18)；行 18
- [ser_lib/engine/checkpoint_catalog.py:12](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/checkpoint_catalog.py:12)；行 12
- [ser_lib/engine/evaluation_catalog.py:10](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/evaluation_catalog.py:10)；行 10
- [ser_lib/engine/evaluation_reports.py:12](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/evaluation_reports.py:12)；行 12
- [ser_lib/engine/evaluator.py:15](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/evaluator.py:15)；行 15
- [ser_lib/engine/runs.py:15](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/runs.py:15)；行 15
- [ser_lib/engine/trainer.py:11](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/trainer.py:11)；行 11
- [ser_lib/inference/batch.py:13](D:/projects/Speech-Emotion-Recognition/ser_lib/inference/batch.py:13)；行 13
- [ser_lib/services/artifacts.py:22](D:/projects/Speech-Emotion-Recognition/ser_lib/services/artifacts.py:22)；行 22
- [ser_lib/services/datasets.py:8](D:/projects/Speech-Emotion-Recognition/ser_lib/services/datasets.py:8)；行 8
- [ser_lib/services/evaluation.py:12](D:/projects/Speech-Emotion-Recognition/ser_lib/services/evaluation.py:12)；行 12
- [ser_lib/services/inference.py:9](D:/projects/Speech-Emotion-Recognition/ser_lib/services/inference.py:9)；行 9
- [ser_lib/services/training.py:9](D:/projects/Speech-Emotion-Recognition/ser_lib/services/training.py:9)；行 9
- [tests/test_dataset_profile.py:7](D:/projects/Speech-Emotion-Recognition/tests/test_dataset_profile.py:7)；行 7

| class/function/method | 定义行 | 职责说明（源码 docstring） |
| --- | --- | --- |
| `_utc_now() -> datetime` | [ser_lib/core/events.py:36](D:/projects/Speech-Emotion-Recognition/ser_lib/core/events.py:36) | 见实现；私有辅助 |
| `_next_event_sequence() -> int` | [ser_lib/core/events.py:40](D:/projects/Speech-Emotion-Recognition/ser_lib/core/events.py:40) | 见实现；私有辅助 |
| `_timestamp_to_iso(value: datetime) -> str` | [ser_lib/core/events.py:45](D:/projects/Speech-Emotion-Recognition/ser_lib/core/events.py:45) | 见实现；私有辅助 |
| `_json_safe(value: Any) -> Any` | [ser_lib/core/events.py:51](D:/projects/Speech-Emotion-Recognition/ser_lib/core/events.py:51) | 将常见轻量值转换为事件协议可安全 JSON 序列化的值。 |
| `EventContext` | [ser_lib/core/events.py:74](D:/projects/Speech-Emotion-Recognition/ser_lib/core/events.py:74) | 跨事件共享的运行上下文。 |
| `EventContext.to_dict(self) -> dict[str, Any]` | [ser_lib/core/events.py:85](D:/projects/Speech-Emotion-Recognition/ser_lib/core/events.py:85) |  |
| `ProgressEvent` | [ser_lib/core/events.py:98](D:/projects/Speech-Emotion-Recognition/ser_lib/core/events.py:98) | 领域/公开定义 |
| `ProgressEvent.__post_init__(self) -> None` | [ser_lib/core/events.py:111](D:/projects/Speech-Emotion-Recognition/ser_lib/core/events.py:111) |  |
| `ProgressEvent.fraction(self) -> float \| None` | [ser_lib/core/events.py:122](D:/projects/Speech-Emotion-Recognition/ser_lib/core/events.py:122) |  |
| `ProgressEvent.to_dict(self) -> dict[str, Any]` | [ser_lib/core/events.py:127](D:/projects/Speech-Emotion-Recognition/ser_lib/core/events.py:127) |  |
| `MetricEvent` | [ser_lib/core/events.py:143](D:/projects/Speech-Emotion-Recognition/ser_lib/core/events.py:143) | 领域/公开定义 |
| `MetricEvent.__post_init__(self) -> None` | [ser_lib/core/events.py:155](D:/projects/Speech-Emotion-Recognition/ser_lib/core/events.py:155) |  |
| `MetricEvent.to_dict(self) -> dict[str, Any]` | [ser_lib/core/events.py:166](D:/projects/Speech-Emotion-Recognition/ser_lib/core/events.py:166) |  |
| `LogEvent` | [ser_lib/core/events.py:181](D:/projects/Speech-Emotion-Recognition/ser_lib/core/events.py:181) | 领域/公开定义 |
| `LogEvent.__post_init__(self) -> None` | [ser_lib/core/events.py:193](D:/projects/Speech-Emotion-Recognition/ser_lib/core/events.py:193) |  |
| `LogEvent.to_dict(self) -> dict[str, Any]` | [ser_lib/core/events.py:201](D:/projects/Speech-Emotion-Recognition/ser_lib/core/events.py:201) |  |
| `LifecycleEvent` | [ser_lib/core/events.py:216](D:/projects/Speech-Emotion-Recognition/ser_lib/core/events.py:216) | 描述长任务或其阶段的生命周期变化。 |
| `LifecycleEvent.__post_init__(self) -> None` | [ser_lib/core/events.py:230](D:/projects/Speech-Emotion-Recognition/ser_lib/core/events.py:230) |  |
| `LifecycleEvent.to_dict(self) -> dict[str, Any]` | [ser_lib/core/events.py:239](D:/projects/Speech-Emotion-Recognition/ser_lib/core/events.py:239) |  |
| `CheckpointEvent` | [ser_lib/core/events.py:254](D:/projects/Speech-Emotion-Recognition/ser_lib/core/events.py:254) | 描述 checkpoint 保存生命周期，供 UI 展示而无需扫描文件系统。 |
| `CheckpointEvent.__post_init__(self) -> None` | [ser_lib/core/events.py:272](D:/projects/Speech-Emotion-Recognition/ser_lib/core/events.py:272) |  |
| `CheckpointEvent.to_dict(self) -> dict[str, Any]` | [ser_lib/core/events.py:285](D:/projects/Speech-Emotion-Recognition/ser_lib/core/events.py:285) |  |
| `PredictionEvent` | [ser_lib/core/events.py:304](D:/projects/Speech-Emotion-Recognition/ser_lib/core/events.py:304) | 单条推理结果事件，供批量任务边执行边展示结果。 |
| `PredictionEvent.__post_init__(self) -> None` | [ser_lib/core/events.py:320](D:/projects/Speech-Emotion-Recognition/ser_lib/core/events.py:320) |  |
| `PredictionEvent.to_dict(self) -> dict[str, Any]` | [ser_lib/core/events.py:334](D:/projects/Speech-Emotion-Recognition/ser_lib/core/events.py:334) |  |
| `CancellationCheck` | [ser_lib/core/events.py:361](D:/projects/Speech-Emotion-Recognition/ser_lib/core/events.py:361) | 长操作只依赖此协议，不依赖具体调度器。 |
| `CancellationCheck.is_cancelled(self) -> bool` | [ser_lib/core/events.py:365](D:/projects/Speech-Emotion-Recognition/ser_lib/core/events.py:365) |  |
| `CancellationCheck.raise_if_cancelled(self) -> None` | [ser_lib/core/events.py:367](D:/projects/Speech-Emotion-Recognition/ser_lib/core/events.py:367) |  |
| `CancellationToken` | [ser_lib/core/events.py:370](D:/projects/Speech-Emotion-Recognition/ser_lib/core/events.py:370) | 可在线程间安全共享的协作式取消令牌。 |
| `CancellationToken.__init__(self) -> None` | [ser_lib/core/events.py:373](D:/projects/Speech-Emotion-Recognition/ser_lib/core/events.py:373) |  |
| `CancellationToken.is_cancelled(self) -> bool` | [ser_lib/core/events.py:377](D:/projects/Speech-Emotion-Recognition/ser_lib/core/events.py:377) |  |
| `CancellationToken.cancel(self) -> None` | [ser_lib/core/events.py:380](D:/projects/Speech-Emotion-Recognition/ser_lib/core/events.py:380) |  |
| `CancellationToken.raise_if_cancelled(self) -> None` | [ser_lib/core/events.py:383](D:/projects/Speech-Emotion-Recognition/ser_lib/core/events.py:383) |  |

### ser_lib/core/exceptions.py

处理：**迁移**。目标：`ser_lib/foundation/errors.py`。理由：公共异常基础，不携带领域执行逻辑。

直接 import 消费者（含测试；从公共包重导入的间接消费者还需沿 D/C 展开）：

- [ser_lib/artifacts/exporter.py:25](D:/projects/Speech-Emotion-Recognition/ser_lib/artifacts/exporter.py:25)；行 25
- [ser_lib/artifacts/loader.py:23](D:/projects/Speech-Emotion-Recognition/ser_lib/artifacts/loader.py:23)；行 23
- [ser_lib/core/__init__.py:25](D:/projects/Speech-Emotion-Recognition/ser_lib/core/__init__.py:25)；行 25
- [ser_lib/core/config.py:11](D:/projects/Speech-Emotion-Recognition/ser_lib/core/config.py:11)；行 11
- [ser_lib/core/diagnostics.py:91](D:/projects/Speech-Emotion-Recognition/ser_lib/core/diagnostics.py:91)；行 91
- [ser_lib/core/events.py:14](D:/projects/Speech-Emotion-Recognition/ser_lib/core/events.py:14)；行 14
- [ser_lib/core/migrations.py:10](D:/projects/Speech-Emotion-Recognition/ser_lib/core/migrations.py:10)；行 10
- [ser_lib/data/errors.py:27](D:/projects/Speech-Emotion-Recognition/ser_lib/data/errors.py:27)；行 27
- [ser_lib/data/importers/base.py:23](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/base.py:23)；行 23
- [ser_lib/data/manifest.py:20](D:/projects/Speech-Emotion-Recognition/ser_lib/data/manifest.py:20)；行 20
- [ser_lib/engine/_trainer_core.py:28](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/_trainer_core.py:28)；行 28
- [ser_lib/engine/evaluator.py:22](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/evaluator.py:22)；行 22
- [tests/test_dataset_profile.py:8](D:/projects/Speech-Emotion-Recognition/tests/test_dataset_profile.py:8)；行 8

| class/function/method | 定义行 | 职责说明（源码 docstring） |
| --- | --- | --- |
| `SERError` | [ser_lib/core/exceptions.py:9](D:/projects/Speech-Emotion-Recognition/ser_lib/core/exceptions.py:9) | 所有可预期 SER 领域错误的根类型。 |
| `SERError.__init__(self, message: str, *, code: str \| None=None, details: Mapping[str, Any] \| None=None) -> None` | [ser_lib/core/exceptions.py:18](D:/projects/Speech-Emotion-Recognition/ser_lib/core/exceptions.py:18) |  |
| `SERError.to_dict(self) -> dict[str, Any]` | [ser_lib/core/exceptions.py:34](D:/projects/Speech-Emotion-Recognition/ser_lib/core/exceptions.py:34) | 返回适合 CLI、日志或其他调用方消费的结构化信息。 |
| `ConfigurationError` | [ser_lib/core/exceptions.py:39](D:/projects/Speech-Emotion-Recognition/ser_lib/core/exceptions.py:39) | 配置文件无法读取、版本不兼容或内容校验失败。 |
| `SchemaMigrationError` | [ser_lib/core/exceptions.py:45](D:/projects/Speech-Emotion-Recognition/ser_lib/core/exceptions.py:45) | 持久化 schema 版本非法、缺迁移路径或迁移执行失败。 |
| `OperationCancelled` | [ser_lib/core/exceptions.py:51](D:/projects/Speech-Emotion-Recognition/ser_lib/core/exceptions.py:51) | 调用方请求取消一个可取消操作。 |

### ser_lib/core/logging.py

处理：**迁移**。目标：`ser_lib/foundation/logging.py`。理由：显式库日志 helper 保留。

直接 import 消费者（含测试；从公共包重导入的间接消费者还需沿 D/C 展开）：

- [ser_lib/core/__init__.py:31](D:/projects/Speech-Emotion-Recognition/ser_lib/core/__init__.py:31)；行 31

| class/function/method | 定义行 | 职责说明（源码 docstring） |
| --- | --- | --- |
| `get_logger(name: str \| None=None) -> logging.Logger` | [ser_lib/core/logging.py:12](D:/projects/Speech-Emotion-Recognition/ser_lib/core/logging.py:12) | 获取库命名空间下的 logger。 |
| `configure_library_logging(level: int \| str=logging.INFO, *, stream: TextIO \| None=None) -> logging.Handler` | [ser_lib/core/logging.py:19](D:/projects/Speech-Emotion-Recognition/ser_lib/core/logging.py:19) | 显式为 ``ser_lib`` 安装一个 handler，并返回它供调用方移除。 |

### ser_lib/core/migrations.py

处理：**拆分**。目标：`ser_lib/{config,data,engine,artifacts}/migrations.py`。理由：全局格式注册回归领域，禁止 foundation migrations。

直接 import 消费者（含测试；从公共包重导入的间接消费者还需沿 D/C 展开）：

- [ser_lib/artifacts/loader.py:24](D:/projects/Speech-Emotion-Recognition/ser_lib/artifacts/loader.py:24)；行 24
- [ser_lib/core/__init__.py:32](D:/projects/Speech-Emotion-Recognition/ser_lib/core/__init__.py:32)；行 32
- [ser_lib/core/config.py:82](D:/projects/Speech-Emotion-Recognition/ser_lib/core/config.py:82)；行 82
- [ser_lib/data/history.py:22](D:/projects/Speech-Emotion-Recognition/ser_lib/data/history.py:22)；行 22
- [ser_lib/data/manifest.py:21](D:/projects/Speech-Emotion-Recognition/ser_lib/data/manifest.py:21)；行 21
- [ser_lib/engine/evaluation_runs.py:14](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/evaluation_runs.py:14)；行 14
- [ser_lib/engine/runs.py:16](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/runs.py:16)；行 16

| class/function/method | 定义行 | 职责说明（源码 docstring） |
| --- | --- | --- |
| `SchemaMigration` | [ser_lib/core/migrations.py:16](D:/projects/Speech-Emotion-Recognition/ser_lib/core/migrations.py:16) | 一个严格的 ``N -> N+1`` schema migration。 |
| `SchemaMigration.__post_init__(self) -> None` | [ser_lib/core/migrations.py:24](D:/projects/Speech-Emotion-Recognition/ser_lib/core/migrations.py:24) |  |
| `MigrationRegistry` | [ser_lib/core/migrations.py:33](D:/projects/Speech-Emotion-Recognition/ser_lib/core/migrations.py:33) | 按 domain/from_version 注册并顺序执行 migration。 |
| `MigrationRegistry.__init__(self) -> None` | [ser_lib/core/migrations.py:36](D:/projects/Speech-Emotion-Recognition/ser_lib/core/migrations.py:36) |  |
| `MigrationRegistry.register(self, domain: str, from_version: int, to_version: int, function: MigrationFunction) -> SchemaMigration` | [ser_lib/core/migrations.py:39](D:/projects/Speech-Emotion-Recognition/ser_lib/core/migrations.py:39) |  |
| `MigrationRegistry.registered(self, domain: str \| None=None) -> tuple[SchemaMigration, ...]` | [ser_lib/core/migrations.py:55](D:/projects/Speech-Emotion-Recognition/ser_lib/core/migrations.py:55) |  |
| `MigrationRegistry.migrate(self, domain: str, payload: Mapping[str, Any], *, target_version: int) -> dict[str, Any]` | [ser_lib/core/migrations.py:61](D:/projects/Speech-Emotion-Recognition/ser_lib/core/migrations.py:61) |  |
| `_schema_version(payload: Mapping[str, Any], *, domain: str) -> int` | [ser_lib/core/migrations.py:135](D:/projects/Speech-Emotion-Recognition/ser_lib/core/migrations.py:135) | 见实现；私有辅助 |
| `validate_schema_version(domain: str, payload: Mapping[str, Any], *, supported_versions: set[int] \| frozenset[int] \| tuple[int, ...]) -> int` | [ser_lib/core/migrations.py:146](D:/projects/Speech-Emotion-Recognition/ser_lib/core/migrations.py:146) | 集中校验一个 payload 是否属于显式支持的 schema 版本。 |
| `register_schema_migration(domain: str, from_version: int, to_version: int, function: MigrationFunction) -> SchemaMigration` | [ser_lib/core/migrations.py:170](D:/projects/Speech-Emotion-Recognition/ser_lib/core/migrations.py:170) | 领域/公开定义 |
| `list_schema_migrations(domain: str \| None=None) -> tuple[SchemaMigration, ...]` | [ser_lib/core/migrations.py:179](D:/projects/Speech-Emotion-Recognition/ser_lib/core/migrations.py:179) | 领域/公开定义 |
| `migrate_schema_payload(domain: str, payload: Mapping[str, Any], *, target_version: int) -> dict[str, Any]` | [ser_lib/core/migrations.py:183](D:/projects/Speech-Emotion-Recognition/ser_lib/core/migrations.py:183) | 领域/公开定义 |

### ser_lib/data/__init__.py

处理：**瘦身**。目标：`原路径`。理由：更新 config/退役包装导出及内置注册顺序，不改变算法。

直接 import 消费者（含测试；从公共包重导入的间接消费者还需沿 D/C 展开）：

- [benchmarks/benchmark_data_pipeline.py:11](D:/projects/Speech-Emotion-Recognition/benchmarks/benchmark_data_pipeline.py:11)；行 11
- [examples/train_from_python.py:10](D:/projects/Speech-Emotion-Recognition/examples/train_from_python.py:10)；行 10
- [ser_lib/__init__.py:6](D:/projects/Speech-Emotion-Recognition/ser_lib/__init__.py:6)；行 6
- [ser_lib/catalog.py:16](D:/projects/Speech-Emotion-Recognition/ser_lib/catalog.py:16)；行 16
- [ser_lib/cli/main.py:17](D:/projects/Speech-Emotion-Recognition/ser_lib/cli/main.py:17)；行 17
- [ser_lib/cli/workflows.py:16](D:/projects/Speech-Emotion-Recognition/ser_lib/cli/workflows.py:16)；行 16
- [tests/test_batch_inference.py:11](D:/projects/Speech-Emotion-Recognition/tests/test_batch_inference.py:11)；行 11
- [tests/test_batch_prediction_events.py:5](D:/projects/Speech-Emotion-Recognition/tests/test_batch_prediction_events.py:5)；行 5
- [tests/test_batch_prediction_sink.py:8](D:/projects/Speech-Emotion-Recognition/tests/test_batch_prediction_sink.py:8)；行 8
- [tests/test_checkpoint_resume.py:10](D:/projects/Speech-Emotion-Recognition/tests/test_checkpoint_resume.py:10)；行 10
- [tests/test_compatibility_report.py:9](D:/projects/Speech-Emotion-Recognition/tests/test_compatibility_report.py:9)；行 9
- [tests/test_dataset_editor.py:6](D:/projects/Speech-Emotion-Recognition/tests/test_dataset_editor.py:6)；行 6
- [tests/test_dataset_fingerprint.py:4](D:/projects/Speech-Emotion-Recognition/tests/test_dataset_fingerprint.py:4)；行 4
- [tests/test_dataset_history.py:10](D:/projects/Speech-Emotion-Recognition/tests/test_dataset_history.py:10)；行 10
- [tests/test_dataset_profile.py:9](D:/projects/Speech-Emotion-Recognition/tests/test_dataset_profile.py:9)；行 9
- [tests/test_dataset_query.py:6](D:/projects/Speech-Emotion-Recognition/tests/test_dataset_query.py:6)；行 6
- [tests/test_dataset_summary.py:7](D:/projects/Speech-Emotion-Recognition/tests/test_dataset_summary.py:7)；行 7
- [tests/test_engine_config.py:10](D:/projects/Speech-Emotion-Recognition/tests/test_engine_config.py:10)；行 10
- [tests/test_evaluation_prediction_sink.py:7](D:/projects/Speech-Emotion-Recognition/tests/test_evaluation_prediction_sink.py:7)；行 7
- [tests/test_evaluator_observability.py:17](D:/projects/Speech-Emotion-Recognition/tests/test_evaluator_observability.py:17)；行 17
- [tests/test_evaluator_reports.py:15](D:/projects/Speech-Emotion-Recognition/tests/test_evaluator_reports.py:15)；行 15
- [tests/test_experiment_validation.py:8](D:/projects/Speech-Emotion-Recognition/tests/test_experiment_validation.py:8)；行 8
- [tests/test_pretrained_adapter.py:12](D:/projects/Speech-Emotion-Recognition/tests/test_pretrained_adapter.py:12)；行 12
- [tests/test_public_api.py:8](D:/projects/Speech-Emotion-Recognition/tests/test_public_api.py:8)；行 8
- [tests/test_ravdess_and_benchmark.py:11](D:/projects/Speech-Emotion-Recognition/tests/test_ravdess_and_benchmark.py:11)；行 11
- [tests/test_rnn_models.py:10](D:/projects/Speech-Emotion-Recognition/tests/test_rnn_models.py:10)；行 10
- [tests/test_services.py:6](D:/projects/Speech-Emotion-Recognition/tests/test_services.py:6)；行 6
- [tests/test_trainer_observability.py:17](D:/projects/Speech-Emotion-Recognition/tests/test_trainer_observability.py:17)；行 17
- [tests/test_training_lineage.py:9](D:/projects/Speech-Emotion-Recognition/tests/test_training_lineage.py:9)；行 9
- [tests/test_training_result.py:11](D:/projects/Speech-Emotion-Recognition/tests/test_training_result.py:11)；行 11
- [tests/test_training_run_catalog.py:12](D:/projects/Speech-Emotion-Recognition/tests/test_training_run_catalog.py:12)；行 12
- [tests/test_transformer_models.py:10](D:/projects/Speech-Emotion-Recognition/tests/test_transformer_models.py:10)；行 10

| class/function/method | 定义行 | 职责说明（源码 docstring） |
| --- | --- | --- |

### ser_lib/data/audio.py

处理：**拆分**。目标：`ser_lib/data/audio.py + ser_lib/config/data.py`。理由：AudioLoaderConfig 与 AudioSettings 四字段重复。

直接 import 消费者（含测试；从公共包重导入的间接消费者还需沿 D/C 展开）：

- [scripts/smoke_train_epoch.py:20](D:/projects/Speech-Emotion-Recognition/scripts/smoke_train_epoch.py:20)；行 20
- [ser_lib/artifacts/loader.py:25](D:/projects/Speech-Emotion-Recognition/ser_lib/artifacts/loader.py:25)；行 25
- [ser_lib/data/__init__.py:7](D:/projects/Speech-Emotion-Recognition/ser_lib/data/__init__.py:7)；行 7
- [ser_lib/data/dataset.py:16](D:/projects/Speech-Emotion-Recognition/ser_lib/data/dataset.py:16)；行 16
- [ser_lib/data/pipeline.py:16](D:/projects/Speech-Emotion-Recognition/ser_lib/data/pipeline.py:16)；行 16, 292
- [ser_lib/data/profiling.py:10](D:/projects/Speech-Emotion-Recognition/ser_lib/data/profiling.py:10)；行 10
- [ser_lib/engine/config.py:16](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/config.py:16)；行 16
- [ser_lib/inference/offline.py:8](D:/projects/Speech-Emotion-Recognition/ser_lib/inference/offline.py:8)；行 8
- [tests/test_audio_pipeline.py:9](D:/projects/Speech-Emotion-Recognition/tests/test_audio_pipeline.py:9)；行 9
- [tests/test_model_engine.py:11](D:/projects/Speech-Emotion-Recognition/tests/test_model_engine.py:11)；行 11

| class/function/method | 定义行 | 职责说明（源码 docstring） |
| --- | --- | --- |
| `AudioFileInfo` | [ser_lib/data/audio.py:41](D:/projects/Speech-Emotion-Recognition/ser_lib/data/audio.py:41) | 与具体解码库无关的稳定音频 header 信息。 |
| `_probe_soundfile(path: Path) -> AudioFileInfo` | [ser_lib/data/audio.py:50](D:/projects/Speech-Emotion-Recognition/ser_lib/data/audio.py:50) | 见实现；私有辅助 |
| `_probe_torchaudio(path: Path) -> AudioFileInfo` | [ser_lib/data/audio.py:60](D:/projects/Speech-Emotion-Recognition/ser_lib/data/audio.py:60) | 见实现；私有辅助 |
| `probe_audio(path: Path \| str, *, preferred_backend: AudioBackend='soundfile') -> AudioFileInfo` | [ser_lib/data/audio.py:70](D:/projects/Speech-Emotion-Recognition/ser_lib/data/audio.py:70) | 读取音频 header；TorchAudio 不可用时透明回退到 SoundFile。 |
| `_decode_soundfile(path: Path, *, frame_offset: int, num_frames: int) -> tuple[torch.Tensor, int]` | [ser_lib/data/audio.py:96](D:/projects/Speech-Emotion-Recognition/ser_lib/data/audio.py:96) | 见实现；私有辅助 |
| `_decode_torchaudio(path: Path, *, frame_offset: int, num_frames: int) -> tuple[torch.Tensor, int]` | [ser_lib/data/audio.py:115](D:/projects/Speech-Emotion-Recognition/ser_lib/data/audio.py:115) | 见实现；私有辅助 |
| `decode_audio(path: Path \| str, *, frame_offset: int=0, num_frames: int=-1, preferred_backend: AudioBackend='soundfile') -> tuple[torch.Tensor, int]` | [ser_lib/data/audio.py:127](D:/projects/Speech-Emotion-Recognition/ser_lib/data/audio.py:127) | 按 frame 范围解码音频并返回 ``([C,T], sample_rate)``。 |
| `AudioLoaderConfig` | [ser_lib/data/audio.py:159](D:/projects/Speech-Emotion-Recognition/ser_lib/data/audio.py:159) | AudioLoader 运行时配置（设计文档 §7.1）。 |
| `AudioLoader` | [ser_lib/data/audio.py:168](D:/projects/Speech-Emotion-Recognition/ser_lib/data/audio.py:168) | 从 :class:`AudioRecord` 加载音频并输出标准化的 :class:`AudioData`。 |
| `AudioLoader.__init__(self, config: AudioLoaderConfig \| None=None) -> None` | [ser_lib/data/audio.py:175](D:/projects/Speech-Emotion-Recognition/ser_lib/data/audio.py:175) |  |
| `AudioLoader.load(self, record: AudioRecord, *, base_dir: Path \| None=None) -> AudioData` | [ser_lib/data/audio.py:194](D:/projects/Speech-Emotion-Recognition/ser_lib/data/audio.py:194) | 加载一条记录对应的音频。 |
| `AudioLoader.resolve_path(audio_path: Path, base_dir: Path \| None) -> Path` | [ser_lib/data/audio.py:298](D:/projects/Speech-Emotion-Recognition/ser_lib/data/audio.py:298) | 解析音频路径：绝对路径直接规范化，相对路径基于 base_dir。 |
| `AudioLoader._segment_to_frames(self, record: AudioRecord, *, original_sr: int, total_frames: int, uid: str, path: Path) -> tuple[int, int]` | [ser_lib/data/audio.py:309](D:/projects/Speech-Emotion-Recognition/ser_lib/data/audio.py:309) | 把毫秒片段转换为 frame offset / num_frames。 |
| `AudioLoader._resample(self, waveform: torch.Tensor, orig_sr: int) -> torch.Tensor` | [ser_lib/data/audio.py:350](D:/projects/Speech-Emotion-Recognition/ser_lib/data/audio.py:350) | 用缓存的 resampler 重采样。key 含 (orig, target, dtype, device)。 |

### ser_lib/data/cache.py

处理：**保留**。目标：`原路径`。理由：实际为 SER 数据/执行基础，无确认的页面专属职责；更新被迁移 import。

直接 import 消费者（含测试；从公共包重导入的间接消费者还需沿 D/C 展开）：

- [ser_lib/data/__init__.py:8](D:/projects/Speech-Emotion-Recognition/ser_lib/data/__init__.py:8)；行 8
- [ser_lib/data/pipeline.py:262](D:/projects/Speech-Emotion-Recognition/ser_lib/data/pipeline.py:262)；行 262
- [tests/test_cache.py:5](D:/projects/Speech-Emotion-Recognition/tests/test_cache.py:5)；行 5

| class/function/method | 定义行 | 职责说明（源码 docstring） |
| --- | --- | --- |
| `_json_value(value: Any) -> Any` | [ser_lib/data/cache.py:18](D:/projects/Speech-Emotion-Recognition/ser_lib/data/cache.py:18) | 见实现；私有辅助 |
| `CachedRepresentation` | [ser_lib/data/cache.py:31](D:/projects/Speech-Emotion-Recognition/ser_lib/data/cache.py:31) | 缓存任意确定性 Representation 的输出。 |
| `CachedRepresentation.__init__(self, representation: Representation, directory: Path \| str) -> None` | [ser_lib/data/cache.py:42](D:/projects/Speech-Emotion-Recognition/ser_lib/data/cache.py:42) |  |
| `CachedRepresentation.output_specs(self) -> dict[str, TensorSpec]` | [ser_lib/data/cache.py:49](D:/projects/Speech-Emotion-Recognition/ser_lib/data/cache.py:49) |  |
| `CachedRepresentation.cache_key(self, audio: AudioData) -> str` | [ser_lib/data/cache.py:52](D:/projects/Speech-Emotion-Recognition/ser_lib/data/cache.py:52) |  |
| `CachedRepresentation.forward(self, audio: AudioData) -> RepresentationOutput` | [ser_lib/data/cache.py:80](D:/projects/Speech-Emotion-Recognition/ser_lib/data/cache.py:80) |  |
| `CachedRepresentation.entry_count(self) -> int` | [ser_lib/data/cache.py:119](D:/projects/Speech-Emotion-Recognition/ser_lib/data/cache.py:119) |  |
| `CachedRepresentation.size_bytes(self) -> int` | [ser_lib/data/cache.py:122](D:/projects/Speech-Emotion-Recognition/ser_lib/data/cache.py:122) |  |

### ser_lib/data/collate.py

处理：**保留**。目标：`原路径`。理由：实际为 SER 数据/执行基础，无确认的页面专属职责；更新被迁移 import。

直接 import 消费者（含测试；从公共包重导入的间接消费者还需沿 D/C 展开）：

- [scripts/smoke_train_epoch.py:21](D:/projects/Speech-Emotion-Recognition/scripts/smoke_train_epoch.py:21)；行 21
- [ser_lib/artifacts/loader.py:26](D:/projects/Speech-Emotion-Recognition/ser_lib/artifacts/loader.py:26)；行 26
- [ser_lib/data/__init__.py:9](D:/projects/Speech-Emotion-Recognition/ser_lib/data/__init__.py:9)；行 9
- [ser_lib/engine/config.py:17](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/config.py:17)；行 17, 113
- [ser_lib/inference/offline.py:9](D:/projects/Speech-Emotion-Recognition/ser_lib/inference/offline.py:9)；行 9
- [tests/test_audio_pipeline.py:10](D:/projects/Speech-Emotion-Recognition/tests/test_audio_pipeline.py:10)；行 10
- [tests/test_model_engine.py:10](D:/projects/Speech-Emotion-Recognition/tests/test_model_engine.py:10)；行 10
- [tests/test_new_collate.py:4](D:/projects/Speech-Emotion-Recognition/tests/test_new_collate.py:4)；行 4

| class/function/method | 定义行 | 职责说明（源码 docstring） |
| --- | --- | --- |
| `CollateStrategy` | [ser_lib/data/collate.py:36](D:/projects/Speech-Emotion-Recognition/ser_lib/data/collate.py:36) | 批处理策略（与 BatchingConfig.type 对齐）。 |
| `SERCollator` | [ser_lib/data/collate.py:44](D:/projects/Speech-Emotion-Recognition/ser_lib/data/collate.py:44) | 基于输入规格的通用 Collator。 |
| `SERCollator.__init__(self, specs: dict[str, TensorSpec], batching: BatchingConfig) -> None` | [ser_lib/data/collate.py:52](D:/projects/Speech-Emotion-Recognition/ser_lib/data/collate.py:52) |  |
| `SERCollator.__call__(self, samples: Sequence[SERSample]) -> SERBatch` | [ser_lib/data/collate.py:84](D:/projects/Speech-Emotion-Recognition/ser_lib/data/collate.py:84) |  |
| `SERCollator._collate_dynamic(self, samples: list[SERSample], labels: torch.Tensor \| None) -> SERBatch` | [ser_lib/data/collate.py:128](D:/projects/Speech-Emotion-Recognition/ser_lib/data/collate.py:128) |  |
| `SERCollator._collate_fixed(self, samples: list[SERSample], labels: torch.Tensor \| None) -> SERBatch` | [ser_lib/data/collate.py:158](D:/projects/Speech-Emotion-Recognition/ser_lib/data/collate.py:158) |  |
| `SERCollator._collate_sliding(self, samples: list[SERSample], labels: torch.Tensor \| None) -> SERBatch` | [ser_lib/data/collate.py:187](D:/projects/Speech-Emotion-Recognition/ser_lib/data/collate.py:187) |  |
| `_pad_time(tensor: torch.Tensor, spec: TensorSpec, target: int) -> torch.Tensor` | [ser_lib/data/collate.py:265](D:/projects/Speech-Emotion-Recognition/ser_lib/data/collate.py:265) | 沿 spec 的时间轴右侧 padding 到 target 长度。 |
| `_truncate_time(tensor: torch.Tensor, spec: TensorSpec, target: int) -> torch.Tensor` | [ser_lib/data/collate.py:279](D:/projects/Speech-Emotion-Recognition/ser_lib/data/collate.py:279) | 沿 spec 的时间轴截断到 target 长度。 |
| `_slice_time(tensor: torch.Tensor, spec: TensorSpec, start: int, end: int) -> torch.Tensor` | [ser_lib/data/collate.py:290](D:/projects/Speech-Emotion-Recognition/ser_lib/data/collate.py:290) | 沿 spec 的时间轴切片 [start, end)。 |
| `build_collator(specs: dict[str, TensorSpec], batching: BatchingConfig) -> SERCollator` | [ser_lib/data/collate.py:297](D:/projects/Speech-Emotion-Recognition/ser_lib/data/collate.py:297) | 便捷构造函数。 |

### ser_lib/data/config.py

处理：**迁移**。目标：`ser_lib/config/data.py`。理由：所有用户 schema 中央定义；Audio 两套配置合并。

直接 import 消费者（含测试；从公共包重导入的间接消费者还需沿 D/C 展开）：

- [scripts/smoke_train_epoch.py:22](D:/projects/Speech-Emotion-Recognition/scripts/smoke_train_epoch.py:22)；行 22
- [ser_lib/artifacts/exporter.py:26](D:/projects/Speech-Emotion-Recognition/ser_lib/artifacts/exporter.py:26)；行 26
- [ser_lib/artifacts/loader.py:27](D:/projects/Speech-Emotion-Recognition/ser_lib/artifacts/loader.py:27)；行 27
- [ser_lib/data/__init__.py:10](D:/projects/Speech-Emotion-Recognition/ser_lib/data/__init__.py:10)；行 10
- [ser_lib/data/collate.py:25](D:/projects/Speech-Emotion-Recognition/ser_lib/data/collate.py:25)；行 25
- [ser_lib/data/pipeline.py:18](D:/projects/Speech-Emotion-Recognition/ser_lib/data/pipeline.py:18)；行 18
- [ser_lib/data/validation.py:14](D:/projects/Speech-Emotion-Recognition/ser_lib/data/validation.py:14)；行 14
- [ser_lib/engine/config.py:12](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/config.py:12)；行 12
- [ser_lib/services/artifacts.py:23](D:/projects/Speech-Emotion-Recognition/ser_lib/services/artifacts.py:23)；行 23
- [tests/test_artifact_catalog.py:6](D:/projects/Speech-Emotion-Recognition/tests/test_artifact_catalog.py:6)；行 6
- [tests/test_artifact_inspect.py:11](D:/projects/Speech-Emotion-Recognition/tests/test_artifact_inspect.py:11)；行 11
- [tests/test_artifact_progress.py:12](D:/projects/Speech-Emotion-Recognition/tests/test_artifact_progress.py:12)；行 12
- [tests/test_artifacts.py:15](D:/projects/Speech-Emotion-Recognition/tests/test_artifacts.py:15)；行 15
- [tests/test_audio_pipeline.py:11](D:/projects/Speech-Emotion-Recognition/tests/test_audio_pipeline.py:11)；行 11
- [tests/test_cache.py:6](D:/projects/Speech-Emotion-Recognition/tests/test_cache.py:6)；行 6
- [tests/test_checkpoint_resume.py:11](D:/projects/Speech-Emotion-Recognition/tests/test_checkpoint_resume.py:11)；行 11
- [tests/test_engine_config.py:11](D:/projects/Speech-Emotion-Recognition/tests/test_engine_config.py:11)；行 11
- [tests/test_experiment_validation.py:9](D:/projects/Speech-Emotion-Recognition/tests/test_experiment_validation.py:9)；行 9
- [tests/test_model_engine.py:12](D:/projects/Speech-Emotion-Recognition/tests/test_model_engine.py:12)；行 12
- [tests/test_new_collate.py:5](D:/projects/Speech-Emotion-Recognition/tests/test_new_collate.py:5)；行 5
- [tests/test_pretrained_adapter.py:20](D:/projects/Speech-Emotion-Recognition/tests/test_pretrained_adapter.py:20)；行 20
- [tests/test_rnn_models.py:11](D:/projects/Speech-Emotion-Recognition/tests/test_rnn_models.py:11)；行 11
- [tests/test_services.py:7](D:/projects/Speech-Emotion-Recognition/tests/test_services.py:7)；行 7
- [tests/test_training_lineage.py:10](D:/projects/Speech-Emotion-Recognition/tests/test_training_lineage.py:10)；行 10
- [tests/test_training_run_catalog.py:13](D:/projects/Speech-Emotion-Recognition/tests/test_training_run_catalog.py:13)；行 13
- [tests/test_transformer_models.py:11](D:/projects/Speech-Emotion-Recognition/tests/test_transformer_models.py:11)；行 11

| class/function/method | 定义行 | 职责说明（源码 docstring） |
| --- | --- | --- |
| `_StrictModel` | [ser_lib/data/config.py:21](D:/projects/Speech-Emotion-Recognition/ser_lib/data/config.py:21) | 全库配置模型基类：禁止未知字段。 |
| `ComponentConfig` | [ser_lib/data/config.py:25](D:/projects/Speech-Emotion-Recognition/ser_lib/data/config.py:25) | 通用组件引用：``{type, params, probability}``。 |
| `AudioSettings` | [ser_lib/data/config.py:39](D:/projects/Speech-Emotion-Recognition/ser_lib/data/config.py:39) | AudioLoader 的可序列化配置（对应运行时 AudioLoaderConfig）。 |
| `CacheSettings` | [ser_lib/data/config.py:50](D:/projects/Speech-Emotion-Recognition/ser_lib/data/config.py:50) | 确定性 Representation 磁盘缓存。 |
| `FixedBatching` | [ser_lib/data/config.py:57](D:/projects/Speech-Emotion-Recognition/ser_lib/data/config.py:57) | 固定长度批处理参数：按 key 配置最大长度。 |
| `FixedBatching._positive(cls, v: dict[str, int]) -> dict[str, int]` | [ser_lib/data/config.py:64](D:/projects/Speech-Emotion-Recognition/ser_lib/data/config.py:64) |  |
| `SlidingBatching` | [ser_lib/data/config.py:71](D:/projects/Speech-Emotion-Recognition/ser_lib/data/config.py:71) | 滑动窗口批处理参数。 |
| `SlidingBatching._stride_le_window(cls, v: int, info) -> int` | [ser_lib/data/config.py:79](D:/projects/Speech-Emotion-Recognition/ser_lib/data/config.py:79) |  |
| `BatchingConfig` | [ser_lib/data/config.py:86](D:/projects/Speech-Emotion-Recognition/ser_lib/data/config.py:86) | 批处理配置（设计文档 §11）。 |
| `BatchingConfig._none_to_missing(cls, v: Any) -> Any` | [ser_lib/data/config.py:102](D:/projects/Speech-Emotion-Recognition/ser_lib/data/config.py:102) |  |
| `BatchingConfig.is_dynamic(self) -> bool` | [ser_lib/data/config.py:106](D:/projects/Speech-Emotion-Recognition/ser_lib/data/config.py:106) |  |
| `BatchingConfig.validate_completeness(self) -> None` | [ser_lib/data/config.py:109](D:/projects/Speech-Emotion-Recognition/ser_lib/data/config.py:109) | 校验策略与参数节点的一致性，在任务启动前失败。 |
| `DataConfig` | [ser_lib/data/config.py:126](D:/projects/Speech-Emotion-Recognition/ser_lib/data/config.py:126) | 数据模块顶层配置（设计文档 §15）。 |
| `DataConfig._validate_batching(cls, v: BatchingConfig) -> BatchingConfig` | [ser_lib/data/config.py:147](D:/projects/Speech-Emotion-Recognition/ser_lib/data/config.py:147) |  |
| `DataConfig._validate_labels(cls, v: dict[int, dict[str, Any]] \| None) -> dict[int, dict[str, Any]] \| None` | [ser_lib/data/config.py:153](D:/projects/Speech-Emotion-Recognition/ser_lib/data/config.py:153) |  |
| `DataConfig.num_classes(self) -> int \| None` | [ser_lib/data/config.py:162](D:/projects/Speech-Emotion-Recognition/ser_lib/data/config.py:162) |  |
| `load_data_config(path: Path \| str) -> DataConfig` | [ser_lib/data/config.py:166](D:/projects/Speech-Emotion-Recognition/ser_lib/data/config.py:166) | 从 YAML 文件加载 DataConfig。 |

### ser_lib/data/dataset.py

处理：**保留**。目标：`原路径`。理由：实际为 SER 数据/执行基础，无确认的页面专属职责；更新被迁移 import。

直接 import 消费者（含测试；从公共包重导入的间接消费者还需沿 D/C 展开）：

- [scripts/smoke_train_epoch.py:23](D:/projects/Speech-Emotion-Recognition/scripts/smoke_train_epoch.py:23)；行 23
- [ser_lib/data/__init__.py:11](D:/projects/Speech-Emotion-Recognition/ser_lib/data/__init__.py:11)；行 11
- [tests/test_audio_pipeline.py:12](D:/projects/Speech-Emotion-Recognition/tests/test_audio_pipeline.py:12)；行 12

| class/function/method | 定义行 | 职责说明（源码 docstring） |
| --- | --- | --- |
| `SERDataset` | [ser_lib/data/dataset.py:22](D:/projects/Speech-Emotion-Recognition/ser_lib/data/dataset.py:22) | 核心 SER 数据集。 |
| `SERDataset.__init__(self, records: Sequence[AudioRecord], audio_loader: AudioLoader, pipeline: SamplePipeline, *, base_dir: Path \| None=None, strict: bool=True) -> None` | [ser_lib/data/dataset.py:34](D:/projects/Speech-Emotion-Recognition/ser_lib/data/dataset.py:34) |  |
| `SERDataset.__len__(self) -> int` | [ser_lib/data/dataset.py:54](D:/projects/Speech-Emotion-Recognition/ser_lib/data/dataset.py:54) |  |
| `SERDataset.__getitem__(self, index: int) -> SERSample` | [ser_lib/data/dataset.py:57](D:/projects/Speech-Emotion-Recognition/ser_lib/data/dataset.py:57) |  |
| `SERDataset.records(self) -> tuple[AudioRecord, ...]` | [ser_lib/data/dataset.py:63](D:/projects/Speech-Emotion-Recognition/ser_lib/data/dataset.py:63) | 数据集内的记录（只读视图）。 |
| `SERDataset.get_labels(self) -> list[int \| None]` | [ser_lib/data/dataset.py:67](D:/projects/Speech-Emotion-Recognition/ser_lib/data/dataset.py:67) | 返回全部标签列表，用于计算类别权重或平衡采样。 |

### ser_lib/data/editor.py

处理：**保留**。目标：`原路径`。理由：事务编辑、乐观并发、回滚保留。

直接 import 消费者（含测试；从公共包重导入的间接消费者还需沿 D/C 展开）：

- [ser_lib/data/__init__.py:12](D:/projects/Speech-Emotion-Recognition/ser_lib/data/__init__.py:12)；行 12
- [ser_lib/services/datasets.py:9](D:/projects/Speech-Emotion-Recognition/ser_lib/services/datasets.py:9)；行 9
- [tests/test_dataset_editor.py:5](D:/projects/Speech-Emotion-Recognition/tests/test_dataset_editor.py:5)；行 5

| class/function/method | 定义行 | 职责说明（源码 docstring） |
| --- | --- | --- |
| `DatasetEditor` | [ser_lib/data/editor.py:27](D:/projects/Speech-Emotion-Recognition/ser_lib/data/editor.py:27) | 对标准 Dataset 做内存编辑，并通过事务层一次性提交。 |
| `DatasetEditor.__init__(self, manifest: DatasetManifest \| Path \| str) -> None` | [ser_lib/data/editor.py:41](D:/projects/Speech-Emotion-Recognition/ser_lib/data/editor.py:41) |  |
| `DatasetEditor.dataset_id(self) -> str` | [ser_lib/data/editor.py:56](D:/projects/Speech-Emotion-Recognition/ser_lib/data/editor.py:56) |  |
| `DatasetEditor.dirty(self) -> bool` | [ser_lib/data/editor.py:60](D:/projects/Speech-Emotion-Recognition/ser_lib/data/editor.py:60) |  |
| `DatasetEditor.snapshot(self) -> DatasetManifest` | [ser_lib/data/editor.py:66](D:/projects/Speech-Emotion-Recognition/ser_lib/data/editor.py:66) | 返回当前内存编辑状态的独立 ``DatasetManifest`` 视图。 |
| `DatasetEditor.update_record(self, uid: str, *, audio_path: Path \| str \| object=_UNSET, label: int \| None \| object=_UNSET, split: str \| object=_UNSET, speaker_id: str \| None \| object=_UNSET, start_ms: int \| None \| object=_UNSET, end_ms: int \| None \| object=_UNSET, sample_rate_hint: int \| None \| object=_UNSET, metadata: Mapping[str, Any] \| object=_UNSET) -> AudioRecord` | [ser_lib/data/editor.py:74](D:/projects/Speech-Emotion-Recognition/ser_lib/data/editor.py:74) | 修改单条记录；未传字段保持不变。 |
| `DatasetEditor.delete_records(self, uids: Iterable[str]) -> int` | [ser_lib/data/editor.py:120](D:/projects/Speech-Emotion-Recognition/ser_lib/data/editor.py:120) | 删除一批记录；任一 uid 不存在时整个操作拒绝执行。 |
| `DatasetEditor.move_records(self, uids: Iterable[str], split: str) -> int` | [ser_lib/data/editor.py:129](D:/projects/Speech-Emotion-Recognition/ser_lib/data/editor.py:129) | 批量移动记录到目标 split。 |
| `DatasetEditor.replace_label(self, source_label: int \| None, target_label: int \| None, *, split: str \| None=None) -> int` | [ser_lib/data/editor.py:138](D:/projects/Speech-Emotion-Recognition/ser_lib/data/editor.py:138) | 批量把 ``source_label`` 替换成 ``target_label``。 |
| `DatasetEditor.update_speaker(self, uids: Iterable[str], speaker_id: str \| None) -> int` | [ser_lib/data/editor.py:159](D:/projects/Speech-Emotion-Recognition/ser_lib/data/editor.py:159) | 批量设置或清空 speaker_id。 |
| `DatasetEditor.rollback(self) -> 'DatasetEditor'` | [ser_lib/data/editor.py:170](D:/projects/Speech-Emotion-Recognition/ser_lib/data/editor.py:170) | 丢弃所有尚未提交的内存修改。 |
| `DatasetEditor.commit(self) -> DatasetManifest` | [ser_lib/data/editor.py:176](D:/projects/Speech-Emotion-Recognition/ser_lib/data/editor.py:176) | 把当前编辑状态事务化写回磁盘，并返回重新加载后的 Dataset。 |
| `DatasetEditor._write_staging(self, staging_root: Path) -> '_CommitPlan'` | [ser_lib/data/editor.py:223](D:/projects/Speech-Emotion-Recognition/ser_lib/data/editor.py:223) |  |
| `DatasetEditor._dataset_doc(self, split_refs: Mapping[str, str]) -> dict[str, Any]` | [ser_lib/data/editor.py:280](D:/projects/Speech-Emotion-Recognition/ser_lib/data/editor.py:280) |  |
| `DatasetEditor._commit_plan(self, plan: '_CommitPlan') -> None` | [ser_lib/data/editor.py:292](D:/projects/Speech-Emotion-Recognition/ser_lib/data/editor.py:292) |  |
| `DatasetEditor._assert_source_unchanged(self) -> None` | [ser_lib/data/editor.py:324](D:/projects/Speech-Emotion-Recognition/ser_lib/data/editor.py:324) |  |
| `DatasetEditor._index_for_uid(self, uid: str) -> int` | [ser_lib/data/editor.py:338](D:/projects/Speech-Emotion-Recognition/ser_lib/data/editor.py:338) |  |
| `DatasetEditor._require_uids(self, uids: set[str]) -> None` | [ser_lib/data/editor.py:344](D:/projects/Speech-Emotion-Recognition/ser_lib/data/editor.py:344) |  |
| `DatasetEditor._normalize_uids(uids: Iterable[str]) -> set[str]` | [ser_lib/data/editor.py:351](D:/projects/Speech-Emotion-Recognition/ser_lib/data/editor.py:351) |  |
| `DatasetEditor._validate_label(self, label: object) -> None` | [ser_lib/data/editor.py:359](D:/projects/Speech-Emotion-Recognition/ser_lib/data/editor.py:359) |  |
| `DatasetEditor._validate_split(split: object) -> None` | [ser_lib/data/editor.py:369](D:/projects/Speech-Emotion-Recognition/ser_lib/data/editor.py:369) |  |
| `_CommitPlan` | [ser_lib/data/editor.py:376](D:/projects/Speech-Emotion-Recognition/ser_lib/data/editor.py:376) | 见实现；私有辅助 |
| `_CommitPlan.__init__(self, *, validation_yaml: Path, final_yaml: Path, staged_paths: dict[str, Path], target_paths: dict[str, Path]) -> None` | [ser_lib/data/editor.py:377](D:/projects/Speech-Emotion-Recognition/ser_lib/data/editor.py:377) |  |
| `_write_yaml(doc: Mapping[str, Any], path: Path) -> None` | [ser_lib/data/editor.py:391](D:/projects/Speech-Emotion-Recognition/ser_lib/data/editor.py:391) | 见实现；私有辅助 |
| `_path_reference(path: Path, base: Path) -> str` | [ser_lib/data/editor.py:396](D:/projects/Speech-Emotion-Recognition/ser_lib/data/editor.py:396) | 见实现；私有辅助 |
| `_commit_replace_file(source: Path, target: Path) -> None` | [ser_lib/data/editor.py:403](D:/projects/Speech-Emotion-Recognition/ser_lib/data/editor.py:403) | 把 staged 文件在目标目录中通过 ``os.replace`` 原子替换。 |
| `_restore_backups(backups: Mapping[Path, Path \| None]) -> list[str]` | [ser_lib/data/editor.py:419](D:/projects/Speech-Emotion-Recognition/ser_lib/data/editor.py:419) | 见实现；私有辅助 |
| `_restore_file(source: Path, target: Path) -> None` | [ser_lib/data/editor.py:432](D:/projects/Speech-Emotion-Recognition/ser_lib/data/editor.py:432) | 见实现；私有辅助 |

### ser_lib/data/errors.py

处理：**拆分**。目标：`原路径 + foundation/errors.py + engine/compatibility.py`。理由：RegistryError 跨模型/数据共用；CompatibilityError 跨域归位。

直接 import 消费者（含测试；从公共包重导入的间接消费者还需沿 D/C 展开）：

- [ser_lib/catalog.py:18](D:/projects/Speech-Emotion-Recognition/ser_lib/catalog.py:18)；行 18
- [ser_lib/data/__init__.py:13](D:/projects/Speech-Emotion-Recognition/ser_lib/data/__init__.py:13)；行 13
- [ser_lib/data/audio.py:27](D:/projects/Speech-Emotion-Recognition/ser_lib/data/audio.py:27)；行 27
- [ser_lib/data/collate.py:26](D:/projects/Speech-Emotion-Recognition/ser_lib/data/collate.py:26)；行 26
- [ser_lib/data/dataset.py:17](D:/projects/Speech-Emotion-Recognition/ser_lib/data/dataset.py:17)；行 17
- [ser_lib/data/editor.py:15](D:/projects/Speech-Emotion-Recognition/ser_lib/data/editor.py:15)；行 15
- [ser_lib/data/history.py:23](D:/projects/Speech-Emotion-Recognition/ser_lib/data/history.py:23)；行 23
- [ser_lib/data/importers/jsonl_importer.py:13](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/jsonl_importer.py:13)；行 13
- [ser_lib/data/manifest.py:22](D:/projects/Speech-Emotion-Recognition/ser_lib/data/manifest.py:22)；行 22
- [ser_lib/data/pipeline.py:19](D:/projects/Speech-Emotion-Recognition/ser_lib/data/pipeline.py:19)；行 19, 206, 223
- [ser_lib/data/registry.py:18](D:/projects/Speech-Emotion-Recognition/ser_lib/data/registry.py:18)；行 18
- [ser_lib/data/representations/acoustic.py:25](D:/projects/Speech-Emotion-Recognition/ser_lib/data/representations/acoustic.py:25)；行 25
- [ser_lib/data/representations/base.py:14](D:/projects/Speech-Emotion-Recognition/ser_lib/data/representations/base.py:14)；行 14
- [ser_lib/data/representations/composite.py:15](D:/projects/Speech-Emotion-Recognition/ser_lib/data/representations/composite.py:15)；行 15
- [ser_lib/data/representations/spectral.py:14](D:/projects/Speech-Emotion-Recognition/ser_lib/data/representations/spectral.py:14)；行 14
- [ser_lib/data/transforms/base.py:14](D:/projects/Speech-Emotion-Recognition/ser_lib/data/transforms/base.py:14)；行 14
- [ser_lib/data/types.py:20](D:/projects/Speech-Emotion-Recognition/ser_lib/data/types.py:20)；行 20
- [ser_lib/data/validation.py:15](D:/projects/Speech-Emotion-Recognition/ser_lib/data/validation.py:15)；行 15
- [ser_lib/models/registry.py:9](D:/projects/Speech-Emotion-Recognition/ser_lib/models/registry.py:9)；行 9
- [tests/test_audio_pipeline.py:13](D:/projects/Speech-Emotion-Recognition/tests/test_audio_pipeline.py:13)；行 13
- [tests/test_compatibility_report.py:10](D:/projects/Speech-Emotion-Recognition/tests/test_compatibility_report.py:10)；行 10
- [tests/test_component_catalog.py:20](D:/projects/Speech-Emotion-Recognition/tests/test_component_catalog.py:20)；行 20
- [tests/test_core.py:24](D:/projects/Speech-Emotion-Recognition/tests/test_core.py:24)；行 24
- [tests/test_diagnostics.py:10](D:/projects/Speech-Emotion-Recognition/tests/test_diagnostics.py:10)；行 10
- [tests/test_engine_config.py:12](D:/projects/Speech-Emotion-Recognition/tests/test_engine_config.py:12)；行 12
- [tests/test_manifest.py:5](D:/projects/Speech-Emotion-Recognition/tests/test_manifest.py:5)；行 5
- [tests/test_new_collate.py:6](D:/projects/Speech-Emotion-Recognition/tests/test_new_collate.py:6)；行 6
- [tests/test_registry_config.py:4](D:/projects/Speech-Emotion-Recognition/tests/test_registry_config.py:4)；行 4

| class/function/method | 定义行 | 职责说明（源码 docstring） |
| --- | --- | --- |
| `SERDataError` | [ser_lib/data/errors.py:30](D:/projects/Speech-Emotion-Recognition/ser_lib/data/errors.py:30) | 数据模块所有业务异常的基类。 |
| `SERDataError.__init__(self, message: str, *, uid: str \| None=None, path: Path \| str \| None=None, component: str \| None=None, stage: str \| None=None) -> None` | [ser_lib/data/errors.py:35](D:/projects/Speech-Emotion-Recognition/ser_lib/data/errors.py:35) | 初始化异常。 |
| `ManifestError` | [ser_lib/data/errors.py:77](D:/projects/Speech-Emotion-Recognition/ser_lib/data/errors.py:77) | Manifest 读取、校验或路径解析失败。 |
| `DatasetEditError` | [ser_lib/data/errors.py:83](D:/projects/Speech-Emotion-Recognition/ser_lib/data/errors.py:83) | DatasetEditor 参数、目标记录或编辑操作非法。 |
| `DatasetEditConflictError` | [ser_lib/data/errors.py:89](D:/projects/Speech-Emotion-Recognition/ser_lib/data/errors.py:89) | 编辑期间源 Dataset 已被外部修改，拒绝覆盖新版本。 |
| `DatasetTransactionError` | [ser_lib/data/errors.py:95](D:/projects/Speech-Emotion-Recognition/ser_lib/data/errors.py:95) | Dataset staging、验证、提交或自动恢复失败。 |
| `AudioNotFoundError` | [ser_lib/data/errors.py:101](D:/projects/Speech-Emotion-Recognition/ser_lib/data/errors.py:101) | 音频文件不存在。 |
| `AudioDecodeError` | [ser_lib/data/errors.py:107](D:/projects/Speech-Emotion-Recognition/ser_lib/data/errors.py:107) | 音频解码失败或内容损坏。 |
| `InvalidAudioSegmentError` | [ser_lib/data/errors.py:113](D:/projects/Speech-Emotion-Recognition/ser_lib/data/errors.py:113) | 音频片段定义非法（越界、零长度或解码结果为空）。 |
| `RepresentationError` | [ser_lib/data/errors.py:119](D:/projects/Speech-Emotion-Recognition/ser_lib/data/errors.py:119) | 表示（Representation）计算失败或输出违反契约。 |
| `TransformError` | [ser_lib/data/errors.py:125](D:/projects/Speech-Emotion-Recognition/ser_lib/data/errors.py:125) | Transform 构建或执行失败。 |
| `CollationError` | [ser_lib/data/errors.py:131](D:/projects/Speech-Emotion-Recognition/ser_lib/data/errors.py:131) | 批处理（collate）失败：key 不一致、layout 不匹配、部分样本缺标签等。 |
| `CompatibilityError` | [ser_lib/data/errors.py:137](D:/projects/Speech-Emotion-Recognition/ser_lib/data/errors.py:137) | 表示、批处理与模型输入要求之间的兼容性校验失败。 |
| `RegistryError` | [ser_lib/data/errors.py:143](D:/projects/Speech-Emotion-Recognition/ser_lib/data/errors.py:143) | 注册表操作失败：重复注册、未知组件、schema 校验失败等。 |
| `wrap_error(exc: Exception, target: type[SERDataError], message: str, *, uid: str \| None=None, path: Any=None, component: str \| None=None, stage: str \| None=None) -> SERDataError` | [ser_lib/data/errors.py:149](D:/projects/Speech-Emotion-Recognition/ser_lib/data/errors.py:149) | 把底层异常包装为业务异常并保留 ``__cause__``。 |

### ser_lib/data/fingerprint.py

处理：**保留**。目标：`原路径`。理由：清单文件指纹保留，不把它描述为音频内容指纹。

直接 import 消费者（含测试；从公共包重导入的间接消费者还需沿 D/C 展开）：

- [ser_lib/data/__init__.py:19](D:/projects/Speech-Emotion-Recognition/ser_lib/data/__init__.py:19)；行 19
- [ser_lib/data/editor.py:20](D:/projects/Speech-Emotion-Recognition/ser_lib/data/editor.py:20)；行 20
- [ser_lib/data/history.py:24](D:/projects/Speech-Emotion-Recognition/ser_lib/data/history.py:24)；行 24
- [ser_lib/services/datasets.py:10](D:/projects/Speech-Emotion-Recognition/ser_lib/services/datasets.py:10)；行 10

| class/function/method | 定义行 | 职责说明（源码 docstring） |
| --- | --- | --- |
| `DatasetFingerprint` | [ser_lib/data/fingerprint.py:17](D:/projects/Speech-Emotion-Recognition/ser_lib/data/fingerprint.py:17) | 由 dataset.yaml 与 split manifests 生成的稳定内容指纹。 |
| `DatasetFingerprint.to_dict(self) -> dict[str, Any]` | [ser_lib/data/fingerprint.py:25](D:/projects/Speech-Emotion-Recognition/ser_lib/data/fingerprint.py:25) |  |
| `fingerprint_manifest(manifest: DatasetManifest \| Path \| str, *, event_callback: EventCallback \| None=None, cancellation: CancellationCheck \| None=None) -> DatasetFingerprint` | [ser_lib/data/fingerprint.py:29](D:/projects/Speech-Emotion-Recognition/ser_lib/data/fingerprint.py:29) | 计算 dataset.yaml + 所有声明 split 文件的 SHA256 指纹。 |
| `_sha256_file(path: Path, *, cancellation: CancellationCheck \| None=None) -> str` | [ser_lib/data/fingerprint.py:82](D:/projects/Speech-Emotion-Recognition/ser_lib/data/fingerprint.py:82) | 见实现；私有辅助 |

### ser_lib/data/history.py

处理：**保留**。目标：`原路径 + ser_lib/data/migrations.py`。理由：manifest 修订/事务恢复真实价值；不备份音频。

直接 import 消费者（含测试；从公共包重导入的间接消费者还需沿 D/C 展开）：

- [ser_lib/data/__init__.py:20](D:/projects/Speech-Emotion-Recognition/ser_lib/data/__init__.py:20)；行 20
- [ser_lib/services/datasets.py:11](D:/projects/Speech-Emotion-Recognition/ser_lib/services/datasets.py:11)；行 11

| class/function/method | 定义行 | 职责说明（源码 docstring） |
| --- | --- | --- |
| `_valid_sha256(value: str) -> bool` | [ser_lib/data/history.py:34](D:/projects/Speech-Emotion-Recognition/ser_lib/data/history.py:34) | 见实现；私有辅助 |
| `_RevisionFileModel` | [ser_lib/data/history.py:40](D:/projects/Speech-Emotion-Recognition/ser_lib/data/history.py:40) | 见实现；私有辅助 |
| `_RevisionFileModel._safe_snapshot_file(cls, value: str) -> str` | [ser_lib/data/history.py:50](D:/projects/Speech-Emotion-Recognition/ser_lib/data/history.py:50) |  |
| `_RevisionFileModel._sha256(cls, value: str) -> str` | [ser_lib/data/history.py:63](D:/projects/Speech-Emotion-Recognition/ser_lib/data/history.py:63) |  |
| `_RevisionRecordModel` | [ser_lib/data/history.py:69](D:/projects/Speech-Emotion-Recognition/ser_lib/data/history.py:69) | 见实现；私有辅助 |
| `_RevisionRecordModel._revision_id(cls, value: str) -> str` | [ser_lib/data/history.py:83](D:/projects/Speech-Emotion-Recognition/ser_lib/data/history.py:83) |  |
| `_RevisionRecordModel._fingerprint(cls, value: str) -> str` | [ser_lib/data/history.py:90](D:/projects/Speech-Emotion-Recognition/ser_lib/data/history.py:90) |  |
| `_RevisionRecordModel._timezone_aware(cls, value: datetime) -> datetime` | [ser_lib/data/history.py:97](D:/projects/Speech-Emotion-Recognition/ser_lib/data/history.py:97) |  |
| `_RevisionRecordModel._validate_files(self) -> '_RevisionRecordModel'` | [ser_lib/data/history.py:103](D:/projects/Speech-Emotion-Recognition/ser_lib/data/history.py:103) |  |
| `DatasetRevisionInfo` | [ser_lib/data/history.py:118](D:/projects/Speech-Emotion-Recognition/ser_lib/data/history.py:118) | 领域/公开定义 |
| `DatasetRevisionInfo.to_dict(self) -> dict[str, Any]` | [ser_lib/data/history.py:129](D:/projects/Speech-Emotion-Recognition/ser_lib/data/history.py:129) |  |
| `DatasetRevisionScanFailure` | [ser_lib/data/history.py:144](D:/projects/Speech-Emotion-Recognition/ser_lib/data/history.py:144) | 领域/公开定义 |
| `DatasetRevisionScanFailure.to_dict(self) -> dict[str, str]` | [ser_lib/data/history.py:149](D:/projects/Speech-Emotion-Recognition/ser_lib/data/history.py:149) |  |
| `DatasetRevisionCatalog` | [ser_lib/data/history.py:158](D:/projects/Speech-Emotion-Recognition/ser_lib/data/history.py:158) | 领域/公开定义 |
| `DatasetRevisionCatalog.total(self) -> int` | [ser_lib/data/history.py:165](D:/projects/Speech-Emotion-Recognition/ser_lib/data/history.py:165) |  |
| `DatasetRevisionCatalog.to_dict(self) -> dict[str, Any]` | [ser_lib/data/history.py:168](D:/projects/Speech-Emotion-Recognition/ser_lib/data/history.py:168) |  |
| `create_dataset_revision(manifest: DatasetManifest \| Path \| str, *, history_root: Path \| str \| None=None, revision_id: str \| None=None, note: str='', created_at: datetime \| None=None, event_callback: EventCallback \| None=None, cancellation: CancellationCheck \| None=None) -> DatasetRevisionInfo` | [ser_lib/data/history.py:178](D:/projects/Speech-Emotion-Recognition/ser_lib/data/history.py:178) | 快照 dataset.yaml 与 split JSONL；音频文件永远不会被复制。 |
| `inspect_dataset_revision(path: Path \| str, *, verify: bool=False, cancellation: CancellationCheck \| None=None) -> DatasetRevisionInfo` | [ser_lib/data/history.py:298](D:/projects/Speech-Emotion-Recognition/ser_lib/data/history.py:298) | 读取一个 revision；``verify=True`` 时重新 hash 所有快照文件。 |
| `scan_dataset_revisions(manifest: DatasetManifest \| Path \| str, *, history_root: Path \| str \| None=None, fail_fast: bool=False, event_callback: EventCallback \| None=None, cancellation: CancellationCheck \| None=None) -> DatasetRevisionCatalog` | [ser_lib/data/history.py:333](D:/projects/Speech-Emotion-Recognition/ser_lib/data/history.py:333) | 扫描当前 Dataset 的 revision 目录，不做内容 hash。 |
| `restore_dataset_revision(manifest: DatasetManifest \| Path \| str, revision: Path \| str, *, expected_current_fingerprint: str, event_callback: EventCallback \| None=None, cancellation: CancellationCheck \| None=None) -> DatasetManifest` | [ser_lib/data/history.py:386](D:/projects/Speech-Emotion-Recognition/ser_lib/data/history.py:386) | 在乐观锁保护下，把 Dataset manifest 文件事务化恢复到指定 revision。 |
| `_load_dataset(manifest: DatasetManifest \| Path \| str) -> DatasetManifest` | [ser_lib/data/history.py:494](D:/projects/Speech-Emotion-Recognition/ser_lib/data/history.py:494) | 见实现；私有辅助 |
| `_history_root(dataset: DatasetManifest, history_root: Path \| str \| None) -> Path` | [ser_lib/data/history.py:502](D:/projects/Speech-Emotion-Recognition/ser_lib/data/history.py:502) | 见实现；私有辅助 |
| `_ordered_logical_names(files: dict[str, _RevisionFileModel]) -> list[str]` | [ser_lib/data/history.py:510](D:/projects/Speech-Emotion-Recognition/ser_lib/data/history.py:510) | 见实现；私有辅助 |
| `_combined_digest(files: dict[str, _RevisionFileModel]) -> str` | [ser_lib/data/history.py:514](D:/projects/Speech-Emotion-Recognition/ser_lib/data/history.py:514) | 见实现；私有辅助 |
| `_load_revision(path: Path \| str) -> tuple[Path, _RevisionRecordModel]` | [ser_lib/data/history.py:524](D:/projects/Speech-Emotion-Recognition/ser_lib/data/history.py:524) | 见实现；私有辅助 |
| `_copy_hash(source: Path, destination: Path, *, cancellation: CancellationCheck \| None, on_chunk: Callable[[int], None] \| None=None) -> tuple[str, int]` | [ser_lib/data/history.py:542](D:/projects/Speech-Emotion-Recognition/ser_lib/data/history.py:542) | 见实现；私有辅助 |
| `_sha256(path: Path, *, cancellation: CancellationCheck \| None=None) -> str` | [ser_lib/data/history.py:567](D:/projects/Speech-Emotion-Recognition/ser_lib/data/history.py:567) | 见实现；私有辅助 |
| `_stage_file(source: Path, target: Path) -> Path` | [ser_lib/data/history.py:577](D:/projects/Speech-Emotion-Recognition/ser_lib/data/history.py:577) | 见实现；私有辅助 |
| `_backup_file(target: Path) -> Path \| None` | [ser_lib/data/history.py:588](D:/projects/Speech-Emotion-Recognition/ser_lib/data/history.py:588) | 见实现；私有辅助 |
| `_restore_backups(backups: dict[Path, Path \| None]) -> list[str]` | [ser_lib/data/history.py:601](D:/projects/Speech-Emotion-Recognition/ser_lib/data/history.py:601) | 见实现；私有辅助 |
| `_emit_progress(callback: EventCallback \| None, stage: str, completed: int, total: int, details: dict[str, Any]) -> None` | [ser_lib/data/history.py:614](D:/projects/Speech-Emotion-Recognition/ser_lib/data/history.py:614) | 见实现；私有辅助 |

### ser_lib/data/importers/__init__.py

处理：**瘦身**。目标：`原路径`。理由：更新 config/退役包装导出及内置注册顺序，不改变算法。

直接 import 消费者（含测试；从公共包重导入的间接消费者还需沿 D/C 展开）：

- [ser_lib/data/__init__.py:25](D:/projects/Speech-Emotion-Recognition/ser_lib/data/__init__.py:25)；行 25
- [tests/test_diagnostics.py:14](D:/projects/Speech-Emotion-Recognition/tests/test_diagnostics.py:14)；行 14
- [tests/test_importer_observability.py:15](D:/projects/Speech-Emotion-Recognition/tests/test_importer_observability.py:15)；行 15

| class/function/method | 定义行 | 职责说明（源码 docstring） |
| --- | --- | --- |
| `register_importers(registry=default_registry) -> None` | [ser_lib/data/importers/__init__.py:33](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/__init__.py:33) | 领域/公开定义 |

### ser_lib/data/importers/_conversion.py

处理：**保留**。目标：`原路径`。理由：实际为 SER 数据/执行基础，无确认的页面专属职责；更新被迁移 import。

直接 import 消费者（含测试；从公共包重导入的间接消费者还需沿 D/C 展开）：

- [ser_lib/data/importers/casia.py:12](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/casia.py:12)；行 12
- [ser_lib/data/importers/crema_d.py:13](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/crema_d.py:13)；行 13
- [ser_lib/data/importers/csemotions.py:13](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/csemotions.py:13)；行 13
- [ser_lib/data/importers/csv_importer.py:13](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/csv_importer.py:13)；行 13
- [ser_lib/data/importers/emotiontalk.py:13](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/emotiontalk.py:13)；行 13
- [ser_lib/data/importers/esd.py:12](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/esd.py:12)；行 12
- [ser_lib/data/importers/folder.py:12](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/folder.py:12)；行 12
- [ser_lib/data/importers/jsonl_importer.py:14](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/jsonl_importer.py:14)；行 14
- [ser_lib/data/importers/ravdess.py:12](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/ravdess.py:12)；行 12

| class/function/method | 定义行 | 职责说明（源码 docstring） |
| --- | --- | --- |
| `run_manifest_conversion(*, importer_id: str, scan: ScanCallable, source: Path, destination: Path, config: Mapping[str, Any], build_manifest: BuildManifest, failure_message: FailureFormatter \| None=None, event_callback: EventCallback \| None=None, cancellation: CancellationCheck \| None=None, event_context: EventContext \| None=None) -> DatasetManifest` | [ser_lib/data/importers/_conversion.py:26](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/_conversion.py:26) | 统一 convert 生命周期、scan 调用、preview 门禁和终态统计。 |
| `run_single_manifest_conversion(*, importer_id: str, scan: ScanCallable, source: Path, destination: Path, config: Mapping[str, Any], dataset_id: str, root: Path \| str, labels: LabelResolver \| None=None, records: RecordResolver \| None=None, failure_message: FailureFormatter \| None=None, event_callback: EventCallback \| None=None, cancellation: CancellationCheck \| None=None, event_context: EventContext \| None=None) -> DatasetManifest` | [ser_lib/data/importers/_conversion.py:87](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/_conversion.py:87) | 执行单 JSONL manifest importer 的标准 convert 流程。 |
| `write_partitioned_manifest(*, destination: Path, dataset_id: str, root: Path \| str, split_names: Sequence[str], labels: Mapping[int, Mapping[str, str]], records: Sequence[AudioRecord], assignments: Mapping[str, str], task: ImportTask) -> DatasetManifest` | [ser_lib/data/importers/_conversion.py:142](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/_conversion.py:142) | 统一写入带显式 record→split 映射的标准 DatasetManifest。 |

### ser_lib/data/importers/base.py

处理：**保留**。目标：`原路径`。理由：实际为 SER 数据/执行基础，无确认的页面专属职责；更新被迁移 import。

直接 import 消费者（含测试；从公共包重导入的间接消费者还需沿 D/C 展开）：

- [ser_lib/data/importers/__init__.py:5](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/__init__.py:5)；行 5
- [ser_lib/data/importers/_conversion.py:12](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/_conversion.py:12)；行 12
- [ser_lib/data/importers/casia.py:13](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/casia.py:13)；行 13
- [ser_lib/data/importers/crema_d.py:14](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/crema_d.py:14)；行 14
- [ser_lib/data/importers/csemotions.py:14](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/csemotions.py:14)；行 14
- [ser_lib/data/importers/csv_importer.py:14](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/csv_importer.py:14)；行 14
- [ser_lib/data/importers/emotiontalk.py:14](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/emotiontalk.py:14)；行 14
- [ser_lib/data/importers/esd.py:13](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/esd.py:13)；行 13
- [ser_lib/data/importers/folder.py:13](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/folder.py:13)；行 13
- [ser_lib/data/importers/jsonl_importer.py:15](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/jsonl_importer.py:15)；行 15
- [ser_lib/data/importers/ravdess.py:13](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/ravdess.py:13)；行 13

| class/function/method | 定义行 | 职责说明（源码 docstring） |
| --- | --- | --- |
| `ImportPreview` | [ser_lib/data/importers/base.py:32](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/base.py:32) | ``scan()`` 结果；所有问题只通过统一 Diagnostic 表达。 |
| `ImportPreview.error_count(self) -> int` | [ser_lib/data/importers/base.py:41](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/base.py:41) |  |
| `ImportPreview.warning_count(self) -> int` | [ser_lib/data/importers/base.py:45](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/base.py:45) |  |
| `ImportPreview.info_count(self) -> int` | [ser_lib/data/importers/base.py:49](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/base.py:49) |  |
| `ImportPreview.ok(self) -> bool` | [ser_lib/data/importers/base.py:53](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/base.py:53) |  |
| `ImportPreview.format_errors(self, *, limit: int=10) -> str` | [ser_lib/data/importers/base.py:56](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/base.py:56) | 为异常消息生成紧凑的人类可读错误摘要。 |
| `ImportPreview.summary(self) -> dict[str, Any]` | [ser_lib/data/importers/base.py:66](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/base.py:66) | 返回单轨、JSON-safe 的预览摘要。 |
| `ImportTask` | [ser_lib/data/importers/base.py:80](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/base.py:80) | Importer ``scan``/``convert`` 的共享生命周期、进度和取消适配器。 |
| `ImportTask.__init__(self, importer_id: str, operation: ImportOperation, *, source: Path, destination: Path \| None=None, event_callback: EventCallback \| None=None, cancellation: CancellationCheck \| None=None, event_context: EventContext \| None=None) -> None` | [ser_lib/data/importers/base.py:83](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/base.py:83) |  |
| `ImportTask.stage(self) -> str` | [ser_lib/data/importers/base.py:105](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/base.py:105) |  |
| `ImportTask._emit(self, event: LifecycleEvent \| ProgressEvent) -> None` | [ser_lib/data/importers/base.py:108](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/base.py:108) |  |
| `ImportTask._base_details(self) -> dict[str, Any]` | [ser_lib/data/importers/base.py:112](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/base.py:112) |  |
| `ImportTask.__enter__(self) -> 'ImportTask'` | [ser_lib/data/importers/base.py:119](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/base.py:119) |  |
| `ImportTask.__exit__(self, exc_type: type[BaseException] \| None, exc: BaseException \| None, traceback: object) -> Literal[False]` | [ser_lib/data/importers/base.py:139](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/base.py:139) |  |
| `ImportTask.check(self) -> None` | [ser_lib/data/importers/base.py:162](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/base.py:162) |  |
| `ImportTask.update_details(self, **details: Any) -> None` | [ser_lib/data/importers/base.py:166](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/base.py:166) |  |
| `ImportTask.progress(self, completed: int, total: int \| None, *, message: str='', details: Mapping[str, Any] \| None=None) -> None` | [ser_lib/data/importers/base.py:169](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/base.py:169) |  |
| `DatasetImporter` | [ser_lib/data/importers/base.py:196](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/base.py:196) | 领域/公开定义 |
| `DatasetImporter.scan(self, source: Path, config: Mapping[str, Any], *, event_callback: EventCallback \| None=None, cancellation: CancellationCheck \| None=None, event_context: EventContext \| None=None) -> ImportPreview` | [ser_lib/data/importers/base.py:199](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/base.py:199) |  |
| `DatasetImporter.convert(self, source: Path, destination: Path, config: Mapping[str, Any], *, event_callback: EventCallback \| None=None, cancellation: CancellationCheck \| None=None, event_context: EventContext \| None=None) -> DatasetManifest` | [ser_lib/data/importers/base.py:210](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/base.py:210) |  |

### ser_lib/data/importers/casia.py

处理：**拆分**。目标：`原路径 + ser_lib/config/importers.py`。理由：算法/组件注册保留，内嵌用户 schema 中央化。

直接 import 消费者（含测试；从公共包重导入的间接消费者还需沿 D/C 展开）：

- [scripts/prepare_casia.py:8](D:/projects/Speech-Emotion-Recognition/scripts/prepare_casia.py:8)；行 8
- [ser_lib/data/importers/__init__.py:6](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/__init__.py:6)；行 6

| class/function/method | 定义行 | 职责说明（源码 docstring） |
| --- | --- | --- |
| `CasiaImportConfig` | [ser_lib/data/importers/casia.py:37](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/casia.py:37) | 领域/公开定义 |
| `CasiaImporter` | [ser_lib/data/importers/casia.py:43](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/casia.py:43) | 领域/公开定义 |
| `CasiaImporter.scan(self, source: Path, config: Mapping[str, Any], *, event_callback: EventCallback \| None=None, cancellation: CancellationCheck \| None=None, event_context: EventContext \| None=None) -> ImportPreview` | [ser_lib/data/importers/casia.py:52](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/casia.py:52) |  |
| `CasiaImporter.convert(self, source: Path, destination: Path, config: Mapping[str, Any], *, event_callback: EventCallback \| None=None, cancellation: CancellationCheck \| None=None, event_context: EventContext \| None=None) -> DatasetManifest` | [ser_lib/data/importers/casia.py:138](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/casia.py:138) |  |

### ser_lib/data/importers/crema_d.py

处理：**拆分**。目标：`原路径 + ser_lib/config/importers.py`。理由：算法/组件注册保留，内嵌用户 schema 中央化。

直接 import 消费者（含测试；从公共包重导入的间接消费者还需沿 D/C 展开）：

- [ser_lib/data/importers/__init__.py:9](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/__init__.py:9)；行 9
- [tests/test_crema_d_importer.py:9](D:/projects/Speech-Emotion-Recognition/tests/test_crema_d_importer.py:9)；行 9

| class/function/method | 定义行 | 职责说明（源码 docstring） |
| --- | --- | --- |
| `CremaDImportConfig` | [ser_lib/data/importers/crema_d.py:39](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/crema_d.py:39) | 领域/公开定义 |
| `_read_demographics(path: Path, encoding: str) -> dict[str, dict[str, Any]]` | [ser_lib/data/importers/crema_d.py:48](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/crema_d.py:48) | 见实现；私有辅助 |
| `_speaker_splits(configured: dict[str, list[str]] \| None, speakers: set[str], demographics: Mapping[str, Mapping[str, Any]]) -> dict[str, list[str]]` | [ser_lib/data/importers/crema_d.py:73](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/crema_d.py:73) | 见实现；私有辅助 |
| `CremaDImporter` | [ser_lib/data/importers/crema_d.py:94](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/crema_d.py:94) | 领域/公开定义 |
| `CremaDImporter.scan(self, source: Path, config: Mapping[str, Any], *, event_callback: EventCallback \| None=None, cancellation: CancellationCheck \| None=None, event_context: EventContext \| None=None) -> ImportPreview` | [ser_lib/data/importers/crema_d.py:103](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/crema_d.py:103) |  |
| `CremaDImporter.convert(self, source: Path, destination: Path, config: Mapping[str, Any], *, event_callback: EventCallback \| None=None, cancellation: CancellationCheck \| None=None, event_context: EventContext \| None=None) -> DatasetManifest` | [ser_lib/data/importers/crema_d.py:230](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/crema_d.py:230) |  |

### ser_lib/data/importers/csemotions.py

处理：**拆分**。目标：`原路径 + ser_lib/config/importers.py`。理由：算法/组件注册保留，内嵌用户 schema 中央化。

直接 import 消费者（含测试；从公共包重导入的间接消费者还需沿 D/C 展开）：

- [ser_lib/data/importers/__init__.py:8](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/__init__.py:8)；行 8
- [ser_lib/data/importers/crema_d.py:15](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/crema_d.py:15)；行 15
- [ser_lib/data/importers/emotiontalk.py:15](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/emotiontalk.py:15)；行 15
- [ser_lib/data/importers/esd.py:14](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/esd.py:14)；行 14
- [tests/test_csemotions_importer.py:9](D:/projects/Speech-Emotion-Recognition/tests/test_csemotions_importer.py:9)；行 9

| class/function/method | 定义行 | 职责说明（源码 docstring） |
| --- | --- | --- |
| `CsemotionsImportConfig` | [ser_lib/data/importers/csemotions.py:34](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/csemotions.py:34) | 领域/公开定义 |
| `_gender(speaker: str) -> str` | [ser_lib/data/importers/csemotions.py:43](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/csemotions.py:43) | 见实现；私有辅助 |
| `_automatic_speaker_splits(speakers: set[str]) -> dict[str, list[str]]` | [ser_lib/data/importers/csemotions.py:52](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/csemotions.py:52) | 见实现；私有辅助 |
| `_validate_speaker_splits(configured: dict[str, list[str]] \| None, speakers: set[str]) -> dict[str, list[str]]` | [ser_lib/data/importers/csemotions.py:79](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/csemotions.py:79) | 见实现；私有辅助 |
| `CsemotionsImporter` | [ser_lib/data/importers/csemotions.py:100](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/csemotions.py:100) | 领域/公开定义 |
| `CsemotionsImporter.scan(self, source: Path, config: Mapping[str, Any], *, event_callback: EventCallback \| None=None, cancellation: CancellationCheck \| None=None, event_context: EventContext \| None=None) -> ImportPreview` | [ser_lib/data/importers/csemotions.py:109](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/csemotions.py:109) |  |
| `CsemotionsImporter.convert(self, source: Path, destination: Path, config: Mapping[str, Any], *, event_callback: EventCallback \| None=None, cancellation: CancellationCheck \| None=None, event_context: EventContext \| None=None) -> DatasetManifest` | [ser_lib/data/importers/csemotions.py:235](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/csemotions.py:235) |  |

### ser_lib/data/importers/csv_importer.py

处理：**拆分**。目标：`原路径 + ser_lib/config/importers.py`。理由：算法/组件注册保留，内嵌用户 schema 中央化。

直接 import 消费者（含测试；从公共包重导入的间接消费者还需沿 D/C 展开）：

- [ser_lib/data/importers/__init__.py:7](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/__init__.py:7)；行 7

| class/function/method | 定义行 | 职责说明（源码 docstring） |
| --- | --- | --- |
| `CsvImportConfig` | [ser_lib/data/importers/csv_importer.py:20](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/csv_importer.py:20) | 领域/公开定义 |
| `CsvImporter` | [ser_lib/data/importers/csv_importer.py:34](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/csv_importer.py:34) | 领域/公开定义 |
| `CsvImporter.scan(self, source: Path, config: Mapping[str, Any], *, event_callback: EventCallback \| None=None, cancellation: CancellationCheck \| None=None, event_context: EventContext \| None=None) -> ImportPreview` | [ser_lib/data/importers/csv_importer.py:43](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/csv_importer.py:43) |  |
| `CsvImporter.convert(self, source: Path, destination: Path, config: Mapping[str, Any], *, event_callback: EventCallback \| None=None, cancellation: CancellationCheck \| None=None, event_context: EventContext \| None=None) -> DatasetManifest` | [ser_lib/data/importers/csv_importer.py:202](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/csv_importer.py:202) |  |
| `_is_int(value: str) -> bool` | [ser_lib/data/importers/csv_importer.py:235](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/csv_importer.py:235) | 见实现；私有辅助 |

### ser_lib/data/importers/emotiontalk.py

处理：**拆分**。目标：`原路径 + ser_lib/config/importers.py`。理由：算法/组件注册保留，内嵌用户 schema 中央化。

直接 import 消费者（含测试；从公共包重导入的间接消费者还需沿 D/C 展开）：

- [ser_lib/data/importers/__init__.py:11](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/__init__.py:11)；行 11
- [tests/test_emotiontalk_importer.py:9](D:/projects/Speech-Emotion-Recognition/tests/test_emotiontalk_importer.py:9)；行 9

| class/function/method | 定义行 | 职责说明（源码 docstring） |
| --- | --- | --- |
| `EmotionTalkImportConfig` | [ser_lib/data/importers/emotiontalk.py:31](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/emotiontalk.py:31) | 领域/公开定义 |
| `_automatic_splits(speakers: set[str]) -> dict[str, list[str]]` | [ser_lib/data/importers/emotiontalk.py:41](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/emotiontalk.py:41) | 见实现；私有辅助 |
| `_safe_relative_audio(raw: Any) -> Path \| None` | [ser_lib/data/importers/emotiontalk.py:55](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/emotiontalk.py:55) | 见实现；私有辅助 |
| `EmotionTalkImporter` | [ser_lib/data/importers/emotiontalk.py:64](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/emotiontalk.py:64) | 领域/公开定义 |
| `EmotionTalkImporter.scan(self, source: Path, config: Mapping[str, Any], *, event_callback: EventCallback \| None=None, cancellation: CancellationCheck \| None=None, event_context: EventContext \| None=None) -> ImportPreview` | [ser_lib/data/importers/emotiontalk.py:73](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/emotiontalk.py:73) |  |
| `EmotionTalkImporter.convert(self, source: Path, destination: Path, config: Mapping[str, Any], *, event_callback: EventCallback \| None=None, cancellation: CancellationCheck \| None=None, event_context: EventContext \| None=None) -> DatasetManifest` | [ser_lib/data/importers/emotiontalk.py:209](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/emotiontalk.py:209) |  |

### ser_lib/data/importers/esd.py

处理：**拆分**。目标：`原路径 + ser_lib/config/importers.py`。理由：算法/组件注册保留，内嵌用户 schema 中央化。

直接 import 消费者（含测试；从公共包重导入的间接消费者还需沿 D/C 展开）：

- [ser_lib/data/importers/__init__.py:10](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/__init__.py:10)；行 10
- [tests/test_esd_importer.py:8](D:/projects/Speech-Emotion-Recognition/tests/test_esd_importer.py:8)；行 8

| class/function/method | 定义行 | 职责说明（源码 docstring） |
| --- | --- | --- |
| `EsdImportConfig` | [ser_lib/data/importers/esd.py:23](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/esd.py:23) | 领域/公开定义 |
| `_language(speaker: str) -> str \| None` | [ser_lib/data/importers/esd.py:31](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/esd.py:31) | 见实现；私有辅助 |
| `_speaker_splits(configured: dict[str, list[str]] \| None, speakers: set[str]) -> dict[str, list[str]]` | [ser_lib/data/importers/esd.py:39](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/esd.py:39) | 见实现；私有辅助 |
| `_transcripts(path: Path, encoding: str) -> tuple[dict[str, str], list[Diagnostic]]` | [ser_lib/data/importers/esd.py:53](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/esd.py:53) | 见实现；私有辅助 |
| `EsdImporter` | [ser_lib/data/importers/esd.py:85](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/esd.py:85) | 领域/公开定义 |
| `EsdImporter.scan(self, source: Path, config: Mapping[str, Any], *, event_callback: EventCallback \| None=None, cancellation: CancellationCheck \| None=None, event_context: EventContext \| None=None) -> ImportPreview` | [ser_lib/data/importers/esd.py:94](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/esd.py:94) |  |
| `EsdImporter.convert(self, source: Path, destination: Path, config: Mapping[str, Any], *, event_callback: EventCallback \| None=None, cancellation: CancellationCheck \| None=None, event_context: EventContext \| None=None) -> DatasetManifest` | [ser_lib/data/importers/esd.py:207](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/esd.py:207) |  |

### ser_lib/data/importers/folder.py

处理：**拆分**。目标：`原路径 + ser_lib/config/importers.py`。理由：算法/组件注册保留，内嵌用户 schema 中央化。

直接 import 消费者（含测试；从公共包重导入的间接消费者还需沿 D/C 展开）：

- [ser_lib/data/importers/__init__.py:12](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/__init__.py:12)；行 12
- [ser_lib/data/importers/casia.py:14](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/casia.py:14)；行 14

| class/function/method | 定义行 | 职责说明（源码 docstring） |
| --- | --- | --- |
| `FolderImportConfig` | [ser_lib/data/importers/folder.py:21](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/folder.py:21) | 领域/公开定义 |
| `FolderImportConfig._normalize_ext(cls, value: list[str]) -> list[str]` | [ser_lib/data/importers/folder.py:32](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/folder.py:32) |  |
| `FolderImporter` | [ser_lib/data/importers/folder.py:42](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/folder.py:42) | 领域/公开定义 |
| `FolderImporter.scan(self, source: Path, config: Mapping[str, Any], *, event_callback: EventCallback \| None=None, cancellation: CancellationCheck \| None=None, event_context: EventContext \| None=None) -> ImportPreview` | [ser_lib/data/importers/folder.py:51](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/folder.py:51) |  |
| `FolderImporter.convert(self, source: Path, destination: Path, config: Mapping[str, Any], *, event_callback: EventCallback \| None=None, cancellation: CancellationCheck \| None=None, event_context: EventContext \| None=None) -> DatasetManifest` | [ser_lib/data/importers/folder.py:176](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/folder.py:176) |  |

### ser_lib/data/importers/jsonl_importer.py

处理：**拆分**。目标：`原路径 + ser_lib/config/importers.py`。理由：算法/组件注册保留，内嵌用户 schema 中央化。

直接 import 消费者（含测试；从公共包重导入的间接消费者还需沿 D/C 展开）：

- [ser_lib/data/importers/__init__.py:13](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/__init__.py:13)；行 13

| class/function/method | 定义行 | 职责说明（源码 docstring） |
| --- | --- | --- |
| `JsonlImportConfig` | [ser_lib/data/importers/jsonl_importer.py:31](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/jsonl_importer.py:31) | 领域/公开定义 |
| `normalize_raw_record(raw: Mapping[str, Any], *, index: int, uid_prefix: str) -> dict[str, Any]` | [ser_lib/data/importers/jsonl_importer.py:37](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/jsonl_importer.py:37) | 领域/公开定义 |
| `normalize_raw_records(raw_records: list[Mapping[str, Any]], *, uid_prefix: str) -> list[AudioRecord]` | [ser_lib/data/importers/jsonl_importer.py:62](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/jsonl_importer.py:62) | 领域/公开定义 |
| `JsonlImporter` | [ser_lib/data/importers/jsonl_importer.py:75](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/jsonl_importer.py:75) | 领域/公开定义 |
| `JsonlImporter.scan(self, source: Path, config: Mapping[str, Any], *, event_callback: EventCallback \| None=None, cancellation: CancellationCheck \| None=None, event_context: EventContext \| None=None) -> ImportPreview` | [ser_lib/data/importers/jsonl_importer.py:84](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/jsonl_importer.py:84) |  |
| `JsonlImporter.convert(self, source: Path, destination: Path, config: Mapping[str, Any], *, event_callback: EventCallback \| None=None, cancellation: CancellationCheck \| None=None, event_context: EventContext \| None=None) -> DatasetManifest` | [ser_lib/data/importers/jsonl_importer.py:178](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/jsonl_importer.py:178) |  |

### ser_lib/data/importers/ravdess.py

处理：**拆分**。目标：`原路径 + ser_lib/config/importers.py`。理由：算法/组件注册保留，内嵌用户 schema 中央化。

直接 import 消费者（含测试；从公共包重导入的间接消费者还需沿 D/C 展开）：

- [ser_lib/data/importers/__init__.py:14](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/__init__.py:14)；行 14
- [tests/test_ravdess_and_benchmark.py:12](D:/projects/Speech-Emotion-Recognition/tests/test_ravdess_and_benchmark.py:12)；行 12

| class/function/method | 定义行 | 职责说明（源码 docstring） |
| --- | --- | --- |
| `RavdessImportConfig` | [ser_lib/data/importers/ravdess.py:30](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/ravdess.py:30) | 领域/公开定义 |
| `RavdessImporter` | [ser_lib/data/importers/ravdess.py:36](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/ravdess.py:36) | 领域/公开定义 |
| `RavdessImporter.scan(self, source: Path, config: Mapping[str, Any], *, event_callback: EventCallback \| None=None, cancellation: CancellationCheck \| None=None, event_context: EventContext \| None=None) -> ImportPreview` | [ser_lib/data/importers/ravdess.py:45](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/ravdess.py:45) |  |
| `RavdessImporter.convert(self, source: Path, destination: Path, config: Mapping[str, Any], *, event_callback: EventCallback \| None=None, cancellation: CancellationCheck \| None=None, event_context: EventContext \| None=None) -> DatasetManifest` | [ser_lib/data/importers/ravdess.py:182](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/ravdess.py:182) |  |

### ser_lib/data/manifest.py

处理：**瘦身**。目标：`原路径 + ser_lib/data/migrations.py`。理由：持久化元数据保留，迁移逻辑按领域。

直接 import 消费者（含测试；从公共包重导入的间接消费者还需沿 D/C 展开）：

- [scripts/prepare_casia.py:13](D:/projects/Speech-Emotion-Recognition/scripts/prepare_casia.py:13)；行 13
- [ser_lib/data/__init__.py:29](D:/projects/Speech-Emotion-Recognition/ser_lib/data/__init__.py:29)；行 29
- [ser_lib/data/editor.py:21](D:/projects/Speech-Emotion-Recognition/ser_lib/data/editor.py:21)；行 21
- [ser_lib/data/fingerprint.py:11](D:/projects/Speech-Emotion-Recognition/ser_lib/data/fingerprint.py:11)；行 11
- [ser_lib/data/history.py:25](D:/projects/Speech-Emotion-Recognition/ser_lib/data/history.py:25)；行 25
- [ser_lib/data/importers/_conversion.py:13](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/_conversion.py:13)；行 13
- [ser_lib/data/importers/base.py:24](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/base.py:24)；行 24
- [ser_lib/data/importers/casia.py:15](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/casia.py:15)；行 15
- [ser_lib/data/importers/crema_d.py:16](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/crema_d.py:16)；行 16
- [ser_lib/data/importers/csemotions.py:15](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/csemotions.py:15)；行 15
- [ser_lib/data/importers/csv_importer.py:15](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/csv_importer.py:15)；行 15
- [ser_lib/data/importers/emotiontalk.py:16](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/emotiontalk.py:16)；行 16
- [ser_lib/data/importers/esd.py:15](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/esd.py:15)；行 15
- [ser_lib/data/importers/folder.py:14](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/folder.py:14)；行 14
- [ser_lib/data/importers/jsonl_importer.py:16](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/jsonl_importer.py:16)；行 16
- [ser_lib/data/importers/ravdess.py:14](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/ravdess.py:14)；行 14
- [ser_lib/data/profiling.py:11](D:/projects/Speech-Emotion-Recognition/ser_lib/data/profiling.py:11)；行 11
- [ser_lib/data/query.py:11](D:/projects/Speech-Emotion-Recognition/ser_lib/data/query.py:11)；行 11
- [ser_lib/engine/validation.py:12](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/validation.py:12)；行 12
- [ser_lib/inference/batch.py:20](D:/projects/Speech-Emotion-Recognition/ser_lib/inference/batch.py:20)；行 20
- [ser_lib/services/datasets.py:19](D:/projects/Speech-Emotion-Recognition/ser_lib/services/datasets.py:19)；行 19
- [ser_lib/services/inference.py:10](D:/projects/Speech-Emotion-Recognition/ser_lib/services/inference.py:10)；行 10
- [tests/test_manifest.py:6](D:/projects/Speech-Emotion-Recognition/tests/test_manifest.py:6)；行 6

| class/function/method | 定义行 | 职责说明（源码 docstring） |
| --- | --- | --- |
| `ManifestMeta` | [ser_lib/data/manifest.py:31](D:/projects/Speech-Emotion-Recognition/ser_lib/data/manifest.py:31) | dataset.yaml 元信息。 |
| `ManifestMeta.num_classes(self) -> int` | [ser_lib/data/manifest.py:42](D:/projects/Speech-Emotion-Recognition/ser_lib/data/manifest.py:42) |  |
| `parse_record(raw: Mapping[str, Any], *, source: Path, line_number: int \| None=None) -> AudioRecord` | [ser_lib/data/manifest.py:46](D:/projects/Speech-Emotion-Recognition/ser_lib/data/manifest.py:46) | 解析并校验一条标准 manifest 记录。 |
| `write_jsonl(records: list[AudioRecord], path: Path) -> None` | [ser_lib/data/manifest.py:95](D:/projects/Speech-Emotion-Recognition/ser_lib/data/manifest.py:95) | 把记录写入标准 JSONL（音频路径保留为给定形式）。 |
| `read_jsonl(path: Path) -> list[AudioRecord]` | [ser_lib/data/manifest.py:122](D:/projects/Speech-Emotion-Recognition/ser_lib/data/manifest.py:122) | 读取标准 JSONL manifest。文件内 uid 必须唯一。 |
| `load_meta(yaml_path: Path) -> ManifestMeta` | [ser_lib/data/manifest.py:153](D:/projects/Speech-Emotion-Recognition/ser_lib/data/manifest.py:153) | 加载、read-time migrate 并校验 dataset.yaml。 |
| `DatasetManifest` | [ser_lib/data/manifest.py:217](D:/projects/Speech-Emotion-Recognition/ser_lib/data/manifest.py:217) | 标准数据集 manifest：迭代记录、按 split 获取、轻量统计。 |
| `DatasetManifest.__init__(self, meta: ManifestMeta, records: list[AudioRecord], record_splits: dict[str, str] \| None=None) -> None` | [ser_lib/data/manifest.py:220](D:/projects/Speech-Emotion-Recognition/ser_lib/data/manifest.py:220) |  |
| `DatasetManifest.load(cls, yaml_path: Path \| str) -> 'DatasetManifest'` | [ser_lib/data/manifest.py:227](D:/projects/Speech-Emotion-Recognition/ser_lib/data/manifest.py:227) | 加载 dataset.yaml 及其全部 splits。 |
| `DatasetManifest.resolve_audio_path(self, record: AudioRecord) -> Path` | [ser_lib/data/manifest.py:247](D:/projects/Speech-Emotion-Recognition/ser_lib/data/manifest.py:247) |  |
| `DatasetManifest.iter_records(self, split: str \| None=None) -> Iterator[AudioRecord]` | [ser_lib/data/manifest.py:253](D:/projects/Speech-Emotion-Recognition/ser_lib/data/manifest.py:253) |  |
| `DatasetManifest.get_records(self, split: str \| None=None) -> list[AudioRecord]` | [ser_lib/data/manifest.py:258](D:/projects/Speech-Emotion-Recognition/ser_lib/data/manifest.py:258) |  |
| `DatasetManifest.resolved_records(self, split: str \| None=None) -> list[AudioRecord]` | [ser_lib/data/manifest.py:261](D:/projects/Speech-Emotion-Recognition/ser_lib/data/manifest.py:261) |  |
| `DatasetManifest.stats(self) -> dict[str, Any]` | [ser_lib/data/manifest.py:278](D:/projects/Speech-Emotion-Recognition/ser_lib/data/manifest.py:278) |  |
| `DatasetManifest.write(self, yaml_path: Path \| None=None) -> None` | [ser_lib/data/manifest.py:294](D:/projects/Speech-Emotion-Recognition/ser_lib/data/manifest.py:294) |  |
| `_validate_label_range(records: list[AudioRecord], meta: ManifestMeta, yaml_path: Path) -> None` | [ser_lib/data/manifest.py:330](D:/projects/Speech-Emotion-Recognition/ser_lib/data/manifest.py:330) | 见实现；私有辅助 |

### ser_lib/data/pipeline.py

处理：**保留**。目标：`原路径`。理由：实际为 SER 数据/执行基础，无确认的页面专属职责；更新被迁移 import。

直接 import 消费者（含测试；从公共包重导入的间接消费者还需沿 D/C 展开）：

- [scripts/smoke_train_epoch.py:24](D:/projects/Speech-Emotion-Recognition/scripts/smoke_train_epoch.py:24)；行 24
- [ser_lib/artifacts/loader.py:28](D:/projects/Speech-Emotion-Recognition/ser_lib/artifacts/loader.py:28)；行 28
- [ser_lib/data/__init__.py:30](D:/projects/Speech-Emotion-Recognition/ser_lib/data/__init__.py:30)；行 30
- [ser_lib/data/dataset.py:18](D:/projects/Speech-Emotion-Recognition/ser_lib/data/dataset.py:18)；行 18
- [ser_lib/engine/config.py:18](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/config.py:18)；行 18, 114
- [ser_lib/engine/validation.py:13](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/validation.py:13)；行 13
- [ser_lib/inference/offline.py:10](D:/projects/Speech-Emotion-Recognition/ser_lib/inference/offline.py:10)；行 10
- [tests/test_audio_pipeline.py:14](D:/projects/Speech-Emotion-Recognition/tests/test_audio_pipeline.py:14)；行 14
- [tests/test_cache.py:9](D:/projects/Speech-Emotion-Recognition/tests/test_cache.py:9)；行 9
- [tests/test_model_engine.py:13](D:/projects/Speech-Emotion-Recognition/tests/test_model_engine.py:13)；行 13

| class/function/method | 定义行 | 职责说明（源码 docstring） |
| --- | --- | --- |
| `SamplePipeline` | [ser_lib/data/pipeline.py:38](D:/projects/Speech-Emotion-Recognition/ser_lib/data/pipeline.py:38) | 单样本处理流水线。 |
| `SamplePipeline.__init__(self, representation: Representation, waveform_transforms: nn.Module \| None=None, feature_transforms: nn.Module \| None=None, *, validate_contract: bool=True) -> None` | [ser_lib/data/pipeline.py:48](D:/projects/Speech-Emotion-Recognition/ser_lib/data/pipeline.py:48) |  |
| `SamplePipeline.output_specs(self) -> dict[str, TensorSpec]` | [ser_lib/data/pipeline.py:63](D:/projects/Speech-Emotion-Recognition/ser_lib/data/pipeline.py:63) | 输出形状契约（与 representation 一致）。 |
| `SamplePipeline.forward(self, audio: AudioData, record: AudioRecord) -> SERSample` | [ser_lib/data/pipeline.py:67](D:/projects/Speech-Emotion-Recognition/ser_lib/data/pipeline.py:67) |  |
| `SamplePipeline.__call__(self, audio: AudioData, record: AudioRecord) -> SERSample` | [ser_lib/data/pipeline.py:132](D:/projects/Speech-Emotion-Recognition/ser_lib/data/pipeline.py:132) |  |
| `build_representation(component: Mapping[str, Any] \| str) -> Representation` | [ser_lib/data/pipeline.py:141](D:/projects/Speech-Emotion-Recognition/ser_lib/data/pipeline.py:141) | 根据组件配置从注册表构建表示。 |
| `_factory_accepts(factory: type, param: str) -> bool` | [ser_lib/data/pipeline.py:154](D:/projects/Speech-Emotion-Recognition/ser_lib/data/pipeline.py:154) | 见实现；私有辅助 |
| `_build_waveform_transforms(configs: Sequence[ComponentConfig], *, sample_rate: int, allow_random: bool) -> WaveformTransformPipeline \| None` | [ser_lib/data/pipeline.py:162](D:/projects/Speech-Emotion-Recognition/ser_lib/data/pipeline.py:162) | 构建波形 transform 流水线。 |
| `_waveform_transform_entry(name: str)` | [ser_lib/data/pipeline.py:200](D:/projects/Speech-Emotion-Recognition/ser_lib/data/pipeline.py:200) | 见实现；私有辅助 |
| `_build_feature_transforms(configs: Sequence[ComponentConfig], *, specs: dict[str, TensorSpec], allow_random: bool) -> FeatureTransformPipeline \| None` | [ser_lib/data/pipeline.py:213](D:/projects/Speech-Emotion-Recognition/ser_lib/data/pipeline.py:213) | 构建特征 transform 流水线，并做构建期 layout 兼容性校验。 |
| `build_pipeline(data_config: DataConfig, *, train: bool, validate_contract: bool=True) -> SamplePipeline` | [ser_lib/data/pipeline.py:241](D:/projects/Speech-Emotion-Recognition/ser_lib/data/pipeline.py:241) | 从 DataConfig 构建 SamplePipeline（训练与推理共享同一入口）。 |
| `build_components(data_config: DataConfig, *, train: bool, validate_contract: bool=True) -> tuple['AudioLoader', SamplePipeline]` | [ser_lib/data/pipeline.py:285](D:/projects/Speech-Emotion-Recognition/ser_lib/data/pipeline.py:285) | 构建 (AudioLoader, SamplePipeline) 组件对。 |

### ser_lib/data/profiling.py

处理：**瘦身**。目标：`ser_lib/data/profiling.py`。理由：保留分布/时长统计，合并 summary/profile 重复，去展示派生字段。

直接 import 消费者（含测试；从公共包重导入的间接消费者还需沿 D/C 展开）：

- [ser_lib/data/__init__.py:31](D:/projects/Speech-Emotion-Recognition/ser_lib/data/__init__.py:31)；行 31
- [ser_lib/services/datasets.py:20](D:/projects/Speech-Emotion-Recognition/ser_lib/services/datasets.py:20)；行 20

| class/function/method | 定义行 | 职责说明（源码 docstring） |
| --- | --- | --- |
| `AudioProbeFailure` | [ser_lib/data/profiling.py:15](D:/projects/Speech-Emotion-Recognition/ser_lib/data/profiling.py:15) | 领域/公开定义 |
| `DurationHistogramBin` | [ser_lib/data/profiling.py:23](D:/projects/Speech-Emotion-Recognition/ser_lib/data/profiling.py:23) | 领域/公开定义 |
| `DurationHistogramBin.to_dict(self) -> dict[str, Any]` | [ser_lib/data/profiling.py:28](D:/projects/Speech-Emotion-Recognition/ser_lib/data/profiling.py:28) |  |
| `DatasetAudioProfile` | [ser_lib/data/profiling.py:33](D:/projects/Speech-Emotion-Recognition/ser_lib/data/profiling.py:33) | 领域/公开定义 |
| `DatasetAudioProfile.to_dict(self) -> dict[str, Any]` | [ser_lib/data/profiling.py:52](D:/projects/Speech-Emotion-Recognition/ser_lib/data/profiling.py:52) |  |
| `DatasetSummary` | [ser_lib/data/profiling.py:57](D:/projects/Speech-Emotion-Recognition/ser_lib/data/profiling.py:57) | 供 CLI/Web 列表和详情首屏直接消费的数据集摘要。 |
| `DatasetSummary.to_dict(self) -> dict[str, Any]` | [ser_lib/data/profiling.py:78](D:/projects/Speech-Emotion-Recognition/ser_lib/data/profiling.py:78) |  |
| `DatasetProfile` | [ser_lib/data/profiling.py:83](D:/projects/Speech-Emotion-Recognition/ser_lib/data/profiling.py:83) | 供可视化数据集分析页使用的详细、JSON-safe profile。 |
| `DatasetProfile.to_dict(self) -> dict[str, Any]` | [ser_lib/data/profiling.py:100](D:/projects/Speech-Emotion-Recognition/ser_lib/data/profiling.py:100) |  |
| `_percentile(sorted_values: list[float], quantile: float) -> float \| None` | [ser_lib/data/profiling.py:122](D:/projects/Speech-Emotion-Recognition/ser_lib/data/profiling.py:122) | 见实现；私有辅助 |
| `_duration_histogram(durations: list[float], *, bins: int) -> tuple[DurationHistogramBin, ...]` | [ser_lib/data/profiling.py:134](D:/projects/Speech-Emotion-Recognition/ser_lib/data/profiling.py:134) | 见实现；私有辅助 |
| `_label_display_name(label_id: int, metadata: dict[str, Any]) -> str` | [ser_lib/data/profiling.py:162](D:/projects/Speech-Emotion-Recognition/ser_lib/data/profiling.py:162) | 见实现；私有辅助 |
| `profile_manifest_audio(manifest: DatasetManifest \| Path \| str, *, split: str \| None=None, fail_fast: bool=False, histogram_bins: int=10, event_callback: EventCallback \| None=None, cancellation: CancellationCheck \| None=None) -> DatasetAudioProfile` | [ser_lib/data/profiling.py:173](D:/projects/Speech-Emotion-Recognition/ser_lib/data/profiling.py:173) | 使用音频 header 统计时长、分位数、采样率、声道和损坏/缺失文件。 |
| `summarize_manifest(manifest: DatasetManifest \| Path \| str, *, include_audio_profile: bool=False, fail_fast: bool=False, event_callback: EventCallback \| None=None, cancellation: CancellationCheck \| None=None) -> DatasetSummary` | [ser_lib/data/profiling.py:260](D:/projects/Speech-Emotion-Recognition/ser_lib/data/profiling.py:260) | 构建稳定、JSON-safe 的轻量数据集摘要。 |
| `profile_dataset(manifest: DatasetManifest \| Path \| str, *, include_audio: bool=False, fail_fast: bool=False, histogram_bins: int=10, event_callback: EventCallback \| None=None, cancellation: CancellationCheck \| None=None) -> DatasetProfile` | [ser_lib/data/profiling.py:331](D:/projects/Speech-Emotion-Recognition/ser_lib/data/profiling.py:331) | 构建数据集分析页所需的详细 profile。 |

### ser_lib/data/query.py

处理：**重构**。目标：`ser_lib/data/query.py:iter_records`。理由：删除 RecordView/RecordPage/_to_view，保留记录过滤。

直接 import 消费者（含测试；从公共包重导入的间接消费者还需沿 D/C 展开）：

- [ser_lib/data/__init__.py:35](D:/projects/Speech-Emotion-Recognition/ser_lib/data/__init__.py:35)；行 35
- [ser_lib/services/datasets.py:28](D:/projects/Speech-Emotion-Recognition/ser_lib/services/datasets.py:28)；行 28

| class/function/method | 定义行 | 职责说明（源码 docstring） |
| --- | --- | --- |
| `RecordView` | [ser_lib/data/query.py:16](D:/projects/Speech-Emotion-Recognition/ser_lib/data/query.py:16) | 不泄漏内部 ``AudioRecord`` 的 JSON-safe 浏览视图。 |
| `RecordView.to_dict(self) -> dict[str, Any]` | [ser_lib/data/query.py:29](D:/projects/Speech-Emotion-Recognition/ser_lib/data/query.py:29) |  |
| `RecordPage` | [ser_lib/data/query.py:34](D:/projects/Speech-Emotion-Recognition/ser_lib/data/query.py:34) | 领域/公开定义 |
| `RecordPage.has_more(self) -> bool` | [ser_lib/data/query.py:41](D:/projects/Speech-Emotion-Recognition/ser_lib/data/query.py:41) |  |
| `RecordPage.to_dict(self) -> dict[str, Any]` | [ser_lib/data/query.py:44](D:/projects/Speech-Emotion-Recognition/ser_lib/data/query.py:44) |  |
| `query_records(manifest: DatasetManifest \| Path \| str, *, split: str \| None=None, label_id: int \| None=None, speaker_id: str \| None=None, keyword: str \| None=None, offset: int=0, limit: int=50) -> RecordPage` | [ser_lib/data/query.py:54](D:/projects/Speech-Emotion-Recognition/ser_lib/data/query.py:54) | 过滤标准 manifest 并返回稳定分页结果。 |
| `_to_view(record: AudioRecord, split: str) -> RecordView` | [ser_lib/data/query.py:115](D:/projects/Speech-Emotion-Recognition/ser_lib/data/query.py:115) | 见实现；私有辅助 |
| `_matches_keyword(record: AudioRecord, keyword: str) -> bool` | [ser_lib/data/query.py:129](D:/projects/Speech-Emotion-Recognition/ser_lib/data/query.py:129) | 见实现；私有辅助 |
| `_json_safe_mapping(value: Mapping[str, Any]) -> dict[str, Any]` | [ser_lib/data/query.py:142](D:/projects/Speech-Emotion-Recognition/ser_lib/data/query.py:142) | 见实现；私有辅助 |
| `_json_safe(value: Any) -> Any` | [ser_lib/data/query.py:146](D:/projects/Speech-Emotion-Recognition/ser_lib/data/query.py:146) | 见实现；私有辅助 |

### ser_lib/data/registry.py

处理：**保留**。目标：`原路径`。理由：实际为 SER 数据/执行基础，无确认的页面专属职责；更新被迁移 import。

直接 import 消费者（含测试；从公共包重导入的间接消费者还需沿 D/C 展开）：

- [ser_lib/catalog.py:19](D:/projects/Speech-Emotion-Recognition/ser_lib/catalog.py:19)；行 19
- [ser_lib/data/__init__.py:36](D:/projects/Speech-Emotion-Recognition/ser_lib/data/__init__.py:36)；行 36
- [ser_lib/data/cache.py:11](D:/projects/Speech-Emotion-Recognition/ser_lib/data/cache.py:11)；行 11
- [ser_lib/data/importers/__init__.py:15](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/__init__.py:15)；行 15
- [ser_lib/data/importers/base.py:25](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/base.py:25)；行 25
- [ser_lib/data/importers/casia.py:16](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/casia.py:16)；行 16
- [ser_lib/data/importers/crema_d.py:17](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/crema_d.py:17)；行 17
- [ser_lib/data/importers/csemotions.py:16](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/csemotions.py:16)；行 16
- [ser_lib/data/importers/csv_importer.py:16](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/csv_importer.py:16)；行 16
- [ser_lib/data/importers/emotiontalk.py:17](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/emotiontalk.py:17)；行 17
- [ser_lib/data/importers/esd.py:16](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/esd.py:16)；行 16
- [ser_lib/data/importers/folder.py:15](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/folder.py:15)；行 15
- [ser_lib/data/importers/jsonl_importer.py:17](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/jsonl_importer.py:17)；行 17
- [ser_lib/data/importers/ravdess.py:15](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/ravdess.py:15)；行 15
- [ser_lib/data/pipeline.py:20](D:/projects/Speech-Emotion-Recognition/ser_lib/data/pipeline.py:20)；行 20
- [ser_lib/data/representations/__init__.py:5](D:/projects/Speech-Emotion-Recognition/ser_lib/data/representations/__init__.py:5)；行 5
- [ser_lib/data/representations/acoustic.py:26](D:/projects/Speech-Emotion-Recognition/ser_lib/data/representations/acoustic.py:26)；行 26
- [ser_lib/data/representations/base.py:15](D:/projects/Speech-Emotion-Recognition/ser_lib/data/representations/base.py:15)；行 15
- [ser_lib/data/representations/composite.py:16](D:/projects/Speech-Emotion-Recognition/ser_lib/data/representations/composite.py:16)；行 16
- [ser_lib/data/representations/spectral.py:15](D:/projects/Speech-Emotion-Recognition/ser_lib/data/representations/spectral.py:15)；行 15
- [ser_lib/data/representations/waveform.py:7](D:/projects/Speech-Emotion-Recognition/ser_lib/data/representations/waveform.py:7)；行 7
- [ser_lib/data/transforms/__init__.py:5](D:/projects/Speech-Emotion-Recognition/ser_lib/data/transforms/__init__.py:5)；行 5
- [ser_lib/data/transforms/feature.py:14](D:/projects/Speech-Emotion-Recognition/ser_lib/data/transforms/feature.py:14)；行 14
- [ser_lib/data/transforms/waveform.py:21](D:/projects/Speech-Emotion-Recognition/ser_lib/data/transforms/waveform.py:21)；行 21
- [tests/test_cache.py:10](D:/projects/Speech-Emotion-Recognition/tests/test_cache.py:10)；行 10
- [tests/test_registry_config.py:5](D:/projects/Speech-Emotion-Recognition/tests/test_registry_config.py:5)；行 5

| class/function/method | 定义行 | 职责说明（源码 docstring） |
| --- | --- | --- |
| `ComponentDescriptor` | [ser_lib/data/registry.py:32](D:/projects/Speech-Emotion-Recognition/ser_lib/data/registry.py:32) | 统一的公开组件描述信息。 |
| `ComponentDescriptor.to_json_safe(self) -> dict[str, Any]` | [ser_lib/data/registry.py:52](D:/projects/Speech-Emotion-Recognition/ser_lib/data/registry.py:52) | 序列化为 JSON 安全结构；``torch.dtype`` 转换为稳定字符串。 |
| `_dtype_to_str(dtype: torch.dtype) -> str` | [ser_lib/data/registry.py:68](D:/projects/Speech-Emotion-Recognition/ser_lib/data/registry.py:68) | 见实现；私有辅助 |
| `_spec_to_json_safe(spec: TensorSpec) -> dict[str, Any]` | [ser_lib/data/registry.py:82](D:/projects/Speech-Emotion-Recognition/ser_lib/data/registry.py:82) | 见实现；私有辅助 |
| `_specs_to_json_safe(specs: Mapping[str, TensorSpec] \| None) -> dict[str, Any] \| None` | [ser_lib/data/registry.py:92](D:/projects/Speech-Emotion-Recognition/ser_lib/data/registry.py:92) | 见实现；私有辅助 |
| `ComponentEntry` | [ser_lib/data/registry.py:99](D:/projects/Speech-Emotion-Recognition/ser_lib/data/registry.py:99) | 注册表中的一条组件记录。 |
| `Registry` | [ser_lib/data/registry.py:109](D:/projects/Speech-Emotion-Recognition/ser_lib/data/registry.py:109) | 命名空间隔离的组件注册表。 |
| `Registry.__init__(self) -> None` | [ser_lib/data/registry.py:112](D:/projects/Speech-Emotion-Recognition/ser_lib/data/registry.py:112) |  |
| `Registry.register(self, *, namespace: str, name: str, factory: Callable[..., Any], config_model: type[BaseModel] \| None=None, descriptor: ComponentDescriptor \| None=None, replace: bool=False) -> None` | [ser_lib/data/registry.py:115](D:/projects/Speech-Emotion-Recognition/ser_lib/data/registry.py:115) |  |
| `Registry.get_entry(self, namespace: str, name: str) -> ComponentEntry` | [ser_lib/data/registry.py:155](D:/projects/Speech-Emotion-Recognition/ser_lib/data/registry.py:155) |  |
| `Registry.create(self, namespace: str, component: Mapping[str, Any] \| str, **overrides: Any) -> Any` | [ser_lib/data/registry.py:165](D:/projects/Speech-Emotion-Recognition/ser_lib/data/registry.py:165) |  |
| `Registry.names(self, namespace: str) -> list[str]` | [ser_lib/data/registry.py:215](D:/projects/Speech-Emotion-Recognition/ser_lib/data/registry.py:215) |  |
| `Registry.descriptors(self, namespace: str, *, statuses: tuple[str, ...] \| None=PUBLIC_STATUSES) -> list[ComponentDescriptor]` | [ser_lib/data/registry.py:218](D:/projects/Speech-Emotion-Recognition/ser_lib/data/registry.py:218) | 枚举组件；``statuses=None`` 时返回包括 optional/unavailable 在内的全部项。 |
| `Registry.json_safe_descriptors(self, namespace: str, *, statuses: tuple[str, ...] \| None=PUBLIC_STATUSES) -> list[dict[str, Any]]` | [ser_lib/data/registry.py:234](D:/projects/Speech-Emotion-Recognition/ser_lib/data/registry.py:234) |  |

### ser_lib/data/representations/__init__.py

处理：**瘦身**。目标：`原路径`。理由：更新 config/退役包装导出及内置注册顺序，不改变算法。

直接 import 消费者（含测试；从公共包重导入的间接消费者还需沿 D/C 展开）：

- [ser_lib/data/__init__.py:37](D:/projects/Speech-Emotion-Recognition/ser_lib/data/__init__.py:37)；行 37

| class/function/method | 定义行 | 职责说明（源码 docstring） |
| --- | --- | --- |
| `register_representations(registry: Registry \| None=None) -> None` | [ser_lib/data/representations/__init__.py:47](D:/projects/Speech-Emotion-Recognition/ser_lib/data/representations/__init__.py:47) | 把全部表示注册到注册表（默认注册到 default_registry）。 |

### ser_lib/data/representations/acoustic.py

处理：**拆分**。目标：`原路径 + ser_lib/config/representations.py`。理由：算法/组件注册保留，内嵌用户 schema 中央化。

直接 import 消费者（含测试；从公共包重导入的间接消费者还需沿 D/C 展开）：

- [ser_lib/data/representations/__init__.py:6](D:/projects/Speech-Emotion-Recognition/ser_lib/data/representations/__init__.py:6)；行 6

| class/function/method | 定义行 | 职责说明（源码 docstring） |
| --- | --- | --- |
| `AcousticFeaturesConfig` | [ser_lib/data/representations/acoustic.py:57](D:/projects/Speech-Emotion-Recognition/ser_lib/data/representations/acoustic.py:57) | AcousticFeatures 参数。 |
| `AcousticFeaturesConfig._validate(self) -> 'AcousticFeaturesConfig'` | [ser_lib/data/representations/acoustic.py:74](D:/projects/Speech-Emotion-Recognition/ser_lib/data/representations/acoustic.py:74) |  |
| `_FrameFeature` | [ser_lib/data/representations/acoustic.py:82](D:/projects/Speech-Emotion-Recognition/ser_lib/data/representations/acoustic.py:82) | 帧级特征基类：输入 [1, T]，输出 [T_f] 或 [T_f, D]。 |
| `_FrameFeature.compute(self, waveform: torch.Tensor) -> torch.Tensor` | [ser_lib/data/representations/acoustic.py:85](D:/projects/Speech-Emotion-Recognition/ser_lib/data/representations/acoustic.py:85) |  |
| `_PitchF0` | [ser_lib/data/representations/acoustic.py:89](D:/projects/Speech-Emotion-Recognition/ser_lib/data/representations/acoustic.py:89) | 见实现；私有辅助 |
| `_PitchF0.__init__(self, sample_rate: int, hop_length: int) -> None` | [ser_lib/data/representations/acoustic.py:90](D:/projects/Speech-Emotion-Recognition/ser_lib/data/representations/acoustic.py:90) |  |
| `_PitchF0.compute(self, waveform: torch.Tensor) -> torch.Tensor` | [ser_lib/data/representations/acoustic.py:95](D:/projects/Speech-Emotion-Recognition/ser_lib/data/representations/acoustic.py:95) |  |
| `_RMS` | [ser_lib/data/representations/acoustic.py:108](D:/projects/Speech-Emotion-Recognition/ser_lib/data/representations/acoustic.py:108) | 见实现；私有辅助 |
| `_RMS.__init__(self, win_length: int, hop_length: int) -> None` | [ser_lib/data/representations/acoustic.py:109](D:/projects/Speech-Emotion-Recognition/ser_lib/data/representations/acoustic.py:109) |  |
| `_RMS.compute(self, waveform: torch.Tensor) -> torch.Tensor` | [ser_lib/data/representations/acoustic.py:115](D:/projects/Speech-Emotion-Recognition/ser_lib/data/representations/acoustic.py:115) |  |
| `_ZeroCrossingRate` | [ser_lib/data/representations/acoustic.py:121](D:/projects/Speech-Emotion-Recognition/ser_lib/data/representations/acoustic.py:121) | 见实现；私有辅助 |
| `_ZeroCrossingRate.__init__(self, win_length: int, hop_length: int) -> None` | [ser_lib/data/representations/acoustic.py:122](D:/projects/Speech-Emotion-Recognition/ser_lib/data/representations/acoustic.py:122) |  |
| `_ZeroCrossingRate.compute(self, waveform: torch.Tensor) -> torch.Tensor` | [ser_lib/data/representations/acoustic.py:128](D:/projects/Speech-Emotion-Recognition/ser_lib/data/representations/acoustic.py:128) |  |
| `_StftFeature` | [ser_lib/data/representations/acoustic.py:136](D:/projects/Speech-Emotion-Recognition/ser_lib/data/representations/acoustic.py:136) | 基于 STFT 幅度谱的帧级特征公共基类。 |
| `_StftFeature.__init__(self, sample_rate: int, n_fft: int, hop_length: int) -> None` | [ser_lib/data/representations/acoustic.py:139](D:/projects/Speech-Emotion-Recognition/ser_lib/data/representations/acoustic.py:139) |  |
| `_StftFeature._magnitude(self, waveform: torch.Tensor) -> torch.Tensor` | [ser_lib/data/representations/acoustic.py:148](D:/projects/Speech-Emotion-Recognition/ser_lib/data/representations/acoustic.py:148) |  |
| `_StftFeature.compute(self, waveform: torch.Tensor) -> torch.Tensor` | [ser_lib/data/representations/acoustic.py:157](D:/projects/Speech-Emotion-Recognition/ser_lib/data/representations/acoustic.py:157) |  |
| `_SpectralCentroid` | [ser_lib/data/representations/acoustic.py:161](D:/projects/Speech-Emotion-Recognition/ser_lib/data/representations/acoustic.py:161) | 见实现；私有辅助 |
| `_SpectralCentroid.compute(self, waveform: torch.Tensor) -> torch.Tensor` | [ser_lib/data/representations/acoustic.py:162](D:/projects/Speech-Emotion-Recognition/ser_lib/data/representations/acoustic.py:162) |  |
| `_SpectralRolloff` | [ser_lib/data/representations/acoustic.py:169](D:/projects/Speech-Emotion-Recognition/ser_lib/data/representations/acoustic.py:169) | 见实现；私有辅助 |
| `_SpectralRolloff.__init__(self, sample_rate: int, n_fft: int, hop_length: int, roll_percent: float) -> None` | [ser_lib/data/representations/acoustic.py:170](D:/projects/Speech-Emotion-Recognition/ser_lib/data/representations/acoustic.py:170) |  |
| `_SpectralRolloff.compute(self, waveform: torch.Tensor) -> torch.Tensor` | [ser_lib/data/representations/acoustic.py:175](D:/projects/Speech-Emotion-Recognition/ser_lib/data/representations/acoustic.py:175) |  |
| `_SpectralFlatness` | [ser_lib/data/representations/acoustic.py:185](D:/projects/Speech-Emotion-Recognition/ser_lib/data/representations/acoustic.py:185) | 见实现；私有辅助 |
| `_SpectralFlatness.compute(self, waveform: torch.Tensor) -> torch.Tensor` | [ser_lib/data/representations/acoustic.py:186](D:/projects/Speech-Emotion-Recognition/ser_lib/data/representations/acoustic.py:186) |  |
| `_SpectralFlux` | [ser_lib/data/representations/acoustic.py:194](D:/projects/Speech-Emotion-Recognition/ser_lib/data/representations/acoustic.py:194) | 见实现；私有辅助 |
| `_SpectralFlux.compute(self, waveform: torch.Tensor) -> torch.Tensor` | [ser_lib/data/representations/acoustic.py:195](D:/projects/Speech-Emotion-Recognition/ser_lib/data/representations/acoustic.py:195) |  |
| `_Delta` | [ser_lib/data/representations/acoustic.py:202](D:/projects/Speech-Emotion-Recognition/ser_lib/data/representations/acoustic.py:202) | 对波形按 legacy 语义计算一阶/二阶差分并拼接，输出 [T, 3]。 |
| `_Delta.__init__(self, win_length: int) -> None` | [ser_lib/data/representations/acoustic.py:205](D:/projects/Speech-Emotion-Recognition/ser_lib/data/representations/acoustic.py:205) |  |
| `_Delta.compute(self, waveform: torch.Tensor) -> torch.Tensor` | [ser_lib/data/representations/acoustic.py:209](D:/projects/Speech-Emotion-Recognition/ser_lib/data/representations/acoustic.py:209) |  |
| `_JitterShimmerHNR` | [ser_lib/data/representations/acoustic.py:218](D:/projects/Speech-Emotion-Recognition/ser_lib/data/representations/acoustic.py:218) | utterance 级音质向量 [3] = (jitter, shimmer, hnr)。 |
| `_JitterShimmerHNR.compute(self, waveform: torch.Tensor, pitch: torch.Tensor) -> torch.Tensor` | [ser_lib/data/representations/acoustic.py:225](D:/projects/Speech-Emotion-Recognition/ser_lib/data/representations/acoustic.py:225) |  |
| `AcousticFeatures` | [ser_lib/data/representations/acoustic.py:236](D:/projects/Speech-Emotion-Recognition/ser_lib/data/representations/acoustic.py:236) | 声学帧级/全局特征表示（详见模块 docstring 的输出协议）。 |
| `AcousticFeatures.__init__(self, **params) -> None` | [ser_lib/data/representations/acoustic.py:248](D:/projects/Speech-Emotion-Recognition/ser_lib/data/representations/acoustic.py:248) |  |
| `AcousticFeatures.output_specs(self) -> dict[str, TensorSpec]` | [ser_lib/data/representations/acoustic.py:288](D:/projects/Speech-Emotion-Recognition/ser_lib/data/representations/acoustic.py:288) |  |
| `AcousticFeatures._frame_names(self) -> list[str]` | [ser_lib/data/representations/acoustic.py:300](D:/projects/Speech-Emotion-Recognition/ser_lib/data/representations/acoustic.py:300) |  |
| `AcousticFeatures.forward(self, audio: AudioData) -> RepresentationOutput` | [ser_lib/data/representations/acoustic.py:303](D:/projects/Speech-Emotion-Recognition/ser_lib/data/representations/acoustic.py:303) |  |

### ser_lib/data/representations/base.py

处理：**保留**。目标：`原路径`。理由：实际为 SER 数据/执行基础，无确认的页面专属职责；更新被迁移 import。

直接 import 消费者（含测试；从公共包重导入的间接消费者还需沿 D/C 展开）：

- [ser_lib/data/cache.py:12](D:/projects/Speech-Emotion-Recognition/ser_lib/data/cache.py:12)；行 12
- [ser_lib/data/pipeline.py:21](D:/projects/Speech-Emotion-Recognition/ser_lib/data/pipeline.py:21)；行 21
- [ser_lib/data/representations/__init__.py:10](D:/projects/Speech-Emotion-Recognition/ser_lib/data/representations/__init__.py:10)；行 10
- [ser_lib/data/representations/acoustic.py:27](D:/projects/Speech-Emotion-Recognition/ser_lib/data/representations/acoustic.py:27)；行 27
- [ser_lib/data/representations/composite.py:17](D:/projects/Speech-Emotion-Recognition/ser_lib/data/representations/composite.py:17)；行 17
- [ser_lib/data/representations/spectral.py:16](D:/projects/Speech-Emotion-Recognition/ser_lib/data/representations/spectral.py:16)；行 16
- [ser_lib/data/representations/waveform.py:8](D:/projects/Speech-Emotion-Recognition/ser_lib/data/representations/waveform.py:8)；行 8
- [tests/test_cache.py:11](D:/projects/Speech-Emotion-Recognition/tests/test_cache.py:11)；行 11

| class/function/method | 定义行 | 职责说明（源码 docstring） |
| --- | --- | --- |
| `Representation` | [ser_lib/data/representations/base.py:19](D:/projects/Speech-Emotion-Recognition/ser_lib/data/representations/base.py:19) | 输入表示的抽象基类。 |
| `Representation.output_specs(self) -> dict[str, TensorSpec]` | [ser_lib/data/representations/base.py:33](D:/projects/Speech-Emotion-Recognition/ser_lib/data/representations/base.py:33) | 声明输出 tensor 的形状契约。 |
| `Representation.forward(self, audio: AudioData) -> RepresentationOutput` | [ser_lib/data/representations/base.py:38](D:/projects/Speech-Emotion-Recognition/ser_lib/data/representations/base.py:38) | 把 AudioData 转换为标准表示输出。 |
| `Representation._require_mono(self, audio: AudioData) -> None` | [ser_lib/data/representations/base.py:42](D:/projects/Speech-Emotion-Recognition/ser_lib/data/representations/base.py:42) | 第一版表示要求单声道输入（``[1, T]``）。 |
| `Representation._require_sample_rate(self, audio: AudioData) -> None` | [ser_lib/data/representations/base.py:54](D:/projects/Speech-Emotion-Recognition/ser_lib/data/representations/base.py:54) | 校验配置采样率与 Loader 输出一致，不得静默以不同采样率计算。 |

### ser_lib/data/representations/composite.py

处理：**拆分**。目标：`原路径 + ser_lib/config/representations.py`。理由：算法/组件注册保留，内嵌用户 schema 中央化。

直接 import 消费者（含测试；从公共包重导入的间接消费者还需沿 D/C 展开）：

- [ser_lib/data/representations/__init__.py:11](D:/projects/Speech-Emotion-Recognition/ser_lib/data/representations/__init__.py:11)；行 11

| class/function/method | 定义行 | 职责说明（源码 docstring） |
| --- | --- | --- |
| `CompositeConfig` | [ser_lib/data/representations/composite.py:25](D:/projects/Speech-Emotion-Recognition/ser_lib/data/representations/composite.py:25) | 组合表示参数：``{key: 组件配置}``。 |
| `CompositeRepresentation` | [ser_lib/data/representations/composite.py:33](D:/projects/Speech-Emotion-Recognition/ser_lib/data/representations/composite.py:33) | 组合多个子表示。 |
| `CompositeRepresentation.__init__(self, **params: Any) -> None` | [ser_lib/data/representations/composite.py:55](D:/projects/Speech-Emotion-Recognition/ser_lib/data/representations/composite.py:55) |  |
| `CompositeRepresentation.output_specs(self) -> dict[str, TensorSpec]` | [ser_lib/data/representations/composite.py:96](D:/projects/Speech-Emotion-Recognition/ser_lib/data/representations/composite.py:96) |  |
| `CompositeRepresentation.forward(self, audio: AudioData) -> RepresentationOutput` | [ser_lib/data/representations/composite.py:102](D:/projects/Speech-Emotion-Recognition/ser_lib/data/representations/composite.py:102) |  |

### ser_lib/data/representations/spectral.py

处理：**拆分**。目标：`原路径 + ser_lib/config/representations.py`。理由：算法/组件注册保留，内嵌用户 schema 中央化。

直接 import 消费者（含测试；从公共包重导入的间接消费者还需沿 D/C 展开）：

- [scripts/smoke_train_epoch.py:25](D:/projects/Speech-Emotion-Recognition/scripts/smoke_train_epoch.py:25)；行 25
- [ser_lib/data/representations/__init__.py:15](D:/projects/Speech-Emotion-Recognition/ser_lib/data/representations/__init__.py:15)；行 15
- [tests/test_audio_pipeline.py:15](D:/projects/Speech-Emotion-Recognition/tests/test_audio_pipeline.py:15)；行 15
- [tests/test_model_engine.py:14](D:/projects/Speech-Emotion-Recognition/tests/test_model_engine.py:14)；行 14

| class/function/method | 定义行 | 职责说明（源码 docstring） |
| --- | --- | --- |
| `SpectralConfigBase` | [ser_lib/data/representations/spectral.py:25](D:/projects/Speech-Emotion-Recognition/ser_lib/data/representations/spectral.py:25) | 谱图类表示的公共参数（对齐 torchaudio 默认值）。 |
| `SpectralConfigBase._validate_params(self) -> 'SpectralConfigBase'` | [ser_lib/data/representations/spectral.py:40](D:/projects/Speech-Emotion-Recognition/ser_lib/data/representations/spectral.py:40) |  |
| `SpectrogramConfig` | [ser_lib/data/representations/spectral.py:49](D:/projects/Speech-Emotion-Recognition/ser_lib/data/representations/spectral.py:49) | 线性谱图参数。power 固定为 2.0（幅度谱使用 power=None 的场景第一版不暴露）。 |
| `MelConfig` | [ser_lib/data/representations/spectral.py:55](D:/projects/Speech-Emotion-Recognition/ser_lib/data/representations/spectral.py:55) | Mel 谱公共参数。 |
| `LogMelConfig` | [ser_lib/data/representations/spectral.py:62](D:/projects/Speech-Emotion-Recognition/ser_lib/data/representations/spectral.py:62) | Log-Mel 参数。``top_db`` 传给 AmplitudeToDB。 |
| `MFCCConfig` | [ser_lib/data/representations/spectral.py:68](D:/projects/Speech-Emotion-Recognition/ser_lib/data/representations/spectral.py:68) | MFCC 参数；Mel 参数封装在组件内部。 |
| `MFCCConfig._validate_mfcc(self) -> 'MFCCConfig'` | [ser_lib/data/representations/spectral.py:78](D:/projects/Speech-Emotion-Recognition/ser_lib/data/representations/spectral.py:78) |  |
| `_SpectralRepresentationBase` | [ser_lib/data/representations/spectral.py:84](D:/projects/Speech-Emotion-Recognition/ser_lib/data/representations/spectral.py:84) | 谱图类表示公共实现：单声道输入 + 采样率校验 + ``features`` 输出。 |
| `_SpectralRepresentationBase.__init__(self, config: SpectralConfigBase) -> None` | [ser_lib/data/representations/spectral.py:87](D:/projects/Speech-Emotion-Recognition/ser_lib/data/representations/spectral.py:87) |  |
| `_SpectralRepresentationBase.output_specs(self) -> dict[str, TensorSpec]` | [ser_lib/data/representations/spectral.py:93](D:/projects/Speech-Emotion-Recognition/ser_lib/data/representations/spectral.py:93) |  |
| `_SpectralRepresentationBase._feature_dim(self) -> int` | [ser_lib/data/representations/spectral.py:102](D:/projects/Speech-Emotion-Recognition/ser_lib/data/representations/spectral.py:102) |  |
| `_SpectralRepresentationBase._to_output(self, features: 'T.Tensor', audio: AudioData) -> RepresentationOutput` | [ser_lib/data/representations/spectral.py:105](D:/projects/Speech-Emotion-Recognition/ser_lib/data/representations/spectral.py:105) |  |
| `SpectrogramRepresentation` | [ser_lib/data/representations/spectral.py:122](D:/projects/Speech-Emotion-Recognition/ser_lib/data/representations/spectral.py:122) | 线性幅度谱（power 谱）。 |
| `SpectrogramRepresentation.__init__(self, **params) -> None` | [ser_lib/data/representations/spectral.py:133](D:/projects/Speech-Emotion-Recognition/ser_lib/data/representations/spectral.py:133) |  |
| `SpectrogramRepresentation._feature_dim(self) -> int` | [ser_lib/data/representations/spectral.py:149](D:/projects/Speech-Emotion-Recognition/ser_lib/data/representations/spectral.py:149) |  |
| `SpectrogramRepresentation.forward(self, audio: AudioData) -> RepresentationOutput` | [ser_lib/data/representations/spectral.py:152](D:/projects/Speech-Emotion-Recognition/ser_lib/data/representations/spectral.py:152) |  |
| `MelSpectrogramRepresentation` | [ser_lib/data/representations/spectral.py:158](D:/projects/Speech-Emotion-Recognition/ser_lib/data/representations/spectral.py:158) | Mel 谱。 |
| `MelSpectrogramRepresentation.__init__(self, **params) -> None` | [ser_lib/data/representations/spectral.py:169](D:/projects/Speech-Emotion-Recognition/ser_lib/data/representations/spectral.py:169) |  |
| `MelSpectrogramRepresentation._feature_dim(self) -> int` | [ser_lib/data/representations/spectral.py:186](D:/projects/Speech-Emotion-Recognition/ser_lib/data/representations/spectral.py:186) |  |
| `MelSpectrogramRepresentation.forward(self, audio: AudioData) -> RepresentationOutput` | [ser_lib/data/representations/spectral.py:189](D:/projects/Speech-Emotion-Recognition/ser_lib/data/representations/spectral.py:189) |  |
| `LogMelRepresentation` | [ser_lib/data/representations/spectral.py:195](D:/projects/Speech-Emotion-Recognition/ser_lib/data/representations/spectral.py:195) | Log-Mel 谱：Mel 谱后接 AmplitudeToDB。 |
| `LogMelRepresentation.__init__(self, **params) -> None` | [ser_lib/data/representations/spectral.py:206](D:/projects/Speech-Emotion-Recognition/ser_lib/data/representations/spectral.py:206) |  |
| `LogMelRepresentation._feature_dim(self) -> int` | [ser_lib/data/representations/spectral.py:224](D:/projects/Speech-Emotion-Recognition/ser_lib/data/representations/spectral.py:224) |  |
| `LogMelRepresentation.forward(self, audio: AudioData) -> RepresentationOutput` | [ser_lib/data/representations/spectral.py:227](D:/projects/Speech-Emotion-Recognition/ser_lib/data/representations/spectral.py:227) |  |
| `MFCCRepresentation` | [ser_lib/data/representations/spectral.py:234](D:/projects/Speech-Emotion-Recognition/ser_lib/data/representations/spectral.py:234) | MFCC：Mel 参数转换逻辑封装在组件内部。 |
| `MFCCRepresentation.__init__(self, **params) -> None` | [ser_lib/data/representations/spectral.py:245](D:/projects/Speech-Emotion-Recognition/ser_lib/data/representations/spectral.py:245) |  |
| `MFCCRepresentation._feature_dim(self) -> int` | [ser_lib/data/representations/spectral.py:267](D:/projects/Speech-Emotion-Recognition/ser_lib/data/representations/spectral.py:267) |  |
| `MFCCRepresentation.forward(self, audio: AudioData) -> RepresentationOutput` | [ser_lib/data/representations/spectral.py:270](D:/projects/Speech-Emotion-Recognition/ser_lib/data/representations/spectral.py:270) |  |

### ser_lib/data/representations/waveform.py

处理：**拆分**。目标：`原路径 + ser_lib/config/representations.py`。理由：算法/组件注册保留，内嵌用户 schema 中央化。

直接 import 消费者（含测试；从公共包重导入的间接消费者还需沿 D/C 展开）：

- [ser_lib/data/representations/__init__.py:25](D:/projects/Speech-Emotion-Recognition/ser_lib/data/representations/__init__.py:25)；行 25
- [tests/test_audio_pipeline.py:16](D:/projects/Speech-Emotion-Recognition/tests/test_audio_pipeline.py:16)；行 16

| class/function/method | 定义行 | 职责说明（源码 docstring） |
| --- | --- | --- |
| `RawWaveformConfig` | [ser_lib/data/representations/waveform.py:17](D:/projects/Speech-Emotion-Recognition/ser_lib/data/representations/waveform.py:17) | RawWaveform 无参数；保留空模型用于 schema 生成与未知参数报错。 |
| `RawWaveform` | [ser_lib/data/representations/waveform.py:23](D:/projects/Speech-Emotion-Recognition/ser_lib/data/representations/waveform.py:23) | 原始波形表示。 |
| `RawWaveform.__init__(self) -> None` | [ser_lib/data/representations/waveform.py:39](D:/projects/Speech-Emotion-Recognition/ser_lib/data/representations/waveform.py:39) |  |
| `RawWaveform.output_specs(self) -> dict[str, TensorSpec]` | [ser_lib/data/representations/waveform.py:44](D:/projects/Speech-Emotion-Recognition/ser_lib/data/representations/waveform.py:44) |  |
| `RawWaveform.forward(self, audio: AudioData) -> RepresentationOutput` | [ser_lib/data/representations/waveform.py:47](D:/projects/Speech-Emotion-Recognition/ser_lib/data/representations/waveform.py:47) |  |

### ser_lib/data/transforms/__init__.py

处理：**瘦身**。目标：`原路径`。理由：更新 config/退役包装导出及内置注册顺序，不改变算法。

直接 import 消费者（含测试；从公共包重导入的间接消费者还需沿 D/C 展开）：

- [ser_lib/data/__init__.py:38](D:/projects/Speech-Emotion-Recognition/ser_lib/data/__init__.py:38)；行 38

| class/function/method | 定义行 | 职责说明（源码 docstring） |
| --- | --- | --- |
| `register_transforms(registry: Registry \| None=None) -> None` | [ser_lib/data/transforms/__init__.py:31](D:/projects/Speech-Emotion-Recognition/ser_lib/data/transforms/__init__.py:31) | 注册波形级与特征级 transform（默认注册到 default_registry）。 |

### ser_lib/data/transforms/base.py

处理：**保留**。目标：`原路径`。理由：实际为 SER 数据/执行基础，无确认的页面专属职责；更新被迁移 import。

直接 import 消费者（含测试；从公共包重导入的间接消费者还需沿 D/C 展开）：

- [ser_lib/data/pipeline.py:22](D:/projects/Speech-Emotion-Recognition/ser_lib/data/pipeline.py:22)；行 22
- [ser_lib/data/transforms/__init__.py:6](D:/projects/Speech-Emotion-Recognition/ser_lib/data/transforms/__init__.py:6)；行 6
- [ser_lib/data/transforms/waveform.py:22](D:/projects/Speech-Emotion-Recognition/ser_lib/data/transforms/waveform.py:22)；行 22

| class/function/method | 定义行 | 职责说明（源码 docstring） |
| --- | --- | --- |
| `RandomApply` | [ser_lib/data/transforms/base.py:18](D:/projects/Speech-Emotion-Recognition/ser_lib/data/transforms/base.py:18) | 以概率 ``probability`` 应用内部 transform，否则原样返回。 |
| `RandomApply.__init__(self, transform: nn.Module, probability: float) -> None` | [ser_lib/data/transforms/base.py:26](D:/projects/Speech-Emotion-Recognition/ser_lib/data/transforms/base.py:26) |  |
| `RandomApply.forward(self, *args, **kwargs)` | [ser_lib/data/transforms/base.py:37](D:/projects/Speech-Emotion-Recognition/ser_lib/data/transforms/base.py:37) |  |
| `RandomApply.extra_repr(self) -> str` | [ser_lib/data/transforms/base.py:42](D:/projects/Speech-Emotion-Recognition/ser_lib/data/transforms/base.py:42) |  |
| `WaveformTransformPipeline` | [ser_lib/data/transforms/base.py:46](D:/projects/Speech-Emotion-Recognition/ser_lib/data/transforms/base.py:46) | 波形级 transform 流水线：``[C, T] -> [C, T]``。 |
| `WaveformTransformPipeline.__init__(self, transforms: Sequence[nn.Module] \| None=None) -> None` | [ser_lib/data/transforms/base.py:49](D:/projects/Speech-Emotion-Recognition/ser_lib/data/transforms/base.py:49) |  |
| `WaveformTransformPipeline.forward(self, waveform: torch.Tensor) -> torch.Tensor` | [ser_lib/data/transforms/base.py:53](D:/projects/Speech-Emotion-Recognition/ser_lib/data/transforms/base.py:53) |  |
| `FeatureTransformPipeline` | [ser_lib/data/transforms/base.py:68](D:/projects/Speech-Emotion-Recognition/ser_lib/data/transforms/base.py:68) | 特征级 transform 流水线：对每个输入 key 应用全部 transform。 |
| `FeatureTransformPipeline.__init__(self, transforms: Sequence[nn.Module] \| None=None) -> None` | [ser_lib/data/transforms/base.py:75](D:/projects/Speech-Emotion-Recognition/ser_lib/data/transforms/base.py:75) |  |
| `FeatureTransformPipeline.forward(self, inputs: dict[str, torch.Tensor]) -> dict[str, torch.Tensor]` | [ser_lib/data/transforms/base.py:79](D:/projects/Speech-Emotion-Recognition/ser_lib/data/transforms/base.py:79) |  |
| `validate_feature_transform_layouts(transform: nn.Module, specs: dict[str, TensorSpec]) -> None` | [ser_lib/data/transforms/base.py:100](D:/projects/Speech-Emotion-Recognition/ser_lib/data/transforms/base.py:100) | 构建期校验特征 transform 与输入 layout 兼容（验证优先于运行）。 |

### ser_lib/data/transforms/feature.py

处理：**拆分**。目标：`原路径 + ser_lib/config/transforms.py`。理由：算法/组件注册保留，内嵌用户 schema 中央化。

直接 import 消费者（含测试；从公共包重导入的间接消费者还需沿 D/C 展开）：

- [ser_lib/data/transforms/__init__.py:12](D:/projects/Speech-Emotion-Recognition/ser_lib/data/transforms/__init__.py:12)；行 12

| class/function/method | 定义行 | 职责说明（源码 docstring） |
| --- | --- | --- |
| `SpecMaskingConfig` | [ser_lib/data/transforms/feature.py:17](D:/projects/Speech-Emotion-Recognition/ser_lib/data/transforms/feature.py:17) | SpecAugment 掩码参数。 |
| `SpecMasking` | [ser_lib/data/transforms/feature.py:26](D:/projects/Speech-Emotion-Recognition/ser_lib/data/transforms/feature.py:26) | 时间掩码 + 频率掩码（分别评估触发概率由 RandomApply 包装器决定）。 |
| `SpecMasking.__init__(self, time_mask_param: int=30, freq_mask_param: int=15) -> None` | [ser_lib/data/transforms/feature.py:31](D:/projects/Speech-Emotion-Recognition/ser_lib/data/transforms/feature.py:31) |  |
| `SpecMasking.forward(self, features: torch.Tensor) -> torch.Tensor` | [ser_lib/data/transforms/feature.py:36](D:/projects/Speech-Emotion-Recognition/ser_lib/data/transforms/feature.py:36) |  |

### ser_lib/data/transforms/waveform.py

处理：**拆分**。目标：`原路径 + ser_lib/config/transforms.py`。理由：算法/组件注册保留，内嵌用户 schema 中央化。

直接 import 消费者（含测试；从公共包重导入的间接消费者还需沿 D/C 展开）：

- [ser_lib/data/pipeline.py:201](D:/projects/Speech-Emotion-Recognition/ser_lib/data/pipeline.py:201)；行 201
- [ser_lib/data/transforms/__init__.py:17](D:/projects/Speech-Emotion-Recognition/ser_lib/data/transforms/__init__.py:17)；行 17

| class/function/method | 定义行 | 职责说明（源码 docstring） |
| --- | --- | --- |
| `NormalizeConfig` | [ser_lib/data/transforms/waveform.py:25](D:/projects/Speech-Emotion-Recognition/ser_lib/data/transforms/waveform.py:25) | Normalize 无参数。 |
| `GaussianNoiseConfig` | [ser_lib/data/transforms/waveform.py:31](D:/projects/Speech-Emotion-Recognition/ser_lib/data/transforms/waveform.py:31) | 高斯噪声参数。 |
| `TimeShiftConfig` | [ser_lib/data/transforms/waveform.py:39](D:/projects/Speech-Emotion-Recognition/ser_lib/data/transforms/waveform.py:39) | 时间平移参数。 |
| `VolumeScaleConfig` | [ser_lib/data/transforms/waveform.py:47](D:/projects/Speech-Emotion-Recognition/ser_lib/data/transforms/waveform.py:47) | 音量缩放参数。 |
| `VolumeScaleConfig._validate_range(self) -> 'VolumeScaleConfig'` | [ser_lib/data/transforms/waveform.py:56](D:/projects/Speech-Emotion-Recognition/ser_lib/data/transforms/waveform.py:56) |  |
| `PitchShiftConfig` | [ser_lib/data/transforms/waveform.py:62](D:/projects/Speech-Emotion-Recognition/ser_lib/data/transforms/waveform.py:62) | 音高偏移参数。sample_rate 由 pipeline 构建时按 AudioLoader 配置注入。 |
| `TimeStretchConfig` | [ser_lib/data/transforms/waveform.py:71](D:/projects/Speech-Emotion-Recognition/ser_lib/data/transforms/waveform.py:71) | 时间拉伸参数。 |
| `Normalize` | [ser_lib/data/transforms/waveform.py:79](D:/projects/Speech-Emotion-Recognition/ser_lib/data/transforms/waveform.py:79) | 逐条 waveform 归一化（确定性，零均值单位方差）。 |
| `Normalize.forward(self, waveform: torch.Tensor) -> torch.Tensor` | [ser_lib/data/transforms/waveform.py:85](D:/projects/Speech-Emotion-Recognition/ser_lib/data/transforms/waveform.py:85) |  |
| `AddGaussianNoise` | [ser_lib/data/transforms/waveform.py:90](D:/projects/Speech-Emotion-Recognition/ser_lib/data/transforms/waveform.py:90) | 按目标信噪比注入高斯白噪声。 |
| `AddGaussianNoise.__init__(self, snr_db: float=15.0) -> None` | [ser_lib/data/transforms/waveform.py:93](D:/projects/Speech-Emotion-Recognition/ser_lib/data/transforms/waveform.py:93) |  |
| `AddGaussianNoise.forward(self, waveform: torch.Tensor) -> torch.Tensor` | [ser_lib/data/transforms/waveform.py:97](D:/projects/Speech-Emotion-Recognition/ser_lib/data/transforms/waveform.py:97) |  |
| `TimeShift` | [ser_lib/data/transforms/waveform.py:108](D:/projects/Speech-Emotion-Recognition/ser_lib/data/transforms/waveform.py:108) | 时间平移，越界部分用零填充（输出长度不变）。 |
| `TimeShift.__init__(self, max_ratio: float=0.2) -> None` | [ser_lib/data/transforms/waveform.py:111](D:/projects/Speech-Emotion-Recognition/ser_lib/data/transforms/waveform.py:111) |  |
| `TimeShift.forward(self, waveform: torch.Tensor) -> torch.Tensor` | [ser_lib/data/transforms/waveform.py:115](D:/projects/Speech-Emotion-Recognition/ser_lib/data/transforms/waveform.py:115) |  |
| `VolumeScale` | [ser_lib/data/transforms/waveform.py:128](D:/projects/Speech-Emotion-Recognition/ser_lib/data/transforms/waveform.py:128) | 随机音量缩放，模拟麦克风远近波动。 |
| `VolumeScale.__init__(self, gain_min: float=0.5, gain_max: float=1.5) -> None` | [ser_lib/data/transforms/waveform.py:131](D:/projects/Speech-Emotion-Recognition/ser_lib/data/transforms/waveform.py:131) |  |
| `VolumeScale.forward(self, waveform: torch.Tensor) -> torch.Tensor` | [ser_lib/data/transforms/waveform.py:136](D:/projects/Speech-Emotion-Recognition/ser_lib/data/transforms/waveform.py:136) |  |
| `PitchShift` | [ser_lib/data/transforms/waveform.py:141](D:/projects/Speech-Emotion-Recognition/ser_lib/data/transforms/waveform.py:141) | 音高偏移（半音）。 |
| `PitchShift.__init__(self, sample_rate: int=16000, n_steps: int=4) -> None` | [ser_lib/data/transforms/waveform.py:144](D:/projects/Speech-Emotion-Recognition/ser_lib/data/transforms/waveform.py:144) |  |
| `PitchShift.forward(self, waveform: torch.Tensor) -> torch.Tensor` | [ser_lib/data/transforms/waveform.py:150](D:/projects/Speech-Emotion-Recognition/ser_lib/data/transforms/waveform.py:150) |  |
| `TimeStretch` | [ser_lib/data/transforms/waveform.py:154](D:/projects/Speech-Emotion-Recognition/ser_lib/data/transforms/waveform.py:154) | 时间拉伸（相位声码器；输出长度随 rate 变化）。 |
| `TimeStretch.__init__(self, rate: float=1.2, n_fft: int=1024, hop_length: int=256) -> None` | [ser_lib/data/transforms/waveform.py:157](D:/projects/Speech-Emotion-Recognition/ser_lib/data/transforms/waveform.py:157) |  |
| `TimeStretch.forward(self, waveform: torch.Tensor) -> torch.Tensor` | [ser_lib/data/transforms/waveform.py:166](D:/projects/Speech-Emotion-Recognition/ser_lib/data/transforms/waveform.py:166) |  |

### ser_lib/data/types.py

处理：**保留**。目标：`原路径`。理由：实际为 SER 数据/执行基础，无确认的页面专属职责；更新被迁移 import。

直接 import 消费者（含测试；从公共包重导入的间接消费者还需沿 D/C 展开）：

- [scripts/smoke_train_epoch.py:26](D:/projects/Speech-Emotion-Recognition/scripts/smoke_train_epoch.py:26)；行 26
- [ser_lib/data/__init__.py:39](D:/projects/Speech-Emotion-Recognition/ser_lib/data/__init__.py:39)；行 39
- [ser_lib/data/audio.py:33](D:/projects/Speech-Emotion-Recognition/ser_lib/data/audio.py:33)；行 33
- [ser_lib/data/cache.py:13](D:/projects/Speech-Emotion-Recognition/ser_lib/data/cache.py:13)；行 13
- [ser_lib/data/collate.py:27](D:/projects/Speech-Emotion-Recognition/ser_lib/data/collate.py:27)；行 27
- [ser_lib/data/dataset.py:19](D:/projects/Speech-Emotion-Recognition/ser_lib/data/dataset.py:19)；行 19
- [ser_lib/data/editor.py:22](D:/projects/Speech-Emotion-Recognition/ser_lib/data/editor.py:22)；行 22
- [ser_lib/data/importers/_conversion.py:14](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/_conversion.py:14)；行 14
- [ser_lib/data/importers/base.py:26](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/base.py:26)；行 26
- [ser_lib/data/importers/casia.py:17](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/casia.py:17)；行 17
- [ser_lib/data/importers/crema_d.py:18](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/crema_d.py:18)；行 18
- [ser_lib/data/importers/csemotions.py:17](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/csemotions.py:17)；行 17
- [ser_lib/data/importers/csv_importer.py:17](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/csv_importer.py:17)；行 17
- [ser_lib/data/importers/emotiontalk.py:18](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/emotiontalk.py:18)；行 18
- [ser_lib/data/importers/esd.py:17](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/esd.py:17)；行 17
- [ser_lib/data/importers/folder.py:16](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/folder.py:16)；行 16
- [ser_lib/data/importers/jsonl_importer.py:18](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/jsonl_importer.py:18)；行 18
- [ser_lib/data/importers/ravdess.py:16](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/ravdess.py:16)；行 16
- [ser_lib/data/manifest.py:23](D:/projects/Speech-Emotion-Recognition/ser_lib/data/manifest.py:23)；行 23
- [ser_lib/data/pipeline.py:28](D:/projects/Speech-Emotion-Recognition/ser_lib/data/pipeline.py:28)；行 28
- [ser_lib/data/query.py:12](D:/projects/Speech-Emotion-Recognition/ser_lib/data/query.py:12)；行 12
- [ser_lib/data/registry.py:19](D:/projects/Speech-Emotion-Recognition/ser_lib/data/registry.py:19)；行 19
- [ser_lib/data/representations/acoustic.py:28](D:/projects/Speech-Emotion-Recognition/ser_lib/data/representations/acoustic.py:28)；行 28
- [ser_lib/data/representations/base.py:16](D:/projects/Speech-Emotion-Recognition/ser_lib/data/representations/base.py:16)；行 16
- [ser_lib/data/representations/composite.py:18](D:/projects/Speech-Emotion-Recognition/ser_lib/data/representations/composite.py:18)；行 18
- [ser_lib/data/representations/spectral.py:17](D:/projects/Speech-Emotion-Recognition/ser_lib/data/representations/spectral.py:17)；行 17
- [ser_lib/data/representations/waveform.py:9](D:/projects/Speech-Emotion-Recognition/ser_lib/data/representations/waveform.py:9)；行 9
- [ser_lib/data/transforms/base.py:15](D:/projects/Speech-Emotion-Recognition/ser_lib/data/transforms/base.py:15)；行 15
- [ser_lib/data/validation.py:16](D:/projects/Speech-Emotion-Recognition/ser_lib/data/validation.py:16)；行 16
- [ser_lib/engine/_trainer_core.py:29](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/_trainer_core.py:29)；行 29
- [ser_lib/engine/evaluator.py:23](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/evaluator.py:23)；行 23
- [ser_lib/inference/batch.py:21](D:/projects/Speech-Emotion-Recognition/ser_lib/inference/batch.py:21)；行 21
- [ser_lib/inference/offline.py:11](D:/projects/Speech-Emotion-Recognition/ser_lib/inference/offline.py:11)；行 11
- [ser_lib/inference/streaming.py:11](D:/projects/Speech-Emotion-Recognition/ser_lib/inference/streaming.py:11)；行 11
- [ser_lib/models/base.py:9](D:/projects/Speech-Emotion-Recognition/ser_lib/models/base.py:9)；行 9
- [ser_lib/models/cnn_models.py:12](D:/projects/Speech-Emotion-Recognition/ser_lib/models/cnn_models.py:12)；行 12
- [ser_lib/models/pretrained.py:14](D:/projects/Speech-Emotion-Recognition/ser_lib/models/pretrained.py:14)；行 14
- [ser_lib/models/rnn_models.py:13](D:/projects/Speech-Emotion-Recognition/ser_lib/models/rnn_models.py:13)；行 13
- [ser_lib/models/transformer_models.py:13](D:/projects/Speech-Emotion-Recognition/ser_lib/models/transformer_models.py:13)；行 13
- [ser_lib/services/evaluation.py:13](D:/projects/Speech-Emotion-Recognition/ser_lib/services/evaluation.py:13)；行 13
- [ser_lib/services/inference.py:11](D:/projects/Speech-Emotion-Recognition/ser_lib/services/inference.py:11)；行 11
- [ser_lib/services/training.py:10](D:/projects/Speech-Emotion-Recognition/ser_lib/services/training.py:10)；行 10
- [tests/test_audio_pipeline.py:17](D:/projects/Speech-Emotion-Recognition/tests/test_audio_pipeline.py:17)；行 17
- [tests/test_cache.py:12](D:/projects/Speech-Emotion-Recognition/tests/test_cache.py:12)；行 12
- [tests/test_data_types.py:4](D:/projects/Speech-Emotion-Recognition/tests/test_data_types.py:4)；行 4
- [tests/test_manifest.py:7](D:/projects/Speech-Emotion-Recognition/tests/test_manifest.py:7)；行 7
- [tests/test_model_engine.py:15](D:/projects/Speech-Emotion-Recognition/tests/test_model_engine.py:15)；行 15
- [tests/test_new_collate.py:7](D:/projects/Speech-Emotion-Recognition/tests/test_new_collate.py:7)；行 7

| class/function/method | 定义行 | 职责说明（源码 docstring） |
| --- | --- | --- |
| `time_axis_of(layout: str) -> int \| None` | [ser_lib/data/types.py:44](D:/projects/Speech-Emotion-Recognition/ser_lib/data/types.py:44) | 返回 layout 的时间轴索引；非时序 layout 返回 ``None``。 |
| `is_temporal(layout: str) -> bool` | [ser_lib/data/types.py:50](D:/projects/Speech-Emotion-Recognition/ser_lib/data/types.py:50) | layout 是否带时间轴。 |
| `_validate_layout_name(layout: str) -> None` | [ser_lib/data/types.py:55](D:/projects/Speech-Emotion-Recognition/ser_lib/data/types.py:55) | 见实现；私有辅助 |
| `AudioRecord` | [ser_lib/data/types.py:69](D:/projects/Speech-Emotion-Recognition/ser_lib/data/types.py:69) | Manifest 中的一条音频记录。 |
| `AudioRecord.__post_init__(self) -> None` | [ser_lib/data/types.py:92](D:/projects/Speech-Emotion-Recognition/ser_lib/data/types.py:92) |  |
| `AudioData` | [ser_lib/data/types.py:120](D:/projects/Speech-Emotion-Recognition/ser_lib/data/types.py:120) | AudioLoader 的输出。 |
| `AudioData.__post_init__(self) -> None` | [ser_lib/data/types.py:136](D:/projects/Speech-Emotion-Recognition/ser_lib/data/types.py:136) |  |
| `TensorSpec` | [ser_lib/data/types.py:160](D:/projects/Speech-Emotion-Recognition/ser_lib/data/types.py:160) | 单个输入 tensor 的形状契约。 |
| `TensorSpec.__post_init__(self) -> None` | [ser_lib/data/types.py:177](D:/projects/Speech-Emotion-Recognition/ser_lib/data/types.py:177) |  |
| `TensorSpec.temporal(self) -> bool` | [ser_lib/data/types.py:194](D:/projects/Speech-Emotion-Recognition/ser_lib/data/types.py:194) | 是否为时序输入。 |
| `TensorSpec.validate_tensor(self, tensor: torch.Tensor, *, key: str, uid: str \| None=None, error_cls: type[SERDataError]=RepresentationError) -> None` | [ser_lib/data/types.py:198](D:/projects/Speech-Emotion-Recognition/ser_lib/data/types.py:198) | 校验单个 tensor 是否满足本 spec。 |
| `_feature_dim_index(layout: str) -> int` | [ser_lib/data/types.py:243](D:/projects/Speech-Emotion-Recognition/ser_lib/data/types.py:243) | 返回 feature_dim 校验时检查的维度索引。 |
| `validate_representation_output(output: 'RepresentationOutput', specs: Mapping[str, TensorSpec]) -> None` | [ser_lib/data/types.py:253](D:/projects/Speech-Emotion-Recognition/ser_lib/data/types.py:253) | 校验 RepresentationOutput 是否满足声明的 specs（设计文档 §5.4）。 |
| `RepresentationOutput` | [ser_lib/data/types.py:311](D:/projects/Speech-Emotion-Recognition/ser_lib/data/types.py:311) | Representation 的输出。 |
| `SERSample` | [ser_lib/data/types.py:326](D:/projects/Speech-Emotion-Recognition/ser_lib/data/types.py:326) | Dataset 的单样本输出。 |
| `SERSample.__post_init__(self) -> None` | [ser_lib/data/types.py:335](D:/projects/Speech-Emotion-Recognition/ser_lib/data/types.py:335) |  |
| `SERBatch` | [ser_lib/data/types.py:346](D:/projects/Speech-Emotion-Recognition/ser_lib/data/types.py:346) | Collator 的批次输出（设计文档 §5.6）。 |
| `SERBatch.__post_init__(self) -> None` | [ser_lib/data/types.py:365](D:/projects/Speech-Emotion-Recognition/ser_lib/data/types.py:365) |  |
| `validate_sample_contract(sample: SERSample, specs: Mapping[str, TensorSpec]) -> None` | [ser_lib/data/types.py:421](D:/projects/Speech-Emotion-Recognition/ser_lib/data/types.py:421) | 运行时样本契约校验（debug/strict 模式调用，见设计文档 T3.4）。 |

### ser_lib/data/validation.py

处理：**拆分**。目标：`ser_lib/models/specs.py + ser_lib/engine/compatibility.py`。理由：ModelSpec 与跨域兼容检查归位，data 不回引 engine。

直接 import 消费者（含测试；从公共包重导入的间接消费者还需沿 D/C 展开）：

- [ser_lib/artifacts/loader.py:29](D:/projects/Speech-Emotion-Recognition/ser_lib/artifacts/loader.py:29)；行 29
- [ser_lib/data/__init__.py:43](D:/projects/Speech-Emotion-Recognition/ser_lib/data/__init__.py:43)；行 43
- [ser_lib/engine/config.py:115](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/config.py:115)；行 115
- [ser_lib/engine/validation.py:14](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/validation.py:14)；行 14
- [ser_lib/models/base.py:10](D:/projects/Speech-Emotion-Recognition/ser_lib/models/base.py:10)；行 10
- [ser_lib/models/cnn_models.py:13](D:/projects/Speech-Emotion-Recognition/ser_lib/models/cnn_models.py:13)；行 13
- [ser_lib/models/pretrained.py:15](D:/projects/Speech-Emotion-Recognition/ser_lib/models/pretrained.py:15)；行 15
- [ser_lib/models/registry.py:13](D:/projects/Speech-Emotion-Recognition/ser_lib/models/registry.py:13)；行 13, 108
- [ser_lib/models/rnn_models.py:14](D:/projects/Speech-Emotion-Recognition/ser_lib/models/rnn_models.py:14)；行 14
- [ser_lib/models/transformer_models.py:14](D:/projects/Speech-Emotion-Recognition/ser_lib/models/transformer_models.py:14)；行 14
- [tests/test_batch_inference.py:20](D:/projects/Speech-Emotion-Recognition/tests/test_batch_inference.py:20)；行 20
- [tests/test_compatibility_report.py:11](D:/projects/Speech-Emotion-Recognition/tests/test_compatibility_report.py:11)；行 11
- [tests/test_evaluation_prediction_sink.py:8](D:/projects/Speech-Emotion-Recognition/tests/test_evaluation_prediction_sink.py:8)；行 8
- [tests/test_evaluator_reports.py:16](D:/projects/Speech-Emotion-Recognition/tests/test_evaluator_reports.py:16)；行 16
- [tests/test_model_engine.py:16](D:/projects/Speech-Emotion-Recognition/tests/test_model_engine.py:16)；行 16
- [tests/test_services.py:8](D:/projects/Speech-Emotion-Recognition/tests/test_services.py:8)；行 8

| class/function/method | 定义行 | 职责说明（源码 docstring） |
| --- | --- | --- |
| `ModelSpec` | [ser_lib/data/validation.py:20](D:/projects/Speech-Emotion-Recognition/ser_lib/data/validation.py:20) | 模型输入规格（模型显式声明，禁止调用方猜测 tensor shape）。 |
| `CompatibilityReport` | [ser_lib/data/validation.py:32](D:/projects/Speech-Emotion-Recognition/ser_lib/data/validation.py:32) | 模型与数据流水线的非抛异常兼容性检查结果。 |
| `CompatibilityReport.to_dict(self) -> dict[str, Any]` | [ser_lib/data/validation.py:38](D:/projects/Speech-Emotion-Recognition/ser_lib/data/validation.py:38) |  |
| `_problem(code: str, message: str, *, field: str \| None=None, details: dict[str, Any] \| None=None, suggestion: str \| None=None) -> Diagnostic` | [ser_lib/data/validation.py:45](D:/projects/Speech-Emotion-Recognition/ser_lib/data/validation.py:45) | 见实现；私有辅助 |
| `inspect_compatibility(representation_specs: Mapping[str, TensorSpec], model_spec: ModelSpec, batching_config: BatchingConfig, *, num_classes: int \| None=None, sample_rate: int \| None=None) -> CompatibilityReport` | [ser_lib/data/validation.py:64](D:/projects/Speech-Emotion-Recognition/ser_lib/data/validation.py:64) | 检查兼容性并返回全部问题，不抛 ``CompatibilityError``。 |
| `validate_compatibility(representation_specs: Mapping[str, TensorSpec], model_spec: ModelSpec, batching_config: BatchingConfig, *, num_classes: int \| None=None, sample_rate: int \| None=None) -> None` | [ser_lib/data/validation.py:246](D:/projects/Speech-Emotion-Recognition/ser_lib/data/validation.py:246) | 保留历史 raise 接口；内部复用 ``inspect_compatibility``。 |

### ser_lib/engine/__init__.py

处理：**瘦身**。目标：`原路径`。理由：更新 config/退役包装导出及内置注册顺序，不改变算法。

直接 import 消费者（含测试；从公共包重导入的间接消费者还需沿 D/C 展开）：

- [examples/train_from_python.py:11](D:/projects/Speech-Emotion-Recognition/examples/train_from_python.py:11)；行 11
- [ser_lib/__init__.py:26](D:/projects/Speech-Emotion-Recognition/ser_lib/__init__.py:26)；行 26
- [ser_lib/cli/workflows.py:17](D:/projects/Speech-Emotion-Recognition/ser_lib/cli/workflows.py:17)；行 17
- [tests/test_checkpoint_catalog.py:9](D:/projects/Speech-Emotion-Recognition/tests/test_checkpoint_catalog.py:9)；行 9
- [tests/test_checkpoint_resume.py:12](D:/projects/Speech-Emotion-Recognition/tests/test_checkpoint_resume.py:12)；行 12
- [tests/test_engine_config.py:13](D:/projects/Speech-Emotion-Recognition/tests/test_engine_config.py:13)；行 13
- [tests/test_evaluation_prediction_query.py:9](D:/projects/Speech-Emotion-Recognition/tests/test_evaluation_prediction_query.py:9)；行 9
- [tests/test_evaluation_prediction_sink.py:9](D:/projects/Speech-Emotion-Recognition/tests/test_evaluation_prediction_sink.py:9)；行 9
- [tests/test_evaluation_report_inspect.py:9](D:/projects/Speech-Emotion-Recognition/tests/test_evaluation_report_inspect.py:9)；行 9
- [tests/test_evaluation_run_catalog.py:11](D:/projects/Speech-Emotion-Recognition/tests/test_evaluation_run_catalog.py:11)；行 11
- [tests/test_evaluation_run_detail.py:7](D:/projects/Speech-Emotion-Recognition/tests/test_evaluation_run_detail.py:7)；行 7
- [tests/test_evaluation_run_metadata.py:11](D:/projects/Speech-Emotion-Recognition/tests/test_evaluation_run_metadata.py:11)；行 11
- [tests/test_evaluator_observability.py:18](D:/projects/Speech-Emotion-Recognition/tests/test_evaluator_observability.py:18)；行 18
- [tests/test_evaluator_reports.py:17](D:/projects/Speech-Emotion-Recognition/tests/test_evaluator_reports.py:17)；行 17
- [tests/test_experiment_presets.py:10](D:/projects/Speech-Emotion-Recognition/tests/test_experiment_presets.py:10)；行 10
- [tests/test_experiment_validation.py:10](D:/projects/Speech-Emotion-Recognition/tests/test_experiment_validation.py:10)；行 10
- [tests/test_objectives.py:8](D:/projects/Speech-Emotion-Recognition/tests/test_objectives.py:8)；行 8
- [tests/test_pretrained_adapter.py:21](D:/projects/Speech-Emotion-Recognition/tests/test_pretrained_adapter.py:21)；行 21
- [tests/test_public_api.py:9](D:/projects/Speech-Emotion-Recognition/tests/test_public_api.py:9)；行 9
- [tests/test_release_examples.py:5](D:/projects/Speech-Emotion-Recognition/tests/test_release_examples.py:5)；行 5
- [tests/test_rnn_models.py:12](D:/projects/Speech-Emotion-Recognition/tests/test_rnn_models.py:12)；行 12
- [tests/test_service_catalog_presets.py:5](D:/projects/Speech-Emotion-Recognition/tests/test_service_catalog_presets.py:5)；行 5
- [tests/test_services.py:9](D:/projects/Speech-Emotion-Recognition/tests/test_services.py:9)；行 9
- [tests/test_trainer_observability.py:18](D:/projects/Speech-Emotion-Recognition/tests/test_trainer_observability.py:18)；行 18
- [tests/test_training_history.py:9](D:/projects/Speech-Emotion-Recognition/tests/test_training_history.py:9)；行 9
- [tests/test_training_lineage.py:11](D:/projects/Speech-Emotion-Recognition/tests/test_training_lineage.py:11)；行 11
- [tests/test_training_result.py:12](D:/projects/Speech-Emotion-Recognition/tests/test_training_result.py:12)；行 12
- [tests/test_training_run_catalog.py:14](D:/projects/Speech-Emotion-Recognition/tests/test_training_run_catalog.py:14)；行 14
- [tests/test_training_run_detail.py:9](D:/projects/Speech-Emotion-Recognition/tests/test_training_run_detail.py:9)；行 9
- [tests/test_transformer_models.py:12](D:/projects/Speech-Emotion-Recognition/tests/test_transformer_models.py:12)；行 12

| class/function/method | 定义行 | 职责说明（源码 docstring） |
| --- | --- | --- |

### ser_lib/engine/_trainer_core.py

处理：**合并**。目标：`ser_lib/engine/trainer.py + ser_lib/engine/state.py + data/types.py:move_batch_to_device`。理由：只有一套循环；保留全部 resume/AMP/状态，batch helper 回 data。

直接 import 消费者（含测试；从公共包重导入的间接消费者还需沿 D/C 展开）：

- [ser_lib/engine/trainer.py:12](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/trainer.py:12)；行 12

| class/function/method | 定义行 | 职责说明（源码 docstring） |
| --- | --- | --- |
| `EpochResult` | [ser_lib/engine/_trainer_core.py:47](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/_trainer_core.py:47) | 领域/公开定义 |
| `EpochResult.to_dict(self) -> dict[str, Any]` | [ser_lib/engine/_trainer_core.py:55](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/_trainer_core.py:55) | 返回适合 JSON 序列化的 epoch 结果。 |
| `TrainingResult` | [ser_lib/engine/_trainer_core.py:68](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/_trainer_core.py:68) | 一次 ``Trainer.fit`` 调用的稳定、JSON-safe 终态结果。 |
| `TrainingResult.to_dict(self) -> dict[str, Any]` | [ser_lib/engine/_trainer_core.py:84](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/_trainer_core.py:84) | 返回可直接交给 Web/CLI JSON 层的标准字典。 |
| `seed_everything(seed: int, *, deterministic: bool=True) -> None` | [ser_lib/engine/_trainer_core.py:106](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/_trainer_core.py:106) | 为 Python 与 PyTorch 设置可复现 seed。 |
| `move_batch_to_device(batch: SERBatch, device: torch.device) -> SERBatch` | [ser_lib/engine/_trainer_core.py:116](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/_trainer_core.py:116) | 将 batch 中的 tensor 移动到目标设备，保留元数据。 |
| `_safe_len(value: object) -> int \| None` | [ser_lib/engine/_trainer_core.py:128](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/_trainer_core.py:128) | 见实现；私有辅助 |
| `_infer_total_samples(batches: object) -> int \| None` | [ser_lib/engine/_trainer_core.py:137](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/_trainer_core.py:137) | 见实现；私有辅助 |
| `Trainer` | [ser_lib/engine/_trainer_core.py:154](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/_trainer_core.py:154) | 领域/公开定义 |
| `Trainer.__init__(self, model: SERModel, config: TrainerConfig \| None=None, *, optimizer: torch.optim.Optimizer, scheduler: torch.optim.lr_scheduler.LRScheduler \| None=None, loss_fn: torch.nn.Module \| None=None, event_callback: EventCallback \| None=None, cancellation: CancellationCheck \| None=None, observability: ObservabilityConfig \| None=None, run_id: str \| None=None) -> None` | [ser_lib/engine/_trainer_core.py:155](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/_trainer_core.py:155) |  |
| `Trainer.from_experiment(cls, model: SERModel, experiment: ExperimentConfig, *, event_callback: EventCallback \| None=None, cancellation: CancellationCheck \| None=None, observability: ObservabilityConfig \| None=None, run_id: str \| None=None) -> 'Trainer'` | [ser_lib/engine/_trainer_core.py:208](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/_trainer_core.py:208) | 按白名单实验配置构造 optimizer、scheduler 和 Trainer。 |
| `Trainer._emit(self, event: LibraryEvent) -> None` | [ser_lib/engine/_trainer_core.py:252](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/_trainer_core.py:252) |  |
| `Trainer._check_cancelled(self) -> None` | [ser_lib/engine/_trainer_core.py:256](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/_trainer_core.py:256) |  |
| `Trainer._context(self, *, epoch: int \| None=None, batch: int \| None=None, total_batches: int \| None=None, split: str \| None=None) -> EventContext` | [ser_lib/engine/_trainer_core.py:260](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/_trainer_core.py:260) |  |
| `Trainer._current_learning_rate(self) -> float` | [ser_lib/engine/_trainer_core.py:278](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/_trainer_core.py:278) |  |
| `Trainer._build_training_result(self, history: Sequence[EpochResult], *, status: TrainingStatus, started_at: datetime, finished_at: datetime, duration_seconds: float, stop_reason: str \| None) -> TrainingResult` | [ser_lib/engine/_trainer_core.py:283](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/_trainer_core.py:283) |  |
| `Trainer._optimizer_step(self) -> None` | [ser_lib/engine/_trainer_core.py:308](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/_trainer_core.py:308) |  |
| `Trainer._emit_live_metrics(self, *, epoch: int, batch_index: int, total_batches: int \| None, batch_loss: float, running_loss: float, running_accuracy: float, samples_per_second: float) -> None` | [ser_lib/engine/_trainer_core.py:323](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/_trainer_core.py:323) |  |
| `Trainer.train_epoch(self, batches: Iterable[SERBatch], *, epoch: int) -> EpochResult` | [ser_lib/engine/_trainer_core.py:358](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/_trainer_core.py:358) |  |
| `Trainer._emit_validation_event(self, event: LibraryEvent, *, epoch: int, total_batches: int \| None) -> None` | [ser_lib/engine/_trainer_core.py:506](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/_trainer_core.py:506) |  |
| `Trainer._save_checkpoint_with_event(self, path: Path, *, kind: str, epoch: int, metrics: dict[str, float], metadata: dict[str, object]) -> Path` | [ser_lib/engine/_trainer_core.py:557](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/_trainer_core.py:557) |  |
| `Trainer.fit(self, train_batches: Iterable[SERBatch] \| Callable[[], Iterable[SERBatch]], *, val_batches: Iterable[SERBatch] \| Callable[[], Iterable[SERBatch]] \| None=None, on_epoch_end: Callable[[EpochResult], None] \| None=None, start_epoch: int \| None=None) -> list[EpochResult]` | [ser_lib/engine/_trainer_core.py:638](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/_trainer_core.py:638) |  |
| `Trainer._is_improved(self, value: float) -> bool` | [ser_lib/engine/_trainer_core.py:964](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/_trainer_core.py:964) |  |
| `Trainer.resume_from(self, path, *, restore_rng: bool=True) -> dict` | [ser_lib/engine/_trainer_core.py:972](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/_trainer_core.py:972) | 恢复训练状态，并使下次 ``fit`` 从 checkpoint 的下一 epoch 开始。 |

### ser_lib/engine/checkpoint.py

处理：**保留**。目标：`原路径`。理由：v1/v2 保存恢复保留；Adapter 键/配置兼容需新增验收。

直接 import 消费者（含测试；从公共包重导入的间接消费者还需沿 D/C 展开）：

- [ser_lib/engine/__init__.py:1](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/__init__.py:1)；行 1
- [ser_lib/engine/_trainer_core.py:566](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/_trainer_core.py:566)；行 566, 974
- [tests/test_model_engine.py:17](D:/projects/Speech-Emotion-Recognition/tests/test_model_engine.py:17)；行 17

| class/function/method | 定义行 | 职责说明（源码 docstring） |
| --- | --- | --- |
| `_rng_state() -> dict[str, Any]` | [ser_lib/engine/checkpoint.py:17](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/checkpoint.py:17) | 见实现；私有辅助 |
| `_restore_rng_state(state: dict[str, Any]) -> None` | [ser_lib/engine/checkpoint.py:27](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/checkpoint.py:27) | 见实现；私有辅助 |
| `save_checkpoint(path: Path \| str, model: SERModel, optimizer: torch.optim.Optimizer \| None, *, epoch: int, scheduler: torch.optim.lr_scheduler.LRScheduler \| None=None, scaler: torch.cuda.amp.GradScaler \| None=None, metrics: dict[str, float] \| None=None, metadata: dict[str, Any] \| None=None, trainer_config: dict[str, Any] \| None=None) -> Path` | [ser_lib/engine/checkpoint.py:36](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/checkpoint.py:36) | 原子保存继续训练所需状态。 |
| `load_checkpoint(path: Path \| str, model: SERModel, optimizer: torch.optim.Optimizer \| None=None, *, scheduler: torch.optim.lr_scheduler.LRScheduler \| None=None, scaler: torch.cuda.amp.GradScaler \| None=None, map_location: str \| torch.device='cpu', restore_rng: bool=True, expected_trainer_config: dict[str, Any] \| None=None) -> dict[str, Any]` | [ser_lib/engine/checkpoint.py:81](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/checkpoint.py:81) | 加载可信 checkpoint；兼容格式 v1，完整恢复格式 v2。 |

### ser_lib/engine/checkpoint_catalog.py

处理：**保留**。目标：`原路径`。理由：stat 级扫描保留；文件名 epoch 不是 payload epoch。

直接 import 消费者（含测试；从公共包重导入的间接消费者还需沿 D/C 展开）：

- [ser_lib/engine/__init__.py:2](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/__init__.py:2)；行 2
- [ser_lib/engine/runs.py:17](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/runs.py:17)；行 17
- [ser_lib/services/training.py:11](D:/projects/Speech-Emotion-Recognition/ser_lib/services/training.py:11)；行 11

| class/function/method | 定义行 | 职责说明（源码 docstring） |
| --- | --- | --- |
| `CheckpointInfo` | [ser_lib/engine/checkpoint_catalog.py:19](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/checkpoint_catalog.py:19) | 不反序列化 `.pt` 内容即可获得的 checkpoint 文件信息。 |
| `CheckpointInfo.to_dict(self) -> dict[str, Any]` | [ser_lib/engine/checkpoint_catalog.py:29](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/checkpoint_catalog.py:29) |  |
| `CheckpointScanFailure` | [ser_lib/engine/checkpoint_catalog.py:41](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/checkpoint_catalog.py:41) | 领域/公开定义 |
| `CheckpointScanFailure.to_dict(self) -> dict[str, str]` | [ser_lib/engine/checkpoint_catalog.py:46](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/checkpoint_catalog.py:46) |  |
| `CheckpointCatalog` | [ser_lib/engine/checkpoint_catalog.py:55](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/checkpoint_catalog.py:55) | Checkpoint 列表；扫描不会调用 `torch.load()`。 |
| `CheckpointCatalog.total(self) -> int` | [ser_lib/engine/checkpoint_catalog.py:63](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/checkpoint_catalog.py:63) |  |
| `CheckpointCatalog.to_dict(self) -> dict[str, Any]` | [ser_lib/engine/checkpoint_catalog.py:66](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/checkpoint_catalog.py:66) |  |
| `inspect_checkpoint_file(path: Path \| str) -> CheckpointInfo` | [ser_lib/engine/checkpoint_catalog.py:75](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/checkpoint_catalog.py:75) | 只读取一个 `.pt` 文件的 stat 信息，不解析 pickle payload。 |
| `scan_checkpoints(root: Path \| str, *, recursive: bool=False, fail_fast: bool=False, event_callback: EventCallback \| None=None, cancellation: CancellationCheck \| None=None) -> CheckpointCatalog` | [ser_lib/engine/checkpoint_catalog.py:94](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/checkpoint_catalog.py:94) | 扫描 `.pt` checkpoint；不读取模型、optimizer 或 RNG state。 |
| `_classify_checkpoint_name(name: str) -> tuple[CheckpointKind, int \| None]` | [ser_lib/engine/checkpoint_catalog.py:132](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/checkpoint_catalog.py:132) | 见实现；私有辅助 |
| `_candidate_files(root: Path, *, recursive: bool) -> list[Path]` | [ser_lib/engine/checkpoint_catalog.py:143](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/checkpoint_catalog.py:143) | 见实现；私有辅助 |

### ser_lib/engine/config.py

处理：**拆分**。目标：`ser_lib/config/{experiment,model,training,loader}.py + ser_lib/engine/experiment.py`。理由：config schema 与 ExperimentComponents/build 分离。

直接 import 消费者（含测试；从公共包重导入的间接消费者还需沿 D/C 展开）：

- [ser_lib/engine/__init__.py:10](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/__init__.py:10)；行 10
- [ser_lib/engine/_trainer_core.py:30](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/_trainer_core.py:30)；行 30
- [ser_lib/engine/presets.py:9](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/presets.py:9)；行 9
- [ser_lib/engine/trainer.py:22](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/trainer.py:22)；行 22
- [ser_lib/engine/validation.py:15](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/validation.py:15)；行 15
- [ser_lib/services/catalog.py:13](D:/projects/Speech-Emotion-Recognition/ser_lib/services/catalog.py:13)；行 13
- [ser_lib/services/training.py:17](D:/projects/Speech-Emotion-Recognition/ser_lib/services/training.py:17)；行 17
- [tests/test_experiment_validation.py:11](D:/projects/Speech-Emotion-Recognition/tests/test_experiment_validation.py:11)；行 11

| class/function/method | 定义行 | 职责说明（源码 docstring） |
| --- | --- | --- |
| `ModelConfig` | [ser_lib/engine/config.py:22](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/config.py:22) | 注册表模型及其构造参数。 |
| `ObservabilityConfig` | [ser_lib/engine/config.py:29](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/config.py:29) | 训练运行时事件频率与轻量 ETA 参数。 |
| `ObservabilityConfig._validate_eta_window(self) -> 'ObservabilityConfig'` | [ser_lib/engine/config.py:38](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/config.py:38) |  |
| `TrainerConfig` | [ser_lib/engine/config.py:44](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/config.py:44) | 表示无关的训练循环配置；optimizer 参数不属于本节点。 |
| `ExperimentConfig` | [ser_lib/engine/config.py:65](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/config.py:65) | 一次可复现实验的完整、可序列化配置快照。 |
| `ExperimentConfig._validate_optimizer(cls, value: dict[str, Any]) -> dict[str, Any]` | [ser_lib/engine/config.py:82](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/config.py:82) |  |
| `ExperimentConfig._validate_scheduler(cls, value: dict[str, Any] \| None) -> dict[str, Any] \| None` | [ser_lib/engine/config.py:90](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/config.py:90) |  |
| `ExperimentComponents` | [ser_lib/engine/config.py:98](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/config.py:98) | 通过完整预检后可直接交给训练代码的运行时组件。 |
| `build_experiment_components(config: ExperimentConfig, *, train: bool=True) -> ExperimentComponents` | [ser_lib/engine/config.py:107](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/config.py:107) | 构建实验组件，并在读取训练数据前完成全部静态兼容性检查。 |
| `load_experiment_config(path: Path \| str) -> ExperimentConfig` | [ser_lib/engine/config.py:132](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/config.py:132) | 读取时迁移到当前 schema v1；相对输出路径基于配置文件目录。 |

### ser_lib/engine/eta.py

处理：**保留**。目标：`原路径`。理由：长任务估时有 CLI/SDK 价值。

直接 import 消费者（含测试；从公共包重导入的间接消费者还需沿 D/C 展开）：

- [ser_lib/engine/__init__.py:19](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/__init__.py:19)；行 19
- [ser_lib/engine/_trainer_core.py:31](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/_trainer_core.py:31)；行 31
- [tests/test_eta.py:5](D:/projects/Speech-Emotion-Recognition/tests/test_eta.py:5)；行 5

| class/function/method | 定义行 | 职责说明（源码 docstring） |
| --- | --- | --- |
| `EtaSnapshot` | [ser_lib/engine/eta.py:11](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/eta.py:11) | 某一阶段的稳定 ETA/吞吐快照。 |
| `EtaSnapshot.to_dict(self) -> dict[str, Any]` | [ser_lib/engine/eta.py:24](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/eta.py:24) |  |
| `_BatchTiming` | [ser_lib/engine/eta.py:39](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/eta.py:39) | 见实现；私有辅助 |
| `EtaEstimator` | [ser_lib/engine/eta.py:44](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/eta.py:44) | 按 phase 维护固定 recent-N 窗口的 ETA 状态。 |
| `EtaEstimator.__init__(self, *, window_size: int=20, warmup_batches: int=3) -> None` | [ser_lib/engine/eta.py:51](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/eta.py:51) |  |
| `EtaEstimator.reset(self, phase: str \| None=None) -> None` | [ser_lib/engine/eta.py:66](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/eta.py:66) |  |
| `EtaEstimator.record_batch(self, duration_seconds: float, samples: int=0, *, phase: str='train') -> None` | [ser_lib/engine/eta.py:76](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/eta.py:76) |  |
| `EtaEstimator.snapshot(self, *, phase: str='train', completed_batches: int, total_batches: int \| None, future_batches: int=0) -> EtaSnapshot` | [ser_lib/engine/eta.py:93](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/eta.py:93) |  |

### ser_lib/engine/evaluation_catalog.py

处理：**保留**。目标：`原路径`。理由：真实 evaluation.json 扫描，不扩展页面组合。

直接 import 消费者（含测试；从公共包重导入的间接消费者还需沿 D/C 展开）：

- [ser_lib/engine/__init__.py:20](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/__init__.py:20)；行 20
- [ser_lib/services/evaluation.py:14](D:/projects/Speech-Emotion-Recognition/ser_lib/services/evaluation.py:14)；行 14

| class/function/method | 定义行 | 职责说明（源码 docstring） |
| --- | --- | --- |
| `EvaluationRunScanFailure` | [ser_lib/engine/evaluation_catalog.py:17](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/evaluation_catalog.py:17) | 领域/公开定义 |
| `EvaluationRunScanFailure.to_dict(self) -> dict[str, str]` | [ser_lib/engine/evaluation_catalog.py:22](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/evaluation_catalog.py:22) |  |
| `EvaluationRunCatalog` | [ser_lib/engine/evaluation_catalog.py:31](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/evaluation_catalog.py:31) | 评估历史列表；扫描时不读取 metrics/predictions/artifact。 |
| `EvaluationRunCatalog.total(self) -> int` | [ser_lib/engine/evaluation_catalog.py:39](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/evaluation_catalog.py:39) |  |
| `EvaluationRunCatalog.to_dict(self) -> dict[str, Any]` | [ser_lib/engine/evaluation_catalog.py:42](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/evaluation_catalog.py:42) |  |
| `scan_evaluation_runs(root: Path \| str, *, recursive: bool=False, fail_fast: bool=False, event_callback: EventCallback \| None=None, cancellation: CancellationCheck \| None=None) -> EvaluationRunCatalog` | [ser_lib/engine/evaluation_catalog.py:51](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/evaluation_catalog.py:51) | 扫描 ``evaluation.json``，不加载模型、Artifact、指标文件或预测明细。 |
| `_candidate_directories(root: Path, *, recursive: bool) -> list[Path]` | [ser_lib/engine/evaluation_catalog.py:86](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/evaluation_catalog.py:86) | 见实现；私有辅助 |

### ser_lib/engine/evaluation_detail.py

处理：**拆分**。目标：`ser_lib/engine/evaluation_reports.py`。理由：删除 EvaluationRunDetail；prediction stat metadata 合并到 reports。

直接 import 消费者（含测试；从公共包重导入的间接消费者还需沿 D/C 展开）：

- [ser_lib/engine/__init__.py:25](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/__init__.py:25)；行 25
- [ser_lib/services/evaluation.py:15](D:/projects/Speech-Emotion-Recognition/ser_lib/services/evaluation.py:15)；行 15

| class/function/method | 定义行 | 职责说明（源码 docstring） |
| --- | --- | --- |
| `EvaluationPredictionFileInfo` | [ser_lib/engine/evaluation_detail.py:15](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/evaluation_detail.py:15) | 仅通过 evaluation metadata 与文件 stat 获得的 prediction 文件信息。 |
| `EvaluationPredictionFileInfo.to_dict(self) -> dict[str, Any]` | [ser_lib/engine/evaluation_detail.py:22](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/evaluation_detail.py:22) |  |
| `EvaluationRunDetail` | [ser_lib/engine/evaluation_detail.py:31](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/evaluation_detail.py:31) | Worker/详情页可直接消费的轻量评估聚合结果。 |
| `EvaluationRunDetail.to_dict(self) -> dict[str, Any]` | [ser_lib/engine/evaluation_detail.py:43](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/evaluation_detail.py:43) |  |
| `inspect_evaluation_prediction_file(run: EvaluationRunInfo) -> EvaluationPredictionFileInfo` | [ser_lib/engine/evaluation_detail.py:52](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/evaluation_detail.py:52) | 按 ``evaluation.json`` 声明的文件名做 stat，不打开 prediction 内容。 |

### ser_lib/engine/evaluation_reports.py

处理：**拆分**。目标：`原路径:iter_evaluation_predictions + report inspection`。理由：删除 Page，保留严格 JSONL 校验与过滤。

直接 import 消费者（含测试；从公共包重导入的间接消费者还需沿 D/C 展开）：

- [ser_lib/engine/__init__.py:30](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/__init__.py:30)；行 30
- [ser_lib/engine/evaluation_detail.py:10](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/evaluation_detail.py:10)；行 10
- [ser_lib/services/evaluation.py:19](D:/projects/Speech-Emotion-Recognition/ser_lib/services/evaluation.py:19)；行 19

| class/function/method | 定义行 | 职责说明（源码 docstring） |
| --- | --- | --- |
| `_ClassMetricsModel` | [ser_lib/engine/evaluation_reports.py:16](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/evaluation_reports.py:16) | 见实现；私有辅助 |
| `_EvaluationMetricsModel` | [ser_lib/engine/evaluation_reports.py:27](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/evaluation_reports.py:27) | ``metrics.json`` 的严格 schema。 |
| `_EvaluationMetricsModel._validate_dimensions(self) -> '_EvaluationMetricsModel'` | [ser_lib/engine/evaluation_reports.py:48](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/evaluation_reports.py:48) |  |
| `_PredictionRecordModel` | [ser_lib/engine/evaluation_reports.py:63](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/evaluation_reports.py:63) | ``predictions.jsonl`` 单行的严格 schema。 |
| `_PredictionRecordModel._validate_probabilities(self) -> '_PredictionRecordModel'` | [ser_lib/engine/evaluation_reports.py:75](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/evaluation_reports.py:75) |  |
| `EvaluationReportInfo` | [ser_lib/engine/evaluation_reports.py:85](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/evaluation_reports.py:85) | 无需读取预测明细即可展示的评估报告信息。 |
| `EvaluationReportInfo.to_dict(self) -> dict[str, Any]` | [ser_lib/engine/evaluation_reports.py:106](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/evaluation_reports.py:106) |  |
| `EvaluationPredictionPage` | [ser_lib/engine/evaluation_reports.py:129](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/evaluation_reports.py:129) | 对 ``predictions.jsonl`` 的一次有界内存分页查询结果。 |
| `EvaluationPredictionPage.returned_count(self) -> int` | [ser_lib/engine/evaluation_reports.py:141](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/evaluation_reports.py:141) |  |
| `EvaluationPredictionPage.to_dict(self) -> dict[str, Any]` | [ser_lib/engine/evaluation_reports.py:144](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/evaluation_reports.py:144) |  |
| `inspect_evaluation_report(directory: Path \| str) -> EvaluationReportInfo` | [ser_lib/engine/evaluation_reports.py:157](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/evaluation_reports.py:157) | 读取并严格校验 ``metrics.json``，但不读取 ``predictions.jsonl`` 内容。 |
| `query_evaluation_predictions(directory: Path \| str, *, offset: int=0, limit: int=100, incorrect_only: bool=False, target: int \| None=None, predicted: int \| None=None, cancellation: CancellationCheck \| None=None) -> EvaluationPredictionPage` | [ser_lib/engine/evaluation_reports.py:203](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/evaluation_reports.py:203) | 顺序扫描预测 JSONL，并按过滤后的结果执行 offset/limit 分页。 |

### ser_lib/engine/evaluation_runs.py

处理：**保留**。目标：`原路径 + ser_lib/engine/migrations.py`。理由：真实评估记录，library_version 默认回归 metadata builder。

直接 import 消费者（含测试；从公共包重导入的间接消费者还需沿 D/C 展开）：

- [ser_lib/engine/__init__.py:36](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/__init__.py:36)；行 36
- [ser_lib/engine/evaluation_catalog.py:11](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/evaluation_catalog.py:11)；行 11
- [ser_lib/engine/evaluation_detail.py:11](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/evaluation_detail.py:11)；行 11
- [ser_lib/services/evaluation.py:25](D:/projects/Speech-Emotion-Recognition/ser_lib/services/evaluation.py:25)；行 25

| class/function/method | 定义行 | 职责说明（源码 docstring） |
| --- | --- | --- |
| `_EvaluationRunRecordModel` | [ser_lib/engine/evaluation_runs.py:34](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/evaluation_runs.py:34) | ``evaluation.json`` 的严格磁盘 schema。 |
| `_EvaluationRunRecordModel._require_timezone(cls, value: datetime) -> datetime` | [ser_lib/engine/evaluation_runs.py:61](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/evaluation_runs.py:61) |  |
| `_EvaluationRunRecordModel._optional_nonempty(cls, value: str \| None) -> str \| None` | [ser_lib/engine/evaluation_runs.py:68](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/evaluation_runs.py:68) |  |
| `_EvaluationRunRecordModel._safe_report_file(cls, value: str \| None) -> str \| None` | [ser_lib/engine/evaluation_runs.py:75](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/evaluation_runs.py:75) |  |
| `_EvaluationRunRecordModel._validate_timeline_and_metrics(self) -> '_EvaluationRunRecordModel'` | [ser_lib/engine/evaluation_runs.py:84](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/evaluation_runs.py:84) |  |
| `EvaluationRunMetadata` | [ser_lib/engine/evaluation_runs.py:99](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/evaluation_runs.py:99) | 评估开始前即可创建并用于事件上下文的稳定 lineage。 |
| `EvaluationRunMetadata.__post_init__(self) -> None` | [ser_lib/engine/evaluation_runs.py:113](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/evaluation_runs.py:113) |  |
| `EvaluationRunMetadata.to_dict(self) -> dict[str, Any]` | [ser_lib/engine/evaluation_runs.py:132](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/evaluation_runs.py:132) |  |
| `EvaluationRunInfo` | [ser_lib/engine/evaluation_runs.py:148](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/evaluation_runs.py:148) | 历史列表/详情可直接消费的评估终态记录。 |
| `EvaluationRunInfo.to_dict(self) -> dict[str, Any]` | [ser_lib/engine/evaluation_runs.py:170](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/evaluation_runs.py:170) |  |
| `EvaluationRunInfo.from_evaluation(cls, directory: Path \| str, metadata: EvaluationRunMetadata, result: EvaluationResult, *, started_at: datetime, finished_at: datetime, predictions_file: str \| None='predictions.jsonl') -> 'EvaluationRunInfo'` | [ser_lib/engine/evaluation_runs.py:177](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/evaluation_runs.py:177) |  |
| `EvaluationRunInfo.from_dict(cls, value: Mapping[str, Any], *, directory: Path \| str \| None=None) -> 'EvaluationRunInfo'` | [ser_lib/engine/evaluation_runs.py:213](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/evaluation_runs.py:213) |  |
| `build_evaluation_run_metadata(*, source_artifact: Path \| str, dataset_id: str, model_name: str, split: str, device: str, library_version: str, source_run_id: str \| None=None, dataset_fingerprint: str \| None=None, evaluation_id: str \| None=None, created_at: datetime \| None=None) -> EvaluationRunMetadata` | [ser_lib/engine/evaluation_runs.py:234](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/evaluation_runs.py:234) | 构造评估 lineage；不执行文件扫描、模型加载或 fingerprint 计算。 |
| `write_evaluation_run_info(directory: Path \| str, metadata: EvaluationRunMetadata, result: EvaluationResult, *, started_at: datetime, finished_at: datetime, predictions_file: str \| None='predictions.jsonl') -> Path` | [ser_lib/engine/evaluation_runs.py:262](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/evaluation_runs.py:262) | 把终态评估记录原子写入 ``evaluation.json``。 |
| `load_evaluation_run_info(path: Path \| str) -> EvaluationRunInfo` | [ser_lib/engine/evaluation_runs.py:296](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/evaluation_runs.py:296) | 读取 evaluation 目录或 ``evaluation.json``；目录以实际位置为准。 |

### ser_lib/engine/evaluator.py

处理：**瘦身**。目标：`原路径；batch helper 改从 data/types.py 导入`。理由：保留 evaluate/metrics/sink/report，消除对 Trainer helper 的依赖。

直接 import 消费者（含测试；从公共包重导入的间接消费者还需沿 D/C 展开）：

- [ser_lib/engine/__init__.py:44](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/__init__.py:44)；行 44
- [ser_lib/engine/_trainer_core.py:722](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/_trainer_core.py:722)；行 722
- [ser_lib/engine/evaluation_reports.py:13](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/evaluation_reports.py:13)；行 13
- [ser_lib/engine/evaluation_runs.py:15](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/evaluation_runs.py:15)；行 15
- [ser_lib/services/evaluation.py:32](D:/projects/Speech-Emotion-Recognition/ser_lib/services/evaluation.py:32)；行 32
- [tests/test_model_engine.py:18](D:/projects/Speech-Emotion-Recognition/tests/test_model_engine.py:18)；行 18

| class/function/method | 定义行 | 职责说明（源码 docstring） |
| --- | --- | --- |
| `ClassMetrics` | [ser_lib/engine/evaluator.py:29](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/evaluator.py:29) | 领域/公开定义 |
| `ClassMetrics.to_dict(self) -> dict[str, object]` | [ser_lib/engine/evaluator.py:37](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/evaluator.py:37) | 返回稳定、可直接 JSON 序列化的类别指标。 |
| `PredictionRecord` | [ser_lib/engine/evaluator.py:50](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/evaluator.py:50) | 领域/公开定义 |
| `PredictionRecord.to_dict(self) -> dict[str, object]` | [ser_lib/engine/evaluator.py:57](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/evaluator.py:57) | 返回单样本预测的 JSON-safe 表示。 |
| `PredictionSink` | [ser_lib/engine/evaluator.py:68](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/evaluator.py:68) | 评估逐样本结果的增量消费者协议。 |
| `PredictionSink.write(self, record: PredictionRecord) -> None` | [ser_lib/engine/evaluator.py:71](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/evaluator.py:71) | 消费一条已经完成 softmax/argmax 的预测记录。 |
| `JsonlPredictionSink` | [ser_lib/engine/evaluator.py:76](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/evaluator.py:76) | 把评估预测增量写入 JSONL，避免完整预测常驻内存。 |
| `JsonlPredictionSink.__init__(self, path: Path \| str, *, append: bool=False, flush_each: bool=False) -> None` | [ser_lib/engine/evaluator.py:83](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/evaluator.py:83) |  |
| `JsonlPredictionSink.write(self, record: PredictionRecord) -> None` | [ser_lib/engine/evaluator.py:96](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/evaluator.py:96) |  |
| `JsonlPredictionSink.flush(self) -> None` | [ser_lib/engine/evaluator.py:103](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/evaluator.py:103) |  |
| `JsonlPredictionSink.close(self) -> None` | [ser_lib/engine/evaluator.py:107](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/evaluator.py:107) |  |
| `JsonlPredictionSink.__enter__(self) -> 'JsonlPredictionSink'` | [ser_lib/engine/evaluator.py:111](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/evaluator.py:111) |  |
| `JsonlPredictionSink.__exit__(self, exc_type: object, exc: object, traceback: object) -> None` | [ser_lib/engine/evaluator.py:114](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/evaluator.py:114) |  |
| `EvaluationResult` | [ser_lib/engine/evaluator.py:119](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/evaluator.py:119) | 领域/公开定义 |
| `EvaluationResult.to_dict(self, *, include_predictions: bool=True) -> dict[str, object]` | [ser_lib/engine/evaluator.py:136](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/evaluator.py:136) | 返回公开 Result 的统一 JSON-safe 表示。 |
| `EvaluationResult.summary_dict(self) -> dict[str, object]` | [ser_lib/engine/evaluator.py:162](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/evaluator.py:162) | 兼容旧 API：返回不含样本明细的 JSON-safe 聚合报告。 |
| `_safe_len(value: object) -> int \| None` | [ser_lib/engine/evaluator.py:167](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/evaluator.py:167) | 见实现；私有辅助 |
| `_validate_labels(labels: Mapping[int, str] \| None, num_classes: int) -> dict[int, str]` | [ser_lib/engine/evaluator.py:176](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/evaluator.py:176) | 见实现；私有辅助 |
| `_resolve_event_context(context: EventContext \| None, *, split: str \| None, total_batches: int \| None) -> EventContext` | [ser_lib/engine/evaluator.py:190](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/evaluator.py:190) | 见实现；私有辅助 |
| `_result_event_details(result: EvaluationResult) -> dict[str, object]` | [ser_lib/engine/evaluator.py:214](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/evaluator.py:214) | 生命周期完成事件只携带紧凑聚合值，避免把预测明细塞进事件流。 |
| `evaluate(model: SERModel, batches: Iterable[SERBatch], *, num_classes: int, device: str \| torch.device='cpu', labels: Mapping[int, str] \| None=None, event_callback: EventCallback \| None=None, cancellation: CancellationCheck \| None=None, loss_fn: torch.nn.Module \| None=None, event_context: EventContext \| None=None, split: str \| None=None, prediction_sink: PredictionSink \| None=None, retain_predictions: bool=True) -> EvaluationResult` | [ser_lib/engine/evaluator.py:229](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/evaluator.py:229) | 评估分类模型，并可增量输出每个样本的预测。 |
| `write_evaluation_report(directory: Path \| str, result: EvaluationResult) -> Path` | [ser_lib/engine/evaluator.py:494](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/evaluator.py:494) | 原子写入 ``metrics.json`` 与 ``predictions.jsonl``。 |

### ser_lib/engine/lineage.py

处理：**保留**。目标：`原路径`。理由：可复现来源/配置指纹，不是页面对象。

直接 import 消费者（含测试；从公共包重导入的间接消费者还需沿 D/C 展开）：

- [ser_lib/engine/__init__.py:53](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/__init__.py:53)；行 53
- [ser_lib/engine/runs.py:18](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/runs.py:18)；行 18
- [ser_lib/engine/trainer.py:23](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/trainer.py:23)；行 23
- [ser_lib/services/artifacts.py:24](D:/projects/Speech-Emotion-Recognition/ser_lib/services/artifacts.py:24)；行 24
- [ser_lib/services/training.py:18](D:/projects/Speech-Emotion-Recognition/ser_lib/services/training.py:18)；行 18

| class/function/method | 定义行 | 职责说明（源码 docstring） |
| --- | --- | --- |
| `TrainingRunMetadata` | [ser_lib/engine/lineage.py:11](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/lineage.py:11) | 一次训练运行的稳定、JSON-safe lineage 描述。 |
| `TrainingRunMetadata.__post_init__(self) -> None` | [ser_lib/engine/lineage.py:29](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/lineage.py:29) |  |
| `TrainingRunMetadata.to_dict(self) -> dict[str, Any]` | [ser_lib/engine/lineage.py:48](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/lineage.py:48) |  |
| `TrainingRunMetadata.from_dict(cls, value: Mapping[str, Any]) -> 'TrainingRunMetadata'` | [ser_lib/engine/lineage.py:62](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/lineage.py:62) |  |
| `TrainingRunMetadata.with_run_id(self, run_id: str) -> 'TrainingRunMetadata'` | [ser_lib/engine/lineage.py:90](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/lineage.py:90) |  |
| `build_training_run_metadata(*, run_id: str, model_id: str, config: Mapping[str, Any], seed: int, device: str, library_version: str, dataset_id: str \| None=None, dataset_fingerprint: str \| None=None, created_at: datetime \| None=None) -> TrainingRunMetadata` | [ser_lib/engine/lineage.py:94](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/lineage.py:94) | 构造 lineage DTO；不执行任何文件系统或数据集探测。 |

### ser_lib/engine/objectives.py

处理：**拆分**。目标：`原路径 + ser_lib/config/training.py`。理由：LossConfig/SamplingConfig 中央化，计算不搬。

直接 import 消费者（含测试；从公共包重导入的间接消费者还需沿 D/C 展开）：

- [ser_lib/catalog.py:20](D:/projects/Speech-Emotion-Recognition/ser_lib/catalog.py:20)；行 20
- [ser_lib/engine/__init__.py:65](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/__init__.py:65)；行 65
- [ser_lib/engine/_trainer_core.py:235](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/_trainer_core.py:235)；行 235
- [ser_lib/engine/config.py:13](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/config.py:13)；行 13

| class/function/method | 定义行 | 职责说明（源码 docstring） |
| --- | --- | --- |
| `LossConfig` | [ser_lib/engine/objectives.py:16](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/objectives.py:16) | 领域/公开定义 |
| `LossConfig._validate_weights(self) -> 'LossConfig'` | [ser_lib/engine/objectives.py:23](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/objectives.py:23) |  |
| `SamplingConfig` | [ser_lib/engine/objectives.py:31](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/objectives.py:31) | 领域/公开定义 |
| `SamplingConfig._validate_options(self) -> 'SamplingConfig'` | [ser_lib/engine/objectives.py:38](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/objectives.py:38) |  |
| `ClassificationLoss` | [ser_lib/engine/objectives.py:48](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/objectives.py:48) | 领域/公开定义 |
| `ClassificationLoss.__init__(self, config: LossConfig, num_classes: int) -> None` | [ser_lib/engine/objectives.py:49](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/objectives.py:49) |  |
| `ClassificationLoss.forward(self, logits: torch.Tensor, targets: torch.Tensor) -> torch.Tensor` | [ser_lib/engine/objectives.py:62](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/objectives.py:62) |  |
| `build_weighted_sampler(labels: Sequence[int \| None], *, num_classes: int, config: SamplingConfig, seed: int) -> WeightedRandomSampler \| None` | [ser_lib/engine/objectives.py:76](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/objectives.py:76) | 领域/公开定义 |

### ser_lib/engine/optim.py

处理：**拆分**。目标：`原路径 + ser_lib/config/{optimizer,scheduler}.py`。理由：schema/parse 与 torch build 分离，消除 config 回引。

直接 import 消费者（含测试；从公共包重导入的间接消费者还需沿 D/C 展开）：

- [ser_lib/catalog.py:21](D:/projects/Speech-Emotion-Recognition/ser_lib/catalog.py:21)；行 21
- [ser_lib/engine/__init__.py:54](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/__init__.py:54)；行 54
- [ser_lib/engine/_trainer_core.py:32](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/_trainer_core.py:32)；行 32
- [ser_lib/engine/config.py:83](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/config.py:83)；行 83, 91
- [ser_lib/engine/trainer.py:24](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/trainer.py:24)；行 24
- [ser_lib/engine/validation.py:16](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/validation.py:16)；行 16

| class/function/method | 定义行 | 职责说明（源码 docstring） |
| --- | --- | --- |
| `AdamWConfig` | [ser_lib/engine/optim.py:13](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/optim.py:13) | 领域/公开定义 |
| `AdamConfig` | [ser_lib/engine/optim.py:22](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/optim.py:22) | 领域/公开定义 |
| `SGDConfig` | [ser_lib/engine/optim.py:31](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/optim.py:31) | 领域/公开定义 |
| `SGDConfig._validate_nesterov(self) -> 'SGDConfig'` | [ser_lib/engine/optim.py:39](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/optim.py:39) |  |
| `StepSchedulerConfig` | [ser_lib/engine/optim.py:48](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/optim.py:48) | 领域/公开定义 |
| `CosineSchedulerConfig` | [ser_lib/engine/optim.py:54](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/optim.py:54) | 领域/公开定义 |
| `parse_optimizer_config(raw: dict[str, Any]) -> OptimizerConfig` | [ser_lib/engine/optim.py:63](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/optim.py:63) | 解析白名单优化器，未知类型和参数立即失败。 |
| `build_optimizer(parameters, config: OptimizerConfig) -> torch.optim.Optimizer` | [ser_lib/engine/optim.py:77](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/optim.py:77) | 领域/公开定义 |
| `parse_scheduler_config(raw: dict[str, Any] \| None) -> SchedulerConfig \| None` | [ser_lib/engine/optim.py:97](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/optim.py:97) | 领域/公开定义 |
| `build_scheduler(optimizer: torch.optim.Optimizer, config: SchedulerConfig \| None) -> torch.optim.lr_scheduler.LRScheduler \| None` | [ser_lib/engine/optim.py:112](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/optim.py:112) | 领域/公开定义 |

### ser_lib/engine/presets.py

处理：**迁移**。目标：`ser_lib/config/presets.py`。理由：模板保留，去 ExperimentPresetCatalog 聚合壳。

直接 import 消费者（含测试；从公共包重导入的间接消费者还需沿 D/C 展开）：

- [ser_lib/engine/__init__.py:71](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/__init__.py:71)；行 71
- [ser_lib/services/catalog.py:14](D:/projects/Speech-Emotion-Recognition/ser_lib/services/catalog.py:14)；行 14

| class/function/method | 定义行 | 职责说明（源码 docstring） |
| --- | --- | --- |
| `ExperimentPresetInfo` | [ser_lib/engine/presets.py:222](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/presets.py:222) | 领域/公开定义 |
| `ExperimentPresetInfo.to_dict(self) -> dict[str, Any]` | [ser_lib/engine/presets.py:230](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/presets.py:230) |  |
| `ExperimentPresetCatalog` | [ser_lib/engine/presets.py:242](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/presets.py:242) | 领域/公开定义 |
| `ExperimentPresetCatalog.total(self) -> int` | [ser_lib/engine/presets.py:246](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/presets.py:246) |  |
| `ExperimentPresetCatalog.get(self, preset_id: str) -> ExperimentPresetInfo` | [ser_lib/engine/presets.py:249](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/presets.py:249) |  |
| `ExperimentPresetCatalog.to_dict(self) -> dict[str, Any]` | [ser_lib/engine/presets.py:255](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/presets.py:255) |  |
| `list_experiment_presets() -> ExperimentPresetCatalog` | [ser_lib/engine/presets.py:262](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/presets.py:262) | 枚举稳定 preset；只做配置模型校验，不创建模型或分配设备。 |
| `get_experiment_preset(preset_id: str) -> ExperimentPresetInfo` | [ser_lib/engine/presets.py:281](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/presets.py:281) | 领域/公开定义 |
| `build_experiment_config(preset_id: str, overrides: Mapping[str, Any] \| None=None) -> ExperimentConfig` | [ser_lib/engine/presets.py:285](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/presets.py:285) | 从 preset 构造唯一的 ExperimentConfig；override 后重新执行严格校验。 |
| `_deep_merge(target: dict[str, Any], updates: Mapping[str, Any]) -> None` | [ser_lib/engine/presets.py:299](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/presets.py:299) | 见实现；私有辅助 |

### ser_lib/engine/runs.py

处理：**拆分**。目标：`原路径 + ser_lib/engine/migrations.py`。理由：删除 TrainingRunDetail；run.json/read/write/scan 保留。

直接 import 消费者（含测试；从公共包重导入的间接消费者还需沿 D/C 展开）：

- [ser_lib/engine/__init__.py:79](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/__init__.py:79)；行 79
- [ser_lib/services/training.py:19](D:/projects/Speech-Emotion-Recognition/ser_lib/services/training.py:19)；行 19

| class/function/method | 定义行 | 职责说明（源码 docstring） |
| --- | --- | --- |
| `_RunRecordModel` | [ser_lib/engine/runs.py:26](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/runs.py:26) | run.json 的严格磁盘 schema；额外字段会被拒绝。 |
| `_RunRecordModel._require_timezone(cls, value: datetime) -> datetime` | [ser_lib/engine/runs.py:57](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/runs.py:57) |  |
| `TrainingRunInfo` | [ser_lib/engine/runs.py:64](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/runs.py:64) | Web 历史列表/详情共用的轻量、JSON-safe 训练记录。 |
| `TrainingRunInfo.to_dict(self) -> dict[str, Any]` | [ser_lib/engine/runs.py:90](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/runs.py:90) |  |
| `TrainingRunInfo.from_training(cls, directory: Path \| str, metadata: TrainingRunMetadata, result: TrainingResult) -> 'TrainingRunInfo'` | [ser_lib/engine/runs.py:97](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/runs.py:97) |  |
| `TrainingRunInfo.from_dict(cls, value: dict[str, Any], *, directory: Path \| str \| None=None) -> 'TrainingRunInfo'` | [ser_lib/engine/runs.py:135](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/runs.py:135) |  |
| `TrainingRunDetail` | [ser_lib/engine/runs.py:163](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/runs.py:163) | 训练详情页/Worker 可直接消费的轻量聚合结果。 |
| `TrainingRunDetail.to_dict(self) -> dict[str, Any]` | [ser_lib/engine/runs.py:175](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/runs.py:175) |  |
| `TrainingRunScanFailure` | [ser_lib/engine/runs.py:185](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/runs.py:185) | 领域/公开定义 |
| `TrainingRunScanFailure.to_dict(self) -> dict[str, str]` | [ser_lib/engine/runs.py:190](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/runs.py:190) |  |
| `TrainingRunCatalog` | [ser_lib/engine/runs.py:199](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/runs.py:199) | 领域/公开定义 |
| `TrainingRunCatalog.total(self) -> int` | [ser_lib/engine/runs.py:205](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/runs.py:205) |  |
| `TrainingRunCatalog.to_dict(self) -> dict[str, Any]` | [ser_lib/engine/runs.py:208](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/runs.py:208) |  |
| `write_training_run_info(directory: Path \| str, metadata: TrainingRunMetadata, result: TrainingResult) -> Path` | [ser_lib/engine/runs.py:217](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/runs.py:217) | 把终态训练记录原子写入 ``run.json``。 |
| `load_training_run_info(path: Path \| str) -> TrainingRunInfo` | [ser_lib/engine/runs.py:240](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/runs.py:240) | 读取一个 run 目录或其 ``run.json``。目录字段始终以实际位置为准。 |
| `scan_training_runs(root: Path \| str, *, recursive: bool=False, fail_fast: bool=False, event_callback: EventCallback \| None=None, cancellation: CancellationCheck \| None=None) -> TrainingRunCatalog` | [ser_lib/engine/runs.py:252](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/runs.py:252) | 轻量扫描 ``run.json``；不读取 checkpoint、不加载模型、不计算 hash。 |
| `_candidate_directories(root: Path, *, recursive: bool) -> list[Path]` | [ser_lib/engine/runs.py:287](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/runs.py:287) | 见实现；私有辅助 |

### ser_lib/engine/trainer.py

处理：**合并**。目标：`ser_lib/engine/trainer.py + ser_lib/engine/state.py`。理由：合并公开/内部继承包装；fit 直接返回 TrainingResult。

直接 import 消费者（含测试；从公共包重导入的间接消费者还需沿 D/C 展开）：

- [scripts/smoke_train_epoch.py:27](D:/projects/Speech-Emotion-Recognition/scripts/smoke_train_epoch.py:27)；行 27
- [ser_lib/engine/__init__.py:90](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/__init__.py:90)；行 90
- [ser_lib/engine/evaluator.py:24](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/evaluator.py:24)；行 24
- [ser_lib/engine/runs.py:20](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/runs.py:20)；行 20
- [ser_lib/engine/training_history.py:13](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/training_history.py:13)；行 13
- [ser_lib/inference/offline.py:12](D:/projects/Speech-Emotion-Recognition/ser_lib/inference/offline.py:12)；行 12
- [ser_lib/services/training.py:28](D:/projects/Speech-Emotion-Recognition/ser_lib/services/training.py:28)；行 28
- [tests/test_model_engine.py:19](D:/projects/Speech-Emotion-Recognition/tests/test_model_engine.py:19)；行 19

| class/function/method | 定义行 | 职责说明（源码 docstring） |
| --- | --- | --- |
| `Trainer` | [ser_lib/engine/trainer.py:28](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/trainer.py:28) | SER 唯一公开训练器。 |
| `Trainer.__init__(self, model: SERModel, config: TrainerConfig \| None=None, *, optimizer: torch.optim.Optimizer \| None=None, scheduler: torch.optim.lr_scheduler.LRScheduler \| None=None, loss_fn: torch.nn.Module \| None=None, event_callback: EventCallback \| None=None, cancellation: CancellationCheck \| None=None, observability: ObservabilityConfig \| None=None, run_id: str \| None=None, run_metadata: TrainingRunMetadata \| None=None) -> None` | [ser_lib/engine/trainer.py:39](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/trainer.py:39) |  |
| `Trainer.from_experiment(cls, model: SERModel, experiment: ExperimentConfig, *, event_callback: EventCallback \| None=None, cancellation: CancellationCheck \| None=None, observability: ObservabilityConfig \| None=None, run_id: str \| None=None) -> 'Trainer'` | [ser_lib/engine/trainer.py:71](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/trainer.py:71) | 按完整 ExperimentConfig 构造当前公开 Trainer 类型。 |
| `Trainer._save_checkpoint_with_event(self, path: Path, *, kind: str, epoch: int, metrics: dict[str, float], metadata: dict[str, object]) -> Path` | [ser_lib/engine/trainer.py:94](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/trainer.py:94) |  |
| `Trainer.resume_from(self, path, *, restore_rng: bool=True) -> dict` | [ser_lib/engine/trainer.py:114](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/trainer.py:114) |  |

### ser_lib/engine/training_history.py

处理：**保留**。目标：`原路径`。理由：epoch 历史和校验保留。

直接 import 消费者（含测试；从公共包重导入的间接消费者还需沿 D/C 展开）：

- [ser_lib/engine/__init__.py:89](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/__init__.py:89)；行 89
- [ser_lib/engine/runs.py:19](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/runs.py:19)；行 19
- [ser_lib/services/training.py:27](D:/projects/Speech-Emotion-Recognition/ser_lib/services/training.py:27)；行 27

| class/function/method | 定义行 | 职责说明（源码 docstring） |
| --- | --- | --- |
| `_EpochResultModel` | [ser_lib/engine/training_history.py:18](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/training_history.py:18) | CLI 已有 ``history.json`` 单个 epoch 的严格 schema。 |
| `_EpochResultModel._validate_validation_metrics(cls, value: dict[str, float] \| None) -> dict[str, float] \| None` | [ser_lib/engine/training_history.py:32](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/training_history.py:32) |  |
| `TrainingHistoryInfo` | [ser_lib/engine/training_history.py:46](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/training_history.py:46) | Web 训练曲线页可直接消费的完整 epoch 历史。 |
| `TrainingHistoryInfo.epoch_count(self) -> int` | [ser_lib/engine/training_history.py:54](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/training_history.py:54) |  |
| `TrainingHistoryInfo.to_dict(self) -> dict[str, Any]` | [ser_lib/engine/training_history.py:57](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/training_history.py:57) |  |
| `load_training_history(path: Path \| str) -> TrainingHistoryInfo` | [ser_lib/engine/training_history.py:66](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/training_history.py:66) | 读取 run 目录或其 ``history.json``；不读取 checkpoint / metrics.jsonl。 |

### ser_lib/engine/validation.py

处理：**瘦身**。目标：`原路径 + ser_lib/engine/compatibility.py`。理由：预检保留，summary 去重复，补 adapter capability。

直接 import 消费者（含测试；从公共包重导入的间接消费者还需沿 D/C 展开）：

- [ser_lib/engine/__init__.py:97](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/__init__.py:97)；行 97
- [ser_lib/services/training.py:29](D:/projects/Speech-Emotion-Recognition/ser_lib/services/training.py:29)；行 29

| class/function/method | 定义行 | 职责说明（源码 docstring） |
| --- | --- | --- |
| `ExperimentValidationResult` | [ser_lib/engine/validation.py:21](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/validation.py:21) | Web/CLI 可直接消费的实验 dry-run 结果。 |
| `ExperimentValidationResult.to_dict(self) -> dict[str, Any]` | [ser_lib/engine/validation.py:29](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/validation.py:29) |  |
| `_diagnostic(code: str, message: str, *, field: str \| None=None, path: Path \| str \| None=None, suggestion: str \| None=None, details: dict[str, Any] \| None=None) -> Diagnostic` | [ser_lib/engine/validation.py:38](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/validation.py:38) | 见实现；私有辅助 |
| `_load_config(value: ExperimentConfig \| Path \| str) -> tuple[ExperimentConfig \| None, list[Diagnostic]]` | [ser_lib/engine/validation.py:59](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/validation.py:59) | 见实现；私有辅助 |
| `_inspect_manifest(config: ExperimentConfig, diagnostics: list[Diagnostic]) -> ManifestMeta \| None` | [ser_lib/engine/validation.py:79](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/validation.py:79) | 见实现；私有辅助 |
| `_inspect_pipeline(config: ExperimentConfig, diagnostics: list[Diagnostic]) -> SamplePipeline \| None` | [ser_lib/engine/validation.py:176](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/validation.py:176) | 见实现；私有辅助 |
| `_inspect_model_spec(config: ExperimentConfig, diagnostics: list[Diagnostic]) -> tuple[ModelSpec \| None, dict[str, Any] \| None]` | [ser_lib/engine/validation.py:200](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/validation.py:200) | 见实现；私有辅助 |
| `_inspect_training_options(config: ExperimentConfig, *, num_classes: int \| None, diagnostics: list[Diagnostic]) -> tuple[dict[str, Any] \| None, dict[str, Any] \| None]` | [ser_lib/engine/validation.py:223](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/validation.py:223) | 见实现；私有辅助 |
| `_inspect_paths_and_device(config: ExperimentConfig, diagnostics: list[Diagnostic]) -> str \| None` | [ser_lib/engine/validation.py:285](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/validation.py:285) | 见实现；私有辅助 |
| `_spec_summary(pipeline: SamplePipeline \| None) -> dict[str, Any]` | [ser_lib/engine/validation.py:348](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/validation.py:348) | 见实现；私有辅助 |
| `validate_experiment(config: ExperimentConfig \| Path \| str) -> ExperimentValidationResult` | [ser_lib/engine/validation.py:361](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/validation.py:361) | 执行训练前 dry-run，不加载样本、不创建模型、不分配 GPU。 |

### ser_lib/inference/__init__.py

处理：**瘦身**。目标：`原路径`。理由：更新 config/退役包装导出及内置注册顺序，不改变算法。

直接 import 消费者（含测试；从公共包重导入的间接消费者还需沿 D/C 展开）：

- [examples/predict_artifact.py:9](D:/projects/Speech-Emotion-Recognition/examples/predict_artifact.py:9)；行 9
- [ser_lib/__init__.py:82](D:/projects/Speech-Emotion-Recognition/ser_lib/__init__.py:82)；行 82
- [tests/test_batch_inference.py:21](D:/projects/Speech-Emotion-Recognition/tests/test_batch_inference.py:21)；行 21
- [tests/test_batch_prediction_events.py:6](D:/projects/Speech-Emotion-Recognition/tests/test_batch_prediction_events.py:6)；行 6
- [tests/test_batch_prediction_sink.py:9](D:/projects/Speech-Emotion-Recognition/tests/test_batch_prediction_sink.py:9)；行 9
- [tests/test_public_api.py:10](D:/projects/Speech-Emotion-Recognition/tests/test_public_api.py:10)；行 10
- [tests/test_streaming_inference.py:8](D:/projects/Speech-Emotion-Recognition/tests/test_streaming_inference.py:8)；行 8

| class/function/method | 定义行 | 职责说明（源码 docstring） |
| --- | --- | --- |

### ser_lib/inference/batch.py

处理：**保留**。目标：`原路径`。理由：批量与 sink/有限内存保留，Service 改直接调用。

直接 import 消费者（含测试；从公共包重导入的间接消费者还需沿 D/C 展开）：

- [ser_lib/inference/__init__.py:1](D:/projects/Speech-Emotion-Recognition/ser_lib/inference/__init__.py:1)；行 1
- [ser_lib/services/inference.py:12](D:/projects/Speech-Emotion-Recognition/ser_lib/services/inference.py:12)；行 12

| class/function/method | 定义行 | 职责说明（源码 docstring） |
| --- | --- | --- |
| `PredictionFailure` | [ser_lib/inference/batch.py:29](D:/projects/Speech-Emotion-Recognition/ser_lib/inference/batch.py:29) | 领域/公开定义 |
| `PredictionFailure.to_dict(self) -> dict[str, object]` | [ser_lib/inference/batch.py:35](D:/projects/Speech-Emotion-Recognition/ser_lib/inference/batch.py:35) |  |
| `BatchPredictionSink` | [ser_lib/inference/batch.py:39](D:/projects/Speech-Emotion-Recognition/ser_lib/inference/batch.py:39) | 批量推理逐条结果消费者；生命周期由调用方管理。 |
| `BatchPredictionSink.write_prediction(self, result: PredictionResult) -> None` | [ser_lib/inference/batch.py:42](D:/projects/Speech-Emotion-Recognition/ser_lib/inference/batch.py:42) |  |
| `BatchPredictionSink.write_failure(self, failure: PredictionFailure) -> None` | [ser_lib/inference/batch.py:45](D:/projects/Speech-Emotion-Recognition/ser_lib/inference/batch.py:45) |  |
| `JsonlBatchPredictionSink` | [ser_lib/inference/batch.py:49](D:/projects/Speech-Emotion-Recognition/ser_lib/inference/batch.py:49) | 把批量推理结果增量写入 JSONL，避免完整结果常驻内存。 |
| `JsonlBatchPredictionSink.__init__(self, path: Path \| str, *, append: bool=False, flush_each: bool=False) -> None` | [ser_lib/inference/batch.py:52](D:/projects/Speech-Emotion-Recognition/ser_lib/inference/batch.py:52) |  |
| `JsonlBatchPredictionSink._write(self, row: dict[str, object]) -> None` | [ser_lib/inference/batch.py:68](D:/projects/Speech-Emotion-Recognition/ser_lib/inference/batch.py:68) |  |
| `JsonlBatchPredictionSink.write_prediction(self, result: PredictionResult) -> None` | [ser_lib/inference/batch.py:75](D:/projects/Speech-Emotion-Recognition/ser_lib/inference/batch.py:75) |  |
| `JsonlBatchPredictionSink.write_failure(self, failure: PredictionFailure) -> None` | [ser_lib/inference/batch.py:78](D:/projects/Speech-Emotion-Recognition/ser_lib/inference/batch.py:78) |  |
| `JsonlBatchPredictionSink.flush(self) -> None` | [ser_lib/inference/batch.py:81](D:/projects/Speech-Emotion-Recognition/ser_lib/inference/batch.py:81) |  |
| `JsonlBatchPredictionSink.close(self) -> None` | [ser_lib/inference/batch.py:85](D:/projects/Speech-Emotion-Recognition/ser_lib/inference/batch.py:85) |  |
| `JsonlBatchPredictionSink.__enter__(self) -> 'JsonlBatchPredictionSink'` | [ser_lib/inference/batch.py:89](D:/projects/Speech-Emotion-Recognition/ser_lib/inference/batch.py:89) |  |
| `JsonlBatchPredictionSink.__exit__(self, exc_type: object, exc: object, traceback: object) -> None` | [ser_lib/inference/batch.py:92](D:/projects/Speech-Emotion-Recognition/ser_lib/inference/batch.py:92) |  |
| `BatchPredictionResult` | [ser_lib/inference/batch.py:97](D:/projects/Speech-Emotion-Recognition/ser_lib/inference/batch.py:97) | 领域/公开定义 |
| `BatchPredictionResult.__post_init__(self) -> None` | [ser_lib/inference/batch.py:104](D:/projects/Speech-Emotion-Recognition/ser_lib/inference/batch.py:104) |  |
| `BatchPredictionResult.succeeded(self) -> int` | [ser_lib/inference/batch.py:115](D:/projects/Speech-Emotion-Recognition/ser_lib/inference/batch.py:115) |  |
| `BatchPredictionResult.failed(self) -> int` | [ser_lib/inference/batch.py:119](D:/projects/Speech-Emotion-Recognition/ser_lib/inference/batch.py:119) |  |
| `BatchPredictionResult.retained_results(self) -> int` | [ser_lib/inference/batch.py:123](D:/projects/Speech-Emotion-Recognition/ser_lib/inference/batch.py:123) |  |
| `BatchPredictionResult.to_dict(self) -> dict[str, object]` | [ser_lib/inference/batch.py:126](D:/projects/Speech-Emotion-Recognition/ser_lib/inference/batch.py:126) |  |
| `_safe_len(value: object) -> int \| None` | [ser_lib/inference/batch.py:137](D:/projects/Speech-Emotion-Recognition/ser_lib/inference/batch.py:137) | 见实现；私有辅助 |
| `_iter_chunks(records: Iterable[AudioRecord], batch_size: int) -> Iterator[list[AudioRecord]]` | [ser_lib/inference/batch.py:146](D:/projects/Speech-Emotion-Recognition/ser_lib/inference/batch.py:146) | 见实现；私有辅助 |
| `BatchEmotionPredictor` | [ser_lib/inference/batch.py:155](D:/projects/Speech-Emotion-Recognition/ser_lib/inference/batch.py:155) | 在单文件预测器之上提供来源枚举、增量事件和逐条失败策略。 |
| `BatchEmotionPredictor.__init__(self, predictor: EmotionPredictor) -> None` | [ser_lib/inference/batch.py:158](D:/projects/Speech-Emotion-Recognition/ser_lib/inference/batch.py:158) |  |
| `BatchEmotionPredictor.predict_records(self, records: Iterable[AudioRecord], *, fail_fast: bool=True, batch_size: int=16, total: int \| None=None, result_sink: BatchPredictionSink \| None=None, retain_results: bool=True, event_callback: EventCallback \| None=None, cancellation: CancellationCheck \| None=None, event_context: EventContext \| None=None) -> BatchPredictionResult` | [ser_lib/inference/batch.py:161](D:/projects/Speech-Emotion-Recognition/ser_lib/inference/batch.py:161) | 批量预测，并支持流式 Iterable 与增量结果 sink。 |
| `BatchEmotionPredictor.predict_files(self, paths: Iterable[Path \| str], **kwargs) -> BatchPredictionResult` | [ser_lib/inference/batch.py:294](D:/projects/Speech-Emotion-Recognition/ser_lib/inference/batch.py:294) |  |
| `BatchEmotionPredictor.predict_directory(self, directory: Path \| str, *, recursive: bool=True, extensions: Sequence[str] \| None=None, **kwargs) -> BatchPredictionResult` | [ser_lib/inference/batch.py:311](D:/projects/Speech-Emotion-Recognition/ser_lib/inference/batch.py:311) |  |
| `BatchEmotionPredictor.predict_manifest(self, manifest: DatasetManifest \| Path \| str, *, split: str \| None=None, **kwargs) -> BatchPredictionResult` | [ser_lib/inference/batch.py:337](D:/projects/Speech-Emotion-Recognition/ser_lib/inference/batch.py:337) |  |
| `write_batch_predictions(path: Path \| str, result: BatchPredictionResult, *, format: Literal['jsonl', 'csv'] \| None=None) -> Path` | [ser_lib/inference/batch.py:352](D:/projects/Speech-Emotion-Recognition/ser_lib/inference/batch.py:352) | 原子写入内存中保留的完整批量结果。 |

### ser_lib/inference/offline.py

处理：**重构**。目标：`原路径`。理由：预测核心保留，接回 from_loaded_artifact 便利构造。

直接 import 消费者（含测试；从公共包重导入的间接消费者还需沿 D/C 展开）：

- [ser_lib/inference/__init__.py:9](D:/projects/Speech-Emotion-Recognition/ser_lib/inference/__init__.py:9)；行 9
- [ser_lib/inference/batch.py:22](D:/projects/Speech-Emotion-Recognition/ser_lib/inference/batch.py:22)；行 22
- [ser_lib/inference/streaming.py:12](D:/projects/Speech-Emotion-Recognition/ser_lib/inference/streaming.py:12)；行 12
- [ser_lib/services/inference.py:18](D:/projects/Speech-Emotion-Recognition/ser_lib/services/inference.py:18)；行 18
- [tests/test_model_engine.py:23](D:/projects/Speech-Emotion-Recognition/tests/test_model_engine.py:23)；行 23

| class/function/method | 定义行 | 职责说明（源码 docstring） |
| --- | --- | --- |
| `PredictionResult` | [ser_lib/inference/offline.py:16](D:/projects/Speech-Emotion-Recognition/ser_lib/inference/offline.py:16) | 领域/公开定义 |
| `EmotionPredictor` | [ser_lib/inference/offline.py:23](D:/projects/Speech-Emotion-Recognition/ser_lib/inference/offline.py:23) | 领域/公开定义 |
| `EmotionPredictor.__init__(self, model: SERModel, audio_loader: AudioLoader, pipeline: SamplePipeline, collator: SERCollator, labels: Mapping[int, str] \| None=None, *, device: str \| torch.device='cpu', window_aggregation: Literal['mean_logits', 'mean_probabilities', 'max_confidence'] \| None=None) -> None` | [ser_lib/inference/offline.py:24](D:/projects/Speech-Emotion-Recognition/ser_lib/inference/offline.py:24) |  |
| `EmotionPredictor.predict_file(self, path: Path \| str, *, uid: str \| None=None) -> PredictionResult` | [ser_lib/inference/offline.py:38](D:/projects/Speech-Emotion-Recognition/ser_lib/inference/offline.py:38) |  |
| `EmotionPredictor.predict_record(self, record: AudioRecord) -> PredictionResult` | [ser_lib/inference/offline.py:44](D:/projects/Speech-Emotion-Recognition/ser_lib/inference/offline.py:44) | 预测已解析路径的记录，并保留 UID 与片段范围。 |
| `EmotionPredictor.predict_audio(self, audio: AudioData, *, uid: str='stream') -> PredictionResult` | [ser_lib/inference/offline.py:49](D:/projects/Speech-Emotion-Recognition/ser_lib/inference/offline.py:49) | 预测已在内存中的标准 AudioData，供流式核心等调用方复用。 |
| `EmotionPredictor.predict_records(self, records: Sequence[AudioRecord]) -> list[PredictionResult]` | [ser_lib/inference/offline.py:57](D:/projects/Speech-Emotion-Recognition/ser_lib/inference/offline.py:57) | 在一次模型 forward 中预测多个记录，并正确聚合各自的滑窗。 |
| `EmotionPredictor._predict_samples(self, samples, records) -> list[PredictionResult]` | [ser_lib/inference/offline.py:67](D:/projects/Speech-Emotion-Recognition/ser_lib/inference/offline.py:67) |  |
| `EmotionPredictor._aggregate(self, logits: torch.Tensor) -> torch.Tensor` | [ser_lib/inference/offline.py:96](D:/projects/Speech-Emotion-Recognition/ser_lib/inference/offline.py:96) |  |

### ser_lib/inference/streaming.py

处理：**拆分**。目标：`原路径 + ser_lib/config/inference.py`。理由：PCM 流式核心保留，StreamingConfig 中央化。

直接 import 消费者（含测试；从公共包重导入的间接消费者还需沿 D/C 展开）：

- [ser_lib/inference/__init__.py:10](D:/projects/Speech-Emotion-Recognition/ser_lib/inference/__init__.py:10)；行 10
- [ser_lib/services/inference.py:19](D:/projects/Speech-Emotion-Recognition/ser_lib/services/inference.py:19)；行 19

| class/function/method | 定义行 | 职责说明（源码 docstring） |
| --- | --- | --- |
| `StreamingConfig` | [ser_lib/inference/streaming.py:16](D:/projects/Speech-Emotion-Recognition/ser_lib/inference/streaming.py:16) | 领域/公开定义 |
| `StreamingConfig.__post_init__(self) -> None` | [ser_lib/inference/streaming.py:25](D:/projects/Speech-Emotion-Recognition/ser_lib/inference/streaming.py:25) |  |
| `StreamingPrediction` | [ser_lib/inference/streaming.py:41](D:/projects/Speech-Emotion-Recognition/ser_lib/inference/streaming.py:41) | 领域/公开定义 |
| `StreamingLatency` | [ser_lib/inference/streaming.py:51](D:/projects/Speech-Emotion-Recognition/ser_lib/inference/streaming.py:51) | 领域/公开定义 |
| `_LinearResampler` | [ser_lib/inference/streaming.py:58](D:/projects/Speech-Emotion-Recognition/ser_lib/inference/streaming.py:58) | 分块方式无关、仅保留下一插值点所需状态的线性重采样器。 |
| `_LinearResampler.__init__(self, source_rate: int, target_rate: int) -> None` | [ser_lib/inference/streaming.py:61](D:/projects/Speech-Emotion-Recognition/ser_lib/inference/streaming.py:61) |  |
| `_LinearResampler.push(self, samples: torch.Tensor, *, final: bool=False) -> torch.Tensor` | [ser_lib/inference/streaming.py:69](D:/projects/Speech-Emotion-Recognition/ser_lib/inference/streaming.py:69) |  |
| `_LinearResampler.reset(self) -> None` | [ser_lib/inference/streaming.py:99](D:/projects/Speech-Emotion-Recognition/ser_lib/inference/streaming.py:99) |  |
| `StreamingEmotionRecognizer` | [ser_lib/inference/streaming.py:106](D:/projects/Speech-Emotion-Recognition/ser_lib/inference/streaming.py:106) | 同步消费 PCM，并为每个完整窗口返回一次预测。 |
| `StreamingEmotionRecognizer.__init__(self, predictor: EmotionPredictor, config: StreamingConfig) -> None` | [ser_lib/inference/streaming.py:109](D:/projects/Speech-Emotion-Recognition/ser_lib/inference/streaming.py:109) |  |
| `StreamingEmotionRecognizer.buffered_samples(self) -> int` | [ser_lib/inference/streaming.py:126](D:/projects/Speech-Emotion-Recognition/ser_lib/inference/streaming.py:126) |  |
| `StreamingEmotionRecognizer.latency(self) -> StreamingLatency` | [ser_lib/inference/streaming.py:130](D:/projects/Speech-Emotion-Recognition/ser_lib/inference/streaming.py:130) |  |
| `StreamingEmotionRecognizer.push_pcm(self, pcm: torch.Tensor \| Sequence[float]) -> list[StreamingPrediction]` | [ser_lib/inference/streaming.py:139](D:/projects/Speech-Emotion-Recognition/ser_lib/inference/streaming.py:139) |  |
| `StreamingEmotionRecognizer.flush(self, *, pad_final: bool=False) -> list[StreamingPrediction]` | [ser_lib/inference/streaming.py:159](D:/projects/Speech-Emotion-Recognition/ser_lib/inference/streaming.py:159) |  |
| `StreamingEmotionRecognizer._drain(self) -> list[StreamingPrediction]` | [ser_lib/inference/streaming.py:177](D:/projects/Speech-Emotion-Recognition/ser_lib/inference/streaming.py:177) |  |
| `StreamingEmotionRecognizer._predict_window(self, window: torch.Tensor) -> StreamingPrediction` | [ser_lib/inference/streaming.py:186](D:/projects/Speech-Emotion-Recognition/ser_lib/inference/streaming.py:186) |  |
| `StreamingEmotionRecognizer.reset(self) -> None` | [ser_lib/inference/streaming.py:217](D:/projects/Speech-Emotion-Recognition/ser_lib/inference/streaming.py:217) |  |
| `StreamingEmotionRecognizer.close(self) -> None` | [ser_lib/inference/streaming.py:227](D:/projects/Speech-Emotion-Recognition/ser_lib/inference/streaming.py:227) |  |

### ser_lib/models/__init__.py

处理：**瘦身**。目标：`原路径`。理由：更新 config/退役包装导出及内置注册顺序，不改变算法。

直接 import 消费者（含测试；从公共包重导入的间接消费者还需沿 D/C 展开）：

- [ser_lib/__init__.py:96](D:/projects/Speech-Emotion-Recognition/ser_lib/__init__.py:96)；行 96
- [ser_lib/catalog.py:17](D:/projects/Speech-Emotion-Recognition/ser_lib/catalog.py:17)；行 17
- [ser_lib/cli/main.py:23](D:/projects/Speech-Emotion-Recognition/ser_lib/cli/main.py:23)；行 23
- [tests/test_artifact_catalog.py:7](D:/projects/Speech-Emotion-Recognition/tests/test_artifact_catalog.py:7)；行 7
- [tests/test_artifact_inspect.py:12](D:/projects/Speech-Emotion-Recognition/tests/test_artifact_inspect.py:12)；行 12
- [tests/test_artifact_progress.py:13](D:/projects/Speech-Emotion-Recognition/tests/test_artifact_progress.py:13)；行 13
- [tests/test_artifacts.py:16](D:/projects/Speech-Emotion-Recognition/tests/test_artifacts.py:16)；行 16
- [tests/test_batch_inference.py:27](D:/projects/Speech-Emotion-Recognition/tests/test_batch_inference.py:27)；行 27
- [tests/test_checkpoint_resume.py:20](D:/projects/Speech-Emotion-Recognition/tests/test_checkpoint_resume.py:20)；行 20
- [tests/test_engine_config.py:23](D:/projects/Speech-Emotion-Recognition/tests/test_engine_config.py:23)；行 23
- [tests/test_evaluation_prediction_sink.py:10](D:/projects/Speech-Emotion-Recognition/tests/test_evaluation_prediction_sink.py:10)；行 10
- [tests/test_evaluator_observability.py:19](D:/projects/Speech-Emotion-Recognition/tests/test_evaluator_observability.py:19)；行 19
- [tests/test_evaluator_reports.py:18](D:/projects/Speech-Emotion-Recognition/tests/test_evaluator_reports.py:18)；行 18
- [tests/test_pretrained_adapter.py:22](D:/projects/Speech-Emotion-Recognition/tests/test_pretrained_adapter.py:22)；行 22
- [tests/test_public_api.py:11](D:/projects/Speech-Emotion-Recognition/tests/test_public_api.py:11)；行 11
- [tests/test_rnn_models.py:13](D:/projects/Speech-Emotion-Recognition/tests/test_rnn_models.py:13)；行 13
- [tests/test_services.py:10](D:/projects/Speech-Emotion-Recognition/tests/test_services.py:10)；行 10
- [tests/test_trainer_observability.py:19](D:/projects/Speech-Emotion-Recognition/tests/test_trainer_observability.py:19)；行 19
- [tests/test_training_lineage.py:12](D:/projects/Speech-Emotion-Recognition/tests/test_training_lineage.py:12)；行 12
- [tests/test_training_result.py:13](D:/projects/Speech-Emotion-Recognition/tests/test_training_result.py:13)；行 13
- [tests/test_training_run_catalog.py:23](D:/projects/Speech-Emotion-Recognition/tests/test_training_run_catalog.py:23)；行 23
- [tests/test_transformer_models.py:13](D:/projects/Speech-Emotion-Recognition/tests/test_transformer_models.py:13)；行 13

| class/function/method | 定义行 | 职责说明（源码 docstring） |
| --- | --- | --- |

### ser_lib/models/base.py

处理：**保留**。目标：`原路径 + ser_lib/models/specs.py`。理由：统一输出已有；不建立第二套执行契约。

直接 import 消费者（含测试；从公共包重导入的间接消费者还需沿 D/C 展开）：

- [ser_lib/artifacts/exporter.py:27](D:/projects/Speech-Emotion-Recognition/ser_lib/artifacts/exporter.py:27)；行 27
- [ser_lib/artifacts/loader.py:30](D:/projects/Speech-Emotion-Recognition/ser_lib/artifacts/loader.py:30)；行 30
- [ser_lib/engine/_trainer_core.py:39](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/_trainer_core.py:39)；行 39
- [ser_lib/engine/checkpoint.py:11](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/checkpoint.py:11)；行 11
- [ser_lib/engine/config.py:19](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/config.py:19)；行 19
- [ser_lib/engine/evaluator.py:25](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/evaluator.py:25)；行 25
- [ser_lib/engine/trainer.py:25](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/trainer.py:25)；行 25
- [ser_lib/inference/offline.py:13](D:/projects/Speech-Emotion-Recognition/ser_lib/inference/offline.py:13)；行 13
- [ser_lib/models/__init__.py:1](D:/projects/Speech-Emotion-Recognition/ser_lib/models/__init__.py:1)；行 1
- [ser_lib/models/cnn_models.py:14](D:/projects/Speech-Emotion-Recognition/ser_lib/models/cnn_models.py:14)；行 14
- [ser_lib/models/pretrained.py:16](D:/projects/Speech-Emotion-Recognition/ser_lib/models/pretrained.py:16)；行 16
- [ser_lib/models/registry.py:10](D:/projects/Speech-Emotion-Recognition/ser_lib/models/registry.py:10)；行 10
- [ser_lib/models/rnn_models.py:15](D:/projects/Speech-Emotion-Recognition/ser_lib/models/rnn_models.py:15)；行 15
- [ser_lib/models/transformer_models.py:15](D:/projects/Speech-Emotion-Recognition/ser_lib/models/transformer_models.py:15)；行 15
- [ser_lib/services/artifacts.py:25](D:/projects/Speech-Emotion-Recognition/ser_lib/services/artifacts.py:25)；行 25
- [ser_lib/services/evaluation.py:38](D:/projects/Speech-Emotion-Recognition/ser_lib/services/evaluation.py:38)；行 38
- [ser_lib/services/training.py:30](D:/projects/Speech-Emotion-Recognition/ser_lib/services/training.py:30)；行 30
- [tests/test_model_engine.py:20](D:/projects/Speech-Emotion-Recognition/tests/test_model_engine.py:20)；行 20

| class/function/method | 定义行 | 职责说明（源码 docstring） |
| --- | --- | --- |
| `ModelOutput` | [ser_lib/models/base.py:13](D:/projects/Speech-Emotion-Recognition/ser_lib/models/base.py:13) | 所有 SER 模型的标准输出。 |
| `ModelOutput.__post_init__(self) -> None` | [ser_lib/models/base.py:25](D:/projects/Speech-Emotion-Recognition/ser_lib/models/base.py:25) |  |
| `SERModel` | [ser_lib/models/base.py:42](D:/projects/Speech-Emotion-Recognition/ser_lib/models/base.py:42) | 所有内置及第三方适配模型必须实现的最小稳定接口。 |
| `SERModel.model_spec(self) -> ModelSpec` | [ser_lib/models/base.py:47](D:/projects/Speech-Emotion-Recognition/ser_lib/models/base.py:47) |  |
| `SERModel.model_config(self) -> dict[str, Any]` | [ser_lib/models/base.py:51](D:/projects/Speech-Emotion-Recognition/ser_lib/models/base.py:51) | 返回可 JSON 序列化、可用于注册表重建模型的完整配置。 |
| `SERModel.parameter_count(self, *, trainable_only: bool=False) -> int` | [ser_lib/models/base.py:55](D:/projects/Speech-Emotion-Recognition/ser_lib/models/base.py:55) | 返回模型参数量；可限制为需要梯度的参数。 |
| `SERModel.forward(self, batch: SERBatch) -> ModelOutput` | [ser_lib/models/base.py:64](D:/projects/Speech-Emotion-Recognition/ser_lib/models/base.py:64) |  |

### ser_lib/models/cnn_models.py

处理：**拆分**。目标：`原路径 + ser_lib/config/model.py`。理由：原生模型保留，仅配置定义中央化。

直接 import 消费者（含测试；从公共包重导入的间接消费者还需沿 D/C 展开）：

- [scripts/smoke_train_epoch.py:28](D:/projects/Speech-Emotion-Recognition/scripts/smoke_train_epoch.py:28)；行 28
- [ser_lib/models/__init__.py:2](D:/projects/Speech-Emotion-Recognition/ser_lib/models/__init__.py:2)；行 2
- [tests/test_model_engine.py:21](D:/projects/Speech-Emotion-Recognition/tests/test_model_engine.py:21)；行 21

| class/function/method | 定义行 | 职责说明（源码 docstring） |
| --- | --- | --- |
| `CNNBaselineConfig` | [ser_lib/models/cnn_models.py:18](D:/projects/Speech-Emotion-Recognition/ser_lib/models/cnn_models.py:18) | 领域/公开定义 |
| `CNNBaseline` | [ser_lib/models/cnn_models.py:25](D:/projects/Speech-Emotion-Recognition/ser_lib/models/cnn_models.py:25) | 保持时间分辨率的一维卷积分类器。 |
| `CNNBaseline.__init__(self, feature_dim: int, num_classes: int, hidden_dim: int=128, dropout: float=0.2) -> None` | [ser_lib/models/cnn_models.py:32](D:/projects/Speech-Emotion-Recognition/ser_lib/models/cnn_models.py:32) |  |
| `CNNBaseline.model_spec(self) -> ModelSpec` | [ser_lib/models/cnn_models.py:59](D:/projects/Speech-Emotion-Recognition/ser_lib/models/cnn_models.py:59) |  |
| `CNNBaseline.model_config(self) -> dict[str, int \| float]` | [ser_lib/models/cnn_models.py:63](D:/projects/Speech-Emotion-Recognition/ser_lib/models/cnn_models.py:63) |  |
| `CNNBaseline.forward(self, batch: SERBatch) -> ModelOutput` | [ser_lib/models/cnn_models.py:71](D:/projects/Speech-Emotion-Recognition/ser_lib/models/cnn_models.py:71) |  |
| `_model_spec_from_config(params: dict[str, Any]) -> ModelSpec` | [ser_lib/models/cnn_models.py:101](D:/projects/Speech-Emotion-Recognition/ser_lib/models/cnn_models.py:101) | 见实现；私有辅助 |

### ser_lib/models/pretrained.py

处理：**拆分**。目标：`ser_lib/models/adapters/huggingface.py + ser_lib/config/model.py`。理由：保留注册 ID/旧重建语义，补 processor/真实长度映射。

直接 import 消费者（含测试；从公共包重导入的间接消费者还需沿 D/C 展开）：

- [ser_lib/models/__init__.py:5](D:/projects/Speech-Emotion-Recognition/ser_lib/models/__init__.py:5)；行 5

| class/function/method | 定义行 | 职责说明（源码 docstring） |
| --- | --- | --- |
| `HFAudioClassifierConfig` | [ser_lib/models/pretrained.py:20](D:/projects/Speech-Emotion-Recognition/ser_lib/models/pretrained.py:20) | 领域/公开定义 |
| `HFAudioClassifierConfig._exactly_one_encoder_source(self) -> 'HFAudioClassifierConfig'` | [ser_lib/models/pretrained.py:32](D:/projects/Speech-Emotion-Recognition/ser_lib/models/pretrained.py:32) |  |
| `_transformers()` | [ser_lib/models/pretrained.py:45](D:/projects/Speech-Emotion-Recognition/ser_lib/models/pretrained.py:45) | 见实现；私有辅助 |
| `HFAudioClassifier` | [ser_lib/models/pretrained.py:54](D:/projects/Speech-Emotion-Recognition/ser_lib/models/pretrained.py:54) | 为 Hugging Face AutoModel 语音编码器增加掩码池化与分类头。 |
| `HFAudioClassifier.__init__(self, num_classes: int, pretrained_model_name_or_path: str \| None=None, encoder_config: dict[str, Any] \| None=None, local_files_only: bool=True, revision: str \| None=None, freeze_encoder: bool=False, dropout: float=0.1, pooling: Literal['mean', 'max']='mean', expected_sample_rate: int=16000) -> None` | [ser_lib/models/pretrained.py:61](D:/projects/Speech-Emotion-Recognition/ser_lib/models/pretrained.py:61) |  |
| `HFAudioClassifier.model_spec(self) -> ModelSpec` | [ser_lib/models/pretrained.py:121](D:/projects/Speech-Emotion-Recognition/ser_lib/models/pretrained.py:121) |  |
| `HFAudioClassifier.model_config(self) -> dict[str, Any]` | [ser_lib/models/pretrained.py:125](D:/projects/Speech-Emotion-Recognition/ser_lib/models/pretrained.py:125) |  |
| `HFAudioClassifier.train(self, mode: bool=True) -> 'HFAudioClassifier'` | [ser_lib/models/pretrained.py:138](D:/projects/Speech-Emotion-Recognition/ser_lib/models/pretrained.py:138) |  |
| `HFAudioClassifier._mask(self, batch: SERBatch, waveform: torch.Tensor) -> torch.Tensor` | [ser_lib/models/pretrained.py:144](D:/projects/Speech-Emotion-Recognition/ser_lib/models/pretrained.py:144) |  |
| `HFAudioClassifier.forward(self, batch: SERBatch) -> ModelOutput` | [ser_lib/models/pretrained.py:169](D:/projects/Speech-Emotion-Recognition/ser_lib/models/pretrained.py:169) |  |
| `_model_spec_from_config(params: dict[str, Any]) -> ModelSpec` | [ser_lib/models/pretrained.py:199](D:/projects/Speech-Emotion-Recognition/ser_lib/models/pretrained.py:199) | 见实现；私有辅助 |

### ser_lib/models/registry.py

处理：**重构**。目标：`原路径`。理由：唯一模型注册；补 capability/plugin metadata，配置引用中央化。

直接 import 消费者（含测试；从公共包重导入的间接消费者还需沿 D/C 展开）：

- [ser_lib/artifacts/exporter.py:28](D:/projects/Speech-Emotion-Recognition/ser_lib/artifacts/exporter.py:28)；行 28
- [ser_lib/artifacts/loader.py:31](D:/projects/Speech-Emotion-Recognition/ser_lib/artifacts/loader.py:31)；行 31
- [ser_lib/catalog.py:28](D:/projects/Speech-Emotion-Recognition/ser_lib/catalog.py:28)；行 28
- [ser_lib/engine/_trainer_core.py:219](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/_trainer_core.py:219)；行 219
- [ser_lib/engine/config.py:116](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/config.py:116)；行 116
- [ser_lib/engine/validation.py:17](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/validation.py:17)；行 17
- [ser_lib/models/__init__.py:6](D:/projects/Speech-Emotion-Recognition/ser_lib/models/__init__.py:6)；行 6
- [ser_lib/models/cnn_models.py:15](D:/projects/Speech-Emotion-Recognition/ser_lib/models/cnn_models.py:15)；行 15
- [ser_lib/models/pretrained.py:17](D:/projects/Speech-Emotion-Recognition/ser_lib/models/pretrained.py:17)；行 17
- [ser_lib/models/rnn_models.py:16](D:/projects/Speech-Emotion-Recognition/ser_lib/models/rnn_models.py:16)；行 16
- [ser_lib/models/transformer_models.py:16](D:/projects/Speech-Emotion-Recognition/ser_lib/models/transformer_models.py:16)；行 16
- [tests/test_component_catalog.py:21](D:/projects/Speech-Emotion-Recognition/tests/test_component_catalog.py:21)；行 21
- [tests/test_experiment_validation.py:12](D:/projects/Speech-Emotion-Recognition/tests/test_experiment_validation.py:12)；行 12
- [tests/test_model_engine.py:22](D:/projects/Speech-Emotion-Recognition/tests/test_model_engine.py:22)；行 22

| class/function/method | 定义行 | 职责说明（源码 docstring） |
| --- | --- | --- |
| `ModelDescriptor` | [ser_lib/models/registry.py:19](D:/projects/Speech-Emotion-Recognition/ser_lib/models/registry.py:19) | 领域/公开定义 |
| `ModelDescriptor.to_json_safe(self) -> dict[str, Any]` | [ser_lib/models/registry.py:28](D:/projects/Speech-Emotion-Recognition/ser_lib/models/registry.py:28) |  |
| `_ModelEntry` | [ser_lib/models/registry.py:38](D:/projects/Speech-Emotion-Recognition/ser_lib/models/registry.py:38) | 见实现；私有辅助 |
| `ModelRegistry` | [ser_lib/models/registry.py:45](D:/projects/Speech-Emotion-Recognition/ser_lib/models/registry.py:45) | 领域/公开定义 |
| `ModelRegistry.__init__(self) -> None` | [ser_lib/models/registry.py:46](D:/projects/Speech-Emotion-Recognition/ser_lib/models/registry.py:46) |  |
| `ModelRegistry.register(self, name: str, factory: Callable[..., SERModel], *, config_model: type[BaseModel] \| None=None, descriptor: ModelDescriptor \| None=None, spec_factory: ModelSpecFactory \| None=None, replace: bool=False) -> None` | [ser_lib/models/registry.py:49](D:/projects/Speech-Emotion-Recognition/ser_lib/models/registry.py:49) |  |
| `ModelRegistry.create(self, name: str, **params: Any) -> SERModel` | [ser_lib/models/registry.py:68](D:/projects/Speech-Emotion-Recognition/ser_lib/models/registry.py:68) |  |
| `ModelRegistry.validate_config(self, name: str, params: dict[str, Any]) -> dict[str, Any]` | [ser_lib/models/registry.py:82](D:/projects/Speech-Emotion-Recognition/ser_lib/models/registry.py:82) | 严格校验模型配置，并返回带默认值的 JSON-safe 参数。 |
| `ModelRegistry.inspect_spec(self, name: str, params: dict[str, Any]) -> 'ModelSpec'` | [ser_lib/models/registry.py:94](D:/projects/Speech-Emotion-Recognition/ser_lib/models/registry.py:94) | 仅根据配置生成 ModelSpec，不实例化模型、不加载权重。 |
| `ModelRegistry.supports_static_spec(self, name: str) -> bool` | [ser_lib/models/registry.py:116](D:/projects/Speech-Emotion-Recognition/ser_lib/models/registry.py:116) | 模型是否支持不实例化模型的静态 ModelSpec 查询。 |
| `ModelRegistry.descriptor(self, name: str) -> dict[str, Any]` | [ser_lib/models/registry.py:122](D:/projects/Speech-Emotion-Recognition/ser_lib/models/registry.py:122) |  |
| `ModelRegistry.names(self) -> list[str]` | [ser_lib/models/registry.py:127](D:/projects/Speech-Emotion-Recognition/ser_lib/models/registry.py:127) |  |
| `ModelRegistry.descriptors(self) -> list[dict[str, Any]]` | [ser_lib/models/registry.py:130](D:/projects/Speech-Emotion-Recognition/ser_lib/models/registry.py:130) |  |

### ser_lib/models/rnn_models.py

处理：**拆分**。目标：`原路径 + ser_lib/config/model.py`。理由：原生模型保留，仅配置定义中央化。

直接 import 消费者（含测试；从公共包重导入的间接消费者还需沿 D/C 展开）：

- [ser_lib/models/__init__.py:3](D:/projects/Speech-Emotion-Recognition/ser_lib/models/__init__.py:3)；行 3

| class/function/method | 定义行 | 职责说明（源码 docstring） |
| --- | --- | --- |
| `GRUBaselineConfig` | [ser_lib/models/rnn_models.py:19](D:/projects/Speech-Emotion-Recognition/ser_lib/models/rnn_models.py:19) | 领域/公开定义 |
| `GRUBaselineConfig._dropout_requires_multiple_layers(self) -> 'GRUBaselineConfig'` | [ser_lib/models/rnn_models.py:28](D:/projects/Speech-Emotion-Recognition/ser_lib/models/rnn_models.py:28) |  |
| `GRUBaseline` | [ser_lib/models/rnn_models.py:35](D:/projects/Speech-Emotion-Recognition/ser_lib/models/rnn_models.py:35) | 使用 packed sequence 忽略 padding 的 GRU 分类基线。 |
| `GRUBaseline.__init__(self, feature_dim: int, num_classes: int, hidden_dim: int=128, num_layers: int=1, bidirectional: bool=True, dropout: float=0.0) -> None` | [ser_lib/models/rnn_models.py:42](D:/projects/Speech-Emotion-Recognition/ser_lib/models/rnn_models.py:42) |  |
| `GRUBaseline.model_spec(self) -> ModelSpec` | [ser_lib/models/rnn_models.py:78](D:/projects/Speech-Emotion-Recognition/ser_lib/models/rnn_models.py:78) |  |
| `GRUBaseline.model_config(self) -> dict[str, int \| float \| bool]` | [ser_lib/models/rnn_models.py:82](D:/projects/Speech-Emotion-Recognition/ser_lib/models/rnn_models.py:82) |  |
| `GRUBaseline._lengths(self, batch: SERBatch, features: torch.Tensor) -> torch.Tensor` | [ser_lib/models/rnn_models.py:92](D:/projects/Speech-Emotion-Recognition/ser_lib/models/rnn_models.py:92) |  |
| `GRUBaseline.forward(self, batch: SERBatch) -> ModelOutput` | [ser_lib/models/rnn_models.py:111](D:/projects/Speech-Emotion-Recognition/ser_lib/models/rnn_models.py:111) |  |
| `_model_spec_from_config(params: dict[str, Any]) -> ModelSpec` | [ser_lib/models/rnn_models.py:136](D:/projects/Speech-Emotion-Recognition/ser_lib/models/rnn_models.py:136) | 见实现；私有辅助 |

### ser_lib/models/transformer_models.py

处理：**拆分**。目标：`原路径 + ser_lib/config/model.py`。理由：原生模型保留，仅配置定义中央化。

直接 import 消费者（含测试；从公共包重导入的间接消费者还需沿 D/C 展开）：

- [ser_lib/models/__init__.py:4](D:/projects/Speech-Emotion-Recognition/ser_lib/models/__init__.py:4)；行 4

| class/function/method | 定义行 | 职责说明（源码 docstring） |
| --- | --- | --- |
| `TransformerBaselineConfig` | [ser_lib/models/transformer_models.py:19](D:/projects/Speech-Emotion-Recognition/ser_lib/models/transformer_models.py:19) | 领域/公开定义 |
| `TransformerBaselineConfig._validate_attention_dimensions(self) -> 'TransformerBaselineConfig'` | [ser_lib/models/transformer_models.py:31](D:/projects/Speech-Emotion-Recognition/ser_lib/models/transformer_models.py:31) |  |
| `_sinusoidal_positions(length: int, dimension: int, tensor: torch.Tensor) -> torch.Tensor` | [ser_lib/models/transformer_models.py:39](D:/projects/Speech-Emotion-Recognition/ser_lib/models/transformer_models.py:39) | 动态生成位置编码，避免固定最大序列长度和 artifact 状态膨胀。 |
| `TransformerBaseline` | [ser_lib/models/transformer_models.py:53](D:/projects/Speech-Emotion-Recognition/ser_lib/models/transformer_models.py:53) | 投影声学帧、加入正弦位置编码并进行 masked mean pooling。 |
| `TransformerBaseline.__init__(self, feature_dim: int, num_classes: int, d_model: int=128, num_heads: int=4, num_layers: int=2, feedforward_dim: int=256, dropout: float=0.1, activation: Literal['relu', 'gelu']='gelu', norm_first: bool=False) -> None` | [ser_lib/models/transformer_models.py:56](D:/projects/Speech-Emotion-Recognition/ser_lib/models/transformer_models.py:56) |  |
| `TransformerBaseline.model_spec(self) -> ModelSpec` | [ser_lib/models/transformer_models.py:99](D:/projects/Speech-Emotion-Recognition/ser_lib/models/transformer_models.py:99) |  |
| `TransformerBaseline.model_config(self) -> dict[str, int \| float \| bool \| str]` | [ser_lib/models/transformer_models.py:103](D:/projects/Speech-Emotion-Recognition/ser_lib/models/transformer_models.py:103) |  |
| `TransformerBaseline._valid_mask(self, batch: SERBatch, features: torch.Tensor) -> torch.Tensor` | [ser_lib/models/transformer_models.py:116](D:/projects/Speech-Emotion-Recognition/ser_lib/models/transformer_models.py:116) |  |
| `TransformerBaseline.forward(self, batch: SERBatch) -> ModelOutput` | [ser_lib/models/transformer_models.py:141](D:/projects/Speech-Emotion-Recognition/ser_lib/models/transformer_models.py:141) |  |
| `_model_spec_from_config(params: dict[str, Any]) -> ModelSpec` | [ser_lib/models/transformer_models.py:166](D:/projects/Speech-Emotion-Recognition/ser_lib/models/transformer_models.py:166) | 见实现；私有辅助 |

### ser_lib/runtime.py

处理：**迁移**。目标：`ser_lib/engine/runtime.py`。理由：按需设备/host metrics 保留，不创建监控产品。

直接 import 消费者（含测试；从公共包重导入的间接消费者还需沿 D/C 展开）：

- [ser_lib/__init__.py:112](D:/projects/Speech-Emotion-Recognition/ser_lib/__init__.py:112)；行 112
- [ser_lib/services/runtime.py:7](D:/projects/Speech-Emotion-Recognition/ser_lib/services/runtime.py:7)；行 7
- [tests/test_runtime_host_metrics.py:5](D:/projects/Speech-Emotion-Recognition/tests/test_runtime_host_metrics.py:5)；行 5

| class/function/method | 定义行 | 职责说明（源码 docstring） |
| --- | --- | --- |
| `RuntimeDevice` | [ser_lib/runtime.py:15](D:/projects/Speech-Emotion-Recognition/ser_lib/runtime.py:15) | 一个可供单设备训练/评估/推理选择的运行设备。 |
| `RuntimeDevice.to_dict(self) -> dict[str, Any]` | [ser_lib/runtime.py:24](D:/projects/Speech-Emotion-Recognition/ser_lib/runtime.py:24) |  |
| `RuntimeCapabilities` | [ser_lib/runtime.py:29](D:/projects/Speech-Emotion-Recognition/ser_lib/runtime.py:29) | 一次性环境能力快照；不承担持续 CPU/GPU 资源监控。 |
| `RuntimeCapabilities.to_dict(self) -> dict[str, Any]` | [ser_lib/runtime.py:37](D:/projects/Speech-Emotion-Recognition/ser_lib/runtime.py:37) |  |
| `RuntimeMetrics` | [ser_lib/runtime.py:47](D:/projects/Speech-Emotion-Recognition/ser_lib/runtime.py:47) | 单设备 + 主进程即时资源快照；设计为由上层低频主动轮询。 |
| `RuntimeMetrics.to_dict(self) -> dict[str, Any]` | [ser_lib/runtime.py:65](D:/projects/Speech-Emotion-Recognition/ser_lib/runtime.py:65) |  |
| `_HostRuntimeMetrics` | [ser_lib/runtime.py:85](D:/projects/Speech-Emotion-Recognition/ser_lib/runtime.py:85) | 见实现；私有辅助 |
| `get_runtime_capabilities() -> RuntimeCapabilities` | [ser_lib/runtime.py:94](D:/projects/Speech-Emotion-Recognition/ser_lib/runtime.py:94) | 返回 JSON-safe 的 Python/PyTorch 与本机可选设备信息。 |
| `_resolve_cuda_index(device: torch.device) -> int` | [ser_lib/runtime.py:140](D:/projects/Speech-Emotion-Recognition/ser_lib/runtime.py:140) | 见实现；私有辅助 |
| `_host_metrics() -> _HostRuntimeMetrics` | [ser_lib/runtime.py:152](D:/projects/Speech-Emotion-Recognition/ser_lib/runtime.py:152) | 单次、非阻塞采样宿主机与当前 Python 进程资源。 |
| `_runtime_metrics_with_host(*, device_id: str, device_type: str, captured_at: datetime, host: _HostRuntimeMetrics, allocated_memory: int \| None=None, reserved_memory: int \| None=None, max_allocated_memory: int \| None=None, free_memory: int \| None=None, total_memory: int \| None=None) -> RuntimeMetrics` | [ser_lib/runtime.py:167](D:/projects/Speech-Emotion-Recognition/ser_lib/runtime.py:167) | 见实现；私有辅助 |
| `get_runtime_metrics(device: str \| torch.device='cpu') -> RuntimeMetrics` | [ser_lib/runtime.py:197](D:/projects/Speech-Emotion-Recognition/ser_lib/runtime.py:197) | 返回设备和宿主机的即时资源快照，不做 GPU synchronize，也不 sleep。 |

### ser_lib/services/__init__.py

处理：**删除**。目标：`相应 data/engine/inference/artifacts/config public API`。理由：先迁真实行为/消费者/测试，再退役 facade。

直接 import 消费者（含测试；从公共包重导入的间接消费者还需沿 D/C 展开）：

- [examples/inspect_runs_and_presets.py:12](D:/projects/Speech-Emotion-Recognition/examples/inspect_runs_and_presets.py:12)；行 12
- [ser_lib/cli/workflows.py:24](D:/projects/Speech-Emotion-Recognition/ser_lib/cli/workflows.py:24)；行 24
- [tests/test_artifact_catalog.py:8](D:/projects/Speech-Emotion-Recognition/tests/test_artifact_catalog.py:8)；行 8
- [tests/test_batch_prediction_sink.py:15](D:/projects/Speech-Emotion-Recognition/tests/test_batch_prediction_sink.py:15)；行 15
- [tests/test_checkpoint_catalog.py:10](D:/projects/Speech-Emotion-Recognition/tests/test_checkpoint_catalog.py:10)；行 10
- [tests/test_cli_lineage.py:17](D:/projects/Speech-Emotion-Recognition/tests/test_cli_lineage.py:17)；行 17
- [tests/test_dataset_history.py:20](D:/projects/Speech-Emotion-Recognition/tests/test_dataset_history.py:20)；行 20
- [tests/test_dataset_profile.py:10](D:/projects/Speech-Emotion-Recognition/tests/test_dataset_profile.py:10)；行 10
- [tests/test_evaluation_prediction_query.py:10](D:/projects/Speech-Emotion-Recognition/tests/test_evaluation_prediction_query.py:10)；行 10
- [tests/test_evaluation_report_inspect.py:10](D:/projects/Speech-Emotion-Recognition/tests/test_evaluation_report_inspect.py:10)；行 10
- [tests/test_evaluation_run_catalog.py:12](D:/projects/Speech-Emotion-Recognition/tests/test_evaluation_run_catalog.py:12)；行 12
- [tests/test_evaluation_run_detail.py:8](D:/projects/Speech-Emotion-Recognition/tests/test_evaluation_run_detail.py:8)；行 8
- [tests/test_evaluation_run_metadata.py:20](D:/projects/Speech-Emotion-Recognition/tests/test_evaluation_run_metadata.py:20)；行 20
- [tests/test_public_api.py:12](D:/projects/Speech-Emotion-Recognition/tests/test_public_api.py:12)；行 12
- [tests/test_runtime_metrics.py:7](D:/projects/Speech-Emotion-Recognition/tests/test_runtime_metrics.py:7)；行 7
- [tests/test_service_catalog_presets.py:6](D:/projects/Speech-Emotion-Recognition/tests/test_service_catalog_presets.py:6)；行 6
- [tests/test_services.py:11](D:/projects/Speech-Emotion-Recognition/tests/test_services.py:11)；行 11
- [tests/test_training_history.py:10](D:/projects/Speech-Emotion-Recognition/tests/test_training_history.py:10)；行 10
- [tests/test_training_lineage.py:13](D:/projects/Speech-Emotion-Recognition/tests/test_training_lineage.py:13)；行 13
- [tests/test_training_run_catalog.py:24](D:/projects/Speech-Emotion-Recognition/tests/test_training_run_catalog.py:24)；行 24
- [tests/test_training_run_detail.py:10](D:/projects/Speech-Emotion-Recognition/tests/test_training_run_detail.py:10)；行 10

| class/function/method | 定义行 | 职责说明（源码 docstring） |
| --- | --- | --- |

### ser_lib/services/artifacts.py

处理：**删除**。目标：`相应 data/engine/inference/artifacts/config public API`。理由：先迁真实行为/消费者/测试，再退役 facade。

直接 import 消费者（含测试；从公共包重导入的间接消费者还需沿 D/C 展开）：

- [ser_lib/services/__init__.py:3](D:/projects/Speech-Emotion-Recognition/ser_lib/services/__init__.py:3)；行 3

| class/function/method | 定义行 | 职责说明（源码 docstring） |
| --- | --- | --- |
| `ArtifactService` | [ser_lib/services/artifacts.py:28](D:/projects/Speech-Emotion-Recognition/ser_lib/services/artifacts.py:28) | 统一模型管理页所需的 scan/inspect/verify/export/load 入口。 |
| `ArtifactService.scan(root: Path \| str, *, recursive: bool=False, fail_fast: bool=False, event_callback: EventCallback \| None=None, cancellation: CancellationCheck \| None=None) -> ArtifactCatalog` | [ser_lib/services/artifacts.py:32](D:/projects/Speech-Emotion-Recognition/ser_lib/services/artifacts.py:32) |  |
| `ArtifactService.inspect(directory: Path \| str) -> ModelArtifactManifest` | [ser_lib/services/artifacts.py:49](D:/projects/Speech-Emotion-Recognition/ser_lib/services/artifacts.py:49) |  |
| `ArtifactService.verify(directory: Path \| str, *, event_callback: EventCallback \| None=None, cancellation: CancellationCheck \| None=None, event_context: EventContext \| None=None) -> ModelArtifactManifest` | [ser_lib/services/artifacts.py:53](D:/projects/Speech-Emotion-Recognition/ser_lib/services/artifacts.py:53) |  |
| `ArtifactService.export(directory: Path \| str, model: SERModel, *, model_name: str, data_config: DataConfig, labels: Mapping[int, str], model_params: Mapping[str, Any] \| None=None, metrics: Mapping[str, float] \| None=None, metadata: Mapping[str, Any] \| None=None, source_run: TrainingRunMetadata \| None=None, model_card: ModelCard \| Mapping[str, Any] \| None=None, event_callback: EventCallback \| None=None, cancellation: CancellationCheck \| None=None, event_context: EventContext \| None=None) -> Path` | [ser_lib/services/artifacts.py:68](D:/projects/Speech-Emotion-Recognition/ser_lib/services/artifacts.py:68) |  |
| `ArtifactService.load(directory: Path \| str, *, map_location: str \| torch.device='cpu', allow_legacy_pickle: bool=False) -> LoadedArtifact` | [ser_lib/services/artifacts.py:109](D:/projects/Speech-Emotion-Recognition/ser_lib/services/artifacts.py:109) |  |

### ser_lib/services/catalog.py

处理：**删除**。目标：`相应 data/engine/inference/artifacts/config public API`。理由：先迁真实行为/消费者/测试，再退役 facade。

直接 import 消费者（含测试；从公共包重导入的间接消费者还需沿 D/C 展开）：

- [ser_lib/services/__init__.py:4](D:/projects/Speech-Emotion-Recognition/ser_lib/services/__init__.py:4)；行 4

| class/function/method | 定义行 | 职责说明（源码 docstring） |
| --- | --- | --- |
| `CatalogService` | [ser_lib/services/catalog.py:23](D:/projects/Speech-Emotion-Recognition/ser_lib/services/catalog.py:23) | 为动态表单、组件选择器与实验向导提供只读 facade。 |
| `CatalogService.snapshot() -> ComponentCatalog` | [ser_lib/services/catalog.py:27](D:/projects/Speech-Emotion-Recognition/ser_lib/services/catalog.py:27) |  |
| `CatalogService.list(category: str \| None=None, *, statuses: tuple[str, ...] \| None=None) -> tuple[ComponentDescriptor, ...]` | [ser_lib/services/catalog.py:31](D:/projects/Speech-Emotion-Recognition/ser_lib/services/catalog.py:31) |  |
| `CatalogService.get(category: str, component_id: str) -> ComponentDescriptor` | [ser_lib/services/catalog.py:39](D:/projects/Speech-Emotion-Recognition/ser_lib/services/catalog.py:39) |  |
| `CatalogService.presets() -> ExperimentPresetCatalog` | [ser_lib/services/catalog.py:43](D:/projects/Speech-Emotion-Recognition/ser_lib/services/catalog.py:43) | 返回稳定、JSON-safe 的实验 preset catalog。 |
| `CatalogService.get_preset(preset_id: str) -> ExperimentPresetInfo` | [ser_lib/services/catalog.py:48](D:/projects/Speech-Emotion-Recognition/ser_lib/services/catalog.py:48) |  |
| `CatalogService.build_experiment(preset_id: str, *, overrides: Mapping[str, Any] \| None=None) -> ExperimentConfig` | [ser_lib/services/catalog.py:52](D:/projects/Speech-Emotion-Recognition/ser_lib/services/catalog.py:52) | 基于 preset 构建唯一的 ``ExperimentConfig``，不引入第二套配置模型。 |

### ser_lib/services/datasets.py

处理：**删除**。目标：`相应 data/engine/inference/artifacts/config public API`。理由：先迁真实行为/消费者/测试，再退役 facade。

直接 import 消费者（含测试；从公共包重导入的间接消费者还需沿 D/C 展开）：

- [ser_lib/services/__init__.py:5](D:/projects/Speech-Emotion-Recognition/ser_lib/services/__init__.py:5)；行 5

| class/function/method | 定义行 | 职责说明（源码 docstring） |
| --- | --- | --- |
| `DatasetService` | [ser_lib/services/datasets.py:31](D:/projects/Speech-Emotion-Recognition/ser_lib/services/datasets.py:31) | 薄 facade；不复制 Manifest/Query/Editor/History 的业务规则。 |
| `DatasetService.summary(manifest: DatasetManifest \| Path \| str, *, include_audio_profile: bool=False, fail_fast: bool=False, event_callback: EventCallback \| None=None, cancellation: CancellationCheck \| None=None) -> DatasetSummary` | [ser_lib/services/datasets.py:35](D:/projects/Speech-Emotion-Recognition/ser_lib/services/datasets.py:35) |  |
| `DatasetService.profile(manifest: DatasetManifest \| Path \| str, *, split: str \| None=None, fail_fast: bool=False, histogram_bins: int=10, event_callback: EventCallback \| None=None, cancellation: CancellationCheck \| None=None) -> DatasetAudioProfile` | [ser_lib/services/datasets.py:52](D:/projects/Speech-Emotion-Recognition/ser_lib/services/datasets.py:52) | 保留现有音频 header profile API。 |
| `DatasetService.detailed_profile(manifest: DatasetManifest \| Path \| str, *, include_audio: bool=False, fail_fast: bool=False, histogram_bins: int=10, event_callback: EventCallback \| None=None, cancellation: CancellationCheck \| None=None) -> DatasetProfile` | [ser_lib/services/datasets.py:72](D:/projects/Speech-Emotion-Recognition/ser_lib/services/datasets.py:72) | 返回数据集分析页使用的 split/label/speaker/audio 详细统计。 |
| `DatasetService.query(manifest: DatasetManifest \| Path \| str, *, split: str \| None=None, label_id: int \| None=None, speaker_id: str \| None=None, keyword: str \| None=None, offset: int=0, limit: int=50) -> RecordPage` | [ser_lib/services/datasets.py:92](D:/projects/Speech-Emotion-Recognition/ser_lib/services/datasets.py:92) |  |
| `DatasetService.fingerprint(manifest: DatasetManifest \| Path \| str, *, event_callback: EventCallback \| None=None, cancellation: CancellationCheck \| None=None) -> DatasetFingerprint` | [ser_lib/services/datasets.py:113](D:/projects/Speech-Emotion-Recognition/ser_lib/services/datasets.py:113) |  |
| `DatasetService.editor(manifest: DatasetManifest \| Path \| str) -> DatasetEditor` | [ser_lib/services/datasets.py:126](D:/projects/Speech-Emotion-Recognition/ser_lib/services/datasets.py:126) |  |
| `DatasetService.snapshot_revision(manifest: DatasetManifest \| Path \| str, *, history_root: Path \| str \| None=None, revision_id: str \| None=None, note: str='', created_at: datetime \| None=None, event_callback: EventCallback \| None=None, cancellation: CancellationCheck \| None=None) -> DatasetRevisionInfo` | [ser_lib/services/datasets.py:130](D:/projects/Speech-Emotion-Recognition/ser_lib/services/datasets.py:130) |  |
| `DatasetService.inspect_revision(revision: Path \| str, *, verify: bool=False, cancellation: CancellationCheck \| None=None) -> DatasetRevisionInfo` | [ser_lib/services/datasets.py:151](D:/projects/Speech-Emotion-Recognition/ser_lib/services/datasets.py:151) |  |
| `DatasetService.revision_history(manifest: DatasetManifest \| Path \| str, *, history_root: Path \| str \| None=None, fail_fast: bool=False, event_callback: EventCallback \| None=None, cancellation: CancellationCheck \| None=None) -> DatasetRevisionCatalog` | [ser_lib/services/datasets.py:164](D:/projects/Speech-Emotion-Recognition/ser_lib/services/datasets.py:164) |  |
| `DatasetService.restore_revision(manifest: DatasetManifest \| Path \| str, revision: Path \| str, *, expected_current_fingerprint: str, event_callback: EventCallback \| None=None, cancellation: CancellationCheck \| None=None) -> DatasetManifest` | [ser_lib/services/datasets.py:181](D:/projects/Speech-Emotion-Recognition/ser_lib/services/datasets.py:181) |  |

### ser_lib/services/evaluation.py

处理：**删除**。目标：`相应 data/engine/inference/artifacts/config public API`。理由：先迁真实行为/消费者/测试，再退役 facade。

直接 import 消费者（含测试；从公共包重导入的间接消费者还需沿 D/C 展开）：

- [ser_lib/services/__init__.py:6](D:/projects/Speech-Emotion-Recognition/ser_lib/services/__init__.py:6)；行 6

| class/function/method | 定义行 | 职责说明（源码 docstring） |
| --- | --- | --- |
| `EvaluationService` | [ser_lib/services/evaluation.py:41](D:/projects/Speech-Emotion-Recognition/ser_lib/services/evaluation.py:41) | 统一 standalone/Web evaluation 的运行、lineage、落盘与查询入口。 |
| `EvaluationService.create_run_metadata(*, source_artifact: Path \| str, dataset_id: str, model_name: str, split: str, device: str, source_run_id: str \| None=None, dataset_fingerprint: str \| None=None, evaluation_id: str \| None=None, created_at: datetime \| None=None) -> EvaluationRunMetadata` | [ser_lib/services/evaluation.py:45](D:/projects/Speech-Emotion-Recognition/ser_lib/services/evaluation.py:45) |  |
| `EvaluationService.run(model: SERModel, batches: Iterable[SERBatch], *, num_classes: int, device: str \| torch.device='cpu', labels: Mapping[int, str] \| None=None, event_callback: EventCallback \| None=None, cancellation: CancellationCheck \| None=None, loss_fn: torch.nn.Module \| None=None, event_context: EventContext \| None=None, split: str \| None=None, prediction_sink: PredictionSink \| None=None, retain_predictions: bool=True) -> EvaluationResult` | [ser_lib/services/evaluation.py:73](D:/projects/Speech-Emotion-Recognition/ser_lib/services/evaluation.py:73) |  |
| `EvaluationService.write_report(directory: Path \| str, result: EvaluationResult) -> Path` | [ser_lib/services/evaluation.py:104](D:/projects/Speech-Emotion-Recognition/ser_lib/services/evaluation.py:104) |  |
| `EvaluationService.save_run(directory: Path \| str, metadata: EvaluationRunMetadata, result: EvaluationResult, *, started_at: datetime, finished_at: datetime, predictions_file: str \| None='predictions.jsonl') -> EvaluationRunInfo` | [ser_lib/services/evaluation.py:108](D:/projects/Speech-Emotion-Recognition/ser_lib/services/evaluation.py:108) |  |
| `EvaluationService.inspect_run(path: Path \| str) -> EvaluationRunInfo` | [ser_lib/services/evaluation.py:128](D:/projects/Speech-Emotion-Recognition/ser_lib/services/evaluation.py:128) |  |
| `EvaluationService.inspect_run_detail(path: Path \| str) -> EvaluationRunDetail` | [ser_lib/services/evaluation.py:132](D:/projects/Speech-Emotion-Recognition/ser_lib/services/evaluation.py:132) | 聚合 evaluation metadata、metrics 与 prediction stat，不读预测明细。 |
| `EvaluationService.scan_runs(root: Path \| str, *, recursive: bool=False, fail_fast: bool=False, event_callback: EventCallback \| None=None, cancellation: CancellationCheck \| None=None) -> EvaluationRunCatalog` | [ser_lib/services/evaluation.py:173](D:/projects/Speech-Emotion-Recognition/ser_lib/services/evaluation.py:173) |  |
| `EvaluationService.inspect_report(directory: Path \| str) -> EvaluationReportInfo` | [ser_lib/services/evaluation.py:190](D:/projects/Speech-Emotion-Recognition/ser_lib/services/evaluation.py:190) |  |
| `EvaluationService.query_predictions(directory: Path \| str, *, offset: int=0, limit: int=100, incorrect_only: bool=False, target: int \| None=None, predicted: int \| None=None, cancellation: CancellationCheck \| None=None) -> EvaluationPredictionPage` | [ser_lib/services/evaluation.py:194](D:/projects/Speech-Emotion-Recognition/ser_lib/services/evaluation.py:194) |  |

### ser_lib/services/inference.py

处理：**删除**。目标：`相应 data/engine/inference/artifacts/config public API`。理由：先迁真实行为/消费者/测试，再退役 facade。

直接 import 消费者（含测试；从公共包重导入的间接消费者还需沿 D/C 展开）：

- [ser_lib/services/__init__.py:7](D:/projects/Speech-Emotion-Recognition/ser_lib/services/__init__.py:7)；行 7

| class/function/method | 定义行 | 职责说明（源码 docstring） |
| --- | --- | --- |
| `InferenceService` | [ser_lib/services/inference.py:31](D:/projects/Speech-Emotion-Recognition/ser_lib/services/inference.py:31) | 统一应用层的 predictor 构造、批量来源选择、结果写盘和流式入口。 |
| `InferenceService.create_predictor(artifact: 'LoadedArtifact', *, device: str='cpu', window_aggregation: WindowAggregation \| None=None) -> EmotionPredictor` | [ser_lib/services/inference.py:35](D:/projects/Speech-Emotion-Recognition/ser_lib/services/inference.py:35) |  |
| `InferenceService.predict_file(predictor: EmotionPredictor, path: Path \| str, *, uid: str \| None=None) -> PredictionResult` | [ser_lib/services/inference.py:52](D:/projects/Speech-Emotion-Recognition/ser_lib/services/inference.py:52) |  |
| `InferenceService.predict_record(predictor: EmotionPredictor, record: AudioRecord) -> PredictionResult` | [ser_lib/services/inference.py:61](D:/projects/Speech-Emotion-Recognition/ser_lib/services/inference.py:61) |  |
| `InferenceService.predict_records(predictor: EmotionPredictor, records: Iterable[AudioRecord], *, fail_fast: bool=True, batch_size: int=16, total: int \| None=None, result_sink: BatchPredictionSink \| None=None, retain_results: bool=True, event_callback: EventCallback \| None=None, cancellation: CancellationCheck \| None=None) -> BatchPredictionResult` | [ser_lib/services/inference.py:68](D:/projects/Speech-Emotion-Recognition/ser_lib/services/inference.py:68) |  |
| `InferenceService.predict_files(predictor: EmotionPredictor, paths: Iterable[Path \| str], *, fail_fast: bool=True, batch_size: int=16, result_sink: BatchPredictionSink \| None=None, retain_results: bool=True, event_callback: EventCallback \| None=None, cancellation: CancellationCheck \| None=None) -> BatchPredictionResult` | [ser_lib/services/inference.py:92](D:/projects/Speech-Emotion-Recognition/ser_lib/services/inference.py:92) |  |
| `InferenceService.predict_directory(predictor: EmotionPredictor, directory: Path \| str, *, recursive: bool=True, extensions: Sequence[str] \| None=None, fail_fast: bool=True, batch_size: int=16, result_sink: BatchPredictionSink \| None=None, retain_results: bool=True, event_callback: EventCallback \| None=None, cancellation: CancellationCheck \| None=None) -> BatchPredictionResult` | [ser_lib/services/inference.py:114](D:/projects/Speech-Emotion-Recognition/ser_lib/services/inference.py:114) |  |
| `InferenceService.predict_manifest(predictor: EmotionPredictor, manifest: DatasetManifest \| Path \| str, *, split: str \| None=None, fail_fast: bool=True, batch_size: int=16, result_sink: BatchPredictionSink \| None=None, retain_results: bool=True, event_callback: EventCallback \| None=None, cancellation: CancellationCheck \| None=None) -> BatchPredictionResult` | [ser_lib/services/inference.py:140](D:/projects/Speech-Emotion-Recognition/ser_lib/services/inference.py:140) |  |
| `InferenceService.write_predictions(path: Path \| str, result: BatchPredictionResult, *, format: Literal['jsonl', 'csv'] \| None=None) -> Path` | [ser_lib/services/inference.py:164](D:/projects/Speech-Emotion-Recognition/ser_lib/services/inference.py:164) |  |
| `InferenceService.create_stream(predictor: EmotionPredictor, config: StreamingConfig \| None=None) -> StreamingEmotionRecognizer` | [ser_lib/services/inference.py:173](D:/projects/Speech-Emotion-Recognition/ser_lib/services/inference.py:173) |  |

### ser_lib/services/runtime.py

处理：**删除**。目标：`相应 data/engine/inference/artifacts/config public API`。理由：先迁真实行为/消费者/测试，再退役 facade。

直接 import 消费者（含测试；从公共包重导入的间接消费者还需沿 D/C 展开）：

- [ser_lib/services/__init__.py:8](D:/projects/Speech-Emotion-Recognition/ser_lib/services/__init__.py:8)；行 8

| class/function/method | 定义行 | 职责说明（源码 docstring） |
| --- | --- | --- |
| `RuntimeService` | [ser_lib/services/runtime.py:15](D:/projects/Speech-Emotion-Recognition/ser_lib/services/runtime.py:15) | 提供环境能力与按需资源快照；不负责后台轮询。 |
| `RuntimeService.capabilities() -> RuntimeCapabilities` | [ser_lib/services/runtime.py:19](D:/projects/Speech-Emotion-Recognition/ser_lib/services/runtime.py:19) |  |
| `RuntimeService.metrics(device: str \| torch.device='cpu') -> RuntimeMetrics` | [ser_lib/services/runtime.py:23](D:/projects/Speech-Emotion-Recognition/ser_lib/services/runtime.py:23) |  |

### ser_lib/services/training.py

处理：**删除**。目标：`相应 data/engine/inference/artifacts/config public API`。理由：先迁真实行为/消费者/测试，再退役 facade。

直接 import 消费者（含测试；从公共包重导入的间接消费者还需沿 D/C 展开）：

- [ser_lib/services/__init__.py:9](D:/projects/Speech-Emotion-Recognition/ser_lib/services/__init__.py:9)；行 9

| class/function/method | 定义行 | 职责说明（源码 docstring） |
| --- | --- | --- |
| `TrainingService` | [ser_lib/services/training.py:33](D:/projects/Speech-Emotion-Recognition/ser_lib/services/training.py:33) | 训练应用层 facade；Trainer 本身负责训练状态与 checkpoint lineage。 |
| `TrainingService.validate(config: ExperimentConfig \| Path \| str) -> ExperimentValidationResult` | [ser_lib/services/training.py:37](D:/projects/Speech-Emotion-Recognition/ser_lib/services/training.py:37) |  |
| `TrainingService.create_trainer(model: SERModel, experiment: ExperimentConfig, *, event_callback: EventCallback \| None=None, cancellation: CancellationCheck \| None=None, observability: ObservabilityConfig \| None=None, run_id: str \| None=None, dataset_id: str \| None=None, dataset_fingerprint: str \| None=None) -> Trainer` | [ser_lib/services/training.py:43](D:/projects/Speech-Emotion-Recognition/ser_lib/services/training.py:43) | 构造可追踪 Trainer，不读取 manifest 或隐式计算 fingerprint。 |
| `TrainingService.get_run_metadata(trainer: Trainer) -> TrainingRunMetadata \| None` | [ser_lib/services/training.py:83](D:/projects/Speech-Emotion-Recognition/ser_lib/services/training.py:83) |  |
| `TrainingService.run(trainer: Trainer, train_batches: Iterable[SERBatch] \| Callable[[], Iterable[SERBatch]], *, val_batches: Iterable[SERBatch] \| Callable[[], Iterable[SERBatch]] \| None=None, on_epoch_end: Callable[[EpochResult], None] \| None=None, start_epoch: int \| None=None) -> TrainingResult` | [ser_lib/services/training.py:87](D:/projects/Speech-Emotion-Recognition/ser_lib/services/training.py:87) | 执行 Trainer.fit，并直接返回 Web 需要的 TrainingResult。 |
| `TrainingService.save_run(directory: Path \| str, trainer: Trainer, result: TrainingResult) -> TrainingRunInfo` | [ser_lib/services/training.py:107](D:/projects/Speech-Emotion-Recognition/ser_lib/services/training.py:107) | 原子持久化终态 run.json，并返回重新读取后的规范记录。 |
| `TrainingService.inspect_run(path: Path \| str) -> TrainingRunInfo` | [ser_lib/services/training.py:120](D:/projects/Speech-Emotion-Recognition/ser_lib/services/training.py:120) |  |
| `TrainingService.inspect_history(path: Path \| str) -> TrainingHistoryInfo` | [ser_lib/services/training.py:124](D:/projects/Speech-Emotion-Recognition/ser_lib/services/training.py:124) |  |
| `TrainingService.inspect_run_detail(path: Path \| str) -> TrainingRunDetail` | [ser_lib/services/training.py:128](D:/projects/Speech-Emotion-Recognition/ser_lib/services/training.py:128) | 聚合训练元数据、曲线与 checkpoint stat，不加载任何 checkpoint 内容。 |
| `TrainingService.scan_runs(root: Path \| str, *, recursive: bool=False, fail_fast: bool=False, event_callback: EventCallback \| None=None, cancellation: CancellationCheck \| None=None) -> TrainingRunCatalog` | [ser_lib/services/training.py:176](D:/projects/Speech-Emotion-Recognition/ser_lib/services/training.py:176) |  |
| `TrainingService.inspect_checkpoint(path: Path \| str) -> CheckpointInfo` | [ser_lib/services/training.py:193](D:/projects/Speech-Emotion-Recognition/ser_lib/services/training.py:193) |  |
| `TrainingService.scan_checkpoints(root: Path \| str, *, recursive: bool=False, fail_fast: bool=False, event_callback: EventCallback \| None=None, cancellation: CancellationCheck \| None=None) -> CheckpointCatalog` | [ser_lib/services/training.py:197](D:/projects/Speech-Emotion-Recognition/ser_lib/services/training.py:197) |  |
| `_checkpoint_root_for_run(run: TrainingRunInfo) -> Path` | [ser_lib/services/training.py:214](D:/projects/Speech-Emotion-Recognition/ser_lib/services/training.py:214) | 见实现；私有辅助 |

## F. 可静态解析的关键调用点

记录实际 Call AST；局部变量实例方法（如 trainer.fit）保留源码表达式。这里只列关键边界调用，不把无法静态确定的变量类型伪装成已解析目标。D 提供完整 import 清单，E 提供所有定义。

| 调用位置 | 调用表达式 | 可解析来源/限制 |
| --- | --- | --- |
| [examples/inspect_runs_and_presets.py:21](D:/projects/Speech-Emotion-Recognition/examples/inspect_runs_and_presets.py:21) | `CatalogService.presets` | `ser_lib.services.CatalogService.presets` |
| [examples/inspect_runs_and_presets.py:22](D:/projects/Speech-Emotion-Recognition/examples/inspect_runs_and_presets.py:22) | `RuntimeService.metrics` | `ser_lib.services.RuntimeService.metrics` |
| [examples/inspect_runs_and_presets.py:29](D:/projects/Speech-Emotion-Recognition/examples/inspect_runs_and_presets.py:29) | `TrainingService.inspect_run_detail(args.training_run).to_dict` | `ser_lib.services.TrainingService.inspect_run_detail(args.training_run).to_dict` |
| [examples/inspect_runs_and_presets.py:31](D:/projects/Speech-Emotion-Recognition/examples/inspect_runs_and_presets.py:31) | `EvaluationService.inspect_run_detail(args.evaluation_run).to_dict` | `ser_lib.services.EvaluationService.inspect_run_detail(args.evaluation_run).to_dict` |
| [examples/inspect_runs_and_presets.py:29](D:/projects/Speech-Emotion-Recognition/examples/inspect_runs_and_presets.py:29) | `TrainingService.inspect_run_detail` | `ser_lib.services.TrainingService.inspect_run_detail` |
| [examples/inspect_runs_and_presets.py:31](D:/projects/Speech-Emotion-Recognition/examples/inspect_runs_and_presets.py:31) | `EvaluationService.inspect_run_detail` | `ser_lib.services.EvaluationService.inspect_run_detail` |
| [examples/predict_artifact.py:19](D:/projects/Speech-Emotion-Recognition/examples/predict_artifact.py:19) | `load_model_artifact` | `ser_lib.artifacts.load_model_artifact` |
| [examples/train_from_python.py:22](D:/projects/Speech-Emotion-Recognition/examples/train_from_python.py:22) | `build_experiment_components` | `ser_lib.engine.build_experiment_components` |
| [examples/train_from_python.py:36](D:/projects/Speech-Emotion-Recognition/examples/train_from_python.py:36) | `trainer.fit` | `实例/局部 factory；需结合上下文` |
| [scripts/smoke_train_epoch.py:120](D:/projects/Speech-Emotion-Recognition/scripts/smoke_train_epoch.py:120) | `trainer.fit` | `实例/局部 factory；需结合上下文` |
| [ser_lib/artifacts/loader.py:292](D:/projects/Speech-Emotion-Recognition/ser_lib/artifacts/loader.py:292) | `model_registry.create` | `ser_lib.models.registry.model_registry.create` |
| [ser_lib/artifacts/loader.py:294](D:/projects/Speech-Emotion-Recognition/ser_lib/artifacts/loader.py:294) | `validate_compatibility` | `ser_lib.data.validation.validate_compatibility` |
| [ser_lib/cli/main.py:184](D:/projects/Speech-Emotion-Recognition/ser_lib/cli/main.py:184) | `default_registry.create` | `ser_lib.data.default_registry.create` |
| [ser_lib/cli/workflows.py:90](D:/projects/Speech-Emotion-Recognition/ser_lib/cli/workflows.py:90) | `build_experiment_components` | `ser_lib.engine.build_experiment_components` |
| [ser_lib/cli/workflows.py:104](D:/projects/Speech-Emotion-Recognition/ser_lib/cli/workflows.py:104) | `TrainingService.create_trainer` | `ser_lib.services.TrainingService.create_trainer` |
| [ser_lib/cli/workflows.py:132](D:/projects/Speech-Emotion-Recognition/ser_lib/cli/workflows.py:132) | `TrainingService.run` | `ser_lib.services.TrainingService.run` |
| [ser_lib/cli/workflows.py:146](D:/projects/Speech-Emotion-Recognition/ser_lib/cli/workflows.py:146) | `TrainingService.save_run` | `ser_lib.services.TrainingService.save_run` |
| [ser_lib/cli/workflows.py:181](D:/projects/Speech-Emotion-Recognition/ser_lib/cli/workflows.py:181) | `ArtifactService.load` | `ser_lib.services.ArtifactService.load` |
| [ser_lib/cli/workflows.py:192](D:/projects/Speech-Emotion-Recognition/ser_lib/cli/workflows.py:192) | `EvaluationService.create_run_metadata` | `ser_lib.services.EvaluationService.create_run_metadata` |
| [ser_lib/cli/workflows.py:209](D:/projects/Speech-Emotion-Recognition/ser_lib/cli/workflows.py:209) | `EvaluationService.run` | `ser_lib.services.EvaluationService.run` |
| [ser_lib/cli/workflows.py:218](D:/projects/Speech-Emotion-Recognition/ser_lib/cli/workflows.py:218) | `EvaluationService.write_report` | `ser_lib.services.EvaluationService.write_report` |
| [ser_lib/cli/workflows.py:219](D:/projects/Speech-Emotion-Recognition/ser_lib/cli/workflows.py:219) | `EvaluationService.save_run` | `ser_lib.services.EvaluationService.save_run` |
| [ser_lib/cli/workflows.py:251](D:/projects/Speech-Emotion-Recognition/ser_lib/cli/workflows.py:251) | `ArtifactService.load` | `ser_lib.services.ArtifactService.load` |
| [ser_lib/cli/workflows.py:252](D:/projects/Speech-Emotion-Recognition/ser_lib/cli/workflows.py:252) | `InferenceService.create_predictor` | `ser_lib.services.InferenceService.create_predictor` |
| [ser_lib/cli/workflows.py:280](D:/projects/Speech-Emotion-Recognition/ser_lib/cli/workflows.py:280) | `InferenceService.write_predictions` | `ser_lib.services.InferenceService.write_predictions` |
| [ser_lib/cli/workflows.py:297](D:/projects/Speech-Emotion-Recognition/ser_lib/cli/workflows.py:297) | `build_experiment_components` | `ser_lib.engine.build_experiment_components` |
| [ser_lib/cli/workflows.py:318](D:/projects/Speech-Emotion-Recognition/ser_lib/cli/workflows.py:318) | `ArtifactService.export` | `ser_lib.services.ArtifactService.export` |
| [ser_lib/cli/workflows.py:112](D:/projects/Speech-Emotion-Recognition/ser_lib/cli/workflows.py:112) | `build_experiment_components` | `ser_lib.engine.build_experiment_components` |
| [ser_lib/cli/workflows.py:121](D:/projects/Speech-Emotion-Recognition/ser_lib/cli/workflows.py:121) | `trainer.resume_from` | `实例/局部 factory；需结合上下文` |
| [ser_lib/cli/workflows.py:258](D:/projects/Speech-Emotion-Recognition/ser_lib/cli/workflows.py:258) | `InferenceService.predict_directory` | `ser_lib.services.InferenceService.predict_directory` |
| [ser_lib/cli/workflows.py:338](D:/projects/Speech-Emotion-Recognition/ser_lib/cli/workflows.py:338) | `ArtifactService.verify` | `ser_lib.services.ArtifactService.verify` |
| [ser_lib/cli/workflows.py:338](D:/projects/Speech-Emotion-Recognition/ser_lib/cli/workflows.py:338) | `ArtifactService.inspect` | `ser_lib.services.ArtifactService.inspect` |
| [ser_lib/cli/workflows.py:266](D:/projects/Speech-Emotion-Recognition/ser_lib/cli/workflows.py:266) | `InferenceService.predict_manifest` | `ser_lib.services.InferenceService.predict_manifest` |
| [ser_lib/cli/workflows.py:274](D:/projects/Speech-Emotion-Recognition/ser_lib/cli/workflows.py:274) | `InferenceService.predict_files` | `ser_lib.services.InferenceService.predict_files` |
| [ser_lib/core/migrations.py:176](D:/projects/Speech-Emotion-Recognition/ser_lib/core/migrations.py:176) | `_default_registry.register` | `实例/局部 factory；需结合上下文` |
| [ser_lib/data/importers/__init__.py:39](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/__init__.py:39) | `registry.register` | `实例/局部 factory；需结合上下文` |
| [ser_lib/data/pipeline.py:145](D:/projects/Speech-Emotion-Recognition/ser_lib/data/pipeline.py:145) | `default_registry.create` | `ser_lib.data.registry.default_registry.create` |
| [ser_lib/data/pipeline.py:228](D:/projects/Speech-Emotion-Recognition/ser_lib/data/pipeline.py:228) | `default_registry.create` | `ser_lib.data.registry.default_registry.create` |
| [ser_lib/data/pipeline.py:180](D:/projects/Speech-Emotion-Recognition/ser_lib/data/pipeline.py:180) | `default_registry.create` | `ser_lib.data.registry.default_registry.create` |
| [ser_lib/data/representations/__init__.py:50](D:/projects/Speech-Emotion-Recognition/ser_lib/data/representations/__init__.py:50) | `registry.register` | `实例/局部 factory；需结合上下文` |
| [ser_lib/data/representations/__init__.py:55](D:/projects/Speech-Emotion-Recognition/ser_lib/data/representations/__init__.py:55) | `registry.register` | `实例/局部 factory；需结合上下文` |
| [ser_lib/data/representations/__init__.py:60](D:/projects/Speech-Emotion-Recognition/ser_lib/data/representations/__init__.py:60) | `registry.register` | `实例/局部 factory；需结合上下文` |
| [ser_lib/data/representations/__init__.py:65](D:/projects/Speech-Emotion-Recognition/ser_lib/data/representations/__init__.py:65) | `registry.register` | `实例/局部 factory；需结合上下文` |
| [ser_lib/data/representations/__init__.py:70](D:/projects/Speech-Emotion-Recognition/ser_lib/data/representations/__init__.py:70) | `registry.register` | `实例/局部 factory；需结合上下文` |
| [ser_lib/data/representations/__init__.py:75](D:/projects/Speech-Emotion-Recognition/ser_lib/data/representations/__init__.py:75) | `registry.register` | `实例/局部 factory；需结合上下文` |
| [ser_lib/data/representations/__init__.py:80](D:/projects/Speech-Emotion-Recognition/ser_lib/data/representations/__init__.py:80) | `registry.register` | `实例/局部 factory；需结合上下文` |
| [ser_lib/data/representations/composite.py:64](D:/projects/Speech-Emotion-Recognition/ser_lib/data/representations/composite.py:64) | `default_registry.create` | `ser_lib.data.registry.default_registry.create` |
| [ser_lib/data/transforms/__init__.py:39](D:/projects/Speech-Emotion-Recognition/ser_lib/data/transforms/__init__.py:39) | `registry.register` | `实例/局部 factory；需结合上下文` |
| [ser_lib/data/transforms/__init__.py:35](D:/projects/Speech-Emotion-Recognition/ser_lib/data/transforms/__init__.py:35) | `registry.register` | `实例/局部 factory；需结合上下文` |
| [ser_lib/engine/config.py:119](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/config.py:119) | `model_registry.create` | `ser_lib.models.registry.model_registry.create` |
| [ser_lib/engine/config.py:121](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/config.py:121) | `validate_compatibility` | `ser_lib.data.validation.validate_compatibility` |
| [ser_lib/engine/trainer.py:115](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/trainer.py:115) | `super().resume_from` | `实例/局部 factory；需结合上下文` |
| [ser_lib/engine/validation.py:208](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/validation.py:208) | `model_registry.inspect_spec` | `ser_lib.models.registry.model_registry.inspect_spec` |
| [ser_lib/models/cnn_models.py:113](D:/projects/Speech-Emotion-Recognition/ser_lib/models/cnn_models.py:113) | `model_registry.register` | `ser_lib.models.registry.model_registry.register` |
| [ser_lib/models/pretrained.py:210](D:/projects/Speech-Emotion-Recognition/ser_lib/models/pretrained.py:210) | `model_registry.register` | `ser_lib.models.registry.model_registry.register` |
| [ser_lib/models/rnn_models.py:148](D:/projects/Speech-Emotion-Recognition/ser_lib/models/rnn_models.py:148) | `model_registry.register` | `ser_lib.models.registry.model_registry.register` |
| [ser_lib/models/transformer_models.py:178](D:/projects/Speech-Emotion-Recognition/ser_lib/models/transformer_models.py:178) | `model_registry.register` | `ser_lib.models.registry.model_registry.register` |
| [ser_lib/services/artifacts.py:93](D:/projects/Speech-Emotion-Recognition/ser_lib/services/artifacts.py:93) | `export_model_artifact` | `ser_lib.artifacts.export_model_artifact` |
| [ser_lib/services/artifacts.py:115](D:/projects/Speech-Emotion-Recognition/ser_lib/services/artifacts.py:115) | `load_model_artifact` | `ser_lib.artifacts.load_model_artifact` |
| [ser_lib/services/datasets.py:102](D:/projects/Speech-Emotion-Recognition/ser_lib/services/datasets.py:102) | `query_records` | `ser_lib.data.query.query_records` |
| [ser_lib/services/evaluation.py:204](D:/projects/Speech-Emotion-Recognition/ser_lib/services/evaluation.py:204) | `query_evaluation_predictions` | `ser_lib.engine.evaluation_reports.query_evaluation_predictions` |
| [ser_lib/services/training.py:96](D:/projects/Speech-Emotion-Recognition/ser_lib/services/training.py:96) | `trainer.fit` | `实例/局部 factory；需结合上下文` |
| [ser_lib/services/training.py:113](D:/projects/Speech-Emotion-Recognition/ser_lib/services/training.py:113) | `TrainingService.get_run_metadata` | `实例/局部 factory；需结合上下文` |
| [tests/test_artifact_catalog.py:39](D:/projects/Speech-Emotion-Recognition/tests/test_artifact_catalog.py:39) | `ArtifactService.export` | `ser_lib.services.ArtifactService.export` |
| [tests/test_artifact_catalog.py:90](D:/projects/Speech-Emotion-Recognition/tests/test_artifact_catalog.py:90) | `ArtifactService.export` | `ser_lib.services.ArtifactService.export` |
| [tests/test_artifact_catalog.py:99](D:/projects/Speech-Emotion-Recognition/tests/test_artifact_catalog.py:99) | `ArtifactService.scan` | `ser_lib.services.ArtifactService.scan` |
| [tests/test_artifact_catalog.py:98](D:/projects/Speech-Emotion-Recognition/tests/test_artifact_catalog.py:98) | `ArtifactService.scan` | `ser_lib.services.ArtifactService.scan` |
| [tests/test_artifact_inspect.py:37](D:/projects/Speech-Emotion-Recognition/tests/test_artifact_inspect.py:37) | `export_model_artifact` | `ser_lib.artifacts.export_model_artifact` |
| [tests/test_artifact_progress.py:41](D:/projects/Speech-Emotion-Recognition/tests/test_artifact_progress.py:41) | `export_model_artifact` | `ser_lib.artifacts.export_model_artifact` |
| [tests/test_artifact_progress.py:102](D:/projects/Speech-Emotion-Recognition/tests/test_artifact_progress.py:102) | `export_model_artifact` | `ser_lib.artifacts.export_model_artifact` |
| [tests/test_artifact_progress.py:156](D:/projects/Speech-Emotion-Recognition/tests/test_artifact_progress.py:156) | `export_model_artifact` | `ser_lib.artifacts.export_model_artifact` |
| [tests/test_artifacts.py:37](D:/projects/Speech-Emotion-Recognition/tests/test_artifacts.py:37) | `export_model_artifact` | `ser_lib.artifacts.export_model_artifact` |
| [tests/test_artifacts.py:43](D:/projects/Speech-Emotion-Recognition/tests/test_artifacts.py:43) | `load_model_artifact` | `ser_lib.artifacts.load_model_artifact` |
| [tests/test_artifacts.py:55](D:/projects/Speech-Emotion-Recognition/tests/test_artifacts.py:55) | `export_model_artifact` | `ser_lib.artifacts.export_model_artifact` |
| [tests/test_artifacts.py:68](D:/projects/Speech-Emotion-Recognition/tests/test_artifacts.py:68) | `export_model_artifact` | `ser_lib.artifacts.export_model_artifact` |
| [tests/test_artifacts.py:72](D:/projects/Speech-Emotion-Recognition/tests/test_artifacts.py:72) | `load_model_artifact` | `ser_lib.artifacts.load_model_artifact` |
| [tests/test_artifacts.py:88](D:/projects/Speech-Emotion-Recognition/tests/test_artifacts.py:88) | `export_model_artifact` | `ser_lib.artifacts.export_model_artifact` |
| [tests/test_artifacts.py:123](D:/projects/Speech-Emotion-Recognition/tests/test_artifacts.py:123) | `export_model_artifact` | `ser_lib.artifacts.export_model_artifact` |
| [tests/test_artifacts.py:155](D:/projects/Speech-Emotion-Recognition/tests/test_artifacts.py:155) | `load_model_artifact` | `ser_lib.artifacts.load_model_artifact` |
| [tests/test_artifacts.py:63](D:/projects/Speech-Emotion-Recognition/tests/test_artifacts.py:63) | `load_model_artifact` | `ser_lib.artifacts.load_model_artifact` |
| [tests/test_artifacts.py:79](D:/projects/Speech-Emotion-Recognition/tests/test_artifacts.py:79) | `export_model_artifact` | `ser_lib.artifacts.export_model_artifact` |
| [tests/test_artifacts.py:113](D:/projects/Speech-Emotion-Recognition/tests/test_artifacts.py:113) | `export_model_artifact` | `ser_lib.artifacts.export_model_artifact` |
| [tests/test_artifacts.py:154](D:/projects/Speech-Emotion-Recognition/tests/test_artifacts.py:154) | `load_model_artifact` | `ser_lib.artifacts.load_model_artifact` |
| [tests/test_batch_prediction_sink.py:98](D:/projects/Speech-Emotion-Recognition/tests/test_batch_prediction_sink.py:98) | `InferenceService.predict_records` | `ser_lib.services.InferenceService.predict_records` |
| [tests/test_checkpoint_catalog.py:55](D:/projects/Speech-Emotion-Recognition/tests/test_checkpoint_catalog.py:55) | `TrainingService.scan_checkpoints` | `ser_lib.services.TrainingService.scan_checkpoints` |
| [tests/test_checkpoint_resume.py:102](D:/projects/Speech-Emotion-Recognition/tests/test_checkpoint_resume.py:102) | `continuous.fit` | `实例/局部 factory；需结合上下文` |
| [tests/test_checkpoint_resume.py:118](D:/projects/Speech-Emotion-Recognition/tests/test_checkpoint_resume.py:118) | `resumed.resume_from` | `实例/局部 factory；需结合上下文` |
| [tests/test_checkpoint_resume.py:119](D:/projects/Speech-Emotion-Recognition/tests/test_checkpoint_resume.py:119) | `resumed.fit` | `实例/局部 factory；需结合上下文` |
| [tests/test_checkpoint_resume.py:112](D:/projects/Speech-Emotion-Recognition/tests/test_checkpoint_resume.py:112) | `interrupted.fit` | `实例/局部 factory；需结合上下文` |
| [tests/test_cli_lineage.py:93](D:/projects/Speech-Emotion-Recognition/tests/test_cli_lineage.py:93) | `TrainingService.inspect_history` | `ser_lib.services.TrainingService.inspect_history` |
| [tests/test_compatibility_report.py:38](D:/projects/Speech-Emotion-Recognition/tests/test_compatibility_report.py:38) | `validate_compatibility` | `ser_lib.data.validation.validate_compatibility` |
| [tests/test_compatibility_report.py:121](D:/projects/Speech-Emotion-Recognition/tests/test_compatibility_report.py:121) | `validate_compatibility` | `ser_lib.data.validation.validate_compatibility` |
| [tests/test_dataset_history.py:92](D:/projects/Speech-Emotion-Recognition/tests/test_dataset_history.py:92) | `DatasetService.snapshot_revision` | `ser_lib.services.DatasetService.snapshot_revision` |
| [tests/test_dataset_history.py:101](D:/projects/Speech-Emotion-Recognition/tests/test_dataset_history.py:101) | `DatasetService.revision_history` | `ser_lib.services.DatasetService.revision_history` |
| [tests/test_dataset_history.py:144](D:/projects/Speech-Emotion-Recognition/tests/test_dataset_history.py:144) | `DatasetService.restore_revision` | `ser_lib.services.DatasetService.restore_revision` |
| [tests/test_dataset_profile.py:86](D:/projects/Speech-Emotion-Recognition/tests/test_dataset_profile.py:86) | `DatasetService.detailed_profile` | `ser_lib.services.DatasetService.detailed_profile` |
| [tests/test_dataset_profile.py:111](D:/projects/Speech-Emotion-Recognition/tests/test_dataset_profile.py:111) | `DatasetService.profile` | `ser_lib.services.DatasetService.profile` |
| [tests/test_dataset_query.py:43](D:/projects/Speech-Emotion-Recognition/tests/test_dataset_query.py:43) | `query_records` | `ser_lib.data.query_records` |
| [tests/test_dataset_query.py:56](D:/projects/Speech-Emotion-Recognition/tests/test_dataset_query.py:56) | `query_records` | `ser_lib.data.query_records` |
| [tests/test_dataset_query.py:59](D:/projects/Speech-Emotion-Recognition/tests/test_dataset_query.py:59) | `query_records` | `ser_lib.data.query_records` |
| [tests/test_dataset_query.py:63](D:/projects/Speech-Emotion-Recognition/tests/test_dataset_query.py:63) | `query_records` | `ser_lib.data.query_records` |
| [tests/test_dataset_query.py:71](D:/projects/Speech-Emotion-Recognition/tests/test_dataset_query.py:71) | `query_records` | `ser_lib.data.query_records` |
| [tests/test_dataset_query.py:72](D:/projects/Speech-Emotion-Recognition/tests/test_dataset_query.py:72) | `query_records` | `ser_lib.data.query_records` |
| [tests/test_dataset_query.py:94](D:/projects/Speech-Emotion-Recognition/tests/test_dataset_query.py:94) | `query_records` | `ser_lib.data.query_records` |
| [tests/test_dataset_query.py:96](D:/projects/Speech-Emotion-Recognition/tests/test_dataset_query.py:96) | `query_records` | `ser_lib.data.query_records` |
| [tests/test_engine_config.py:113](D:/projects/Speech-Emotion-Recognition/tests/test_engine_config.py:113) | `trainer.fit` | `实例/局部 factory；需结合上下文` |
| [tests/test_engine_config.py:153](D:/projects/Speech-Emotion-Recognition/tests/test_engine_config.py:153) | `build_experiment_components` | `ser_lib.engine.build_experiment_components` |
| [tests/test_engine_config.py:185](D:/projects/Speech-Emotion-Recognition/tests/test_engine_config.py:185) | `trainer.fit` | `实例/局部 factory；需结合上下文` |
| [tests/test_engine_config.py:201](D:/projects/Speech-Emotion-Recognition/tests/test_engine_config.py:201) | `resumed.resume_from` | `实例/局部 factory；需结合上下文` |
| [tests/test_engine_config.py:127](D:/projects/Speech-Emotion-Recognition/tests/test_engine_config.py:127) | `trainer.fit` | `实例/局部 factory；需结合上下文` |
| [tests/test_engine_config.py:167](D:/projects/Speech-Emotion-Recognition/tests/test_engine_config.py:167) | `build_experiment_components` | `ser_lib.engine.build_experiment_components` |
| [tests/test_engine_config.py:213](D:/projects/Speech-Emotion-Recognition/tests/test_engine_config.py:213) | `trainer.fit` | `实例/局部 factory；需结合上下文` |
| [tests/test_evaluation_prediction_query.py:52](D:/projects/Speech-Emotion-Recognition/tests/test_evaluation_prediction_query.py:52) | `EvaluationService.query_predictions` | `ser_lib.services.EvaluationService.query_predictions` |
| [tests/test_evaluation_prediction_query.py:66](D:/projects/Speech-Emotion-Recognition/tests/test_evaluation_prediction_query.py:66) | `query_evaluation_predictions` | `ser_lib.engine.query_evaluation_predictions` |
| [tests/test_evaluation_prediction_query.py:82](D:/projects/Speech-Emotion-Recognition/tests/test_evaluation_prediction_query.py:82) | `query_evaluation_predictions` | `ser_lib.engine.query_evaluation_predictions` |
| [tests/test_evaluation_prediction_query.py:83](D:/projects/Speech-Emotion-Recognition/tests/test_evaluation_prediction_query.py:83) | `query_evaluation_predictions` | `ser_lib.engine.query_evaluation_predictions` |
| [tests/test_evaluation_prediction_query.py:84](D:/projects/Speech-Emotion-Recognition/tests/test_evaluation_prediction_query.py:84) | `query_evaluation_predictions` | `ser_lib.engine.query_evaluation_predictions` |
| [tests/test_evaluation_prediction_query.py:108](D:/projects/Speech-Emotion-Recognition/tests/test_evaluation_prediction_query.py:108) | `query_evaluation_predictions` | `ser_lib.engine.query_evaluation_predictions` |
| [tests/test_evaluation_prediction_query.py:116](D:/projects/Speech-Emotion-Recognition/tests/test_evaluation_prediction_query.py:116) | `query_evaluation_predictions` | `ser_lib.engine.query_evaluation_predictions` |
| [tests/test_evaluation_prediction_query.py:125](D:/projects/Speech-Emotion-Recognition/tests/test_evaluation_prediction_query.py:125) | `query_evaluation_predictions` | `ser_lib.engine.query_evaluation_predictions` |
| [tests/test_evaluation_prediction_query.py:134](D:/projects/Speech-Emotion-Recognition/tests/test_evaluation_prediction_query.py:134) | `query_evaluation_predictions` | `ser_lib.engine.query_evaluation_predictions` |
| [tests/test_evaluation_report_inspect.py:75](D:/projects/Speech-Emotion-Recognition/tests/test_evaluation_report_inspect.py:75) | `EvaluationService.inspect_report` | `ser_lib.services.EvaluationService.inspect_report` |
| [tests/test_evaluation_run_catalog.py:72](D:/projects/Speech-Emotion-Recognition/tests/test_evaluation_run_catalog.py:72) | `EvaluationService.scan_runs` | `ser_lib.services.EvaluationService.scan_runs` |
| [tests/test_evaluation_run_detail.py:106](D:/projects/Speech-Emotion-Recognition/tests/test_evaluation_run_detail.py:106) | `EvaluationService.inspect_run_detail` | `ser_lib.services.EvaluationService.inspect_run_detail` |
| [tests/test_evaluation_run_detail.py:125](D:/projects/Speech-Emotion-Recognition/tests/test_evaluation_run_detail.py:125) | `EvaluationService.inspect_run_detail` | `ser_lib.services.EvaluationService.inspect_run_detail` |
| [tests/test_evaluation_run_detail.py:139](D:/projects/Speech-Emotion-Recognition/tests/test_evaluation_run_detail.py:139) | `EvaluationService.inspect_run_detail` | `ser_lib.services.EvaluationService.inspect_run_detail` |
| [tests/test_evaluation_run_detail.py:154](D:/projects/Speech-Emotion-Recognition/tests/test_evaluation_run_detail.py:154) | `EvaluationService.inspect_run_detail` | `ser_lib.services.EvaluationService.inspect_run_detail` |
| [tests/test_evaluation_run_detail.py:173](D:/projects/Speech-Emotion-Recognition/tests/test_evaluation_run_detail.py:173) | `EvaluationService.inspect_run_detail` | `ser_lib.services.EvaluationService.inspect_run_detail` |
| [tests/test_evaluation_run_metadata.py:101](D:/projects/Speech-Emotion-Recognition/tests/test_evaluation_run_metadata.py:101) | `EvaluationService.create_run_metadata` | `ser_lib.services.EvaluationService.create_run_metadata` |
| [tests/test_evaluation_run_metadata.py:116](D:/projects/Speech-Emotion-Recognition/tests/test_evaluation_run_metadata.py:116) | `EvaluationService.save_run` | `ser_lib.services.EvaluationService.save_run` |
| [tests/test_evaluation_run_metadata.py:123](D:/projects/Speech-Emotion-Recognition/tests/test_evaluation_run_metadata.py:123) | `EvaluationService.inspect_run` | `ser_lib.services.EvaluationService.inspect_run` |
| [tests/test_experiment_validation.py:202](D:/projects/Speech-Emotion-Recognition/tests/test_experiment_validation.py:202) | `model_registry.inspect_spec` | `ser_lib.models.registry.model_registry.inspect_spec` |
| [tests/test_model_engine.py:36](D:/projects/Speech-Emotion-Recognition/tests/test_model_engine.py:36) | `model_registry.create` | `ser_lib.models.registry.model_registry.create` |
| [tests/test_model_engine.py:44](D:/projects/Speech-Emotion-Recognition/tests/test_model_engine.py:44) | `model_registry.create` | `ser_lib.models.registry.model_registry.create` |
| [tests/test_model_engine.py:81](D:/projects/Speech-Emotion-Recognition/tests/test_model_engine.py:81) | `validate_compatibility` | `ser_lib.data.validation.validate_compatibility` |
| [tests/test_pretrained_adapter.py:181](D:/projects/Speech-Emotion-Recognition/tests/test_pretrained_adapter.py:181) | `model_registry.create` | `ser_lib.models.model_registry.create` |
| [tests/test_pretrained_adapter.py:185](D:/projects/Speech-Emotion-Recognition/tests/test_pretrained_adapter.py:185) | `export_model_artifact` | `ser_lib.artifacts.export_model_artifact` |
| [tests/test_pretrained_adapter.py:189](D:/projects/Speech-Emotion-Recognition/tests/test_pretrained_adapter.py:189) | `load_model_artifact` | `ser_lib.artifacts.load_model_artifact` |
| [tests/test_pretrained_adapter.py:204](D:/projects/Speech-Emotion-Recognition/tests/test_pretrained_adapter.py:204) | `validate_compatibility` | `ser_lib.data.validate_compatibility` |
| [tests/test_registry_config.py:20](D:/projects/Speech-Emotion-Recognition/tests/test_registry_config.py:20) | `registry.register` | `实例/局部 factory；需结合上下文` |
| [tests/test_registry_config.py:33](D:/projects/Speech-Emotion-Recognition/tests/test_registry_config.py:33) | `registry.register` | `实例/局部 factory；需结合上下文` |
| [tests/test_registry_config.py:39](D:/projects/Speech-Emotion-Recognition/tests/test_registry_config.py:39) | `registry.create` | `实例/局部 factory；需结合上下文` |
| [tests/test_release_examples.py:27](D:/projects/Speech-Emotion-Recognition/tests/test_release_examples.py:27) | `build_experiment_components` | `ser_lib.engine.build_experiment_components` |
| [tests/test_rnn_models.py:46](D:/projects/Speech-Emotion-Recognition/tests/test_rnn_models.py:46) | `model_registry.create` | `ser_lib.models.model_registry.create` |
| [tests/test_rnn_models.py:92](D:/projects/Speech-Emotion-Recognition/tests/test_rnn_models.py:92) | `export_model_artifact` | `ser_lib.artifacts.export_model_artifact` |
| [tests/test_rnn_models.py:96](D:/projects/Speech-Emotion-Recognition/tests/test_rnn_models.py:96) | `load_model_artifact` | `ser_lib.artifacts.load_model_artifact` |
| [tests/test_rnn_models.py:54](D:/projects/Speech-Emotion-Recognition/tests/test_rnn_models.py:54) | `model_registry.create` | `ser_lib.models.model_registry.create` |
| [tests/test_runtime_metrics.py:48](D:/projects/Speech-Emotion-Recognition/tests/test_runtime_metrics.py:48) | `RuntimeService.metrics` | `ser_lib.services.RuntimeService.metrics` |
| [tests/test_schema_migrations.py:21](D:/projects/Speech-Emotion-Recognition/tests/test_schema_migrations.py:21) | `registry.register` | `实例/局部 factory；需结合上下文` |
| [tests/test_schema_migrations.py:22](D:/projects/Speech-Emotion-Recognition/tests/test_schema_migrations.py:22) | `registry.register` | `实例/局部 factory；需结合上下文` |
| [tests/test_schema_migrations.py:66](D:/projects/Speech-Emotion-Recognition/tests/test_schema_migrations.py:66) | `registry.register` | `实例/局部 factory；需结合上下文` |
| [tests/test_schema_migrations.py:78](D:/projects/Speech-Emotion-Recognition/tests/test_schema_migrations.py:78) | `registry.register` | `实例/局部 factory；需结合上下文` |
| [tests/test_schema_migrations.py:64](D:/projects/Speech-Emotion-Recognition/tests/test_schema_migrations.py:64) | `registry.register` | `实例/局部 factory；需结合上下文` |
| [tests/test_schema_migrations.py:80](D:/projects/Speech-Emotion-Recognition/tests/test_schema_migrations.py:80) | `registry.register` | `实例/局部 factory；需结合上下文` |
| [tests/test_service_catalog_presets.py:10](D:/projects/Speech-Emotion-Recognition/tests/test_service_catalog_presets.py:10) | `CatalogService.presets` | `ser_lib.services.CatalogService.presets` |
| [tests/test_service_catalog_presets.py:14](D:/projects/Speech-Emotion-Recognition/tests/test_service_catalog_presets.py:14) | `CatalogService.get_preset` | `ser_lib.services.CatalogService.get_preset` |
| [tests/test_service_catalog_presets.py:17](D:/projects/Speech-Emotion-Recognition/tests/test_service_catalog_presets.py:17) | `CatalogService.build_experiment` | `ser_lib.services.CatalogService.build_experiment` |
| [tests/test_services.py:103](D:/projects/Speech-Emotion-Recognition/tests/test_services.py:103) | `DatasetService.summary` | `ser_lib.services.DatasetService.summary` |
| [tests/test_services.py:104](D:/projects/Speech-Emotion-Recognition/tests/test_services.py:104) | `DatasetService.query` | `ser_lib.services.DatasetService.query` |
| [tests/test_services.py:105](D:/projects/Speech-Emotion-Recognition/tests/test_services.py:105) | `DatasetService.fingerprint` | `ser_lib.services.DatasetService.fingerprint` |
| [tests/test_services.py:106](D:/projects/Speech-Emotion-Recognition/tests/test_services.py:106) | `DatasetService.editor` | `ser_lib.services.DatasetService.editor` |
| [tests/test_services.py:118](D:/projects/Speech-Emotion-Recognition/tests/test_services.py:118) | `CatalogService.snapshot` | `ser_lib.services.CatalogService.snapshot` |
| [tests/test_services.py:122](D:/projects/Speech-Emotion-Recognition/tests/test_services.py:122) | `RuntimeService.capabilities` | `ser_lib.services.RuntimeService.capabilities` |
| [tests/test_services.py:136](D:/projects/Speech-Emotion-Recognition/tests/test_services.py:136) | `TrainingService.run` | `ser_lib.services.TrainingService.run` |
| [tests/test_services.py:137](D:/projects/Speech-Emotion-Recognition/tests/test_services.py:137) | `EvaluationService.run` | `ser_lib.services.EvaluationService.run` |
| [tests/test_services.py:149](D:/projects/Speech-Emotion-Recognition/tests/test_services.py:149) | `ArtifactService.export` | `ser_lib.services.ArtifactService.export` |
| [tests/test_services.py:157](D:/projects/Speech-Emotion-Recognition/tests/test_services.py:157) | `ArtifactService.inspect` | `ser_lib.services.ArtifactService.inspect` |
| [tests/test_services.py:158](D:/projects/Speech-Emotion-Recognition/tests/test_services.py:158) | `ArtifactService.verify` | `ser_lib.services.ArtifactService.verify` |
| [tests/test_services.py:120](D:/projects/Speech-Emotion-Recognition/tests/test_services.py:120) | `CatalogService.list` | `ser_lib.services.CatalogService.list` |
| [tests/test_services.py:119](D:/projects/Speech-Emotion-Recognition/tests/test_services.py:119) | `CatalogService.get` | `ser_lib.services.CatalogService.get` |
| [tests/test_trainer_observability.py:70](D:/projects/Speech-Emotion-Recognition/tests/test_trainer_observability.py:70) | `trainer.fit` | `实例/局部 factory；需结合上下文` |
| [tests/test_trainer_observability.py:132](D:/projects/Speech-Emotion-Recognition/tests/test_trainer_observability.py:132) | `trainer.fit` | `实例/局部 factory；需结合上下文` |
| [tests/test_trainer_observability.py:159](D:/projects/Speech-Emotion-Recognition/tests/test_trainer_observability.py:159) | `trainer.fit` | `实例/局部 factory；需结合上下文` |
| [tests/test_trainer_observability.py:213](D:/projects/Speech-Emotion-Recognition/tests/test_trainer_observability.py:213) | `plain.fit` | `实例/局部 factory；需结合上下文` |
| [tests/test_trainer_observability.py:224](D:/projects/Speech-Emotion-Recognition/tests/test_trainer_observability.py:224) | `observed.fit` | `实例/局部 factory；需结合上下文` |
| [tests/test_trainer_observability.py:242](D:/projects/Speech-Emotion-Recognition/tests/test_trainer_observability.py:242) | `trainer.fit` | `实例/局部 factory；需结合上下文` |
| [tests/test_trainer_observability.py:245](D:/projects/Speech-Emotion-Recognition/tests/test_trainer_observability.py:245) | `resumed.resume_from` | `实例/局部 factory；需结合上下文` |
| [tests/test_trainer_observability.py:191](D:/projects/Speech-Emotion-Recognition/tests/test_trainer_observability.py:191) | `trainer.fit` | `实例/局部 factory；需结合上下文` |
| [tests/test_training_history.py:35](D:/projects/Speech-Emotion-Recognition/tests/test_training_history.py:35) | `TrainingService.inspect_history` | `ser_lib.services.TrainingService.inspect_history` |
| [tests/test_training_lineage.py:68](D:/projects/Speech-Emotion-Recognition/tests/test_training_lineage.py:68) | `TrainingService.create_trainer` | `ser_lib.services.TrainingService.create_trainer` |
| [tests/test_training_lineage.py:75](D:/projects/Speech-Emotion-Recognition/tests/test_training_lineage.py:75) | `TrainingService.get_run_metadata` | `ser_lib.services.TrainingService.get_run_metadata` |
| [tests/test_training_lineage.py:92](D:/projects/Speech-Emotion-Recognition/tests/test_training_lineage.py:92) | `TrainingService.create_trainer` | `ser_lib.services.TrainingService.create_trainer` |
| [tests/test_training_lineage.py:98](D:/projects/Speech-Emotion-Recognition/tests/test_training_lineage.py:98) | `TrainingService.get_run_metadata` | `ser_lib.services.TrainingService.get_run_metadata` |
| [tests/test_training_lineage.py:101](D:/projects/Speech-Emotion-Recognition/tests/test_training_lineage.py:101) | `TrainingService.run` | `ser_lib.services.TrainingService.run` |
| [tests/test_training_lineage.py:112](D:/projects/Speech-Emotion-Recognition/tests/test_training_lineage.py:112) | `ArtifactService.export` | `ser_lib.services.ArtifactService.export` |
| [tests/test_training_lineage.py:120](D:/projects/Speech-Emotion-Recognition/tests/test_training_lineage.py:120) | `ArtifactService.inspect` | `ser_lib.services.ArtifactService.inspect` |
| [tests/test_training_lineage.py:129](D:/projects/Speech-Emotion-Recognition/tests/test_training_lineage.py:129) | `TrainingService.create_trainer` | `ser_lib.services.TrainingService.create_trainer` |
| [tests/test_training_lineage.py:135](D:/projects/Speech-Emotion-Recognition/tests/test_training_lineage.py:135) | `TrainingService.run` | `ser_lib.services.TrainingService.run` |
| [tests/test_training_lineage.py:137](D:/projects/Speech-Emotion-Recognition/tests/test_training_lineage.py:137) | `TrainingService.create_trainer` | `ser_lib.services.TrainingService.create_trainer` |
| [tests/test_training_lineage.py:138](D:/projects/Speech-Emotion-Recognition/tests/test_training_lineage.py:138) | `resumed.resume_from` | `实例/局部 factory；需结合上下文` |
| [tests/test_training_lineage.py:139](D:/projects/Speech-Emotion-Recognition/tests/test_training_lineage.py:139) | `TrainingService.get_run_metadata` | `ser_lib.services.TrainingService.get_run_metadata` |
| [tests/test_training_result.py:50](D:/projects/Speech-Emotion-Recognition/tests/test_training_result.py:50) | `trainer.fit` | `实例/局部 factory；需结合上下文` |
| [tests/test_training_result.py:86](D:/projects/Speech-Emotion-Recognition/tests/test_training_result.py:86) | `trainer.fit` | `实例/局部 factory；需结合上下文` |
| [tests/test_training_result.py:116](D:/projects/Speech-Emotion-Recognition/tests/test_training_result.py:116) | `trainer.fit` | `实例/局部 factory；需结合上下文` |
| [tests/test_training_result.py:176](D:/projects/Speech-Emotion-Recognition/tests/test_training_result.py:176) | `source.fit` | `实例/局部 factory；需结合上下文` |
| [tests/test_training_result.py:179](D:/projects/Speech-Emotion-Recognition/tests/test_training_result.py:179) | `resumed.resume_from` | `实例/局部 factory；需结合上下文` |
| [tests/test_training_result.py:182](D:/projects/Speech-Emotion-Recognition/tests/test_training_result.py:182) | `resumed.fit` | `实例/局部 factory；需结合上下文` |
| [tests/test_training_result.py:138](D:/projects/Speech-Emotion-Recognition/tests/test_training_result.py:138) | `trainer.fit` | `实例/局部 factory；需结合上下文` |
| [tests/test_training_result.py:157](D:/projects/Speech-Emotion-Recognition/tests/test_training_result.py:157) | `trainer.fit` | `实例/局部 factory；需结合上下文` |
| [tests/test_training_run_catalog.py:73](D:/projects/Speech-Emotion-Recognition/tests/test_training_run_catalog.py:73) | `TrainingService.create_trainer` | `ser_lib.services.TrainingService.create_trainer` |
| [tests/test_training_run_catalog.py:80](D:/projects/Speech-Emotion-Recognition/tests/test_training_run_catalog.py:80) | `TrainingService.run` | `ser_lib.services.TrainingService.run` |
| [tests/test_training_run_catalog.py:88](D:/projects/Speech-Emotion-Recognition/tests/test_training_run_catalog.py:88) | `TrainingService.save_run` | `ser_lib.services.TrainingService.save_run` |
| [tests/test_training_run_catalog.py:103](D:/projects/Speech-Emotion-Recognition/tests/test_training_run_catalog.py:103) | `TrainingService.inspect_run` | `ser_lib.services.TrainingService.inspect_run` |
| [tests/test_training_run_catalog.py:111](D:/projects/Speech-Emotion-Recognition/tests/test_training_run_catalog.py:111) | `TrainingService.save_run` | `ser_lib.services.TrainingService.save_run` |
| [tests/test_training_run_catalog.py:125](D:/projects/Speech-Emotion-Recognition/tests/test_training_run_catalog.py:125) | `TrainingService.save_run` | `ser_lib.services.TrainingService.save_run` |
| [tests/test_training_run_catalog.py:131](D:/projects/Speech-Emotion-Recognition/tests/test_training_run_catalog.py:131) | `TrainingService.scan_runs` | `ser_lib.services.TrainingService.scan_runs` |
| [tests/test_training_run_catalog.py:137](D:/projects/Speech-Emotion-Recognition/tests/test_training_run_catalog.py:137) | `TrainingService.scan_runs` | `ser_lib.services.TrainingService.scan_runs` |
| [tests/test_training_run_catalog.py:176](D:/projects/Speech-Emotion-Recognition/tests/test_training_run_catalog.py:176) | `TrainingService.save_run` | `ser_lib.services.TrainingService.save_run` |
| [tests/test_training_run_catalog.py:204](D:/projects/Speech-Emotion-Recognition/tests/test_training_run_catalog.py:204) | `TrainingService.get_run_metadata` | `ser_lib.services.TrainingService.get_run_metadata` |
| [tests/test_training_run_catalog.py:215](D:/projects/Speech-Emotion-Recognition/tests/test_training_run_catalog.py:215) | `TrainingService.run` | `ser_lib.services.TrainingService.run` |
| [tests/test_training_run_catalog.py:217](D:/projects/Speech-Emotion-Recognition/tests/test_training_run_catalog.py:217) | `TrainingService.save_run` | `ser_lib.services.TrainingService.save_run` |
| [tests/test_training_run_detail.py:94](D:/projects/Speech-Emotion-Recognition/tests/test_training_run_detail.py:94) | `TrainingService.inspect_run_detail` | `ser_lib.services.TrainingService.inspect_run_detail` |
| [tests/test_training_run_detail.py:114](D:/projects/Speech-Emotion-Recognition/tests/test_training_run_detail.py:114) | `TrainingService.inspect_run_detail` | `ser_lib.services.TrainingService.inspect_run_detail` |
| [tests/test_training_run_detail.py:137](D:/projects/Speech-Emotion-Recognition/tests/test_training_run_detail.py:137) | `TrainingService.inspect_run_detail` | `ser_lib.services.TrainingService.inspect_run_detail` |
| [tests/test_training_run_detail.py:151](D:/projects/Speech-Emotion-Recognition/tests/test_training_run_detail.py:151) | `TrainingService.inspect_run_detail` | `ser_lib.services.TrainingService.inspect_run_detail` |
| [tests/test_training_run_detail.py:179](D:/projects/Speech-Emotion-Recognition/tests/test_training_run_detail.py:179) | `TrainingService.inspect_run_detail` | `ser_lib.services.TrainingService.inspect_run_detail` |
| [tests/test_transformer_models.py:49](D:/projects/Speech-Emotion-Recognition/tests/test_transformer_models.py:49) | `model_registry.create` | `ser_lib.models.model_registry.create` |
| [tests/test_transformer_models.py:57](D:/projects/Speech-Emotion-Recognition/tests/test_transformer_models.py:57) | `model_registry.create` | `ser_lib.models.model_registry.create` |
| [tests/test_transformer_models.py:109](D:/projects/Speech-Emotion-Recognition/tests/test_transformer_models.py:109) | `export_model_artifact` | `ser_lib.artifacts.export_model_artifact` |
| [tests/test_transformer_models.py:113](D:/projects/Speech-Emotion-Recognition/tests/test_transformer_models.py:113) | `load_model_artifact` | `ser_lib.artifacts.load_model_artifact` |

## G. UI/DTO/历史兼容关键词命中

这些仅是审计线索；最终处理以正文与 A 为准。关键词在注释出现不构成产品依赖。只列源码，避免把历史设计文档当现状。

| 位置 | 源码行 |
| --- | --- |
| [ser_lib/__init__.py:36](D:/projects/Speech-Emotion-Recognition/ser_lib/__init__.py:36) | `EvaluationPredictionPage,` |
| [ser_lib/__init__.py:39](D:/projects/Speech-Emotion-Recognition/ser_lib/__init__.py:39) | `EvaluationRunDetail,` |
| [ser_lib/__init__.py:55](D:/projects/Speech-Emotion-Recognition/ser_lib/__init__.py:55) | `TrainingRunDetail,` |
| [ser_lib/__init__.py:137](D:/projects/Speech-Emotion-Recognition/ser_lib/__init__.py:137) | `"RUN_RECORD_SCHEMA_VERSION", "TrainingRunInfo", "TrainingRunDetail",` |
| [ser_lib/__init__.py:144](D:/projects/Speech-Emotion-Recognition/ser_lib/__init__.py:144) | `"EvaluationPredictionFileInfo", "EvaluationRunDetail",` |
| [ser_lib/__init__.py:149](D:/projects/Speech-Emotion-Recognition/ser_lib/__init__.py:149) | `"EvaluationReportInfo", "EvaluationPredictionPage",` |
| [ser_lib/artifacts/catalog.py:17](D:/projects/Speech-Emotion-Recognition/ser_lib/artifacts/catalog.py:17) | `"""模型管理列表所需的轻量、JSON-safe Artifact 信息。"""` |
| [ser_lib/artifacts/loader.py:44](D:/projects/Speech-Emotion-Recognition/ser_lib/artifacts/loader.py:44) | `"""兼容旧内部测试/调用的无观察 SHA256 helper。"""` |
| [ser_lib/artifacts/loader.py:97](D:/projects/Speech-Emotion-Recognition/ser_lib/artifacts/loader.py:97) | `# 然后继续交给当前 ModelArtifactManifest 的 legacy defaults/严格验证。` |
| [ser_lib/artifacts/loader.py:283](D:/projects/Speech-Emotion-Recognition/ser_lib/artifacts/loader.py:283) | `allow_legacy_pickle: bool = False,` |
| [ser_lib/artifacts/loader.py:305](D:/projects/Speech-Emotion-Recognition/ser_lib/artifacts/loader.py:305) | `elif manifest.weights_format == "pytorch" and allow_legacy_pickle:` |
| [ser_lib/artifacts/loader.py:309](D:/projects/Speech-Emotion-Recognition/ser_lib/artifacts/loader.py:309) | `"旧 PyTorch artifact 可能包含 pickle；仅可信文件可设置 allow_legacy_pickle=True"` |
| [ser_lib/artifacts/manifest.py:42](D:/projects/Speech-Emotion-Recognition/ser_lib/artifacts/manifest.py:42) | `def _legacy_defaults(cls, value: Any) -> Any:` |
| [ser_lib/catalog.py:1](D:/projects/Speech-Emotion-Recognition/ser_lib/catalog.py:1) | `"""供 Web/CLI 查询的统一组件目录。` |
| [ser_lib/catalog.py:206](D:/projects/Speech-Emotion-Recognition/ser_lib/catalog.py:206) | `"""稳定、JSON-safe 的组件目录快照。"""` |
| [ser_lib/core/_catalog_scan.py:1](D:/projects/Speech-Emotion-Recognition/ser_lib/core/_catalog_scan.py:1) | `"""Catalog 扫描器共享控制流；领域 candidate、DTO 与排序规则保持独立。"""` |
| [ser_lib/core/_catalog_scan.py:29](D:/projects/Speech-Emotion-Recognition/ser_lib/core/_catalog_scan.py:29) | `例如 Dataset revision 属于其他 dataset_id。候选发现、结果排序和领域 DTO` |
| [ser_lib/core/diagnostics.py:1](D:/projects/Speech-Emotion-Recognition/ser_lib/core/diagnostics.py:1) | `"""面向 CLI/Web 的结构化诊断协议。` |
| [ser_lib/core/diagnostics.py:45](D:/projects/Speech-Emotion-Recognition/ser_lib/core/diagnostics.py:45) | `"""一个稳定、可 JSON 序列化、可由 UI 直接展示的诊断项。"""` |
| [ser_lib/core/events.py:255](D:/projects/Speech-Emotion-Recognition/ser_lib/core/events.py:255) | `"""描述 checkpoint 保存生命周期，供 UI 展示而无需扫描文件系统。"""` |
| [ser_lib/data/__init__.py:35](D:/projects/Speech-Emotion-Recognition/ser_lib/data/__init__.py:35) | `from ser_lib.data.query import RecordPage, RecordView, query_records` |
| [ser_lib/data/__init__.py:69](D:/projects/Speech-Emotion-Recognition/ser_lib/data/__init__.py:69) | `"RecordView", "RecordPage", "query_records", "DatasetFingerprint", "fingerprint_manifest",` |
| [ser_lib/data/editor.py:1](D:/projects/Speech-Emotion-Recognition/ser_lib/data/editor.py:1) | `"""面向 Web/CLI 的 Dataset 编辑器与多文件事务提交。"""` |
| [ser_lib/data/errors.py:19](D:/projects/Speech-Emotion-Recognition/ser_lib/data/errors.py:19) | `Web/CLI 不需要通过异常类名或消息字符串推断错误类型。` |
| [ser_lib/data/importers/base.py:67](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/base.py:67) | `"""返回单轨、JSON-safe 的预览摘要。"""` |
| [ser_lib/data/importers/emotiontalk.py:123](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/emotiontalk.py:123) | `details={"entry_index": index, "detail": str(exc)},` |
| [ser_lib/data/importers/jsonl_importer.py:23](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/jsonl_importer.py:23) | `LEGACY_ALIASES = {` |
| [ser_lib/data/importers/jsonl_importer.py:44](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/jsonl_importer.py:44) | `elif key in LEGACY_ALIASES:` |
| [ser_lib/data/importers/jsonl_importer.py:45](D:/projects/Speech-Emotion-Recognition/ser_lib/data/importers/jsonl_importer.py:45) | `canonical = LEGACY_ALIASES[key]` |
| [ser_lib/data/profiling.py:58](D:/projects/Speech-Emotion-Recognition/ser_lib/data/profiling.py:58) | `"""供 CLI/Web 列表和详情首屏直接消费的数据集摘要。` |
| [ser_lib/data/profiling.py:84](D:/projects/Speech-Emotion-Recognition/ser_lib/data/profiling.py:84) | `"""供可视化数据集分析页使用的详细、JSON-safe profile。"""` |
| [ser_lib/data/profiling.py:268](D:/projects/Speech-Emotion-Recognition/ser_lib/data/profiling.py:268) | `"""构建稳定、JSON-safe 的轻量数据集摘要。` |
| [ser_lib/data/query.py:1](D:/projects/Speech-Emotion-Recognition/ser_lib/data/query.py:1) | `"""面向数据浏览器的稳定查询与分页 DTO。"""` |
| [ser_lib/data/query.py:16](D:/projects/Speech-Emotion-Recognition/ser_lib/data/query.py:16) | `class RecordView:` |
| [ser_lib/data/query.py:17](D:/projects/Speech-Emotion-Recognition/ser_lib/data/query.py:17) | `"""不泄漏内部 AudioRecord 的 JSON-safe 浏览视图。"""` |
| [ser_lib/data/query.py:34](D:/projects/Speech-Emotion-Recognition/ser_lib/data/query.py:34) | `class RecordPage:` |
| [ser_lib/data/query.py:35](D:/projects/Speech-Emotion-Recognition/ser_lib/data/query.py:35) | `items: tuple[RecordView, ...]` |
| [ser_lib/data/query.py:63](D:/projects/Speech-Emotion-Recognition/ser_lib/data/query.py:63) | `) -> RecordPage:` |
| [ser_lib/data/query.py:68](D:/projects/Speech-Emotion-Recognition/ser_lib/data/query.py:68) | `仅为 O(limit)，不会为所有命中记录提前构建 DTO。` |
| [ser_lib/data/query.py:88](D:/projects/Speech-Emotion-Recognition/ser_lib/data/query.py:88) | `items: list[RecordView] = []` |
| [ser_lib/data/query.py:107](D:/projects/Speech-Emotion-Recognition/ser_lib/data/query.py:107) | `return RecordPage(` |
| [ser_lib/data/query.py:115](D:/projects/Speech-Emotion-Recognition/ser_lib/data/query.py:115) | `def _to_view(record: AudioRecord, split: str) -> RecordView:` |
| [ser_lib/data/query.py:116](D:/projects/Speech-Emotion-Recognition/ser_lib/data/query.py:116) | `return RecordView(` |
| [ser_lib/data/query.py:161](D:/projects/Speech-Emotion-Recognition/ser_lib/data/query.py:161) | `__all__ = ["RecordPage", "RecordView", "query_records"]` |
| [ser_lib/data/registry.py:35](D:/projects/Speech-Emotion-Recognition/ser_lib/data/registry.py:35) | `config_schema 来自 Pydantic JSON Schema，Web 可据此动态生成参数表单；` |
| [ser_lib/data/representations/acoustic.py:203](D:/projects/Speech-Emotion-Recognition/ser_lib/data/representations/acoustic.py:203) | `"""对波形按 legacy 语义计算一阶/二阶差分并拼接，输出 [T, 3]。"""` |
| [ser_lib/data/validation.py:3](D:/projects/Speech-Emotion-Recognition/ser_lib/data/validation.py:3) | `inspect_compatibility 返回结构化报告，适合 Web/dry-run 展示；` |
| [ser_lib/engine/__init__.py:27](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/__init__.py:27) | `EvaluationRunDetail,` |
| [ser_lib/engine/__init__.py:31](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/__init__.py:31) | `EvaluationPredictionPage,` |
| [ser_lib/engine/__init__.py:82](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/__init__.py:82) | `TrainingRunDetail,` |
| [ser_lib/engine/__init__.py:107](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/__init__.py:107) | `"RUN_RECORD_SCHEMA_VERSION", "TrainingRunInfo", "TrainingRunDetail",` |
| [ser_lib/engine/__init__.py:112](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/__init__.py:112) | `"EvaluationPredictionFileInfo", "EvaluationRunDetail",` |
| [ser_lib/engine/__init__.py:124](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/__init__.py:124) | `"EvaluationResult", "EvaluationReportInfo", "EvaluationPredictionPage",` |
| [ser_lib/engine/_trainer_core.py:69](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/_trainer_core.py:69) | `"""一次 Trainer.fit 调用的稳定、JSON-safe 终态结果。"""` |
| [ser_lib/engine/_trainer_core.py:85](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/_trainer_core.py:85) | `"""返回可直接交给 Web/CLI JSON 层的标准字典。"""` |
| [ser_lib/engine/evaluation_detail.py:1](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/evaluation_detail.py:1) | `"""评估运行的轻量详情聚合 DTO 与 prediction 文件元数据。"""` |
| [ser_lib/engine/evaluation_detail.py:31](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/evaluation_detail.py:31) | `class EvaluationRunDetail:` |
| [ser_lib/engine/evaluation_detail.py:73](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/evaluation_detail.py:73) | `"EvaluationRunDetail",` |
| [ser_lib/engine/evaluation_reports.py:129](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/evaluation_reports.py:129) | `class EvaluationPredictionPage:` |
| [ser_lib/engine/evaluation_reports.py:212](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/evaluation_reports.py:212) | `) -> EvaluationPredictionPage:` |
| [ser_lib/engine/evaluation_reports.py:267](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/evaluation_reports.py:267) | `return EvaluationPredictionPage(` |
| [ser_lib/engine/evaluation_reports.py:280](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/evaluation_reports.py:280) | `"EvaluationPredictionPage",` |
| [ser_lib/engine/evaluator.py:58](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/evaluator.py:58) | `"""返回单样本预测的 JSON-safe 表示。"""` |
| [ser_lib/engine/evaluator.py:137](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/evaluator.py:137) | `"""返回公开 Result 的统一 JSON-safe 表示。` |
| [ser_lib/engine/evaluator.py:140](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/evaluator.py:140) | `完整预测，方便 Web Backend 直接消费结果而无需了解内部 dataclass/Tensor。` |
| [ser_lib/engine/evaluator.py:163](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/evaluator.py:163) | `"""兼容旧 API：返回不含样本明细的 JSON-safe 聚合报告。"""` |
| [ser_lib/engine/evaluator.py:250](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/evaluator.py:250) | `event_context 是与 Web/传输无关的运行上下文，可原生携带 run_id、` |
| [ser_lib/engine/lineage.py:12](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/lineage.py:12) | `"""一次训练运行的稳定、JSON-safe lineage 描述。` |
| [ser_lib/engine/lineage.py:15](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/lineage.py:15) | `计算 fingerprint。这样构造 Trainer 不会引入隐藏 I/O，也不会让 Web 创建任务` |
| [ser_lib/engine/lineage.py:106](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/lineage.py:106) | `"""构造 lineage DTO；不执行任何文件系统或数据集探测。"""` |
| [ser_lib/engine/runs.py:1](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/runs.py:1) | `"""训练运行记录的原子持久化、轻量 Catalog 扫描与详情聚合 DTO。"""` |
| [ser_lib/engine/runs.py:65](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/runs.py:65) | `"""Web 历史列表/详情共用的轻量、JSON-safe 训练记录。"""` |
| [ser_lib/engine/runs.py:163](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/runs.py:163) | `class TrainingRunDetail:` |
| [ser_lib/engine/runs.py:166](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/runs.py:166) | `该 DTO 只组合 run.json、history.json 与 checkpoint 文件 stat，` |
| [ser_lib/engine/runs.py:305](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/runs.py:305) | `"TrainingRunDetail",` |
| [ser_lib/engine/training_history.py:1](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/training_history.py:1) | `"""已完成训练的 history.json 严格读取与曲线 DTO。"""` |
| [ser_lib/engine/training_history.py:47](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/training_history.py:47) | `"""Web 训练曲线页可直接消费的完整 epoch 历史。"""` |
| [ser_lib/engine/validation.py:22](D:/projects/Speech-Emotion-Recognition/ser_lib/engine/validation.py:22) | `"""Web/CLI 可直接消费的实验 dry-run 结果。"""` |
| [ser_lib/inference/streaming.py:1](D:/projects/Speech-Emotion-Recognition/ser_lib/inference/streaming.py:1) | `"""与设备和 UI 无关的纯 PCM 流式 SER 核心。"""` |
| [ser_lib/models/registry.py:83](D:/projects/Speech-Emotion-Recognition/ser_lib/models/registry.py:83) | `"""严格校验模型配置，并返回带默认值的 JSON-safe 参数。"""` |
| [ser_lib/runtime.py:1](D:/projects/Speech-Emotion-Recognition/ser_lib/runtime.py:1) | `"""面向 CLI/Web 的轻量运行环境能力与资源快照。"""` |
| [ser_lib/runtime.py:95](D:/projects/Speech-Emotion-Recognition/ser_lib/runtime.py:95) | `"""返回 JSON-safe 的 Python/PyTorch 与本机可选设备信息。"""` |
| [ser_lib/services/__init__.py:1](D:/projects/Speech-Emotion-Recognition/ser_lib/services/__init__.py:1) | `"""面向 Web/CLI/Desktop 的稳定 Python Application Service facade。"""` |
| [ser_lib/services/artifacts.py:113](D:/projects/Speech-Emotion-Recognition/ser_lib/services/artifacts.py:113) | `allow_legacy_pickle: bool = False,` |
| [ser_lib/services/artifacts.py:118](D:/projects/Speech-Emotion-Recognition/ser_lib/services/artifacts.py:118) | `allow_legacy_pickle=allow_legacy_pickle,` |
| [ser_lib/services/catalog.py:44](D:/projects/Speech-Emotion-Recognition/ser_lib/services/catalog.py:44) | `"""返回稳定、JSON-safe 的实验 preset catalog。"""` |
| [ser_lib/services/datasets.py:1](D:/projects/Speech-Emotion-Recognition/ser_lib/services/datasets.py:1) | `"""数据集应用服务：为 Web/CLI 提供稳定的领域入口。"""` |
| [ser_lib/services/datasets.py:28](D:/projects/Speech-Emotion-Recognition/ser_lib/services/datasets.py:28) | `from ser_lib.data.query import RecordPage, query_records` |
| [ser_lib/services/datasets.py:101](D:/projects/Speech-Emotion-Recognition/ser_lib/services/datasets.py:101) | `) -> RecordPage:` |
| [ser_lib/services/evaluation.py:16](D:/projects/Speech-Emotion-Recognition/ser_lib/services/evaluation.py:16) | `EvaluationRunDetail,` |
| [ser_lib/services/evaluation.py:20](D:/projects/Speech-Emotion-Recognition/ser_lib/services/evaluation.py:20) | `EvaluationPredictionPage,` |
| [ser_lib/services/evaluation.py:42](D:/projects/Speech-Emotion-Recognition/ser_lib/services/evaluation.py:42) | `"""统一 standalone/Web evaluation 的运行、lineage、落盘与查询入口。"""` |
| [ser_lib/services/evaluation.py:132](D:/projects/Speech-Emotion-Recognition/ser_lib/services/evaluation.py:132) | `def inspect_run_detail(path: Path \| str) -> EvaluationRunDetail:` |
| [ser_lib/services/evaluation.py:165](D:/projects/Speech-Emotion-Recognition/ser_lib/services/evaluation.py:165) | `return EvaluationRunDetail(` |
| [ser_lib/services/evaluation.py:203](D:/projects/Speech-Emotion-Recognition/ser_lib/services/evaluation.py:203) | `) -> EvaluationPredictionPage:` |
| [ser_lib/services/training.py:21](D:/projects/Speech-Emotion-Recognition/ser_lib/services/training.py:21) | `TrainingRunDetail,` |
| [ser_lib/services/training.py:56](D:/projects/Speech-Emotion-Recognition/ser_lib/services/training.py:56) | `dataset_id 可以由已经加载 manifest 的 CLI/Web 显式传入；未提供时` |
| [ser_lib/services/training.py:95](D:/projects/Speech-Emotion-Recognition/ser_lib/services/training.py:95) | `"""执行 Trainer.fit，并直接返回 Web 需要的 TrainingResult。"""` |
| [ser_lib/services/training.py:128](D:/projects/Speech-Emotion-Recognition/ser_lib/services/training.py:128) | `def inspect_run_detail(path: Path \| str) -> TrainingRunDetail:` |
| [ser_lib/services/training.py:168](D:/projects/Speech-Emotion-Recognition/ser_lib/services/training.py:168) | `return TrainingRunDetail(` |

## H. 验证状态与边界

已完成：Git 跟踪清单对照、全库 AST 解析、配置和所有显式 __all__ 枚举、import/直接消费者与关键 Call 枚举、文档链接目标核验。未执行：pytest、Ruff、mypy、coverage、模型训练、pip 安装、真实 HF 下载或远端 CI 查询。源码中的测试断言是资产，不是本轮通过记录。

静态清单不能覆盖用户库外代码、动态注册及 notebook 字符串代码的完整调用图；Phase 0/迁移删除前需结合本附录与全仓搜索再次核对。不得因为没有直接 import 就自动删除算法，也不得因注释包含 Web 就保留产品包装。
