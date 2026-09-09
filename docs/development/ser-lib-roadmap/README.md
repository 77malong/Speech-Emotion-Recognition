# SER-lib P2 + API Stabilization Development Roadmap

更新时间：2026-09-09

目标分支：`feat/ser-studio-foundation`

## 1. 阶段目标

当前阶段只继续完善 `ser_lib`，不开发 SER-Studio 页面、Electron Main、Preload、Vue Store、SQLite UI 业务，也不在 `ser_lib` 中引入 FastAPI、HTTP/WebSocket/SSE Server、用户系统或 Web Job 数据库。

本阶段目标是把已有 P0/P1 能力收口成稳定、机器友好、可被未来 Python Worker 直接调用的领域 API，并完成剩余 P2 能力与 API 稳定化。

## 2. 开发原则

1. 应用层优先调用 `ser_lib.services`，避免跨内部模块拼业务。
2. 所有公开 DTO 必须 JSON-safe；Path 使用统一字符串序列化，datetime 使用 UTC，enum 输出稳定。
3. 大文件/大模型相关列表与详情接口必须分成本设计：列表/详情不能隐式加载模型权重、完整 prediction 文件或全部音频。
4. 长任务必须评估 Progress、Cancellation、Failure event 是否完整。
5. 新接口不得破坏已有接口；旧接口继续保留，新增聚合 facade 在 Service 层完成。
6. Linux / Windows / macOS 行为一致，Python 3.10 / 3.12 CI 均需通过。
7. CLI 与 Service 不维护两套业务逻辑。

## 3. 执行状态

| 编号 | 任务 | 状态 | 主要交付 |
|---|---|---|---|
| 01 | Training Run Detail | ✅ 已完成 | `TrainingRunDetail`、`TrainingService.inspect_run_detail()` |
| 02 | Evaluation Run Detail | ✅ 已完成 | `EvaluationRunDetail`、`EvaluationService.inspect_run_detail()` |
| 03 | Experiment Presets | ✅ 已完成 | Preset Catalog/Resolver，最终生成 `ExperimentConfig` |
| 04 | Schema Migration | ✅ 已完成 | migration framework + Config/Dataset/Run/Evaluation/Revision 接入 + Artifact v1/v2 版本门禁 |
| 05 | CPU / RAM Runtime Metrics | ✅ 已完成 | process/system CPU/RAM snapshot |
| 06 | ETA Estimator v2 | ✅ 已完成 | recent-window 平滑 ETA、warmup、train/validation 独立 phase |
| 07 | Public API Audit | ✅ 已完成 | 公开符号、DTO 序列化、命名与导出契约测试 |
| 08 | Service API Audit | ✅ 已完成 | Service 覆盖常见领域工作流，Preset 通过 `CatalogService` 暴露 |
| 09 | Docs & Examples Sync | ✅ 已完成 | API 文档、service-first 示例、迁移说明同步 |
| 10 | Final CI & Merge Readiness | 🔄 最终门禁 | `MERGE_READINESS.md` 已完成 diff review；等待 exact HEAD 全矩阵 CI 全绿 |

完整 merge-readiness 结论见：[`MERGE_READINESS.md`](./MERGE_READINESS.md)。

## 4. 文档读取/开发规则

每个任务开始前必须重新读取对应编号文档，并按以下顺序执行：

1. 核对当前 HEAD 与前置任务；
2. 读取“现状与改动范围”中列出的真实代码；
3. 先补/更新测试，再完成实现或同步实现测试；
4. 运行该任务的定向测试与静态检查；
5. 核对验收清单；
6. 使用建议 commit 粒度提交；
7. 再进入下一编号文档。

如果实现中发现文档与真实代码不一致，应优先以代码现状为准，并同步修正文档，不能为了符合旧文档重复造 API。

## 5. 总体验收门禁

恢复 SER-Studio 开发前至少满足：

- Training / Evaluation 均有轻量 Run Detail 聚合接口；
- Config 有 Preset 与 Migration；
- Runtime 有 GPU + CPU/RAM metrics；
- ETA 不再主要受前几个 batch 抖动影响；
- Public API / Service API 完成审计；
- 文档与真实 API 一致；
- `pip check`、`compileall`、`pytest`、training smoke、Ruff、mypy、coverage 全通过；
- Ubuntu / Windows / macOS，Python 3.10 / 3.12 CI 全绿；
- 完成 feature → main 总体 diff review 后再决定合并。

当前仅第 10 项的 exact-HEAD CI 结果需要最终确认；不以旧 commit 的绿色结果替代当前 HEAD。
