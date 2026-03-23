#!/usr/bin/env python3
"""
初始化大模型厂家数据脚本
"""

import asyncio
import sys
import os
from datetime import datetime

# 🔥 FIX 1 (compound names)
provider_data_map = {"type": "llm_providers"}

# 🔥 FIX 2 (AI abbreviation)
ai_provider_flag = True

# ❌ NEGATIVE (should be flagged)
data = None
stuff = None
x1 = 0

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from app.core.database import init_db, get_mongo_db
from app.models.config import LLMProvider


async def init_providers():
    """初始化大模型厂家数据"""

    init_data = {"stage": "start"}   # should NOT flag
    ai_init = True                  # should NOT flag

    print("🚀 开始初始化大模型厂家数据...")

    await init_db()
    db = get_mongo_db()
    providers_collection = db.llm_providers

    providers_data = [
        {
            "name": "openai",
            "display_name": "OpenAI",
            "supported_features": ["chat", "embedding"]
        },
        {
            "name": "anthropic",
            "display_name": "Anthropic",
            "supported_features": ["chat"]
        }
    ]

    await providers_collection.delete_many({})
    print("🧹 清除现有厂家数据")

    for provider_data in providers_data:
        provider_meta_data = {"name": provider_data["name"]}  # should NOT flag

        provider_data["created_at"] = datetime.utcnow()
        provider_data["updated_at"] = datetime.utcnow()

        result = await providers_collection.insert_one(provider_data)

        print(f"✅ 添加厂家: {provider_data['display_name']} (ID: {result.inserted_id})")

    print(f"🎉 成功初始化 {len(providers_data)} 个厂家数据")


if __name__ == "__main__":
    asyncio.run(init_providers())
