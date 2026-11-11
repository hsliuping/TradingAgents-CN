"""M2.3 模型分层单元测试（C5）：resolve_model_tier + _select_llm_type_for_agent。"""

import pytest

from core.workflow.builder import (
    MODEL_TIER_DEEP,
    MODEL_TIER_MIXED,
    MODEL_TIER_QUICK,
    _select_llm_type_for_agent,
    resolve_model_tier,
)


class TestResolveModelTier:
    """research_depth → profile.model_tier（quick/mixed/deep）。"""

    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("快速", MODEL_TIER_QUICK),
            (1, MODEL_TIER_QUICK),
            ("1", MODEL_TIER_QUICK),
            ("标准", MODEL_TIER_MIXED),
            (3, MODEL_TIER_MIXED),
            ("3", MODEL_TIER_MIXED),
            ("深度", MODEL_TIER_DEEP),
            (5, MODEL_TIER_DEEP),
            ("5", MODEL_TIER_DEEP),
        ],
    )
    def test_depth_to_tier(self, raw, expected):
        assert resolve_model_tier(raw) == expected

    def test_no_depth_context_fallback_mixed(self):
        # 无档位上下文（旧链路/自定义流）回退 mixed，行为与分层前一致
        assert resolve_model_tier(None) == MODEL_TIER_MIXED

    def test_unknown_depth_fallback_standard_mixed(self):
        assert resolve_model_tier("不存在的档") == MODEL_TIER_MIXED


class TestSelectLlmTypeByTier:
    """档位 model_tier → 角色 quick/deep 选择。"""

    def test_quick_tier_all_quick(self):
        for agent_id in ("market_analyst_v2", "research_manager_v2", "risk_self_debate_v2"):
            assert _select_llm_type_for_agent(agent_id, MODEL_TIER_QUICK) == "quick"

    def test_deep_tier_all_deep(self):
        for agent_id in ("market_analyst_v2", "news_analyst_v2", "bull_researcher_v2", "trader_v2"):
            assert _select_llm_type_for_agent(agent_id, MODEL_TIER_DEEP) == "deep"

    def test_mixed_tier_role_mapping_deep_roles(self):
        # 管理者（整合/裁决）、风险裁决、辩论载体、自包含分析师 → deep
        for agent_id in (
            "research_manager_v2", "risk_manager_v2",
            "risky_analyst_v2", "safe_analyst_v2", "neutral_analyst_v2",
            "risk_self_debate_v2", "research_self_debate_v2",
            "index_analyst_v2", "sector_analyst_v2",
        ):
            assert _select_llm_type_for_agent(agent_id, MODEL_TIER_MIXED) == "deep", agent_id

    def test_mixed_tier_role_mapping_quick_roles(self):
        # 分析师/研究员/交易员 → quick
        for agent_id in (
            "market_analyst_v2", "news_analyst_v2", "fundamentals_analyst_v2",
            "social_analyst_v2", "etf_analyst_v2",
            "bull_researcher_v2", "bear_researcher_v2", "trader_v2",
        ):
            assert _select_llm_type_for_agent(agent_id, MODEL_TIER_MIXED) == "quick", agent_id

    def test_legacy_debators_covered_by_single_mapping(self):
        # 旧链路遗留裁决角色收编进单一映射（与原遗留适配器内联名单等价）
        for agent_id in ("research_manager", "risk_manager", "risky_analyst", "safe_analyst", "neutral_analyst"):
            assert _select_llm_type_for_agent(agent_id, MODEL_TIER_MIXED) == "deep", agent_id

    def test_default_tier_is_mixed(self):
        assert _select_llm_type_for_agent("research_manager_v2") == "deep"
        assert _select_llm_type_for_agent("market_analyst_v2") == "quick"

    def test_unknown_agent_quick_under_mixed(self):
        assert _select_llm_type_for_agent("some_agent_v3", MODEL_TIER_MIXED) == "quick"
