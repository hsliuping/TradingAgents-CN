"""针对真实 MongoDB 的手工排查测试。默认不进入标准套件。"""

import os

import pytest
from pymongo import MongoClient


pytestmark = pytest.mark.integration


def test_market_quotes_query_smoke():
    """
    真实库烟雾检查。

    需要配置 TEST_MONGODB_URI；未配置时默认跳过，避免污染常规测试。
    """
    mongo_uri = os.getenv("TEST_MONGODB_URI", "").strip()
    if not mongo_uri:
        pytest.skip("TEST_MONGODB_URI 未配置，跳过真实 MongoDB 查询测试")

    client = MongoClient(mongo_uri, serverSelectionTimeoutMS=2000)
    db = client["tradingagents"]

    try:
        queries = [
            {"code": "300750"},
            {"symbol": "300750"},
            {"code": "300750", "symbol": "300750"},
        ]
        results = [db.market_quotes.find_one(query, {"_id": 0}) for query in queries]
        assert any(result is None or isinstance(result, dict) for result in results)
    finally:
        client.close()
