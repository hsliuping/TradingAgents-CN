"""
初始化交易复盘工作流到 MongoDB

运行方式:
    python scripts/init_trade_review_workflow.py

功能:
    1. 将交易复盘工作流保存到 workflows 集合
    2. 如果已存在则更新版本
"""

import os
import sys
from datetime import datetime
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# 加载环境变量
from dotenv import load_dotenv
load_dotenv()


def init_trade_review_workflow():
    """初始化交易复盘工作流"""
    from pymongo import MongoClient
    from core.workflow.templates.trade_review_workflow import TRADE_REVIEW_WORKFLOW
    
    # 连接 MongoDB
    mongo_uri = os.getenv(
        "MONGODB_CONNECTION_STRING",
        "mongodb://admin:tradingagents123@127.0.0.1:27017/tradingagents?authSource=admin"
    )
    db_name = os.getenv("MONGODB_DATABASE_NAME", "tradingagents")
    
    print(f"📦 连接 MongoDB: {db_name}")
    client = MongoClient(mongo_uri)
    db = client[db_name]
    
    # 检查是否已存在
    existing = db.workflows.find_one({"id": TRADE_REVIEW_WORKFLOW.id})
    
    # 准备文档
    doc = TRADE_REVIEW_WORKFLOW.to_dict()
    doc["updated_at"] = datetime.utcnow().isoformat()
    doc["created_by"] = "system"
    doc["is_system"] = True
    
    if existing:
        # 更新
        old_version = existing.get("version", "1.0.0")
        # 增加次版本号
        parts = old_version.split(".")
        parts[-1] = str(int(parts[-1]) + 1)
        new_version = ".".join(parts)
        doc["version"] = new_version
        
        result = db.workflows.update_one(
            {"id": TRADE_REVIEW_WORKFLOW.id},
            {"$set": doc}
        )
        print(f"✅ 已更新交易复盘工作流: {TRADE_REVIEW_WORKFLOW.id}")
        print(f"   版本: {old_version} -> {new_version}")
        print(f"   修改数: {result.modified_count}")
    else:
        # 插入
        doc["created_at"] = datetime.utcnow().isoformat()
        result = db.workflows.insert_one(doc)
        print(f"✅ 已创建交易复盘工作流: {TRADE_REVIEW_WORKFLOW.id}")
        print(f"   版本: {doc['version']}")
        print(f"   ID: {result.inserted_id}")
    
    # 显示工作流信息
    print(f"\n📋 工作流详情:")
    print(f"   名称: {TRADE_REVIEW_WORKFLOW.name}")
    print(f"   描述: {TRADE_REVIEW_WORKFLOW.description}")
    print(f"   节点数: {len(TRADE_REVIEW_WORKFLOW.nodes)}")
    print(f"   边数: {len(TRADE_REVIEW_WORKFLOW.edges)}")
    print(f"   标签: {', '.join(TRADE_REVIEW_WORKFLOW.tags)}")
    
    # 列出节点
    print(f"\n🔷 节点列表:")
    for node in TRADE_REVIEW_WORKFLOW.nodes:
        agent_info = f" (agent: {node.agent_id})" if node.agent_id else ""
        print(f"   - {node.id}: {node.label} [{node.type}]{agent_info}")
    
    client.close()
    print(f"\n✅ 初始化完成!")


def list_workflows():
    """列出所有工作流"""
    from pymongo import MongoClient
    
    mongo_uri = os.getenv(
        "MONGODB_CONNECTION_STRING",
        "mongodb://admin:tradingagents123@127.0.0.1:27017/tradingagents?authSource=admin"
    )
    db_name = os.getenv("MONGODB_DATABASE_NAME", "tradingagents")
    
    client = MongoClient(mongo_uri)
    db = client[db_name]
    
    print(f"\n📋 所有工作流:")
    workflows = db.workflows.find({}, {"id": 1, "name": 1, "version": 1, "is_system": 1})
    for wf in workflows:
        system_tag = " [系统]" if wf.get("is_system") else ""
        print(f"   - {wf['id']}: {wf.get('name', 'N/A')} v{wf.get('version', '?')}{system_tag}")
    
    client.close()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="初始化交易复盘工作流")
    parser.add_argument("--list", action="store_true", help="列出所有工作流")
    args = parser.parse_args()
    
    if args.list:
        list_workflows()
    else:
        init_trade_review_workflow()
        list_workflows()

