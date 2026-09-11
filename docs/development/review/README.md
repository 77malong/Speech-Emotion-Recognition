# 开发审查与证据

latest-only 重构说明（2026-09-11）：本目录文档对应历史架构基线，不代表当前 API。历史复现脚本需要在各自注明的提交上执行；新分支会移除旧格式和 release fixture，不能据脚本在新结构上无法运行判定旧 bug 仍存在。实施进度见 `docs/development/LATEST_ONLY_PROGRESS.md`。

同步说明：审查资料现统一位于 `docs/development/review`。本地审查提交已接入远程 `34ee3b3` 的后续整改历史；下列报告的缺陷数量和评分仍针对各自注明的旧基线，不代表这些缺陷在最新代码中全部仍然存在。最新代码需要重新复验，历史报告不作追溯改写。

本目录集中存放 review、audit 与审计证据文档。实施阶段记录仍在 `docs/development/core-boundary-refactor`。

- [逐模块严格评估](SER_LIB_STRICT_REVIEW_2026-09-10.md)：保留第一轮历史判断，新增当前基线的模块复评与联合检查矩阵。
- [第二轮严格审查及扩展缺陷清单](SER_LIB_STRICT_REVIEW_ROUND2_2026-09-10.md)：R2-01～R2-11，以及扩展复现的 R3-01～R3-18。
- [核心边界审计](SER_LIB_CORE_BOUNDARY_AUDIT.md)
- [核心边界证据](SER_LIB_CORE_BOUNDARY_EVIDENCE.md)

当前扩展复现基线为 `0d4bd75`，日期 2026-09-10。第一轮正文属于 `5184155` 历史快照；已修复问题不能仅凭旧正文重新计入当前缺陷。

在仓库根目录运行 `python -m scripts.audit_expanded_repros`。依赖使用项目运行环境；本机使用 `.venv-audit/Scripts/python.exe`。探针只在临时目录操作自建数据，无网络访问、无生产实现修改。输出中的预期异常属于被审项目的缺陷证据，`probe_error` 才表示探针执行失败。通过运行不等于库通过验收。

前两轮复现脚本为 `scripts/audit_boundary_repros.py`（历史基线）和 `scripts/audit_round2_repros.py`（当前基线）。不要把历史脚本在新实现上失败解释为同一个旧缺陷仍然存在。

本次文档扩展验证：扩展探针十组全部执行、无 `probe_error`；两个当前基线审计脚本 Ruff 通过；`tests/test_tutorials.py` 为 1 passed；`git diff --check` 通过；仓库 Markdown 中上述四份审查文档的旧目录引用已清除。此前的 420 passed 属于第二轮完整测试记录，本次仅文档与探针变动，未重新执行全套测试。
