# ser_lib 面向 SER-Studio 可视化平台的完整优化设计文档

## 1. 文档目的

本文用于指导 `Speech-Emotion-Recognition` 项目中 `ser_lib` 的下一阶段重构。

本次重构的主要目标不是增加新的 SER 模型，也不是增加多机、多卡、分布式训练，而是让 `ser_lib` 成为未来 `SER-Studio` Web 平台稳定、清晰、可复用的核心业务库。

未来 SER-Studio 预计包含：

- 数据集管理
- 数据集导入
- 数据检查与统计
- 数据浏览与编辑
- 训练配置
- 实时训练状态
- 训练曲线
- Checkpoint 管理
- 模型评估
- 混淆矩阵
- 错误样本分析
- 单音频推理
- 批量推理
- 实时流式推理
- Artifact/模型管理
- 运行环境查看

因此，本次优化的核心方向是：

> 将当前“适合 Python/CLI 调用的 ser_lib”，升级成“同时适合 CLI、Python、Web Backend、未来 Desktop 调用的稳定领域核心”。

---

# 2. 本次重构的边界

## 2.1 ser_lib 应负责

`ser_lib` 应继续负责：

- SER 数据领域模型
- 数据集 manifest
- 数据导入与校验
- 数据统计与 profiling
- Representation
- Transform
- Dataset / Collator
- Model
- Optimizer / Scheduler / Loss 配置
- 模型训练
- 模型评估
- 推理
- Streaming inference
- Artifact
- Checkpoint
- Runtime capability
- 结构化事件
- 结构化错误
- 结构化结果 DTO
- 组件能力发现
- 可取消长任务
- Python Application Service

## 2.2 ser_lib 不负责

以下功能不得加入 `ser_lib`：

- FastAPI
- HTTP API
- WebSocket Server
- SSE Server
- SQLAlchemy
- 用户登录
- JWT
- Session
- Redis
- Celery
- Web 页面
- Vue / React
- 前端状态
- HTTP 文件上传
- HTTP Status Code
- 用户权限
- Web Job 持久化数据库

这些属于未来：

```text
SER-Studio/backend
```

而不是：

```text
ser_lib
```

---

# 3. 最终推荐架构

```text
                    SER-Studio

          ┌─────────────────────────┐
          │        Frontend         │
          │      Vue / React        │
          └────────────┬────────────┘
                       │
                HTTP / WebSocket
                       │
          ┌────────────▼────────────┐
          │         Backend         │
          │                         │
          │ REST API                │
          │ JobManager              │
          │ EventStore              │
          │ WebSocket               │
          │ SQLite/PostgreSQL       │
          │ FileManager             │
          └────────────┬────────────┘
                       │ Python API
                       │
          ┌────────────▼────────────┐
          │         ser_lib         │
          │                         │
          │ Catalog                 │
          │ Services                │
          │ Events                  │
          │ Diagnostics             │
          │ Dataset                 │
          │ Trainer                 │
          │ Evaluator               │
          │ Inference               │
          │ Artifact                │
          └─────────────────────────┘
```

核心原则：

```text
Web 知道 ser_lib

ser_lib 不知道 Web
```

---

# 4. 当前代码基础评估

当前项目已经具备比较好的基础。

目前 `ser_lib` 已明确拆分为：

```text
artifacts
cli
core
data
engine
inference
models
```

当前尤其值得保留的设计包括：

1. Pydantic 配置体系
2. Component Registry
3. Model Registry
4. TensorSpec / ModelSpec
5. Compatibility Validation
6. `dataset.yaml + JSONL`
7. Checkpoint 与 Artifact 分离
8. safetensors Artifact
9. `EventCallback`
10. `CancellationToken`
11. Batch inference
12. Streaming inference
13. Importer `scan()` / `convert()` 两阶段设计

因此本次不建议进行大规模推倒重写。

应该在现有结构上补齐：

```text
Events
Results
Diagnostics
Catalog
Services
Query
Observability
```

---

# 5. 优化优先级

## P0：Web 开发前建议完成

### P0-1 Event System v2

### P0-2 Trainer 完整可观察性

### P0-3 Evaluator 可观察性与标准 Result

### P0-4 Importer Progress + Cancellation

### P0-5 Diagnostic / Error 统一

### P0-6 Result DTO / JSON-safe 标准

### P0-7 Component Catalog 统一

### P0-8 Experiment Dry-run / Compatibility Report

这些完成后即可正式启动 SER-Studio Web。

## P1：建议在 Web 第一阶段同步完成

### P1-1 Dataset Summary

### P1-2 Dataset Query / Pagination

### P1-3 Dataset Fingerprint

### P1-4 Dataset Editor

### P1-5 Dataset Transaction

### P1-6 Evaluation Prediction Sink

### P1-7 Batch Inference 增量结果

### P1-8 Artifact Inspect / Verify 分离

### P1-9 Artifact Progress

### P1-10 TrainingResult / Run 信息

### P1-11 Runtime Capabilities

### P1-12 Application Service Layer

## P2：后续增强

- Dataset 历史版本
- Schema migration
- 实验 preset
- GPU 实时显存指标
- CPU/RAM utilization
- Artifact registry index
- 更详细 duration histogram
- 模型参数量/磁盘占用自动统计
- 训练速度统计
- ETA 优化
- Web-friendly documentation metadata

---

# 6. P0-1：Event System v2

当前 `core/events.py` 已经包含：

```python
ProgressEvent
MetricEvent
LogEvent
EventCallback
CancellationToken
```

这是一个正确的基础，但是当前事件还不足以作为未来 Web 的正式事件协议。

当前 `ProgressEvent` 主要只有：

```text
stage
completed
total
message
timestamp
```

`MetricEvent` 主要只有：

```text
name
value
step
split
timestamp
```

缺少：

```text
run_id
sequence
event_type
schema_version
epoch
total_epochs
batch
total_batches
global_step
phase
context
```

## 推荐设计

新增统一事件基础上下文：

```python
@dataclass(frozen=True, slots=True)
class EventContext:
    run_id: str | None = None
    epoch: int | None = None
    total_epochs: int | None = None
    batch: int | None = None
    total_batches: int | None = None
    global_step: int | None = None
    split: str | None = None
```

新增 Event 元信息：

```python
schema_version
sequence
timestamp
```

推荐事件种类：

```text
LifecycleEvent
ProgressEvent
MetricEvent
LogEvent
CheckpointEvent
PredictionEvent
DiagnosticEvent
```

## LifecycleEvent

建议支持：

```text
started
phase_started
phase_completed
completed
cancelled
failed
early_stopped
```

例如：

```json
{
  "schema_version": 2,
  "event_type": "lifecycle",
  "sequence": 12,
  "stage": "training",
  "status": "started",
  "context": {
    "run_id": "run_xxx"
  }
}
```

## sequence

必须增加事件序列号。

作用：

```text
WebSocket:
100
101
102
断线

重新连接后：
103
104
...
```

即使未来 EventStore 放在 Web Backend，而不是 ser_lib，稳定 sequence 对事件排序依旧非常有价值。

`run_id` 是领域概念；Web Backend 的 `job_id` 不应强行进入 ser_lib。

## 序列化

所有事件必须提供统一：

```python
to_dict()
```

返回值必须：

```python
json.dumps(event.to_dict())
```

可以直接成功。

不得包含：

- Tensor
- Path
- torch.dtype
- Exception
- Model
- numpy array

---

# 7. P0-2：Trainer 完整实时可观察性

当前 Trainer 已接受：

```python
event_callback
cancellation
```

训练 batch 后也会 emit `ProgressEvent`，但当前训练进度对 Web 体验仍不充分。

## Trainer 应暴露

### Run 信息

```text
run_id
status
started_at
finished_at
```

### Epoch

```text
epoch
total_epochs
```

### Batch

```text
batch
total_batches
```

### Global Step

```text
global_step
optimizer_step
```

### 样本

```text
samples_processed
samples_total
```

### 实时训练指标

```text
batch_loss
running_loss
running_accuracy
learning_rate
```

### 时间

```text
elapsed_seconds
epoch_elapsed_seconds
estimated_remaining_seconds
```

## 推荐事件流程

```text
training_started

epoch_started

phase_started(train)

train_progress
train_metric
train_progress
train_metric
...

phase_completed(train)

phase_started(validation)

validation_progress
validation_metric

phase_completed(validation)

checkpoint_started
checkpoint_saved

epoch_completed

...

training_completed
```

Early stopping：

```text
early_stopped
training_completed
```

Cancel：

```text
cancelled
```

错误：

```text
failed
```

---

# 8. Trainer 事件频率控制

不能每个 batch 无限制发送所有指标。

建议增加：

```python
class ObservabilityConfig:
    progress_interval_batches: int = 1
    metric_interval_batches: int = 10
```

默认：

```text
Progress：每 batch
Metric：每 10 batch
```

如果训练 batch 很快，可以进一步将 Progress 间隔提高到 5 个 batch。

未来 Web Backend 再决定是否进行网络层节流，ser_lib 不负责网络节流。

---

# 9. Trainer callback 不得执行网络 IO

当前 `_emit()` 同步调用 `event_callback(event)`，该设计可以继续保留。

但是未来 Web Backend 必须这样：

```text
Trainer
   │
   │ callback
   ▼
Thread-safe Queue
   │
   ▼
Backend
   │
   ├─ EventStore
   └─ WebSocket
```

禁止：

```python
def callback(event):
    websocket.send(...)
```

原因是网络阻塞会直接影响训练线程。

---

# 10. P0-3：TrainingResult

未来 Web 不应该从 Trainer 内部属性、checkpoint 文件和日志中重新拼训练结果。

新增：

```python
@dataclass(frozen=True)
class TrainingResult:
    run_id: str
    status: str

    epochs: tuple[EpochResult, ...]

    best_epoch: int | None
    best_metric: float | None
    monitored_metric: str

    started_at: datetime
    finished_at: datetime
    duration_seconds: float

    last_checkpoint: Path | None
    best_checkpoint: Path | None

    stop_reason: str | None
```

status：

```text
completed
early_stopped
cancelled
failed
```

为了向后兼容，第一阶段建议保留：

```python
trainer.fit() -> list[EpochResult]
trainer.last_result -> TrainingResult
```

以后 1.0 再考虑统一 `fit()` 的返回类型。

---

# 11. P0-4：Checkpoint 事件

建议新增：

```text
checkpoint_started
checkpoint_saved
checkpoint_failed
best_model_updated
```

例如：

```json
{
  "event_type": "checkpoint",
  "action": "saved",
  "kind": "best",
  "epoch": 8,
  "metric_name": "val_uar",
  "metric_value": 0.6832,
  "path": "checkpoints/best.pt"
}
```

前端可以直接展示最佳模型和最后 checkpoint，而不需要扫描文件系统推断状态。

---

# 12. on_epoch_end 的处理

当前 Trainer 同时存在：

```text
EventCallback
```

和：

```python
on_epoch_end
```

建议短期保留 `on_epoch_end` 保证兼容。

长期：

```text
Event 系统作为唯一正式观察接口
```

不要继续增加：

```text
on_batch_end
on_validation_end
on_checkpoint
on_train_begin
...
```

否则会形成 callback API 膨胀。

---

# 13. P0-5：Evaluator 优化

当前 Evaluator 已具备较丰富的 SER 指标，可继续保留现有评估逻辑。

主要需要优化两个方向。

## 13.1 Evaluation progress 补 total

应尽可能提供：

```python
ProgressEvent(
    stage="evaluation",
    completed=batch_index,
    total=total_batches,
)
```

如果来源没有 `len()`：

```text
total=None
```

规则：能知道 total 的长任务必须提供 total。

## 13.2 EvaluationResult JSON 标准统一

整个 ser_lib 规定所有公开 Result 类型必须至少支持：

```python
to_dict()
```

或者统一使用 Pydantic：

```python
model_dump(mode="json")
```

二选一并统一。

不要存在：

```text
A 使用 asdict
B 使用 summary_dict
C 使用 to_json_safe
D 自己 json.dumps
```

---

# 14. P1：Evaluation Prediction Sink

对于大数据集，样本级 PredictionRecord 不应被强制长期全部保留在内存中。

建议：

```python
evaluate(
    ...,
    prediction_sink=None,
)
```

定义：

```python
class PredictionSink(Protocol):
    def write(self, record: PredictionRecord) -> None:
        ...
```

ser_lib 可提供：

```text
MemoryPredictionSink
JsonlPredictionSink
```

未来 Web Backend 可以自行实现：

```text
DatabasePredictionSink
```

但是 DatabasePredictionSink 不放进 ser_lib。

---

# 15. P0-6：Importer 长任务化

当前 Importer 的两阶段设计：

```text
scan()
convert()
```

应继续保留。

但是协议需要增加：

```python
scan(
    source,
    config,
    *,
    event_callback=None,
    cancellation=None,
)
```

```python
convert(
    source,
    destination,
    config,
    *,
    event_callback=None,
    cancellation=None,
)
```

阶段建议：

```text
discover
parse
validate
map_labels
prepare
write
finalize
```

前端可显示：

```text
扫描文件 12,310 / 32,441

解析标签

检查数据

写入 manifest
```

---

# 16. Importer 接口兼容

新增参数使用 optional keyword-only：

```python
event_callback: EventCallback | None = None
cancellation: CancellationCheck | None = None
```

所有内置 Importer 更新。

尽量避免无必要地破坏第三方实现。

---

# 17. P0-7：统一 Diagnostic

建议新增：

```python
@dataclass(frozen=True)
class Diagnostic:
    severity: str
    code: str
    message: str

    stage: str | None = None
    field: str | None = None
    path: str | None = None
    uid: str | None = None

    suggestion: str | None = None

    details: dict[str, JSONValue] = ...
```

severity：

```text
info
warning
error
```

示例：

```json
{
  "severity": "error",
  "code": "audio_missing",
  "message": "音频文件不存在",
  "stage": "dataset_scan",
  "path": "...",
  "suggestion": "检查数据集根路径"
}
```

---

# 18. Diagnostic 与 Exception 的关系

规则：

### Exception

表示：

```text
操作不能继续
```

### Diagnostic

表示：

```text
发现一个问题，需要展示给调用方
```

例如数据集扫描过程中个别文件损坏、标签未知，应该累计为 Diagnostic，而不是中断整个扫描。

但 `dataset.yaml` 彻底损坏等无法继续的情况仍应抛 Exception。

---

# 19. Error Code 稳定化

建议所有领域错误拥有独立稳定 code：

```text
configuration_error

manifest_error
audio_not_found
audio_decode_error
audio_invalid_segment

representation_error
transform_error
collation_error

compatibility_error
registry_error

checkpoint_error
artifact_invalid
artifact_integrity_error

prediction_error

operation_cancelled
```

Web Backend 可以：

```text
SERError
    ↓
error.to_dict()
    ↓
HTTP response
```

无需通过字符串分析异常类型。

---

# 20. P0-8：CompatibilityReport

新增：

```python
inspect_compatibility(...)
    -> CompatibilityReport
```

结构：

```python
@dataclass
class CompatibilityReport:
    compatible: bool
    diagnostics: tuple[Diagnostic, ...]
```

原来的：

```python
validate_compatibility(...)
```

改为内部：

```python
report = inspect_compatibility(...)

if not report.compatible:
    raise CompatibilityError(...)
```

这样：

```text
CLI → raise
Web → report
```

两种调用方式都可以复用同一套检查逻辑。

---

# 21. Experiment Dry Run

未来 Web 新建训练任务时，应在真正运行前执行：

```python
validate_experiment(...)
```

返回：

```json
{
  "valid": true,
  "diagnostics": [],
  "normalized_config": {},
  "summary": {}
}
```

检查至少包括：

```text
配置 Schema
Dataset 是否存在
标签数量
Representation
ModelSpec
Input layout
Feature dimension
Sample rate
Batch mode
Loss
Optimizer
Scheduler
Checkpoint path
Device
```

但是不应该加载完整训练数据、占用大量 GPU 或启动训练。

---

# 22. P0-9：Component Catalog 统一

现有 Model/Data Component Registry 的 Descriptor 思路应继续扩展。

未来统一：

```text
Models
Representations
Waveform Transforms
Feature Transforms
Importers
Optimizers
Schedulers
Losses
Samplers
```

形成统一 Descriptor：

```python
ComponentDescriptor:
    id
    display_name
    category
    version
    status
    description

    config_schema

    capabilities
```

---

# 23. 前端配置不允许写死模型参数

错误设计：

```javascript
if model === "cnn" {
    show("hidden_channels")
    show("dropout")
}
```

正确设计：

```text
ser_lib Descriptor
       ↓
Backend API
       ↓
JSON Schema
       ↓
Dynamic Form
```

因此以后增加 WavLM、HuBERT、Emotion2Vec 时，前端无需修改模型参数页面。

---

# 24. Config metadata 完善

现有 Pydantic Config 建议逐渐补：

```text
title
description
default
minimum
maximum
examples
```

例如：

```python
learning_rate: float = Field(
    default=1e-3,
    gt=0,
    title="Learning Rate",
    description="Optimizer initial learning rate.",
    examples=[0.001],
)
```

前端即可自动生成更友好的表单。

---

# 25. P1：DatasetSummary

新增：

```python
DatasetSummary
```

建议字段：

```text
dataset_id
name

total_records
num_classes
num_speakers

splits
labels

total_duration_seconds

sample_rates
channels

fingerprint

created_at
modified_at
```

部分耗时统计可以为空，例如：

```text
profile_status = unknown
```

避免每次列表刷新都扫描音频。

---

# 26. DatasetProfile 增强

未来建议增加：

```text
p50_duration
p90_duration
p95_duration
p99_duration

duration_histogram

per_split_counts
per_split_duration

per_label_counts
per_label_duration

speaker_count

sample_rate_distribution
channel_distribution
```

Web 不应该为了画时长分布，获取几万条原始 duration。

应该由 ser_lib 返回聚合 histogram。

---

# 27. P1：Dataset Query

为未来数据浏览器增加：

```python
query_records(
    *,
    split=None,
    label_id=None,
    speaker_id=None,
    keyword=None,
    offset=0,
    limit=50,
) -> RecordPage
```

返回：

```python
RecordPage:
    items
    total
    offset
    limit
```

当前可以继续使用内存过滤。

重要的是先稳定接口，未来即使实现迁移到 SQLite、DuckDB 或 indexed manifest，Web API 都无需改变。

---

# 28. DatasetManifest 不应直接成为 Web Pagination API

未来 Backend 不应该：

```python
manifest.records[0:50]
```

因为这会把内部数据结构直接暴露给 Web。

Web 应只依赖：

```text
DatasetService.query_records()
```

---

# 29. Dataset Fingerprint

建议对：

```text
dataset.yaml
train.jsonl
val.jsonl
test.jsonl
```

生成稳定 fingerprint，例如 SHA256。

训练记录中保存：

```text
dataset_id
dataset_fingerprint
```

作用：

### 实验可复现

同名 Dataset 被修改后，可以识别版本变化。

### Cache

数据变化后自动失效。

### Artifact

知道模型到底使用哪个数据版本。

### Web

可以展示 Dataset 的具体版本。

---

# 30. P1：DatasetEditor

未来 Web 很可能支持：

```text
修改 label
修改 split
修改 speaker
删除样本
批量换标签
批量移动 split
```

这些逻辑不能放在 FastAPI route。

新增：

```text
ser_lib/data/editor.py
```

推荐：

```python
DatasetEditor
```

API：

```python
update_record()
delete_records()
move_records()
replace_label()
update_speaker()
commit()
rollback()
```

---

# 31. Dataset 写入事务

未来数据集一旦支持 Web 编辑，就必须避免半更新状态。

建议：

```text
dataset/
    ↓
staging temp dir
    ↓
写全部文件
    ↓
validate
    ↓
commit
```

不得逐文件完成后立即视为整个 Dataset 成功。

---

# 32. Dataset 操作事件

未来：

```text
import
profile
validate
edit
rebuild
```

都应统一支持：

```text
EventCallback
CancellationToken
```

原则：

> 所有可能明显超过约 500ms～1s 的领域操作，都应该评估是否支持 Progress 和 Cancel。

不要求短操作强行事件化。

---

# 33. P1：Batch Inference 增量输出

当前 BatchEmotionPredictor 已经具备较好的长任务基础。

未来还需要让 Web 可以边推理边显示结果。

建议新增：

```text
PredictionEvent
```

例如：

```json
{
  "event_type": "prediction",
  "uid": "audio_001",
  "emotion": "happy",
  "confidence": 0.92
}
```

或者每 batch 发送：

```text
PredictionBatchEvent
```

---

# 34. Batch Inference 内存优化

未来如果批量推理文件非常多，可以增加：

```python
result_sink=None
```

思想与 Evaluation PredictionSink 相同。

该优化属于 P2，可以暂缓。

---

# 35. Streaming Inference

当前 Streaming 模块设计天然适合未来 WebSocket 集成，原则上不要大改。

保持：

```text
PCM input
window
hop
smoothing
sequence
start/end
prediction
```

未来 Backend：

```text
WebSocket PCM
    ↓
StreamingEmotionRecognizer
    ↓
StreamingPrediction
    ↓
WebSocket JSON
```

ser_lib 不需要知道 WebSocket。

---

# 36. P1：Artifact Inspect 与 Verify 分离

未来模型管理页面需要快速读取：

```text
模型列表
名称
模型类型
创建时间
数据集
指标
大小
```

完整 SHA256 verify 可能需要读取数 GB 权重，因此建议：

```python
inspect_model_artifact()
```

只读取：

```text
manifest
metadata
```

不做完整 hash。

然后：

```python
verify_model_artifact()
```

用户明确执行“验证完整性”时再计算 SHA256。

---

# 37. Artifact Verify Progress

为：

```python
verify_model_artifact()
```

增加：

```text
EventCallback
CancellationToken
```

事件：

```text
artifact_verify

1.2 GB / 4.3 GB
```

Web 就可以显示真实进度。

---

# 38. Artifact Export Progress

Artifact export 通常包含：

```text
prepare
weights
metadata
hash
manifest
finalize
```

建议事件：

```text
artifact_export_started
artifact_export_weights
artifact_export_metadata
artifact_export_hash
artifact_export_completed
```

大模型保存 safetensors 时不会看起来像“页面卡死”。

---

# 39. ArtifactInfo

增加轻量：

```python
ArtifactInfo
```

字段建议：

```text
artifact_id
model_id
display_name

created_at

parameter_count
size_bytes

dataset_id
dataset_fingerprint

source_run_id

num_classes

best_metric
best_metric_name

artifact_version
library_version
```

列表页面使用 `ArtifactInfo`，详情页面再读 `ArtifactManifest`。

---

# 40. RuntimeCapabilities

增加：

```python
get_runtime_capabilities()
```

返回 JSON-safe：

```json
{
  "python_version": "...",
  "torch_version": "...",
  "cuda_available": true,
  "devices": [
    {
      "id": "cuda:0",
      "type": "cuda",
      "name": "...",
      "total_memory": 25769803776,
      "amp_supported": true
    }
  ]
}
```

本阶段不考虑多 GPU 训练。

即使机器有多张 GPU，Web 只需要让用户单选目标 device 即可。

---

# 41. Application Service Layer

建议新增：

```text
ser_lib/services/
```

目录：

```text
services/
├── __init__.py
├── catalog.py
├── datasets.py
├── training.py
├── evaluation.py
├── inference.py
├── artifacts.py
└── runtime.py
```

这里不是 HTTP Service，而是 Python Application Service。

---

# 42. CatalogService

API 示例：

```python
CatalogService.list_models()
CatalogService.list_representations()
CatalogService.list_transforms()
CatalogService.list_importers()
CatalogService.list_optimizers()
CatalogService.list_schedulers()
CatalogService.list_losses()
```

返回全部 JSON-safe Descriptor。

---

# 43. DatasetService

建议：

```python
DatasetService.inspect()
DatasetService.summary()
DatasetService.profile()
DatasetService.query()
DatasetService.validate()
DatasetService.scan_import()
DatasetService.import_dataset()
DatasetService.edit()
```

---

# 44. TrainingService

建议：

```python
TrainingService.validate_config()
TrainingService.create_components()
TrainingService.train()
```

不负责：

```text
线程池
Job ID
数据库
WebSocket
```

这些由 Backend JobManager 处理。

---

# 45. EvaluationService

建议：

```python
EvaluationService.evaluate()
EvaluationService.inspect_report()
```

---

# 46. ArtifactService

建议：

```python
ArtifactService.list()
ArtifactService.inspect()
ArtifactService.verify()
ArtifactService.export()
ArtifactService.load()
```

`list()` 可以由调用方传入模型根目录，ser_lib 不保存用户自己的模型库路径设置。

---

# 47. Result DTO 统一规范

建议给所有公开操作结果制定统一规则。

例如：

```text
DatasetSummary
DatasetAudioProfile
ImportPreview
CompatibilityReport
TrainingResult
EpochResult
EvaluationResult
PredictionResult
BatchPredictionResult
StreamingPrediction
ArtifactInfo
ArtifactVerifyResult
RuntimeCapabilities
```

全部要求：

### Rule 1

必须类型明确。

### Rule 2

必须可转换为 JSON-safe 数据。

### Rule 3

不能把 `torch.Tensor` 直接暴露给 Web DTO。

### Rule 4

不能把 Exception 放进去。

### Rule 5

Path 序列化为字符串。

### Rule 6

datetime 使用 ISO 8601。

### Rule 7

enum 使用稳定字符串。

统一：

```python
to_dict()
```

如果使用 Pydantic：

```python
model_dump(mode="json")
```

二选一并统一。

---

# 48. JSON 类型定义

建议在：

```text
ser_lib/core/types.py
```

加入：

```python
JSONScalar = str | int | float | bool | None

JSONValue = (
    JSONScalar
    | list["JSONValue"]
    | dict[str, "JSONValue"]
)
```

所有 `details`、`metadata`、`payload` 原则上使用 JSON-safe 类型。

---

# 49. 路径安全

未来 Web 化之后，用户输入路径会明显增加。

ser_lib 应负责的只是：

```text
路径是否合法
文件是否存在
格式是否正确
```

但：

```text
用户能不能访问 /etc/
```

这种权限问题属于 Web Backend sandbox/path policy。

不要把 Web 安全策略塞进 ser_lib。

---

# 50. Run ID

建议 ser_lib 支持可选：

```python
run_id
```

但不要产生 Web：

```text
job_id
```

两者区分：

```text
run_id
= SER 实验/训练运行标识

job_id
= Web 后端调度任务标识
```

Backend 可以保存 `job_id -> run_id` 的关联。

---

# 51. Training Run Metadata

建议训练时保存：

```text
run_id
created_at
dataset_id
dataset_fingerprint
model_id
config
seed
device
library_version
```

这些 metadata 可以进入 checkpoint。

未来 Artifact 保存：

```text
source_run_id
```

实现：

```text
Dataset
  ↓
Training Run
  ↓
Checkpoint
  ↓
Artifact
```

完整追踪。

---

# 52. ETA 设计

ETA 不需要复杂。

开始阶段可以使用最近 N batch 平均时间乘以剩余 batch。

训练完整 ETA 可以使用：

```text
当前 epoch 剩余
+
历史 epoch 平均
×
剩余 epoch
```

仅作为估算字段：

```text
estimated_remaining_seconds
```

前端显示“约 12 分钟”，不要承诺严格准确。

---

# 53. 训练速度

建议添加：

```text
samples_per_second
batches_per_second
```

未来 UI 可以显示训练吞吐，不需要引入高级 profiler。

---

# 54. GPU 显存

P2 可以考虑：

```text
allocated_memory
reserved_memory
max_allocated_memory
```

但建议 ser_lib 只做可选采样。

不要在每个 batch 强制采集。

可以：

```text
resource_metrics=False
```

默认关闭。

---

# 55. 日志与事件职责区分

`logging`：

```text
面向开发者/服务器日志
```

Event：

```text
面向程序调用者/UI
```

因此：

```python
logger.info("saving checkpoint")
```

不能替代：

```text
CheckpointEvent
```

也不要让 Web 解析 `train.log` 来获取状态。

---

# 56. CLI 与 Web 共存

CLI 最终应该也是 ser_lib 的一个客户端。

例如：

```text
CLI
 ↓
TrainingService
 ↓
Trainer
```

Web：

```text
REST
 ↓
TrainingService
 ↓
Trainer
```

不要出现 CLI 调一套、Web 再复制一套的情况。

---

# 57. 建议目录调整

不建议大搬迁现有目录。

新增即可：

```text
ser_lib/
├── artifacts/
├── cli/
├── core/
│   ├── events.py
│   ├── exceptions.py
│   ├── diagnostics.py      # 新
│   └── types.py            # 新
│
├── data/
│   ├── editor.py           # P1 新
│   ├── query.py            # P1 新
│   └── ...
│
├── engine/
│   ├── trainer.py
│   ├── evaluator.py
│   ├── results.py          # 建议新
│   └── ...
│
├── inference/
├── models/
│
├── catalog.py              # 或 services/catalog
│
└── services/
    ├── catalog.py
    ├── datasets.py
    ├── training.py
    ├── evaluation.py
    ├── inference.py
    ├── artifacts.py
    └── runtime.py
```

---

# 58. API 兼容策略

当前项目仍处于 1.0 之前，因此现在是完成这次 API 整理的合适阶段。

但是仍建议：

### 保留

```text
ProgressEvent
MetricEvent
LogEvent
CancellationToken

Trainer
Evaluator

原 DatasetManifest
原 Component Registry
```

### 扩展而不是重写

例如 `ProgressEvent` 新增 context 时尽量提供默认值。

### Breaking Change

确实必要时必须在 CHANGELOG 和 Migration Guide 中明确记录。

---

# 59. 版本建议

建议这次优化完成后进入：

```text
v0.3.0
```

定位：

> Machine-facing API & observability release.

主要 feature：

```text
Event v2
Diagnostics
Training observability
Long-operation progress
CompatibilityReport
Catalog
Services
Serializable Result
Dataset Query
Artifact Inspect
```

---

# 60. 测试要求

本次任何优化不得导致现有测试无理由减少。

新增测试至少覆盖：

## Events

```text
Progress serialization
Metric serialization
Lifecycle serialization
sequence
context
fraction
invalid completed/total
```

## Cancellation

```text
training cancel
evaluation cancel
import scan cancel
import convert cancel
profile cancel
artifact verify cancel
artifact export cancel
batch inference cancel
```

## Trainer

```text
total_batches
epoch context
global_step
metric frequency
checkpoint event
early stop event
completed event
```

## Evaluation

```text
total progress
JSON-safe result
prediction sink
```

## Diagnostics

```text
serialization
severity
codes
```

## Catalog

```text
all component schemas are JSON-safe
IDs unique
descriptor stable
```

## Dataset

```text
pagination
filters
fingerprint
editor transaction
rollback
```

## Artifact

```text
inspect does not hash weights
verify emits progress
cancel verify
```

---

# 61. Event 单元测试的关键约束

事件 callback 不允许破坏训练状态。

需要测试：

```python
events = []

trainer = Trainer(
    ...,
    event_callback=events.append,
)
```

训练结果必须与：

```python
event_callback=None
```

保持一致。

观察行为不得改变算法行为。

---

# 62. 性能约束

Web 化改造不能明显降低训练性能。

### Event

Event 建立必须轻量。

### Metric

不要每个 batch 做额外昂贵计算。

### JSON

Trainer 内不要不断：

```python
json.dumps()
```

只生成 Python event object。

JSON 序列化由 Backend 完成。

### GPU Sync

为了拿统计指标，不要频繁增加：

```python
torch.cuda.synchronize()
```

---

# 63. P0 实施顺序

建议严格按：

```text
阶段 1
core/events.py

阶段 2
core/diagnostics.py
core/exceptions.py

阶段 3
engine/trainer.py

阶段 4
engine/evaluator.py

阶段 5
data/importers

阶段 6
CompatibilityReport

阶段 7
Catalog

阶段 8
统一 Result Serialization
```

到此即可开始 Web。

---

# 64. P1 实施顺序

```text
阶段 9
DatasetSummary/Profile

阶段 10
Dataset Query

阶段 11
Dataset fingerprint

阶段 12
DatasetEditor + transaction

阶段 13
Artifact inspect/verify/export

阶段 14
Batch prediction events

阶段 15
RuntimeCapabilities

阶段 16
Service layer
```

---

# 65. 建议 Commit 拆分

不要一个巨大 commit。

建议：

### Commit 1

```text
feat(core): add structured diagnostics and event context
```

内容：

```text
Event v2 基础
Diagnostic
JSON types
```

### Commit 2

```text
feat(engine): expose detailed training lifecycle and progress
```

内容：

```text
epoch
batch
total
global step
running metrics
lifecycle
checkpoint events
```

### Commit 3

```text
feat(engine): improve evaluation observability and result serialization
```

### Commit 4

```text
feat(data): add progress and cancellation to dataset importers
```

### Commit 5

```text
feat(data): add compatibility reports and structured validation
```

### Commit 6

```text
feat(catalog): unify discoverable component metadata
```

### Commit 7

```text
feat(data): add dataset summary query and fingerprint APIs
```

### Commit 8

```text
feat(data): add transactional dataset editing
```

### Commit 9

```text
feat(artifacts): add lightweight inspection and observable verification
```

### Commit 10

```text
feat(inference): expose incremental batch prediction events
```

### Commit 11

```text
feat(services): add application service facade
```

### Commit 12

```text
docs: document machine-facing APIs for SER-Studio integration
```

---

# 66. Web 开发启动条件

不是所有内容都完成后才能做 Web。

满足下面条件即可启动：

```text
Event v2                ✓
Trainer progress        ✓
Evaluator progress      ✓
Importer progress       ✓
Cancellation            ✓
Diagnostic              ✓
Error code              ✓
Result serialization    ✓
Component Catalog       ✓
CompatibilityReport     ✓
```

这就是 P0。

---

# 67. SER-Studio 页面与 ser_lib 接口对应

## Dashboard

```text
RuntimeCapabilities
DatasetSummary[]
ArtifactInfo[]
```

## Dataset 页面

```text
DatasetService
DatasetSummary
DatasetProfile
DatasetQuery
DatasetEditor
```

## Dataset Import

```text
Importer
ProgressEvent
Diagnostic[]
CancellationToken
```

## New Training

```text
Catalog
JSON Schema
CompatibilityReport
ExperimentConfig
```

## Training

```text
LifecycleEvent
ProgressEvent
MetricEvent
CheckpointEvent
TrainingResult
```

## Evaluation

```text
EvaluationResult
PredictionRecord
PredictionSink
```

## Inference

```text
PredictionResult
BatchPredictionResult
PredictionEvent
StreamingPrediction
```

## Models

```text
ArtifactInfo
ArtifactManifest
Artifact Verify
Artifact Export
```

---

# 68. 最终 API 形态

理想情况下未来 Backend 中训练逻辑应该非常薄：

```python
def train_job(config):
    token = CancellationToken()

    def emit(event):
        queue.put(event)

    result = training_service.train(
        config,
        event_callback=emit,
        cancellation=token,
    )

    return result
```

Backend 不应该知道：

```text
optimizer 怎么创建
representation 怎么连接
checkpoint 怎么保存
UAR 怎么计算
artifact 怎么加载
```

这些都属于 ser_lib。

---

# 69. Backend 的职责

未来 Backend 只负责：

```text
用户请求
↓
创建 job_id
↓
线程/进程执行
↓
调用 ser_lib
↓
事件入 EventStore
↓
WebSocket 发送
↓
结果持久化
```

例如：

```text
job_id = web_train_001
run_id = ser_run_001
```

Backend 保存映射：

```text
web_train_001 → ser_run_001
```

---

# 70. 不推荐的设计

## 不要解析 console log 获取进度

错误：

```text
stdout
 ↓
regex
 ↓
loss
```

## 不要在 Trainer 中 import FastAPI

错误：

```python
from fastapi import WebSocket
```

## 不要让 DatasetManifest 直接承担 REST API

## 不要把 Web JobManager 放进 ser_lib

## 不要为 Web 重新写一套 Trainer

## 不要把所有 Result 都做成 dict

强类型领域对象依旧应该保留。

## 不要一次重写整个仓库

当前基础设计已经足够好。

---

# 71. 完成 P0 后的预期训练事件示例

```json
{
  "schema_version": 2,
  "event_type": "progress",
  "sequence": 812,
  "stage": "train",
  "timestamp": "2026-09-08T08:00:00Z",
  "context": {
    "run_id": "run_001",
    "epoch": 3,
    "total_epochs": 30,
    "batch": 128,
    "total_batches": 500,
    "global_step": 1128,
    "split": "train"
  },
  "completed": 128,
  "total": 500,
  "message": ""
}
```

对应：

```json
{
  "schema_version": 2,
  "event_type": "metric",
  "sequence": 813,
  "name": "running_loss",
  "value": 0.7281,
  "context": {
    "run_id": "run_001",
    "epoch": 3,
    "batch": 128,
    "global_step": 1128,
    "split": "train"
  }
}
```

再：

```json
{
  "schema_version": 2,
  "event_type": "metric",
  "sequence": 814,
  "name": "learning_rate",
  "value": 0.00082
}
```

---

# 72. 前端最终效果

ser_lib 做完这些以后，Web 页面可以自然显示：

```text
Training
────────────────────────

Epoch
3 / 30

Current Phase
Training

Epoch Progress
128 / 500
████████░░░░░░░ 25.6%

Loss
0.7281

Running Accuracy
68.42%

Learning Rate
8.2e-4

Samples
2,048 / 8,000

Speed
128.3 samples/s

Estimated Remaining
12m 31s

Best UAR
0.6732

Best Epoch
2
```

验证开始：

```text
Current Phase
Validation

36 / 80
█████████░░░░░
```

保存时：

```text
Saving best checkpoint...
```

不会出现页面无反馈。

---

# 73. 最终目标状态

本次优化完成后，`ser_lib` 应具备四个稳定层：

```text
                  ser_lib

        ┌────────────────────┐
        │      Services      │
        └─────────┬──────────┘
                  │
        ┌─────────▼──────────┐
        │ Machine-facing API │
        │                    │
        │ Events             │
        │ Results            │
        │ Diagnostics        │
        │ Catalog            │
        └─────────┬──────────┘
                  │
        ┌─────────▼──────────┐
        │   Domain Engine    │
        │                    │
        │ Data               │
        │ Trainer            │
        │ Evaluator          │
        │ Inference          │
        │ Artifact           │
        └─────────┬──────────┘
                  │
        ┌─────────▼──────────┐
        │ PyTorch/TorchAudio │
        └────────────────────┘
```

---

# 74. 最终优先级结论

必须先完成：

```text
P0
├── Event System v2
├── Trainer Observability
├── Evaluator Observability
├── Importer Progress/Cancel
├── Diagnostic
├── Stable Error Codes
├── JSON-safe Results
├── Component Catalog
└── CompatibilityReport
```

然后即可开始：

```text
SER-Studio
```

之后并行完成：

```text
P1
├── Dataset Query
├── Dataset Editor
├── Dataset Fingerprint
├── Evaluation Sink
├── Artifact Inspect
├── Artifact Progress
├── Batch Prediction Events
├── RuntimeCapabilities
└── Services
```

---

# 75. 总结

当前 `ser_lib` 并不需要推翻。

真正需要做的是在现有：

```text
Data
Model
Trainer
Evaluator
Inference
Artifact
```

之上建立稳定的：

```text
Events
Diagnostics
Results
Catalog
Services
```

五个机器接口层。

这五层完成以后，SER-Studio 后端将不需要理解算法内部实现，只需要：

```text
调用 ser_lib
+
监听事件
+
保存结果
+
通过 HTTP/WebSocket 暴露
```

这将使：

```text
CLI
Web
Desktop
Python API
```

全部使用同一套领域逻辑，同时保证 `ser_lib` 自身仍然是一个干净、独立、无需 Web 依赖的 Python SER 基础库。
