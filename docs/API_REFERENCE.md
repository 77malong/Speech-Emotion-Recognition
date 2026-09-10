# 公共 API 索引

稳定入口优先从对应领域子包导入。Python Worker、CLI、Notebook 与未来 Web/Desktop
宿主应组合 `ser_lib.config`、`ser_lib.data`、`ser_lib.models`、`ser_lib.engine`、
`ser_lib.inference` 和 `ser_lib.artifacts` 的公开 API；库内不提供 Application Service、
Page/View/Detail 或跨领域 ComponentCatalog facade。未列入各模块 `__all__` 的名称视为实现细节。

| 子包 | 主要公开能力 |
|---|---|
| `ser_lib.foundation` | 事件、取消、Diagnostic、公共异常与显式日志辅助 |
| `ser_lib.config` | 严格配置 schema、配置加载、preset payload 与实验配置构造 |
| `ser_lib.data` | Manifest、AudioLoader、SERDataset、Pipeline、Collator、record iterator/profile/revision、数据组件 registry |
| `ser_lib.models` | SERModel、ModelOutput、ModelSpec、CNN、GRU、Transformer、HF adapter 与模型 registry |
| `ser_lib.engine` | ExperimentConfig、Trainer、训练/评估实验、run metadata、report、prediction iterator、checkpoint |
| `ser_lib.artifacts` | artifact 导出、轻量 inspect/catalog、验证、加载和模型卡 |
| `ser_lib.inference` | 单文件、批量和纯 PCM 流式推理 |
| `ser_lib.runtime` | 按需运行环境能力与资源快照 |
| `ser_lib.benchmark` | 可序列化微基准和同环境回归比较 |
| `ser_lib.cli` | `ser` 命令入口 |

当前版本为 `0.2.0`，尚未承诺 1.0 级别的长期兼容性。本轮边界重构会删除已经明确判定为应用包装的旧入口；规范路径以各领域子包为准。

## Direct API 推荐入口

```python
from itertools import islice

from ser_lib.config import build_experiment_config, list_experiment_preset_ids
from ser_lib.data import fingerprint_manifest, iter_records, summarize_manifest
from ser_lib.runtime import get_runtime_metrics

summary = summarize_manifest("data/dataset.yaml")
fingerprint = fingerprint_manifest("data/dataset.yaml")
first_records = list(islice(iter_records("data/dataset.yaml"), 50))
preset_ids = list_experiment_preset_ids()
config = build_experiment_config("cnn_logmel_baseline")
runtime = get_runtime_metrics("cpu")
```

这些函数返回真实领域对象或 iterator，不引入 HTTP、RPC、FastAPI、WebSocket、分页 DTO 或后台 job 概念。

## Dataset records

`ser_lib.data.iter_records(...)` 按 manifest 原始顺序惰性返回 `AudioRecord`，支持：

- split；
- label_id；
- speaker_id；
- keyword（uid、audio path、speaker_id、metadata 的大小写不敏感包含匹配）。

核心库不再计算分页 `total`、`has_more` 或构造 `RecordView`。需要分页时由上层使用
`itertools.islice` 等 iterator 工具自行切片。

## Training run resources

训练详情不再由一个 `TrainingRunDetail` 聚合。调用方按需求读取真实资源：

```python
from ser_lib.engine import (
    load_training_history,
    load_training_run_info,
    scan_checkpoints,
)

run = load_training_run_info("runs/demo")
history = load_training_history("runs/demo")
checkpoints = scan_checkpoints("runs/demo/checkpoints")
```

`load_training_run_info` 只读取 `run.json`，`load_training_history` 只读取 `history.json`，
`scan_checkpoints` 只做 checkpoint 文件扫描/stat，不调用 `torch.load()`。缺失或损坏资源以各自真实异常显式返回，不由详情 wrapper 吞掉后转换为展示 Diagnostic。

## Evaluation run resources

评估 metadata、report 和 prediction 文件信息也分别读取：

```python
from ser_lib.engine import (
    inspect_evaluation_prediction_file,
    inspect_evaluation_report,
    load_evaluation_run_info,
)

run = load_evaluation_run_info("runs/eval-demo")
report = inspect_evaluation_report("runs/eval-demo")
prediction_file = inspect_evaluation_prediction_file(run)
```

`inspect_evaluation_prediction_file` 只做文件 stat，不读取 `predictions.jsonl` 内容。

预测明细使用流式 iterator：

```python
from itertools import islice
from ser_lib.engine import iter_evaluation_predictions

records = iter_evaluation_predictions(
    "runs/eval-demo",
    incorrect_only=True,
    target=1,
)
page = list(islice(records, 100))
```

`iter_evaluation_predictions` 每次只解析当前 JSONL 行，保留严格 `PredictionRecord` 校验、
错误行号和 cancellation；它不会为了 `matched_count` 或 `has_more` 预先扫描到文件末尾。

## Experiment presets

Preset 的规范入口位于 `ser_lib.config`：

```python
from ser_lib.config import (
    build_experiment_config,
    get_experiment_preset_payload,
    list_experiment_preset_ids,
)

preset_ids = list_experiment_preset_ids()
payload = get_experiment_preset_payload("gru_mfcc_baseline")
config = build_experiment_config(
    "gru_mfcc_baseline",
    overrides={"trainer": {"epochs": 20}},
)
```

Preset 最终仍生成唯一的 `ExperimentConfig`。`get_experiment_preset_payload` 返回深拷贝，
调用方修改不会污染内置模板。核心库不再额外构造 `ExperimentPresetInfo` / `ExperimentPresetCatalog`。

## Component discovery

核心库不再提供跨领域 `ComponentCatalog`。组件发现直接使用真实 owner：

```python
from ser_lib.data import default_registry
from ser_lib.models import model_registry

representations = default_registry.json_safe_descriptors("representation", statuses=None)
importers = default_registry.json_safe_descriptors("importer", statuses=None)
models = model_registry.descriptors()
```

optimizer、scheduler、loss、sampling 的可配置字段直接来自 `ser_lib.config` 中对应 Pydantic
配置模型的 `model_json_schema()`；CLI 的 `ser components list` 也直接使用 data/model registry。

## Artifact catalog

`scan_model_artifacts()` 保留，因为本地 artifact 扫描是实际资源能力。每条结果是最小
`ArtifactEntry`：

- `path`：artifact 目录；
- `manifest`：原始 `ModelArtifactManifest`；
- `weights_bytes`：权重文件 stat 大小。

扫描只执行 manifest inspect 与必要 stat，不计算 SHA256、不加载模型。展示别名、总目录容量、
flatten metadata 等派生信息由上层应用自行计算；完整 hash 验证仍通过 `verify_model_artifact()`。

## Schema migration

schema migration 已按格式所属领域拆分：配置机制位于 `ser_lib.config.migrations`，
dataset/revision、run/evaluation、artifact 的版本门禁分别位于 data、engine、artifacts
领域。原则是只注册真实的 `N -> N+1` 结构迁移：

- 当前版本 payload 为 no-op 深拷贝；
- 不支持的未来版本明确拒绝；
- 缺失迁移路径明确报错；
- migration 不负责业务 I/O，也不会自动改写源文件；
- 不为从未存在过的旧版本伪造 migration。

Artifact manifest 继续兼容真实存在的 v1/v2。v1→v2 涉及权重完整性元数据，不能仅靠
结构转换凭空生成，因此不会伪装成纯 schema migration。

## Runtime snapshot

`ser_lib.runtime.get_runtime_metrics(device)` 是按需、非阻塞资源快照。除已有 CUDA
allocator/driver memory 字段外，还提供：

- `process_rss_bytes`；
- `system_memory_used_bytes`；
- `system_memory_available_bytes`；
- `system_memory_total_bytes`；
- `process_cpu_percent`；
- `system_cpu_percent`。

CPU/RAM 通过跨平台 psutil API 获取，不依赖 Linux `/proc`，不会在 API 内 sleep。
`cpu_percent(interval=None)` 第一次采样可能为 0；调用方应低频轮询而不是塞进 Trainer
每个 batch 的热路径。

## ETA v2

`ser_lib.EtaEstimator` / `ser_lib.engine.EtaEstimator` 使用有界 recent-N batch window，
配置由 `ObservabilityConfig.eta_window_batches` 与 `eta_warmup_batches` 控制。Trainer
ProgressEvent 继续保留：

- `estimated_epoch_remaining_seconds`；
- `estimated_remaining_seconds`。

warmup 未完成时这些 ETA 为 `None`，并通过 `eta_ready` 明确表示状态。事件同时提供
recent throughput；validation 使用独立 phase 状态，不会污染 train ETA。

## 成本边界

资源检查时按需要组合最小 API：

- checkpoint scan：只做目录扫描/stat，不隐式加载权重；
- evaluation report/stat：不整文件读取 predictions；prediction records 用 iterator；
- dataset record filter：iterator 不计算分页总数；
- dataset summary：默认不扫描音频 header，只有显式请求 audio profile 才增加 I/O；
- artifact catalog/inspect：不隐式加载模型权重，完整 verify/hash 由显式接口触发。

这些边界同样适用于未来 Desktop/Web 宿主。

## 类别不平衡与训练目标

- `ser_lib.engine.LossConfig`：交叉熵、focal loss、类别权重和 label smoothing。
- `ser_lib.engine.SamplingConfig`：随机打乱或 WeightedRandomSampler 配置。
- `ser_lib.engine.ClassificationLoss`：经过严格配置校验的分类损失。
- `ser_lib.engine.build_weighted_sampler`：根据训练标签构建确定性平衡采样器。

## 数据导入器

内置 importer 从 `ser_lib.data.importers` 导入，包括 `FolderImporter`、
`CsvImporter`、`JsonlImporter`、`CasiaImporter`、`RavdessImporter`、
`CsemotionsImporter`、`EsdImporter`、`CremaDImporter` 和 `EmotionTalkImporter`。
所有实现遵循 `scan(source, config) -> ImportPreview` 与
`convert(source, destination, config) -> DatasetManifest` 契约；组件发现应使用
registry descriptor，而不是硬编码类列表。
