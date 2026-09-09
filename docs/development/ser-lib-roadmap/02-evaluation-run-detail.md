# 02 - Evaluation Run Detail

## 背景

当前评估已经有 `evaluation.json` 运行元数据、`metrics.json` 轻量报告详情以及 `predictions.jsonl` 流式查询。列表扫描也明确不会读取完整 predictions。下一步需要像 TrainingRunDetail 一样，为 Worker/应用层提供单次详情聚合。

## 目标

新增：

```python
EvaluationRunDetail
EvaluationService.inspect_run_detail(...)
```

聚合：

- EvaluationRunInfo / evaluation metadata；
- metrics/report summary；
- predictions metadata（路径、存在状态、文件大小等）；

默认绝不读取完整 `predictions.jsonl`。

## 主要代码

- `ser_lib/engine/evaluation_runs.py`
- `ser_lib/engine/evaluation_catalog.py`
- `ser_lib/engine/evaluation_reports.py`
- `ser_lib/services/evaluation.py`
- `ser_lib/engine/__init__.py`
- 新增 `tests/test_evaluation_run_detail.py`

## 非范围

- 不把 prediction records 放进 detail；
- 不扫描整个 JSONL 来计算总数，除非现有 metadata 已有该值；
- 不加载 Artifact 权重；
- 不改变现有 prediction query 分页接口。

## DTO 要求

建议结构：

```text
EvaluationRunDetail
├── run
├── report / metrics
├── predictions
└── diagnostics
```

`predictions` 应是轻量 metadata，而不是 `list[PredictionRecord]`。如果 `evaluation_reports.py` 已有可复用的 inspect DTO，直接嵌套，不重复建模。

## 实现步骤

1. 复核 `inspect_evaluation_report()` 的成本边界。
2. 复核 evaluation catalog/run DTO 与 report DTO 的字段重叠。
3. 设计最小聚合 DTO，避免复制 aggregate metrics。
4. 在 `EvaluationService` 复用已有 run/report inspect。
5. 对缺失 metrics / predictions 分别建模；metrics 缺失是否致命应沿用现有语义。
6. 更新公共导出与测试。

## 测试

- 完整目录正确聚合；
- 大 predictions 文件不被 `read_text()` / 全量 open 读取；
- predictions 内容损坏不影响仅查看 metadata；
- metrics 可读取时 detail 正常；
- predictions 缺失时返回稳定状态；
- JSON-safe；
- 原 report inspect 与 prediction query 不回归。

## 验收

- 详情页只需一次 Service 调用；
- 默认成本与 `evaluation.json + metrics.json + stat(predictions)` 同量级；
- 不自动读取 prediction records；
- 不加载模型或 Artifact 权重。

## 建议提交

`feat(evaluation): add lightweight evaluation run detail`
