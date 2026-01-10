"""
检查投资组合经理和交易员的模板配置
"""
import sys
sys.path.insert(0, '.')

from app.core.database import get_mongo_db_sync

db = get_mongo_db_sync()
templates_collection = db.prompt_templates

print("=" * 80)
print("检查 managers 和 trader 的模板")
print("=" * 80)

# 查询所有 managers 类型的模板
managers_templates = list(templates_collection.find({
    'agent_type': 'managers'
}))

print(f"\n找到 {len(managers_templates)} 个 managers 模板:")
for t in managers_templates:
    agent_name = t.get('agent_name', 'N/A')
    preference = t.get('preference', 'N/A')
    system_prompt = t.get('content', {}).get('system_prompt', '')
    print(f"\n  - agent_name: {agent_name}")
    print(f"    preference: {preference}")
    print(f"    system_prompt 前100字: {system_prompt[:100]}...")

# 查询所有 trader 类型的模板
trader_templates = list(templates_collection.find({
    'agent_type': 'trader'
}))

print(f"\n\n找到 {len(trader_templates)} 个 trader 模板:")
for t in trader_templates:
    agent_name = t.get('agent_name', 'N/A')
    preference = t.get('preference', 'N/A')
    system_prompt = t.get('content', {}).get('system_prompt', '')
    print(f"\n  - agent_name: {agent_name}")
    print(f"    preference: {preference}")
    print(f"    system_prompt 前100字: {system_prompt[:100]}...")

print("\n" + "=" * 80)

