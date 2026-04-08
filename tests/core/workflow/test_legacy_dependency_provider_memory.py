from core.workflow import builder as builder_module
from tradingagents.core.engine import memory_provider as memory_provider_module


class _FakeMemoryProvider:
    def __init__(self, config=None, memory_enabled=True):
        self.config = config or {}
        self.memory_enabled = memory_enabled
        self.requested = []

    def get_memory(self, memory_type):
        self.requested.append(memory_type)
        return {"memory_type": memory_type}


def test_legacy_dependency_provider_uses_memory_provider(monkeypatch):
    fake_provider = _FakeMemoryProvider()

    builder_module.LegacyDependencyProvider.reset_instance()
    monkeypatch.setattr(memory_provider_module, "MemoryProvider", lambda config=None, memory_enabled=True: fake_provider)

    provider = builder_module.LegacyDependencyProvider({"memory_enabled": True})

    provider._create_memory("bull_memory")

    assert fake_provider.requested == ["bull_memory"]
    assert provider.get_memory("bull_memory") == {"memory_type": "bull_memory"}


def test_legacy_dependency_provider_resets_memory_cache_on_config_update():
    builder_module.LegacyDependencyProvider.reset_instance()

    provider = builder_module.LegacyDependencyProvider.get_instance({"memory_enabled": True})
    provider._memories["bull_memory"] = {"memory_type": "bull_memory"}
    provider._memory_provider = object()

    refreshed = builder_module.LegacyDependencyProvider.get_instance({"memory_use_mem0_compat": True})

    assert refreshed is provider
    assert refreshed._memories == {}
    assert refreshed._memory_provider is None
