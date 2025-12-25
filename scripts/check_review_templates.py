"""检查复盘分析师的提示词模板"""
from pymongo import MongoClient

# 连接MongoDB
client = MongoClient('mongodb://admin:tradingagents123@127.0.0.1:27017/tradingagents?authSource=admin')
db = client['tradingagents']

# 查询 reviewers_v2 类型的模板
print("=" * 80)
print("检查 reviewers_v2 类型的提示词模板")
print("=" * 80)

agent_names = ['timing_analyst_v2', 'position_analyst_v2', 'emotion_analyst_v2', 'attribution_analyst_v2', 'review_manager_v2']

for agent_name in agent_names:
    print(f"\n{'=' * 80}")
    print(f"Agent: {agent_name}")
    print(f"{'=' * 80}")
    
    templates = list(db.prompt_templates.find({
        'agent_type': 'reviewers_v2',
        'agent_name': agent_name
    }))
    
    print(f"找到模板数量: {len(templates)}")
    
    for t in templates:
        print(f"\n模板ID: {t.get('_id')}")
        print(f"模板名称: {t.get('template_name', '❌ 缺失')}")
        print(f"来源: {t.get('source', 'N/A')}")
        print(f"版本: {t.get('version', '❌ 缺失')}")
        print(f"偏好: {t.get('preference_id', 'N/A')}")
        print(f"状态: {t.get('status', 'N/A')}")
        print(f"系统模板: {t.get('is_system', 'N/A')}")
        
        content = t.get('content', {})
        if isinstance(content, dict):
            print(f"\n内容字段:")
            for key in content.keys():
                value = content[key]
                if isinstance(value, str):
                    print(f"  - {key}: {len(value)}字符")
                    # 检查是否包含交易计划相关的占位符
                    if 'trading_plan' in value.lower() or '交易计划' in value:
                        print(f"    ✅ 包含交易计划相关内容")
                    else:
                        print(f"    ❌ 不包含交易计划相关内容")
                    
                    # 显示前200字符
                    print(f"    前200字符: {value[:200]}")
        else:
            print(f"内容类型: {type(content)}")

print("\n" + "=" * 80)
print("检查完成")
print("=" * 80)

