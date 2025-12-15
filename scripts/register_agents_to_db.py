#!/usr/bin/env python3
"""
注册所有 Agent 到 MongoDB
将 core/agents/config.py 中的 Agent 配置同步到数据库
"""

import sys
import os
from pathlib import Path
from datetime import datetime
from pymongo import MongoClient, UpdateOne

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# 导入 Agent 配置
try:
    from core.agents.config import BUILTIN_AGENTS as AGENTS, AgentMetadata
except ImportError:
    try:
        from core.agents.config import AGENTS, AgentMetadata
    except ImportError as e:
        print(f"❌ 无法导入 Agent 配置: {e}")
        sys.exit(1)

def get_mongo_client():
    """获取 MongoDB 客户端"""
    # 优先使用环境变量
    mongo_uri = os.getenv("MONGODB_CONNECTION_STRING") or os.getenv("MONGO_URI") or "mongodb://admin:tradingagents123@localhost:27017/tradingagents?authSource=admin"
    db_name = os.getenv("MONGODB_DATABASE_NAME") or os.getenv("MONGO_DB") or "tradingagents"
    
    print(f"🔌 连接到 MongoDB: {mongo_uri.split('@')[-1]}")  # 隐藏密码
    
    try:
        client = MongoClient(mongo_uri, serverSelectionTimeoutMS=5000)
        client.admin.command('ping')
        return client, client[db_name]
    except Exception as e:
        print(f"❌ MongoDB 连接失败: {e}")
        return None, None

def register_agents():
    """注册所有 Agent"""
    client, db = get_mongo_client()
    if db is None:
        return

    collection = db["agent_configs"]
    operations = []
    
    print(f"\n📋 准备注册 {len(AGENTS)} 个 Agent...")
    
    for agent_id, agent in AGENTS.items():
        # 构建文档
        doc = {
            "agent_id": agent.id,
            "name": agent.name,
            "description": agent.description,
            "category": agent.category.value if hasattr(agent.category, "value") else str(agent.category),
            "icon": agent.icon,
            "color": agent.color,
            "tags": agent.tags,
            "tools": agent.tools,
            "default_tools": agent.default_tools,
            "max_tool_calls": agent.max_tool_calls,
            "requires_tools": agent.requires_tools,
            "output_field": agent.output_field,
            "report_label": agent.report_label,
            "node_name": agent.node_name,
            "execution_order": agent.execution_order,
            "is_active": True,  # 默认为激活状态
            "updated_at": datetime.utcnow()
        }
        
        # 处理可能的额外字段 (如 v2 架构的 inputs/outputs)
        if hasattr(agent, "inputs") and agent.inputs:
            doc["inputs"] = [
                {"name": i.name, "type": i.type, "description": i.description} 
                for i in agent.inputs
            ]
            
        if hasattr(agent, "outputs") and agent.outputs:
            doc["outputs"] = [
                {"name": o.name, "type": o.type, "description": o.description}
                for o in agent.outputs
            ]
            
        # 准备 upsert 操作
        operations.append(
            UpdateOne(
                {"agent_id": agent.id},
                {"$set": doc},
                upsert=True
            )
        )
        print(f"  - 准备注册: {agent.name} ({agent.id})")

    if operations:
        try:
            result = collection.bulk_write(operations)
            print(f"\n✅ 注册完成:")
            print(f"   - 匹配: {result.matched_count}")
            print(f"   - 修改: {result.modified_count}")
            print(f"   - 插入: {result.upserted_count}")
            
            # 验证结果
            count = collection.count_documents({})
            print(f"   - 当前数据库中共有 {count} 个 Agent 配置")
            
        except Exception as e:
            print(f"❌ 批量写入失败: {e}")
    else:
        print("⚠️ 没有需要注册的 Agent")

if __name__ == "__main__":
    register_agents()
