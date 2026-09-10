# 公共 API 索引

稳定入口优先从对应领域子包导入。Python Worker、CLI、Notebook 与未来 Web/Desktop
宿主都应组合 `ser_lib.data`、`ser_lib.models`、`ser_lib.engine`、`ser_lib.inference`
和 `ser_lib.artifacts` 的公开 API；库内不再提供 Application Service facade。
未列入各模块 `__all__` 的名称视为实现细节。

| 子包 | 主要公开能力 |
|---|---|
| `ser_lib.foundation` | 事件、取消、Diagnostic、公共异常与显式日志辅助 |
| `ser_lib.config` | 严格配置 schema、配置加载与各领域用户配置 |
| `ser_lib.data` | Manifest、AudioLoader、SERDataset、Pipeline、Collator、查询/profile/revision |
| `ser_lib.models` | SERModel、ModelOutput、ModelSpec、CNN、GRU、Transformer、HF adapter 与注册表 |
| `ser_lib.engine` | ExperimentConfig、Preset、Trainer、训练/评估实验、Run metadata、checkpoint |
| `ser_lib.artifacts` | artifact 导出、轻量 inspect/catalog、验证、加载和模型卡 |
| `ser_lib.inference` | 单文件、批量和纯 PCM 流式推理 |
| `ser_lib.runtime` | 按需运行环境能力与资源快照 |
| `ser_lib.benchmark` | 可序列化微基准和同环境回归比较 |
| `ser_lib.cli` | `ser` 命令入口 |

当前版本为 `0.2.0`，尚未承诺 1.0 级别的长期兼容性。本轮边界重构会删除已经明确判定为应用包装的旧入口；迁移后的规范路径以各领域子包为准。

## Direct API 推荐入口

```python
from ser_lib.data import fingerprint_manifest, summarize_manifest
from ser_lib.engine import build_experiment_config, list_experiment_presets
from ser_lib.runtime import get_runtime_metrics

summary = summarize_manifest("data/dataset.yaml")
fingerprint = fingerprint_manifest("data/dataset.yaml")
presets = list_experiment_presets()
config = build_experiment_config("cnn_logmel_baseline")
runtime = get_runtime_metrics("cpu")
```

这些函数返回领域 DTO/对象，不引入 HTTP、RPC、FastAPI、WebSocket 或后台 job 概念。

## Training Run Detail

`ser_lib.engine.inspect_training_run_detail(path)` / `ser_lib.TrainingRunDetail` 当前聚合：

- `run.json` 的稳定训练 metadata；
- `history.json`（缺失或损坏时以 Diagnostic 降级）；
- checkpoint catalog 的文件名/大小/mtime 等 stat 信息。

该接口不会 `torch.load()` checkpoint。真正恢复训练时应显式调用 checkpoint load/resume 路径。
`TrainingRunDetail` 属于当前兼容表面，后续边界阶段会继续收缩页面型聚合对象。

## Evaluation Run Detail

`ser_lib.engine.inspect_evaluation_run_detail(path)` / `ser_lib.EvaluationRunDetail` 当前聚合
`evaluation.json`、metrics report 与 prediction 文件 metadata。详情接口只检查 predictions
文件是否存在及大小，不读取整份 JSONL；预测明细当前使用
`ser_lib.engine.query_evaluation_predictions(..., offset=..., limit=...)` 读取。

`EvaluationRunDetail` 与分页包装属于当前兼容表面，后续边界阶段会继续收缩页面型 API，
但 evaluation metadata、report 和 prediction records 本身会保留。

## Experiment Presets

```python
from ser_lib.engine import (
    build_experiment_config,
    get_experiment_preset,
    list_experiment_presets,
)

catalog = list_experiment_presets()
preset = get_experiment_preset("gru_mfcc_baseline")
config = build_experiment_config(
    "gru_mfcc_baseline",
    overrides={"trainer": {"epochs": 20}},
)
```

Preset 最终仍生成唯一的 `ExperimentConfig`，不会形成第二套配置模型。目前稳定 preset
包括 CNN+LogMel、GRU+MFCC、Transformer+LogMel；未为需要额外权重/依赖的 HF 模型
伪造不完整默认值。

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

面向列表/详情读取时应优先使用轻量接口：

- training checkpoint list/detail：只做目录扫描/stat，不隐式加载权重；
- evaluation run detail：不整文件读取 predictions；
- dataset summary：默认不扫描音频 header，只有显式请求 audio profile 才增加 I/O；
- artifact catalog/inspect：列表阶段不隐式加载模型权重，完整 verify/hash 由显式接口触发。

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
`convert(source, destination, config) -> DatasetManifest` 契约；组件发现应优先使用
registry descriptor，而不是硬编码类列表。
