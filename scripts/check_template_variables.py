#!/usr/bin/env python3
"""检查模板中的变量"""

from pymongo import MongoClient
from urllib.parse import quote_plus
from bson import ObjectId
import re

# MongoDB 连接配置
username = quote_plus("admin")
password = quote_plus("tradingagents123")
MONGO_URI = f"mongodb://{username}:{password}@localhost:27017/"

def check_template_variables():
    """检查模板中的变量"""
    client = MongoClient(MONGO_URI)
    db = client["tradingagents"]
    collection = db["prompt_templates"]

    # 查找 with_plan 模板
    template = collection.find_one({
        "agent_type": "reviewers_v2",
        "agent_name": "review_manager_v2",
        "preference_type": "with_plan"
    })
    
    if not template:
        print("❌ 未找到 with_plan 模板")
        return
    
    print(f"✅ 找到模板: {template.get('template_name')}")
    print(f"   - preference_type: {template.get('preference_type')}")
    
    # 提取 user_prompt
    user_prompt = template.get('content', {}).get('user_prompt', '')
    
    print(f"\n📝 user_prompt 长度: {len(user_prompt)}")
    print(f"\n=== USER PROMPT ===")
    print(user_prompt)
    
    # 提取所有变量
    pattern = re.compile(r'\{\{([^}]+)\}\}|\{([^}]+)\}')
    matches = pattern.findall(user_prompt)
    
    variables = set()
    for m in matches:
        var_name = m[0] if m[0] else m[1]
        variables.add(var_name.strip())
    
    print(f"\n=== 需要的变量 ({len(variables)} 个) ===")
    for var in sorted(variables):
        print(f"  - {var}")
    
    # 模拟变量替换
    test_variables = {
        'code': '688111',
        'name': '金山办公',
        'pnl_sign': '+',
        'realized_pnl': '29900.00',
        'realized_pnl_pct': '12.59',
        'holding_days': '62',
        'timing_analysis': '时机分析内容...',
        'position_analysis': '仓位分析内容...',
        'emotion_analysis': '情绪分析内容...',
        'attribution_analysis': '归因分析内容...',
        'trading_plan': {
            'plan_name': '短线趋势追踪系统',
            'style': 'short_term',
            'rules_text': '规则文本...'
        }
    }
    
    def get_nested_value(data, path):
        """获取嵌套字典的值"""
        keys = path.split('.')
        value = data
        for key in keys:
            if isinstance(value, dict):
                value = value.get(key, '')
            else:
                return ''
        return value
    
    print(f"\n=== 测试变量替换 ===")
    for var in sorted(variables):
        value = get_nested_value(test_variables, var)
        if value:
            print(f"  ✅ {var} -> {str(value)[:50]}...")
        else:
            print(f"  ❌ {var} -> (未找到)")

if __name__ == "__main__":
    check_template_variables()

