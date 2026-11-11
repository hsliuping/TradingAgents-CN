"""M2.1/M2.2 档位契约块注入与工具预算单元测试（C4）。

验证 core/agents/base.py 提示词组装处的档位契约块注入（M2.1）
与 invoke_with_tools 工具预算解析（M2.2）。
"""

import pytest

from core.agents.base import DEFAULT_MAX_TOOL_ITERATIONS, BaseAgent
from core.agents.config import AgentCategory, AgentMetadata


class _DummyAgent(BaseAgent):
    metadata = AgentMetadata(
        id="dummy_analyst_v2",
        name="测试分析师",
        description="单元测试用 Agent",
        category=AgentCategory.ANALYST,
    )

    def execute(self, state):
        return {}


@pytest.fixture()
def agent():
    return _DummyAgent()


@pytest.fixture()
def template_stub(monkeypatch):
    """打桩模板系统（返回固定提示词），并跳过知识型 Skill 注入。"""
    import tradingagents.utils.template_client as template_client

    def _get_prompt(**kwargs):
        return "BASE_PROMPT"

    monkeypatch.setattr(template_client, "get_agent_prompt", _get_prompt)
    monkeypatch.setattr(template_client, "get_user_prompt", _get_prompt)
    monkeypatch.setattr(
        BaseAgent, "_load_bound_knowledge_skills", lambda self, name: None
    )


def _render(agent, state, agent_name="market_analyst_v2"):
    return agent._get_prompt_from_template(
        agent_type="analysts_v2",
        agent_name=agent_name,
        variables={},
        state=state,
        prompt_type="system",
    )


class TestContractInjection:
    def test_injects_contract_and_sets_budget(self, agent, template_stub):
        prompt = _render(agent, {"research_depth": "快速"})
        assert prompt.startswith("BASE_PROMPT")
        assert "【本档分析契约：快速档】" in prompt
        assert "口径纪律" in prompt
        assert "本档不含环节：风险会审、情景试算" in prompt
        assert agent._tool_budget == 2

    def test_deep_tier_budget_and_role_section(self, agent, template_stub):
        prompt = _render(agent, {"research_depth": "深度"}, agent_name="trader_v2")
        assert "【本档分析契约：深度档】" in prompt
        assert "报告章节要求" in prompt
        assert agent._tool_budget == 15

    def test_no_depth_no_injection(self, agent, template_stub):
        prompt = _render(agent, {})
        assert prompt == "BASE_PROMPT"
        assert "档位契约" not in prompt
        assert agent._tool_budget is None

    def test_unknown_depth_fallback_to_standard(self, agent, template_stub):
        prompt = _render(agent, {"research_depth": "不存在的档"})
        assert "【本档分析契约：标准档】" in prompt
        assert agent._tool_budget == 6

    def test_budget_reset_without_depth(self, agent, template_stub):
        _render(agent, {"research_depth": "深度"})
        assert agent._tool_budget == 15
        _render(agent, {})
        assert agent._tool_budget is None


class TestToolBudgetResolution:
    def test_explicit_wins(self, agent):
        agent._tool_budget = 2
        assert agent._resolve_tool_budget(7) == 7

    def test_profile_budget_used(self, agent):
        agent._tool_budget = 2
        assert agent._resolve_tool_budget(None) == 2

    def test_default_fallback(self, agent):
        assert agent._tool_budget is None
        assert agent._resolve_tool_budget(None) == DEFAULT_MAX_TOOL_ITERATIONS
