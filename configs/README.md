# 实验配置模板

本目录提供 SER-lib 1.0 可直接校验的 ExperimentConfig 示例。配置只接受当前严格结构，
不包含 schema_version/format_version；未知字段会被拒绝。

## 通用模板

~~~bash
ser train configs/cnn_logmel.yaml --split train --batch-size 16
ser train configs/gru_mfcc.yaml --split train --batch-size 16
ser train configs/transformer_logmel.yaml --split train --batch-size 16
~~~

这些模板默认引用标准 dataset.yaml。使用前必须根据自己的数据同步检查：

- data.manifest
- data.labels
- model.params.num_classes
- representation 输出 feature_dim 与模型输入维度
- trainer.device / batch size / checkpoint_dir

相对路径始终相对于配置文件自身，而不是当前 shell 工作目录。

## 数据集专用模板

~~~bash
ser train configs/casia_cnn_logmel.yaml --batch-size 32
ser train configs/csemotions_cnn_logmel.yaml --batch-size 32
ser train configs/esd_cnn_logmel.yaml --batch-size 32
ser train configs/crema_d_cnn_logmel.yaml --batch-size 32
ser train configs/emotiontalk_cnn_logmel.yaml --batch-size 32
~~~

对应数据必须先用 importer 转换为标准 manifest。专用配置中的 label mapping 是训练语义的一部分；
artifact 导出会与 checkpoint lineage 和 manifest 再次比对，不能随意交换 label ID 含义。

EmotionTalk 示例默认展示 focal loss + WeightedRandomSampler 组合，用于处理类别不均衡；
这不是所有数据集的默认建议。

## 模型卡

CASIA、CSEMOTIONS、ESD、CREMA-D、EmotionTalk 同时提供 model_card YAML 示例。
正式发布 artifact 时应根据真实训练数据、指标、许可和限制修改，不能直接把示例当作真实声明。

完整训练说明见 [docs/TRAINING_AND_CLI.md](../docs/TRAINING_AND_CLI.md)。
