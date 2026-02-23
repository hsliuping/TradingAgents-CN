"""
v2_stock_analysis 流程专属提示词模板种子脚本

从默认模板复制，为 v2_stock_analysis 工作流创建流程绑定的提示词模板。
用户可在前端或 API 中按 workflow_id 筛选、创建、编辑这些模板，实现「按流程+agent 获取配置」。

用法:
    python scripts/seed_stock_workflow_templates.py          # 创建/更新流程专属模板
    python scripts/seed_stock_workflow_templates.py --reset  # 重置后重新创建
"""

import asyncio
import os
import sys
from pathlib import Path
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()


def build_mongo_uri():
    """构建 MongoDB URI"""
    host = os.getenv("MONGODB_HOST", "localhost")
    port = int(os.getenv("MONGODB_PORT", "27017"))
    db = os.getenv("MONGODB_DATABASE", os.getenv("MONGODB_DB_NAME", "tradingagents"))
    user = os.getenv("MONGODB_USERNAME", "")
    pwd = os.getenv("MONGODB_PASSWORD", "")
    auth_src = os.getenv("MONGODB_AUTH_SOURCE", "admin")

    full_uri = os.getenv("MONGO_URI") or os.getenv("MONGODB_URL")
    if full_uri and ("@" in full_uri or "localhost" in full_uri):
        return full_uri, db

    if user and pwd:
        return f"mongodb://{user}:{pwd}@{host}:{port}/{db}?authSource={auth_src}", db
    return f"mongodb://{host}:{port}/{db}", db


# v2_stock_analysis 工作流中的 Agent（agent_type, agent_name，与流程定义一致）
STOCK_WORKFLOW_ID = "v2_stock_analysis"
STOCK_WORKFLOW_AGENTS = [
    # 分析师
    ("analysts_v2", "index_analyst_v2"),
    ("analysts_v2", "sector_analyst_v2"),
    ("analysts_v2", "market_analyst_v2"),
    ("analysts_v2", "fundamentals_analyst_v2"),
    ("analysts_v2", "news_analyst_v2"),
    ("analysts_v2", "social_analyst_v2"),
    # 研究员
    ("researchers_v2", "bull_researcher_v2"),
    ("researchers_v2", "bear_researcher_v2"),
    # 管理者
    ("managers_v2", "research_manager_v2"),
    ("managers_v2", "risk_manager_v2"),
    # 交易员
    ("trader_v2", "trader_v2"),
    # 风险分析师
    ("debators_v2", "risky_analyst_v2"),
    ("debators_v2", "safe_analyst_v2"),
    ("debators_v2", "neutral_analyst_v2"),
]


async def seed_stock_workflow_templates(reset: bool = False):
    """从默认模板复制，为 v2_stock_analysis 创建流程专属提示词"""
    from motor.motor_asyncio import AsyncIOMotorClient

    mongo_uri, db_name = build_mongo_uri()
    client = AsyncIOMotorClient(mongo_uri)
    db = client[db_name]
    collection = db["prompt_templates"]

    if reset:
        result = await collection.delete_many({
            "workflow_id": STOCK_WORKFLOW_ID,
        })
        print(f"🗑️ 删除现有 v2_stock_analysis 流程专属模板: {result.deleted_count} 个")

    created = 0
    updated = 0
    skipped = 0

    for agent_type, agent_name in STOCK_WORKFLOW_AGENTS:
        # 查找默认模板（workflow_id 不存在或为 None）
        default_query = {
            "agent_type": agent_type,
            "agent_name": agent_name,
            "is_system": True,
            "status": "active",
            "$or": [
                {"workflow_id": {"$exists": False}},
                {"workflow_id": None},
            ]
        }
        # 优先 neutral，其次任意 preference
        default_template = await collection.find_one(
            {**default_query, "preference_type": "neutral"}
        )
        if not default_template:
            default_template = await collection.find_one(default_query)

        if not default_template:
            print(f"  ⏭️ 跳过 {agent_name}: 未找到默认模板")
            skipped += 1
            continue

        existing = await collection.find_one({
            "agent_type": agent_type,
            "agent_name": agent_name,
            "workflow_id": STOCK_WORKFLOW_ID,
            "is_system": True,
        })

        doc = {
            "agent_type": agent_type,
            "agent_name": agent_name,
            "workflow_id": STOCK_WORKFLOW_ID,
            "template_name": f"[股票流程] {default_template.get('template_name', agent_name)}",
            "preference_type": default_template.get("preference_type", "neutral"),
            "content": default_template.get("content", {}),
            "is_system": True,
            "status": "active",
            "version": default_template.get("version", 2),
            "remark": f"v2_stock_analysis 流程专属，按 workflow_id+agent_id 加载",
            "updated_at": datetime.now(timezone.utc),
        }

        if existing:
            await collection.update_one({"_id": existing["_id"]}, {"$set": doc})
            print(f"  🔄 更新流程专属: {agent_name} (workflow_id={STOCK_WORKFLOW_ID})")
            updated += 1
        else:
            doc["created_at"] = datetime.now(timezone.utc)
            await collection.insert_one(doc)
            print(f"  ✅ 创建流程专属: {agent_name} (workflow_id={STOCK_WORKFLOW_ID})")
            created += 1

    client.close()
    print(f"\n📊 v2_stock_analysis 流程专属模板: 创建 {created} 个, 更新 {updated} 个, 跳过 {skipped} 个")
    return created, updated, skipped


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="初始化 v2_stock_analysis 流程专属提示词模板")
    parser.add_argument("--reset", action="store_true", help="重置（删除现有流程专属模板后重新创建）")
    args = parser.parse_args()

    asyncio.run(seed_stock_workflow_templates(reset=args.reset))
