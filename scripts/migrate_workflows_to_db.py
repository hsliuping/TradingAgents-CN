#!/usr/bin/env python
"""
工作流迁移脚本

将 data/workflows/ 目录中的工作流文件迁移到 MongoDB 数据库
"""

import json
import logging
import os
import sys
from pathlib import Path
from datetime import datetime

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from pymongo import MongoClient

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def migrate_workflows():
    """迁移工作流文件到数据库"""
    
    # 连接数据库
    mongo_uri = os.getenv(
        "MONGODB_CONNECTION_STRING",
        "mongodb://admin:tradingagents123@127.0.0.1:27017/tradingagents?authSource=admin"
    )
    db_name = os.getenv("MONGODB_DATABASE_NAME", "tradingagents")
    
    try:
        client = MongoClient(mongo_uri)
        db = client[db_name]
        workflows_collection = db.workflows
        logger.info(f"✅ 数据库连接成功: {db_name}")
    except Exception as e:
        logger.error(f"❌ 数据库连接失败: {e}")
        return
    
    # 扫描工作流目录
    workflows_dir = Path("data/workflows")
    if not workflows_dir.exists():
        logger.warning(f"⚠️ 工作流目录不存在: {workflows_dir}")
        return
    
    migrated = 0
    skipped = 0
    failed = 0
    
    for file_path in workflows_dir.glob("*.json"):
        workflow_id = file_path.stem
        
        try:
            # 读取文件
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # 检查是否已存在
            existing = workflows_collection.find_one({"id": workflow_id})
            if existing:
                logger.info(f"⏭️ 跳过已存在的工作流: {workflow_id} - {data.get('name', 'N/A')}")
                skipped += 1
                continue
            
            # 补充必要字段
            data.setdefault("version", 1)
            data.setdefault("is_system", False)
            data.setdefault("created_at", datetime.now().isoformat())
            data.setdefault("updated_at", datetime.now().isoformat())
            
            # 插入到数据库
            workflows_collection.insert_one(data)
            logger.info(f"✅ 迁移成功: {workflow_id} - {data.get('name', 'N/A')}")
            migrated += 1
            
        except Exception as e:
            logger.error(f"❌ 迁移失败 {workflow_id}: {e}")
            failed += 1
    
    logger.info(f"\n📊 迁移统计:")
    logger.info(f"   ✅ 成功: {migrated}")
    logger.info(f"   ⏭️ 跳过: {skipped}")
    logger.info(f"   ❌ 失败: {failed}")


def verify_migration():
    """验证迁移结果"""
    
    mongo_uri = os.getenv(
        "MONGODB_CONNECTION_STRING",
        "mongodb://admin:tradingagents123@127.0.0.1:27017/tradingagents?authSource=admin"
    )
    db_name = os.getenv("MONGODB_DATABASE_NAME", "tradingagents")
    
    try:
        client = MongoClient(mongo_uri)
        db = client[db_name]
        workflows_collection = db.workflows
    except Exception as e:
        logger.error(f"❌ 数据库连接失败: {e}")
        return
    
    logger.info("\n📋 数据库中的工作流列表:")
    for doc in workflows_collection.find():
        workflow_id = doc.get("id", "N/A")
        name = doc.get("name", "N/A")
        version = doc.get("version", 1)
        
        # 统计分析师节点
        nodes = doc.get("nodes", [])
        analyst_nodes = [n for n in nodes if n.get("type") == "analyst"]
        analyst_ids = [n.get("agent_id") for n in analyst_nodes]
        
        logger.info(f"   - {workflow_id}")
        logger.info(f"     名称: {name}")
        logger.info(f"     版本: {version}")
        logger.info(f"     分析师: {analyst_ids}")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="工作流迁移工具")
    parser.add_argument("--verify", action="store_true", help="仅验证，不执行迁移")
    args = parser.parse_args()
    
    if args.verify:
        verify_migration()
    else:
        migrate_workflows()
        verify_migration()

