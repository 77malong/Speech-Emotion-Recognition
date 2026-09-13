# 跨模块深入审查

> **1.0 归档说明（2026-09-13）**：本文是 SER-lib 1.0 形成过程中的历史记录，状态、路径、缺陷与“下一步”只对文中注明的历史基线负责。当前 1.0 规范请从 [文档索引](../README.md) 或仓库 `docs/README.md` 进入；当前发布状态见 `CHANGELOG.md`。原始正文保留用于审计追溯。


## 2026-09-13 修复复验

DW-01～DW-08 已在基于 `64ff7e2` 的实现中修复。下方原始审查正文保留历史发现，不代表修复后状态。

| 编号 | 修复行为 |
| --- | --- |
| DW-01 | 训练和评估在统计指标、更新参数前拒绝非有限 logits；有限的模型自带 loss 不能绕过检查。 |
| DW-02 | 报告读取 schema 接受并保留 sample/window 的 metric_unit，两个单位均验证实际读写闭环。 |
| DW-03 | 不保留明细时清理旧 predictions.jsonl，记录和返回路径均为 None；显式写入该路径的 JsonlPredictionSink 则保留并记录，避免重复替换已打开的文件。外部 sink 的文件归调用方管理。 |
| DW-04 | 回溯到早于输出目录已有 last_epoch 的 checkpoint 时拒绝覆盖原目录，要求使用新 output_dir；拒绝后原历史和日志不变。新目录中的历史仅记录本次执行段，不伪造之前的 epoch。 |
| DW-05 | 会话保留尚未交付的已完成预测。push 预测失败后用空 chunk 重试，可取回完整前缀；flush 失败可重试 flush，不重复完成重采样。reset/close 明确丢弃队列。 |
| DW-06 | 未分配记录与已有 unassigned split 冲突时，在任何文件写入前报错，原文件不变。 |
| DW-07 | 输出规划包含所有声明 split，零记录 split 写出空 JSONL，读写后声明不丢失。 |
| DW-08 | strict 存储于 Dataset，作为单次 pipeline 调用参数传递；不修改共享 pipeline 的默认设置。 |

新增回归文件 `tests/test_deep_workflow_fixes.py` 共 **16 项测试**。最终完整回归 **529 passed**；Ruff、mypy（109 文件）、git diff --check 通过。唯一警告仍是已有 GradScaler 弃用提示。

流式重试注意：预测异常发生前可能已接收完整 PCM chunk，应按文档用空 chunk 继续处理，不能重复提交相同 PCM；flush 异常后应重试 flush。待交付队列不保证跨进程重启持久化。

原两个 audit 脚本保留为 `64ff7e2` 缺陷探针，断言目标是复现旧 bug；修复验证应运行 `python -m pytest -q tests/test_deep_workflow_fixes.py`。

## 原始审查证据

基线：`64ff7e2`，分支 `codex/ser-lib-latest-only`。本轮仅审查，不修改业务实现。此前 513 passed 属于该基线的完整回归记录，本轮新增独立组合探针，未重复执行全套测试。

**累计确认 8 项尚未修复的问题：2 项 P1、6 项 P2。** 原一轮的 DW-01～DW-05 聚焦实验和推理组合路径；2026-09-13 续查新增 DW-06～DW-08，基线仍为 `64ff7e2`。以下均有实际复现，不把推测计入缺陷数量。

## DW-01 · P1：非有限 logits 可通过训练和评估，产生虚假成功指标

位置：`ser_lib/engine/training/trainer.py:475`、`:491`；`ser_lib/engine/evaluator.py:355–357`。

前提：模型返回 NaN logits，但自带 scalar loss 是有限数值。这适用于允许模型自己提供 loss 的公共接口；ModelOutput 文档明确允许非有限 logits 进入上层，由训练器统一诊断。

探针使用一个 CNNBaseline 子类，返回 `[NaN, NaN]` logits 和参数乘零得到的合法标量 loss。实际结果：

- Trainer.fit 返回 `completed`。
- evaluate 返回 loss=0、accuracy=1.0。
- 预测 confidence 为 NaN。

原因：两条路径都只验证 loss，没有验证 logits。有限的自定义 loss 遮蔽分类输出异常，argmax 对 NaN 输出的行为被当成有效预测并进入统计。普通交叉熵测试通常会因 loss 也为 NaN 而报错，所以无法覆盖该组合。

影响：损坏输出可能被标为训练成功、参与选模并产生看似完美的评估指标。不是“所有模型必然触发”，触发条件是独立的有限 loss 与非有限 logits 同时出现。

建议：在 loss、argmax、softmax 和任何优化器更新之前验证 logits 有限性。补测 NaN、正负 Inf 与有限自定义 loss 的组合，断言不生成成功指标或 checkpoint，不更新参数。

## DW-02 · P2：高层评估生成的 metrics.json 无法由本库报告读取器读取

位置：`ser_lib/engine/experiment.py:359`；`ser_lib/engine/evaluation_reports.py:32`、`:157`。

复现：通过 evaluate_artifact 生成报告，再调用 inspect_evaluation_report 读取同一目录，抛出 Pydantic ValidationError：`metric_unit: Extra inputs are not permitted`。

原因：高层写入器向 metrics.json 添加 metric_unit，读取器的严格 schema 不包含该字段，却禁止额外字段。两端针对不同结构各自通过测试，公共 API 连用就失败。

影响：正常生成的评估报告不能被标准报告检查接口消费，影响结果展示与后续分析。这是当前格式内部不一致，与旧格式迁移无关。

建议：统一读写 schema，保留并验证 sample/window 单位，而非简单忽略字段。补充高层生成 → 标准检查 → 预测迭代的完整测试，并覆盖两种 metric_unit。

## DW-03 · P2：不保留预测明细时，评估记录仍引用旧文件或不存在的文件

位置：`ser_lib/engine/experiment.py:535–546`；`ser_lib/engine/evaluation_records.py:260`。

复现：

1. 在目录内评估 2 个样本并保存明细。
2. 数据改为 1 个样本，再向同目录评估，传 retain_predictions=False。
3. 返回值 predictions_path=None，新评估 sample_count=1，但持久化 record 的 predictions_file 仍为 predictions.jsonl，旧文件未移除，迭代接口仍读出 2 行旧预测。

另在全新目录使用 retain_predictions=False，记录同样引用 predictions.jsonl，但该文件根本不存在。

原因：记录写入采用默认 predictions_file，不跟随实际明细保留策略；复用目录时也没有处理旧明细。

影响：同一次评估的返回值、持久化记录、统计和明细相互矛盾；下游可能把旧预测当作新结果。

建议：明确记录中明细文件的实际来源，不保留且没有本目录 sink 输出时设为 None；复用目录需要清理旧产物或拒绝覆盖。外部 prediction_sink 的路径不可凭空猜测，应按明确契约记录。补测全新目录与已有目录两种情况。

## DW-04 · P2：回溯续训后，历史与日志仍混有未来轮次

位置：`ser_lib/engine/experiment.py:304`、`:442`、`:453`。

复现：先完成 4 epoch，再从 epoch-0001.pt 恢复，目标 epochs=2，复用原输出目录。返回 run.last_epoch=2，但 history.json 仍为 `[1,2,3,4]`，metrics.jsonl 的 epoch 为 `[1,2,3,4,2]`。

原因：同一 run 的历史按 epoch 合并、日志直接追加，没有根据恢复点截断旧分支的未来记录，也没有禁止回溯覆盖同目录。

影响：真正执行到第 2 轮的恢复分支，被显示为包含原第 3、4 轮；曲线和恢复后权重不再对应。区别于已修复的“不同 run 混入”：这里 run_id 完全一致，文件快照也能正确恢复，但实验记录仍错误。

建议：明确回溯语义——拒绝在非最新恢复点复用目录，或者以恢复 epoch 为边界重建历史和日志、为分支建立独立来源记录。补测向前续训、回溯续训和新目录续训，不能只测 last.pt 顺序续训。

## DW-05 · P2：流式批量窗口中途失败，会丢失已完成但尚未返回的预测

位置：`ser_lib/inference/streaming.py:253–259`。

复现：一个 PCM chunk 包含 3 个完整窗口。模拟模型仅在第 2 次预测时发生一次异常。push_pcm 抛出异常，未返回任何结果；修复瞬时故障后用空 chunk 继续处理，返回 sequence `[1,2]`，sequence 0 永久缺失。

原因：_drain 对每个成功窗口立即推进 buffer、consumed 和 sequence，却只在整批处理完成后返回本地 results。后续窗口失败时，已经消费的前缀结果随调用栈丢失。会话仍允许继续 push，但没有补交付机制。

影响：捕获瞬时错误后继续会话，会出现未明确报告的结果缺口；简单重送原 PCM 又可能重复输入和改变时间轴。

建议：设计明确的失败交付契约，例如待交付结果队列、携带已完成结果的异常，或对整次 push 实施完整回滚。若选择失败即终止会话，应明确使会话失效，并提供对已消费结果的处理方式。补测中间窗口失败、重试、平滑状态和时间戳连续性。

## DW-06 · P1：unassigned split 与未分配记录发生冲突，成功写入却丢失数据

位置：`ser_lib/data/manifest.py`，DatasetManifest.write 中对 planned_paths["unassigned"] 的赋值及末尾 write_jsonl(unassigned, ...)。

复现：通过公开 DatasetManifest/ManifestMeta 构造两个合法 AudioRecord：assigned 已归属名为 unassigned 的 split，pending 尚未分配 split。调用 write 成功，再 load，只剩 pending；assigned 被覆盖，没有异常或警告。

原因：已分配记录先按 split 写入 unassigned.jsonl，未分配记录随后使用同一路径再次写入。路径冲突检查按 split 名建立字典，同名的两组来源已被合并成一个键，因此检查不到碰撞。

影响：保存看似成功，却永久丢失已分配记录。unassigned 并未被声明为不可使用的 split 名，公开构造器也接受上述输入。

建议：在任何写入之前处理保留名冲突，可明确拒绝该输入，或合并两组记录并验证 UID；不能让后写入的组覆盖前一组。补充成功写入后记录集合不丢失的测试，以及拒绝输入时磁盘文件不变的测试。

## DW-07 · P2：普通 manifest 读写会丢掉空 split 声明

位置：`ser_lib/data/manifest.py`，DatasetManifest.write 的 by_split 构造及 `for split_name in by_split` 路径规划。

复现：创建可正常加载的 dataset.yaml，声明 train 与 val；train 有一条记录，val.jsonl 为空。执行 load → write → load，不作任何数据修改，声明的 splits 从 `[train,val]` 变成 `[train]`。

原因：write 只根据已有记录推导 split 列表，未保留 meta.splits 中零记录的项。

影响：保存改变了数据集结构。高层训练根据 val 声明决定是否构建验证过程：原先空验证集应明确失败，声明消失后会绕过该检查并成为不带验证的训练。该影响来自现有分支条件；探针直接验证的是 split 声明丢失。

建议：以元信息中声明的 split 为基础规划输出，并为零记录 split 写入空 JSONL。若选择禁止空 split，应在加载时明确拒绝，而不是在保存时静默移除。

## DW-08 · P2：共享 pipeline 的 Dataset 互相修改严格校验设置

位置：`ser_lib/data/dataset.py:52`、`:60`。

复现：用同一 SamplePipeline 构造 strict=True 的 Dataset A。探针表示组件声明 float32，却返回 float64；A 首次读取正确抛出 RepresentationError。随后仅构造共享该 pipeline 的 Dataset B，设 strict=False，再读取 A，同样的非法 float64 被成功返回。

原因：SERDataset 构造器直接设置共享对象的 pipeline.validate_contract，strict 实际成为 pipeline 的可变全局属性，而不是 Dataset 实例的独立设置。

影响：创建另一个 Dataset 就能改变已有 Dataset 的行为，结果依赖对象构造顺序。开发或校验数据集原本启用的契约检查可能在不知情时被关闭；反方向也会意外打开检查。

建议：让校验策略归属 Dataset 或单次 pipeline 调用，不修改调用方传入的共享组件；若显式禁止共享，应在接口中说明并检测。补测两个 Dataset 交替读取与两种构造顺序。

## 检查范围与证据

| 范围 | 本轮检查重点 | 结论边界 |
| --- | --- | --- |
| 训练、评估与模型输出 | 自带 loss、非有限输出、指标统计 | DW-01 已复现 |
| 评估产物与记录 | writer/reader schema、明细保留、目录复用 | DW-02、DW-03 已复现 |
| 恢复与实验历史 | 历史恢复点、同 run 日志合并 | DW-04 已复现 |
| 流式推理 | 多窗口交付、异常后继续、状态推进 | DW-05 已复现 |
| 数据及模型实现 | 音频加载、缓存、组合表示、变换、CNN/GRU 输入、批量推理、checkpoint catalog | 已阅读相关路径，本轮未将未复现的怀疑列为缺陷；不等于全面验收 |

复现脚本：`scripts/audit_deep_workflows.py`。四组探针覆盖上述五项，执行成功且断言全部成立；脚本只使用临时目录和自建音频。Ruff 检查通过。

```powershell
python -m scripts.audit_deep_workflows
```

注意：探针的成功条件是复现缺陷。它不是修复后的回归测试。尚未验证所有硬件、模型规模和第三方依赖版本，不能据本报告声称已找到全部 bug。

2026-09-13 续查补充：已阅读 manifest 解析/序列化、数据指纹、Dataset/pipeline 共享状态、变换和 artifact 导出加载相关路径；不把“轻量 fingerprint 不哈希音频”这种明确写入契约的取舍当成新增 bug。新增探针 `scripts/audit_data_boundaries.py` 的三组断言全部成立，Ruff 通过；所有写入都位于临时目录。运行方式为 `python -m scripts.audit_data_boundaries`。本轮未修改业务实现，也未重复全套测试。
