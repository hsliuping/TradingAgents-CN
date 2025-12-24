"""查看提示词模板的完整内容"""
from pymongo import MongoClient
import json

# 连接MongoDB
client = MongoClient('mongodb://admin:tradingagents123@127.0.0.1:27017/tradingagents?authSource=admin')
db = client['tradingagents']

print("=" * 80)
print("查看所有新创建的复盘分析模板")
print("=" * 80)

# 查询所有 reviewers_v2 模板
templates = db.prompt_templates.find({'agent_type': 'reviewers_v2'})

for template in templates:
    print(f"\n{'=' * 80}")
    print(f"{template.get('template_name', 'N/A')}")
    print(f"{'=' * 80}")
    print(f"模板ID: {template['_id']}")
    print(f"Agent名称: {template.get('agent_name', 'N/A')}")
    print(f"偏好: {template.get('preference_id', 'N/A')}")
    print(f"版本: {template.get('version', 'N/A')}")
    print(f"来源: {template.get('source', 'N/A')}")

    content = template.get('content', {})

    # 只显示 analysis_requirements（包含交易计划占位符）
    if 'analysis_requirements' in content:
        print(f"\n{'=' * 80}")
        print("ANALYSIS_REQUIREMENTS (包含交易计划占位符)")
        print(f"{'=' * 80}")
        print(content['analysis_requirements'])

    print("\n")

