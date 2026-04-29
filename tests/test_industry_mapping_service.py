import pytest
from pymongo import UpdateMany
from unittest.mock import AsyncMock, Mock, patch

from app.services.official_industry_service import (
    sync_industry_to_stock_basic_info,
    upsert_industry_mapping_from_records,
)


@pytest.mark.asyncio
async def test_upsert_industry_mapping_from_records_writes_system_collection():
    mock_collection = Mock()
    mock_collection.bulk_write = AsyncMock(return_value=Mock(modified_count=1, upserted_count=1))
    mock_db = {"stock_industry_mappings": mock_collection}

    records = [
        {"code": "000001", "industry": "银行"},
        {"symbol": "000002", "industry": "全国地产"},
        {"code": "000003", "industry": ""},
    ]

    with patch('app.services.official_industry_service.get_mongo_db', return_value=mock_db):
        result = await upsert_industry_mapping_from_records(records, provider="tushare_fallback")

    assert result["provider"] == "tushare_fallback"
    assert result["total"] == 2
    mock_collection.bulk_write.assert_awaited_once()


@pytest.mark.asyncio
async def test_sync_industry_to_stock_basic_info_updates_all_sources_for_same_code():
    mock_collection = Mock()
    mock_collection.bulk_write = AsyncMock(return_value=Mock(modified_count=2))
    mock_db = {"stock_basic_info": mock_collection}

    with patch('app.services.official_industry_service.get_mongo_db', return_value=mock_db), patch(
        'app.services.official_industry_service.fetch_industry_mapping',
        new=AsyncMock(return_value={"000001": "银行"})
    ):
        result = await sync_industry_to_stock_basic_info()

    assert result["updated"] == 2
    assert result["total"] == 1
    mock_collection.bulk_write.assert_awaited_once()

    operations = mock_collection.bulk_write.await_args.args[0]
    assert len(operations) == 1
    assert isinstance(operations[0], UpdateMany)
    assert operations[0]._filter == {"code": "000001"}
    assert operations[0]._doc["$set"]["industry"] == "银行"
