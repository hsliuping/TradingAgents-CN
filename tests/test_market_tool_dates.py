from datetime import datetime

import pandas as pd


def test_resolve_china_actual_data_date_rolls_back_before_open():
    from core.tools.implementations.market import stock_market_data as module

    effective_end_date, actual_data_date, note = module._resolve_china_actual_data_date(
        ticker="600519",
        requested_end_date="2026-04-13",
        now=datetime(2026, 4, 13, 9, 15),
        db_latest_trade_date="2026-04-10",
    )

    assert effective_end_date == "2026-04-10"
    assert actual_data_date == "2026-04-10"
    assert note is not None
    assert "盘前时段" in note
    assert "2026-04-10" in note


def test_unified_market_tool_emits_actual_data_date_context(monkeypatch):
    from core.tools.implementations.market import stock_market_data as module
    from tradingagents.dataflows import interface as interface_module
    from tradingagents.utils import stock_utils as stock_utils_module

    class FakeStockUtils:
        @staticmethod
        def get_market_info(ticker):
            return {
                "is_china": True,
                "is_hk": False,
                "is_us": False,
                "market_name": "中国A股",
                "currency_name": "人民币",
                "currency_symbol": "¥",
            }

    captured = {}

    def fake_get_china_stock_data_unified(ticker, start_date, end_date):
        captured["args"] = (ticker, start_date, end_date)
        return "MOCK_STOCK_DATA"

    monkeypatch.setattr(stock_utils_module, "StockUtils", FakeStockUtils)
    monkeypatch.setattr(interface_module, "get_china_stock_data_unified", fake_get_china_stock_data_unified)
    monkeypatch.setattr(module, "_ensure_fresh_china_data", lambda ticker: None)
    monkeypatch.setattr(
        module,
        "_resolve_china_actual_data_date",
        lambda ticker, requested_end_date, now=None, db_latest_trade_date=None: (
            "2026-04-10",
            "2026-04-10",
            "请求分析日期为 2026-04-13，但当前处于盘前时段，尚未形成当日日线数据；以下价格与技术指标以最近已完成交易日 2026-04-10 为准。",
        ),
    )

    result = module.get_stock_market_data_unified.invoke(
        {
            "ticker": "600519",
            "start_date": "2026-04-13",
            "end_date": "2026-04-13",
        }
    )

    assert captured["args"] == ("600519", "2026-04-10", "2026-04-10")
    assert "**请求分析日期**: 2026-04-13" in result
    assert "**实际数据日期**: 2026-04-10" in result
    assert "盘前时段" in result


def test_format_stock_data_response_includes_actual_data_date_note():
    from tradingagents.dataflows import data_source_manager as module

    manager = module.DataSourceManager.__new__(module.DataSourceManager)
    data = pd.DataFrame(
        {
            "date": pd.to_datetime(
                [
                    "2026-04-02",
                    "2026-04-06",
                    "2026-04-07",
                    "2026-04-08",
                    "2026-04-09",
                    "2026-04-10",
                ]
            ),
            "open": [1400.0, 1410.0, 1420.0, 1430.0, 1440.0, 1450.0],
            "high": [1410.0, 1420.0, 1430.0, 1440.0, 1450.0, 1460.0],
            "low": [1390.0, 1405.0, 1415.0, 1425.0, 1435.0, 1445.0],
            "close": [1405.0, 1415.0, 1425.0, 1435.0, 1445.0, 1455.0],
            "volume": [1000, 1100, 1200, 1300, 1400, 1500],
        }
    )

    result = manager._format_stock_data_response(
        data,
        symbol="600519",
        stock_name="贵州茅台",
        start_date="2026-04-13",
        end_date="2026-04-13",
    )

    assert "请求分析日期: 2026-04-13" in result
    assert "实际数据日期: 2026-04-10" in result
    assert "日期说明: 请求分析日期 2026-04-13 暂无完整日线数据" in result
