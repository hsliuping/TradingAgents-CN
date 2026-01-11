"""
检查数据库中的 tool_configs 集合
"""

import logging
from pymongo import MongoClient
import os
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()

def check_tool_configs():
    """检查 tool_configs 集合"""

    # 连接数据库
    mongo_host = os.getenv("MONGODB_HOST", "localhost")
    mongo_port = int(os.getenv("MONGODB_PORT", "27017"))
    mongo_user = os.getenv("MONGODB_USER", "")
    mongo_password = os.getenv("MONGODB_PASSWORD", "")
    db_name = os.getenv("MONGODB_DB_NAME", "tradingagents")

    # 构建连接 URI
    if mongo_user and mongo_password:
        mongo_uri = f"mongodb://{mongo_user}:{mongo_password}@{mongo_host}:{mongo_port}/{db_name}"
    else:
        mongo_uri = f"mongodb://{mongo_host}:{mongo_port}/{db_name}"

    logger.info(f"连接数据库: {mongo_host}:{mongo_port}/{db_name}")

    client = MongoClient(mongo_uri)
    db = client[db_name]
    
    logger.info("=" * 80)
    logger.info("检查 tool_configs 集合")
    logger.info("=" * 80)
    
    # 统计
    total_count = db.tool_configs.count_documents({})
    enabled_count = db.tool_configs.count_documents({"enabled": True})
    disabled_count = db.tool_configs.count_documents({"enabled": False})
    
    logger.info(f"\n📊 统计:")
    logger.info(f"  - 总数: {total_count}")
    logger.info(f"  - 启用: {enabled_count}")
    logger.info(f"  - 禁用: {disabled_count}")
    
    # 按分类统计
    logger.info(f"\n📁 按分类统计:")
    pipeline = [
        {"$group": {"_id": "$category", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}}
    ]
    for item in db.tool_configs.aggregate(pipeline):
        logger.info(f"  - {item['_id']}: {item['count']}")
    
    # 列出所有工具
    logger.info(f"\n📋 所有工具配置:")
    logger.info("-" * 80)
    
    tools = list(db.tool_configs.find({}).sort("category", 1))
    
    current_category = None
    for tool in tools:
        category = tool.get("category", "unknown")
        tool_id = tool.get("tool_id", "unknown")
        name = tool.get("name", "")
        enabled = tool.get("enabled", True)
        
        if category != current_category:
            logger.info(f"\n[{category.upper()}]")
            current_category = category
        
        status = "✅" if enabled else "❌"
        logger.info(f"  {status} {tool_id}")
        if name:
            logger.info(f"     名称: {name}")
        
        # 显示配置
        config = tool.get("config", {})
        if config:
            logger.info(f"     配置: timeout={config.get('timeout', 30)}, "
                       f"retry={config.get('retry_count', 3)}, "
                       f"cache_ttl={config.get('cache_ttl', 300)}")
    
    # 检查是否有不存在的工具
    logger.info(f"\n⚠️ 检查不存在的工具:")
    logger.info("-" * 80)
    
    # 从代码中获取所有已注册的工具
    from core.tools.registry import ToolRegistry
    registry = ToolRegistry()
    registered_tools = set(registry.list_all())
    
    logger.info(f"  - 代码中已注册工具数: {len(registered_tools)}")
    
    # 检查数据库中的工具是否都存在于代码中
    db_tool_ids = set(tool.get("tool_id") for tool in tools)
    logger.info(f"  - 数据库中工具配置数: {len(db_tool_ids)}")
    
    # 数据库中有但代码中没有的
    not_in_code = db_tool_ids - registered_tools
    if not_in_code:
        logger.warning(f"\n  ❌ 数据库中有但代码中未注册的工具 ({len(not_in_code)}):")
        for tool_id in sorted(not_in_code):
            logger.warning(f"     - {tool_id}")
    else:
        logger.info(f"\n  ✅ 所有数据库中的工具都已在代码中注册")
    
    # 代码中有但数据库中没有的
    not_in_db = registered_tools - db_tool_ids
    if not_in_db:
        logger.info(f"\n  ℹ️ 代码中有但数据库中未配置的工具 ({len(not_in_db)}):")
        for tool_id in sorted(not_in_db):
            logger.info(f"     - {tool_id}")
    
    client.close()


if __name__ == "__main__":
    check_tool_configs()

