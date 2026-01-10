"""
发布所有当前生效的模板

功能：
1. 查找所有 is_active=True 的用户模板配置
2. 获取这些配置关联的 template_id
3. 将这些模板的 status 更新为 'active'（如果当前是 'draft'）

用法：
    python scripts/maintenance/publish_active_templates.py
    python scripts/maintenance/publish_active_templates.py --dry-run  # 只查看，不修改
"""

import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from pymongo import MongoClient
from bson import ObjectId
from datetime import datetime
import os
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()


def publish_active_templates(dry_run: bool = False):
    """发布所有当前生效的模板"""

    # 连接数据库
    mongo_host = os.getenv("MONGODB_HOST", "127.0.0.1")
    mongo_port = int(os.getenv("MONGODB_PORT", "27017"))
    mongo_username = os.getenv("MONGODB_USERNAME", "admin")
    mongo_password = os.getenv("MONGODB_PASSWORD", "tradingagents123")
    mongo_auth_source = os.getenv("MONGODB_AUTH_SOURCE", "admin")
    db_name = os.getenv("MONGODB_DATABASE", "tradingagents")

    # 构建 MongoDB URI
    mongo_uri = f"mongodb://{mongo_username}:{mongo_password}@{mongo_host}:{mongo_port}/{db_name}?authSource={mongo_auth_source}"

    client = MongoClient(mongo_uri)
    db = client[db_name]

    print("=" * 80)
    print("🔍 发布所有当前生效的模板")
    print("=" * 80)
    print(f"数据库: {mongo_uri}/{db_name}")
    print(f"模式: {'只查看（不修改）' if dry_run else '修改模式'}")
    print("=" * 80)

    try:
        # 1. 查找所有 is_active=True 的配置
        configs_collection = db.user_template_configs
        templates_collection = db.prompt_templates

        active_configs = list(configs_collection.find({"is_active": True}))
        
        print(f"\n📊 找到 {len(active_configs)} 个当前生效的配置")
        
        if not active_configs:
            print("✅ 没有需要处理的配置")
            return
        
        # 2. 收集所有 template_id（去重）
        template_ids = set()
        for config in active_configs:
            template_id = config.get("template_id")
            if template_id:
                template_ids.add(template_id)
        
        print(f"📝 涉及 {len(template_ids)} 个唯一模板")
        
        # 3. 查找这些模板中状态为 draft 的
        draft_templates = list(templates_collection.find({
            "_id": {"$in": list(template_ids)},
            "status": "draft"
        }))
        
        print(f"\n🔍 找到 {len(draft_templates)} 个草稿状态的模板需要发布")
        
        if not draft_templates:
            print("✅ 所有当前生效的模板都已是已发布状态")
            return
        
        # 4. 显示详细信息
        print("\n" + "=" * 80)
        print("📋 需要发布的模板列表:")
        print("=" * 80)
        
        for i, template in enumerate(draft_templates, 1):
            template_id = template["_id"]
            template_name = template.get("template_name", "未命名")
            agent_type = template.get("agent_type", "未知")
            agent_name = template.get("agent_name", "未知")
            version = template.get("version", 1)
            
            # 查找使用这个模板的配置
            using_configs = [c for c in active_configs if c.get("template_id") == template_id]
            
            print(f"\n{i}. 模板ID: {template_id}")
            print(f"   名称: {template_name}")
            print(f"   Agent: {agent_type}/{agent_name}")
            print(f"   版本: {version}")
            print(f"   当前状态: draft")
            print(f"   被 {len(using_configs)} 个配置使用")
        
        # 5. 执行更新
        if not dry_run:
            print("\n" + "=" * 80)
            print("🚀 开始发布模板...")
            print("=" * 80)
            
            updated_count = 0
            for template in draft_templates:
                template_id = template["_id"]
                template_name = template.get("template_name", "未命名")
                
                result = templates_collection.update_one(
                    {"_id": template_id},
                    {
                        "$set": {
                            "status": "active",
                            "updated_at": datetime.utcnow()
                        }
                    }
                )
                
                if result.modified_count > 0:
                    updated_count += 1
                    print(f"✅ 已发布: {template_name} ({template_id})")
                else:
                    print(f"⚠️ 更新失败: {template_name} ({template_id})")
            
            print("\n" + "=" * 80)
            print(f"✅ 完成！共发布 {updated_count}/{len(draft_templates)} 个模板")
            print("=" * 80)
        else:
            print("\n" + "=" * 80)
            print("ℹ️ 只查看模式，未执行任何修改")
            print("   如需执行修改，请运行: python scripts/maintenance/publish_active_templates.py")
            print("=" * 80)
    
    finally:
        client.close()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="发布所有当前生效的模板")
    parser.add_argument("--dry-run", action="store_true", help="只查看，不修改")

    args = parser.parse_args()

    publish_active_templates(dry_run=args.dry_run)

