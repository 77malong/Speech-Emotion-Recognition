# Stage 12 — Public API、CLI、文档、依赖与发布验收收口

## 目标

完成整个核心边界重构的最终清场：收缩公开 API、删除所有过渡 shim 和死路径、同步 CLI/示例/配置/教程/文档、收紧依赖与 CI，并从源码树外对 wheel 做最终验证。

## 前置条件

- Stage 01–11 全部完成。
- `core/`、`services/`、Page/View/Detail 包装已经按计划退役。
- Torch/HF adapter 全链路已有真实测试证据。

## 修改范围

重点包括：

- `ser_lib/__init__.py`
- 各子包 `__init__.py` / `__all__`
- `ser_lib/_version.py`
- `ser_lib/cli/*`
- `pyproject.toml`
- `.github/workflows/ci.yml`
- `scripts/check_coverage.py`
- `tests/test_coverage_policy.py`
- `README.md`
- `docs/API_REFERENCE.md`
- `docs/MODEL_DEVELOPMENT.md`
- `docs/TRAINING_AND_CLI.md`
- `docs/ARTIFACTS_AND_SECURITY.md`
- examples/configs/tutorials/notebooks
- `CHANGELOG.md`

## 具体任务

1. 收缩根包重导出，避免 import `ser_lib` 加载几乎全部 package。
2. 删除所有中间 deprecation shim、旧 `core`/`services` import alias、Page/View/Detail/Catalog 残留。
3. 搜索源码、测试、示例、配置、notebook、文档中的旧路径，必须归零或明确作为历史兼容说明。
4. 更新 CLI，使所有命令只调用新的 public domain API。
5. 更新 API reference、模型开发、训练 CLI、artifact/security、安装说明和示例。
6. 检查 tutorial/notebook 是否仍引用旧 Service/DTO；不可执行教程继续明确标注状态。
7. 更新 coverage policy：删除 core 门槛，foundation/config 分别建立合理门槛且不降低其他领域标准。
8. 清洁环境验证基础安装不引入 transformers；单独验证 `.[hf]`。
9. Linux/Windows/macOS × 已声明 Python 版本运行 pip check、compileall、pytest、Ruff、mypy、coverage、CPU training smoke、build/wheel smoke。
10. wheel smoke 必须在源码树外、隔离 venv 中执行，避免源码遮蔽和系统 site-packages 污染。
11. 检查 wheel 内容：不得包含 core/services/应用包装；必须包含新 config、foundation、adapter 和必要 processor assets/entry metadata。
12. 固定旧 config/dataset/checkpoint/artifact fixture 做最终读兼容验证。
13. 更新 CHANGELOG，明确 breaking API、保留的持久化兼容面和迁移示例。
14. 最终比较本分支与 main，确认没有无意删除真实 SER 能力。

## 完成定义

- `ser_lib` 是纯 Python SER Core/SDK，边界清晰，不预置未来 Web/Desktop 的 Service/Page/DTO。
- foundation 足够小，无领域反向依赖；所有内置用户配置集中在 config。
- 只有一套正式 Trainer/evaluate/predict 路径和一套 model registry。
- Torch/HF 模型均可通过统一契约训练、评估、推理、保存和恢复。
- 文档、示例、CLI、wheel 与源码真实 API 一致。
- CI 全部通过后才允许合并，不用旧 commit 的绿色结果替代当前 HEAD。

## 风险

- 最终清理遗漏旧 import，源码环境可运行但 wheel 失败。
- 更新文档时继续保留已删除的 Service-first 架构描述。
- coverage 因模块移动被错误下调。
- HF extra 支持范围没有真实 matrix 证据。

## 建议提交

可按 docs/ci/dependency 分拆，但最终阶段收口提交建议：

`chore(refactor): finalize SER-lib core boundary migration`
