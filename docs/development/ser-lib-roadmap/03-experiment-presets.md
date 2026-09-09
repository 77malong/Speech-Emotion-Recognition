# 03 - Experiment Presets

## 目标

建立正式实验预设能力，让应用层可以通过稳定 preset id 构造常见训练配置，但最终仍只生成现有 `ExperimentConfig`，绝不建立第二套配置系统。

首批预设建议：

- CNN + LogMel baseline
- GRU + LogMel 或与仓库现有真实 GRU 配置一致的表示组合
- Transformer + LogMel
- HF Audio Classifier（仅当当前 ExperimentConfig/Model registry 已能完整表达；否则标记 unavailable/experimental，而不是硬塞不完整配置）

## 主要代码

先核对：

- `ser_lib/engine/config.py`
- `ser_lib/core/config.py`
- `ser_lib/catalog.py`
- `configs/*.yaml`
- `tests/test_engine_config.py`
- `tests/test_component_catalog.py`

可新增：

- `ser_lib/engine/presets.py`
- `tests/test_experiment_presets.py`

## 设计

建议提供：

```python
ExperimentPresetInfo
ExperimentPresetCatalog
list_experiment_presets()
get_experiment_preset(preset_id)
build_experiment_config(preset_id, overrides=None)
```

具体命名应与现有 Catalog 风格统一。

Preset 描述至少包括：

- stable id；
- display name；
- description；
- status/capabilities（若现有 Catalog 已有枚举则复用）；
- 默认配置模板；
- 可选 tags。

## Overrides 规则

- override 必须作用于 `ExperimentConfig` 可表达字段；
- override 后必须走现有 Pydantic/config validation；
- 不允许绕过 component compatibility；
- 不允许 preset 自己执行 dataset/model runtime validation，这仍由 `validate_experiment()` 完成。

## 配置来源

优先让 Python preset 与仓库现有 `configs/*.yaml` 保持语义一致。必须明确“谁是规范来源”，避免 Python 默认值和 YAML 长期漂移。推荐：preset 由代码构造稳定 DTO，YAML 作为示例/可导出配置；测试负责约束两者关键字段一致。

## 测试

- 每个 stable preset 都能构造 `ExperimentConfig`；
- `to_dict/model_dump` JSON-safe；
- override 正常且非法 override 失败明确；
- preset id 稳定且重复检测；
- 与 component catalog 引用的 model/representation id 均存在；
- baseline preset 可通过不分配 GPU/不 forward 的 dry-run 配置级检查。

## 验收

- 应用层不需要手工拼基础配置；
- 仍只有 `ExperimentConfig` 一套配置模型；
- preset 可被 Catalog/未来 Worker 枚举；
- 无隐式模型加载或 GPU 分配。

## 建议提交

`feat(config): add experiment preset catalog`
