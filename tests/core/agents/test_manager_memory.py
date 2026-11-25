from typing import Any, Dict, List, Optional

from core.agents.factory import AgentFactory
from core.agents.manager import ManagerAgent
from core.agents.config import AgentMetadata, AgentCategory
from core.agents.adapters.risk_manager_v2 import RiskManagerV2


class _DummyLLM:
    def invoke(self, messages):
        class _Response:
            content = "manager decision"

        return _Response()


class _Mem0StyleMemory:
    def __init__(self):
        self.search_calls = []
        self.add_calls = []

    def search_memories(self, query, n_results=5, filter_metadata=None):
        self.search_calls.append(
            {"query": query, "n_results": n_results, "filter_metadata": filter_metadata}
        )
        return [{"content": "历史管理判断 A", "metadata": {"ticker": "300750"}, "similarity": 0.92}]

    def add_memory(self, content, metadata=None, memory_id=None):
        self.add_calls.append({"content": content, "metadata": metadata, "memory_id": memory_id})
        return True


class _TestManagerAgent(ManagerAgent):
    metadata = AgentMetadata(
        id="test_manager_agent",
        name="Test Manager Agent",
        description="test",
        category=AgentCategory.MANAGER,
    )
    manager_type = "research"
    output_field = "investment_plan"

    def _build_system_prompt(self, state: Dict[str, Any] = None) -> str:
        return "system"

    def _build_user_prompt(
        self,
        ticker: str,
        analysis_date: str,
        inputs: Dict[str, Any],
        debate_summary: Optional[str],
        state: Dict[str, Any],
    ) -> str:
        return debate_summary or "no history"

    def _get_required_inputs(self) -> List[str]:
        return ["bull_report", "bear_report"]


class _Registry:
    def get(self, agent_id):
        if agent_id == "test_manager_agent":
            return _TestManagerAgent
        return None

    def get_metadata(self, agent_id):
        if agent_id == "test_manager_agent":
            return _TestManagerAgent.metadata
        return None


def test_manager_agent_reads_history_from_mem0_style_memory():
    memory = _Mem0StyleMemory()
    agent = _TestManagerAgent(memory=memory)

    history = agent._get_memory_context("300750", {"bull_report": "bull", "bear_report": "bear"})

    assert "历史管理经验" in history
    assert "历史管理判断 A" in history
    assert memory.search_calls == [
        {
            "query": "股票代码: 300750\n管理者类型: research\n历史管理决策\nbull_report: bull\nbear_report: bear",
            "n_results": 3,
            "filter_metadata": {"ticker": "300750"},
        }
    ]


def test_manager_agent_execute_reads_and_writes_memory():
    memory = _Mem0StyleMemory()
    agent = _TestManagerAgent(memory=memory, llm=_DummyLLM())

    result = agent.execute(
        {
            "ticker": "300750",
            "analysis_date": "2026-04-08",
            "bull_report": "积极证据",
            "bear_report": "谨慎证据",
        }
    )

    assert result["investment_plan"]["content"] == "manager decision"
    assert len(memory.add_calls) == 1
    assert memory.add_calls[0]["metadata"]["ticker"] == "300750"
    assert memory.add_calls[0]["metadata"]["memory_kind"] == "manager_decision"


def test_agent_factory_passes_memory_to_manager_agents():
    memory = _Mem0StyleMemory()
    factory = AgentFactory(registry=_Registry())

    agent = factory.create("test_manager_agent", llm=_DummyLLM(), memory=memory)

    assert isinstance(agent, _TestManagerAgent)
    assert agent.memory is memory


class _FallbackRiskManager(RiskManagerV2):
    def _get_prompt_from_template(self, *args, **kwargs):
        del args, kwargs
        return None


def test_risk_manager_system_prompt_falls_back_when_template_missing():
    agent = _FallbackRiskManager(llm=_DummyLLM(), memory=_Mem0StyleMemory())

    prompt = agent._build_system_prompt({"ticker": "300750", "analysis_date": "2026-04-08"})

    assert "你是一位风险评估师" in prompt