from __future__ import annotations

import json
from types import SimpleNamespace

import ser_lib.runtime as runtime
from ser_lib.runtime import get_runtime_metrics


def test_cpu_runtime_metrics_include_host_resources_without_sleep():
    metrics = get_runtime_metrics("cpu")
    payload = metrics.to_dict()

    assert metrics.device_type == "cpu"
    assert metrics.process_rss_bytes is not None and metrics.process_rss_bytes >= 0
    assert metrics.system_memory_used_bytes is not None and metrics.system_memory_used_bytes >= 0
    assert (
        metrics.system_memory_available_bytes is not None
        and metrics.system_memory_available_bytes >= 0
    )
    assert metrics.system_memory_total_bytes is not None and metrics.system_memory_total_bytes > 0
    assert metrics.system_memory_used_bytes <= metrics.system_memory_total_bytes
    assert metrics.system_memory_available_bytes <= metrics.system_memory_total_bytes
    assert metrics.process_cpu_percent is not None and metrics.process_cpu_percent >= 0.0
    assert metrics.system_cpu_percent is not None and metrics.system_cpu_percent >= 0.0
    json.dumps(payload)


def test_cpu_runtime_metrics_keep_gpu_allocator_fields_optional():
    metrics = get_runtime_metrics("cpu")

    assert metrics.allocated_memory is None
    assert metrics.reserved_memory is None
    assert metrics.max_allocated_memory is None
    assert metrics.free_memory is None
    assert metrics.total_memory is None



class _FakeProcessSampler:
    def __init__(self) -> None:
        self.cpu_values = iter([75.0, 2.0])
        self.cpu_calls = 0

    def memory_info(self):
        return SimpleNamespace(rss=1234)

    def cpu_percent(self, interval=None):
        assert interval is None
        self.cpu_calls += 1
        return next(self.cpu_values)


def test_host_metrics_reuses_process_cpu_sampling_history(monkeypatch):
    sampler = _FakeProcessSampler()
    memory = SimpleNamespace(used=10, available=20, total=30)
    monkeypatch.setattr(runtime, "_PROCESS_SAMPLER", sampler)
    monkeypatch.setattr(runtime.psutil, "virtual_memory", lambda: memory)
    monkeypatch.setattr(runtime.psutil, "cpu_percent", lambda interval=None: 5.0)

    busy = runtime._host_metrics()
    idle = runtime._host_metrics()

    assert busy.process_cpu_percent == 75.0
    assert idle.process_cpu_percent == 2.0
    assert sampler.cpu_calls == 2
