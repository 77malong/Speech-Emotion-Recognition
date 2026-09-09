# Stage 01 — 重构安全基线与契约锁定

## 目标

在任何架构迁移前建立可回归、可比较的行为基线。该阶段不主动改变正式架构，不删除旧入口，只增加测试、固定样本和审计快照，确保后续每次重构都有明确回退点。

## 基线

- 源码基线：`main@7018e05dbbfd5e40207ac8ccfd886cbaedbebfe6`
- 设计依据：`docs/development/SER_LIB_CORE_BOUNDARY_AUDIT.md`
- 证据依据：`docs/development/SER_LIB_CORE_BOUNDARY_EVIDENCE.md`

## 修改范围

重点检查并必要时补充：

- `tests/test_public_api.py`
- config / schema migration 相关测试
- checkpoint / artifact fixture
- Trainer / Evaluation / Inference 行为测试
- Service 当前行为测试
- HF adapter 当前 fake 测试
- coverage policy 与 CI smoke

## 具体任务

1. 记录当前 `ser_lib` 根包、子包 `__all__` 与关键公开符号。
2. 固定配置 round-trip、unknown-field、路径解析和 schema version 行为。
3. 固定 dataset manifest、revision、checkpoint v1/v2、artifact v1/v2 的读取兼容 fixture。
4. 固定 `TrainingService` 当前隐藏行为：lineage、predictor 构造、artifact provenance、结果落盘。
5. 固定 `Trainer.fit()` 当前返回值、`last_result`、异常传播、取消和 callback 行为。
6. 固定 evaluation report / prediction JSONL、batch inference、streaming 的关键行为。
7. 固定 `hf_audio_classifier` 注册 ID、当前 state_dict key、artifact rebuild 语义。
8. 记录当前 CI 配置与 coverage 门槛，不把“配置存在”误写成“当前 commit 已全绿”。
9. 所有后续阶段必须先通过本阶段新增/固化的回归测试，再允许删除旧代码。

## 非目标

- 不创建 `foundation/` 或 `config/`。
- 不移动生产代码。
- 不删除 `core/`、`services/`、Page/View/Detail。
- 不修改持久化字段、注册 ID 或 error code。

## 验收标准

- 可清晰列出重构前的公开 API、持久化格式和关键运行行为。
- 关键 fixture 可在 CPU、无网络环境下执行。
- 新增测试能覆盖文档列出的最高风险：lineage 丢失、state_dict 前缀变化、processor 不一致、旧格式失效。
- 阶段提交中不包含正式架构迁移。

## 风险

最大的风险是把当前静态审计误当成运行通过证据。测试结果必须以本阶段真实执行为准。

## 建议提交

`test(refactor): lock pre-refactor SER-lib behavior`
