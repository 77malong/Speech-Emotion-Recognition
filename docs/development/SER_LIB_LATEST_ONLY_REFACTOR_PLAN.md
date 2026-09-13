# SER-lib latest-only 基础库重构修改计划

> **1.0 归档说明（2026-09-13）**：本文是 SER-lib 1.0 形成过程中的历史记录，状态、路径、缺陷与“下一步”只对文中注明的历史基线负责。当前 1.0 规范请从 [文档索引](../README.md) 或仓库 `docs/README.md` 进入；当前发布状态见 `CHANGELOG.md`。原始正文保留用于审计追溯。


> 目标分支：`refactor/ser-lib-core-boundary-12-stage`
>
> 规划基线：`86f021218ca00b0f86607a59a338b30aab2869f0`
>
> 定位：**纯 SER 基础 SDK、latest-only、不承担 Web 数据管理、不保留旧版本兼容层**

## 1. 总体目标

本轮重构不是继续追加兼容层，而是把当前仓库彻底收敛成一个只维护最新结构的 SER SDK。

核心原则：

1. 只支持当前 Python API。
2. 只支持当前配置、dataset、artifact、checkpoint、run/evaluation record。
3. 删除所有 schema migration / legacy format / compatibility shim。
4. 删除明显服务 Web/管理后台的数据编辑、历史版本、查询能力。
5. 保留训练、评估、推理、artifact、安全性、lineage、fingerprint 等基础 SDK 能力。
6. 合并 Trainer 双层继承，取消 `_TrainerCore -> Trainer`。
7. errors/events 统一归入 foundation。
8. 删除 DTO / Info / catalog-friendly / Web page 等界面化命名。
9. `library_version` 保留为 provenance，但不参与兼容分支。
10. 每个阶段单独提交并经过 pytest / Ruff / mypy / build / wheel smoke。

---

# 2. 目标目录结构

```text
ser_lib/
├── __init__.py
├── _version.py
├── runtime.py
│
├── foundation/
│   ├── __init__.py
│   ├── diagnostics.py
│   ├── logging.py
│   ├── errors/
│   │   ├── __init__.py
│   │   ├── base.py
│   │   ├── config.py
│   │   ├── data.py
│   │   ├── engine.py
│   │   ├── inference.py
│   │   └── artifacts.py
│   └── events/
│       ├── __init__.py
│       ├── base.py
│       ├── lifecycle.py
│       ├── training.py
│       └── inference.py
│
├── config/
│   ├── __init__.py
│   ├── base.py
│   ├── loader.py
│   ├── data.py
│   ├── model.py
│   ├── training.py
│   ├── optimizer.py
│   ├── scheduler.py
│   ├── representations.py
│   ├── transforms.py
│   ├── inference.py
│   ├── importers.py
│   ├── presets.py
│   └── experiment.py
│
├── data/
│   ├── __init__.py
│   ├── audio.py
│   ├── types.py
│   ├── manifest.py
│   ├── dataset.py
│   ├── fingerprint.py
│   ├── cache.py
│   ├── collate.py
│   ├── pipeline.py
│   ├── registry.py
│   ├── profiling.py
│   ├── importers/
│   ├── representations/
│   └── transforms/
│
├── models/
│   └── ...
│
├── engine/
│   ├── __init__.py
│   ├── evaluator.py
│   ├── checkpoint.py
│   ├── checkpoint_catalog.py
│   ├── compatibility.py
│   ├── objectives.py
│   ├── optim.py
│   ├── eta.py
│   ├── experiment.py
│   ├── validation.py
│   ├── lineage.py
│   ├── training_records.py
│   ├── evaluation_records.py
│   ├── training_history.py
│   └── training/
│       ├── __init__.py
│       ├── trainer.py
│       ├── accumulation.py
│       └── results.py
│
├── inference/
│   ├── __init__.py
│   ├── offline.py
│   ├── batch.py
│   └── streaming.py
│
├── artifacts/
│   ├── __init__.py
│   ├── _compatibility.py
│   ├── manifest.py
│   ├── exporter.py
│   ├── loader.py
│   └── catalog.py
│
└── cli/
    └── ...

benchmarks/
├── common.py
└── benchmark_data_pipeline.py
```

---

# 3. latest-only 的统一规则

## 3.1 删除用户持久化 schema/version 字段

以下对象都不再保留 `schema_version` / `format_version`：

- `ExperimentConfig`
- `DataConfig`
- `dataset.yaml`
- artifact manifest
- `run.json`
- `evaluation.json`
- event JSON
- checkpoint payload

加载规则统一为：

> 当前结构严格解析；缺字段、类型错误、未知字段直接失败。

不再执行：

- `setdefault("schema_version", ...)`
- v1/v2 branch
- migrate
- legacy field alias
- legacy pickle load

## 3.2 `library_version` 保留

`library_version` 用于 provenance，例如：

```json
{"library_version": "0.3.0"}
```

它说明产物由哪个 ser_lib 版本创建，但不触发兼容逻辑。

## 3.3 cache 例外

`ser_lib/data/cache.py` 的缓存格式 identity 建议保留，但改成内部常量，例如：

```python
_CACHE_FORMAT_ID = "ser-cache-current"
```

其目的只是 cache invalidation，不属于 public schema migration。

---

# 4. runtime / benchmark

## 4.1 `ser_lib/benchmark.py`

### 当前
提供：

- `BenchmarkResult`
- `BenchmarkComparison`
- `run_benchmark`
- `compare_benchmarks`
- benchmark JSON 读写

### 修改
删除：

```text
ser_lib/benchmark.py
```

新增：

```text
benchmarks/common.py
```

迁移全部 benchmark helper。

### 原因
benchmark 是开发/性能回归工具，不应该成为 ser_lib runtime public API。

### 同步修改
- `benchmarks/benchmark_data_pipeline.py`
- benchmark tests
- API_REFERENCE / README 中 public benchmark 描述

---

## 4.2 `ser_lib/runtime.py`

### 保留
- `RuntimeDevice`
- `RuntimeCapabilities`
- `get_runtime_capabilities`

用于：
- CPU/CUDA/MPS 探测
- GPU 名称
- total memory
- AMP capability

### 删除
- `RuntimeMetrics`
- `get_runtime_metrics`
- `_HostRuntimeMetrics`
- `_PROCESS_SAMPLER`
- `_host_metrics`
- `_runtime_metrics_with_host`

### 同步删除测试
```text
tests/test_runtime_metrics.py
tests/test_runtime_host_metrics.py
```

### 保留测试
```text
tests/test_runtime_capabilities.py
```

### pyproject
如果全仓无其他使用，删除 `psutil` 依赖。

---

# 5. artifacts 只保留最新格式

## 5.1 `ser_lib/artifacts/manifest.py`

### 删除
- `schema_version`
- `_legacy_defaults`
- `weights_format`
- v1/v2 分支
- PyTorch artifact 格式支持

### 固定
```python
weights_file = "weights.safetensors"
```

### 保留
- `library_version`
- `weights_sha256`
- `files_sha256`
- `preprocessing`
- `processor`
- `labels`
- `metrics`
- `model_card`
- `metadata`

---

## 5.2 `ser_lib/artifacts/migrations.py`

整个文件删除。

删除：
```python
validate_artifact_manifest_version
```

---

## 5.3 `ser_lib/artifacts/loader.py`

删除：
- `raw.setdefault("schema_version", 1)`
- schema v1/v2 判断
- `allow_legacy_pickle`
- `torch.load()` artifact 权重
- `model_state.pt`
- legacy PyTorch artifact
- version-specific metadata branch

仅支持：
- `weights.safetensors`
- strict manifest
- sidecar JSON
- SHA256
- processor
- compatibility validation

---

## 5.4 `ser_lib/artifacts/exporter.py`

删除：
```python
schema_version=2
weights_format="safetensors"
```

保留：
```python
library_version=__version__
```

继续保留：
- staging
- SHA256
- safetensors
- compatibility preflight
- cancellation/events

---

## 5.5 `ser_lib/artifacts/catalog.py`

删除 entry 中的：
```python
schema_version
```

保留：
- artifact path
- model name
- library version
- metadata

暂时保留 catalog，本轮不直接删除。

---

# 6. config latest-only

## 6.1 `ser_lib/config/data.py`

删除：
```python
schema_version
AudioSettings
CacheSettings
```

`load_data_config()` 改为：
1. `load_yaml_mapping`
2. `DataConfig.model_validate`
3. 相对路径解析

不再调用：
```python
load_versioned_config
```

---

## 6.2 `ser_lib/config/experiment.py`

删除：
```python
schema_version
```

从 `engine/config.py` 迁入：
```python
load_experiment_config()
```

职责：
- 定义 `ExperimentConfig`
- 读取 YAML
- strict validate
- 解析 output/checkpoint/data/cache 相对路径

---

## 6.3 `ser_lib/config/loader.py`

保留：
```python
load_yaml_mapping
resolve_config_path
```

删除：
```python
load_versioned_config
require_schema_version
```

---

## 6.4 migration framework

删除：

```text
ser_lib/config/migrations.py
ser_lib/data/migrations.py
ser_lib/engine/migrations.py
ser_lib/artifacts/migrations.py
```

同步删除：
```python
SchemaMigrationError
SchemaMigration
MigrationRegistry
register_schema_migration
list_schema_migrations
migrate_schema_payload
```

删除：
```text
tests/test_schema_migrations.py
```

---

# 7. data 目录

## 7.1 `ser_lib/data/config.py`

直接删除。

全仓：
```python
from ser_lib.data.config import ...
```

改为：
```python
from ser_lib.config import ...
```

重点影响：
- `data/__init__.py`
- `data/collate.py`
- `data/pipeline.py`
- artifact exporter/loader
- smoke script
- 大量 tests

---

## 7.2 `ser_lib/data/editor.py`

直接删除。

删除 public API：
```python
DatasetEditor
```

删除异常：
```python
DatasetEditError
DatasetEditConflictError
DatasetTransactionError
```

删除测试：
```text
tests/test_dataset_editor.py
tests/test_dataset_editor_atomic_updates.py
```

删除当前文档中的 editor/commit/rollback 能力说明。

---

## 7.3 `ser_lib/data/history.py`

直接删除。

删除：
```python
DATASET_REVISION_SCHEMA_VERSION
DatasetRevisionInfo
DatasetRevisionScanFailure
DatasetRevisionCatalog
create_dataset_revision
inspect_dataset_revision
scan_dataset_revisions
restore_dataset_revision
```

删除：
```text
tests/test_dataset_history.py
```

删除 `.ser_history` 相关当前文档。

---

## 7.4 `ser_lib/data/query.py`

直接删除。

删除：
```python
iter_records
```

删除：
```text
tests/test_dataset_query.py
```

---

## 7.5 `ser_lib/data/fingerprint.py`

保留。

用途：
- resume data identity
- training metadata
- artifact provenance
- evaluation lineage

可选重命名：
```python
DatasetFingerprint -> ManifestFingerprint
```

建议不要和大重构同时进行，降低风险。

---

## 7.6 `ser_lib/data/manifest.py`

删除：
```python
MANIFEST_SCHEMA_VERSION
schema_version
migration
```

`ManifestMeta` 删除：
```python
schema_version
```

新 dataset.yaml：

```yaml
dataset_id: demo
root: ./audio
splits:
  train: train.jsonl
```

---

## 7.7 `ser_lib/data/importers/_conversion.py`

删除输出：
```python
"schema_version": 1
```

所有 importer 输出当前唯一格式。

---

# 8. foundation/errors

删除：
```text
ser_lib/foundation/errors.py
ser_lib/data/errors.py
```

新建：

```text
ser_lib/foundation/errors/
├── __init__.py
├── base.py
├── config.py
├── data.py
├── engine.py
├── inference.py
└── artifacts.py
```

## `base.py`
```python
SERError
OperationCancelled
```

## `config.py`
```python
ConfigurationError
```

删除：
```python
SchemaMigrationError
```

## `data.py`
迁入：
```python
SERDataError
ManifestError
AudioNotFoundError
AudioDecodeError
InvalidAudioSegmentError
RepresentationError
TransformError
CollationError
wrap_error
```

删除 editor/history 专属异常。

## `engine.py`
只放真实需要的 engine exception，不为目录对称硬造类型。

## `inference.py`
同上。

## `artifacts.py`
可选增加：
```python
ArtifactError
ArtifactIntegrityError
ArtifactCompatibilityError
```

如本轮不想扩大行为变化，可暂缓。

---

# 9. foundation/events

删除：
```text
ser_lib/foundation/events.py
ser_lib/engine/events.py
ser_lib/inference/events.py
```

新建：

```text
ser_lib/foundation/events/
├── __init__.py
├── base.py
├── lifecycle.py
├── training.py
└── inference.py
```

## `base.py`
迁入：
- `EventContext`
- `EventLike`
- `EventCallback`
- `CancellationCheck`
- `CancellationToken`
- JSON-safe helper
- sequence helper
- time helper

## `lifecycle.py`
迁入：
- `ProgressEvent`
- `MetricEvent`
- `LogEvent`
- `LifecycleEvent`

## `training.py`
迁入：
- `CheckpointEvent`

## `inference.py`
迁入：
- `PredictionEvent`

## 删除版本字段
删除：
```python
EVENT_SCHEMA_VERSION
schema_version
```

事件仍保留：
```python
event_type
```

---

# 10. Trainer 合并

当前问题：

```python
# _trainer_core.py
class Trainer:
    ...

# trainer.py
class Trainer(_TrainerCore):
    ...
```

只有一个子类，却形成两套行为链。

## 删除
```text
ser_lib/engine/_trainer_core.py
ser_lib/engine/trainer.py
```

## 新建
```text
ser_lib/engine/training/
├── __init__.py
├── trainer.py
├── accumulation.py
└── results.py
```

## `results.py`
迁入：
```python
TrainingStatus
EpochResult
TrainingResult
```

## `accumulation.py`
迁入：
```python
_AccumulationState
_AccumulationAwareLoss
```

## `trainer.py`
合并所有 Trainer 行为：

从 `_trainer_core.py`：
- init
- fit
- epoch lifecycle
- validation orchestration
- device
- AMP
- event
- checkpoint
- early stopping
- ETA
- cancellation

从当前 `trainer.py`：
- accumulation
- attempted/applied/skipped optimizer step
- resume compatibility
- sampling generator
- run metadata
- lineage
- checkpoint resume validation

最终只允许：
```python
class Trainer:
```

禁止：
```python
class Trainer(_TrainerCore)
```

---

# 11. `engine/config.py`

直接删除文件，但先迁移真实逻辑。

## 迁移到 `config/experiment.py`
```python
load_experiment_config
```

## 迁移到 `engine/experiment.py`
```python
ExperimentComponents
build_experiment_components
```

如果 `engine/experiment.py` 已存在同类逻辑，合并为唯一实现。

所有：
```python
from ser_lib.engine.config import ...
```

改为：
```python
from ser_lib.config import ...
```
或：
```python
from ser_lib.engine.experiment import ...
```

---

# 12. run/evaluation/history 命名

## 12.1 `evaluation_runs.py`

重命名：
```text
evaluation_records.py
```

重命名：
```python
EvaluationRunMetadata -> EvaluationMetadata
EvaluationRunInfo -> EvaluationRecord
```

函数：
```python
build_evaluation_run_metadata -> build_evaluation_metadata
write_evaluation_run_info -> write_evaluation_record
load_evaluation_run_info -> load_evaluation_record
```

删除：
```python
EVALUATION_RUN_SCHEMA_VERSION
schema_version
migration
```

---

## 12.2 `runs.py`

重命名：
```text
training_records.py
```

重命名：
```python
TrainingRunInfo -> TrainingRecord
```

建议同时：
```python
TrainingRunMetadata -> TrainingMetadata
```

函数：
```python
write_training_run_info -> write_training_record
load_training_run_info -> load_training_record
```

删除：
```python
RUN_RECORD_SCHEMA_VERSION
schema_version
migration
```

---

## 12.3 `training_history.py`

重命名：
```python
TrainingHistoryInfo -> TrainingHistory
```

删除注释中的：
```text
Web
DTO
可直接消费
```

保留：
```python
load_training_history
history.json
```

---

# 13. Catalog 再审计

不要机械全删。

## 倾向保留
```text
engine/checkpoint_catalog.py
artifacts/catalog.py
```

理由：
- checkpoint discovery 对 resume 有用
- artifact discovery 对本地模型管理仍有 SDK/CLI 用途

## 优先审计是否删除
```text
engine/evaluation_catalog.py
TrainingRunCatalog / scan_training_runs
```

若只用于历史列表/管理页，则删除。

对应测试同步删除：
- training run catalog tests
- evaluation catalog tests

---

# 14. checkpoint latest-only

`ser_lib/engine/checkpoint.py`

删除：
```python
CHECKPOINT_FORMAT_VERSION
format_version
legacy v1 branch
```

加载只接受当前 payload。

保留：
- model state
- optimizer
- scheduler
- scaler
- Python RNG
- NumPy RNG
- Torch RNG
- CUDA RNG
- sampler RNG
- metadata
- best checkpoint ref

删除旧 checkpoint fixture/test。

---

# 15. configs YAML

以下所有文件删除：
```yaml
schema_version: 1
```

以及：
```yaml
data:
  schema_version: 1
```

至少：

```text
configs/cnn_logmel.yaml
configs/gru_mfcc.yaml
configs/transformer_logmel.yaml
configs/casia_cnn_logmel.yaml
configs/crema_d_cnn_logmel.yaml
configs/csemotions_cnn_logmel.yaml
configs/emotiontalk_cnn_logmel.yaml
configs/esd_cnn_logmel.yaml
```

---

# 16. release compatibility 全删除

删除：

```text
tests/fixtures/release_compat/
tests/test_release_compatibility.py
tests/fixtures/pre_refactor_contract_snapshot.json
tests/test_pre_refactor_contracts.py
```

删除所有：
- artifact v1
- checkpoint v1
- 0.1.0
- 0.2.x compatibility
- old import compatibility

注意：

`test_compatibility_report.py` 属于当前模型/数据 compatibility，不是历史 release compatibility，保留。

---

# 17. migration tests 删除

删除：
```text
tests/test_schema_migrations.py
```

删除：
- future schema version
- migration chain
- missing migration path

保留：
- extra field forbid
- type validation
- required field validation

---

# 18. public API

## `ser_lib/data/__init__.py`

删除：
```python
DatasetEditor
DatasetRevision*
create_dataset_revision
restore_dataset_revision
scan_dataset_revisions
iter_records
AudioSettings
CacheSettings
```

配置统一从：
```python
ser_lib.config
```
导入。

异常统一从：
```python
ser_lib.foundation.errors
```
导入。

---

## `ser_lib/engine/__init__.py`

替换：

```python
TrainingRunInfo -> TrainingRecord
EvaluationRunInfo -> EvaluationRecord
TrainingHistoryInfo -> TrainingHistory
```

删除：
```python
RUN_RECORD_SCHEMA_VERSION
EVALUATION_RUN_SCHEMA_VERSION
```

catalog exports 根据审计结果决定。

---

## `ser_lib/config/__init__.py`

删除：
```python
AudioSettings
CacheSettings
load_versioned_config
require_schema_version
migration API
```

---

## `ser_lib/__init__.py`

根 12 API 保持：

```text
SERDataset
SERBatch
SERModel
Trainer
TrainingResult
evaluate
train_experiment
evaluate_artifact
EmotionPredictor
PredictionResult
export_model_artifact
load_model_artifact
```

本轮禁止扩大 root API。

---

# 19. tests 确定删除

```text
tests/test_dataset_editor.py
tests/test_dataset_editor_atomic_updates.py
tests/test_dataset_history.py
tests/test_dataset_query.py
tests/test_release_compatibility.py
tests/test_pre_refactor_contracts.py
tests/test_schema_migrations.py
tests/test_runtime_metrics.py
tests/test_runtime_host_metrics.py
```

fixture：

```text
tests/fixtures/release_compat/
tests/fixtures/pre_refactor_contract_snapshot.json
```

---

# 20. tests 必须保留

不能因为结构重构而删掉这些核心数值/安全测试：

```text
test_gradient_accumulation_numerics.py
test_loss_reduction_invariance.py
test_checkpoint_numpy_rng.py
test_checkpoint_resume.py
test_cnn_padding_invariance.py
test_hf_classifier_reset.py
test_spectrogram_representation.py
test_streaming_resampler_numerics.py
test_callback_failure_contract.py
test_artifact_export_preflight.py
test_artifacts.py
test_manifest_split_path_roundtrip.py
test_csv_label_mapping.py
test_csv_root_resolution.py
test_importer_atomic_conversion.py
test_batch_inference.py
```

这些是 review 修复的真实回归保护。

---

# 21. 全仓 import 迁移

## 配置
```python
from ser_lib.data.config ...
from ser_lib.engine.config ...
```

全部清零。

## 错误
```python
from ser_lib.data.errors ...
```

全部清零。

## 事件
```python
from ser_lib.engine.events ...
from ser_lib.inference.events ...
```

全部清零。

## Trainer
```python
from ser_lib.engine._trainer_core ...
```

全部清零。

---

# 22. 文档

必须更新：

```text
readme.md
docs/API_REFERENCE.md
docs/ARTIFACTS_AND_SECURITY.md
docs/DATA_FORMAT.md
docs/TRAINING_AND_CLI.md
docs/INSTALLATION.md
configs/README.md
```

删除当前文档中的：
- legacy artifact
- schema migration
- DatasetEditor
- dataset revision
- dataset query helper
- DTO
- Web page
- compatibility shim
- old import path

历史 review 文档不要改写历史事实。

建议在：
```text
docs/development/review/README.md
```

注明：

> 这些文档对应历史架构基线，不代表当前 API。

---

# 23. pyproject.toml

检查并修改：

- 如无其他 psutil 使用，删除 `psutil`
- 不删除 package version
- latest-only 不等于 package 无版本号

---

# 24. CI

保留：

- Python 3.10 / 3.11 / 3.12
- Linux / Windows / macOS
- Transformers 4.38.2
- Transformers 5.17.0
- Ruff
- mypy
- coverage
- build
- wheel smoke
- CPU training smoke

删除仅服务：
- legacy release fixture
- migration tests

的显式逻辑。

---

# 25. 推荐提交阶段

## Stage 1
```text
docs: define latest-only core architecture
```

只新增 architecture decision。

## Stage 2
```text
test: remove legacy release compatibility fixtures
```

删除 release/pre-refactor fixture。

## Stage 3
```text
refactor: remove schema migration framework
```

删除所有 migrations + migration tests。

## Stage 4
```text
refactor: enforce current persistent formats only
```

删除 config/dataset/artifact/checkpoint/run/evaluation/event version 字段。

## Stage 5
```text
refactor(data): remove compatibility and management APIs
```

删除：
- data/config.py
- editor.py
- history.py
- query.py

## Stage 6
```text
refactor(errors): centralize domain errors under foundation
```

只做 errors 路径和组织调整，不改变行为。

## Stage 7
```text
refactor(events): centralize library events
```

只做 event 组织调整。

## Stage 8
```text
refactor(engine): retire engine config compatibility module
```

迁移真实逻辑后删除 engine/config.py。

## Stage 9
```text
refactor(training): collapse trainer into one implementation
```

建立 engine/training/，删除 `_trainer_core.py`。

## Stage 10
```text
refactor(engine): rename persisted run models
```

统一：
- TrainingRecord
- EvaluationRecord
- TrainingHistory
- TrainingMetadata
- EvaluationMetadata

## Stage 11
```text
refactor(runtime): keep capabilities and move benchmarks out of library
```

删 runtime metrics，benchmark 移到 benchmarks/common.py。

## Stage 12
```text
docs: align documentation with latest-only architecture
```

文档、示例、API reference、最终 audit。

---

# 26. 每阶段验收

每个 stage 至少：

```bash
python -m pytest -q
ruff check .
mypy ser_lib
python -m build
```

最终：

```bash
pip install dist/*.whl
python scripts/smoke_train_epoch.py --device cpu
```

并要求 GitHub Actions exact-head 全绿。

---

# 27. 最终搜索必须清零

生产代码中以下搜索应为 0：

```text
ser_lib.data.config
ser_lib.engine.config
ser_lib.data.errors
ser_lib.engine.events
ser_lib.inference.events
DatasetEditor
DatasetEditError
DatasetRevision
create_dataset_revision
restore_dataset_revision
iter_records
AudioSettings
CacheSettings
_TrainerCore
allow_legacy_pickle
SchemaMigration
migrate_schema_payload
EvaluationRunInfo
TrainingRunInfo
TrainingHistoryInfo
DTO
面向 Web
Web 训练曲线
0.2.x 兼容
```

`schema_version` / `format_version` 在生产用户持久化格式中应为 0。

历史 review 文档中的文本命中可以保留。

---

# 28. 完成定义

- [ ] `data/config.py` 已删除
- [ ] `engine/config.py` 已删除
- [ ] `data/editor.py` 已删除
- [ ] `data/history.py` 已删除
- [ ] `data/query.py` 已删除
- [ ] `_trainer_core.py` 已删除
- [ ] Trainer 只有一个正式实现
- [ ] artifact 只支持 safetensors 当前格式
- [ ] legacy pickle 完全删除
- [ ] migration framework 完全删除
- [ ] public config 无 schema_version
- [ ] dataset.yaml 无 schema_version
- [ ] artifact manifest 无 schema_version
- [ ] run/evaluation/event/checkpoint 无 schema/format version
- [ ] `library_version` 仍保留 provenance
- [ ] errors 统一到 `foundation/errors/`
- [ ] events 统一到 `foundation/events/`
- [ ] `TrainingRecord` / `EvaluationRecord` / `TrainingHistory` 命名统一
- [ ] release compatibility fixture 全删除
- [ ] configs 示例全部更新
- [ ] tests import 全部更新
- [ ] Ruff 通过
- [ ] mypy 通过
- [ ] pytest 通过
- [ ] build 通过
- [ ] wheel smoke 通过
- [ ] exact-head CI 全绿
