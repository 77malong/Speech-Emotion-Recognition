# 标准数据格式

SER-lib 1.0 的标准数据集由一个 `dataset.yaml` 和零个或多个 JSONL split 文件组成。

~~~yaml
dataset_id: demo
root: ./audio
splits:
  train: train.jsonl
  val: val.jsonl
  test: test.jsonl
labels:
  0: {en: neutral, zh: 平静}
  1: {en: happy, zh: 高兴}
~~~

空 split 声明会被保留；未分配到任何 split 的记录也有独立语义，不会与名为
`unassigned` 的真实 split 冲突。

## JSONL record

每行至少需要：

- `uid`：数据集内唯一 ID
- `audio_path`：相对 dataset root 或绝对音频路径

训练记录通常还包含从 0 开始连续编号的整数 `label`。可选字段包括：

- `start_ms` / `end_ms`
- `speaker_id`
- `sample_rate_hint`
- `metadata`

路径解析不依赖当前工作目录：split 文件相对 dataset.yaml，音频相对 root。

## 严格校验

当前结构禁止未知字段和已经退役的版本字段。Manifest 的 write/load 保留 split 归属、
空 split 和未分配记录；同名输出文件冲突会在写入前被拒绝。

~~~bash
ser dataset validate data/standard/dataset.yaml --check-files --json
ser dataset stats data/standard/dataset.yaml --probe-audio --json
~~~

## Importer

~~~bash
ser dataset scan --importer folder --source path/to/audio --json
ser dataset import --importer folder --source path/to/audio   --destination data/standard
~~~

内置 importer：

| ID | 输入 |
|---|---|
| `folder` | 按目录/文件规则组织的音频 |
| `csv` | CSV 元数据 |
| `jsonl` | JSONL 元数据 |
| `casia` | CASIA |
| `ravdess` | RAVDESS |
| `csemotions` | CSEMOTIONS |
| `esd` | Emotional Speech Dataset |
| `crema_d` | CREMA-D |
| `emotiontalk` | BAAI EmotionTalk |

Importer 的转换阶段使用临时输出和校验边界，失败不能静默破坏已有标准数据集。

## Data / Representation 分工

Dataset 不根据模型或特征类型分叉。Waveform、Mel、MFCC 等由 Representation 负责，
输出 TensorSpec；SERDataset 只组合 AudioLoader、Pipeline 和 record。

数据集专用命令和许可说明见 [data/readme.md](../data/readme.md)。
