"""
修复 news_analyst_v2 的工具绑定。

问题：数据库中遗留了 get_stock_news_unified / get_weather 等旧绑定，
会覆盖代码里的 split tools 配置，导致 runtime 仍然只加载旧工具。

使用方法：
    C:/TradingAgentsCN/env/Scripts/python.exe scripts/fix_news_analyst_tool_bindings.py
"""

import asyncio
import sys
from datetime import datetime
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.core.database import get_mongo_db, init_database
from core.tools import get_tool_registry


AGENT_ID = "news_analyst_v2"
REQUIRED_TOOLS = [
    ("get_stock_news_headlines_unified", 200),
    ("get_stock_news_details_unified", 190),
]
LEGACY_TOOLS = {"get_stock_news_unified"}


async def main():
    print("=" * 80)
    print("修复 news_analyst_v2 的工具绑定")
    print("=" * 80)

    print("\n📡 连接数据库...")
    await init_database()
    db = get_mongo_db()
    print("✅ 数据库连接成功")

    registry = get_tool_registry()
    registered_tools = set(registry._tools.keys())

    print("\n1. 当前激活绑定:")
    current_bindings = await db.tool_agent_bindings.find(
        {"agent_id": AGENT_ID, "is_active": {"$ne": False}}
    ).sort("priority", -1).to_list(length=None)

    for binding in current_bindings:
        print(
            f"   - tool_id={binding.get('tool_id')} "
            f"priority={binding.get('priority', 0)} is_active={binding.get('is_active', True)}"
        )

    invalid_or_legacy_tools = []
    for binding in current_bindings:
        tool_id = binding.get("tool_id")
        if tool_id in LEGACY_TOOLS or tool_id not in registered_tools:
            invalid_or_legacy_tools.append(tool_id)

    print("\n2. 停用旧绑定/脏绑定:")
    if invalid_or_legacy_tools:
        result = await db.tool_agent_bindings.update_many(
            {
                "agent_id": AGENT_ID,
                "tool_id": {"$in": invalid_or_legacy_tools},
                "is_active": {"$ne": False},
            },
            {
                "$set": {
                    "is_active": False,
                    "updated_at": datetime.utcnow().isoformat(),
                }
            },
        )
        print(f"   ✅ 已停用 {result.modified_count} 条记录: {invalid_or_legacy_tools}")
    else:
        print("   ℹ️  未发现需要停用的旧绑定")

    print("\n3. 确保 split tools 绑定存在且激活:")
    for tool_id, priority in REQUIRED_TOOLS:
        result = await db.tool_agent_bindings.update_one(
            {"agent_id": AGENT_ID, "tool_id": tool_id},
            {
                "$set": {
                    "agent_id": AGENT_ID,
                    "tool_id": tool_id,
                    "priority": priority,
                    "is_active": True,
                    "updated_at": datetime.utcnow().isoformat(),
                },
                "$setOnInsert": {
                    "created_at": datetime.utcnow().isoformat(),
                },
            },
            upsert=True,
        )

        action = "插入" if result.upserted_id is not None else "更新/确认"
        print(f"   ✅ {action}: {tool_id} (priority={priority})")

    print("\n4. 修复后激活绑定:")
    updated_bindings = await db.tool_agent_bindings.find(
        {"agent_id": AGENT_ID, "is_active": {"$ne": False}}
    ).sort("priority", -1).to_list(length=None)

    for binding in updated_bindings:
        print(
            f"   ✅ tool_id={binding.get('tool_id')} "
            f"priority={binding.get('priority', 0)}"
        )

    print("\n" + "=" * 80)
    print("✅ 修复完成")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())