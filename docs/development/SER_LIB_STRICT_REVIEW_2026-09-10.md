# ser-lib 逐模块严格评估

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
