# 01 - Training Run Detail

## 背景

当前训练运行信息已经拆分为三条轻量读取路径：`run.json`、`history.json` 与 checkpoint 文件 stat。调用方目前需要分别调用 `TrainingService.inspect_run()`、`inspect_history()`、`scan_checkpoints()` 才能构造训练详情页/Worker 返回值。

## 目标

新增稳定聚合 DTO：

```python
TrainingRunDetail
├── run
├── history
└── checkpoints
```

并新增：

```python
TrainingService.inspect_run_detail(...)
```

聚合接口只负责组合既有轻量读取能力，不读取模型权重。

## 范围

优先检查/修改：

- `ser_lib/engine/runs.py`
- `ser_lib/engine/training_history.py`
- `ser_lib/engine/checkpoint_catalog.py`
- `ser_lib/engine/__init__.py`
- `ser_lib/services/training.py`
- 必要时 `ser_lib/__init__.py`
- `tests/test_training_run_catalog.py`
- `tests/test_training_history.py`
- `tests/test_checkpoint_catalog.py`
- 新增 `tests/test_training_run_detail.py`

## 非范围

- 不调用 `torch.load()`；
- 不恢复模型/optimizer；
- 不读取 checkpoint tensor；
- 不修改训练过程写盘格式，除非发现现有格式无法稳定读取；
- 不删除三个已有独立接口。

## DTO 设计要求

建议 `TrainingRunDetail` 至少包含：

- `run: TrainingRunInfo`
- `history: TrainingHistoryInfo | None`
- `checkpoints: CheckpointCatalog`
- `diagnostics: tuple[Diagnostic, ...]` 或与项目现有容错模式一致的稳定缺失状态

必须提供 `to_dict()`，并保证：

- Path 序列化为跨平台规范字符串；
- tuple/list 等输出为 JSON-safe 容器；
- 嵌套 DTO 继续调用其稳定序列化；
- history 缺失不是必须抛出致命异常；
- run 本体缺失/损坏仍属于无法构造详情的主错误。

如果现有 `TrainingHistoryInfo` / Catalog 已经有更适合的缺失表达，应复用，不新造第二种错误模型。

## Service API

建议：

```python
def inspect_run_detail(
    self,
    run_dir: str | Path,
    *,
    tolerate_missing_history: bool = True,
) -> TrainingRunDetail:
    ...
```

最终签名以现有 Service 风格为准，避免引入项目中从未使用的可选参数风格。

实现必须复用：

- run inspect；
- history inspect/load；
- checkpoint scan。

不能在 Service 中复制 JSON 解析与 checkpoint stat 逻辑。

## 实现步骤

1. 读取三个现有 DTO/Catalog 的异常与 `to_dict()` 设计。
2. 决定聚合 DTO 所在模块：优先放在 `runs.py`，若现有职责表明需要独立 `run_detail.py` 才拆分。
3. 实现 DTO 与 JSON-safe 序列化。
4. 在 TrainingService 实现聚合 facade，内部调用已有能力。
5. 处理 history 缺失、history 损坏、checkpoint 目录不存在/为空等边界。
6. 更新 engine/service 公共导出。
7. 增加测试证明聚合调用不会触发 `torch.load()`。

## 测试计划

至少覆盖：

1. 完整 run：run + history + best/last/epoch checkpoint 均正确聚合；
2. 无 history：详情仍可返回，状态明确；
3. 空 checkpoint：返回空 catalog，不报模型加载错误；
4. checkpoint 存在但内容不是合法 PyTorch checkpoint：仅 stat 仍应成功；
5. `to_dict()` 可直接 `json.dumps()`；
6. Windows 风格路径/Path 输出保持现有统一规范；
7. monkeypatch `torch.load` 为抛异常，调用 detail 仍成功；
8. 原 `inspect_run()`、`inspect_history()`、`scan_checkpoints()` 行为不变。

## 验收标准

- 一个 Service 调用即可构造训练详情；
- 不加载任何权重；
- history 缺失有稳定表达；
- checkpoint 只做文件系统 stat；
- JSON-safe；
- 新旧接口并存；
- 定向 pytest、Ruff、mypy 通过。

## 建议提交

优先单提交：

`feat(training): add lightweight training run detail`

如果测试改动较大，可拆：

1. `test(training): cover training run detail aggregation`
2. `feat(training): add lightweight training run detail`
