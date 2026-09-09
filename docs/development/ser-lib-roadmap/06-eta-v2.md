# 06 - ETA Estimator v2

## 背景

Trainer 已有基础 ETA，但训练开始阶段前几个 batch 的耗时容易导致 ETA 大幅抖动，而且 train/validation 阶段的剩余时间表达还可以更清晰。

## 目标

提供更稳定的 ETA：

- recent-N-batch moving average / throughput；
- epoch remaining；
- global remaining；
- train/validation 分阶段 ETA（能可靠估算时提供）；
- warmup 阶段避免输出误导性的极端 ETA。

## 主要代码

- `ser_lib/engine/trainer.py`
- `ser_lib/core/events.py`（只有事件字段需要扩展时）
- `tests/test_trainer_observability.py`
- 可新增 `ser_lib/engine/eta.py` 与 `tests/test_eta.py`

## 设计建议

将计算逻辑从 Trainer 主循环中抽成小型状态对象：

```python
EtaEstimator
record_batch(duration, samples, phase=...)
snapshot(progress_state) -> EtaSnapshot
```

不要让 estimator 知道模型、optimizer、DataLoader 实现细节。

建议采用固定 recent window 或 EWMA，配置应通过已有 ObservabilityConfig 扩展，避免增加第二套观测配置。

## 兼容性

现有 ProgressEvent 字段若已有 `eta_seconds`，继续保留。新增字段必须可选，避免旧 consumer 崩溃。

不要在每个 batch 进行昂贵系统调用；仅使用 Trainer 已有 monotonic timing 与计数。

## 测试

使用 fake clock/显式 duration，禁止依赖真实 sleep：

- 前几个 batch 处于 warmup；
- 稳定 batch 时 ETA 收敛；
- 单个慢 batch 不导致全局 ETA 巨幅永久偏移；
- throughput 改变后 recent window 可逐步跟随；
- epoch 边界计算正确；
- validation phase 不把训练 batch 计数搞乱；
- resumed run/global step 下 remaining 正确；
- cancellation/failure 不受影响。

## 验收

- ETA 明显比全历史简单平均更稳定；
- 计算 O(1) 或 O(window) 且 window 有界；
- 不增加训练关键路径显著开销；
- Event JSON schema 兼容。

## 建议提交

1. `feat(engine): add bounded eta estimator`
2. `feat(training): use smoothed eta in progress events`
