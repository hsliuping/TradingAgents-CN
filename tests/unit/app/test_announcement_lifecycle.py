"""公告独立数据类型 + 独立生命周期 单元测试

覆盖：
1. 独立公告查询只返回公告（query_announcements）
2. 同步入口可单独跑公告类型（sync_stock_announcements / sync_announcements）
3. 保留策略按类型生效（cleanup_expired / delete_old_news 兼容）
4. 存量 get_news 行为回归不变（include_announcements 默认值与混排结果）
"""

import asyncio
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.services.news_data_service import (
    ANNOUNCEMENT_CATEGORY,
    ANNOUNCEMENT_RETENTION_DAYS,
    DATA_TYPE_ALL,
    DATA_TYPE_ANNOUNCEMENT,
    DATA_TYPE_NEWS,
    NEWS_RETENTION_DAYS,
    NewsDataService,
    NewsQueryParams,
)
from app.utils.timezone import now_tz
from app.worker.news_data_sync_service import NewsDataSyncService, NewsSyncStats


# ==================== 测试替身（不依赖真实 MongoDB）====================


def _match(doc, query):
    """极简 Mongo 查询匹配（仅覆盖本测试用到的操作符）"""
    for key, cond in query.items():
        value = doc.get(key)
        if isinstance(cond, dict):
            if "$in" in cond and value not in cond["$in"]:
                return False
            if "$ne" in cond and value == cond["$ne"]:
                return False
            if "$lt" in cond and not (value is not None and value < cond["$lt"]):
                return False
            if "$gte" in cond and not (value is not None and value >= cond["$gte"]):
                return False
            if "$lte" in cond and not (value is not None and value <= cond["$lte"]):
                return False
        else:
            if value != cond:
                return False
    return True


class FakeCursor:
    def __init__(self, docs):
        self._docs = list(docs)

    def sort(self, *args, **kwargs):
        return self

    def skip(self, n):
        return self

    def limit(self, n):
        self._docs = self._docs[:n]
        return self

    async def to_list(self, length=None):
        return list(self._docs)


class FakeCollection:
    def __init__(self, docs):
        self.docs = list(docs)
        self.find_queries = []
        self.delete_queries = []

    def find(self, query=None, *args, **kwargs):
        self.find_queries.append(query or {})
        return FakeCursor([d for d in self.docs if _match(d, query or {})])

    async def count_documents(self, query):
        return len([d for d in self.docs if _match(d, query or {})])

    async def delete_many(self, query):
        self.delete_queries.append(query or {})
        matched = [d for d in self.docs if _match(d, query or {})]
        self.docs = [d for d in self.docs if not _match(d, query or {})]
        return SimpleNamespace(deleted_count=len(matched))


class StubNewsService:
    """新闻数据服务替身：记录保存批次，供同步测试断言"""

    def __init__(self, news=None):
        self.saved_batches = []
        self.news = news or []

    async def save_news_data(self, news_list, data_source, market="CN"):
        self.saved_batches.append(list(news_list))
        return len(news_list)

    async def query_news(self, params):
        return list(self.news)


def _make_sync_service_with_mixed_sources(mixed_news):
    """构造一个数据源返回混合新闻/公告的同步服务替身"""
    service = NewsDataSyncService()
    stub_news_service = StubNewsService()
    service._news_service = stub_news_service

    captured_args = {}

    async def fake_source(symbol, hours_back, max_news):
        captured_args.setdefault("calls", []).append(
            {"symbol": symbol, "hours_back": hours_back, "max_news": max_news}
        )
        return [dict(item) for item in mixed_news]

    service._sync_tushare_news = fake_source
    service._sync_akshare_news = fake_source
    service._sync_realtime_news = fake_source
    return service, stub_news_service, captured_args


MIXED_NEWS = [
    {"title": "重大合同公告", "category": ANNOUNCEMENT_CATEGORY, "url": "http://a/1"},
    {"title": "行业动态新闻", "category": "market_news", "url": "http://a/2"},
    {"title": "政策监管新闻", "category": "policy_news", "url": "http://a/3"},
]


# ==================== 1. 独立公告查询 ====================


def test_query_announcements_returns_only_announcements():
    docs = [
        {"symbol": "000001", "category": ANNOUNCEMENT_CATEGORY, "title": "公告1", "publish_time": datetime(2026, 10, 3)},
        {"symbol": "000001", "category": "market_news", "title": "新闻1", "publish_time": datetime(2026, 10, 2)},
        {"symbol": "000001", "category": "general", "title": "新闻2", "publish_time": datetime(2026, 10, 1)},
    ]
    service = NewsDataService()
    fake = FakeCollection(docs)
    service._collection = fake

    # 故意传入非公告 category，验证公告独立入口强制按公告过滤
    params = NewsQueryParams(symbol="000001", limit=10, category="market_news")
    results = asyncio.run(service.query_announcements(params))

    assert fake.find_queries[-1]["category"] == ANNOUNCEMENT_CATEGORY
    assert [r["title"] for r in results] == ["公告1"]
    assert all(r["category"] == ANNOUNCEMENT_CATEGORY for r in results)
    # 不修改调用方入参
    assert params.category == "market_news"


def test_query_announcements_does_not_affect_query_news():
    docs = [
        {"symbol": "000001", "category": ANNOUNCEMENT_CATEGORY, "title": "公告1", "publish_time": datetime(2026, 10, 3)},
        {"symbol": "000001", "category": "market_news", "title": "新闻1", "publish_time": datetime(2026, 10, 2)},
    ]
    service = NewsDataService()
    fake = FakeCollection(docs)
    service._collection = fake

    results = asyncio.run(service.query_news(NewsQueryParams(symbol="000001", limit=10)))
    assert "category" not in fake.find_queries[-1]
    assert len(results) == 2


# ==================== 2. 独立同步生命周期 ====================


def test_sync_stock_announcements_only_syncs_announcements():
    service, stub, captured = _make_sync_service_with_mixed_sources(MIXED_NEWS)

    stats = asyncio.run(service.sync_stock_announcements("000001", data_sources=["tushare"]))

    assert isinstance(stats, NewsSyncStats)
    saved = [item for batch in stub.saved_batches for item in batch]
    assert [item["title"] for item in saved] == ["重大合同公告"]
    assert all(item["category"] == ANNOUNCEMENT_CATEGORY for item in saved)
    assert stats.successful_saves == 1
    # 刷新节奏走公告独立配置（与新闻配置分开）
    from app.core.config import settings

    assert captured["calls"][0]["hours_back"] == settings.ANNOUNCEMENT_SYNC_HOURS_BACK
    assert captured["calls"][0]["max_news"] == settings.ANNOUNCEMENT_SYNC_MAX_PER_SOURCE


def test_sync_stock_news_default_still_syncs_all_types():
    service, stub, _ = _make_sync_service_with_mixed_sources(MIXED_NEWS)

    stats = asyncio.run(service.sync_stock_news("000001", data_sources=["tushare"]))

    saved = [item for batch in stub.saved_batches for item in batch]
    assert len(saved) == 3  # 兼容旧行为：新闻+公告全量同步
    assert stats.successful_saves == 3


def test_sync_stock_news_data_type_news_excludes_announcements():
    service, stub, _ = _make_sync_service_with_mixed_sources(MIXED_NEWS)

    asyncio.run(service.sync_stock_news("000001", data_sources=["tushare"], data_type=DATA_TYPE_NEWS))

    saved = [item for batch in stub.saved_batches for item in batch]
    assert [item["title"] for item in saved] == ["行业动态新闻", "政策监管新闻"]
    assert all(item["category"] != ANNOUNCEMENT_CATEGORY for item in saved)


def test_sync_announcements_batch_entry():
    service, stub, _ = _make_sync_service_with_mixed_sources(MIXED_NEWS)

    summary = asyncio.run(service.sync_announcements(symbols=["000001", "000002"]))

    assert summary["data_type"] == DATA_TYPE_ANNOUNCEMENT
    assert summary["success_count"] == 2
    assert summary["announcement_count"] == 2  # 每只股票只入库 1 条公告
    saved = [item for batch in stub.saved_batches for item in batch]
    assert all(item["category"] == ANNOUNCEMENT_CATEGORY for item in saved)


# ==================== 3. 独立保留策略 ====================


def test_cleanup_expired_announcement_uses_announcement_retention():
    now = now_tz()
    docs = [
        {"title": "很旧的公告", "category": ANNOUNCEMENT_CATEGORY, "publish_time": now - timedelta(days=ANNOUNCEMENT_RETENTION_DAYS + 10)},
        {"title": "较新的公告", "category": ANNOUNCEMENT_CATEGORY, "publish_time": now - timedelta(days=30)},
        {"title": "很旧的新闻", "category": "market_news", "publish_time": now - timedelta(days=ANNOUNCEMENT_RETENTION_DAYS + 10)},
    ]
    service = NewsDataService()
    fake = FakeCollection(docs)
    service._collection = fake

    deleted = asyncio.run(service.cleanup_expired(DATA_TYPE_ANNOUNCEMENT))

    assert deleted == 1  # 只清理过期公告，不动旧新闻
    query = fake.delete_queries[-1]
    assert query["category"] == ANNOUNCEMENT_CATEGORY
    cutoff = query["publish_time"]["$lt"]
    assert abs((cutoff - (now - timedelta(days=ANNOUNCEMENT_RETENTION_DAYS))).total_seconds()) < 60


def test_cleanup_expired_news_uses_news_retention():
    now = now_tz()
    docs = [
        {"title": "很旧的新闻", "category": "market_news", "publish_time": now - timedelta(days=NEWS_RETENTION_DAYS + 10)},
        {"title": "较旧但未过期的公告", "category": ANNOUNCEMENT_CATEGORY, "publish_time": now - timedelta(days=NEWS_RETENTION_DAYS + 10)},
    ]
    service = NewsDataService()
    fake = FakeCollection(docs)
    service._collection = fake

    deleted = asyncio.run(service.cleanup_expired(DATA_TYPE_NEWS))

    assert deleted == 1  # 只清新闻，公告不受新闻保留策略影响
    query = fake.delete_queries[-1]
    assert query["category"] == {"$ne": ANNOUNCEMENT_CATEGORY}
    cutoff = query["publish_time"]["$lt"]
    assert abs((cutoff - (now - timedelta(days=NEWS_RETENTION_DAYS))).total_seconds()) < 60


def test_delete_old_news_keeps_legacy_all_type_behavior():
    now = now_tz()
    docs = [
        {"title": "旧新闻", "category": "market_news", "publish_time": now - timedelta(days=200)},
        {"title": "旧公告", "category": ANNOUNCEMENT_CATEGORY, "publish_time": now - timedelta(days=200)},
        {"title": "新新闻", "category": "market_news", "publish_time": now - timedelta(days=1)},
    ]
    service = NewsDataService()
    fake = FakeCollection(docs)
    service._collection = fake

    deleted = asyncio.run(service.delete_old_news(90))

    assert deleted == 2  # 兼容旧行为：新闻与公告一起清理，无类别过滤
    query = fake.delete_queries[-1]
    assert "category" not in query
    cutoff = query["publish_time"]["$lt"]
    assert abs((cutoff - (now - timedelta(days=90))).total_seconds()) < 60


def test_cleanup_expired_rejects_unknown_data_type():
    service = NewsDataService()
    service._collection = FakeCollection([])
    # 未知类型抛 ValueError，被内部捕获后返回 0（不误删数据）
    assert asyncio.run(service.cleanup_expired("unknown_type")) == 0


# ==================== 4. 存量 get_news 回归 + 新公告端点 ====================


@pytest.fixture()
def client():
    from app.routers import stocks as stocks_router
    from app.routers.auth_db import get_current_user

    app = FastAPI()
    app.include_router(stocks_router.router, prefix="/api")
    app.dependency_overrides[get_current_user] = lambda: {
        "id": "test",
        "username": "test",
        "is_admin": True,
    }
    with TestClient(app) as c:
        yield c


MIXED_DOCS = [
    {
        "title": "公告标题",
        "source": "tushare",
        "publish_time": datetime(2026, 10, 2, 10, 0, 0),
        "url": "http://x/ann",
        "content": "公告内容",
        "summary": "公告摘要",
        "category": ANNOUNCEMENT_CATEGORY,
    },
    {
        "title": "新闻标题1",
        "source": "tushare",
        "publish_time": datetime(2026, 10, 1, 10, 0, 0),
        "url": "http://x/n1",
        "content": "新闻内容1",
        "summary": "新闻摘要1",
        "category": "market_news",
    },
    {
        "title": "新闻标题2",
        "source": "akshare",
        "publish_time": datetime(2026, 9, 30, 10, 0, 0),
        "url": "http://x/n2",
        "content": "新闻内容2",
        "summary": "新闻摘要2",
        "category": "general",
    },
]


def test_get_news_regression_unchanged(client):
    """存量 get_news 行为回归：include_announcements 默认 True，公告仍混排在新闻里返回"""
    stub = StubNewsService(news=MIXED_DOCS)

    with patch("app.services.news_data_service.get_news_data_service", AsyncMock(return_value=stub)), \
         patch("app.worker.akshare_sync_service.get_akshare_sync_service", AsyncMock(return_value=AsyncMock())):
        resp = client.get("/api/stocks/000001/news", params={"days": 30, "limit": 50})

    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["code"] == "000001"
    assert data["days"] == 30
    assert data["limit"] == 50
    assert data["include_announcements"] is True  # 默认值不变
    assert data["source"] == "database"
    # 旧行为不变：公告依然混在新闻结果里返回（未做类型过滤）
    assert [item["title"] for item in data["items"]] == ["公告标题", "新闻标题1", "新闻标题2"]
    assert all(item["type"] == "news" for item in data["items"])


def test_get_news_regression_include_announcements_false_still_compatible(client):
    """include_announcements=False 传参兼容（响应字段回显不变）"""
    stub = StubNewsService(news=MIXED_DOCS)

    with patch("app.services.news_data_service.get_news_data_service", AsyncMock(return_value=stub)), \
         patch("app.worker.akshare_sync_service.get_akshare_sync_service", AsyncMock(return_value=AsyncMock())):
        resp = client.get("/api/stocks/000001/news", params={"include_announcements": False})

    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["include_announcements"] is False
    assert len(data["items"]) == 3


def test_announcements_endpoint_returns_only_announcements(client):
    """独立公告端点：只返回公告，且走公告独立查询入口"""
    announcement_docs = [doc for doc in MIXED_DOCS if doc["category"] == ANNOUNCEMENT_CATEGORY]
    stub = StubNewsService(news=announcement_docs)
    captured_params = []

    async def fake_query_announcements(params):
        captured_params.append(params)
        return list(announcement_docs)

    stub.query_announcements = fake_query_announcements

    with patch("app.services.news_data_service.get_news_data_service", AsyncMock(return_value=stub)), \
         patch("app.worker.news_data_sync_service.get_news_data_sync_service", AsyncMock(return_value=AsyncMock())):
        resp = client.get("/api/stocks/000001/announcements", params={"days": 90, "limit": 50})

    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["code"] == "000001"
    assert data["data_type"] == "announcement"
    assert len(captured_params) == 1
    assert captured_params[0].symbol == "000001"
    assert [item["title"] for item in data["items"]] == ["公告标题"]
    assert all(item["type"] == "announcement" for item in data["items"])
    assert all(item["category"] == ANNOUNCEMENT_CATEGORY for item in data["items"])
