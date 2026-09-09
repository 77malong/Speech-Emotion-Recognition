from __future__ import annotations

import json

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
