"""Tests for router default configuration behavior."""

from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path
from typing import Any, Dict

import pytest


PYTHON_ROOT = Path(__file__).resolve().parents[3] / "python"
ROUTER_PATH = PYTHON_ROOT / "mlc_llm" / "router" / "router.py"


class _DummyServer:
    """Lightweight stand-in for :class:`PopenServer` used in tests."""

    started_with: Dict[str, Any]

    def __init__(self, *args, **kwargs):
        self.started_with = kwargs

    def start(self, extra_env=None):
        # The router calls ``start`` inside worker threads. Record the value so tests can
        # assert the call happened without launching an actual subprocess.
        self.extra_env = extra_env

    def terminate(self):
        # Mimic the real interface; nothing to clean up in the dummy implementation.
        pass


class _DummyTokenizer:
    def __init__(self, model: str):
        self.model = model

    def encode(self, text: str):
        return text


@pytest.fixture()
def router_module(monkeypatch):
    """Load the router module with heavy dependencies stubbed out."""

    # Stub out the ``mlc_llm`` package hierarchy with the minimal surface that ``router``
    # relies on so we can import the real router implementation without loading optional
    # runtime libraries.
    mlc_llm_pkg = types.ModuleType("mlc_llm")
    mlc_llm_pkg.__path__ = [str(PYTHON_ROOT / "mlc_llm")]
    monkeypatch.setitem(sys.modules, "mlc_llm", mlc_llm_pkg)

    protocol_pkg = types.ModuleType("mlc_llm.protocol")
    protocol_pkg.__path__ = []
    monkeypatch.setitem(sys.modules, "mlc_llm.protocol", protocol_pkg)

    openai_api_protocol_module = types.ModuleType("mlc_llm.protocol.openai_api_protocol")

    class _DummyCompletionRequest:
        def __init__(self, **kwargs):
            for key, value in kwargs.items():
                setattr(self, key, value)

        def model_dump(self):
            return {}

    class _DummyCompletionResponse:
        pass

    class _DummyDebugConfig:
        pass

    class _DummyStreamOptions:
        def __init__(self, include_usage: bool = False):
            self.include_usage = include_usage

    openai_api_protocol_module.CompletionRequest = _DummyCompletionRequest
    openai_api_protocol_module.CompletionResponse = _DummyCompletionResponse
    openai_api_protocol_module.DebugConfig = _DummyDebugConfig
    openai_api_protocol_module.StreamOptions = _DummyStreamOptions
    monkeypatch.setitem(
        sys.modules, "mlc_llm.protocol.openai_api_protocol", openai_api_protocol_module
    )

    serve_module = types.ModuleType("mlc_llm.serve")

    class _DummyEngineConfig:  # pylint: disable=too-few-public-methods
        def __init__(self, prefix_cache_mode: str = "disable", gpu_memory_utilization=None):
            self.additional_models = []
            self.prefix_cache_mode = prefix_cache_mode
            self.gpu_memory_utilization = gpu_memory_utilization
            self.speculative_mode = "disable"
            self.max_num_sequence = None
            self.max_total_sequence_length = None
            self.prefill_chunk_size = None
            self.max_history_size = None
            self.spec_draft_length = None
            self.prefix_cache_max_num_recycling_seqs = None

    serve_module.EngineConfig = _DummyEngineConfig
    serve_module.PopenServer = _DummyServer
    monkeypatch.setitem(sys.modules, "mlc_llm.serve", serve_module)

    entrypoints_module = types.ModuleType("mlc_llm.serve.entrypoints")
    entrypoints_module.__path__ = []
    entrypoints_module.microserving_entrypoints = types.SimpleNamespace()
    monkeypatch.setitem(sys.modules, "mlc_llm.serve.entrypoints", entrypoints_module)

    tokenizers_module = types.ModuleType("mlc_llm.tokenizers")
    tokenizers_module.Tokenizer = _DummyTokenizer
    monkeypatch.setitem(sys.modules, "mlc_llm.tokenizers", tokenizers_module)

    tvm_module = types.ModuleType("tvm")
    tvm_module.get_global_func = lambda name: (lambda: [])
    monkeypatch.setitem(sys.modules, "tvm", tvm_module)

    tvm_base_module = types.ModuleType("tvm.base")
    tvm_base_module._RUNTIME_ONLY = False  # pylint: disable=protected-access
    monkeypatch.setitem(sys.modules, "tvm.base", tvm_base_module)

    tvm_runtime_module = types.ModuleType("tvm.runtime")
    tvm_runtime_module.Object = type("Object", (), {})
    tvm_runtime_module.Tensor = type("Tensor", (), {})
    monkeypatch.setitem(sys.modules, "tvm.runtime", tvm_runtime_module)

    router_pkg = types.ModuleType("mlc_llm.router")
    router_pkg.__path__ = [str(PYTHON_ROOT / "mlc_llm" / "router")]
    monkeypatch.setitem(sys.modules, "mlc_llm.router", router_pkg)

    spec = importlib.util.spec_from_file_location("mlc_llm.router.router", ROUTER_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setitem(sys.modules, "mlc_llm.router.router", module)
    return module


def test_router_defaults_to_one_gpu_per_endpoint(router_module):
    hosts = ["host-a", "host-b", "host-c"]
    ports = [8000, 8001, 8002]

    router = router_module.Router(model="dummy", hosts=hosts, ports=ports)

    try:
        # `device_id_starts` should advance by one for each endpoint, indicating the router
        # provisioned a single GPU per endpoint when ``num_gpus`` is omitted.
        assert router.device_id_starts == [0, 1, 2, 3]

        # Each dummy server receives a distinct CUDA device corresponding to the single GPU
        # assigned to the endpoint.
        devices = [server.started_with["device"] for server in router.servers]
        assert devices == ["cuda:0", "cuda:1", "cuda:2"]
    finally:
        router.terminate()
