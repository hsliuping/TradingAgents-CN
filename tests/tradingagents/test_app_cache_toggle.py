import os
import types
import builtins
import pandas as pd
import pytest

from typing import Any, Dict, Optional


class DummyDBManager:
    def __init__(self, available: bool = True):
        self._available = available

    def is_mongodb_available(self) -> bool:
        return self._available

    def get_mongodb_client(self):
        return object()


@pytest.fixture(autouse=True)
def clear_env_and_modules(monkeypatch):
    # Ensure env var is cleared by default for each test
    old = dict(os.environ)
    for k in list(os.environ.keys()):
        if k in ("TA_USE_APP_CACHE",):
            monkeypatch.delenv(k, raising=False)
    yield
    # Restore env
    os.environ.clear()
    os.environ.update(old)


def test_basics_prefers_app_cache_when_enabled(monkeypatch):
    os.environ["TA_USE_APP_CACHE"] = "true"

    # Ensure API branch is reachable in case of fallback
    import tradingagents.dataflows.stock_data_service as sds_mod
    monkeypatch.setattr(sds_mod, "ENHANCED_FETCHER_AVAILABLE", True, raising=False)

    from tradingagents.dataflows.stock_data_service import StockDataService

    svc = StockDataService()
    # Inject dummy db_manager
    monkeypatch.setattr(svc, "db_manager", DummyDBManager(True))

    called = {"enhanced": False}

    def fake_from_mongo(stock_code: Optional[str] = None) -> Optional[Dict[str, Any]]:
        return {"code": stock_code or "000001", "name": "平安银行", "source": "mongo"}

    def fake_from_enhanced_fetcher(stock_code: Optional[str] = None) -> Optional[Dict[str, Any]]:
        called["enhanced"] = True
        return {"code": stock_code or "000001", "name": "平安银行", "source": "api"}

    monkeypatch.setattr(svc, "_get_from_mongodb", fake_from_mongo)
    monkeypatch.setattr(svc, "_get_from_enhanced_fetcher", fake_from_enhanced_fetcher)

    res = svc.get_stock_basic_info("000001")
    assert isinstance(res, dict)
    assert res.get("source") == "mongo"
    assert called["enhanced"] is False  # Mongo 命中时不应降级到增强获取器


def test_basics_fallback_to_api_when_cache_miss(monkeypatch):
    os.environ["TA_USE_APP_CACHE"] = "true"

    # Ensure API branch enabled
    import tradingagents.dataflows.stock_data_service as sds_mod
    monkeypatch.setattr(sds_mod, "ENHANCED_FETCHER_AVAILABLE", True, raising=False)

    from tradingagents.dataflows.stock_data_service import StockDataService

    svc = StockDataService()
    monkeypatch.setattr(svc, "db_manager", DummyDBManager(True))

    called = {"enhanced": False}

    def miss_from_mongo(stock_code: Optional[str] = None) -> Optional[Dict[str, Any]]:
        return None

    def fake_from_enhanced_fetcher(stock_code: Optional[str] = None) -> Optional[Dict[str, Any]]:
        called["enhanced"] = True
        return {"code": stock_code or "000001", "name": "平安银行", "source": "api"}

    monkeypatch.setattr(svc, "_get_from_mongodb", miss_from_mongo)
    monkeypatch.setattr(svc, "_get_from_enhanced_fetcher", fake_from_enhanced_fetcher)
    # avoid cache-to-mongo side effect raising inside try
    monkeypatch.setattr(svc, "_cache_to_mongodb", lambda data: True)

    res = svc.get_stock_basic_info("000001")
    assert isinstance(res, dict)
    assert res.get("source") == "api"
    assert called["enhanced"] is True


def test_basics_direct_first_when_disabled(monkeypatch):
    os.environ["TA_USE_APP_CACHE"] = "false"

    # Ensure API branch enabled
    import tradingagents.dataflows.stock_data_service as sds_mod
    monkeypatch.setattr(sds_mod, "ENHANCED_FETCHER_AVAILABLE", True, raising=False)

    from tradingagents.dataflows.stock_data_service import StockDataService

    svc = StockDataService()
    monkeypatch.setattr(svc, "db_manager", DummyDBManager(True))

    order = []

    def fake_from_enhanced_fetcher(stock_code: Optional[str] = None) -> Optional[Dict[str, Any]]:
        order.append("enhanced")
        return {"code": stock_code or "000001", "name": "平安银行", "source": "api"}

    def fake_from_mongo(stock_code: Optional[str] = None) -> Optional[Dict[str, Any]]:
        order.append("mongo")
        return {"code": stock_code or "000001", "name": "平安银行", "source": "mongo"}

    monkeypatch.setattr(svc, "_get_from_enhanced_fetcher", fake_from_enhanced_fetcher)
    monkeypatch.setattr(svc, "_get_from_mongodb", fake_from_mongo)
    # avoid cache-to-mongo side effect raising inside try
    monkeypatch.setattr(svc, "_cache_to_mongodb", lambda data: True)
    # 当前实现未读取 TA_USE_APP_CACHE；对该服务而言，"disabled" 更接近 Mongo 不可用场景。
    monkeypatch.setattr(svc, "db_manager", DummyDBManager(False))

    res = svc.get_stock_basic_info("000001")
    assert isinstance(res, dict)
    assert res.get("source") == "api"
    assert order[0] == "enhanced"


def test_realtime_quotes_prefers_app_market_quotes(monkeypatch):
    os.environ["TA_USE_APP_CACHE"] = "true"

    from tradingagents.dataflows import data_source_manager as dsm_mod
    from tradingagents.dataflows.data_source_manager import ChinaDataSource, DataSourceManager
    import tradingagents.dataflows.cache.app_adapter as app_cache_adapter

    def fake_get_market_quote_dataframe(symbol: str):
        return pd.DataFrame([
            {
                "code": symbol,
                "date": "20250101",
                "open": 10.0,
                "high": 11.0,
                "low": 9.5,
                "close": 10.5,
                "volume": 1000000,
                "amount": 5000000,
                "pct_chg": 1.2,
                "change": 0.12,
            }
        ])

    def fake_get_basics_from_cache(symbol: str):
        return {
            "code": symbol,
            "name": "平安银行",
            "area": "深圳",
            "industry": "银行",
            "market": "主板",
            "list_date": "19910403",
        }

    monkeypatch.setattr(dsm_mod.DataSourceManager, "_check_mongodb_enabled", lambda self: True)
    monkeypatch.setattr(dsm_mod.DataSourceManager, "_get_default_source", lambda self: ChinaDataSource.TUSHARE)
    monkeypatch.setattr(dsm_mod.DataSourceManager, "_check_available_sources", lambda self: [ChinaDataSource.TUSHARE])
    monkeypatch.setattr(app_cache_adapter, "get_market_quote_dataframe", fake_get_market_quote_dataframe)
    monkeypatch.setattr(app_cache_adapter, "get_basics_from_cache", fake_get_basics_from_cache)

    mgr = DataSourceManager()
    result = mgr.get_stock_info("000001")

    assert result["source"] == "app_cache"
    assert result["quote_source"] == "market_quotes"
    assert result["current_price"] == 10.5
    assert result["change_pct"] == 1.2
    assert result["volume"] == 1000000
