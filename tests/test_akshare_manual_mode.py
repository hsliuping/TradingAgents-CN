import asyncio
from unittest.mock import AsyncMock, Mock

from app.worker.akshare_sync_service import AKShareSyncService


def test_sync_historical_data_manual_mode_ignores_scheduler_cancel_state():
    service = AKShareSyncService()
    service.db = Mock()
    service.provider = Mock()
    service._current_job_id = "akshare_historical_sync"
    service._should_stop = AsyncMock(return_value=True)
    service._process_historical_batch = AsyncMock(return_value={
        "success_count": 1,
        "error_count": 0,
        "total_records": 5,
        "errors": [],
        "processed_count": 1,
    })

    result = asyncio.run(service.sync_historical_data(
        symbols=["300750"],
        start_date="2026-04-01",
        end_date="2026-04-29",
        incremental=False,
        manual_mode=True,
    ))

    assert result["success_count"] == 1
    assert result["total_records"] == 5
    assert result.get("stopped") is not True
    service._should_stop.assert_not_awaited()
    service._process_historical_batch.assert_awaited_once()