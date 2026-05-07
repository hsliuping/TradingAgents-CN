from datetime import datetime
from unittest.mock import AsyncMock, Mock, patch

import pytest

from app.worker.akshare_sync_service import AKShareSyncService


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