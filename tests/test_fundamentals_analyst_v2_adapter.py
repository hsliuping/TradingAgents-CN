from langchain_core.messages import HumanMessage


def test_build_user_prompt_keeps_state_company_name_when_market_lookup_empty(monkeypatch):
    from core.agents.adapters import fundamentals_analyst_v2 as module

    agent = module.FundamentalsAnalystAgentV2()
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
    agent._get_prompt_from_template = fake_get_prompt_from_template

    prompt = agent._build_user_prompt(
        ticker="000001",
        trade_date="2026-04-10",
        state={"company_name": "平安银行"},
    )

    assert prompt == "PROMPT"
    assert captured["variables"]["company_name"] == "平安银行"


def test_execute_prefetches_required_china_tools_and_uses_analysis_prompt(monkeypatch):
    from core.agents.adapters import fundamentals_analyst_v2 as module

    agent = module.FundamentalsAnalystAgentV2()
    agent._llm = object()

    prefetched_calls = []

    class FakeTool:
        def __init__(self, name, result):
            self.name = name
            self._result = result

        def invoke(self, tool_args):
            prefetched_calls.append((self.name, tool_args))
            return self._result

    class FakeStockUtils:
        @staticmethod
        def get_market_info(ticker):
            return {"is_china": True, "market_name": "中国A股"}

    monkeypatch.setattr(module, "StockUtils", FakeStockUtils)

    agent._langchain_tools = [
        FakeTool("get_stock_fundamentals_unified", "UNIFIED"),
        FakeTool("get_financial_statements", "FINANCIALS"),
        FakeTool("get_cash_flow_statement", "CASHFLOW"),
        FakeTool("get_peer_comparison", "PEERS"),
    ]

    agent._build_system_prompt = lambda state: "SYSTEM"
    agent._build_user_prompt = lambda ticker, trade_date, state: "USER"
    agent._build_analysis_prompt = lambda ticker: "ANALYSIS"

    captured = {}

    def fake_invoke_with_tools(messages, analysis_prompt=None, max_iterations=3):
        captured["messages"] = messages
        captured["analysis_prompt"] = analysis_prompt
        captured["tools_during_call"] = [tool.name for tool in agent._langchain_tools]
        return "REPORT"

    agent.invoke_with_tools = fake_invoke_with_tools

    result = agent.execute({
        "ticker": "000001",
        "trade_date": "2026-04-10",
        "company_name": "平安银行",
    })

    assert result["fundamentals_report"] == "REPORT"
    assert captured["analysis_prompt"] == "ANALYSIS"
    assert captured["tools_during_call"] == ["get_peer_comparison"]
    assert [name for name, _ in prefetched_calls] == [
        "get_stock_fundamentals_unified",
        "get_financial_statements",
        "get_cash_flow_statement",
    ]

    prefetch_messages = [msg for msg in captured["messages"] if isinstance(msg, HumanMessage) and "已预先获取" in msg.content]
    assert len(prefetch_messages) == 1
    assert "UNIFIED" in prefetch_messages[0].content
    assert "FINANCIALS" in prefetch_messages[0].content
    assert "CASHFLOW" in prefetch_messages[0].content
