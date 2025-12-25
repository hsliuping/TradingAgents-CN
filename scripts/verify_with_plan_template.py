# -*- coding: utf-8 -*-
from pymongo import MongoClient
from urllib.parse import quote_plus

username = quote_plus("admin")
password = quote_plus("tradingagents123")
client = MongoClient(f"mongodb://{username}:{password}@localhost:27017/")
db = client["tradingagents"]

# 查询 review_manager_v2 的两个模板
templates = list(db["prompt_templates"].find({
    "agent_type": "reviewers_v2",
    "agent_name": "review_manager_v2"
}).sort("preference_id", 1))

print(f"找到 {len(templates)} 个 review_manager_v2 模板:\n")
for i, t in enumerate(templates, 1):
    print(f"=== 模板 {i} ===")
    print(f"模板名称: {t.get('template_name', '[缺失]')}")
    print(f"Preference ID: {t.get('preference_id', 'N/A')}")
    print(f"版本: {t.get('version', '[缺失]')}")
    print(f"来源: {t.get('source', 'N/A')}")
    print(f"状态: {t.get('status', 'N/A')}")
    print(f"系统模板: {t.get('is_system', 'N/A')}")
    
    # 检查 user_prompt 是否包含交易计划
    user_prompt = t.get('content', {}).get('user_prompt', '')
    has_plan = 'trading_plan' in user_prompt
    print(f"包含交易计划: {'是' if has_plan else '否'}")
    print()

client.close()

