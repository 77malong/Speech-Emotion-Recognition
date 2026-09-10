# ser-lib 第二轮严格审查：修复闭环仍不完整

> 更新：本文件新增 R3-01～R3-18 扩展审查（同一 `0d4bd75` 基线），详见文末。与 R2 的 11 项合计记录 29 项不同根因的当前缺陷。综合判断已收紧为 5/10；下面原第二轮的 6/10 保留为审查历史，最新逐模块评分见[扩展复评](SER_LIB_STRICT_REVIEW_2026-09-10.md)。所有审查文档集中在 `docs/development/review`。

日期：2026-09-10。基线：`refactor/ser-lib-core-boundary-12-stage@0d4bd75`。

本地由 `93991c4` fast-forward 到最新远端。相对第一轮被审代码 `5184155`，新增了一批修复；本轮检查当前实现，不把已修复的旧问题继续当作缺陷，也不把这次才发现的历史问题一律说成新回归。

## 审查结论

**当前仍不应宣称“很完善”或“严格审查整改完成”。可以认可修复投入，不能认可可靠性已经闭环。**

最严重的问题不是缺少多少模型，而是：优化器没有更新却报告更新成功；同一评估数据换个 batch size 就得到不同 loss；真实续训配置与记录不一致；用户明确要求重置的分类头没有重置。这些都直接损害实验结果和制品的可信度。

综合仍约 **6/10**，不因提交数和测试数增加而自动加分。架构组织约 8/10，数值与实验状态可靠性约 5/10。评分是审计判断，不是统计量。本轮没有证据证明该库在真实语料上达到何种准确率、泛化能力或生产 SLA。

## 方法和验证范围

- 拉取最新远端后审阅全部新增 diff，重新走查训练、评估、数据批处理、音频预处理、HF、checkpoint/lineage、artifact 和发布测试的相关调用链。当前库有 110 个 Python 源文件；这里的逐模块评价不是声称对每一行作形式化验证。
- 从 `git archive HEAD` 得到干净源码，在测试进程移除指向旧工作区的 editable finder，避免上一轮残留 namespace 干扰。复用本机依赖：Windows、Python 3.10.16、Torch 2.7.1+cu126、Transformers 5.16.1。
- **现有测试：420 passed，1 warning。** 包含本机实际执行的 CUDA AMP 测试；警告为旧 GradScaler API 的弃用提示。
- Ruff、mypy `--follow-imports=skip ser_lib`、pip check 通过；CPU 单 epoch smoke 通过；sdist/wheel 构建通过。
- 干净源码行覆盖率：foundation 92.05%、config 90.85%、artifacts 89.71%、engine 91.95%、inference 90.67%、models 82.37%、data 77.17%、cli 84.70%。全部达到仓库门槛，仍然漏掉下列问题。
- 独立探针：`scripts/audit_round2_repros.py`。运行 `python -m scripts.audit_round2_repros`，HF 仅创建 tiny 本地模型，不下载权重；数据使用临时合成 WAV。临时样本跨 split 使用不同 UID，避免把合法的 UID 重复检查误说成无效。
- 本轮没有重跑所有 OS/Python/依赖组合、长时间 CUDA 训练或干净 wheel 安装；构建成功不代表这些都已验证。AMP 首步复现不能被扩大为“AMP 永远不会学习”。

## 第一轮问题的复核状态

| 第一轮问题 | 本轮判断 |
|---|---|
| 梯度累积尾组与不同 microbatch 大小 | FP32 主要场景修好；新增 AMP 归一化顺序问题和测试假阳性，不能关闭整个问题 |
| 模型初始化前未设 seed | experiment builder 已提前设 Python/NumPy/Torch seed，主入口修好；NumPy checkpoint 恢复仍缺失 |
| F0 平滑单位错误 | 改为 3 帧，新增短输入、静音和正弦测试；原单位错误已修 |
| shimmer/HNR 固定为零 | 公共配置已拒绝该选项，是正确撤回虚假能力；不等于真实实现了这些特征 |
| CNN padding | dynamic mask 路径修好；fixed/sliding 不产生 mask，仍绕过修复 |
| 流式重采样混叠 | 已换为带限重采样并有离线数值一致性测试；不再保留旧混叠指控。但完整 AudioLoader 预处理仍不一致 |
| 高层标签语义未比较 | train/evaluate_artifact 已新增标签语义检查；HF 分类头重置属于另一个尚未修好的语义问题 |
| weighted sampler RNG | 已绑定并存入 checkpoint，已有恢复测试；不能外推为所有 RNG/数据状态均完整恢复 |
| DatasetEditor.update_record 半更新 | 已先验证后修改，原复现修好；多写者/多文件崩溃一致性仍是能力限制 |
| 返回伪造 checkpoint 路径 | 高层改为用 TrainingResult，原拼接问题修好；恢复已有 best checkpoint 的结果仍丢引用 |
| 不可执行 legacy fixture | 改成有效配置并实际执行构建；比仅解析明显改善，但历史权重 golden 证据仍不充分 |

## 必须优先处理的缺陷

### R2-01 / P1：AMP 测试“两个都没更新，所以相等”

**性质：本轮修复引入的数值回归，已用 CUDA 独立复现。**

代码：`ser_lib/engine/trainer.py:52`、`:194`、`:212`；相关测试为 `tests/test_gradient_accumulation_numerics.py:test_amp_tail_accumulation_matches_large_batch`。

新的 loss wrapper 把反向梯度按有效分母放大，等所有反向结束、GradScaler.unscale_ 后才除回分母。这样梯度在 FP16 反向路径里先经历更大的量级；后面的除法救不了已经发生的 overflow。即使 accumulation_steps=1，也走该机制。

同一 seed=17、同一 Linear 初值、同一 5 条样本、SGD lr=0.1，首步结果：

| 路径 | 参数更新范数 | GradScaler scale | 库报告 optimizer_steps |
|---|---:|---:|---:|
| 当前 Trainer FP32 | 0.07403295 | 不适用 | 1 |
| 当前 Trainer AMP，整批 | **0** | 65536→32768 | **1** |
| 当前 Trainer AMP，拆批累积 | **0** | 65536→32768 | **1** |
| 原生 PyTorch AMP，同输入同初值 | 0.07400519 | 65536 不变 | 不适用 |

GradScaler 合法地跳过了溢出 step，但库无条件增加 optimizer_step。这既是放大梯度导致的额外跳步，也是可观测性失真。现有 AMP 测试只比较两种 SER 路径最终权重接近，没有要求权重真的改变、没有对照原生/FP32，因此在这个例子里成为假阳性。

验收：训练首步必须与可信参考发生非零且相近的更新；检测并分别记录 attempted/applied/skipped step；覆盖 batch size、尾组、weighted loss 和 scaler 调整，不要靠放宽 allclose 容差通过。GradScaler 之后可能适应，不能因此忽略首步测试无效和计数错误。

### R2-02 / P1：weighted validation loss 依赖 batch 划分

**性质：历史问题，本轮深入复现；上轮梯度归一化整改没有覆盖指标归约。**

代码：`ser_lib/engine/evaluator.py:334`、`:437`；训练 epoch 的累计 loss 也仍按 sample_count 聚合。

两条样本 logits 都为 `[4,0]`，target 分别 0/1，class_weights=[1,9]：

- 合成一个 batch：loss=**3.618149996**，与直接全量 weighted CE 一致。
- 拆为两个单样本 batch：loss=**2.018149907**。

evaluator 把每批已经按权重质量归约的 loss 再按样本数加权，数学上不能得到全量 weighted CE。相同模型、相同验证样本，仅改变 batch size，就可能影响 val_loss、best checkpoint 选择和 early stopping。新增 reduction_denominator 已用于反向，却没有统一用于验证指标。

验收：损失对象提供可组合的 numerator/denominator；整批、均匀拆批、非均匀拆批、末尾短批输出一致，并明确自定义 loss 的归约协议。

### R2-03 / P1：CNN 的 padding 修复仅修了一条分支

**性质：上一轮缺陷未完整关闭，已通过正式 fixed collator 复现。**

代码：`ser_lib/data/collate.py:178`、`:252`；`ser_lib/models/cnn_models.py:126`。

fixed/sliding collator 返回真实 lengths，却返回 masks={}。CNN 只看 masks，不从 lengths 构造有效位置，因此直接走旧的普通卷积/BatchNorm/mean pooling。

同一 7 帧输入，fixed.max_lengths 从 7 改为 22，eval logits 最大差 **0.03975323**。这是未截断的同一输入，仅改变零填充长度。不能把 dynamic mask 测试通过写成整个 CNN 变长问题已经解决。

验收：CNN 消费 lengths 与 masks 的统一契约，或所有对应 collator 都生成正确 mask；dynamic/fixed/sliding、短样本、尾窗全部覆盖。不要只测试手工构造的带 mask SERBatch。

### R2-04 / P1：HF reset_classifier_head=True 没有重置同尺寸旧分类头

**性质：已用真实本地 tiny HF checkpoint 复现。**

代码：`ser_lib/models/adapters/huggingface.py:151`—`:158`。

原 checkpoint 两个标签 neutral/happy，给分类头写入可辨认的 weight=0.123、bias=[7,-7]。加载时改为 angry/sad 并显式 reset_classifier_head=True，结果：

- config 标签变成 angry/sad；
- 分类头 weight 与原 checkpoint 完全相等；
- bias 仍为 `[7,-7]`。

ignore_mismatched_sizes 只处理尺寸不匹配；标签语义变了但类别数相同，权重就会照常加载。此时 API 的“重置分类头”承诺并没有发生，旧类别输出被直接贴上新标签。现有测试主要验证 from_config 的映射门禁，没有验证带已训练头的真实 from_pretrained 同尺寸改标签。

验收：显式 reset 必须有真正重建/重初始化头的路径；测试同类数换标签、不同类数、保持原头三种情况，并验证 encoder 权重保持、head 权重变化。

### R2-05 / P1：续训实际配置与 lineage 不一致

**性质：历史状态设计问题，允许 runtime-only 配置变化后更容易暴露，已端到端复现。**

代码：`ser_lib/engine/trainer.py:317`，`ser_lib/engine/checkpoint.py` 的签名只覆盖 TrainerConfig。

先训练 1 epoch cross_entropy，再通过正式 train_experiment 从 last.pt 恢复，epochs=2、loss=focal：恢复被接受，真实使用当前创建的 focal loss，但结果 `run.config.loss.type` 仍为 cross_entropy，`run.config.trainer.epochs` 仍为 1。

原因是恢复时用旧 run_metadata 整体替换当前元数据，同时不校验 experiment.loss 等影响算法的字段。要么拒绝不兼容续训，要么定义新的阶段/派生 run 并记录当前配置；两种都可以，**执行新配置却记录旧配置不可以**。同样需要明确数据指纹、预处理、采样配置变化的政策。

验收：只延长 epochs 的合法恢复也要记录新的有效配置；改变 loss/data/sampling 等字段要拒绝或生成明确 lineage；结果、checkpoint、run.json 的配置须与真正执行的配置一致。

### R2-06 / P1：流式路径忽略 normalize_peak

**性质：完整预处理一致性缺口，已通过公开 predictor/streaming API 复现。**

代码：`ser_lib/data/audio.py:244`，`ser_lib/inference/streaming.py:259`—`:265`，`ser_lib/inference/offline.py:72`。

normalize_peak 是 AudioLoader.load 的步骤。streaming 构造 AudioData 后调用 predict_audio，绕过 loader，所以即使同一个 predictor 配置 normalize_peak=True，也没有执行它。

为隔离边界影响，使用同采样率、正好一个窗口、幅值 0.2 的 PCM，以及一个简单幅度分类器：

- predict_file 概率 `[0.88079703,0.11920291]`；
- streaming 概率 `[0.59868765,0.40131232]`。

没有跨窗口平滑、没有重采样差异，此差异就是前处理路径不同。只验证 resampler 与离线 resample 相同，不等于完整离线/在线预处理相同。

验收：定义哪些音频操作是共同预处理；全文件峰值归一化不适合无界流时，要明确窗口策略或拒绝不兼容配置。不能静默忽略已启用设置。

### R2-07 / P1：推理会把 NaN logits 包装成正常分类结果

**性质：历史边界缺口，本轮通过公开 predict_audio 复现。**

代码：`ser_lib/inference/offline.py:_predict_samples/_aggregate`。ModelOutput 明确允许非有限 logits，指望消费方进行诊断；推理消费方没有完成这一步。

自定义模型返回 NaN logits，公开 API 不抛错误，而是返回 label_id=0、confidence=NaN、probabilities=[NaN,NaN]。这不是“模型自然性能差”，而是把无效数值变成了貌似正常的类别结果。batch sink/JSON 下游可能进一步传播无效数据。

验收：在 argmax/softmax 和输出结果前验证数值，提供带 UID 的诊断；单条失败与批处理错误策略明确，不能默认命中第 0 类。

## 状态与制品问题

### R2-08 / P2：成功导出、成功校验，却无法加载自己的 artifact

代码：`ser_lib/artifacts/exporter.py:134`、`:195`；直到 loader.py:328 才做模型/预处理兼容性校验。

CNN feature_dim=16，data_config 使用 n_mels=32，导出成功；verify_model_artifact 也成功；load_model_artifact 报 CompatibilityError。这是有效但互不兼容的两个配置，不是故意构造的损坏文件。

哈希校验只承诺完整性，这一点没错；问题在于 exporter 明明掌握模型和预处理，却接受了必然不可运行的组合。应在写权重前执行静态兼容性检查，并验证导出→验证→加载→推理闭环。

### R2-09 / P2：resume 丢失原有 best checkpoint 引用

代码：`ser_lib/engine/_trainer_core.py:983` 恢复 best_epoch/best_metric，但没有恢复 `_best_checkpoint`；高层现在忠实返回这个缺失值。

复现中第一轮 best.pt 已存在，恢复后未出现新 best，返回 best_epoch=1、best_checkpoint=None。高层不再伪造路径是进步，但“已有最佳制品不可发现”仍是错误。应持久化并验证 best artifact 引用，同时定义迁移目录后的解析规则。

### R2-10 / P2：续训 history.json 覆盖掉此前历史

代码：`ser_lib/engine/experiment.py:238`、`:323`。

上述两阶段实验后 metrics.jsonl 有两行，但 history.json 只有 epoch 2。默认 run_id 被恢复为同一 run，历史文件却只含本次 fit 的结果，两个持久化来源相互矛盾。更极端地，从已完成 epoch 恢复且无新 epoch 时，会把历史写成空数组。

TrainingResult 描述一次 fit 的新增 epoch 可以成立；完整运行目录的 history 是否累计必须另行定义。应合并并去重历史，或显式拆为 attempt/segment 文件，不能静默覆盖。

### R2-11 / P2：NumPy 初始 seed 修了，NumPy RNG 恢复没修

代码：`ser_lib/engine/_seed.py` 与 `ser_lib/engine/checkpoint.py:23`—`:39`。

实验初始化现在设 NumPy seed，但 checkpoint 仍只保存 Python/Torch。保存后预期下一个 NumPy 随机数 0.07630829，扰动 RNG 后 restore_rng=True 得到 0.80342804。用 NumPy 的用户自定义增强/采样无法依靠该接口精确续训。内置 Torch-only 流程不因此全部失效；这是扩展场景的明确恢复缺口。

## 科研可信度和工程限制

这些项目应与上面的已复现 bug 分开处理，不能用缺少某功能就随意定为阻塞缺陷。

- **跨 split 泄漏无门禁。** 复现使用不同 UID、同一 audio_path/speaker 的 train/val，完整 train_experiment 接受并训练。UID 去重不能替代音频重叠、片段重叠、说话人隔离检测。SER 研究应提供严格预检和显式策略；允许 speaker-dependent 实验没有错，缺少提示和可配置检查才是能力不足。
- **指标口径缺少可选政策。** macro_f1 和 UAR 都只对有真实 support 的类别求平均。对于预测出现但真值未出现的类别，macro-F1 的平均范围可能与常用评估口径不同；报告应记录标签集合与缺失类策略，不能只写一个无上下文数字。
- **F0 的 unvoiced 语义有限。** 当前只对精确全零/极短输入明确输出 0，并未展示噪声、清辅音、低信噪比下的可靠有声判定。不能从一个正弦测试推出实际语音 pitch tracking 已充分验证。
- **事务和并发仍有限。** DatasetEditor 的失败更新已修，但多文件替换加事后回滚不具备完整崩溃恢复或多写者串行化；fingerprint 检查存在检查到替换之间的竞争窗口。
- **数据指纹是 manifest 指纹。** 文档已明确音频本体不参与 hash，不能把它解释为训练音频内容不可变的证据。实际文件被原地替换时，实验数据可变而指纹不变。
- **性能证据不足。** 带限重采样每次调用 functional.resample 重建计算路径；小 chunk、多并发、长时间输入和真实模型 p95 尚待验证。微基准的 Python tracemalloc 不代表 Torch/CUDA 原生内存。
- **发布身份仍不清晰。** 同为 0.2.0 的代码已经经历 API 退役、数值语义修复和特征撤回；不能只用版本字符串解释制品差异。需要明确的新发布身份、变更说明和真实历史制品回放。

## 逐模块当前评价

| 模块 | 分数 /10 | 严格评价 |
|---|---:|---|
| foundation / events / diagnostics | 8 | 分层清晰；同步 callback 异常传播、有限数值 JSON 契约和观察者生命周期仍需明确；本轮未证实新的重大实现回归 |
| config / migrations | 7 | 中央 schema 有效；深层可变配置、不同基类行为和运行期/算法配置兼容政策尚未统一，迁移机制不能替代真实旧制品测试 |
| audio / importers / manifest | 7 | 多语料入口、SoundFile、record 契约具备基础；泄漏预检、音频内容版本和大规模载入策略不够完整 |
| acoustic / spectral / transforms | 6 | F0 单位修复和撤回假音质指标应肯定；声学数值验证仍窄，delta/多时间轴能力要准确描述，不能包装成完整研究特征库 |
| collate / dataset / cache | 6.5 | 基础组件可用，但与 CNN 的 lengths/mask 契约未闭环；缓存配额、共享 pipeline 状态、大批滑窗扩张仍有工程欠账 |
| editor / history / profiling / query | 6.5 | 单次失败更新已修；持久化事务、并发一致性和全量扫描限制仍存在 |
| CNN / GRU / Transformer | 6 | CNN dynamic 修复有效、fixed/sliding 未修；GRU mask 仅按数量检查，统一长度语义不足；模型数量不是成熟度证据 |
| Torch adapter | 7 | 显式输入输出和 factory 是合理方案；部署需自行注册 factory；模型 hook 生命周期/多 Trainer 共享模型值得追加测试，未在本轮定为已复现缺陷 |
| HF adapter | 6 | 真 tiny 模型与离线 snapshot 有价值；reset head 实测失败使标签安全承诺打折；已验证家族不等于所有 HF 音频模型可用 |
| Trainer / loss / AMP | 4.5 | FP32 累积修好，但修补层复杂化并漏掉 AMP 实际更新和梯度量级；这是当前最需要收敛和重构的执行核心 |
| checkpoint / experiment / lineage | 5 | sampler RNG、runtime-only 续训放宽有进步；有效配置、NumPy RNG、best 引用、累计历史不一致，不能称完整可复现恢复 |
| evaluator / reports / catalogs | 5.5 | 指标和 sink 丰富；weighted loss 随分批变动，足以影响早停；类别平均口径和窗口级/样本级指标需清晰表达 |
| offline / batch inference | 6 | 管线复用、窗口聚合与 sink 可用；非有限输出未阻断；自定义模型边界不能只靠 ModelOutput shape 校验 |
| streaming inference | 5.5 | 抗混叠方向修正正确；normalize_peak 被绕过，完整前处理一致性未闭环；真实延迟和长期资源尚缺证据 |
| artifacts | 7 | safetensors、哈希、staging 和 processor 可取；导出器允许生成必然不可加载的组合，完整性与可执行性验收未打通 |
| runtime / benchmark | 6.5 | 基本资源观察与同步微基准够用；不能支撑设备间性能可比、CUDA峰值内存或生产实时性承诺 |
| CLI / docs / CI / release | 6.5 | 420 测试、静态检查、构建均有价值；AMP 假阳性表明测试断言不够强；“final remediation”文档措辞超出本轮证据 |

## 应采用的整改标准

1. **先修可信度，不先扩展功能。** R2-01—R2-07 优先；特别是 AMP 实际更新、loss 归约、标签头重置、真实配置记录。
2. **测试必须有独立参照。** 不只比较两个走相同错误实现的结果；参考原生 PyTorch、明确数学公式或保存的 golden 输出，并断言有实际更新、状态和记录一致。
3. **以功能组合为验收单元。** CNN×dynamic/fixed/sliding；loss×weighted/unweighted×AMP；resume×epochs/目录/配置变化；stream×loader 设置；HF×from_config/from_pretrained×同尺寸/异尺寸头。
4. **让执行核心承载算法。** 当前用 loss 包装、forward hook 和子类 optimizer step 绕过旧循环的缩放约定，维护者需要跨两层理解一次更新。应统一可组合损失归约与优化器执行，而不是继续给 wrapper 打补丁。
5. **状态要有唯一可信来源。** 定义 run 与续训阶段，保留完整历史，记录生效配置和真正 checkpoint 引用。每条记录都应可追溯到实际执行，而不是为了序列化方便复制旧 dict。

这轮修复值得保留，但“针对上轮清单逐条加测试”还没有变成“证明完整工作流正确”。当前仍建议定位为开发中的研究 SDK；先把这些可信度问题关掉，再谈完善程度。

## 扩展审查：R3，2026-09-10

基线仍为 `0d4bd75`，没有修改库实现。新增 18 项复现：**P1 五项、P2 十三项**。P1 表示应优先阻止数据损坏或核心功能失效；这里没有根据单机反例推断远程可利用性或全部用户均受影响。探针 `scripts/audit_expanded_repros.py` 的十组执行覆盖多个独立断言；编号按根因分组，不按异常数量膨胀。

复现命令：在仓库根目录运行 `.venv-audit/Scripts/python.exe -m scripts.audit_expanded_repros`。本机输出留在 `artifacts/audit-expanded-repros.log`，该目录被忽略，不是可分发证据；下面记录关键结果，脚本可重新生成。全部文件操作均限于自建临时目录。测试环境沿用本文件前述版本。

### R3-01 · P1 · 默认 spectrogram 根本无法实例化

位置：`ser_lib/data/representations/spectral.py:82`，`SpectrogramRepresentation.__init__`。

默认调用直接抛出 `TypeError: Spectrogram.__init__() got an unexpected keyword argument 'sample_rate'`。构造器把 MelSpectrogram 的 `sample_rate/f_min/f_max` 参数传给普通 Spectrogram。不是特殊数据触发，也不需要开始读取音频。一个公开内置组件连默认构建都失败，说明组件清单和测试清单没有对齐。

验收：所有内置 representation 的默认配置均能构建；线性谱执行结果与直接调用对应 torchaudio 变换对照，不能仅断言 registry 中有名字。

### R3-02 · P2 · power=1 的 LogMel 使用了功率分贝公式

位置：`ser_lib/data/representations/spectral.py:165`。

`LogMelRepresentation(power=1.0)` 得到幅度谱，却固定使用默认 power 类型的 AmplitudeToDB。将同一输入乘二，探针测得平均变化 **3.010300 dB**，幅度分贝应为 **6.020600 dB**。默认 power=2 不受此反例影响；问题针对公开允许的非默认配置，不能夸大为所有 LogMel 都错。

验收：明确支持的 power 与输出单位，对 power=1、2 分别用解析比例验算；对其他允许值明确换算或拒绝。

### R3-03 · P1 · CSV 混合数字和文本标签发生静默合并

位置：`ser_lib/data/importers/csv_importer.py:141`。

两行标签 `1`、`happy`，扫描报告 `ok=True`，映射为 `{'1': 0, 'happy': 1}`，实际两条记录却都是 label=1。构建映射采用字符串枚举，落记录又对数字字符串直接转整数。损害的是训练真值，而非显示文本；后续训练可以正常完成，结果却已经失真。

验收：一轮导入始终使用同一映射；覆盖纯数字、纯文本、混合、显式映射和缺失标签。对每条源记录验证映射一致。

### R3-04 · P1 · 导入失败发生在覆盖原数据之后

位置：`ser_lib/data/importers/_conversion.py:110`，CSV scan 的 UID 验证链。

向已有合法数据集导入两条相同 UID 的 CSV。scan 返回成功；convert 先写 `manifest.jsonl` 和 `dataset.yaml`，随后 load 才检测重复并抛错。实测旧 YAML 已改变，原数据集再加载也报重复 UID。用户得到“导入失败”，却失去了原来可用的数据集。

共享单 manifest 转换流程都应复核；本轮破坏性反例使用 CSV，不能把所有 importer 的全部路径都写成已经实测。JSONL scan 也没有调用带 seen_uids 检查的批量 normalize helper，这是静态扩展线索。

验收：完整验证暂存结果后再提交；任何验证、写入和提交异常都维持旧目录完整，已有目录和新目录分别测试。

### R3-05 · P2 · CSV 相对 root 被应用两遍

位置：`ser_lib/data/importers/csv_importer.py:120` 及 convert 的 root 参数。

输入 `a.wav`、配置 `root='audio'`，存入记录的路径成为 `audio/a.wav`，manifest root 又指向目标目录下的 audio；最终解析为 `relative_dest/audio/audio/a.wav`。即使另行定义 root 应相对哪个目录，这个双重前缀仍然错误。绝对 root 不走同一故障路径。

验收：明确 root 的相对基准；音频路径只应用一次 root。覆盖源目录、目标目录不同，以及绝对/相对 root 的组合。

### R3-06 · P1 · manifest.write 将不同目录同名 split 合并覆盖

位置：`ser_lib/data/manifest.py:309`。

合法数据集 train=`train/items.jsonl`、val=`val/items.jsonl`，load 成功。write 只取文件 basename，两个 split 都改写为 `items.jsonl`，后写者覆盖先写者，重新 load 报跨 split 重复 UID。没有修改记录，仅保存便破坏结构。

验收：保留无冲突相对路径或预分配唯一目标；load→write→load 的记录、split 归属保持不变；发现冲突必须在任何目标写入前拒绝。

### R3-07 · P1 · revision 的恢复目标不受文件摘要约束

位置：`ser_lib/data/history.py:448`，以及 `_combined_digest`。

创建合法 revision，仅将 revision.json 的 `files['split:train'].target_path` 改为同一临时根目录中、不属于数据集的 `unrelated.txt`。不修改快照内容、hash 或 fingerprint。restore **无异常返回**，无关文件从 `KEEP ME` 被覆盖为训练 JSONL，数据集最终指纹校验仍通过。

原因：摘要绑定逻辑文件名和内容，目标路径却直接信任 revision 描述。触发前提是恢复描述被改写或来源不可信；这不是“任意普通恢复必然越界”，也没有验证网络攻击链。但恢复工具不应给外部描述任意文件写权限。

验收：恢复目标由可信数据集声明推导，检查规范化路径、别名和允许集合；任何未授权目标在 staging/写入前拒绝。原始 target_path 不能成为唯一授权依据。

### R3-08 · P2 · Normalize 将合法单采样点转为 NaN

位置：`ser_lib/data/transforms/waveform.py:36`。

输入 `[[0.5]]`，`std()` 默认使用样本修正，自由度不足，输出 NaN，实测 finite=False。后续 AudioData 校验可能再拒绝，但错误数值由变换本身产生。影响极短片段，并非普通长度音频全部失败。

验收：定义单样本归一化语义，通常输出零；覆盖常量、多通道和单采样点，并断言有限性。

### R3-09 · P2 · 特征增强的构建检查与运行范围不一致

位置：`ser_lib/data/transforms/base.py:83`，`validate_feature_transform_layouts`。

声明 FT features 和 D global 两个输入，SpecMasking 构建检查跳过非时序 D，成功；实际 FeatureTransformPipeline 遍历所有 key，对 global 应用频谱掩码，抛出“至少需要两个维度”。文档承诺处理 temporal key，实现没有遵守。

验收：构建和运行使用同一个 key 选择规则；组合谱图与全局向量的流水线完整执行，全局向量按声明保持不变，或在构建期清楚拒绝。

### R3-10 · P2 · DataConfig 文件入口接受未来 schema_version

位置：`ser_lib/config/data.py:109`、`load_data_config`。

输入 schema_version=999 的 YAML，加载成功并保留 999。入口只调用 Pydantic，不经过实验配置入口使用的版本迁移门。未知未来语义被当成当前字段解释，破坏版本兼容策略。

验收：DataConfig 文件入口与实验入口共用版本解析；未来版本拒绝，支持的历史版本迁移，有效当前版本保持不变。

### R3-11 · P2 · 表示契约允许时序输入没有 lengths

位置：`ser_lib/data/types.py:283`。

`RepresentationOutput(inputs={'waveform': ones(8)}, lengths={})` 对 T spec 校验成功。实现只检查已有 length 项，没有检查应有项。错误被放行到后续批处理消费阶段，所谓契约检查不能保证必需数据完整。

验收：每个 temporal key 必须恰有有效长度，非 temporal key 不得有长度；同时测试缺失、额外、零值及不一致。

### R3-12 · P2 · AudioRecord 可写出自己无法读回的记录

位置：`ser_lib/data/types.py:99` 与 `ser_lib/data/manifest.py` 读写函数。

AudioRecord 接受 `label=True`（bool 属于 int），write_jsonl 正常输出，read_jsonl 明确拒绝 bool label。探针同时设置 start_ms=0.5，但读回首先在 label 处失败，因此本条直接实证只证明 bool 不一致；浮点毫秒的类型边界需单独补回归用例。

验收：内存模型和序列化解析共用语义约束；任何正常可构造记录应可往返，或构造时立即拒绝不支持的值。

### R3-13 · P2 · Torch adapter 嵌套状态无法往返

位置：`ser_lib/models/adapters/torch.py:192`。

把包装 Linear 的 adapter 放入 `nn.ModuleDict({'adapter': model})`，用容器自己的 state_dict 调用 load_state_dict，即报 missing `adapter._module.weight/bias`、unexpected `adapter.weight/bias`。自定义导出展平了内部路径，父模块递归加载仍按注册结构寻找键。独立 adapter 的正常保存测试不能覆盖组合模型。

验收：standalone、ModuleDict/Sequential 和训练 checkpoint 的 strict round trip 均成功；如明确不支持嵌套，应在 API 合同中约束，而不是保存成功后加载才失败。

### R3-14 · P2 · started 回调异常遗留模型 eval 状态

位置：`ser_lib/engine/evaluator.py:282`。

模型初始 training=True，evaluation started 回调抛 RuntimeError，evaluate 退出后 training=False。model.eval 和首次 emit 位于恢复状态的 try/finally 之前。回调异常本身可以传播，状态泄漏不应随之发生，尤其影响直接复用该模型的调用者。

验收：模式切换后的全部代码受 finally 保护；分别从 train/eval 两种初态注入 started、progress、completed 回调异常，验证原状态恢复。

### R3-15 · P2 · 优化器配置接受无限学习率

位置：`ser_lib/config/optimizer.py:14`。

`AdamWConfig(learning_rate=float('inf'))` 构造成功。gt=0 只验证大小，没有保证有限；该值不能作为有效训练超参数。此探针证明配置放行，不宣称已实测所有优化器训练到 NaN。

验收：参与数值运算的配置显式要求 finite；NaN、正负 Inf、合法边界分别测试，避免只在损失变坏后才失败。

### R3-16 · P2 · 自动注入 sample_rate 绕过 transform schema

位置：`ser_lib/data/pipeline.py:178`。

同样 `pitch_shift, n_steps=25`，registry.create 按 [-24,24] 限制拒绝；省略 sample_rate 经 pipeline 自动注入时，直接调用 factory，构建成功。两个正式构建路径对同一参数的合法性判断不同。探针只构建，没有执行昂贵的音高变换。

验收：先合成注入后的完整参数，再统一调用 schema/registry；显式与自动采样率的非法参数行为一致。

### R3-17 · P2 · 批量容错吞掉 OperationCancelled

位置：`ser_lib/inference/batch.py:253`、272。

底层 predictor 主动抛 OperationCancelled；batch_size=1、fail_fast=False 时返回普通失败记录，error_type=OperationCancelled，而非传播取消。外层 token 的检查不能覆盖底层组件自行报告取消的情形。

验收：取消异常优先透传，不能被普通坏样本回退捕获；测试大于 1 的 chunk 回退、单条路径及取消后的剩余输入不再消费。

### R3-18 · P2 · process_cpu_percent 每次都是新对象首次采样

位置：`ser_lib/runtime.py:154`。

每次 `_host_metrics` 新建 psutil.Process，然后调用非阻塞 cpu_percent；没有保留上次进程采样。CPU 忙循环 0.25 秒后，复用参考 Process 的采样为 131.2%，库返回 0.0%。参考百分比会随调度变化，可超过 100%（进程多线程），不能把 131.2 当固定验收值。根因是每次重置采样历史。

验收：保留进程采样状态或显式返回“首次不可用”，连续忙/闲采样能区分负载；维持非阻塞承诺。

## 尚未计入缺陷数的扩展线索

- history restore 在回滚失败后，finally 仍删除 backup；editor 的 staging 清理也需核查失败保全。已有静态依据，但本轮没有故障注入证据，不能写成已验证数据丢失。
- export_checkpoint_artifact 需要比较 checkpoint 记录的标签/预处理与新导出配置，不能仅比较模型形状。尚未完成错标签导出的独立端到端探针。
- 模型兼容性 dtype、非前缀 mask、非时序输入与 fixed batching 的组合需要增补反例；不要凭接口直觉把全部行为定义为 bug。
- 真实语料专用 importer 的命名方言、长音频与损坏解码、并发事务/缓存、进程中断、多 worker 随机性、HF 架构矩阵和长期内存增长尚未穷尽。

**审计限制：本轮确认问题更多，不能据此宣称“所有 bug 都找到了”。** 当前证据已经足以否定“很完善”的结论；后续应先以数据安全和数值正确性建立关闭条件，再持续做组合与故障注入测试。
