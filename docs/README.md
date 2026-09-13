# SER-lib 1.0 文档索引

本目录区分“当前 1.0 规范”和“历史开发记录”。使用库时应优先阅读当前规范；
docs/development 下的计划、阶段日志和审查报告保留用于审计追溯，不代表当前 API 状态。

## 当前 1.0 规范

| 文档 | 用途 |
|---|---|
| [安装与环境](INSTALLATION.md) | Python、依赖、extras、安装验证 |
| [标准数据格式](DATA_FORMAT.md) | dataset.yaml、JSONL、split、importer |
| [训练与 CLI](TRAINING_AND_CLI.md) | train/resume/evaluate/predict/artifact 与运行产物 |
| [公共 API](API_REFERENCE.md) | 1.x 公开 Python API 与领域边界 |
| [模型扩展](MODEL_DEVELOPMENT.md) | SERModel、ModelSpec、registry、测试要求 |
| [Artifact 与安全](ARTIFACTS_AND_SECURITY.md) | checkpoint 与 artifact 的信任边界 |
| [教程状态](TUTORIAL_STATUS.md) | tutorials/00–07 当前可执行状态 |

仓库级补充文档：

- [项目 README](../readme.md)
- [配置模板](../configs/README.md)
- [数据导入说明](../data/readme.md)
- [可执行示例](../examples/README.md)
- [贡献指南](../CONTRIBUTING.md)
- [安全策略](../SECURITY.md)
- [第三方许可](../THIRD_PARTY_LICENSES.md)
- [变更记录](../CHANGELOG.md)

## 版本与兼容性

当前稳定版为 1.0.0。文档列出的公开 API、CLI 与 artifact 契约是 1.x 兼容面。
内部模块和历史 checkpoint 不作为跨版本分发契约。模型发布使用 safetensors artifact。

## 历史开发记录

以下内容保留原始时间点和判断，便于追溯为什么 1.0 采用当前架构：

- DATA_PIPELINE_REFACTOR_PLAN.md：数据管线重构计划与实施背景。
- development/LATEST_ONLY_ARCHITECTURE.md：latest-only 架构 ADR。
- development/LATEST_ONLY_PROGRESS.md：Stage 1–12 实施记录。
- development/SER_LIB_LATEST_ONLY_REFACTOR_PLAN.md：完整重构计划。
- development/core-boundary-refactor/：核心边界 12 阶段方案。
- development/review/：多轮严格审查、复现证据和修复复验。

历史文档中的“未完成”“尚未修复”“当前版本”等文字只对文档注明的 commit 基线有效。
1.0 当前状态以代码、当前规范文档和 main CI 为准。
