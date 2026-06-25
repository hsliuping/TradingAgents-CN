import pytest

from app.services.stop_gain_alert_service import StopGainAlertService


class _FakeCursor:
    def __init__(self, items):
        self._items = list(items)

    def __aiter__(self):
        self._iter = iter(self._items)
        return self

    async def __anext__(self):
        try:
            return next(self._iter)
        except StopIteration as exc:
            raise StopAsyncIteration from exc

    async def to_list(self, length=None):
        if length is None:
            return list(self._items)
        return list(self._items[:length])


class _FakeCollection:
    def __init__(self, docs):
        self._docs = list(docs)

    def find(self, *args, **kwargs):
        return _FakeCursor(self._docs)


class _FakeDb:
    def __init__(self):
        self.users = _FakeCollection([
            {
                "_id": "user_a",
                "favorite_stocks": [
                    {"stock_code": "600519", "stock_name": "茅台", "market": "A股", "alert_gain_price": 1800}
                ],
            }
        ])
        self.user_favorites = _FakeCollection([])
        self.market_quotes = _FakeCollection([
            {"code": "600519", "close": 1810.0}
        ])
        self.market_quotes_hk = _FakeCollection([])
        self.market_quotes_us = _FakeCollection([])


@pytest.mark.asyncio
async def test_load_watch_items_fetches_db_per_run(monkeypatch):
    service = StopGainAlertService()
    calls = []

    def _fake_get_db():
        calls.append("db")
        return _FakeDb()

    monkeypatch.setattr(service, "_get_db", staticmethod(_fake_get_db))

    items = await service._load_watch_items_async()

    assert len(calls) == 1
    assert len(items) == 1
    assert items[0]["user_id"] == "user_a"
    assert items[0]["current_price"] == 1810.0


def test_stop_shuts_down_scheduler_when_running():
    service = StopGainAlertService()

    class _FakeScheduler:
        running = True

        def __init__(self):
            self.shutdown_called = False
            self.wait_value = None

        def shutdown(self, wait=False):
            self.shutdown_called = True
            self.wait_value = wait

    fake_scheduler = _FakeScheduler()
    service.scheduler = fake_scheduler
    service._job = object()

    service.stop()

    assert fake_scheduler.shutdown_called is True
    assert fake_scheduler.wait_value is False
    assert service._job is None
