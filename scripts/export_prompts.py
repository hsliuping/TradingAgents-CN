"""
导出提示词模板到 JSON 文件

直接查询数据库，导出旧版和新版的提示词模板
"""

import sys
import os
import json

# 直接使用 pymongo
try:
    from pymongo import MongoClient
except ImportError:
    print("❌ 请先安装 pymongo: pip install pymongo")
    sys.exit(1)


def export_prompts():
    """导出提示词模板"""

    # 连接 MongoDB（使用认证）
    client = MongoClient(
        "mongodb://admin:tradingagents123@localhost:27017/",
        authSource="admin"
    )
    db = client["tradingagents"]
    collection = db["prompt_templates"]
    
    print("=" * 80)
    print("📊 导出提示词模板")
    print("=" * 80)

    # 先查询所有模板，看看有哪些
    print("\n🔍 查询所有提示词模板...")
    all_templates = list(collection.find({}, {"agent_type": 1, "agent_name": 1, "template_name": 1, "is_system_default": 1}))
    print(f"找到 {len(all_templates)} 个模板:")
    for t in all_templates[:20]:  # 只显示前 20 个
        print(f"  - {t.get('agent_type')}/{t.get('agent_name')} - {t.get('template_name')} (system_default={t.get('is_system_default')})")

    if len(all_templates) > 20:
        print(f"  ... 还有 {len(all_templates) - 20} 个模板")

    print("\n" + "=" * 80)

    # 查询所有相关模板（不限制 is_system_default，取第一个）
    templates = {
        "old_bull": collection.find_one({
            "agent_type": "researchers",
            "agent_name": "bull_researcher",
            "template_name": "System Neutral Template"
        }),
        "new_bull": collection.find_one({
            "agent_type": "researchers_v2",
            "agent_name": "bull_researcher_v2"
        }),
        "old_bear": collection.find_one({
            "agent_type": "researchers",
            "agent_name": "bear_researcher",
            "template_name": "System Neutral Template"
        }),
        "new_bear": collection.find_one({
            "agent_type": "researchers_v2",
            "agent_name": "bear_researcher_v2"
        }),
    }
    
    # 移除 _id 字段并转换 datetime
    from datetime import datetime as dt
    for key in templates:
        if templates[key]:
            if '_id' in templates[key]:
                templates[key]['_id'] = str(templates[key]['_id'])
            # 转换所有 datetime 对象为字符串
            for k, v in templates[key].items():
                if isinstance(v, dt):
                    templates[key][k] = v.isoformat()
    
    # 保存到 JSON 文件
    output_file = 'prompt_comparison.json'
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(templates, f, ensure_ascii=False, indent=2)
    
    print(f"\n✅ 已导出到 {output_file}")
    
    # 打印摘要
    for key, template in templates.items():
        if template:
            print(f"\n{key}:")
            print(f"  - 模板名称: {template.get('template_name')}")
            print(f"  - 版本: {template.get('version')}")
            print(f"  - 系统提示词长度: {len(template.get('system_prompt', ''))}")
            print(f"  - 用户提示词长度: {len(template.get('user_prompt', ''))}")
        else:
            print(f"\n{key}: ❌ 未找到")


if __name__ == "__main__":
    export_prompts()

