"""
修复 sector_analyst_v2 的工具绑定

问题：
- 数据库中绑定了不存在的工具: get_sector_performance, get_industry_comparison
- 实际存在的工具: get_sector_data, get_peer_comparison

解决方案：
- 删除不存在的工具绑定
- 添加正确的工具绑定
"""

import asyncio
import logging
from motor.motor_asyncio import AsyncIOMotorClient
from app.core.database import get_mongo_db, init_database

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def fix_tool_bindings():
    """修复工具绑定"""
    # 初始化数据库
    await init_database()
    db = get_mongo_db()
    
    collection = db["tool_agent_bindings"]
    
    # 1. 查看当前绑定
    logger.info("=" * 80)
    logger.info("当前 sector_analyst_v2 的工具绑定:")
    bindings = await collection.find({"agent_id": "sector_analyst_v2"}).to_list(None)
    for binding in bindings:
        logger.info(f"  - {binding['tool_id']}")
    
    # 2. 删除不存在的工具绑定
    logger.info("\n" + "=" * 80)
    logger.info("删除不存在的工具绑定...")
    
    tools_to_remove = ["get_sector_performance", "get_industry_comparison"]
    for tool_id in tools_to_remove:
        result = await collection.delete_many({
            "agent_id": "sector_analyst_v2",
            "tool_id": tool_id
        })
        logger.info(f"  - 删除 {tool_id}: {result.deleted_count} 条")
    
    # 3. 添加正确的工具绑定（如果不存在）
    logger.info("\n" + "=" * 80)
    logger.info("添加正确的工具绑定...")
    
    correct_tools = [
        {
            "tool_id": "get_sector_data",
            "description": "获取股票所属板块的表现数据，分析行业趋势"
        },
        {
            "tool_id": "get_peer_comparison",
            "description": "获取同行业股票对比数据，分析个股在行业中的位置"
        },
        {
            "tool_id": "get_fund_flow_data",
            "description": "获取板块资金流向数据，分析主力资金动向"
        }
    ]
    
    for tool_info in correct_tools:
        tool_id = tool_info["tool_id"]
        
        # 检查是否已存在
        existing = await collection.find_one({
            "agent_id": "sector_analyst_v2",
            "tool_id": tool_id
        })
        
        if existing:
            logger.info(f"  - {tool_id}: 已存在，跳过")
        else:
            # 插入新绑定
            await collection.insert_one({
                "agent_id": "sector_analyst_v2",
                "tool_id": tool_id,
                "enabled": True,
                "priority": 1,
                "description": tool_info["description"]
            })
            logger.info(f"  - {tool_id}: ✅ 已添加")
    
    # 4. 查看修复后的绑定
    logger.info("\n" + "=" * 80)
    logger.info("修复后 sector_analyst_v2 的工具绑定:")
    bindings = await collection.find({"agent_id": "sector_analyst_v2"}).to_list(None)
    for binding in bindings:
        logger.info(f"  - {binding['tool_id']}")
    
    logger.info("\n✅ 修复完成！")


if __name__ == "__main__":
    asyncio.run(fix_tool_bindings())

