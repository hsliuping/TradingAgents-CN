"""验证最新分析的轨迹和校验状态"""
import os
# 🔧 强制使用 v3.0 端口 27019（与 start_dev.ps1 backend 3.0 一致）
os.environ["MONGODB_PORT"] = "27019"
from pymongo import MongoClient
from app.core.config import settings

print(f"MONGODB_URI port: {settings.MONGO_URI.split('@')[-1].split('/')[0] if '@' in settings.MONGO_URI else settings.MONGO_URI}")
print(f"MONGO_DB: {settings.MONGO_DB}")
print("=" * 100)

client = MongoClient(settings.MONGO_URI)
db = client[settings.MONGO_DB]

# 1. 查看最近 20 条轨迹
print("\n📋 最近 20 条执行轨迹：")
cur = db.agent_execution_traces.find(
    {},
    {"trace_id": 1, "agent_id": 1, "started_at": 1, "validation.validation_status": 1}
).sort("started_at", -1).limit(20)

count = 0
for d in cur:
    count += 1
    started = d.get("started_at", "?")
    agent = d.get("agent_id", "?")
    val = d.get("validation")
    status = val.get("validation_status", "?") if val else "None"
    print(f"  {started} | {agent:35} | validation={status}")

print(f"\n总计: {count} 条")

# 2. 统计今天的轨迹
from datetime import datetime, timezone
today_start = datetime(2026, 7, 28, tzinfo=timezone.utc)
today_count = db.agent_execution_traces.count_documents({"started_at": {"$gte": today_start}})
print(f"\n📊 今天(07-28)的轨迹数: {today_count}")

# 3. 检查 trader_v2 的 validation_status
print("\n🔍 trader_v2 轨迹的 validation_status 分布：")
pipeline = [
    {"$match": {"agent_id": "trader_v2"}},
    {"$group": {"_id": "$validation.validation_status", "count": {"$sum": 1}}},
]
for doc in db.agent_execution_traces.aggregate(pipeline):
    print(f"  validation_status={doc['_id']}: {doc['count']} 条")

# 4. 检查 risk_manager_v2 的 validation_status
print("\n🔍 risk_manager_v2 轨迹的 validation_status 分布：")
pipeline = [
    {"$match": {"agent_id": "risk_manager_v2"}},
    {"$group": {"_id": "$validation.validation_status", "count": {"$sum": 1}}},
]
for doc in db.agent_execution_traces.aggregate(pipeline):
    print(f"  validation_status={doc['_id']}: {doc['count']} 条")

# 5. 检查断言集合
print("\n📋 断言集合 (agent_assertions)：")
assertion_count = db.agent_assertions.count_documents({})
print(f"  总数: {assertion_count}")
enabled_count = db.agent_assertions.count_documents({"is_enabled": True})
print(f"  启用: {enabled_count}")

client.close()
