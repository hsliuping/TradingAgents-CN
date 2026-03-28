"""针对真实 MongoDB 用户表的手工检查测试。默认不进入标准套件。"""

import os

import pytest
from pymongo import MongoClient


pytestmark = pytest.mark.integration


def test_user_collection_smoke():
    """
    真实库 smoke test。

    需要配置 TEST_MONGODB_URI；默认跳过，避免本地数据库依赖进入标准套件。
    """
    mongo_uri = os.getenv("TEST_MONGODB_URI", "").strip()
    if not mongo_uri:
        pytest.skip("TEST_MONGODB_URI 未配置，跳过真实 MongoDB 用户检查")

    client = MongoClient(mongo_uri, serverSelectionTimeoutMS=2000)

    try:
        db = client["tradingagents"]
        collection_names = db.list_collection_names()
        assert isinstance(collection_names, list)

        if "users" in collection_names:
            admin_user = db.users.find_one({"username": "admin"})
            assert admin_user is None or admin_user.get("username") == "admin"
    finally:
        client.close()
