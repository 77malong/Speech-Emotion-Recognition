# Stage 09 — 删除 Page / View / Detail / 聚合 Catalog 包装

> **1.0 归档说明（2026-09-13）**：本文是 SER-lib 1.0 形成过程中的历史记录，状态、路径、缺陷与“下一步”只对文中注明的历史基线负责。当前 1.0 规范请从 [文档索引](../README.md) 或仓库 `docs/README.md` 进入；当前发布状态见 `CHANGELOG.md`。原始正文保留用于审计追溯。


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

## 实施记录

Stage 09 开始前重新读取了 `SER_LIB_CORE_BOUNDARY_AUDIT.md`、`SER_LIB_CORE_BOUNDARY_EVIDENCE.md` 与本阶段计划，并按“删除包装、保留算法”的边界逐项核对 data query、training/evaluation run、prediction report、artifact scan、component catalog 与 preset introspection。实现范围从 Stage 08 closure `2c9a5f78115690b5a94ca338ffec264939e2e815` 推进到代码验收 HEAD `d8c0adcc53bd071f149b81362ea794bf148dd66e`；未修改 models adapter、HF processor、optimizer/checkpoint 训练算法，因此没有越界进入 Stage 10/11。

数据查询已退役 `RecordView`、`RecordPage`、`query_records` 和 `_to_view`，改为 `ser_lib.data.iter_records() -> Iterator[AudioRecord]`；过滤、split/label/speaker/uid 子串筛选、稳定顺序与 cancellation 继续保留，分页/计数由调用方按需 `islice` 或统计，不再为了页面 total 扫描并复制整页 DTO。对应测试直接锁住 iterator 过滤和调用方切片语义。

评估 prediction 查询已退役 `EvaluationPredictionPage` 与 `query_evaluation_predictions`，改为 `iter_evaluation_predictions()` 流式逐行 yield `PredictionRecord`。逐行 schema 校验、坏行行号错误和 cancellation 继续保留，并新增“首条合格记录可在坏尾部被扫描前 yield”的回归，避免因为 matched_count/has_more 再扫描到 EOF。真实 prediction 文件 metadata `EvaluationPredictionFileInfo` 与 stat helper 合并到 `evaluation_reports.py` 并继续保留。

`TrainingRunDetail` 与 `EvaluationRunDetail` 已删除；调用方和测试分别组合 `load_training_run_info`、`load_training_history`、`scan_checkpoints`，以及 `load_evaluation_run_info`、`inspect_evaluation_report`、`inspect_evaluation_prediction_file`。此前 Stage 08 为接回 Service 隐藏行为临时保留的 detail 聚合入口与 `engine/evaluation_detail.py` 在本阶段一并退役；run.json/history/report/checkpoint/prediction stat 等真实资源 API 未删除。

Artifact 扫描继续保留 no-load/no-hash 语义，但 `ArtifactInfo` 已收缩为最小 `ArtifactEntry(path, manifest, weights_bytes)`：不再扁平复制 model/labels/metrics/metadata，也不再替管理页计算总目录容量。`inspect_model_artifact`、`verify_model_artifact`、`load_model_artifact` 的职责边界保持不变，scan 仍只 inspect/stat，verify 才 hash，load 才实例化模型。

跨领域聚合 `ser_lib/catalog.py` 已物理删除（删除提交 `d4a8436c2a349d416599f7f5c1eebe25aca76121`）；组件发现改为 data/model registry 的原生 descriptor/schema。`engine/presets.py` 也已物理删除（`59cb870063ecd1fa7da34c8d19b3f6b3b6247747`），preset 直接使用 `ser_lib.config.list_experiment_preset_ids()`、`get_experiment_preset_payload()` 与 `build_experiment_config()`。根包同步移除 ComponentCatalog/PresetCatalog/Page/Detail 等应用包装导出，同时保留真实 `ComponentDescriptor` 与 `build_experiment_config` 的 canonical convenience 路径。

Stage 01 历史 fixture 未修改；`tests/test_pre_refactor_contracts.py` 只显式声明 Stage 09 的计划内 public-API delta。`tests/test_public_api.py` 进一步要求已退役 wrapper 名不可解析，并把 `ser_lib.catalog`、`ser_lib.engine.presets`、`ser_lib.engine.evaluation_detail` 列为退役 namespace。CI wheel smoke 在 `47abb8f2edca1436773b038b26b1400c7658ee45` 增加这些 namespace 的独立安装包缺失断言；`docs/API_REFERENCE.md` 和 `examples/inspect_runs_and_presets.py` 也改为直接组合领域资源 API。

首轮 exact-head CI #376 / run `34443151078` 的 package install、dependency check、compile、Ruff 和 mypy 均通过，但 pytest collection 发现两个遗漏的旧测试入口：`tests/test_config_schema_centralization.py` 仍导入已删除的 `ser_lib.engine.presets`，`tests/test_direct_domain_apis.py` 仍导入 `query_records`。分别由 `7d45dc54c6d9d7d26ee3d73692498816c2556265` 与 `d8c0adcc53bd071f149b81362ea794bf148dd66e` 迁到 canonical config/record iterator 后，代码验收 CI #378 / run `34443321741` 7/7 `completed/success`：Ruff、mypy、package coverage、Ubuntu/macOS/Windows × Python 3.10/3.12、完整测试与 training smoke 全部通过；Ubuntu 3.12 的 distribution build 与独立 wheel smoke 同样成功。

因此 Stage 09 的代码验收已满足：公开 API 不再暴露 View/Page/Detail/aggregate catalog 包装，数据过滤、prediction 流式读取、run/history/report、scan failure、artifact no-load 扫描和领域 registry/config introspection 均由真实资源 API 继续承担，没有为了统一返回类型创建新的页面 DTO。