# Stage 01 — 重构安全基线与契约锁定

## 目标

在任何架构迁移前建立可回归、可比较的行为基线。该阶段不主动改变正式架构，不删除旧入口，只增加测试、固定样本和审计快照，确保后续每次重构都有明确回退点。

## 基线

- 源码基线：`main@7018e05dbbfd5e40207ac8ccfd886cbaedbebfe6`
- 设计依据：`doc/dev/SER_LIB_CORE_BOUNDARY_AUDIT.md`
- 证据依据：`doc/dev/SER_LIB_CORE_BOUNDARY_EVIDENCE.md`

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

## 实施记录（2026-09-09）

本阶段已完成代码侧基线锁定；**不在文档中预判 CI 为通过**，最终验证必须以本阶段 exact HEAD 的实际检查结果为准。

新增内容：

- `tests/fixtures/pre_refactor_contract_snapshot.json`
  - 固定 `ser_lib`、`core`、`data`、`engine`、`artifacts`、`inference`、`models`、`services` 的完整 `__all__` 顺序快照；
  - 固定当前持久化版本号、coverage 门槛和 CI OS/Python matrix。
- `tests/test_pre_refactor_contracts.py`
  - 校验完整 public API 快照；
  - 校验 event/dataset/revision/run/evaluation/checkpoint/artifact 版本；
  - 校验 artifact v1 继续使用真实 legacy PyTorch defaults，不伪升级为 v2；
  - 校验 `AudioSettings` 默认值、round-trip、unknown field 拒绝和 config-relative path；
  - 校验当前 coverage/CI 基线；
  - 校验 `hf_audio_classifier` 注册 ID、optional 状态和 exact state_dict keys。

现有测试继续承担并已被本阶段确认作为后续回归门禁：

- `tests/test_training_lineage.py`：Service lineage → checkpoint / artifact，以及 resume lineage；
- `tests/test_training_result.py`：当前 `Trainer.fit()` 返回 `list[EpochResult]`，`last_result` 保存 completed/early-stopped/cancelled/failed 终态；
- `tests/test_checkpoint_resume.py`：checkpoint v1/v2 读取与 resume；
- `tests/test_artifacts.py`：artifact v1 显式信任门禁与 v2 safetensors/hash；
- `tests/test_schema_migrations.py`：只读迁移、缺链、future version、坏结果；
- evaluation / batch / streaming 现有测试继续锁定结果格式、取消和流式行为。

本阶段没有修改 `ser_lib/` 生产实现，也没有新增 `foundation/`、`config/` 或删除任何旧 API。
