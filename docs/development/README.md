# 1.0 前开发记录

本目录保存 SER-lib 1.0 形成过程中的 ADR、阶段计划、重构记录和严格审查证据。

> 归档说明：这些文档针对各自注明的历史 commit。正文中的“未完成”“尚未修复”
> “当前版本”“下一步”等状态不应直接解释为 1.0.0 当前状态。当前规范从
> [docs/README.md](../README.md) 进入，当前发布状态见 [CHANGELOG.md](../../CHANGELOG.md)。

## 架构与阶段记录

- [LATEST_ONLY_ARCHITECTURE.md](LATEST_ONLY_ARCHITECTURE.md)：latest-only ADR。
- [LATEST_ONLY_PROGRESS.md](LATEST_ONLY_PROGRESS.md)：Stage 1–12 实施记录。
- [SER_LIB_LATEST_ONLY_REFACTOR_PLAN.md](SER_LIB_LATEST_ONLY_REFACTOR_PLAN.md)：完整重构计划。
- [core-boundary-refactor/](core-boundary-refactor/)：核心边界 12 阶段方案。
- [../DATA_PIPELINE_REFACTOR_PLAN.md](../DATA_PIPELINE_REFACTOR_PLAN.md)：数据管线早期重构计划。

## Review / audit

见 [review/README.md](review/README.md)。

1.0 发布基线为 `495f8f5`；该基线的 CI #581 在 Linux/Windows/macOS、Python
3.10–3.12、HF 版本矩阵、Ruff、mypy、coverage、wheel smoke 与 CPU training smoke
均通过。历史审查用于解释为什么后续修复存在，不代表形式化证明“没有其他 bug”。
