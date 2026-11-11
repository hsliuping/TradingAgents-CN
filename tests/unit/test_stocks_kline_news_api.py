import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from unittest.mock import patch

# Build a minimal app that mounts only the stocks router to avoid triggering app.main lifespan
from app.routers import stocks as stocks_router
from app.routers.auth_db import get_current_user


def create_test_app():
    app = FastAPI()
    app.include_router(stocks_router.router, prefix="/api")
    # Override auth dependency to bypass Bearer token in tests
    app.dependency_overrides[get_current_user] = lambda: {
        "id": "test",
        "username": "test",
        "is_admin": True,
        "roles": ["admin"],
    }
    return app


@pytest.fixture()
def client():
    app = create_test_app()
    with TestClient(app) as c:
        yield c


def test_kline_ok_source_and_adj(client):
    # Mock DataSourceManager fallback to return 2 bars
    items = [
        {"time": "2024-09-01", "open": 10.0, "high": 10.5, "low": 9.8, "close": 10.2, "volume": 100000.0, "amount": 2.3e6},
        {"time": "2024-09-02", "open": 10.2, "high": 10.8, "low": 10.0, "close": 10.6, "volume": 120000.0, "amount": 2.8e6},
    ]
    with patch("app.services.data_sources.manager.DataAdapterOrchestrator.get_kline_with_fallback", return_value=(items, "tushare")):
        resp = client.get("/api/stocks/000001/kline", params={"period": "day", "limit": 2, "adj": "qfq"})
        assert resp.status_code == 200
        body = resp.json()
        assert body.get("success") is True
        data = body.get("data")
        assert data["code"] == "000001"
        assert data["period"] == "day"
        assert data["limit"] == 2
        assert data["adj"] == "qfq"
        assert data["source"] == "tushare"
        assert isinstance(data["items"], list) and len(data["items"]) == 2


def test_kline_invalid_period_returns_400(client):
    resp = client.get("/api/stocks/000001/kline", params={"period": "2m", "limit": 10})
    assert resp.status_code == 400
    j = resp.json()
    # FastAPI default error format
    assert j["detail"].startswith("不支持的period")


def test_news_ok_with_database_source(client):
    # 现役 A 股 news 端点走 news_data_service（MongoDB 查询）+ akshare 同步兜底，
    # mock 数据库查询返回非空列表以走 "database" 路径
    fake_news = [
        {"title": "公告样例", "source": "tushare", "publish_time": "2024-09-02", "url": "http://x", "data_type": "announcement"},
        {"title": "新闻样例", "source": "tushare", "publish_time": "2024-09-02 10:00:00", "url": "http://y", "data_type": "news"},
    ]

    class _FakeNewsService:
        async def query_news(self, params):
            return fake_news

    async def _fake_news_service_factory():
        return _FakeNewsService()

    async def _fake_sync_service_factory():
        return None

    with patch("app.services.news_data_service.get_news_data_service", _fake_news_service_factory), patch(
        "app.worker.akshare_sync_service.get_akshare_sync_service", _fake_sync_service_factory
    ):
        resp = client.get("/api/stocks/000001/news", params={"days": 2, "limit": 2, "include_announcements": True})
        assert resp.status_code == 200
        body = resp.json()
        assert body.get("success") is True
        data = body.get("data")
        assert data["code"] == "000001"
        assert data["days"] == 2
        assert data["limit"] == 2
        assert data["include_announcements"] is True
        assert data["source"] == "database"
        assert isinstance(data["items"], list) and len(data["items"]) == 2

