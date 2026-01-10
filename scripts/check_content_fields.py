"""查看 prompt_templates 的 content 字段结构"""
from pymongo import MongoClient

client = MongoClient('mongodb://admin:tradingagents123@127.0.0.1:27017/tradingagents?authSource=admin')
db = client['tradingagents']

# 查找一个 risk_manager 模板
template = db.prompt_templates.find_one({
    'agent_type': 'managers',
    'agent_name': 'risk_manager',
    'preference_type': 'neutral'
})

if template:
    print("找到模板:")
    print(f"  ID: {template.get('_id')}")
    print(f"  Agent: {template.get('agent_type')}/{template.get('agent_name')}")
    print(f"  Preference: {template.get('preference_type')}")
    print(f"  Updated: {template.get('updated_at')}")
    print()
    
    content = template.get('content', {})
    print("=" * 80)
    print("content 字段包含的键:")
    print("=" * 80)
    for key in content.keys():
        print(f"  - {key}")
    print()
    
    # 显示每个字段的前 200 字符
    print("=" * 80)
    print("各字段内容预览:")
    print("=" * 80)
    for key, value in content.items():
        print(f"\n📋 {key}:")
        print("-" * 80)
        if isinstance(value, str):
            print(value[:500])
            if 'final_trade_decision' in value:
                print("\n✅ 包含 'final_trade_decision'")
            else:
                print("\n❌ 不包含 'final_trade_decision'")
        else:
            print(f"  类型: {type(value)}")
            print(f"  值: {value}")
else:
    print("❌ 未找到模板")

client.close()

