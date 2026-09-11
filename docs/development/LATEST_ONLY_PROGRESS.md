# latest-only 实施记录

基线：`86f0212`。分支：`codex/ser-lib-latest-only`。日期：2026-09-11。

## Stage 1：架构决策

已记录边界、破坏性变更、保留的回归保护和原计划 Stage 3/4 的依赖关系。用户原计划保存于同目录，未改写其中要求。

基线检查结果：

- 全量 pytest：511 passed，1 个既有 GradScaler 弃用警告，实际执行 CUDA 测试。
- `ruff check .`：通过。
- `mypy ser_lib`：46 errors / 11 files，检查 111 个源文件。这是开始改动前的结果，不是本轮引入，也没有通过修改检查参数将其隐藏。
- build：sdist、wheel 通过。
- wheel smoke：装入独立 venv 的 site-packages，移除 editable finder，确认从安装目录导入；CPU 单 epoch、8 samples、2 optimizer steps 通过。该 venv 复用本机依赖，不等同于干净机器依赖安装或跨平台 CI。

日志位于忽略目录 `artifacts/latest-only-*`，不作为唯一交付证据。类型检查基线和最终提交 CI 未通过前，不标记整轮验收完成。

## Stage 2：移除历史 release 兼容测试

已删除 `test_release_compatibility.py`、`test_pre_refactor_contracts.py`、release_compat fixture 和旧公开合同 JSON 快照。seed 与标签语义测试改用临时生成的数据和当前 ExperimentConfig；原合同测试中仍有效的 AudioConfig 往返和 HF state_dict 键结构测试独立保留。测试目录已无对删除 fixture 的引用。

验证：502 passed，1 个既有警告；较基线减少 9 项历史兼容/快照测试。全仓 Ruff、build、安装 wheel 的 CPU smoke、`git diff --check` 通过。mypy 仍为相同的 46 个基线错误，没有新增。该阶段代码变更完成，但类型检查验收尚未关闭。

旧 `scripts/audit_*repros.py` 对应历史 review 基线，部分依赖已经移除的格式/fixture；需要在对应历史提交运行，不能把它们在新分支上的结果用作当前缺陷状态。

## 未完成阶段与下一步

Stage 6～12 尚未完成。当前格式收敛与数据管理功能删除已完成，下一步将 errors/events 归入 foundation。最终提交的跨平台 CI 尚未验收。

本记录中的本机验证均为 Windows/Python 3.10；按 ADR 的验收范围，它不替代 Linux/macOS、Python 3.11/3.12 与两个 Transformers 版本的 CI 结果。

## 验收前置修复：严格类型检查基线

已清除基线 46 个类型错误：显式声明 Tensor buffer 和谱配置类型；Transformer 使用具名配置属性代替动态 setattr；优化器显式传递参数；外部字典经过实际 schema 验证；回调通过 partial 绑定上下文；收紧时间轴、语言默认值和 transform 注册表类型。没有关闭 mypy 规则或添加忽略错误指令。

更新 CI：Ruff 检查全仓；mypy 移除 `--follow-imports=skip`，与计划命令一致。未改动 Python/OS/HF 版本矩阵。

验证：`mypy ser_lib` 为 111 source files 无错误；全仓 Ruff 通过；502 passed，1 个既有 GradScaler 警告；sdist/wheel 构建通过；安装 wheel 后 CPU 单 epoch smoke 通过（8 samples、2 optimizer steps）。Stage 1/2 记录保留当时基线结果，当前本机类型门禁已恢复为通过。

## Stage 3/4：删除迁移框架并收敛当前格式

按照 ADR 中的依赖说明合并为一个可运行提交：四个 migrations 模块和迁移专属测试删除；配置、dataset、artifact、checkpoint、run/evaluation、事件及修订记录删除格式版本字段。没有留下占位 migration、恒等转换或旧版加载分支。

配置文件先验证当前模型，再按配置所在目录解析路径；dataset 加入严格顶层模型，拒绝未知字段、错误类型及缺少 splits。示例 YAML 和仍保留的测试 fixture 已同步。

artifact 固定 weights.safetensors，移除 weights_format、pickle 开关及 library_version 兼容比较；必需侧文件仍检查内容一致性及摘要覆盖。checkpoint 保留可信本地 Torch 序列化，增加必需字段、类型和 RNG 键集校验，校验发生在模型状态加载之前；library_version 只记录来源。缓存采用内部 `_CACHE_FORMAT_ID`，不是公共版本协议。

新增 20 个当前格式用例，覆盖旧字段拒绝、缺字段、错误类型、摘要文件缺失、固定权重文件名、来源版本不影响加载，以及训练/评估记录的端到端输出。原有数值、恢复、HF、导出预检和原子导入测试保留。

验证：509 passed，1 个既有 GradScaler 警告；后续 checkpoint 类型放宽为支持 Torch 模块 extra_state 后，34 项相关测试通过；全仓 Ruff 通过；严格 mypy 检查 107 个文件通过；sdist/wheel 构建与安装后的 CPU smoke 通过，确认安装包中四个 migrations 模块不存在。生产代码格式版本/migration/pickle 开关搜索无命中。历史 review 和历史探针原文保留。

## Stage 5：删除管理功能与配置转发入口

按计划删除 `data/config.py`、`data/editor.py`、`data/history.py`、`data/query.py` 四个模块，以及仅服务于它们的 `DatasetEditError`、`DatasetEditConflictError`、`DatasetTransactionError` 异常和四个测试文件（共 20 个用例）。

配置引用收敛到 `ser_lib.config`：调用方改用 `AudioConfig`/`CacheConfig` 正式名称，删除 `AudioSettings`/`CacheSettings` 别名及 `data.config` 转发模块。`DatasetManifest.iter_records` 同时移除，记录访问统一走 `get_records(resolved_records)`；`docs/API_REFERENCE.md` 的推荐入口与 Dataset records 章节同步更新，不再引用已删除的 `iter_records`。历史 review 文档与 `scripts/audit_*repros.py` 探针按 ADR 保留原文。

验证：488 passed（较 509 减少的 21 项来自被删除的管理 API 用例），1 个既有 GradScaler 警告；全仓 Ruff 通过；mypy 检查 103 个文件无错误；sdist/wheel 构建通过；wheel 装入独立 venv 后确认从 site-packages 导入，`ONE_EPOCH_SMOKE_TEST=PASS`（8 samples、2 batches、2 optimizer steps）；构建产物中四个已删除模块均不存在，migrations 无残留；`git diff --check` 无命中。

本机环境补充：`psutil` 是 `pyproject.toml` 已声明的依赖，但本机 conda 环境缺失，导致 `ser_lib.runtime` 导入失败并使收集阶段报错。已按声明的约束安装 `psutil>=5.9` 后运行上述验证；该问题属于本机环境缺口，不是本轮改动引入。


## Stage 6：errors/events 统一归入 foundation

将异常体系从单文件与 data 领域兼容入口收敛为 `foundation/errors/` 包：基础异常、配置异常、数据异常与兼容性异常按职责拆分，删除 `foundation/errors.py` 与 `data/errors.py`。生产代码与测试统一从 `ser_lib.foundation.errors` 导入，不保留旧路径转发模块。

将事件体系收敛为 `foundation/events/` 包：共享 context、序列号、JSON-safe helper 与 cancellation 协议位于 `base.py`；进度/指标/日志/生命周期事件位于 `lifecycle.py`；checkpoint 与 prediction 事件分别归入 `training.py` 与 `inference.py`。删除 `foundation/events.py`、`engine/events.py`、`inference/events.py`，所有事件继续共享同一个全局 sequence 计数器。

边界测试同步递归检查 foundation 子包，确认 foundation 不反向依赖 data/models/engine/inference/artifacts/cli，并显式确认旧 errors/events 文件不存在。Stage 6 的实际测试与 CI 结果以该提交对应的 GitHub Actions run 为准，不在提交前预写验收结论。


## Stage 7：Trainer 单实现收敛

删除 `ser_lib/engine/_trainer_core.py` 与 `ser_lib/engine/trainer.py`，新增 `ser_lib/engine/training/`。训练结果类型迁入 `results.py`，gradient accumulation 状态与 loss wrapper 迁入 `accumulation.py`，训练生命周期、验证、checkpoint、resume、lineage、sampling RNG、AMP step accounting 全部合并到唯一的 `training/trainer.py::Trainer`。

当前结构不再存在 `Trainer(_TrainerCore)` 双层行为链；生产代码、脚本和测试统一使用 `ser_lib.engine.training` 或 `ser_lib.engine` 公共入口。Stage 7 的 CI 验收由该提交触发的 GitHub Actions 结果确认。


## Stage 8：删除 engine/config.py 并归位实验职责

删除 `ser_lib/engine/config.py`。配置文件加载职责迁入 `ser_lib/config/experiment.py`，`load_experiment_config` 继续严格校验当前结构，并按配置文件目录解析 output、checkpoint、manifest 与 cache 相对路径。

运行时组件构建统一归入 `ser_lib/engine/experiment.py`：原有内部 `_DataComponents` 收敛为正式 `ExperimentComponents`，`build_experiment_components` 保留公开默认 `train=True` 行为，并继续执行 seed、模型参数规范化、pipeline 构建与静态 compatibility 预检。engine 公共入口继续转发配置类型，但不再依赖 engine.config。

边界测试显式确认 `engine/config.py` 不存在，并校验 ExperimentConfig、ExperimentComponents 与 build_experiment_components 的唯一规范归属。Stage 8 的 CI 验收由该提交触发的 GitHub Actions 结果确认。


## Stage 9：训练/评估记录命名收敛

将 `engine/runs.py` 重命名为 `engine/training_records.py`，将训练终态类型和读写 API 收敛为 `TrainingRecord`、`write_training_record`、`load_training_record`。训练 lineage 类型同步由 `TrainingRunMetadata` 收敛为 `TrainingMetadata`，构造函数改为 `build_training_metadata`；checkpoint 中现有 `run_metadata` 持久化字段保持不变，不引入格式迁移。

将 `engine/evaluation_runs.py` 重命名为 `engine/evaluation_records.py`，类型和读写 API 收敛为 `EvaluationMetadata`、`EvaluationRecord`、`build_evaluation_metadata`、`write_evaluation_record`、`load_evaluation_record`。训练 history 的 `TrainingHistoryInfo` 同步改为 `TrainingHistory`，删除 Web/DTO 导向注释。显式的 0.2.x `evaluation_record` compatibility property 被移除，统一使用 `run_record`。

本阶段只调整 Python 模块与 API 命名；`run.json`、`evaluation.json` 及 checkpoint 当前磁盘结构保持不变。training/evaluation catalog 暂时保留并迁移到新的 record 类型，其去留留给后续 catalog 审计阶段。


## Runtime / benchmark 边界收敛

按 latest-only 计划将 benchmark helper 从安装包移出：删除 `ser_lib/benchmark.py`，迁移到
`benchmarks/common.py`。benchmark 继续作为仓库级开发/性能回归工具，不再属于
`ser_lib` public API。

`ser_lib/runtime.py` 只保留 `RuntimeDevice`、`RuntimeCapabilities` 与
`get_runtime_capabilities`，删除 RuntimeMetrics、host/process resource polling 及其
辅助实现。同步删除 runtime metrics/host metrics 测试；由于全仓已无其他使用，基础依赖中
移除 `psutil`。wheel smoke 显式验证 `ser_lib.benchmark` 不再随安装包发布。
