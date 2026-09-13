# 数据集与导入流程

data/ 用于用户自行准备的原始语料或本地数据卷。SER-lib 1.0 不下载、不打包、不重新分发
第三方语料。

所有外部数据统一通过 importer 转换为标准 DatasetManifest；训练只读取标准
dataset.yaml + JSONL split，不再维护“每个数据集一套 Dataset 类”的离线 Processor 体系。

## 统一 CLI

预览：

~~~bash
ser dataset scan --importer <importer-id> --source <raw-data> --json
~~~

导入：

~~~bash
ser dataset import --importer <importer-id> --source <raw-data>   --destination data/<dataset>-standard --json
~~~

验证：

~~~bash
ser dataset validate data/<dataset>-standard/dataset.yaml --check-files --json
ser dataset stats data/<dataset>-standard/dataset.yaml --probe-audio --json
~~~

convert 在最终替换目标前完成结构校验；失败不应静默破坏已有标准数据集。

## 内置 importer

- folder
- csv
- jsonl
- casia
- ravdess
- csemotions
- esd
- crema_d
- emotiontalk

Importer 负责扫描、标签/说话人解析、split 和 manifest 生成；音频解码、Representation、
batching 和模型 compatibility 由统一数据管线负责。

## CASIA 示例

~~~bash
python scripts/prepare_casia.py   --source data/CASIA   --destination data/casia-standard

ser dataset validate data/casia-standard/dataset.yaml --check-files
ser train configs/casia_cnn_logmel.yaml --batch-size 32
~~~

prepare_casia.py 使用 CasiaImporter 并生成说话人互斥划分。也可直接使用统一 importer：

~~~bash
ser dataset scan --importer casia --source data/CASIA --json
ser dataset import --importer casia --source data/CASIA   --destination data/casia-standard
~~~

## Python API

~~~python
from pathlib import Path
from ser_lib.data.importers import CasiaImporter

importer = CasiaImporter()
source = Path("data/CASIA")
preview = importer.scan(source, {})
if preview.ok:
    manifest = importer.convert(source, Path("data/casia-standard"), {})
~~~

底层加载统一使用 ser_lib.data 中的 DatasetManifest、SERDataset、build_components 和
build_collator。

新增数据集应实现 DatasetImporter 协议并注册到统一 registry，不要重新引入 Processor
基类或特征类型专用 Dataset。

## 许可

数据许可与代码许可相互独立。请以实际取得数据副本附带的官方条款为准；发布模型时在模型卡
记录训练数据和使用限制。参考 [THIRD_PARTY_LICENSES.md](../THIRD_PARTY_LICENSES.md)。
