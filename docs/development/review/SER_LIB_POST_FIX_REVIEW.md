# 修复合并后的追加审查

## 本轮修复复验

基于 `d252a93` 修复 PF-01～PF-03，下面原始发现保留作为历史证据。

- PF-01：最佳模型更新先保存带唯一文件名的快照，再写入 epoch/last 的关联引用；best.pt 仍是便捷入口。回溯到旧 epoch 时使用其自己的快照，不再引用后来覆盖的权重。恢复前检查关联快照的 epoch/run 身份，跨目录续训会复制引用快照。保存事件顺序相应改为 best → epoch → last。
- PF-02：关联文件、训练计数、最佳指标及采样器状态均在应用运行状态前检查；模型、优化器、调度器和 scaler 在加载前保存状态副本，加载异常时恢复这些副本及 RNG。测试确认缺失/错误 best、错误模型尺寸、错误优化器结构不会留下已修改的模型状态。
- PF-03：优化器 applied/attempted/skipped 计数一起持久化和恢复，并检查 attempted = applied + skipped。没有保存过 attempted/skipped 的已有 checkpoint 按可获得的 applied 计数初始化，无法追溯此前未记录的 AMP 跳过次数。
- 继续检查发现的同类遗漏：采样器状态原来在模型恢复后才调用 set_state，非法 tensor 会造成部分恢复；现已用独立 Generator 前置验证并补测。另覆盖 save_best=False 的正常续训路径。

回归入口：`python -m pytest -q tests/test_checkpoint_recovery_boundaries.py`。本轮新增 9 项测试，完整验证 **513 passed**，Ruff 和 mypy（109 文件）通过；仍有既有 GradScaler 弃用警告。原 `audit_post_fix_review.py` 是 `3e4c66a` 的缺陷复现脚本，不应用它的旧缺陷断言判断修复是否成功。

代价和边界：独立最佳快照会增加磁盘占用，不应单独删除仍被历史 checkpoint 引用的快照；状态回滚需要额外内存保存原状态。回滚依赖组件能够重新加载自身有效的 state_dict，自定义组件若连自身原状态也拒绝加载，不属于已验证保证。此次检查不构成所有平台、模型和依赖组合均无 bug 的证明。

## 原始发现

基线：`3e4c66a`，分支 `codex/ser-lib-latest-only`。

本轮先提交本地修复 `6ecc6e7`，发现远程已有六个针对同批问题的提交，随后合并为 `3e4c66a` 并成功推送。合并保留远程更完整的 checkpoint 事件处理、标签及 fingerprint 检查，也保留本地的导出前置校验、预处理一致性及历史归属检查。没有强制推送。

合并后完整测试 **504 passed**，Ruff、mypy（109 文件）通过。以下是后续独立复现的遗留问题，尚未修复；不能用测试全绿替代这些边界的验收。

## PF-01 · P1：历史 checkpoint 的 best 引用随未来训练改变

位置：`ser_lib/engine/training/trainer.py:954`、`:1153`。

训练两个 epoch，并使第 2 个 epoch 的验证 loss 优于第 1 个。恢复 `epoch-0001.pt` 成功，其 `best_epoch=1`，但恢复后的最佳文件指向可变的 `best.pt`，该文件实际保存的是 epoch 2 权重。探针读取文件中的 epoch 确认为 2。

这不是上轮“换目录缺文件”的重复报告：所有关联文件都存在，恢复没有报错，错误在于关联文件的版本与历史 checkpoint 不一致。回溯到历史轮次后，保存、迁移或导出 best 可能使用原历史时点之后的权重，而记录中的最佳指标仍属于历史时点。

建议：历史 checkpoint 引用不可变的最佳 epoch 文件；`best.pt` 可以保留为便捷入口，但不能成为历史恢复的唯一身份标识。恢复时还应验证引用文件的 epoch/run 身份。回归测试应覆盖连续改善后回溯到旧 epoch，断言最佳指标、epoch 与权重来自同一时点。

## PF-02 · P2：恢复失败仍可能留下部分修改状态

位置：`ser_lib/engine/training/trainer.py:1127` 及后续 best 检查；`ser_lib/engine/checkpoint.py:219`。

实测两条路径：

1. 正常训练两轮后移除 `best.pt`，从 last.pt 恢复。API 抛出 FileNotFoundError，但目标模型已经变化，last_completed_epoch 也已从 0 变成 2。
2. 当前格式 checkpoint 中仅将 classifier.bias 改为错误尺寸。load_state_dict 抛出尺寸不匹配异常，但此前兼容的参数已被覆盖。

上轮 LO-05 修复了非法 RNG 的前置检查，这里确认的是其他失败分支仍缺乏状态一致性保证，并非声称原 RNG 修复无效。调用方捕获异常后继续使用原对象，可能在不知情的情况下使用混合状态。

建议：把 best 引用、采样器状态及 Trainer 元数据等校验前移；预检模型 state_dict 的键和形状。对于无法完整预检的组件，明确实施回滚或隔离加载，不能将调用 load_state_dict 本身视为无副作用校验。补测异常前后模型、优化器、Trainer 和 RNG 状态保持一致。

## PF-03 · P3：续训后的优化器计数口径不一致

位置：`ser_lib/engine/training/trainer.py:202`、`:1160–1164`。

从完成一次优化器更新的 checkpoint 恢复，optimizer_step 为 1，但 optimizer_step_attempted 和 optimizer_step_skipped 均为 0。成功次数从 checkpoint 恢复，尝试与跳过次数却保留新对象的初始值。

当前证据是可观测计数不一致，没有证据表明它直接改变梯度更新。建议统一为累计计数并一起保存恢复，或明确区分本段与全程统计；测试应覆盖恢复前后 `attempted = applied + skipped`，包括 AMP 跳过更新的场景。

## 复现及范围

在具备项目依赖的环境，从仓库根目录运行：

```powershell
python -m scripts.audit_post_fix_review
```

探针只在临时目录创建模型、训练文件并移除自建 best.pt。退出成功代表上述缺陷全部复现，不代表项目验收通过。原始输出的关键值：历史 best 元数据为 1、引用文件为 2；恢复计数为 applied=1/attempted=0/skipped=0；两种失败加载均 model_changed=true。

本轮重点检查合并实现及训练持久化边界，并浏览批量推理和模型输入处理；没有对所有数据集、模型、硬件及第三方依赖组合作穷尽验证。没有把未复现的怀疑计入缺陷数量。
