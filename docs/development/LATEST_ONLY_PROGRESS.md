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

## 未完成阶段

Stage 2～12 尚未完成；不得从架构决策或新分支推断 latest-only API 已生效。
