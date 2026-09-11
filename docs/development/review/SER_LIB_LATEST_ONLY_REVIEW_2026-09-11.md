# latest-only 完成版严格审查（2026-09-11）

## 修复复验（基于 2667803 的工作区修改）

以下原始审查正文保留 `2e4839a` 的发现，不代表修复后的现状。LO-01 至 LO-05 已修复，并由 `tests/test_latest_only_review_fixes.py` 覆盖：

- LO-01：loss 包装器透传归约分母，训练事件及进度使用同一累计加权均值；验证结果不再随 batch 划分改变。
- LO-02：跨目录保存时原子复制最佳 checkpoint，再写入相对引用；测试移除原目录中的 checkpoint 后再次恢复和训练成功。
- LO-03：导出前校验 manifest、配置与训练 lineage 的标签，以及音频、表示、变换和 batching 配置；同时修改配置和 manifest 的标签也不能绕过训练标签检查。缺少 lineage 的 checkpoint 会明确拒绝导出，避免无法验证的静默重标注。需要主动构建 artifact 的低层调用方仍可使用 export_model_artifact，自行负责语义正确性。
- LO-04：全新 run 覆盖历史；续训只合并归属一致的已有历史，不同 run 或无法确认归属的目录被拒绝。原有同 run 续训测试继续通过。
- LO-05：在独立随机数生成器中预验证 RNG 状态，发生非法 RNG 错误时模型和全局随机状态保持不变。此修复不宣称任意自定义 optimizer/scheduler 的加载异常都具备事务回滚能力。

最终验证：**498 passed**；Ruff 通过；mypy 的 **109 个源文件**通过。唯一警告仍是既有 GradScaler 弃用提示。本轮未重新发布安装包。

`scripts/audit_latest_only_review.py` 仍作为原审查基线的缺陷探针保留，其成功条件是复现旧 bug；修复后请运行上述回归测试，不应把历史探针的断言失败视为新的回归。

## 原始审查

审查基线：`codex/ser-lib-latest-only`，`2e4839a`。已获取远程引用，本地与远程一致。范围为当前实现及训练、评估、续训、导出之间的组合路径；发现项不全部是本次重构新引入的问题。历史报告不追溯改写，也不把已删除 API 的历史探针失效算作当前缺陷。

**结论：结构收敛已经完成，但不能据 CI 全绿认定功能完善或验收通过。当前确认 3 项 P1、2 项 P2。前三项分别影响选模指标、连续恢复和模型输出的语义，建议修复后再验收。**

## LO-01 · P1：Trainer 包装 loss 后丢失评估归约协议

- 位置：`ser_lib/engine/training/accumulation.py:71`、`ser_lib/engine/training/trainer.py:850`、`ser_lib/engine/evaluator.py:189`。
- 条件：给 Trainer 显式传入带类别权重的 ClassificationLoss，再通过 fit 执行验证。同一批样本改变验证 batch 划分。
- 复现：固定 logits 为 `[4, 0]`，标签为 `[0, 1]`，类别权重为 `[1, 9]`，学习率为 0 以排除训练更新。一个 batch 的 validation loss 为 **3.618150**；拆为两个单样本 batch 后为 **2.018150**，而训练结果中的正确加权 loss 仍为 **3.618150**。
- 原因：`_AccumulationAwareLoss` 在 forward 内使用底层 denominator，却没有向 evaluator 暴露 `reduction_denominator`。fit 传入包装对象后，评估器退回按样本数归约。
- 影响：验证 loss 随 batch size 改变，依赖此指标的最佳 checkpoint、调度和早停可能产生不同决策。同一探针还确认训练 loss 事件为 2.018150，与返回的训练 loss 3.618150 不一致；事件路径也未统一归约。
- 修复要求：让训练包装、评估和事件使用一致的归约契约；补充经 Trainer.fit 的组合测试，断言不同划分的验证结果及训练事件一致。仅测试 evaluator 接收未包装 loss 不足以覆盖此问题。

## LO-02 · P1：更换 checkpoint 目录续训后生成悬空 best 引用

- 位置：`ser_lib/engine/training/trainer.py:657–659`、`:1114–1126`。
- 条件：从 source/last.pt 恢复，后续 checkpoint 写入 destination；续训未刷新最佳分数。
- 复现：第一次恢复成功，source/best.pt 仍存在；destination/last.pt 保存的 best_checkpoint 仅为 `best.pt`，但 destination/best.pt 不存在。再次从 destination/last.pt 恢复时抛出“checkpoint 引用的 best artifact 不存在”。
- 原因：保存时无条件取旧最佳路径的文件名，加载时则相对新 checkpoint 所在目录解析。首次恢复允许更换目录，却没有迁移关联文件。
- 影响：本次训练看似正常结束，产物却无法支持下一次恢复；只测一次 resume 会漏检。
- 修复要求：明确关联文件的可移植性，在保存前保证新目录中的引用真实有效，或使用经过验证的引用策略。补充换目录且不刷新 best 的连续两次恢复测试。

## LO-03 · P1：导出允许悄悄交换已训练类别的含义

- 位置：`ser_lib/cli/workflows.py:153–161`。
- 条件：训练完成后，将导出配置中的两个标签对调，类别数和模型结构保持不变。
- 复现：checkpoint 的训练配置为 `0=neutral, 1=happy`；导出配置改为 `0=happy, 1=neutral`。export_checkpoint_artifact 成功，生成的 artifact 也可加载，标签确实变成相反映射。
- 原因：加载 checkpoint 未核对导出配置与训练 lineage 的标签语义，随后优先使用当前配置标签。模型结构和类别数检查无法发现这种错误。
- 影响：权重的分类头没有变，输出标签却反转，得到可正常加载但含义错误的推理产物。
- 修复要求：导出前核对 checkpoint、manifest 和导出配置的标签映射；有意转换应采用明确接口和规则。补充类别数量相同、语义顺序不同的拒绝测试。预处理参数也应按同一原则检查，但本报告实测证据仅覆盖标签交换。

## LO-04 · P2：复用输出目录进行全新训练会混入旧 run 的历史

- 位置：`ser_lib/engine/experiment.py:304–324`、`:440`。
- 条件：同一输出目录先完成 2 epoch，再不指定 resume，执行新的 1 epoch 训练。
- 复现：两个 run_id 不同，新 run.json 的 epochs_completed 为 1，metrics.jsonl 只有 1 行，但 history.json 仍含 epoch `[1, 2]`。
- 原因：history 写入无条件读取并按 epoch 合并已有文件，没有区分全新 run 与同一 run 的续训。
- 影响：新实验混入旧实验数据，历史曲线和实际训练记录矛盾。
- 修复要求：只有明确属于同一 run 的恢复才合并历史；新训练应重置历史或拒绝非空输出目录。分别测试同 run 恢复保留历史、不同 run 不继承历史。

## LO-05 · P2：非法 RNG 状态导致 checkpoint 加载失败后模型已经被修改

- 位置：`ser_lib/engine/checkpoint.py:147–153`、`:178–186`。
- 条件：当前格式 checkpoint 的 numpy RNG 字段内容不合法，其余内容有效。
- 复现：把该字段替换成字符串 `not a numpy state`，加载抛出 `TypeError: state must be a dict or a tuple.`；但目标模型的参数已经被 checkpoint 参数覆盖。
- 原因：前置校验只检查 RNG 字段名，真正的状态校验发生在模型和其他组件加载之后。
- 影响：捕获恢复异常后继续使用原对象，会得到部分恢复的状态，失败操作不再保持原对象可预测。
- 修复要求：应用状态前验证 RNG 值，或在失败时回滚；使用独立随机数对象验证，避免校验本身修改全局 RNG。补充失败加载前后模型及随机状态一致的测试。

## 验证证据与范围

- 完整测试：**486 passed**，1 项 GradScaler 弃用警告。
- Ruff 检查通过；mypy 检查 **109 个源文件**通过。
- sdist 和 wheel 构建成功；将 wheel 安装到独立安装目录后，确认导入来自该目录，CPU 单 epoch 冒烟测试通过（8 样本、2 batch、2 次 optimizer step）。该环境复用本机依赖，不代表全新操作系统安装验证。
- 新探针：`scripts/audit_latest_only_review.py`，四组探针确认上述五项，输出无 probe_error。探针在临时目录生成音频及训练文件，不修改生产实现。运行成功表示缺陷复现成功，不表示库通过验收。

复现命令（仓库根目录、已安装项目依赖）：

```powershell
python -m scripts.audit_latest_only_review
```

训练/评估的数值契约、checkpoint 的文件关联、导出的语义一致性是当前最薄弱的边界。基础测试与打包可用性已有证据，但不能抵消上述确定性错误。本次不是对所有模型、平台、设备和外部依赖组合的穷尽证明，也不声称已经找出所有 bug。
