"""
测试 ConditionalLogic 是否正确接收配置参数
验证辩论轮次配置是否正确传递到 TradingAgentsGraph
"""
import pytest
from tradingagents.graph.conditional_logic import ConditionalLogic
from tradingagents.graph.trading_graph import TradingAgentsGraph
from tradingagents.default_config import DEFAULT_CONFIG


@pytest.fixture(autouse=True)
def stub_graph_llms(monkeypatch):
    """这些测试只关心配置传递，不需要真实 LLM 初始化。"""
    import tradingagents.graph.trading_graph as trading_graph_module
    import app.services.simple_analysis_service as simple_analysis_service

    class _DummyLLM:
        def __init__(self, *args, **kwargs):
            self.kwargs = kwargs

        def bind_tools(self, tools):
            return self

    monkeypatch.setattr(trading_graph_module, "ChatDashScopeOpenAI", _DummyLLM, raising=True)
    monkeypatch.setattr(trading_graph_module, "ChatGoogleOpenAI", _DummyLLM, raising=True)
    monkeypatch.setattr(
        simple_analysis_service,
        "get_provider_and_url_by_model_sync",
        lambda model_name: {
            "provider": "dashscope",
            "backend_url": "https://dashscope.aliyuncs.com/api/v1",
            "api_key": "sk-test-placeholder-001",
        },
        raising=True,
    )


class TestConditionalLogicConfig:
    """测试 ConditionalLogic 配置传递"""

    def test_conditional_logic_default_params(self):
        """测试 ConditionalLogic 默认参数"""
        logic = ConditionalLogic()
        
        assert logic.max_debate_rounds == 1
        assert logic.max_risk_discuss_rounds == 1

    def test_conditional_logic_custom_params(self):
        """测试 ConditionalLogic 自定义参数"""
        logic = ConditionalLogic(max_debate_rounds=3, max_risk_discuss_rounds=2)
        
        assert logic.max_debate_rounds == 3
        assert logic.max_risk_discuss_rounds == 2

    def test_trading_graph_with_level_4_config(self):
        """测试 TradingGraph 使用4级深度配置"""
        config = DEFAULT_CONFIG.copy()
        config["max_debate_rounds"] = 2
        config["max_risk_discuss_rounds"] = 2
        config["research_depth"] = "深度"
        
        graph = TradingAgentsGraph(
            selected_analysts=["market"],
            config=config
        )
        
        # 🔥 关键断言：ConditionalLogic 应该接收到正确的配置
        assert graph.conditional_logic.max_debate_rounds == 2, \
            f"4级深度分析应该有2轮辩论，实际是{graph.conditional_logic.max_debate_rounds}"
        assert graph.conditional_logic.max_risk_discuss_rounds == 2, \
            f"4级深度分析应该有2轮风险讨论，实际是{graph.conditional_logic.max_risk_discuss_rounds}"

    def test_trading_graph_with_level_5_config(self):
        """测试 TradingGraph 使用5级深度配置"""
        config = DEFAULT_CONFIG.copy()
        config["max_debate_rounds"] = 3
        config["max_risk_discuss_rounds"] = 3
        config["research_depth"] = "全面"
        
        graph = TradingAgentsGraph(
            selected_analysts=["market"],
            config=config
        )
        
        # 🔥 关键断言：ConditionalLogic 应该接收到正确的配置
        assert graph.conditional_logic.max_debate_rounds == 3, \
            f"5级全面分析应该有3轮辩论，实际是{graph.conditional_logic.max_debate_rounds}"
        assert graph.conditional_logic.max_risk_discuss_rounds == 3, \
            f"5级全面分析应该有3轮风险讨论，实际是{graph.conditional_logic.max_risk_discuss_rounds}"

    def test_trading_graph_without_config(self):
        """测试 TradingGraph 不传配置时使用默认值"""
        graph = TradingAgentsGraph(selected_analysts=["market"])
        
        # 应该使用默认配置
        assert graph.conditional_logic.max_debate_rounds == 1
        assert graph.conditional_logic.max_risk_discuss_rounds == 1

    def test_trading_graph_with_partial_config(self):
        """测试 TradingGraph 部分配置"""
        config = DEFAULT_CONFIG.copy()
        config["max_debate_rounds"] = 5  # 只设置辩论轮次
        
        graph = TradingAgentsGraph(
            selected_analysts=["market"],
            config=config
        )
        
        assert graph.conditional_logic.max_debate_rounds == 5
        assert graph.conditional_logic.max_risk_discuss_rounds == 1  # 使用默认值


class TestDebateRoundsProgression:
    """测试辩论轮次的递进关系"""

    @pytest.mark.parametrize("level,debate_rounds,risk_rounds", [
        (1, 1, 1),  # 快速
        (2, 1, 1),  # 基础
        (3, 1, 2),  # 标准
        (4, 2, 2),  # 深度
        (5, 3, 3),  # 全面
    ])
    def test_debate_rounds_by_level(self, level, debate_rounds, risk_rounds):
        """测试不同级别的辩论轮次"""
        from app.services.simple_analysis_service import create_analysis_config
        
        config_dict = create_analysis_config(
            research_depth=level,
            selected_analysts=["market"],
            quick_model="qwen-plus",
            deep_model="qwen-max",
            llm_provider="dashscope",
            market_type="A股"
        )
        
        # 创建 TradingGraph 并验证配置传递
        graph = TradingAgentsGraph(
            selected_analysts=["market"],
            config=config_dict
        )
        
        assert graph.conditional_logic.max_debate_rounds == debate_rounds, \
            f"级别{level}的辩论轮次应该是{debate_rounds}，实际是{graph.conditional_logic.max_debate_rounds}"
        assert graph.conditional_logic.max_risk_discuss_rounds == risk_rounds, \
            f"级别{level}的风险讨论轮次应该是{risk_rounds}，实际是{graph.conditional_logic.max_risk_discuss_rounds}"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
