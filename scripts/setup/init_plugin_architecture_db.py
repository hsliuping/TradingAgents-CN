#!/usr/bin/env python3
"""
插件化架构数据库初始化脚本

创建以下集合：
1. tool_configs - 工具配置
2. agent_configs - Agent配置
3. workflow_definitions - 工作流定义
4. tool_agent_bindings - 工具-Agent绑定
5. agent_workflow_bindings - Agent-工作流绑定
6. agent_io_definitions - Agent输入输出定义
"""

import sys
from pathlib import Path
from datetime import datetime

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from pymongo import MongoClient, ASCENDING, DESCENDING
from pymongo.errors import CollectionInvalid


def get_mongo_client():
    """获取MongoDB客户端"""
    import os
    from dotenv import load_dotenv

    # 加载 .env 文件
    load_dotenv()

    mongo_uri = os.getenv("MONGO_URI", "mongodb://localhost:27017")
    mongo_db = os.getenv("MONGO_DB", "tradingagents")

    print(f"📡 MongoDB URI: {mongo_uri[:50]}...")

    client = MongoClient(mongo_uri)
    return client, client[mongo_db]


def create_collections_and_indexes(db):
    """创建集合和索引"""
    
    collections_config = {
        # 工具配置
        "tool_configs": {
            "indexes": [
                {"keys": [("tool_id", ASCENDING)], "unique": True},
                {"keys": [("category", ASCENDING)]},
                {"keys": [("is_active", ASCENDING)]},
            ]
        },
        # Agent配置
        "agent_configs": {
            "indexes": [
                {"keys": [("agent_id", ASCENDING)], "unique": True},
                {"keys": [("category", ASCENDING)]},
                {"keys": [("is_active", ASCENDING)]},
            ]
        },
        # 工作流定义
        "workflow_definitions": {
            "indexes": [
                {"keys": [("workflow_id", ASCENDING)], "unique": True},
                {"keys": [("is_template", ASCENDING)]},
                {"keys": [("tags", ASCENDING)]},
            ]
        },
        # 工具-Agent绑定
        "tool_agent_bindings": {
            "indexes": [
                {"keys": [("agent_id", ASCENDING), ("tool_id", ASCENDING)], "unique": True},
                {"keys": [("agent_id", ASCENDING)]},
                {"keys": [("tool_id", ASCENDING)]},
            ]
        },
        # Agent-工作流绑定
        "agent_workflow_bindings": {
            "indexes": [
                {"keys": [("workflow_id", ASCENDING), ("agent_id", ASCENDING)], "unique": True},
                {"keys": [("workflow_id", ASCENDING)]},
                {"keys": [("agent_id", ASCENDING)]},
            ]
        },
        # Agent输入输出定义
        "agent_io_definitions": {
            "indexes": [
                {"keys": [("agent_id", ASCENDING)], "unique": True},
            ]
        },
    }
    
    created = []
    existing = []
    
    for collection_name, config in collections_config.items():
        # 创建集合
        try:
            db.create_collection(collection_name)
            created.append(collection_name)
            print(f"✅ 创建集合: {collection_name}")
        except CollectionInvalid:
            existing.append(collection_name)
            print(f"📋 集合已存在: {collection_name}")
        
        # 创建索引
        collection = db[collection_name]
        for idx_config in config.get("indexes", []):
            try:
                collection.create_index(
                    idx_config["keys"],
                    unique=idx_config.get("unique", False)
                )
            except Exception as e:
                print(f"⚠️ 创建索引失败 ({collection_name}): {e}")
    
    return created, existing


def insert_initial_data(db):
    """插入初始数据"""
    now = datetime.utcnow().isoformat()
    
    # 插入默认工具配置示例
    tool_configs = db["tool_configs"]
    sample_tool = {
        "tool_id": "get_stock_market_data_unified",
        "name": "统一股票市场数据",
        "description": "获取统一格式的股票市场数据",
        "category": "market",
        "module_path": "tradingagents.dataflows.interface",
        "function_name": "get_stock_data_unified",
        "parameters": [
            {"name": "ticker", "type": "string", "required": True},
            {"name": "start_date", "type": "string", "required": True},
            {"name": "end_date", "type": "string", "required": True},
        ],
        "is_active": True,
        "is_builtin": True,
        "created_at": now,
        "updated_at": now,
    }
    
    try:
        tool_configs.update_one(
            {"tool_id": sample_tool["tool_id"]},
            {"$set": sample_tool},
            upsert=True
        )
        print(f"✅ 插入示例工具配置: {sample_tool['tool_id']}")
    except Exception as e:
        print(f"⚠️ 插入工具配置失败: {e}")


def main():
    """主函数"""
    print("=" * 60)
    print("🚀 插件化架构数据库初始化")
    print("=" * 60)
    
    try:
        client, db = get_mongo_client()
        print(f"📦 连接数据库: {db.name}")
        
        # 创建集合和索引
        created, existing = create_collections_and_indexes(db)
        
        # 插入初始数据
        insert_initial_data(db)
        
        print("\n" + "=" * 60)
        print(f"✅ 初始化完成!")
        print(f"   - 新建集合: {len(created)}")
        print(f"   - 已存在: {len(existing)}")
        print("=" * 60)
        
    except Exception as e:
        print(f"❌ 初始化失败: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

