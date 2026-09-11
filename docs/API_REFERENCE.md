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
| `ser_lib.engine` | ExperimentConfig、Trainer、训练/评估实验、TrainingRecord/EvaluationRecord、report、prediction iterator、checkpoint |
| `ser_lib.artifacts` | artifact 导出、轻量 inspect/catalog、验证、加载和模型卡 |
| `ser_lib.inference` | 单文件、批量和纯 PCM 流式推理 |
| `ser_lib.runtime` | Python/PyTorch 与 CPU/CUDA/MPS 运行能力探测 |
| `ser_lib.cli` | `ser` 命令入口 |

当前待发布版本为 `0.3.0`，尚未承诺 1.0 级别的长期兼容性。本轮边界重构包含 breaking Python API 调整；规范路径以各领域子包为准，迁移说明见 `CHANGELOG.md`。

## 根包便利入口

`import ser_lib` 只保留少量高层、惰性加载的便利入口，不作为完整 API 目录：

- `SERDataset`、`SERBatch`、`SERModel`；
- `Trainer`、`TrainingResult`、`evaluate`、`train_experiment`、`evaluate_artifact`；
- `EmotionPredictor`、`PredictionResult`；
- `export_model_artifact`、`load_model_artifact`。

配置、运行时、诊断、兼容性报告、lineage、catalog 等能力必须从其领域子包导入。这样
`import ser_lib` 不会为了访问一个简单符号而加载整个库，也避免重新形成跨领域 facade。

## Direct API 推荐入口

```python
from ser_lib.config import build_experiment_config, list_experiment_preset_ids
from ser_lib.data import DatasetManifest, fingerprint_manifest, summarize_manifest
from ser_lib.runtime import get_runtime_capabilities

summary = summarize_manifest("data/dataset.yaml")
fingerprint = fingerprint_manifest("data/dataset.yaml")
first_records = DatasetManifest.load("data/dataset.yaml").get_records()[:50]
preset_ids = list_experiment_preset_ids()
config = build_experiment_config("cnn_logmel_baseline")
runtime = get_runtime_capabilities()
```

这些函数返回真实领域对象或 iterator，不引入 HTTP、RPC、FastAPI、WebSocket、分页包装或后台 job 概念。

## Dataset records

`DatasetManifest.get_records(split=...)` 按 manifest 原始顺序返回 `AudioRecord` 列表；`split=None`
返回全部记录，每条记录的 split 归属由 `record_splits` 保留。需要逐条解析音频路径时使用
`resolved_records(split=...)`。

核心库不计算分页 `total`、`has_more`，不构造 `RecordView`，也不提供 label/speaker/keyword
筛选。分页与筛选由上层自行实现。

## Training run resources

训练记录、history 与 checkpoint 分别由各自领域 API 读取：

```python
from ser_lib.engine import (
    load_training_history,
    load_training_record,
    scan_checkpoints,
)

run = load_training_record("runs/demo")
history = load_training_history("runs/demo")
checkpoints = scan_checkpoints("runs/demo/checkpoints")
```

`load_training_record` 只读取 `run.json`，`load_training_history` 只读取 `history.json`，
`scan_checkpoints` 只做 checkpoint 文件扫描/stat，不调用 `torch.load()`。缺失或损坏资源以各自真实异常显式返回，不由详情 wrapper 吞掉后转换为展示 Diagnostic。

## Evaluation run resources

评估 record、report 和 prediction 文件信息也分别读取：

```python
from ser_lib.engine import (
    inspect_evaluation_prediction_file,
    inspect_evaluation_report,
    load_evaluation_record,
)

run = load_evaluation_record("runs/eval-demo")
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

## 当前持久化格式

配置、dataset、artifact、checkpoint、run/evaluation 和事件只使用当前结构。
当前格式必需字段缺失、错误类型、未知字段以及已废弃的版本字段都会被直接拒绝。
`library_version` 保留创建来源，不参与兼容分支；模型与数据的形状、标签及预处理契约仍须校验。
artifact 固定使用 weights.safetensors；checkpoint 仅用于可信本地恢复。

## Runtime capabilities

`ser_lib.runtime.get_runtime_capabilities()` 只做一次性环境能力探测，返回 Python/PyTorch
版本、CPU/CUDA/MPS 可选设备、GPU 名称与总显存以及 AMP capability。核心库不再提供
CPU/GPU 资源轮询或进程监控 API；持续资源监控属于宿主应用或外部观测工具职责。

## ETA v2

`ser_lib.engine.EtaEstimator` 使用有界 recent-N batch window，配置由
`ObservabilityConfig.eta_window_batches` 与 `eta_warmup_batches` 控制。Trainer
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