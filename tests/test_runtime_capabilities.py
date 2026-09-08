import json
from types import SimpleNamespace

import torch

from ser_lib import RuntimeCapabilities, get_runtime_capabilities


def test_runtime_capabilities_are_json_safe_and_include_cpu():
    capabilities = get_runtime_capabilities()

    assert isinstance(capabilities, RuntimeCapabilities)
    payload = capabilities.to_dict()
    json.dumps(payload)
    assert payload["python_version"]
    assert payload["torch_version"]
    assert isinstance(payload["cuda_available"], bool)
    assert payload["devices"][0] == {
        "id": "cpu",
        "type": "cpu",
        "name": "CPU",
        "total_memory": None,
        "amp_supported": False,
    }


def test_runtime_capabilities_list_each_cuda_device(monkeypatch):
    monkeypatch.setattr(torch.cuda, "is_available", lambda: True)
    monkeypatch.setattr(torch.cuda, "device_count", lambda: 2)
    monkeypatch.setattr(
        torch.cuda,
        "get_device_properties",
        lambda index: SimpleNamespace(
            name=f"Mock GPU {index}",
            total_memory=(index + 1) * 1024,
        ),
    )
    mps_backend = getattr(torch.backends, "mps", None)
    if mps_backend is not None:
        monkeypatch.setattr(mps_backend, "is_available", lambda: False)

    capabilities = get_runtime_capabilities()

    assert capabilities.cuda_available is True
    cuda_devices = [device for device in capabilities.devices if device.type == "cuda"]
    assert [device.id for device in cuda_devices] == ["cuda:0", "cuda:1"]
    assert [device.name for device in cuda_devices] == ["Mock GPU 0", "Mock GPU 1"]
    assert [device.total_memory for device in cuda_devices] == [1024, 2048]
    assert all(device.amp_supported for device in cuda_devices)
