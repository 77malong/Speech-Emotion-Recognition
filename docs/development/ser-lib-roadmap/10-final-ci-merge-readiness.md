# 10 - Final CI and Merge Readiness

## 目标

完成 `feat/ser-studio-foundation` 合并 `main` 前的最终质量与差异审查。本任务不默认执行 merge；只有所有门禁通过后才进入“可合并”状态。

## 质量门禁

本地/CI 必须覆盖当前项目已有规则：

```text
pip check
compileall
pytest
training smoke
Ruff
mypy
coverage
```

CI 目标：

- Ubuntu / Python 3.10
- Ubuntu / Python 3.12
- Windows / Python 3.10
- Windows / Python 3.12
- macOS / Python 3.10
- macOS / Python 3.12
- Static checks

## Feature -> main Diff Review

重点分类审查：

1. Public API 新增/删除；
2. Config/schema 变化；
3. Dataset 写盘与 transaction/revision；
4. Training/Evaluation run metadata；
5. Artifact 格式；
6. CLI 行为；
7. 新增依赖；
8. 平台特定代码；
9. 性能风险：隐式大文件 load/hash/scan；
10. 安全风险：不可信 checkpoint 是否被列表/inspect 隐式 `torch.load()`。

## 清理项

- 临时 compatibility shim 是否仍需要；
- 重复 DTO/API；
- 未使用 import/dead code；
- 文档 TODO；
- debug print/log；
- 过度宽泛 exception；
- test-only 代码泄漏到 runtime。

## 版本策略

当前版本仍为 `0.2.0`。完成审计后再决定是否提升稳定开发版本。版本变化必须与 CHANGELOG/README/pyproject 同步，不能只改一个地方。

## Merge 前最终验收

- 01-09 文档全部完成并标记实现状态；
- 最新 feature HEAD CI 全绿；
- 对 main 无未解释冲突；
- Public API audit 无 blocking 项；
- Service audit 无 blocking 项；
- 文档与代码一致；
- 无 SER-Studio UI 代码进入此仓库；
- 保持 Python Worker → `ser_lib.services` 的架构边界。

## 建议提交

清理与文档可以分提交。不要为了“一个最终 commit”把无关修正揉在一起。

完成后输出 merge-readiness 总结：

```text
HEAD
CI
API breaking changes
schema changes
new dependencies
known limitations
merge recommendation
```
