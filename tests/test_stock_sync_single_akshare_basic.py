from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from fastapi import BackgroundTasks

from app.routers.stock_sync import SingleStockSyncRequest, sync_single_stock


async def _fake_get_akshare_sync_service():
    provider = Mock()
    provider.get_stock_basic_info_for_single_sync = AsyncMock(return_value={
        "code": "300750",
        "name": "宁德时代",
        "industry": "电气机械和器材制造业",
        "market": "创业板",
        "sse": "深圳证券交易所",
        "list_date": "2018-06-11",
        "sync_status": "success",
    })
    provider.get_stock_basic_info = AsyncMock(return_value=None)
    return SimpleNamespace(provider=provider)


def test_sync_single_stock_akshare_basic_prefers_system_industry_mapping():
    fake_db = Mock()
    fake_db.stock_basic_info.find_one = AsyncMock(return_value=None)
    fake_db.stock_basic_info.update_one = AsyncMock(return_value=Mock())

    request = SingleStockSyncRequest(
        symbol="300750",
        sync_realtime=False,
        sync_historical=False,
        sync_financial=False,
        sync_basic=True,
        data_source="akshare",
    )

    with patch("app.routers.stock_sync.get_mongo_db", return_value=fake_db), \
         patch("app.routers.stock_sync.get_akshare_sync_service", new=AsyncMock(side_effect=_fake_get_akshare_sync_service)), \
         patch("app.services.official_industry_service.fetch_industry_mapping", new=AsyncMock(return_value={"300750": "电力设备"})):
        response = __import__("asyncio").run(
            sync_single_stock(request, BackgroundTasks(), current_user={"id": "u1"})
        )

    assert response["success"] is True
    assert response["data"]["basic_sync"]["success"] is True
    update_payload = fake_db.stock_basic_info.update_one.await_args.args[1]["$set"]
    assert update_payload["industry"] == "电力设备"
    assert update_payload["industry_source"] == "system_industry_mapping"