"""
对比旧版和新版的提示词模板

查询数据库中的 prompt_templates 集合，对比：
- 旧版：agent_type=researchers, agent_name=bull_researcher/bear_researcher
- 新版：agent_type=researchers_v2, agent_name=bull_researcher_v2/bear_researcher_v2
"""

import sys
import io
from pymongo import MongoClient
import json
from datetime import datetime

# 设置 UTF-8 输出
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')


def get_mongo_db_sync():
    """同步获取 MongoDB 数据库连接"""
    client = MongoClient("mongodb://localhost:27017/")
    return client["tradingagents"]


def compare_prompts():
    """对比提示词模板"""
    
    db = get_mongo_db_sync()
    collection = db["prompt_templates"]
    
    print("=" * 80)
    print("📊 提示词模板对比")
    print("=" * 80)
    
    # 查询旧版 Bull Researcher
    print("\n" + "=" * 80)
    print("🐂 旧版 Bull Researcher (researchers/bull_researcher)")
    print("=" * 80)
    
    old_bull = collection.find_one({
        "agent_type": "researchers",
        "agent_name": "bull_researcher",
        "is_system_default": True
    })
    
    if old_bull:
        print(f"\n📝 模板名称: {old_bull.get('template_name')}")
        print(f"📝 版本: {old_bull.get('version')}")
        print(f"📝 创建时间: {old_bull.get('created_at')}")
        print(f"\n【系统提示词】")
        print("-" * 80)
        print(old_bull.get('system_prompt', ''))
        print("\n【用户提示词】")
        print("-" * 80)
        print(old_bull.get('user_prompt', ''))
        print("\n【分析要求】")
        print("-" * 80)
        print(old_bull.get('analysis_requirements', ''))
        print("\n【输出格式】")
        print("-" * 80)
        print(old_bull.get('output_format', ''))
    else:
        print("❌ 未找到旧版 Bull Researcher 模板")
    
    # 查询新版 Bull Researcher
    print("\n" + "=" * 80)
    print("🐂 新版 Bull Researcher (researchers_v2/bull_researcher_v2)")
    print("=" * 80)
    
    new_bull = collection.find_one({
        "agent_type": "researchers_v2",
        "agent_name": "bull_researcher_v2",
        "is_system_default": True
    })
    
    if new_bull:
        print(f"\n📝 模板名称: {new_bull.get('template_name')}")
        print(f"📝 版本: {new_bull.get('version')}")
        print(f"📝 创建时间: {new_bull.get('created_at')}")
        print(f"\n【系统提示词】")
        print("-" * 80)
        print(new_bull.get('system_prompt', ''))
        print("\n【用户提示词】")
        print("-" * 80)
        print(new_bull.get('user_prompt', ''))
        print("\n【分析要求】")
        print("-" * 80)
        print(new_bull.get('analysis_requirements', ''))
        print("\n【输出格式】")
        print("-" * 80)
        print(new_bull.get('output_format', ''))
    else:
        print("❌ 未找到新版 Bull Researcher 模板")
    
    # 查询旧版 Bear Researcher
    print("\n" + "=" * 80)
    print("🐻 旧版 Bear Researcher (researchers/bear_researcher)")
    print("=" * 80)
    
    old_bear = collection.find_one({
        "agent_type": "researchers",
        "agent_name": "bear_researcher",
        "is_system_default": True
    })
    
    if old_bear:
        print(f"\n📝 模板名称: {old_bear.get('template_name')}")
        print(f"📝 版本: {old_bear.get('version')}")
        print(f"📝 创建时间: {old_bear.get('created_at')}")
        print(f"\n【系统提示词】")
        print("-" * 80)
        print(old_bear.get('system_prompt', ''))
        print("\n【用户提示词】")
        print("-" * 80)
        print(old_bear.get('user_prompt', ''))
        print("\n【分析要求】")
        print("-" * 80)
        print(old_bear.get('analysis_requirements', ''))
        print("\n【输出格式】")
        print("-" * 80)
        print(old_bear.get('output_format', ''))
    else:
        print("❌ 未找到旧版 Bear Researcher 模板")
    
    # 查询新版 Bear Researcher
    print("\n" + "=" * 80)
    print("🐻 新版 Bear Researcher (researchers_v2/bear_researcher_v2)")
    print("=" * 80)
    
    new_bear = collection.find_one({
        "agent_type": "researchers_v2",
        "agent_name": "bear_researcher_v2",
        "is_system_default": True
    })
    
    if new_bear:
        print(f"\n📝 模板名称: {new_bear.get('template_name')}")
        print(f"📝 版本: {new_bear.get('version')}")
        print(f"📝 创建时间: {new_bear.get('created_at')}")
        print(f"\n【系统提示词】")
        print("-" * 80)
        print(new_bear.get('system_prompt', ''))
        print("\n【用户提示词】")
        print("-" * 80)
        print(new_bear.get('user_prompt', ''))
        print("\n【分析要求】")
        print("-" * 80)
        print(new_bear.get('analysis_requirements', ''))
        print("\n【输出格式】")
        print("-" * 80)
        print(new_bear.get('output_format', ''))
    else:
        print("❌ 未找到新版 Bear Researcher 模板")
    
    print("\n" + "=" * 80)
    print("✅ 对比完成")
    print("=" * 80)

    # 保存到 JSON 文件
    output = {
        "old_bull": old_bull,
        "new_bull": new_bull,
        "old_bear": old_bear,
        "new_bear": new_bear,
    }

    # 移除 _id 字段（不能序列化）
    for key in output:
        if output[key] and '_id' in output[key]:
            output[key]['_id'] = str(output[key]['_id'])

    with open('prompt_comparison.json', 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print("\n📁 已保存到 prompt_comparison.json")


if __name__ == "__main__":
    compare_prompts()

