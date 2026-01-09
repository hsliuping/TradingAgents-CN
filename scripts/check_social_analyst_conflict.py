"""
检查社交分析师的命名冲突

问题：
1. prompt_templates 中有两个社交分析师：
   - social_analyst_v2
   - social_media_analyst_v2
2. agent_configs 中只有 social_analyst_v2

使用方法：
    python scripts/check_social_analyst_conflict.py
"""

import asyncio
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.core.database import init_database, get_mongo_db


async def main():
    print("=" * 80)
    print("检查社交分析师的命名冲突")
    print("=" * 80)
    
    # 初始化数据库
    print("\n📡 连接数据库...")
    await init_database()
    db = get_mongo_db()
    print("✅ 数据库连接成功")
    
    # 1. 检查 prompt_templates 集合
    print("\n" + "=" * 80)
    print("1. prompt_templates 集合中的社交分析师")
    print("=" * 80)
    
    social_templates = await db.prompt_templates.find({
        "$or": [
            {"agent_name": {"$regex": "social", "$options": "i"}},
            {"agent_type": {"$regex": "social", "$options": "i"}}
        ]
    }).to_list(length=None)
    
    if social_templates:
        for template in social_templates:
            print(f"\n📝 模板 ID: {template['_id']}")
            print(f"   agent_type: {template.get('agent_type', 'N/A')}")
            print(f"   agent_name: {template.get('agent_name', 'N/A')}")
            print(f"   agent_id: {template.get('agent_id', 'N/A')}")
            print(f"   template_name: {template.get('template_name', 'N/A')}")
            print(f"   preference_type: {template.get('preference_type', 'N/A')}")
            print(f"   is_system: {template.get('is_system', 'N/A')}")
            print(f"   status: {template.get('status', 'N/A')}")
    else:
        print("   ℹ️  未找到社交分析师相关的提示词模板")
    
    # 2. 检查 agent_configs 集合
    print("\n" + "=" * 80)
    print("2. agent_configs 集合中的社交分析师")
    print("=" * 80)
    
    social_agents = await db.agent_configs.find({
        "agent_id": {"$regex": "social", "$options": "i"}
    }).to_list(length=None)
    
    if social_agents:
        for agent in social_agents:
            print(f"\n🤖 Agent ID: {agent['agent_id']}")
            print(f"   name: {agent.get('name', 'N/A')}")
            print(f"   description: {agent.get('description', 'N/A')[:100]}...")
            print(f"   category: {agent.get('category', 'N/A')}")
            print(f"   prompt_template_type: {agent.get('prompt_template_type', 'N/A')}")
            print(f"   prompt_template_name: {agent.get('prompt_template_name', 'N/A')}")
    else:
        print("   ℹ️  未找到社交分析师相关的 Agent 配置")
    
    # 3. 检查工具绑定
    print("\n" + "=" * 80)
    print("3. 社交分析师的工具绑定")
    print("=" * 80)
    
    social_bindings = await db.tool_agent_bindings.find({
        "agent_id": {"$regex": "social", "$options": "i"}
    }).to_list(length=None)
    
    if social_bindings:
        bindings_by_agent = {}
        for binding in social_bindings:
            agent_id = binding['agent_id']
            if agent_id not in bindings_by_agent:
                bindings_by_agent[agent_id] = []
            bindings_by_agent[agent_id].append(binding['tool_id'])
        
        for agent_id, tools in bindings_by_agent.items():
            print(f"\n🤖 {agent_id}:")
            for tool in tools:
                print(f"   - {tool}")
    else:
        print("   ℹ️  未找到社交分析师相关的工具绑定")
    
    # 4. 分析冲突
    print("\n" + "=" * 80)
    print("4. 冲突分析")
    print("=" * 80)
    
    template_agent_names = set()
    template_agent_ids = set()
    
    for template in social_templates:
        agent_name = template.get('agent_name')
        agent_id = template.get('agent_id')
        if agent_name:
            template_agent_names.add(agent_name)
        if agent_id:
            template_agent_ids.add(agent_id)
    
    config_agent_ids = {agent['agent_id'] for agent in social_agents}
    
    print(f"\n📊 统计:")
    print(f"   prompt_templates 中的 agent_name: {template_agent_names}")
    print(f"   prompt_templates 中的 agent_id: {template_agent_ids}")
    print(f"   agent_configs 中的 agent_id: {config_agent_ids}")
    
    # 检查不一致
    print(f"\n🔍 不一致检查:")
    
    # agent_name 和 agent_id 不一致
    if template_agent_names != template_agent_ids:
        print(f"   ⚠️  prompt_templates 中 agent_name 和 agent_id 不一致")
        print(f"      agent_name: {template_agent_names}")
        print(f"      agent_id: {template_agent_ids}")
    
    # prompt_templates 和 agent_configs 不一致
    if template_agent_ids != config_agent_ids:
        print(f"   ⚠️  prompt_templates 和 agent_configs 中的 agent_id 不一致")
        print(f"      仅在 prompt_templates: {template_agent_ids - config_agent_ids}")
        print(f"      仅在 agent_configs: {config_agent_ids - template_agent_ids}")
    
    # 5. 修复建议
    print("\n" + "=" * 80)
    print("5. 修复建议")
    print("=" * 80)
    
    if len(template_agent_names) > 1:
        print("\n⚠️  发现重复的社交分析师模板")
        print("\n建议 1: 统一命名")
        print("   - 保留 social_analyst_v2")
        print("   - 删除或重命名 social_media_analyst_v2")
        
        print("\n建议 2: 更新 prompt_templates 中的 agent_id")
        for template in social_templates:
            if template.get('agent_name') == 'social_media_analyst_v2':
                print(f"""
db.prompt_templates.updateOne(
    {{ "_id": ObjectId("{template['_id']}") }},
    {{ "$set": {{ "agent_id": "social_analyst_v2" }} }}
)
""")
        
        print("\n建议 3: 或者删除重复的模板")
        for template in social_templates:
            if template.get('agent_name') == 'social_media_analyst_v2':
                print(f"""
db.prompt_templates.deleteOne(
    {{ "_id": ObjectId("{template['_id']}") }}
)
""")


if __name__ == "__main__":
    asyncio.run(main())

