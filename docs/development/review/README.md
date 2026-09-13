# 开发审查与证据

本目录保存 1.0 前的多轮严格审查，属于**历史架构基线**证据。**所有缺陷编号和评分都只对报告中注明的 commit
基线负责**；原始正文保留，不追溯改写，**不代表当前 API**。

## 1.0 发布时状态

1.0.0 发布基线：`495f8f5`。

- CI #581 全绿。
- Linux/Windows/macOS × Python 3.10–3.12 全部通过。
- HF Transformers 4.38.2 / 5.17.0 通过。
- Ruff、mypy、coverage、wheel 隔离安装、CPU 单 epoch smoke 通过。
- 普通矩阵记录 518 passed / 3 skipped；质量任务记录 528 passed / 1 skipped。

因此，下列旧报告中的“尚未修复”“不能验收”等表述只描述其历史基线。

## 审查链

- [核心边界审计](SER_LIB_CORE_BOUNDARY_AUDIT.md) 与
  [完整证据](SER_LIB_CORE_BOUNDARY_EVIDENCE.md)：0.2-era 架构边界审计，推动 core /
  services / facade 收敛。
- [逐模块严格评估](SER_LIB_STRICT_REVIEW_2026-09-10.md) 与
  [第二轮严格审查](SER_LIB_STRICT_REVIEW_ROUND2_2026-09-10.md)：记录 R2/R3 边界、
  数值与恢复问题；后续重构/修复提交逐步吸收。
- [latest-only 完成版严格审查](SER_LIB_LATEST_ONLY_REVIEW_2026-09-11.md)：基线
  `2e4839a`，LO-01～LO-05；报告顶部已记录修复复验。
- [修复合并后的追加审查](SER_LIB_POST_FIX_REVIEW.md)：基线 `3e4c66a`，
  PF-01～PF-03；报告顶部已记录后续 checkpoint identity/rollback/counter 修复。
- [跨模块深入审查](SER_LIB_DEEP_WORKFLOW_REVIEW.md)：基线 `64ff7e2`，
  DW-01～DW-08；报告顶部记录 2026-09-13 修复复验，最终修复进入 `495f8f5`。

## 如何使用历史复现脚本

scripts/audit_* 是特定历史基线的缺陷探针；很多脚本的“成功”意味着成功复现旧 bug。
不要在 1.0 HEAD 上把旧探针断言失败解释成当前回归。

当前修复验证以 tests/ 中的正式 regression tests 和当前 CI 为准。

## 边界

历史审查覆盖大量高风险路径，但不是形式化验证，也不能证明所有硬件、模型、第三方数据、
依赖上下限或长期运行场景都不存在问题。1.0 兼容与使用契约以当前用户文档为准。
