"""基本面财报工具测试。"""

import pandas as pd

from core.agents.config import BUILTIN_AGENTS
from core.tools.implementations.fundamentals import stock_fundamentals as fundamentals_tools
from core.tools.registry import ToolRegistry
from tradingagents.utils.stock_utils import StockUtils


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
    def test_load_recent_financial_data_prefers_db_cache(self, monkeypatch):
        db_payload = _mock_financial_payload()

        class FakeOptimizedProvider:
            def _get_cached_raw_financial_data(self, ticker):
                assert ticker == "000001"
                return db_payload

        class ForbiddenTushareProvider:
            def get_financial_data(self, *args, **kwargs):
                raise AssertionError("命中数据库后不应调用 Tushare")

        class ForbiddenAKShareProvider:
            def get_financial_data(self, *args, **kwargs):
                raise AssertionError("命中数据库后不应调用 AKShare")

        monkeypatch.setattr(
            "tradingagents.dataflows.optimized_china_data.OptimizedChinaDataProvider",
            FakeOptimizedProvider,
        )
        monkeypatch.setattr(
            "tradingagents.dataflows.providers.china.tushare.TushareProvider",
            ForbiddenTushareProvider,
        )
        monkeypatch.setattr(
            "tradingagents.dataflows.providers.china.akshare.AKShareProvider",
            ForbiddenAKShareProvider,
        )

        result = fundamentals_tools._load_recent_financial_data("000001.SZ", limit=4)

        assert result["ticker"] == "000001"
        assert result["data_source"] == "optimized_cache"
        assert result["income_statement"]
        assert result["cash_flow"]

    def test_stock_utils_supports_a_share_suffixes(self):
        for ticker in ("000001.SZ", "600000.SH", "430001.BJ"):
            market_info = StockUtils.get_market_info(ticker)

            assert market_info["is_china"] is True
            assert market_info["market_name"] == "中国A股"

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

    def test_financial_statement_tools_prefer_db_loaded_payload(self, monkeypatch):
        captured = []

        def fake_loader(ticker, limit=4):
            captured.append((ticker, limit))
            payload = _mock_financial_payload()
            payload["data_source"] = "optimized_cache"
            return payload

        monkeypatch.setattr(fundamentals_tools, "_load_recent_financial_data", fake_loader)

        financial_result = fundamentals_tools.get_financial_statements.invoke({"ticker": "000001.SZ", "limit": 4})
        cash_flow_result = fundamentals_tools.get_cash_flow_statement.invoke({"ticker": "000001.SZ", "limit": 4})

        assert captured == [("000001.SZ", 4), ("000001.SZ", 4)]
        assert "**数据来源**: optimized_cache" in financial_result
        assert "**数据来源**: optimized_cache" in cash_flow_result

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

    def test_unified_fundamentals_unknown_market_does_not_fall_back_to_us(self):
        result = fundamentals_tools.get_stock_fundamentals_unified.invoke({"ticker": "INVALID.CODE"})

        assert "未识别到受支持的股票市场" in result
        assert "美股基本面数据" not in result

    def test_unified_fundamentals_prefers_db_snapshot_for_china(self, monkeypatch):
        captured = {}

        class FakeAnalyzer:
            def _get_stock_basic_info_only(self, ticker):
                raise AssertionError("不应回退到基础信息 provider")

            def _generate_fundamentals_report(self, ticker, stock_data, analysis_modules="standard"):
                captured["ticker"] = ticker
                captured["stock_data"] = stock_data
                captured["analysis_modules"] = analysis_modules
                return "mock fundamentals"

        monkeypatch.setattr(
            "tradingagents.dataflows.cache.app_adapter.get_basics_from_cache",
            lambda ticker: {
                "code": ticker,
                "name": "平安银行",
                "area": "深圳",
                "industry": "银行",
                "market": "主板",
                "list_date": "19910403",
            },
        )
        monkeypatch.setattr(
            "tradingagents.dataflows.cache.app_adapter.get_market_quote_dataframe",
            lambda ticker: pd.DataFrame([
                {"close": 12.34, "pct_chg": 1.23, "volume": 456789}
            ]),
        )
        monkeypatch.setattr(
            "tradingagents.dataflows.interface.get_china_stock_data_unified",
            lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("不应回退到行情 provider")),
        )
        monkeypatch.setattr(
            "tradingagents.dataflows.optimized_china_data.OptimizedChinaDataProvider",
            FakeAnalyzer,
        )

        result = fundamentals_tools.get_stock_fundamentals_unified.invoke({"ticker": "000001.SZ"})

        assert "平安银行" in result
        assert "当前价格: 12.34" in result
        assert "涨跌幅: +1.23%" in result
        assert "mock fundamentals" in result
        assert captured["ticker"] == "000001"
        assert "股票代码: 000001" in captured["stock_data"]
        assert captured["analysis_modules"] == "standard"