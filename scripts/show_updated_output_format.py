"""显示更新后的 output_format 字段内容"""
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
    print("=" * 100)
    print("更新后的 output_format 字段内容")
    print("=" * 100)
    print()
    
    content = template.get('content', {})
    output_format = content.get('output_format', '')
    
    print(output_format)
    print()
    print("=" * 100)
    
    if 'final_trade_decision' in output_format:
        print("✅ 包含 final_trade_decision 字段说明")
        
        # 统计 final_trade_decision 相关的行数
        lines = output_format.split('\n')
        ftd_lines = [line for line in lines if 'final_trade_decision' in line.lower()]
        print(f"✅ 共有 {len(ftd_lines)} 行提到 final_trade_decision")
    else:
        print("❌ 不包含 final_trade_decision 字段说明")
else:
    print("❌ 未找到模板")

client.close()

