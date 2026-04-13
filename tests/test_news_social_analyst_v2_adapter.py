def test_news_execute_uses_default_analysis_prompt(monkeypatch):
    from core.agents.adapters import news_analyst_v2 as module

    agent = module.NewsAnalystV2()
    agent._llm = object()
    agent._langchain_tools = [type("FakeTool", (), {"name": "get_stock_news_unified"})()]

    monkeypatch.setattr(module, "StockUtils", None)

    agent._build_system_prompt = lambda market_type=None, context=None, state=None: "SYSTEM"
    agent._build_user_prompt = lambda ticker, analysis_date, tool_data, state: "USER"
    agent._build_analysis_prompt = lambda ticker: "ANALYSIS"

    captured = {}

    def fake_invoke_with_tools(messages, analysis_prompt=None, max_iterations=3):
        captured["analysis_prompt"] = analysis_prompt
        captured["message_count"] = len(messages)
        return "REPORT"

    agent.invoke_with_tools = fake_invoke_with_tools

    result = agent.execute(
        {
            "ticker": "000001",
            "analysis_date": "2026-04-13",
            "company_name": "平安银行",
        }
    )

    assert result["news_report"] == "REPORT"
    assert captured["analysis_prompt"] == "ANALYSIS"
    assert captured["message_count"] == 2


def test_news_default_analysis_prompt_contains_legacy_structure_guards():
    from core.agents.adapters import news_analyst_v2 as module

    agent = module.NewsAnalystV2()
    prompt = agent._build_analysis_prompt("000001")

    assert "最新新闻汇总" in prompt
    assert "新闻影响分析" in prompt
    assert "市场情绪评估" in prompt
    assert "分析观点" in prompt
    assert "多个标题本质上描述同一事件" in prompt
    assert "短期反应预期" in prompt
    assert "无需单列章节" in prompt
    assert "不要输出投资建议、目标价、价格区间、仓位或执行计划" in prompt


def test_social_execute_uses_default_analysis_prompt(monkeypatch):
    from core.agents.adapters import social_analyst_v2 as module

    agent = module.SocialMediaAnalystV2()
    agent._llm = object()
    agent._langchain_tools = [type("FakeTool", (), {"name": "get_stock_sentiment_unified"})()]

    monkeypatch.setattr(module, "StockUtils", None)

    agent._build_system_prompt = lambda market_type=None, context=None, state=None: "SYSTEM"
    agent._build_user_prompt = lambda ticker, analysis_date, tool_data, state: "USER"
    agent._build_analysis_prompt = lambda ticker: "ANALYSIS"

    captured = {}

    def fake_invoke_with_tools(messages, analysis_prompt=None, max_iterations=3):
        captured["analysis_prompt"] = analysis_prompt
        captured["message_count"] = len(messages)
        return "REPORT"

    agent.invoke_with_tools = fake_invoke_with_tools

    result = agent.execute(
        {
            "ticker": "000001",
            "analysis_date": "2026-04-13",
            "company_name": "平安银行",
        }
    )

    assert result["sentiment_report"] == "REPORT"
    assert captured["analysis_prompt"] == "ANALYSIS"
    assert captured["message_count"] == 2


def test_social_default_analysis_prompt_contains_dimension_guards():
    from core.agents.adapters import social_analyst_v2 as module

    agent = module.SocialMediaAnalystV2()
    prompt = agent._build_analysis_prompt("000001")

    assert "如果工具明确说明当前结果来自新闻回退情绪摘要" in prompt
    assert "不要分析该维度" in prompt
    assert "不要使用“情绪拐点已至”" in prompt
    assert "不要输出投资建议、目标价、价格区间、仓位或执行计划" in prompt
