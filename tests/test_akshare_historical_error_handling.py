import asyncio
from unittest.mock import AsyncMock, Mock, patch

import pandas as pd
import pytest

from app.routers.stock_sync import (
    SingleStockSyncRequest,
    _build_single_historical_sync_result,
    run_single_stock_sync,
)
from tradingagents.dataflows.providers.china.akshare import AKShareNetworkError, AKShareProvider


def test_get_historical_data_falls_back_to_tx_after_primary_network_error():
    with patch.object(AKShareProvider, "_initialize_akshare", return_value=None):
        provider = AKShareProvider()

    provider.connected = True
    provider.ak = Mock()
    provider.ak.stock_zh_a_hist = Mock(side_effect=ConnectionAbortedError("Connection aborted."))
    provider.ak.stock_zh_a_daily = Mock(return_value=pd.DataFrame())
    provider.ak.stock_zh_a_hist_tx = Mock(return_value=pd.DataFrame([
        {"date": "2026-04-28", "open": 426.19, "high": 433.3, "low": 423.0, "close": 427.67, "amount": 14992134063.0},
        {"date": "2026-04-29", "open": 430.0, "high": 435.0, "low": 428.0, "close": 432.0, "amount": 8600000000.0},
    ]))

    with patch('tradingagents.dataflows.providers.china.akshare.asyncio.sleep', new=AsyncMock()):
        result = asyncio.run(provider.get_historical_data("300750", "2026-04-01", "2026-04-29"))

    assert result is not None
    assert len(result) == 2
    assert list(result["code"].unique()) == ["300750"]
    assert result.iloc[-1]["close"] == 432.0
    provider.ak.stock_zh_a_hist_tx.assert_called_once_with(
        symbol="sz300750",
        start_date="2026-04-01",
        end_date="2026-04-29",
        adjust="qfq",
    )


def test_get_historical_data_prefers_sina_daily_before_tx():
    with patch.object(AKShareProvider, "_initialize_akshare", return_value=None):
        provider = AKShareProvider()

    provider.connected = True
    provider.ak = Mock()
    provider.ak.stock_zh_a_hist = Mock(side_effect=ConnectionAbortedError("Connection aborted."))
    provider.ak.stock_zh_a_hist_tx = Mock(side_effect=ValueError("invalid literal for int() with base 10: 'i'"))
    provider.ak.stock_zh_a_daily = Mock(return_value=pd.DataFrame([
        {"date": "2026-04-28", "open": 426.19, "high": 433.3, "low": 423.0, "close": 427.67, "volume": 35012113.0, "amount": 14992134063.0, "turnover": 0.0082},
        {"date": "2026-04-29", "open": 430.0, "high": 435.0, "low": 428.0, "close": 432.0, "volume": 20000000.0, "amount": 8600000000.0, "turnover": 0.0047},
    ]))

    with patch('tradingagents.dataflows.providers.china.akshare.asyncio.sleep', new=AsyncMock()):
        result = asyncio.run(provider.get_historical_data("300750", "2026-04-01", "2026-04-29"))

    assert result is not None
    assert len(result) == 2
    assert list(result["code"].unique()) == ["300750"]
    assert result.iloc[-1]["close"] == 432.0
    provider.ak.stock_zh_a_daily.assert_called_once()
    provider.ak.stock_zh_a_hist_tx.assert_not_called()


def test_get_historical_data_raises_network_error_when_primary_and_fallback_both_fail():
    with patch.object(AKShareProvider, "_initialize_akshare", return_value=None):
        provider = AKShareProvider()

    provider.connected = True
    provider.ak = Mock()
    provider.ak.stock_zh_a_hist = Mock(side_effect=ConnectionAbortedError("Connection aborted."))
    provider.ak.stock_zh_a_hist_tx = Mock(side_effect=ConnectionAbortedError("Connection aborted."))
    provider.ak.stock_zh_a_daily = Mock(side_effect=ConnectionAbortedError("Connection aborted."))

    with patch('tradingagents.dataflows.providers.china.akshare.asyncio.sleep', new=AsyncMock()):
        try:
            asyncio.run(provider.get_historical_data("300750", "2026-04-01", "2026-04-29"))
            assert False, "expected AKShareNetworkError"
        except AKShareNetworkError as exc:
            assert "300750 网络连接中断" in str(exc)


def test_build_single_historical_sync_result_prefers_real_error_message():
    result = _build_single_historical_sync_result({
        "success_count": 0,
        "error_count": 1,
        "total_records": 0,
        "errors": [{"error": "300750 网络连接中断，建议稍后重试或减小时间范围"}],
    })

    assert result == {
        "success": False,
        "records": 0,
        "error": "300750 网络连接中断，建议稍后重试或减小时间范围"
    }


@pytest.mark.parametrize("error_message", [
    "东方财富 push2 行情服务器断开了连接，当前 IP 被临时限流。",
    "远端断开连接",
    "ConnectionError: connection reset by peer",
])
def test_historical_data_falls_back_for_wrapped_network_errors(error_message):
    with patch.object(AKShareProvider, "_initialize_akshare", return_value=None):
        provider = AKShareProvider()
    provider.connected = True
    provider.ak = Mock()
    provider.ak.stock_zh_a_hist = Mock(side_effect=RuntimeError(error_message))
    data = pd.DataFrame([{"date": "2026-11-04", "close": 7.68}])
    provider._get_historical_data_sina_fallback = AsyncMock(return_value=data)
    provider._get_historical_data_tx_fallback = AsyncMock()
    with patch('tradingagents.dataflows.providers.china.akshare.asyncio.sleep', new=AsyncMock()):
        result = asyncio.run(provider.get_historical_data("001979", "2025-11-05", "2026-11-05"))
    assert len(result) == 1
    provider._get_historical_data_tx_fallback.assert_not_awaited()


def test_historical_data_preserves_primary_error_when_fallbacks_fail():
    with patch.object(AKShareProvider, "_initialize_akshare", return_value=None):
        provider = AKShareProvider()
    provider.connected = True
    provider.ak = Mock()
    error_message = "东方财富 push2 行情服务器断开了连接，当前 IP 被临时限流。"
    provider.ak.stock_zh_a_hist = Mock(side_effect=RuntimeError(error_message))
    provider._get_historical_data_sina_fallback = AsyncMock(return_value=None)
    provider._get_historical_data_tx_fallback = AsyncMock(return_value=pd.DataFrame())
    with patch('tradingagents.dataflows.providers.china.akshare.asyncio.sleep', new=AsyncMock()):
        with pytest.raises(AKShareNetworkError, match=error_message):
            asyncio.run(provider.get_historical_data("001979", "2025-11-05", "2026-11-05"))


@pytest.mark.parametrize("raw_result,expected", [
    ({"success_count": 1, "total_records": 242}, {"success": True, "records": 242, "message": "同步了 242 条历史记录"}),
    ({"success_count": 1, "historical_records": 0}, {"success": True, "records": 0, "message": "同步了 0 条历史记录"}),
    ({"errors": [{"error": "历史数据为空"}, {"error": "历史数据为空"}]}, {"success": False, "records": 0, "error": "历史数据为空"}),
    ({"error": "数据源不可用", "errors": None}, {"success": False, "records": 0, "error": "数据源不可用"}),
    ({}, {"success": False, "records": 0, "error": "历史数据同步失败，未获取到可用历史数据"}),
])
def test_build_single_historical_result_handles_success_and_empty_errors(raw_result, expected):
    assert _build_single_historical_sync_result(raw_result) == expected


def test_single_stock_sync_propagates_worker_error():
    service = Mock()
    service.sync_historical_data = AsyncMock(return_value={
        "success_count": 0, "total_records": 0,
        "errors": [{"code": "001979", "error": "东财接口限流"}],
    })
    request = SingleStockSyncRequest(
        symbol="001979", data_source="akshare", sync_historical=True,
        sync_realtime=False, sync_financial=False, sync_basic=False, days=365,
    )
    with patch('app.routers.stock_sync.get_akshare_sync_service', new=AsyncMock(return_value=service)), \
         patch('app.routers.stock_sync._sync_latest_to_market_quotes', new=AsyncMock()) as sync_quote:
        result = asyncio.run(run_single_stock_sync(request))
    assert result["historical_sync"]["error"] == "东财接口限流"
    assert result["overall_success"] is False
    sync_quote.assert_not_awaited()
