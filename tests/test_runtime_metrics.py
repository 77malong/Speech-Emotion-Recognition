import json

import pytest
import torch

from ser_lib import RuntimeMetrics, get_runtime_metrics
from ser_lib.services import RuntimeService


def test_cpu_runtime_metrics_are_lightweight_and_json_safe():
    metrics = get_runtime_metrics("cpu")

    assert isinstance(metrics, RuntimeMetrics)
    assert metrics.device_id == "cpu"
    assert metrics.device_type == "cpu"
    assert metrics.captured_at.tzinfo is not None
    assert metrics.allocated_memory is None
    assert metrics.reserved_memory is None
    assert metrics.max_allocated_memory is None
    assert metrics.free_memory is None
    assert metrics.total_memory is None
    payload = metrics.to_dict()
    assert payload["captured_at"].endswith("+00:00")
    json.dumps(payload)


def test_cuda_runtime_metrics_use_allocator_without_synchronize(monkeypatch):
    monkeypatch.setattr(torch.cuda, "is_available", lambda: True)
    monkeypatch.setattr(torch.cuda, "device_count", lambda: 2)
    monkeypatch.setattr(torch.cuda, "current_device", lambda: 1)
    monkeypatch.setattr(torch.cuda, "mem_get_info", lambda index: (1000 + index, 2000 + index))
    monkeypatch.setattr(torch.cuda, "memory_allocated", lambda index: 3000 + index)
    monkeypatch.setattr(torch.cuda, "memory_reserved", lambda index: 4000 + index)
    monkeypatch.setattr(torch.cuda, "max_memory_allocated", lambda index: 5000 + index)

    metrics = get_runtime_metrics("cuda")

    assert metrics.device_id == "cuda:1"
    assert metrics.device_type == "cuda"
    assert metrics.allocated_memory == 3001
    assert metrics.reserved_memory == 4001
    assert metrics.max_allocated_memory == 5001
    assert metrics.free_memory == 1001
    assert metrics.total_memory == 2001


def test_runtime_service_exposes_metrics_snapshot():
    metrics = RuntimeService.metrics("cpu")

    assert isinstance(metrics, RuntimeMetrics)
    assert metrics.device_id == "cpu"


def test_cuda_runtime_metrics_validate_availability_and_index(monkeypatch):
    monkeypatch.setattr(torch.cuda, "is_available", lambda: False)
    with pytest.raises(ValueError, match="CUDA 不可用"):
        get_runtime_metrics("cuda:0")

    monkeypatch.setattr(torch.cuda, "is_available", lambda: True)
    monkeypatch.setattr(torch.cuda, "device_count", lambda: 1)
    with pytest.raises(ValueError, match="超出当前设备数量"):
        get_runtime_metrics("cuda:2")


def test_runtime_metrics_reject_invalid_device():
    with pytest.raises(ValueError, match="无效运行设备"):
        get_runtime_metrics("not-a-device")
