"""
测试 reasoning_effort 档位映射与合并逻辑（A1：深度档位 × 推理预算）
"""
import pytest

from tradingagents.graph.trading_graph import (
    resolve_reasoning_efforts,
    _lower_reasoning_effort,
)


class TestLowerReasoningEffort:
    """快速模型降档函数"""

    def test_lower_two_steps(self):
        assert _lower_reasoning_effort("xhigh") == "medium"  # idx5 - 2 = idx3
        assert _lower_reasoning_effort("high") == "low"      # idx4 - 2 = idx2

    def test_floor_is_minimal(self):
        # minimal(idx1)/low(idx2) 降两档后不低于 minimal(idx1)，不降到 none
        assert _lower_reasoning_effort("minimal") == "minimal"
        assert _lower_reasoning_effort("low") == "minimal"

    def test_none_passthrough(self):
        assert _lower_reasoning_effort(None) is None

    def test_unknown_value_passthrough(self):
        assert _lower_reasoning_effort("weird-value") == "weird-value"


class TestResolveReasoningEfforts:
    """档位默认值的 provider 注入与 DB 优先级"""

    def test_non_volcengine_provider_not_injected(self):
        """非火山厂家：档位默认不注入"""
        config = {"llm_provider": "dashscope", "depth_reasoning_effort": "high"}
        quick, deep = resolve_reasoning_efforts(config, {}, {})
        assert quick is None
        assert deep is None

    def test_volcengine_coding_not_injected(self):
        """Coding Plan 不注入档位默认（code 模型语义不同）"""
        config = {"llm_provider": "volcengine_coding", "depth_reasoning_effort": "high"}
        quick, deep = resolve_reasoning_efforts(config, {}, {})
        assert quick is None
        assert deep is None

    def test_volcengine_agent_plan_injected(self):
        """Agent Plan：deep 取档位值，quick 降两档"""
        config = {"llm_provider": "volcengine", "depth_reasoning_effort": "high"}
        quick, deep = resolve_reasoning_efforts(config, {}, {})
        assert deep == "high"
        assert quick == "low"  # high(idx4) - 2 = low(idx2)

    def test_db_explicit_effort_takes_precedence(self):
        """DB 模型配置中的显式 effort 优先于档位默认"""
        config = {"llm_provider": "volcengine", "depth_reasoning_effort": "high"}
        quick_cfg = {"reasoning_effort": "max"}
        deep_cfg = {"reasoning_effort": "xhigh"}
        quick, deep = resolve_reasoning_efforts(config, quick_cfg, deep_cfg)
        assert quick == "max"
        assert deep == "xhigh"

    def test_mixed_provider_mode(self):
        """混合模式：quick/deep 来自不同厂家时分别判断"""
        config = {
            "llm_provider": "dashscope",
            "quick_provider": "dashscope",
            "deep_provider": "volcengine",
            "depth_reasoning_effort": "xhigh",
        }
        quick, deep = resolve_reasoning_efforts(config, {}, {})
        assert quick is None       # dashscope 不注入
        assert deep == "xhigh"     # 火山深度模型取档位值

    def test_no_depth_effort_returns_db_values(self):
        """无档位映射时原样返回 DB 值（向后兼容）"""
        config = {"llm_provider": "volcengine"}
        quick_cfg = {"reasoning_effort": "medium"}
        deep_cfg = {"reasoning_effort": "high"}
        quick, deep = resolve_reasoning_efforts(config, quick_cfg, deep_cfg)
        assert quick == "medium"
        assert deep == "high"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
