import asyncio
import json
from concurrent.futures import Future
import sys
import types

from app.routers import memory as memory_router
from core.llm.models import LLMConfig, LLMProvider
from core.memory.config import build_mem0_config, _read_active_system_config
from core.memory.service import MemoryService


def test_memory_health_returns_503_when_mem0_unavailable(monkeypatch):
    class DummyMemoryService:
        async def health_check(self):
            return {
                "ok": False,
                "error": "缺少 LLM API Key，mem0 记忆层不可用",
            }

    monkeypatch.setattr("core.memory.service.get_memory_service", lambda db: DummyMemoryService())

    response = asyncio.run(memory_router.memory_health(db=object()))
    payload = json.loads(response.body.decode("utf-8"))

    assert response.status_code == 503
    assert payload["success"] is False
    assert payload["data"]["ok"] is False
    assert payload["message"] == "缺少 LLM API Key，mem0 记忆层不可用"


def test_memory_health_returns_200_when_mem0_available(monkeypatch):
    class DummyMemoryService:
        async def health_check(self):
            return {
                "ok": True,
                "mem0_version": "1.0.0",
            }

    monkeypatch.setattr("core.memory.service.get_memory_service", lambda db: DummyMemoryService())

    response = asyncio.run(memory_router.memory_health(db=object()))
    payload = json.loads(response.body.decode("utf-8"))

    assert response.status_code == 200
    assert payload["success"] is True
    assert payload["data"]["ok"] is True


def test_memory_service_health_check_builds_mem0_config_once(monkeypatch):
    build_calls = {"count": 0}

    def fake_build_mem0_config(_db=None):
        build_calls["count"] += 1
        return {
            "llm": {
                "provider": "openai",
                "config": {
                    "api_key": "",
                    "model": "deepseek-chat",
                },
            },
            "embedder": {
                "provider": "gemini",
                "config": {
                    "model": "models/text-embedding-004",
                    "api_key": "embed-key",
                    "embedding_dims": 768,
                },
            },
            "vector_store": {
                "provider": "qdrant",
                "config": {
                    "collection_name": "mem0_test",
                    "path": "./data/qdrant/mem0",
                    "on_disk": True,
                },
            },
        }

    dummy_mem0 = types.ModuleType("mem0")
    dummy_mem0.__version__ = "1.0.0"

    class DummyAsyncMemory:
        @staticmethod
        def from_config(_config):
            raise AssertionError("缺少 LLM API Key 时不应真正初始化 AsyncMemory")

    dummy_mem0.AsyncMemory = DummyAsyncMemory

    monkeypatch.setitem(sys.modules, "mem0", dummy_mem0)
    monkeypatch.setattr("core.memory.config.build_mem0_config", fake_build_mem0_config)

    svc = MemoryService(db=object())
    result = asyncio.run(svc.health_check())

    assert build_calls["count"] == 1
    assert result["ok"] is False
    assert result["error"] == "缺少 LLM API Key，mem0 记忆层不可用"
    assert result["diagnostics"]["llm"]["has_api_key"] is False


def test_build_mem0_config_reuses_unified_llm_resolution(monkeypatch):
    config_doc = {
        "system_settings": {
            "quick_analysis_model": "",
            "quick_analysis_model_config_id": "cfg-google",
            "default_embedding_model": "",
        },
        "llm_configs": [
            {
                "config_id": "cfg-google",
                "provider": "google",
                "model_name": "gemini-2.5-flash",
                "enabled": True,
            }
        ],
    }

    monkeypatch.setattr("core.memory.config._read_active_system_config", lambda _db=None: config_doc)
    monkeypatch.setattr("core.memory.config._resolve_embedding_from_db", lambda _settings: {})
    monkeypatch.setattr(
        "app.services.intelligent_assistant_service.get_system_llm_config_from_config_doc",
        lambda _doc, model_keys=None: LLMConfig(
            provider=LLMProvider.GOOGLE,
            model="gemini-2.5-flash",
            api_key="google-key",
            base_url=None,
            temperature=0.2,
            max_tokens=4096,
            timeout=60,
        ),
    )

    config = build_mem0_config()

    assert config["llm"]["provider"] == "gemini"
    assert config["llm"]["config"]["api_key"] == "google-key"
    assert config["llm"]["config"]["model"] == "models/gemini-2.5-flash"


def test_read_active_system_config_falls_back_for_async_proxy(monkeypatch):
    class DummyCollection:
        def find_one(self, *_args, **_kwargs):
            future = Future()
            future.set_result({"unexpected": True})
            return future

    class DummyAsyncProxy:
        system_configs = DummyCollection()

    sync_doc = {"system_settings": {"quick_analysis_model": "qwen-plus"}, "llm_configs": []}

    class DummySyncCollection:
        def find_one(self, *_args, **_kwargs):
            return sync_doc

    class DummySyncDb:
        system_configs = DummySyncCollection()

    monkeypatch.setattr("core.memory.config._get_sync_db", lambda: DummySyncDb())

    result = _read_active_system_config(DummyAsyncProxy())

    assert result == sync_doc