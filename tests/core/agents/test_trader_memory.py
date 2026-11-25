from typing import Any, Dict, List, Optional

from core.agents.trader import TraderAgent


class _TestTraderAgent(TraderAgent):
    def _build_system_prompt(self, state: Dict[str, Any] = None) -> str:
        return "system"

    def _build_user_prompt(
        self,
        ticker: str,
        analysis_date: str,
        investment_plan: Dict[str, Any],
        all_reports: Dict[str, Any],
        historical_trades: Optional[List[Dict[str, Any]]],
        state: Dict[str, Any],
    ) -> str:
        return "user"


class _Mem0StyleMemory:
    def __init__(self):
        self.search_calls = []
        self.add_calls = []

    def search_memories(self, query, n_results=5, filter_metadata=None):
        self.search_calls.append(
            {"query": query, "n_results": n_results, "filter_metadata": filter_metadata}
        )
        return [
            {
                "content": "历史交易计划 A",
                "metadata": {"ticker": "300750", "source": "mem0"},
                "similarity": 0.93,
            }
        ]

    def add_memory(self, content, metadata=None, memory_id=None):
        self.add_calls.append({"content": content, "metadata": metadata, "memory_id": memory_id})
        return True


class _LegacyStyleMemory:
    def __init__(self):
        self.get_calls = []
        self.add_calls = []

    def get_memories(self, current_situation, n_matches=1):
        self.get_calls.append({"current_situation": current_situation, "n_matches": n_matches})
        return [
            {
                "situation": "股票代码: 300750\n交易分析计划",
                "recommendation": "历史交易计划 B",
                "similarity": 0.81,
            }
        ]

    def add_situations(self, situations_and_advice):
        self.add_calls.append(list(situations_and_advice))


def test_trader_agent_get_historical_trades_from_mem0_style_memory():
    memory = _Mem0StyleMemory()
    agent = _TestTraderAgent(memory=memory)

    memories = agent._get_historical_trades("300750")

    assert memories == [
        {
            "content": "历史交易计划 A",
            "metadata": {"ticker": "300750", "source": "mem0"},
            "similarity": 0.93,
        }
    ]
    assert memory.search_calls == [
        {
            "query": "股票代码: 300750\n交易分析计划\n历史交易经验",
            "n_results": 3,
            "filter_metadata": {"ticker": "300750"},
        }
    ]


def test_trader_agent_returns_none_when_memory_lacks_search_interface():
    memory = _LegacyStyleMemory()
    agent = _TestTraderAgent(memory=memory)

    memories = agent._get_historical_trades("300750")

    assert memories is None
    assert memory.get_calls == []


def test_trader_agent_save_to_mem0_style_memory():
    memory = _Mem0StyleMemory()
    agent = _TestTraderAgent(memory=memory)

    agent._save_to_memory("300750", {"content": "新的交易分析计划", "market_view": "bullish"})

    assert len(memory.add_calls) == 1
    call = memory.add_calls[0]
    assert call["content"] == "{\"content\": \"新的交易分析计划\", \"market_view\": \"bullish\"}"
    assert call["metadata"]["ticker"] == "300750"
    assert call["metadata"]["agent_id"] == agent.agent_id
    assert call["metadata"]["memory_kind"] == "trader_plan"
    assert call["metadata"]["output_field"] == agent.output_field


def test_trader_agent_skips_save_when_memory_lacks_add_interface():
    memory = _LegacyStyleMemory()
    agent = _TestTraderAgent(memory=memory)

    agent._save_to_memory("300750", {"content": "新的交易分析计划", "market_view": "bullish"})

    assert memory.add_calls == []