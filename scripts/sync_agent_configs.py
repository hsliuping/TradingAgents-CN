"""
同步代码中的 Agent metadata 到数据库 agent_configs 集合
"""
import sys
import os
import asyncio
from datetime import datetime

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

async def main():
    from app.core.database import init_database, get_mongo_db
    from core.agents import get_registry
    
    # 初始化数据库
    await init_database()
    db = get_mongo_db()
    
    # 获取注册表
    registry = get_registry()
    
    print("=" * 80)
    print("同步 Agent 配置到数据库")
    print("=" * 80)
    
    # 获取所有已注册的 Agent
    all_agents = registry.list_all()
    print(f"\n📦 找到 {len(all_agents)} 个已注册的 Agent\n")
    
    for metadata in all_agents:
        agent_id = metadata.id
        
        # 检查数据库中是否已存在
        existing = await db.agent_configs.find_one({"agent_id": agent_id})
        
        if existing:
            print(f"⏭️  {agent_id:30s} - 已存在，跳过")
            continue
        
        # 构建配置文档
        config_doc = {
            "agent_id": agent_id,
            "name": metadata.name,
            "description": metadata.description,
            "category": metadata.category.value if hasattr(metadata.category, 'value') else str(metadata.category),
            "version": metadata.version,
            "enabled": True,
            "config": {
                "max_iterations": 3,
                "timeout": 120,
                "temperature": 0.7,
            },
            "prompt_template_type": metadata.category.value if hasattr(metadata.category, 'value') else "general",
            "prompt_template_name": agent_id,
            "icon": metadata.icon if hasattr(metadata, 'icon') else "🤖",
            "color": metadata.color if hasattr(metadata, 'color') else "#409EFF",
            "tags": metadata.tags if hasattr(metadata, 'tags') else [],
            "license_tier": metadata.license_tier.value if hasattr(metadata.license_tier, 'value') else "free",
            "requires_tools": metadata.requires_tools if hasattr(metadata, 'requires_tools') else False,
            "output_field": metadata.output_field if hasattr(metadata, 'output_field') else "",
            "report_label": metadata.report_label if hasattr(metadata, 'report_label') else "",
            "execution_order": metadata.execution_order if hasattr(metadata, 'execution_order') else 0,
            "max_tool_calls": metadata.max_tool_calls if hasattr(metadata, 'max_tool_calls') else 3,
            "inputs": [inp.model_dump() if hasattr(inp, 'model_dump') else inp for inp in metadata.inputs] if hasattr(metadata, 'inputs') else [],
            "outputs": [out.model_dump() if hasattr(out, 'model_dump') else out for out in metadata.outputs] if hasattr(metadata, 'outputs') else [],
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
        }
        
        # 插入数据库
        await db.agent_configs.insert_one(config_doc)
        print(f"✅ {agent_id:30s} - 已添加")
    
    print("\n✅ 同步完成！")

if __name__ == "__main__":
    asyncio.run(main())

