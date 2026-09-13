# ser-lib 逐模块严格评估

> **1.0 归档说明（2026-09-13）**：本文是 SER-lib 1.0 形成过程中的历史记录，状态、路径、缺陷与“下一步”只对文中注明的历史基线负责。当前 1.0 规范请从 [文档索引](../README.md) 或仓库 `docs/README.md` 进入；当前发布状态见 `CHANGELOG.md`。原始正文保留用于审计追溯。


> 阅读顺序：本文件原正文保留第一轮历史基线；以下扩展复评针对 `0d4bd75`。当前可复现问题以[第二轮及扩展缺陷清单](SER_LIB_STRICT_REVIEW_ROUND2_2026-09-10.md)为准，不能把已修复的历史条目累加。审查文档现统一位于 `docs/development/review`。

## 扩展复评：2026-09-10，0d4bd75

**结论进一步收紧：架构拆分已经成形，但数据完整性、公共契约与失败恢复达不到成熟基础库的标准。** 扩展探针新增确认 18 项问题，与第二轮 11 项按不同根因编号，共记录 29 项当前基线缺陷；不是 29 个新增回归，也不是项目缺陷总数的估计。综合主观评分下调为 **5/10**。判断变化来自默认组件无法初始化、静默标签合并、失败导入破坏原数据集，以及恢复目标越界的实证，不来自“要严厉”而人为压分。

### 逐模块复评

分数衡量可托付程度，不是代码风格；未发现新增问题的模块不等于已证明无缺陷。原正文的分数为历史快照，下表覆盖当前判断。

| 模块 | 当前分数 | 严格评价与证据 |
|---|---:|---|
| foundation / 事件与异常 | 7/10 | 统一事件类型有价值，但调用方没有一致遵守取消和清理语义；R3-14、17 暴露契约落地不足。 |
| config / 迁移与参数 | 5/10 | 版本检查依入口变化，未来版本和无限学习率可被接受；R3-10、15、16。严格 schema 的存在不能代替所有入口真正调用它。 |
| AudioRecord / 表示契约 | 5/10 | 对象可构建、可写出，却不可读回；时序输出可漏报长度；R3-11、12。边界错误应当在边界被拒绝。 |
| manifest / 路径与持久化 | 4/10 | 合法的不同目录同名 split 在 write 后碰撞；R3-06。基础数据格式不能连自保存都缺少闭环。 |
| importers | 3/10 | 混合标签静默变义、相对 root 重复、失败转换覆盖已有数据；R3-03～05。此模块错误会污染全部下游实验。 |
| editor / history / fingerprint | 3/10 | R3-07 验证通过却能覆盖非数据集文件。指纹只覆盖 manifest 是已声明范围，不能误称音频内容校验；回滚失败后的备份保留还需要故障注入验证。 |
| audio loader / 预处理 | 6/10 | 常规入口有约束，但流式绕过峰值归一化仍见 R2-06；单采样点经 Normalize 产生 NaN（R3-08）。 |
| representations / 谱与韵律 | 4/10 | 默认 spectrogram 直接构建失败；power=1 的 LogMel 分贝换算错误；R3-01、02。韵律特征仍需真实语料与参考实现对照。 |
| transforms / pipeline | 4/10 | 构建检查和实际处理的 key 范围不一致，自动注入采样率又绕过参数 schema；R3-09、16。 |
| dataset / cache / profiling | 6/10 | 本轮没有新增已复现的缓存错误；不能由此宣称多进程、并发失效和大规模资源上界均已验证。 |
| collate / sampling / splitting | 6/10 | lengths 与 mask 的消费不一致继续影响 CNN（R2-03）；相同音频使用不同 UID 跨 split 的泄漏仍需业务级检查。 |
| CNN / GRU 等模型 | 5/10 | CNN padding 依赖已证实；GRU 非前缀 mask 等异常契约尚待专门探针，不计作已确认 bug。 |
| Torch / HF adapters | 4/10 | HF 同尺寸头重置无效（R2-04）；Torch adapter 嵌套在 ModuleDict 后无法加载自己保存的状态（R3-13）。 |
| trainer / loss / evaluator | 4/10 | R2-01、02 的数值错误直接影响训练及选模，事件异常又遗留 eval 模式（R3-14）。有训练循环不代表有可靠实验引擎。 |
| checkpoint / run / history | 4/10 | R2-05、09～11：实际续训配置、最佳路径、历史与 NumPy 随机状态不能完整还原。 |
| artifacts / offline / batch / streaming | 5/10 | R2-06～08 的预处理、非有限输出和导出兼容性问题未闭环；R3-17 将取消当作坏样本继续返回。 |
| runtime / CLI / 测试与发布 | 5/10 | CPU 进程占用采样恒取首次值（R3-18）；已有 420 项测试通过仍漏掉默认谱组件。CLI 复用工作流会继承其缺陷；构建成功不能代替真实安装、设备和依赖矩阵验收。 |

### 模块间联合检查

| 联合路径 | 已验证结果 | 最小验收条件 |
|---|---|---|
| CSV → 标签映射 → manifest | 两个源标签落入同一类，R3-03 | 输出记录与 label_mapping 一一对应，混合数字/文本用例覆盖。 |
| scan → convert → 原数据集重载 | scan 报成功，convert 抛错且旧数据集已损坏，R3-04 | 失败后原目录逐字节不变；成功前完成完整校验。 |
| manifest.load → write → load | 同名 split 文件碰撞，R3-06 | 保持各 split 内容与归属，空 split 另加测试。 |
| revision → 摘要验证 → restore | 摘要不变即可改写目标，R3-07 | 目标绑定受信 manifest 文件集合，非法目标在任何写入前拒绝。 |
| 参数 schema → 自动注入 → transform | 同一非法 n_steps 的接受结果因入口不同，R3-16 | 所有构建入口统一校验最终参数。 |
| 组合表示 → layout 校验 → SpecMasking | 校验通过，运行处理非时序向量并失败，R3-09 | 仅处理适用 key，或构建时明确拒绝组合。 |
| Torch adapter → ModuleDict → checkpoint | 保存后无法严格加载，R3-13 | 单独和嵌套两种状态字典 round trip 均成功。 |
| evaluator → 观察回调 → 后续训练 | started 回调异常后仍为 eval，R3-14 | 成功、失败、取消和回调异常均恢复原模式。 |
| predictor → 批量容错 → 取消 | OperationCancelled 被收集为失败，R3-17 | 取消传播、停止后续输入，普通坏文件继续容错。 |

### 覆盖边界与后续优先级

本轮采用小型离线反例验证公共入口和组合契约，没有逐行证明全部 110 个受版本控制的 Python 文件正确。已检查过的类别与尚未实测的边界必须分开：真实语料导入器的全部方言、任意损坏音频、并发编辑/缓存、多进程 DataLoader、恢复期间磁盘故障、不同 HF 架构、全部依赖上下限、长时间流式内存行为仍有空白。

整改顺序应为：先保护数据不被静默改错或失败操作破坏（R3-03、04、06、07），再修训练数值与标签/预处理语义（R2-01～06、R3-01、02），然后统一所有入口的契约与异常恢复。每个问题都需要反例成为回归测试；仅补正常路径断言、修改文档状态或再拆一层目录，不能关闭这些缺陷。

下文为第一轮历史正文。

审计基线：`refactor/ser-lib-core-boundary-12-stage@5184155cd56323eba8a7742f76698003949e2387`，2026-09-10。远端原名带 `refactor/` 前缀，已 fetch 并切换到跟踪分支。审查对象是当前完整库，不仅限于本次重构新增代码；以下缺陷不能全部归因于这次重构。

## 判断

**还不能称为“已经很完善”。它是架构比较清楚、工程设施较齐全的早期 SER SDK，适合受控研究和原型开发，但尚不足以承诺可靠的通用科研基线或生产级训练/流式推理。**

12 阶段重构的核心收益是真实的：foundation/config 分离、页面和 Service 包装退役、根导出惰性加载、直接领域 API、Torch adapter、HF processor 持久化和真实 tiny 模型集成均已落实。不能因为发现缺陷就否定这些工作；也不能把 API/目录验收通过当作数学正确性和实验可复现性验收。

以下评分是审计判断，不是测试成功率：5 表示已有可用实现，7 表示工程较完整但有关键边界待修，9 表示核心正确性和实际场景都有强证据。总评约 **6/10**；不宜机械平均掩盖训练与特征缺陷。

## 验证与边界

- 审查了 109 个已跟踪库 Python 文件的模块清单，重点阅读执行路径、配置、测试及 CI；并非对每行代码作形式化证明。
- Windows、Python 3.10.16、Torch 2.7.1+cu126、Transformers 5.16.1。复用现有 conda 依赖，在独立 `.venv-audit` 环境补充 psutil，没有改动库实现。
- 原工作区执行完整 pytest+coverage：392 passed、2 failed。失败源于旧 main 的 `ser_lib/core/__pycache__` 残留使退休路径仍存在/可作为 namespace 导入。
- 用 `git archive HEAD` 提取干净源码，并移除该进程中指向原仓库的 editable import finder 后：**394 passed**。因此不把上述两项算作干净分支代码失败。
- Ruff、mypy `--follow-imports=skip ser_lib`、pip check 均通过；CPU 单 epoch 冒烟通过；sdist 与 wheel 构建通过。
- 没有在本轮重跑 Linux/macOS、全部依赖版本组合、完整 CUDA AMP 训练、长时间压力测试或真实语料准确率基准。构建成功不等于重新验证了 wheel 的干净安装；本地测试环境共享已有依赖。
- 本轮包级行覆盖率：foundation 92.05%、config 90.83%、artifacts 89.71%、engine 92.28%、inference 90.41%、models 81.89%、data 76.48%、cli 84.70%。来自原工作区覆盖率运行，不能表述为无失败的 coverage run；干净源码另行全测通过。
- 独立数值探针见 `scripts/audit_boundary_repros.py`，运行方式：`python -m scripts.audit_boundary_repros`。使用 CPU、固定输入，无下载、无数据集写入。

## 优先缺陷

### P1：梯度累积尾组梯度被缩小（数值复现）

位置：`ser_lib/engine/_trainer_core.py:383`、`:471`。

每批 loss 总是除以配置的 accumulation_steps，最后不足一组时直接 optimizer.step，没有补偿。累积 4 步但只有 1 批数据时，本轮 SGD 参数更新范数为 0.06528266；累积 1 步为 0.26113063，恰好相差四倍。正常训练中最后不足 4 批也会触发。

修复应按实际累积样本/有效归约分母归一化；不仅修正尾批数量，还应定义不同 microbatch 大小时与整批训练的等价语义。验收应比较完整大 batch 和拆分 microbatch 的梯度/参数更新，涵盖尾组、不同 batch size、类别权重和 AMP。

### P1：配置 seed 未覆盖模型初始化（数值复现）

位置：`ser_lib/engine/experiment.py:204`、`ser_lib/engine/config.py:43`、`ser_lib/engine/_trainer_core.py:169`。

完整实验先构建模型，再构建 Trainer；seed_everything 在 Trainer 构造中才执行。同一 experiment seed，在不同外部 RNG 状态下构建组件并创建 Trainer，首层初始权重最大差为 0.21141002。新进程重复相同 YAML，初始参数仍可能不同。

完整实验入口应在任何随机组件构建前设种子。低层接受用户已构造模型的 Trainer 不能倒推修复初始化，应明确责任。NumPy RNG 和 deterministic 的完整语义也需要说明；目前 seed_everything 只处理 Python/Torch 和 cuDNN 开关。

### P1：F0 短语音失败，音质特征有占位输出（数值复现）

位置：`ser_lib/data/representations/acoustic.py:68`、`:199`。

F0 把 `sample_rate * 0.03`（默认 480）传为 detect_pitch_frequency 的 win_length，混淆采样点尺度与平滑窗口的帧尺度。实测 16 kHz、1 秒、200 Hz 正弦输入报 `RuntimeError: maximum size ... 302 but size is 480`。

`_JitterShimmerHNR.compute` 只计算 pitch 序列的周期变化，后两维明确为 `zeros_like(jitter)`，并没有计算 shimmer 与 HNR。测试输出 `[0.05004161, 0, 0]`。这比“没有高级特征”严重，因为字段名会让研究者误以为得到了实际测量。

应修正 F0 窗口单位、定义最短输入和无声语义；真实实现其余音质指标，或明确拒绝/退役这些未实现输出。用合成信号和可信参考计算验证数值，而非只验证 shape。

### P1：CNN 变长支持不满足 padding 不变性（数值复现）

位置：`ser_lib/models/cnn_models.py:40`、`:76`。

卷积和 BatchNorm 先处理全部时间轴，最后才 masked pooling。无效位置的中间激活可经后续卷积回流有效边缘；训练时 padding 还参与 BatchNorm 统计。eval 模式、同一条 7 帧特征，仅在右侧追加 15 个零且保持 mask/lengths 不变，logits 最大差 0.01732822。

因此同一输入的输出可能受同批最长样本影响。需要各层处理无效位置和合适的归一化方案，并测试不同 padding 长度、batch 组合下的输出一致性。GRU 已使用 packed sequence、Transformer 使用 attention mask，不能把此结论泛化为所有模型均有此问题。

### P1：流式下采样没有抗混叠（数值复现）

位置：`ser_lib/inference/streaming.py:_LinearResampler.push`。

当前按采样点线性插值，整数 48 kHz→16 kHz 时等价于直接每三点取一。48 kHz 的 12 kHz 正弦下采样后 RMS 仍为 0.70710677，而该分量超出目标 Nyquist 频率，应被滤掉；它将混叠进可听频段。分块一致性测试通过不能证明重采样音质正确。

应使用有状态低通/带限重采样，并明确算法延迟；当前逐输出采样点的 Python/Tensor 循环还需要实际吞吐和 p95 延迟基准。优先测试训练离线预处理与流式预处理在同一音频上的一致性。

### P1：实验评估未校验数据集和 artifact 的标签语义（静态确认）

位置：`ser_lib/engine/experiment.py:306`—`evaluate_artifact` 调用 evaluate 的路径。

加载外部 manifest 后直接使用其整数 target，以 artifact.labels 命名指标，没有比较两边标签语义。同样的 0/1 若在两个数据集分别代表相反情绪，形状、类别数和整数范围全合法，得到的 accuracy/UAR 却没有意义。训练入口同样应验证 manifest 标签与实验标签的对应关系。

应显式校验或接受明确 label mapping，映射不明时拒绝评估。低层 evaluate 接收已经规范化的 batch 可以保留，但高层 artifact+manifest 入口不能静默假设。

### P2：恢复训练不包含 weighted sampler 的独立 RNG（静态确认）

位置：`ser_lib/engine/objectives.py:85`、`ser_lib/engine/checkpoint.py:17`。

WeightedRandomSampler 使用独立 torch.Generator；checkpoint 只保存全局 Python/Torch CPU/CUDA RNG。重建数据加载器后 sampler 从 seed 起点重新开始，不能保证与连续运行的下一 epoch 序列一致。现有恢复测试使用固定批次，未证明该组合。

另：resume_from 比较完整 trainer_config，包含 epochs/checkpoint_dir，正常的“延长训练”或迁移输出目录会被拒绝。它支持严格同配置断点恢复，不等于灵活续训。应区分必须兼容的算法字段和允许修改的运行字段。

### P2：DatasetEditor 失败操作仍修改内存（数值复现）

位置：`ser_lib/data/editor.py:114`—`:116`。

update_record 先替换 record，再验证 split。传入合法 speaker_id 和非法空 split 时抛 DatasetEditError，但 dirty=True，speaker 已变为 audit-change。调用方捕获错误后继续 commit，可能提交它以为失败的修改。

应全部验证完成后一次应用。commit 的 fingerprint 乐观检查和逐文件回滚能处理部分异常，但检查与替换间没有锁，也没有多文件原子快照/崩溃日志，不能承诺多写者串行化或进程崩溃一致性。

### P2：高层训练返回可能不存在的 checkpoint 路径（静态确认）

位置：`ser_lib/engine/experiment.py:268`—`:276`。

返回值根据 epoch/best_epoch 拼接路径，没有遵循 save_last/save_best，也没有直接复用 TrainingResult 的真实 checkpoint 字段。关闭保存仍可能返回非空路径，导致后续导出/恢复失败。应以实际成功保存的路径作为唯一事实来源，并验证恢复场景中 best checkpoint 的位置。

### P2：兼容性测试尚不足以支撑发布承诺（实测）

位置：`tests/test_release_compatibility.py:35`、`tests/fixtures/release_compat/experiment_v1.yaml`。

legacy fixture 的 n_mels=4，但当前 LogMelConfig 要求 >=16。该测试只 load_experiment_config 就通过；实际 build_experiment_components 报 RegistryError。说明“旧 YAML 可以解析”没有验证“旧实验可以执行”。checkpoint fixture 权重也由当前模型生成，不能完全替代真实旧版本 golden artifact/checkpoint。

应保存实际历史版本生成的可执行小制品，在新版本里执行加载→构建→推理/续训。此次退休大量公开导入路径但版本仍为 0.2.0；即使是早期版本，也应以清楚的新发布版本和迁移说明区分两个不兼容 API 面。

## 模块评分与评估

| 模块 | 评分 /10 | 已有优点 | 主要不足与验收要求 |
|---|---:|---|---|
| foundation | 8 | 错误、诊断、事件、取消协议集中；基础层边界有测试 | 同步 callback 异常会传播进任务，需明确是故障传播还是观察者隔离；JSON-safe 的 float 路径未排除 NaN/Inf，严格 JSON 消费者需测试 |
| config / migrations | 7 | schema 集中、未知字段拒绝、版本入口和迁移机制完整 | StrictConfig 与部分直接 BaseModel 配置的冻结/赋值语义不一致；冻结不代表嵌套 dict/list 不可变；相对路径并非所有字段都统一基于 YAML（如 cache.directory）；跨版本执行验收不足 |
| data audio / importers / manifest | 7 | SoundFile 默认路径、标准 record、多个 importer、诊断和错误分类 | 缺少在真实语料上系统验证各 importer 的覆盖证据；大数据 manifest 多处全量载入；实验启动缺少说话人/音频片段跨 split 泄漏门禁 |
| data representations / transforms | 4 | waveform、谱图、多分支协议明确；拒绝不等长特征强拼接 | F0 与音质占位是核心缺陷；delta 直接针对 waveform，不能当作常规声学特征时间差分；需要逐特征数值参考和短音频/静音测试 |
| data collate / dataset / cache | 7 | 动态/固定/滑窗批处理，waveform 内容哈希缓存与并发临时文件 | 缓存无配额/淘汰；每次读音频和算内容哈希有成本；Dataset 设置共享 pipeline.validate_contract 会影响其他共享者；mask 消费者语义仍需统一 |
| data editor / history / query / profiling | 6 | 领域查询替代 Page/View；指纹、修订、staging/回滚可用 | 失败更新残留；多文件事务不具完整并发/崩溃原子性；反复全量扫描限制大型语料效率 |
| models 基类 / registry / CNN / GRU / Transformer | 6 | 明确 ModelSpec/ModelOutput；GRU packed sequence、Transformer mask；静态规格检查 | CNN padding 错误；GRU 只比较 mask 数量，没有像 Transformer 那样验证连续前缀；内置仍主要是轻量基线，未证明实际 SER 水平 |
| models Torch adapter | 7 | 显式输入输出映射、factory 重建、保留权重 key | 第三方 factory 必须在目标进程注册，artifact 并非携带任意模型代码；不代表任意 positional-only/signature 都适配；声明能力依赖用户诚实配置 |
| models HF adapter | 7.5 | 真实 tiny Wav2Vec2/HuBERT/WavLM 测试、processor snapshot、离线重建、禁 remote code | processor 白名单只有 Wav2Vec2FeatureExtractor，不能视为通用 HF 音频支持；tiny 正确性不能证明真实大模型、多设备性能和长期版本兼容 |
| engine training / checkpoint / experiment | 5 | AMP、优化器、scheduler、早停、取消、结果和 lineage 一条正式路径 | 累积梯度、seed、sampler 恢复、伪 checkpoint 路径等影响信任；保留公开 Trainer+内部实现继承不等于两套训练系统；缺少更完整恢复组合测试 |
| engine evaluation / reports / catalogs | 6.5 | 多分类指标、流式 sink、报告与扫描错误信息齐全 | 标签语义未核验；高层 evaluate_artifact 未暴露流式 sink，默认保留所有预测；滑窗按窗口算指标，与推理按原样本聚合口径不同，必须明确标注 |
| inference offline / batch | 7 | 复用 pipeline、显式窗口聚合、批预测事件和 sink | 低层 predictor 构造不提供完整兼容性预检；ModelOutput 允许非有限 logits，而推理 softmax 路径未拒绝，可能产生 NaN confidence；batch/window 扩张需资源预算 |
| inference streaming | 4.5 | 分块状态、窗口/hop、silence、平滑和 reset/flush 契约可用 | 无抗混叠重采样；逐点循环成本；latency 是窗口/重采样理论等待，并非实际端到端 p95；缺少长期持续输入证据 |
| artifacts | 8 | safetensors、哈希、元数据一致性、显式 legacy 门禁、processor 一体化 | 校验完整性不等于真实跨版本/跨设备可移植；factory 环境需另行部署；大型权重加载与目录并发访问仍需压力验证；0.x 仅比较 major 的兼容策略较粗 |
| runtime / benchmark | 6.5 | 按需 CPU/RAM/GPU 快照，无后台服务侵入 | benchmark 是同步操作/Python 内存指标；不能直接代表 CUDA 完成耗时或 Tensor 原生内存峰值；缺少硬件标识充分的可比性能基线 |
| CLI / docs / release / tests | 7 | CLI 下沉编排、明确导出、9 组合 OS/Python CI、HF 两版本任务、构建和 wheel smoke 配置 | 本轮只验证一套本机环境；Ruff 规则有限、mypy 跳过 imported modules；data 覆盖门槛仅60%、未启用分支覆盖；算法错误和不可执行 fixture 都能被现有测试放过 |

## 推荐修复顺序与完成标准

1. **先修结果正确性**：梯度累积、模型 seed、CNN padding、F0/占位特征、标签映射。每项需独立数值回归测试。
2. **再修状态可信度**：sampler RNG 恢复、失败更新原子性、真实 checkpoint 返回、训练历史续写语义；区分续训配置和原样恢复。
3. **再做音频/规模验收**：带限流式重采样、短音频/长音频/噪声输入、批次扩张、实时因子和 p95、内存上限、长时间运行。
4. **最后补发布证据**：真实历史制品、新版本号、干净 wheel 安装、最低依赖组合、完整跨平台 CI，并保存可追溯结果。
5. **独立补科学验证**：按说话人隔离评估、跨语料测试、多个随机种子和置信区间、标签映射/缺失类别策略。当前不应给出任何实际准确率或泛化水平的乐观判断，因为这轮没有相应数据证据。

结论：可以认可这次核心边界重构的方向和工程完成度；仍应阻止将当前版本描述为“完善的 SER 库”。上述 P1 消除、科学与实际运行验收补齐前，推荐定位为持续完善中的研究 SDK。
