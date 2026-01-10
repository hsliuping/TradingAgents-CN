"""检查 risk_manager 模板的字段名和内容"""
from pymongo import MongoClient

client = MongoClient('mongodb://admin:tradingagents123@127.0.0.1:27017/tradingagents?authSource=admin')
db = client['tradingagents']

templates = list(db.prompt_templates.find({'agent_name': {'$regex': 'risk_manager'}}))

print(f"找到 {len(templates)} 个 risk_manager 模板:\n")

for t in templates:
    agent_type = t.get('agent_type', 'N/A')
    agent_name = t.get('agent_name', 'N/A')
    preference_type = t.get('preference_type', 'N/A')
    template_id = str(t.get('_id', 'N/A'))

    print(f"Agent: {agent_type}/{agent_name}")
    print(f"  ID: {template_id}")
    print(f"  preference_type: {preference_type}")

    # 检查 system_prompt 是否包含 final_trade_decision
    content = t.get('content', {})
    system_prompt = content.get('system_prompt', '')

    if 'final_trade_decision' in system_prompt:
        print(f"  ✅ 包含 final_trade_decision")
        # 显示包含 final_trade_decision 的部分
        lines = system_prompt.split('\n')
        for i, line in enumerate(lines):
            if 'final_trade_decision' in line.lower():
                print(f"     第 {i+1} 行: {line.strip()}")
    else:
        print(f"  ❌ 不包含 final_trade_decision")
        print(f"     system_prompt 长度: {len(system_prompt)} 字符")

    print()

client.close()

