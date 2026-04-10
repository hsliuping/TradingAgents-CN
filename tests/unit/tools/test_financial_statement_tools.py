"""基本面财报工具测试。"""

from core.agents.config import BUILTIN_AGENTS
from core.tools.implementations.fundamentals import stock_fundamentals as fundamentals_tools
from core.tools.registry import ToolRegistry


def _mock_financial_payload() -> dict:
    return {
        "ticker": "000001",
        "market_info": {
            "market_name": "中国A股",
            "is_china": True,
        },
        "data_source": "mock_cache",
        "income_statement": [
            {
                "end_date": "20240930",
                "revenue": 12800000000,
                "operate_profit": 2100000000,
                "n_income_attr_p": 1680000000,
                "n_income": 1650000000,
                "basic_eps": 1.23,
            },
            {
                "end_date": "20240630",
                "revenue": 11900000000,
                "n_income_attr_p": 1500000000,
                "basic_eps": 1.10,
            },
        ],
        "balance_sheet": [
            {
                "end_date": "20240930",
                "total_assets": 512000000000,
                "total_liab": 468000000000,
                "total_hldr_eqy_exc_min_int": 44000000000,
                "total_cur_assets": 188000000000,
                "total_cur_liab": 320000000000,
                "money_cap": 92000000000,
            }
        ],
        "cash_flow": [
            {
                "end_date": "20240930",
                "n_cashflow_act": 2250000000,
                "n_cashflow_inv_act": -980000000,
                "n_cash_flows_fnc_act": -420000000,
                "c_cash_equ_beg_period": 84500000000,
                "c_cash_equ_end_period": 86200000000,
            }
        ],
        "financial_indicators": [
            {
                "end_date": "20240930",
                "roe": 11.6,
                "roa": 0.84,
                "gross_margin": 35.2,
                "netprofit_margin": 12.9,
                "debt_to_assets": 91.4,
                "current_ratio": 0.88,
            }
        ],
    }


class TestFinancialStatementTools:
    def test_tools_registered(self):
        registry = ToolRegistry()

        assert registry.get_function("get_financial_statements") is not None
        assert registry.get_function("get_cash_flow_statement") is not None

    def test_financial_statements_output(self, monkeypatch):
        monkeypatch.setattr(
            fundamentals_tools,
            "_load_recent_financial_data",
            lambda ticker, limit=4: _mock_financial_payload(),
        )

        result = fundamentals_tools.get_financial_statements.invoke({"ticker": "000001", "limit": 4})

        assert "最近2个季度财报明细" in result
        assert "2024-09-30" in result
        assert "利润表" in result
        assert "资产负债表" in result
        assert "核心财务指标" in result
        assert "净资产收益率 ROE" in result

    def test_cash_flow_output(self, monkeypatch):
        monkeypatch.setattr(
            fundamentals_tools,
            "_load_recent_financial_data",
            lambda ticker, limit=4: _mock_financial_payload(),
        )

        result = fundamentals_tools.get_cash_flow_statement.invoke({"ticker": "000001", "limit": 4})

        assert "现金流量表" in result
        assert "经营活动现金流量净额" in result
        assert "投资活动现金流量净额" in result
        assert "经营现金净额/净利润" in result

    def test_agent_default_tools_binding(self):
        fundamentals_agent = BUILTIN_AGENTS.get("fundamentals_analyst")
        fundamentals_agent_v2 = BUILTIN_AGENTS.get("fundamentals_analyst_v2")

        assert fundamentals_agent is not None
        assert fundamentals_agent_v2 is not None

        for agent in (fundamentals_agent, fundamentals_agent_v2):
            assert "get_financial_statements" in agent.tools
            assert "get_cash_flow_statement" in agent.tools
            assert "get_financial_statements" in agent.default_tools
            assert "get_cash_flow_statement" in agent.default_tools