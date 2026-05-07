def test_build_user_prompt_keeps_state_company_name_when_market_lookup_empty(monkeypatch):
    from core.agents.adapters import market_analyst_v2 as module

    agent = module.MarketAnalystV2()
    captured = {}

    class FakeStockUtils:
        @staticmethod
        def get_market_info(ticker):
            return {
                "market_name": "中国A股",
                "currency_name": "人民币",
                "currency_symbol": "¥",
                "company_name": "",
            }

    def fake_get_prompt_from_template(*args, **kwargs):
        captured["variables"] = kwargs["variables"]
        return "PROMPT"

    monkeypatch.setattr(module, "StockUtils", FakeStockUtils)
    agent._get_company_name = lambda ticker, market_info: ""
    agent._get_prompt_from_template = fake_get_prompt_from_template

    prompt = agent._build_user_prompt(
        ticker="000001",
        analysis_date="2026-04-13",
        state={"company_name": "平安银行"},
    )

    assert prompt == "PROMPT"
    assert captured["variables"]["company_name"] == "平安银行"


def test_execute_uses_default_analysis_prompt(monkeypatch):
    from core.agents.adapters import market_analyst_v2 as module

    agent = module.MarketAnalystV2()
    agent._llm = object()
    agent._langchain_tools = [type("FakeTool", (), {"name": "get_stock_market_data_unified"})()]

    monkeypatch.setattr(module, "StockUtils", None)

    agent._build_system_prompt = lambda market_type=None, context=None, state=None: "SYSTEM"
    agent._build_user_prompt = lambda ticker, analysis_date, state: "USER"
    agent._build_analysis_prompt = lambda ticker: "ANALYSIS"

    captured = {}

    def fake_invoke_with_tools(messages, analysis_prompt=None, max_iterations=3):
        captured["analysis_prompt"] = analysis_prompt
        captured["message_count"] = len(messages)
        return "REPORT"

    agent.invoke_with_tools = fake_invoke_with_tools

    result = agent.execute({
        "ticker": "000001",
        "analysis_date": "2026-04-13",
        "company_name": "平安银行",
    })

    assert result["market_report"] == "REPORT"
    assert captured["analysis_prompt"] == "ANALYSIS"
    assert captured["message_count"] == 2


def test_default_analysis_prompt_contains_latest_observation_guards():
    from core.agents.adapters import market_analyst_v2 as module

    agent = module.MarketAnalystV2()
    prompt = agent._build_analysis_prompt("000001")

    assert "禁止把分析日期直接写成实际数据日期" in prompt
    assert "尚未站稳于MA5之上" in prompt
    assert "柱状图是否出现持续放大" in prompt
    assert "具备一定上行空间" in prompt
    assert "输出前必须做一次逐词自检" in prompt


def test_sanitize_report_removes_threshold_language():
    from core.agents.adapters import market_analyst_v2 as module

    agent = module.MarketAnalystV2()
    original = (
        "价格尚未站上MA5，未能有效站稳于其上方。未突破布林带上轨，上行空间受限。\n"
        "1. 价格与MA5的偏离是否收敛，能否实现有效站稳。\n"
        "2. MACD正值状态是否延续，柱状图是否出现持续放大或收缩。"
    )

    sanitized = agent._sanitize_report(original)

    assert "站上" not in sanitized
    assert "站稳" not in sanitized
    assert "有效突破" not in sanitized
    assert "持续放大" not in sanitized
    assert "上行空间" not in sanitized
    assert "突破布林带上轨" not in sanitized
    assert "仍低于MA5" in sanitized
    assert "短期均线关系是否改善" in sanitized
    assert "动能一致性是否增强或减弱" in sanitized


def test_sanitize_report_keeps_breakout_rewrite_fluent():
    from core.agents.adapters import market_analyst_v2 as module

    agent = module.MarketAnalystV2()
    original = "布林带位置仅说明当前价格处于相对高位区间，尚未形成有效突破信号。"

    sanitized = agent._sanitize_report(original)

    assert sanitized == "布林带位置仅说明当前价格处于相对高位区间，上破依据仍不足。"


def test_sanitize_report_rewrites_snapshot_as_relationships():
    from core.agents.adapters import market_analyst_v2 as module

    agent = module.MarketAnalystV2()
    original = (
        "价格尚未突破MA5，说明短期动能修复尚未完成对短期均线上方的确认。"
        "该区间范围较前期有所收窄，表明短期波动趋于收敛。"
        "短期均线系统存在向上排列趋势，但缺乏上行突破动力。"
    )

    sanitized = agent._sanitize_report(original)

    assert "尚未突破MA5" not in sanitized
    assert "对短期均线上方的确认" not in sanitized
    assert "较前期有所收窄" not in sanitized
    assert "向上排列趋势" not in sanitized
    assert "上行突破动力" not in sanitized
    assert "仍低于MA5" in sanitized
    assert "与短期均线关系改善的确认" in sanitized
    assert "显示短期波动集中在当前区间内" in sanitized
    assert "偏强排列" in sanitized
    assert "进一步走强依据" in sanitized