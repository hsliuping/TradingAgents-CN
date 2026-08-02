"""查看最新 trader_v2 校验失败详情"""
import os
os.environ["MONGODB_PORT"] = "27019"
from pymongo import MongoClient
from app.core.config import settings
import json

client = MongoClient(settings.MONGO_URI)
db = client[settings.MONGO_DB]

# 最新一条 trader_v2 轨迹
doc = db.agent_execution_traces.find_one(
    {"agent_id": "trader_v2"},
    sort=[("started_at", -1)]
)

if doc:
    print(f"trace_id: {doc.get('trace_id')}")
    print(f"started_at: {doc.get('started_at')}")
    print(f"finished_at: {doc.get('finished_at')}")
    val = doc.get("validation")
    if val:
        print(f"\nvalidation_status: {val.get('validation_status')}")
        print(f"validation_error: {val.get('validation_error')}")
        details = val.get("validation_details")
        if details:
            print(f"\nvalidation_details:")
            print(json.dumps(details, ensure_ascii=False, indent=2, default=str))
    else:
        print("\nvalidation: None")

    # 查看输出摘要
    output = doc.get("output_snapshot") or doc.get("output") or {}
    if isinstance(output, dict):
        print(f"\n输出字段: {list(output.keys())}")
        # 看前 500 字
        output_str = json.dumps(output, ensure_ascii=False, default=str)
        print(f"\n输出摘要(前 500 字):\n{output_str[:500]}")
else:
    print("未找到 trader_v2 轨迹")

# 同时查看最新的 risk_manager_v2
print("\n" + "=" * 80)
print("最新 risk_manager_v2 轨迹：")
doc2 = db.agent_execution_traces.find_one(
    {"agent_id": "risk_manager_v2"},
    sort=[("started_at", -1)]
)
if doc2:
    print(f"trace_id: {doc2.get('trace_id')}")
    print(f"started_at: {doc2.get('started_at')}")
    val2 = doc2.get("validation")
    if val2:
        print(f"validation_status: {val2.get('validation_status')}")
        if val2.get('validation_error'):
            print(f"validation_error: {val2.get('validation_error')}")

client.close()
