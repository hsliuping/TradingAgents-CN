from core.memory.models import MemoryItem, StoreResult
from tradingagents.core.engine.memory_provider import Mem0CompatMemory, MemoryProvider
from tradingagents.agents.utils import memory as legacy_memory_module


class _FakeLegacyMemory:
    def __init__(self):
        self.add_calls = []
        self.get_calls = []

    def add_situations(self, situations_and_advice):
        self.add_calls.append(list(situations_and_advice))

    def get_memories(self, current_situation, n_matches=1):
        self.get_calls.append({"current_situation": current_situation, "n_matches": n_matches})
        return [{"situation": current_situation, "recommendation": "legacy", "similarity": 0.5, "distance": 0.5}]


class _FakeMemoryService:
    def __init__(self, *, store_result=None, recall_result=None):
        self.store_result = store_result or StoreResult(memory_ids=["m1"], facts_extracted=1)
        self.recall_result = list(recall_result or [])
        self.store_calls = []
        self.recall_calls = []

    async def store(self, messages, **kwargs):
        self.store_calls.append({"messages": messages, **kwargs})
        return self.store_result

    async def recall(self, **kwargs):
        self.recall_calls.append(kwargs)
        return list(self.recall_result)


def test_mem0_compat_memory_add_situations_stores_with_object_metadata(monkeypatch):
    fake_service = _FakeMemoryService()
    memory = Mem0CompatMemory("bull_memory", {"user_id": "user-1"})

    monkeypatch.setattr("core.memory.service.get_memory_service", lambda: fake_service)

    memory.add_situations([("贵州茅台 600519 基本面改善", "继续跟踪高端白酒需求与估值切换")])

    assert len(fake_service.store_calls) == 1
    call = fake_service.store_calls[0]
    assert call["user_id"] == "user-1"
    assert call["agent_id"] == "bull_researcher_v2"
    assert call["scope"] == "agent_experience"
    assert call["infer"] is False
    assert call["messages"] == [{"role": "user", "content": "Legacy situation:\n贵州茅台 600519 基本面改善\n\nRecommendation:\n继续跟踪高端白酒需求与估值切换"}]
    assert call["metadata"]["symbol"] == "600519"
    assert call["metadata"]["object_type"] == "stock"
    assert call["metadata"]["object_key"] == "600519"

def test_mem0_compat_memory_get_memories_prefers_v2_alias_for_migrated_records(monkeypatch):
    class _AliasAwareMemoryService(_FakeMemoryService):
        async def recall(self, **kwargs):
            self.recall_calls.append(kwargs)
            if kwargs.get("agent_id") == "bull_researcher_v2":
                return [
                    MemoryItem(
                        id="m-v2-1",
                        memory="推荐继续关注渠道改善",
                        score=0.91,
                        metadata={
                            "legacy_situation": "贵州茅台 600519 基本面改善",
                            "legacy_recommendation": "继续关注渠道改善",
                            "symbol": "600519",
                        },
                    )
                ]
            return []

    fake_service = _AliasAwareMemoryService()
    memory = Mem0CompatMemory("bull_memory", {"user_id": "user-1"})

    monkeypatch.setattr("core.memory.service.get_memory_service", lambda: fake_service)

    memories = memory.get_memories("请回顾 600519 的历史判断", n_matches=2)

    assert len(memories) == 1
    assert memories[0]["recommendation"] == "继续关注渠道改善"
    assert fake_service.recall_calls[0]["agent_id"] == "bull_researcher_v2"

def test_mem0_compat_memory_get_memories_falls_back_to_secondary_alias(monkeypatch):
    class _AliasAwareMemoryService(_FakeMemoryService):
        async def recall(self, **kwargs):
            self.recall_calls.append(kwargs)
            if kwargs.get("agent_id") == "bull_researcher":
                return [
                    MemoryItem(
                        id="m-v1-1",
                        memory="legacy recall",
                        score=0.88,
                        metadata={
                            "legacy_situation": "贵州茅台 600519 基本面改善",
                            "legacy_recommendation": "继续跟踪",
                            "symbol": "600519",
                        },
                    )
                ]
            return []

    fake_service = _AliasAwareMemoryService()
    memory = Mem0CompatMemory("bull_memory", {"user_id": "user-1"})

    monkeypatch.setattr("core.memory.service.get_memory_service", lambda: fake_service)

    memories = memory.get_memories("请回顾 600519 的历史判断", n_matches=1)

    assert len(memories) == 1
    assert [call["agent_id"] for call in fake_service.recall_calls] == ["bull_researcher_v2", "bull_researcher"]

def test_mem0_compat_memory_get_memories_formats_mem0_results(monkeypatch):
    fake_service = _FakeMemoryService(
        recall_result=[
            MemoryItem(
                id="m1",
                memory="推荐继续关注渠道改善",
                score=0.91,
                metadata={
                    "legacy_situation": "贵州茅台 600519 基本面改善",
                    "legacy_recommendation": "继续关注渠道改善",
                    "symbol": "600519",
                },
            )
        ]
    )
    memory = Mem0CompatMemory("invest_judge_memory", {"user_id": "user-1"})

    monkeypatch.setattr("core.memory.service.get_memory_service", lambda: fake_service)

    memories = memory.get_memories("请回顾 600519 的历史判断", n_matches=2)

    assert len(memories) == 1
    assert memories[0]["recommendation"] == "继续关注渠道改善"
    assert memories[0]["situation"] == "贵州茅台 600519 基本面改善"
    assert fake_service.recall_calls[0]["metadata_filters"] == {"symbol": "600519"}
def test_mem0_compat_memory_returns_empty_when_recall_empty(monkeypatch):
    fake_service = _FakeMemoryService(recall_result=[])
    memory = Mem0CompatMemory("risk_manager_memory", {"user_id": "user-1"})

    monkeypatch.setattr("core.memory.service.get_memory_service", lambda: fake_service)

    memories = memory.get_memories("没有股票代码的情境", n_matches=1)

    assert memories == []


def test_memory_provider_creates_mem0_compat_without_legacy_memory(monkeypatch):
    def _unexpected_legacy(*args, **kwargs):
        raise AssertionError("legacy memory should not be created in mem0 compat mode")

    monkeypatch.setattr(legacy_memory_module, "FinancialSituationMemory", _unexpected_legacy)

    provider = MemoryProvider(config={"memory_use_mem0_compat": True}, memory_enabled=True)
    memory = provider.get_memory("bull_memory")

    assert isinstance(memory, Mem0CompatMemory)
    assert memory.agent_id == "bull_researcher_v2"


def test_memory_provider_can_still_create_legacy_memory_when_mem0_compat_disabled(monkeypatch):
    fake_legacy = _FakeLegacyMemory()

    monkeypatch.setattr(legacy_memory_module, "FinancialSituationMemory", lambda memory_name, config: fake_legacy)

    provider = MemoryProvider(config={"memory_use_mem0_compat": False}, memory_enabled=True)
    memory = provider.get_memory("bull_memory")

    assert memory is fake_legacy