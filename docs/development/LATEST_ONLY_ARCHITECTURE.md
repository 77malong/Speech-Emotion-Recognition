# ADR：只维护当前结构的 SER SDK

> **1.0 归档说明（2026-09-13）**：本文是 SER-lib 1.0 形成过程中的历史记录，状态、路径、缺陷与“下一步”只对文中注明的历史基线负责。当前 1.0 规范请从 [文档索引](../README.md) 或仓库 `docs/README.md` 进入；当前发布状态见 `CHANGELOG.md`。原始正文保留用于审计追溯。


日期：2026-09-11。状态：实施中。
开发基线：`86f021218ca00b0f86607a59a338b30aab2869f0`。
实施分支：`codex/ser-lib-latest-only`。
需求来源：用户提供的 `SER_LIB_LATEST_ONLY_REFACTOR_PLAN.md`，保存于同目录。

## 决策

ser-lib 定位为纯 SER 基础 SDK，只维护当前 Python API 和当前持久化结构。此次是有意的破坏性重构，版本号仍保留；`library_version` 只记录来源，不驱动兼容分支。旧配置、旧导入路径和旧产物不再承诺继续加载。

- 删除迁移框架、旧格式分支及兼容转发模块；当前结构严格验证，未知字段和不合法输入拒绝。
- artifact 只保留 safetensors、摘要校验、预处理与 processor 契约及原子导出。
- 保留训练、评估、推理、lineage、manifest fingerprint 和 checkpoint 恢复能力。
- 删除数据编辑、修订、查询管理功能以及进程资源监控；性能工具移入 benchmarks。
- errors/events 统一归入 foundation；Trainer 合并成一个正式实现；持久化记录统一命名。
- 根包的 12 个高层 API 不扩大。当前模型/数据兼容性检查仍保留，它不属于历史版本兼容层。
- 历史 review 保留原基线和事实，不将旧缺陷数量当作新代码状态。

## 实施约束

每个阶段独立提交，记录 pytest、Ruff、mypy、build 与 wheel smoke 的真实结果。已有梯度累积、损失归约、随机状态恢复、padding、分类头重置、频谱、重采样、回调失败、导出预检和导入原子性测试必须保留。

删除兼容 fixture 前，先解除仍有效的 seed/标签语义测试对旧 fixture 的依赖。不能因为 fixture 被删除而一起删除有效回归保护。

原计划 Stage 3 删除迁移框架、Stage 4 改加载入口存在依赖。实施时必须先迁移调用方或将这两个阶段作为同一可运行变更单元，不提交存在悬空导入的中间结构。只有保持可测试的边界才单独提交。

当前基础 API 参数的合法默认值可以保留；latest-only 的“缺字段失败”针对当前格式必需字段，不应机械地把所有可选配置改成必填。缓存 identity 只做内部失效处理，不属于公共版本协议。

## 验收范围

本机 Windows/Python 3.10 验证不替代 Linux/macOS、Python 3.11/3.12 和两个 Transformers 版本的 CI。仅当最终提交对应的远程 CI 全绿，才标记该验收完成；未运行或不可访问时明确记录，不能用旧提交绿灯替代。

实施进度与检查结果记录在 `LATEST_ONLY_PROGRESS.md`。本决策的建立不表示 12 个阶段已经完成。
