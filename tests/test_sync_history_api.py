import asyncio
from unittest.mock import AsyncMock, Mock, patch

from app.routers.multi_source_sync import get_sync_history


class FakeCursor:
    def __init__(self, items):
        self._items = items

    def sort(self, *_args, **_kwargs):
        return self

    def skip(self, *_args, **_kwargs):
        return self

    def limit(self, *_args, **_kwargs):
        return self

    async def to_list(self, length=None):
        if length is None:
            return list(self._items)
        return list(self._items[:length])


def test_get_sync_history_returns_paginated_records() -> None:
    records = [
        {
            "_id": "mongo-id-1",
            "job": "stock_basics_multi_source",
            "status": "success",
            "started_at": "2026-03-27T10:00:00",
            "finished_at": "2026-03-27T10:01:00",
            "total": 10,
        },
        {
            "_id": "mongo-id-2",
            "job": "stock_basics_multi_source",
            "status": "success_with_errors",
            "started_at": "2026-03-27T09:00:00",
            "finished_at": "2026-03-27T09:01:00",
            "total": 8,
        },
    ]

    sync_status = Mock()
    sync_status.find.return_value = FakeCursor(records)
    sync_status.count_documents = AsyncMock(return_value=12)
    fake_db = type("FakeDB", (), {"sync_status": sync_status})()

    with patch("app.core.database.get_mongo_db", return_value=fake_db):
        response = asyncio.run(get_sync_history(page=2, page_size=2, status=None))

    assert response.success is True
    assert response.data["total"] == 12
    assert response.data["page"] == 2
    assert response.data["page_size"] == 2
    assert response.data["has_more"] is True
    assert response.data["records"][0]["status"] == "success"
    assert "_id" not in response.data["records"][0]
    sync_status.find.assert_called_once_with({"job": "stock_basics_multi_source"})
    sync_status.count_documents.assert_awaited_once_with({"job": "stock_basics_multi_source"})


def test_get_sync_history_applies_status_filter() -> None:
    sync_status = Mock()
    sync_status.find.return_value = FakeCursor([])
    sync_status.count_documents = AsyncMock(return_value=0)
    fake_db = type("FakeDB", (), {"sync_status": sync_status})()

    with patch("app.core.database.get_mongo_db", return_value=fake_db):
        response = asyncio.run(get_sync_history(page=1, page_size=5, status="success"))

    assert response.success is True
    assert response.data["records"] == []
    assert response.data["has_more"] is False
    sync_status.find.assert_called_once_with(
        {"job": "stock_basics_multi_source", "status": "success"}
    )
    sync_status.count_documents.assert_awaited_once_with(
        {"job": "stock_basics_multi_source", "status": "success"}
    )
