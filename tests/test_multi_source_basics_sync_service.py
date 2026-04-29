import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pandas as pd

from app.services.multi_source_basics_sync_service import MultiSourceBasicsSyncService


class _FakeManager:
    def get_available_adapters(self):
        return [SimpleNamespace(name="akshare")]

    def get_stock_list_with_fallback(self, preferred_sources=None, exclude_local=True):
        return pd.DataFrame([
            {
                "ts_code": "300750.SZ",
                "symbol": "300750",
                "name": "宁德时代",
                "industry": "",
                "market": "创业板",
            }
        ]), "akshare"

    def find_latest_trade_date_with_fallback(self, preferred_sources=None):
        return None


def test_run_full_sync_uses_system_industry_mapping_for_batch_docs():
    service = MultiSourceBasicsSyncService()
    captured_operations = []

    async def _capture_bulk_write(db, operations, max_retries=3):
        captured_operations.extend(operations)
        return 0, len(operations)

    service._execute_bulk_write_with_retry = AsyncMock(side_effect=_capture_bulk_write)

    status_collection = MagicMock()
    status_collection.update_one = AsyncMock(return_value=None)
    fake_db = MagicMock()
    fake_db.__getitem__.return_value = status_collection

    with patch("app.services.multi_source_basics_sync_service.get_mongo_db", return_value=fake_db), \
         patch("app.services.data_sources.manager.DataSourceManager", return_value=_FakeManager()), \
         patch("app.services.official_industry_service.fetch_industry_mapping", new=AsyncMock(return_value={"300750": "电气设备"})):
        result = asyncio.run(service.run_full_sync(preferred_sources=["akshare"]))

    assert result["status"] == "success"
    assert "industry_mapping:system_industry_mapping" in result["data_sources_used"]
    assert len(captured_operations) == 1

    update_filter = captured_operations[0]._filter
    update_payload = captured_operations[0]._doc["$set"]

    assert update_filter == {"code": "300750", "source": "akshare"}
    assert update_payload["industry"] == "电气设备"
    assert update_payload["industry_source"] == "system_industry_mapping"