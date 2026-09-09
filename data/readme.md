# 数据集与导入流程

`data/` 只用于存放用户自行准备的原始语料或本地数据卷。仓库不再维护独立的数据处理脚本体系，也不再使用 `DatasetProcessor` / `CasiaProcessor` 一类离线 Processor。

所有外部语料统一通过 `ser_lib.data.importers` 转换为标准 `DatasetManifest`，应用层优先使用 `ser dataset ...` CLI 或 `DatasetService`。

## 统一工作流

先预览，不写盘：

```bash
ser dataset scan --importer <importer-id> --source <raw-data> --json
```

确认后导入：

```bash
ser dataset import --importer <importer-id> --source <raw-data> \
  --destination data/<dataset>-standard
```

校验标准数据集：

```bash
ser dataset validate data/<dataset>-standard/dataset.yaml --check-files
ser dataset stats data/<dataset>-standard/dataset.yaml --probe-audio --json
```

训练配置只引用标准 `dataset.yaml`，不再依赖数据处理脚本生成的专用 Dataset 类或额外 pipeline 配置。

## 已内置 Importer

当前统一 Importer 包括：

- `folder`：按目录结构导入通用音频集合；
- `csv`：从 CSV 元数据导入；
- `jsonl`：从 JSONL 元数据导入；
- `casia`：CASIA；
- `ravdess`：RAVDESS；
- `crema_d`：CREMA-D；
- `esd`：Emotional Speech Dataset；
- `csemotions`：CSEMOTIONS；
- `emotiontalk`：BAAI EmotionTalk。

Importer 负责扫描、标签/说话人解析和标准 manifest 生成；音频解码、Representation、batching 与模型兼容性由 `ser_lib.data` 新流水线统一处理。

## CASIA

CASIA 不再使用 `python data/casia_process.py`。需要标准的说话人独立 train/val/test 划分时使用：

```bash
python scripts/prepare_casia.py \
  --source data/CASIA \
  --destination data/casia-standard

ser dataset validate data/casia-standard/dataset.yaml --check-files
ser train configs/casia_cnn_logmel.yaml --batch-size 32
```

`prepare_casia.py` 先使用 `CasiaImporter` 扫描原始目录，再按说话人进行互斥划分。四说话人数据使用 2/1/1 划分；说话人数量不足 4 时拒绝生成伪独立评估集。

如果不需要脚本提供的固定 speaker split，也可以直接调用统一 importer：

```bash
ser dataset scan --importer casia --source data/CASIA --json
ser dataset import --importer casia --source data/CASIA \
  --destination data/casia-standard-flat
```

## Python API

```python
from ser_lib.services import DatasetService

preview = DatasetService.scan_importer("casia", "data/CASIA", {})
if preview.ok:
    manifest = DatasetService.import_dataset(
        "casia",
        "data/CASIA",
        "data/casia-standard",
        {},
    )
```

底层数据加载统一使用：

```python
from ser_lib.data import DatasetManifest, SERDataset, build_components, build_collator
```

不要在 `data/` 下新增新的 Processor 基类或每数据集一套独立流水线。新增数据集应实现 `ser_lib.data.importers.DatasetImporter` 协议并注册到统一 Registry。
