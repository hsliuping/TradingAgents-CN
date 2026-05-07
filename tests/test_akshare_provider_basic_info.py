import asyncio
from unittest.mock import AsyncMock, patch

from tradingagents.dataflows.providers.china.akshare import AKShareProvider


def test_get_stock_basic_info_for_single_sync_uses_stable_sources_before_detail_fallback():
    with patch.object(AKShareProvider, "_initialize_akshare", return_value=None):
        provider = AKShareProvider()

    provider.connected = True
    provider._get_single_stock_profile_info = AsyncMock(return_value={
        "name": "平安银行",
        "industry": "货币金融服务",
        "list_date": "1991-04-03",
        "market": "主板",
        "sse": "深圳证券交易所",
    })
    provider._get_single_stock_listing_info = AsyncMock(return_value={
        "market": "主板",
    })
    provider._get_single_stock_spot_info = AsyncMock(return_value={
        "total_mv": 2235.56,
        "circ_mv": 2235.52,
        "pe_ttm": 5.19,
        "pb": 0.48,
    })
    provider._get_stock_info_detail = AsyncMock(return_value={
        "code": "000001",
        "_detail_fetch_failed": True,
        "_detail_fetch_error": "should not be used",
        "_detail_symbol": "sz000001",
    })

    result = asyncio.run(provider.get_stock_basic_info_for_single_sync("000001"))

    assert result is not None
    assert result["sync_status"] == "success"
    assert result["name"] == "平安银行"
    assert result["industry"] == "货币金融服务"
    assert result["list_date"] == "1991-04-03"
    assert result["total_mv"] == 2235.56
    assert result["pb"] == 0.48
    provider._get_stock_info_detail.assert_not_awaited()


def test_get_stock_basic_info_for_single_sync_returns_degraded_when_all_sources_fail():
    with patch.object(AKShareProvider, "_initialize_akshare", return_value=None):
        provider = AKShareProvider()

    provider.connected = True
    provider._get_single_stock_profile_info = AsyncMock(return_value={})
    provider._get_single_stock_listing_info = AsyncMock(return_value={})
    provider._get_single_stock_spot_info = AsyncMock(return_value={})
    provider._get_stock_info_detail = AsyncMock(return_value={
        "code": "000001",
        "_detail_fetch_failed": True,
        "_detail_fetch_error": "AKShare 个股详情接口网络异常",
        "_detail_symbol": "sz000001",
    })

    result = asyncio.run(provider.get_stock_basic_info_for_single_sync("000001"))

    assert result is not None
    assert result["sync_status"] == "degraded"
    assert result["detail_fetch_error"] == "AKShare 个股详情接口网络异常"
    assert result["detail_fetch_symbol"] == "sz000001"
    provider._get_stock_info_detail.assert_awaited_once()