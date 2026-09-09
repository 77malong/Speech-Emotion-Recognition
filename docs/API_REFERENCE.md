# 公共 API 索引

稳定入口优先从对应子包导入。面向未来 Python Worker 的应用级流程优先使用
`ser_lib.services`；需要组合底层训练、数据、artifact 能力的高级用户再使用领域子包。
未列入各模块 `__all__` 的名称视为实现细节。

| 子包 | 主要公开能力 |
|---|---|
| `ser_lib.core` | 严格配置、事件、取消、Diagnostic、异常与 schema migration |
| `ser_lib.data` | Manifest、AudioLoader、SERDataset、Pipeline、Collator、查询/profile/revision |
| `ser_lib.models` | SERModel、ModelOutput、CNN、GRU、Transformer、HF adapter 与注册表 |
| `ser_lib.engine` | ExperimentConfig、Preset、Trainer、ETA、Run/Evaluation metadata、checkpoint |
| `ser_lib.artifacts` | artifact 导出、轻量 inspect/catalog、验证、加载和模型卡 |
| `ser_lib.inference` | 单文件、批量和纯 PCM 流式推理 |
| `ser_lib.services` | Dataset/Training/Evaluation/Inference/Artifact/Catalog/Runtime 应用 facade |
| `ser_lib.benchmark` | 可序列化微基准和同环境回归比较 |
| `ser_lib.cli` | `ser` 命令入口 |

当前版本为 `0.2.0`，尚未承诺 1.0 级别的长期兼容性；本轮稳定化优先保持已有
0.2.x 调用路径，并通过新增字段/alias 而不是无兼容重命名演进。

## Service-first 推荐入口

```python
from ser_lib.services import (
    ArtifactService,
    CatalogService,
    DatasetService,
    EvaluationService,
    RuntimeService,
    TrainingService,
)

summary = DatasetService.summary("data/dataset.yaml")
presets = CatalogService.presets()
config = CatalogService.build_experiment("cnn_logmel_baseline")
runtime = RuntimeService.metrics("cpu")
```

Service 层返回领域 DTO/对象，不复制底层业务规则，也不引入 HTTP、RPC、FastAPI、
WebSocket 或后台 job 概念。

## Training Run Detail

`TrainingService.inspect_run_detail(path)` / `ser_lib.TrainingRunDetail` 聚合：

- `run.json` 的稳定训练 metadata；
- `history.json`（缺失或损坏时以 Diagnostic 降级）；
- checkpoint catalog 的文件名/大小/mtime 等 stat 信息。

该接口不会 `torch.load()` checkpoint，因此适合历史详情页和 Worker API。需要真正恢复
训练时再显式调用 checkpoint load/resume 路径。

## Evaluation Run Detail

`EvaluationService.inspect_run_detail(path)` / `ser_lib.EvaluationRunDetail` 聚合
`evaluation.json`、metrics report 与 prediction 文件 metadata。详情接口只检查 predictions
文件是否存在及大小，不读取整份 JSONL；预测明细使用
`EvaluationService.query_predictions(..., offset=..., limit=...)` 分页读取。

## Experiment Presets

```python
from ser_lib.services import CatalogService

catalog = CatalogService.presets()
preset = CatalogService.get_preset("gru_mfcc_baseline")
config = CatalogService.build_experiment(
    "gru_mfcc_baseline",
    overrides={"trainer": {"epochs": 20}},
)
```

Preset 最终仍生成唯一的 `ExperimentConfig`，不会形成第二套配置模型。目前稳定 preset
包括 CNN+LogMel、GRU+MFCC、Transformer+LogMel；未为需要额外权重/依赖的 HF 模型
伪造不完整默认值。

## Schema migration

`ser_lib.core` 提供 `SchemaMigration`、`MigrationRegistry`、
`migrate_schema_payload()` 等显式 read-time migration 基础设施。原则是只注册真实的
`N -> N+1` 结构迁移：

- 当前版本 payload 为 no-op 深拷贝；
- 不支持的未来版本明确拒绝；
- 缺失迁移路径明确报错；
- migration 不负责业务 I/O，也不会自动改写源文件；
- 不为从未存在过的旧版本伪造 migration。

Artifact manifest 继续兼容真实存在的 v1/v2。v1→v2 涉及权重完整性元数据，不能仅靠
结构转换凭空生成，因此不会伪装成纯 schema migration。

## Runtime snapshot

`RuntimeService.metrics(device)` / `get_runtime_metrics(device)` 是按需、非阻塞资源快照。
除已有 CUDA allocator/driver memory 字段外，现在还提供：

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

面向列表/详情页时应优先使用轻量接口：

- training checkpoint list/detail：只做目录扫描/stat，不隐式加载权重；
- evaluation run detail：不整文件读取 predictions；
- dataset summary：默认不扫描音频 header，只有显式请求 audio profile 才增加 I/O；
- artifact catalog/inspect：列表阶段不隐式加载模型权重，完整 verify/hash 由显式接口触发。

这些边界是未来 Desktop/Web Worker 的稳定性能契约。

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
