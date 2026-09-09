# SER-lib Stabilization Merge Readiness

更新时间：2026-09-09

目标分支：`feat/ser-studio-foundation`
目标基线：`main`

## 1. 范围结论

本轮仍只修改 `ser_lib` 及其测试、CLI/示例/文档/CI，不开发 SER-Studio UI，也没有在 `ser_lib` 中引入 FastAPI、HTTP/WebSocket/SSE Server、用户系统、Redis/Celery 或 Web Job 数据库。

未来 Worker 应优先通过 `ser_lib.services` 调用领域能力；底层领域模块继续保留给高级 Python 调用方。

## 2. Roadmap 完成情况

| 编号 | 任务 | 状态 | 结果 |
|---|---|---|---|
| 01 | Training Run Detail | ✅ | `TrainingRunDetail` + `TrainingService.inspect_run_detail()`；checkpoint 只做 stat，不加载权重 |
| 02 | Evaluation Run Detail | ✅ | `EvaluationRunDetail` + `EvaluationService.inspect_run_detail()`；prediction detail 不整文件读取 |
| 03 | Experiment Presets | ✅ | 3 个稳定 preset；最终统一生成 `ExperimentConfig` |
| 04 | Schema Migration | ✅ | 通用 migration registry；ExperimentConfig、Dataset Manifest、Training Run、Evaluation Run、Dataset Revision 接入；Artifact v1/v2 统一版本门禁 |
| 05 | CPU / RAM Runtime Metrics | ✅ | psutil 跨平台 process/system CPU/RAM snapshot；无 sleep、无 `/proc` 依赖 |
| 06 | ETA Estimator v2 | ✅ | recent-N bounded estimator、warmup、train/validation 独立 phase，旧 ETA 字段保留 |
| 07 | Public API Audit | ✅ | 根包/领域包 `__all__` 契约测试；ETA/RunDetail/Preset 稳定导出；Migration 留在 `ser_lib.core` |
| 08 | Service API Audit | ✅ | CatalogService 补齐 Preset workflow；既有 Dataset/Training/Evaluation/Inference/Artifact/Runtime facade 保持 thin delegation |
| 09 | Docs & Examples Sync | ✅ | `docs/API_REFERENCE.md` + service-first example 已同步 |
| 10 | Final CI & Merge Readiness | 🔄 | feature→main diff 已审查；以本文件提交后的 exact HEAD CI 全绿为最终门禁 |

## 3. Schema 兼容策略

### 当前 schema

- ExperimentConfig：v1
- Dataset Manifest：v1
- Training Run `run.json`：v1
- Evaluation Run `evaluation.json`：v1
- Dataset Revision `revision.json`：v1
- Artifact Manifest：真实支持 v1 / v2

原则：

1. 只注册真实存在的 `N -> N+1` migration，不伪造从未存在的 v0；
2. migration 发生在 read-time，不自动改写用户文件；
3. 历史上允许省略 `schema_version` 的格式继续按当前 v1 解释，避免无理由破坏已有数据；
4. Artifact v1 不能仅通过结构转换伪造成 v2，因为 v2 的完整性 metadata 依赖真实文件，因此继续双版本读取并集中做版本门禁；
5. 当前版本 payload 为低成本 no-op，未来版本与缺迁移路径有明确错误。

## 4. Public / Service API 审查结论

### 稳定根包能力

根 `ser_lib` 暴露面向常规 Python 调用方的稳定 DTO 与业务类型，包括：

- Training/Evaluation Run Detail；
- Experiment Preset；
- ETA Estimator；
- Runtime snapshot；
- Artifact / Dataset / Model / Inference 的既有公共能力。

Schema migration 属于较低层持久化基础设施，仅从 `ser_lib.core` 暴露。

### Service facade

Service 类只从 `ser_lib.services` 暴露，不提升到根包：

- `DatasetService`
- `TrainingService`
- `EvaluationService`
- `InferenceService`
- `ArtifactService`
- `CatalogService`
- `RuntimeService`

这样未来 Worker 有单一应用级入口，但不会让根包退化成所有内部能力的聚合桶。

## 5. 成本边界复核

以下约束已作为 API 设计的一部分保留：

- Training Run detail 不 `torch.load()` checkpoint；
- Evaluation Run detail 不读取完整 predictions JSONL；
- prediction 明细继续走分页 query；
- Artifact inspect/catalog 不做完整权重 hash，完整 verify 由显式接口触发；
- Dataset summary 默认不强制扫描全部音频 header；
- CPU/RAM metrics 是按需快照，不进入 Trainer 每 batch 热路径；
- ETA estimator 只保存固定大小 recent window，空间复杂度有界。

## 6. 新依赖

本阶段新增运行时依赖：

- `psutil>=5.9`：用于 Windows/macOS/Linux 一致的 process/system CPU/RAM metrics。

没有新增 Web server、数据库、队列或桌面 UI 依赖。

## 7. feature → main 差异审查

在最终审查时，该 feature 分支相对 `main` 为纯 ahead、无 behind；变化覆盖 P0/P1 基础能力以及本轮 P2/API 稳定化，因此 diff 很大，合并应按“完整 SER-lib foundation feature”理解，而不是一个小型局部 patch。

重点风险面已纳入 CI/测试：

- Trainer 主循环与可观察性；
- Artifact v1/v2 兼容与完整性校验；
- Dataset 编辑/transaction/history；
- Run/Evaluation metadata；
- 跨平台 Runtime metrics；
- 公共导出与 Service facade；
- 配置严格校验与 read-time migration。

## 8. 已知限制（不是本轮阻塞项）

- 仍是单设备训练基础，不在本轮实现多卡/多机；
- Runtime metrics 是 snapshot，不是后台 daemon/时序数据库；
- ETA 是估算值，数据加载抖动、validation 成本变化仍可能导致短期变化；
- 没有为 HF/pretrained 模型伪造需要外部权重/依赖的默认 preset；
- Schema v2 只有在未来真实格式确定后才应注册对应 migration；
- 本轮不实现 SER-Studio frontend/backend transport/job persistence。

## 9. 最终质量门禁

只有当前文档提交后的 exact branch HEAD 同时满足以下条件，才推荐合并：

- `pip check` 通过；
- `compileall` 通过；
- pytest 全量通过；
- end-to-end training smoke 通过；
- Ruff 通过；
- mypy 通过；
- coverage gate 通过；
- Ubuntu / Windows / macOS × Python 3.10 / 3.12 全绿；
- Static checks 全绿。

若任一 exact-HEAD job 失败，应先修复并重新跑完整门禁，不能用旧 commit 的绿色结果替代。

## 10. 合并建议

当第 9 节 exact-HEAD CI 全绿后：**推荐将 `feat/ser-studio-foundation` 作为完整 SER-lib foundation feature 合并到 `main`。**

本文件不执行 merge；是否实际合并由仓库维护者单独决定。
