# 训练与 CLI

SER-lib 1.0 以严格校验的 `ExperimentConfig` 作为训练配置源。相对路径按配置文件
自身目录解析。

## 常用命令

~~~bash
ser --version
ser components list --json

ser train configs/cnn_logmel.yaml --split train --batch-size 16 --json
ser train configs/cnn_logmel.yaml   --resume runs/cnn-logmel/checkpoints/epoch-0005.pt   --json

ser evaluate artifacts/model   --manifest data/standard/dataset.yaml   --split test   --output runs/evaluation   --json

ser predict artifacts/model path/to/audio.wav   --output runs/predictions.jsonl   --json
~~~

所有命令支持 `--help`；主要工作流支持 `--json` 方便脚本消费。

## 训练目录

未配置 `checkpoint_dir` 时使用 `output_dir/checkpoints`：

~~~text
output_dir/
├── checkpoints/
│   ├── epoch-NNNN.pt
│   ├── best.pt
│   ├── best-*.pt
│   └── last.pt
├── metrics.jsonl
├── history.json
└── run.json
~~~

不可变 best 快照用于保持历史 checkpoint 的最佳模型身份；`best.pt` 是当前最佳模型
的便捷入口。

fresh run 与 resume 的历史语义不同：

- 不传 `--resume`：创建新 run，重置本次 metrics/history。
- 传 `--resume`：恢复 checkpoint 的训练状态，并继续同一训练 lineage。
- 从较早 epoch 回溯续训时，未来 epoch 的 history/metrics 会被裁剪，避免混合两条时间线。

## 验证、选模和 early stopping

manifest 含 `val` split 时，Trainer 根据配置执行验证。monitor 可使用
`val_loss`、`val_accuracy`、`val_uar`、`val_macro_f1`。

`early_stopping_patience` 与 `early_stopping_min_delta` 控制早停；没有 val split
时不得开启依赖验证集的 early stopping。

weighted loss 的跨 batch 聚合使用 loss 自身 reduction denominator，因此更换 validation
batch 划分不会改变同一数据集的加权 loss。

## 类别不平衡

~~~yaml
loss:
  type: focal
  focal_gamma: 2.0
  class_weights: [1.0, 1.5, 2.0]
  label_smoothing: 0.0

sampling:
  type: weighted
  replacement: true
~~~

loss class_weights 控制损失贡献；sampling class_weights 控制采样概率，两者可独立使用。

## Checkpoint

checkpoint 保存模型、优化器、scheduler、scaler、RNG、训练计数、lineage 等恢复状态。
恢复前会校验模型/训练配置、关联 best、RNG 与采样器状态；恢复过程失败时会回滚已应用的
运行状态，避免留下半恢复对象。

checkpoint 使用 Torch 序列化，只加载来源可信的本地文件。

## Artifact 导出

~~~bash
ser artifact export   --config configs/cnn_logmel.yaml   --checkpoint runs/cnn-logmel/checkpoints/best.pt   --destination artifacts/model   --json
~~~

导出会检查 checkpoint lineage、当前 config、manifest 的标签语义、数据身份和预处理
兼容性；不能只靠相同的 num_classes 绕过标签语义检查。

## 评估输出

高层评估目录包含：

~~~text
evaluation/
├── run.json
├── metrics.json
└── predictions.jsonl   # 启用预测明细时
~~~

指标包含 accuracy/WAR、UAR、macro/weighted precision/recall/F1、balanced accuracy、
MCC、Cohen's kappa、逐类指标和混淆矩阵。

`metric_unit` 明确指标单位：

- dynamic/fixed batching：`sample`
- sliding batching：`window`
- 未声明 batching 语义：`batch_row`

## Event callback

核心 event callback 是同步 fail-fast hook。callback 抛异常会终止当前操作并传播；
核心代码负责在 finally/rollback 边界恢复自己临时改变的状态。若宿主希望遥测失败不影响
训练，应在宿主层包装 callback。

## 工程验收说明

仓库曾用真实 EmotionTalk 数据完成 3 epoch GPU 工程验收，验证混合采样率、单双声道、
focal loss、WeightedRandomSampler、checkpoint、artifact 和评估链路。该记录只证明工程
链路可运行，不构成模型效果或论文基准。
