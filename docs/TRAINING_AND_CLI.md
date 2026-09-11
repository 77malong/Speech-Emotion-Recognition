# 训练与 CLI

训练以严格校验的 `ExperimentConfig` 为唯一配置源，组合 data、model、trainer、
optimizer、scheduler 和 output_dir。相对路径按配置文件位置解析。

```bash
ser train configs/cnn_logmel.yaml --split train --batch-size 16
ser train configs/cnn_logmel.yaml --resume runs/cnn-logmel/checkpoints/epoch-0005.pt
ser evaluate artifacts/model --manifest data/dataset.yaml --split test --output runs/eval
ser predict artifacts/model path/to/audio --output runs/predictions.jsonl
```

未配置 checkpoint 目录时 CLI 使用 `output_dir/checkpoints`。checkpoint 用于可信
本地续训，不用于分发；评估和推理以 artifact 为入口。所有命令支持 `--help`，
主要结果可通过 `--json` 提供给脚本调用。

当 manifest 包含 `val` split 时，训练会在每个 `validation_interval` 自动验证。
`trainer.monitor` 可选择 `val_loss`、`val_accuracy`、`val_uar` 或
`val_macro_f1`；配置 `early_stopping_patience` 后，连续相应次数未达到
`early_stopping_min_delta` 即停止。checkpoint 目录同时保存逐 epoch 文件、
`last.pt` 和指标改善时更新的 `best.pt`。没有 `val` split 时不得启用 early stopping。

类别不平衡可以在实验配置中独立控制 loss 和 sampler：

```yaml
loss:
  type: focal                 # cross_entropy 或 focal
  focal_gamma: 2.0
  class_weights: [1.0, 1.5, 2.0]  # 可省略
  label_smoothing: 0.0
sampling:
  type: weighted              # shuffle 或 weighted
  # 不给 class_weights 时，根据训练 split 的类别频次自动取逆频率
  replacement: true
```

Loss 的 `class_weights` 改变各类别损失贡献，sampling 的 `class_weights` 改变样本
被抽取的概率，两者可以单独或组合使用。训练过程通过 `ser_lib.engine.training.trainer` logger
报告 epoch 指标，并在 `output_dir/metrics.jsonl` 每完成一个 epoch 追加一条记录；
`history.json` 是本次调用结束后的汇总。恢复训练会继续追加 JSONL。

评估报告除 accuracy/WAR、UAR 和 macro-F1 外，还包含 weighted precision、
weighted recall、weighted F1、balanced accuracy、Matthews correlation coefficient
和 Cohen's kappa。高层 `evaluate_artifact()` 的机器可读结果和 `metrics.json` 还会
写出 `metric_unit`：`dynamic/fixed` 为 `sample`，`sliding` 为 `window`；若调用方构造的 preprocessing 未声明 batching 语义，则标为 `batch_row`，不得把窗口级指标误读为原始样本级指标。

## Event callback 失败语义

训练、评估等核心执行路径中的 `event_callback` 是同步的 **fail-fast hook**，不是由
核心库隔离异常的 best-effort observer。callback 抛出的异常会终止当前操作并继续向
调用方传播；核心执行路径仍负责通过 `finally` 等机制恢复自身已经改变的运行状态，
例如评估过程中临时切换的模型 train/eval mode。

如果宿主 Worker 希望某个遥测、日志或 observer 失败后任务仍继续，应在
宿主边界自行包装 callback，明确决定记录、重试或丢弃策略，而不是依赖核心库静默吞掉
异常。`prediction_sink` 等同步持久化 hook 同样遵循失败即传播原则，避免任务表面成功但
关键输出已经丢失。

## 真实数据验收记录

2026-09-08 使用 `audio_classification` Conda 环境和 RTX 4060，在默认说话人独立的
EmotionTalk manifest 上完成 3 epoch 工程训练。训练集/验证集/测试集分别为
12,974/3,661/2,615 条；最佳模型位于 epoch 2，验证 UAR 为 0.3519、macro-F1 为
0.2804。最佳 artifact 在独立测试集得到 accuracy 0.4172、UAR 0.3445、macro-F1
0.2927。该记录用于证明 44.1/16 kHz、单双声道、focal loss、WeightedRandomSampler、
checkpoint、artifact 和评估链路可运行，不应作为模型效果或论文基准。

训练运行目录结构如下：

```text
output_dir/
├── checkpoints/
│   ├── epoch-NNNN.pt
│   ├── best.pt
│   └── last.pt
├── metrics.jsonl
└── history.json
```

PyTorch 2.7 会对旧式 `torch.cuda.amp.GradScaler` 发出弃用提示；当前提示不影响结果，
后续实现应迁移到 `torch.amp.GradScaler("cuda")`。
