from tradingagents.dataflows.data_source_manager import ChinaDataSource, DataSourceManager
from tradingagents.dataflows.optimized_china_data import _coerce_stock_info_text


def test_get_stock_data_normalizes_tuple_fallback_result(monkeypatch):
    manager = DataSourceManager.__new__(DataSourceManager)
    manager.current_source = ChinaDataSource.TUSHARE

    monkeypatch.setattr(
        manager,
        "_get_tushare_data",
        lambda symbol, start_date, end_date, period="daily": "❌ 当前数据源失败",
    )
    monkeypatch.setattr(
        manager,
        "_try_fallback_sources",
        lambda symbol, start_date, end_date, period="daily": ("股票代码: 000001\n股票名称: 平安银行", "mongodb"),
    )

    result = manager.get_stock_data("000001", "2026-04-08", "2026-04-10")

    assert isinstance(result, str)
    assert "股票名称: 平安银行" in result


def test_coerce_stock_info_text_accepts_tuple_payload():
    stock_info = (
        {
            "name": "平安银行",
            "area": "深圳",
            "industry": "银行",
            "market": "主板",
            "list_date": "19910403",
            "current_price": 12.34,
            "change_pct": 1.23,
            "volume": 456789,
        },
        "app_cache",
    )

    text = _coerce_stock_info_text(stock_info, "000001")

    assert "股票代码: 000001" in text
    assert "股票名称: 平安银行" in text
    assert "当前价格: 12.34" in text
    assert "涨跌幅: +1.23%" in text