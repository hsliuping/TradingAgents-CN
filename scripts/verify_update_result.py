"""验证更新结果 - 查看完整的 system_prompt"""
from pymongo import MongoClient

client = MongoClient('mongodb://admin:tradingagents123@127.0.0.1:27017/tradingagents?authSource=admin')
db = client['tradingagents']

# 查找一个 risk_manager_v2 模板
template = db.prompt_templates.find_one({
    'agent_type': 'managers_v2',
    'agent_name': 'risk_manager_v2',
    'preference_type': 'neutral'
})

if template:
    print("找到模板:")
    print(f"  Agent: {template.get('agent_type')}/{template.get('agent_name')}")
    print(f"  Preference: {template.get('preference_type')}")
    print(f"  ID: {template.get('_id')}")
    print()
    
    content = template.get('content', {})
    system_prompt = content.get('system_prompt', '')
    
    print("=" * 80)
    print("完整的 system_prompt:")
    print("=" * 80)
    print(system_prompt)
    print("=" * 80)
    print()
    
    if 'final_trade_decision' in system_prompt:
        print("✅ 包含 final_trade_decision")
    else:
        print("❌ 不包含 final_trade_decision")
        print(f"system_prompt 长度: {len(system_prompt)} 字符")
else:
    print("❌ 未找到模板")

client.close()

