from typing import Any, Dict

from core.agents.researcher import ResearcherAgent


class _TestResearcherAgent(ResearcherAgent):
    researcher_type = "test"
    output_field = "test_report"
    stance = "bull"
    debate_state_field = "investment_debate_state"
    history_field = "bull_history"
    opponent_history_field = "bear_history"

    def _build_system_prompt(self, stance: str, state: Dict[str, Any] = None) -> str:
        return "system"

    def _build_user_prompt(self, ticker: str, analysis_date: str, reports: Dict[str, Any], historical_context: str, state: Dict[str, Any]) -> str:
        return historical_context or "user"

    def _get_required_reports(self):
        return ["market_report"]


class _Mem0StyleMemory:
    def __init__(self):
        self.search_calls = []
        self.add_calls = []

    def search_memories(self, query, n_results=5, filter_metadata=None):
        self.search_calls.append({"query": query, "n_results": n_results, "filter_metadata": filter_metadata})
        return [{"content": "历史研究经验 A", "similarity": 0.95, "metadata": {"ticker": "300750"}}]

    def add_memory(self, content, metadata=None, memory_id=None):
        self.add_calls.append({"content": content, "metadata": metadata, "memory_id": memory_id})
        return True


class _LegacyStyleMemory:
    pass


def test_researcher_agent_reads_history_from_mem0_style_memory():
    memory = _Mem0StyleMemory()
    agent = _TestResearcherAgent(memory=memory)

    context = agent._get_memory_context("300750", {"market_report": "当前报告"})

    assert "【历史经验】" in context
    assert "历史研究经验 A" in context
    assert memory.search_calls


def test_researcher_agent_skips_history_when_memory_lacks_search_interface():
    agent = _TestResearcherAgent(memory=_LegacyStyleMemory())

    context = agent._get_memory_context("300750", {"market_report": "当前报告"})

    assert context == ""


def test_researcher_agent_saves_to_mem0_style_memory():
    memory = _Mem0StyleMemory()
    agent = _TestResearcherAgent(memory=memory)

    agent._save_to_memory("300750", {"content": "新的研究报告"})

    assert len(memory.add_calls) == 1
    assert memory.add_calls[0]["metadata"]["ticker"] == "300750"
    assert memory.add_calls[0]["metadata"]["stance"] == "bull"


def test_researcher_agent_skips_save_when_memory_lacks_add_interface():
    agent = _TestResearcherAgent(memory=_LegacyStyleMemory())

    agent._save_to_memory("300750", {"content": "新的研究报告"})