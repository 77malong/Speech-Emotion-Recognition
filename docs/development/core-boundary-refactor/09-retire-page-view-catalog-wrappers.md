# Stage 09 — 删除 Page / View / Detail / 聚合 Catalog 包装

## 目标

清理为 Web/页面消费形态服务的包装对象，让核心库返回真实领域对象、iterator、metadata 和报告，而不是提前替上层应用定义分页 DTO、详情页聚合或跨领域组件目录。

## 前置条件

- Stage 08 services 已退役。
- 所有消费者已经可以直接使用领域 API。

## 删除重点

根据最新审计，重点退役：

- `RecordView`
- `RecordPage`
- `_to_view`
- `TrainingRunDetail`
- `EvaluationRunDetail`
- 旧 evaluation detail 包装
- `EvaluationPredictionPage`
- 根级 `catalog.py` / `ComponentCatalog` 聚合包装
- 仅为了页面展示而扁平复制 manifest 的 `ArtifactInfo` 形态（按当前实现核实后收缩）

## 必须保留的能力

1. AudioRecord 过滤与 iterator。
2. Dataset profile/statistics。
3. TrainingRunInfo、run.json、history。
4. EvaluationRunInfo、report metadata、prediction JSONL 流式读取。
5. PredictionRecord 校验、坏行处理、取消。
6. Artifact manifest inspect/verify/load 和轻量扫描。
7. Dataset revision、checkpoint、training/evaluation run 的真实资源 catalog。
8. registry/config schema 自发现。

## 具体任务

1. 将分页逻辑改为 iterator + 调用方自行切片/计数，不在核心层免费返回 total。
2. 将 run detail 消费者拆成 read/history/scan 等真实接口组合。
3. 将 evaluation prediction 查询改为流式 JSONL iterator，确保大文件不整体载入内存。
4. 将 CLI components/preset 查询改为各领域 registry/config 原生 introspection。
5. 删除统一 ComponentCatalog 以及转换 ModelDescriptor/ComponentDescriptor 的重复描述层。
6. 清理根包、engine/data/artifacts 导出和文档引用。

## 非目标

- 不删除任何算法数据、历史、报告、扫描失败集合。
- 不为“统一返回类型”再创建新的 DTO/Page 类型。

## 验收标准

- 公开 API 中无 View/Page/Detail 应用包装符号。
- 大 prediction / run / artifact 列表继续满足 no-load、有限内存和 cancellation 性质。
- CLI 组件发现仍可用，但直接来自 registry/config schema。
- 数据过滤、报告、历史与 scan failure 回归全部通过。

## 风险

- 删除包装时误删真正的过滤/统计算法。
- iterator 改造后调用方意外 `list()` 导致内存回退。
- Catalog 删除后遗漏 preset 或 registry discoverability。

## 建议提交

`refactor(api): remove page view detail and aggregate catalog wrappers`
