"""
迁移到 v2.1：添加工作流上下文字段

功能：
1. 为 tool_agent_bindings 添加 workflow_id 和 node_id 字段
2. 为 prompt_templates 添加 agent_id 字段
3. 为 user_template_configs 添加 workflow_id、node_id 和 agent_id 字段
4. 创建新索引

向后兼容：
- workflow_id = null 表示全局配置
- node_id = null 表示工作流级别配置
- 现有数据自动视为全局配置

使用方法：
    python scripts/migration/migrate_to_v2.1.py
"""

import asyncio
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from app.core.database import init_database, get_mongo_db
from motor.motor_asyncio import AsyncIOMotorDatabase


async def migrate_tool_agent_bindings(db: AsyncIOMotorDatabase):
    """
    迁移 tool_agent_bindings 集合
    
    添加字段：
    - workflow_id: 工作流 ID（null 表示全局）
    - node_id: 节点 ID（null 表示工作流级别）
    """
    print("\n" + "=" * 80)
    print("1. 迁移 tool_agent_bindings 集合")
    print("=" * 80)
    
    # 统计现有数据
    total_count = await db.tool_agent_bindings.count_documents({})
    print(f"   📊 现有记录数: {total_count}")
    
    # 添加新字段（默认为 null，表示全局配置）
    result = await db.tool_agent_bindings.update_many(
        {"workflow_id": {"$exists": False}},
        {"$set": {"workflow_id": None, "node_id": None}}
    )
    
    print(f"   ✅ 更新 {result.modified_count} 条记录")
    print(f"   ℹ️  workflow_id = null 表示全局配置")
    print(f"   ℹ️  node_id = null 表示工作流级别配置")


async def migrate_prompt_templates(db: AsyncIOMotorDatabase):
    """
    迁移 prompt_templates 集合
    
    添加字段：
    - agent_id: Agent ID（从 agent_name 推断）
    """
    print("\n" + "=" * 80)
    print("2. 迁移 prompt_templates 集合")
    print("=" * 80)
    
    # 统计现有数据
    total_count = await db.prompt_templates.count_documents({})
    print(f"   📊 现有记录数: {total_count}")
    
    # 查找需要迁移的记录
    templates = await db.prompt_templates.find(
        {"agent_id": {"$exists": False}}
    ).to_list(length=None)
    
    print(f"   📊 需要迁移的记录数: {len(templates)}")
    
    # agent_name 到 agent_id 的映射规则
    name_to_id_mapping = {
        # v2.0 Analysts
        "market_analyst": "market_analyst_v2",
        "sector_analyst": "sector_analyst_v2",
        "fundamental_analyst": "fundamental_analyst_v2",
        "technical_analyst": "technical_analyst_v2",
        
        # v2.0 Strategists
        "strategy_analyst": "strategy_analyst_v2",
        "risk_analyst": "risk_analyst_v2",
        
        # v2.0 Reporters
        "report_writer": "report_writer_v2",
        
        # v1.x (保持不变)
        "market_analyst_v1": "market_analyst_v1",
        "sector_analyst_v1": "sector_analyst_v1",
    }
    
    # 更新每条记录
    updated_count = 0
    for template in templates:
        agent_name = template.get("agent_name", "")
        agent_type = template.get("agent_type", "")
        
        # 推断 agent_id
        if agent_name in name_to_id_mapping:
            agent_id = name_to_id_mapping[agent_name]
        elif agent_type == "analysts":
            agent_id = f"{agent_name}_v2"
        elif agent_type == "strategists":
            agent_id = f"{agent_name}_v2"
        elif agent_type == "reporters":
            agent_id = f"{agent_name}_v2"
        else:
            agent_id = agent_name  # 默认使用 agent_name
        
        # 更新记录
        await db.prompt_templates.update_one(
            {"_id": template["_id"]},
            {"$set": {"agent_id": agent_id}}
        )
        
        updated_count += 1
        print(f"   ✅ {agent_name} -> {agent_id}")
    
    print(f"   ✅ 更新 {updated_count} 条记录")


async def migrate_user_template_configs(db: AsyncIOMotorDatabase):
    """
    迁移 user_template_configs 集合
    
    添加字段：
    - workflow_id: 工作流 ID（null 表示全局）
    - node_id: 节点 ID（null 表示工作流级别）
    - agent_id: Agent ID（从 agent_name 推断）
    """
    print("\n" + "=" * 80)
    print("3. 迁移 user_template_configs 集合")
    print("=" * 80)
    
    # 统计现有数据
    total_count = await db.user_template_configs.count_documents({})
    print(f"   📊 现有记录数: {total_count}")
    
    # 添加 workflow_id 和 node_id 字段
    result = await db.user_template_configs.update_many(
        {"workflow_id": {"$exists": False}},
        {"$set": {"workflow_id": None, "node_id": None}}
    )
    
    print(f"   ✅ 添加 workflow_id 和 node_id: {result.modified_count} 条记录")
    
    # 添加 agent_id 字段（从 agent_name 推断）
    configs = await db.user_template_configs.find(
        {"agent_id": {"$exists": False}}
    ).to_list(length=None)
    
    # 使用与 prompt_templates 相同的映射规则
    name_to_id_mapping = {
        "market_analyst": "market_analyst_v2",
        "sector_analyst": "sector_analyst_v2",
        "fundamental_analyst": "fundamental_analyst_v2",
        "technical_analyst": "technical_analyst_v2",
        "strategy_analyst": "strategy_analyst_v2",
        "risk_analyst": "risk_analyst_v2",
        "report_writer": "report_writer_v2",
    }
    
    updated_count = 0
    for config in configs:
        agent_name = config.get("agent_name", "")
        agent_type = config.get("agent_type", "")
        
        # 推断 agent_id
        if agent_name in name_to_id_mapping:
            agent_id = name_to_id_mapping[agent_name]
        elif agent_type == "analysts":
            agent_id = f"{agent_name}_v2"
        else:
            agent_id = agent_name
        
        await db.user_template_configs.update_one(
            {"_id": config["_id"]},
            {"$set": {"agent_id": agent_id}}
        )
        
        updated_count += 1
    
    print(f"   ✅ 添加 agent_id: {updated_count} 条记录")


async def create_indexes(db: AsyncIOMotorDatabase):
    """创建新索引"""
    print("\n" + "=" * 80)
    print("4. 创建新索引")
    print("=" * 80)
    
    # tool_agent_bindings 索引
    await db.tool_agent_bindings.create_index([
        ("workflow_id", 1),
        ("node_id", 1),
        ("agent_id", 1),
        ("is_active", 1)
    ], name="idx_workflow_node_agent_active")
    print("   ✅ tool_agent_bindings: idx_workflow_node_agent_active")
    
    # prompt_templates 索引
    await db.prompt_templates.create_index([
        ("agent_id", 1),
        ("template_name", 1),
        ("status", 1)
    ], name="idx_agent_template_status")
    print("   ✅ prompt_templates: idx_agent_template_status")
    
    # user_template_configs 索引
    await db.user_template_configs.create_index([
        ("user_id", 1),
        ("workflow_id", 1),
        ("node_id", 1),
        ("agent_id", 1),
        ("is_active", 1)
    ], name="idx_user_workflow_node_agent_active")
    print("   ✅ user_template_configs: idx_user_workflow_node_agent_active")


async def verify_migration(db: AsyncIOMotorDatabase):
    """验证迁移结果"""
    print("\n" + "=" * 80)
    print("5. 验证迁移结果")
    print("=" * 80)
    
    # 验证 tool_agent_bindings
    count = await db.tool_agent_bindings.count_documents({"workflow_id": {"$exists": True}})
    total = await db.tool_agent_bindings.count_documents({})
    print(f"   ✅ tool_agent_bindings: {count}/{total} 条记录包含 workflow_id")
    
    # 验证 prompt_templates
    count = await db.prompt_templates.count_documents({"agent_id": {"$exists": True}})
    total = await db.prompt_templates.count_documents({})
    print(f"   ✅ prompt_templates: {count}/{total} 条记录包含 agent_id")
    
    # 验证 user_template_configs
    count = await db.user_template_configs.count_documents({"workflow_id": {"$exists": True}})
    total = await db.user_template_configs.count_documents({})
    print(f"   ✅ user_template_configs: {count}/{total} 条记录包含 workflow_id")


async def main():
    """主函数"""
    print("=" * 80)
    print("迁移到 v2.1：添加工作流上下文字段")
    print("=" * 80)
    
    # 初始化数据库连接
    print("\n📡 连接数据库...")
    await init_database()
    db = get_mongo_db()
    print("✅ 数据库连接成功")
    
    try:
        # 执行迁移
        await migrate_tool_agent_bindings(db)
        await migrate_prompt_templates(db)
        await migrate_user_template_configs(db)
        await create_indexes(db)
        await verify_migration(db)
        
        print("\n" + "=" * 80)
        print("✅ 迁移完成！")
        print("=" * 80)
        
    except Exception as e:
        print(f"\n❌ 迁移失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())

