import asyncio
from unittest.mock import AsyncMock, Mock, patch

import pandas as pd

from app.routers.stock_sync import _build_single_historical_sync_result
from tradingagents.dataflows.providers.china.akshare import AKShareNetworkError, AKShareProvider


def test_get_historical_data_falls_back_to_tx_after_primary_network_error():
    with patch.object(AKShareProvider, "_initialize_akshare", return_value=None):
        provider = AKShareProvider()

    provider.connected = True
    provider.ak = Mock()
    provider.ak.stock_zh_a_hist = Mock(side_effect=ConnectionAbortedError("Connection aborted."))
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


def test_get_historical_data_falls_back_to_sina_daily_after_tx_failure():
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