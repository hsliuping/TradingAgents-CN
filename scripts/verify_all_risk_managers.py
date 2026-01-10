"""验证所有 risk_manager 模板是否都包含 final_trade_decision"""
from pymongo import MongoClient

client = MongoClient('mongodb://admin:tradingagents123@127.0.0.1:27017/tradingagents?authSource=admin')
db = client['tradingagents']

templates = list(db.prompt_templates.find({'agent_name': {'$regex': 'risk_manager'}}))

print(f"找到 {len(templates)} 个 risk_manager 模板:\n")
print("=" * 100)

all_good = True

for t in templates:
    agent_type = t.get('agent_type', 'N/A')
    agent_name = t.get('agent_name', 'N/A')
    preference_type = t.get('preference_type', 'N/A')
    
    content = t.get('content', {})
    system_prompt = content.get('system_prompt', '')
    output_format = content.get('output_format', '')
    
    has_in_system = 'final_trade_decision' in system_prompt
    has_in_output = 'final_trade_decision' in output_format
    
    status = "✅" if (has_in_system and has_in_output) else "❌"
    
    print(f"{status} {agent_type}/{agent_name} (preference: {preference_type})")
    print(f"   system_prompt: {'✅' if has_in_system else '❌'}")
    print(f"   output_format: {'✅' if has_in_output else '❌'}")
    print()
    
    if not (has_in_system and has_in_output):
        all_good = False

print("=" * 100)
if all_good:
    print("🎉 所有模板都已正确更新！")
else:
    print("⚠️ 还有模板未正确更新")

client.close()

