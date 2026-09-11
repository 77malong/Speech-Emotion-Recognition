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

Stage 3～12 尚未完成；不得从前两个阶段推断 latest-only API 已生效。下一步将迁移调用方与当前格式加载器一起收敛，以保持阶段提交可导入、可测试。最终提交的跨平台 CI 尚未验收。

## 验收前置修复：严格类型检查基线

已清除基线 46 个类型错误：显式声明 Tensor buffer 和谱配置类型；Transformer 使用具名配置属性代替动态 setattr；优化器显式传递参数；外部字典经过实际 schema 验证；回调通过 partial 绑定上下文；收紧时间轴、语言默认值和 transform 注册表类型。没有关闭 mypy 规则或添加忽略错误指令。

更新 CI：Ruff 检查全仓；mypy 移除 `--follow-imports=skip`，与计划命令一致。未改动 Python/OS/HF 版本矩阵。

验证：`mypy ser_lib` 为 111 source files 无错误；全仓 Ruff 通过；502 passed，1 个既有 GradScaler 警告；sdist/wheel 构建通过；安装 wheel 后 CPU 单 epoch smoke 通过（8 samples、2 optimizer steps）。Stage 1/2 记录保留当时基线结果，当前本机类型门禁已恢复为通过。
