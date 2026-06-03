from datetime import datetime
from unittest.mock import AsyncMock, Mock, patch

import pytest

from app.worker.akshare_sync_service import AKShareSyncService


class AsyncCursor:
    def __init__(self, docs):
        self._docs = list(docs)

    def __aiter__(self):
        self._iterator = iter(self._docs)
        return self

    async def __anext__(self):
        try:
            return next(self._iterator)
        except StopIteration as exc:
            raise StopAsyncIteration from exc


@pytest.fixture
def akshare_sync_service():
    service = AKShareSyncService()
    service.db = Mock()
    service.provider = Mock()
    service._is_data_fresh = Mock(return_value=True)
    return service


@pytest.mark.asyncio
async def test_process_basic_info_batch_updates_fresh_record_when_mapping_can_fill_industry(akshare_sync_service):
    akshare_sync_service.db.stock_basic_info.find_one = AsyncMock(return_value={
        "code": "000001",
        "source": "akshare",
        "industry": "未知",
        "updated_at": datetime.utcnow(),
    })
    akshare_sync_service.db.stock_basic_info.update_one = AsyncMock(return_value=Mock(modified_count=1, upserted_id=None))

    with patch('app.services.official_industry_service.fetch_industry_mapping', new_callable=AsyncMock, return_value={"000001": "银行"}):
        result = await akshare_sync_service._process_basic_info_batch([
            {"code": "000001", "name": "平安银行"}
        ], force_update=False)

    assert result["success_count"] == 1
    assert result["skipped_count"] == 0
    update_filter = akshare_sync_service.db.stock_basic_info.update_one.await_args.args[0]
    update_payload = akshare_sync_service.db.stock_basic_info.update_one.await_args.args[1]["$set"]
    assert update_filter == {"code": "000001", "source": "akshare"}
    assert update_payload["industry"] == "银行"
    assert update_payload["industry_source"] == "system_industry_mapping"


@pytest.mark.asyncio
async def test_process_basic_info_batch_skips_fresh_record_when_mapping_already_matches(akshare_sync_service):
    akshare_sync_service.db.stock_basic_info.find_one = AsyncMock(return_value={
        "code": "000001",
        "source": "akshare",
        "industry": "银行",
        "updated_at": datetime.utcnow(),
    })
    akshare_sync_service.db.stock_basic_info.update_one = AsyncMock(return_value=Mock(modified_count=0, upserted_id=None))

    with patch('app.services.official_industry_service.fetch_industry_mapping', new_callable=AsyncMock, return_value={"000001": "银行"}):
        result = await akshare_sync_service._process_basic_info_batch([
            {"code": "000001", "name": "平安银行"}
        ], force_update=False)

    assert result["success_count"] == 0
    assert result["skipped_count"] == 1
    akshare_sync_service.db.stock_basic_info.update_one.assert_not_awaited()


@pytest.mark.asyncio
async def test_get_favorite_stocks_uses_valid_user_favorites_only(akshare_sync_service):
    akshare_sync_service.db.users.find = Mock(return_value=AsyncCursor([
        {"_id": "user-1"},
        {"_id": "user-2"},
    ]))
    akshare_sync_service.db.user_favorites.find = Mock(return_value=AsyncCursor([
        {
            "user_id": "user-1",
            "favorites": [
                {"stock_code": "000001"},
                {"stock_code": "000002"},
            ],
        },
        {
            "user_id": "user-2",
            "favorites": [
                {"stock_code": "000002"},
                {"stock_code": "000003"},
            ],
        },
        {
            "user_id": "stale-user",
            "favorites": [
                {"stock_code": "999999"},
            ],
        },
    ]))

    result = await akshare_sync_service._get_favorite_stocks()

    assert result == ["000001", "000002", "000003"]
    akshare_sync_service.db.users.find.assert_called_once_with({}, {"_id": 1})
    akshare_sync_service.db.user_favorites.find.assert_called_once_with(
        {"favorites": {"$exists": True, "$ne": []}},
        {"user_id": 1, "favorites.stock_code": 1, "_id": 0},
    )