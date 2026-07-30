"""测试 DashScope text-embedding-v4 实际返回维度。"""
import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

import httpx
from pymongo import MongoClient

MONGO_HOST = os.environ.get("MONGODB_HOST", "127.0.0.1")
MONGO_USER = os.environ.get("MONGODB_USERNAME", "")
MONGO_PASS = os.environ.get("MONGODB_PASSWORD", "")
MONGO_AUTH_SOURCE = os.environ.get("MONGODB_AUTH_SOURCE", "admin")
MONGO_PORT = 27019
MONGO_DB = os.environ.get("MONGODB_DATABASE", "tradingagents")

if MONGO_USER and MONGO_PASS:
    MONGO_URI = f"mongodb://{MONGO_USER}:{MONGO_PASS}@{MONGO_HOST}:{MONGO_PORT}/?authSource={MONGO_AUTH_SOURCE}"
else:
    MONGO_URI = f"mongodb://{MONGO_HOST}:{MONGO_PORT}/"


def get_dashscope_key():
    client = MongoClient(MONGO_URI)
    db = client[MONGO_DB]
    doc = db.llm_providers.find_one({"name": "dashscope", "is_active": True})
    if not doc:
        return None
    return str(doc.get("api_key") or "").strip()


async def test_dims(dimensions=None):
    key = get_dashscope_key()
    if not key:
        print("未找到 dashscope api key")
        return
    payload = {"model": "text-embedding-v4", "input": "测试"}
    if dimensions:
        payload["dimensions"] = dimensions
    async with httpx.AsyncClient() as c:
        r = await c.post(
            "https://dashscope.aliyuncs.com/compatible-mode/v1/embeddings",
            headers={"Authorization": f"Bearer {key}"},
            json=payload,
        )
        print(f"dimensions param={dimensions}, status={r.status_code}")
        if r.status_code == 200:
            data = r.json()
            emb = data["data"][0]["embedding"]
            print(f"  returned dims={len(emb)}")
        else:
            print(f"  error: {r.text[:200]}")


async def main():
    await test_dims(None)
    await test_dims(1024)
    await test_dims(1536)


if __name__ == "__main__":
    asyncio.run(main())
