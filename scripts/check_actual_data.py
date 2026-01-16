"""
检查数据库中实际的提示词数据
"""

from pymongo import MongoClient
import json


def check_data():
    """检查实际数据"""
    
    # 连接 MongoDB
    client = MongoClient(
        "mongodb://admin:tradingagents123@localhost:27017/",
        authSource="admin"
    )
    db = client["tradingagents"]
    collection = db["prompt_templates"]
    
    print("=" * 80)
    print("🔍 检查实际数据")
    print("=" * 80)
    
    # 查询一个中性型模板
    template = collection.find_one({
        "agent_type": "researchers_v2",
        "agent_name": "bear_researcher_v2",
        "preference_type": "neutral"
    })
    
    if not template:
        print("❌ 未找到模板")
        return
    
    print(f"\n📋 模板: {template.get('template_name')}")
    print(f"   ID: {template.get('_id')}")
    
    content = template.get("content", {})

    print("\n📝 system_prompt:")
    print("-" * 80)
    print(content.get("system_prompt", ""))
    print("-" * 80)

    print("\n📝 user_prompt:")
    print("-" * 80)
    print(content.get("user_prompt", ""))
    print("-" * 80)

    print("\n📝 tool_guidance:")
    print("-" * 80)
    print(content.get("tool_guidance", ""))
    print("-" * 80)

    print("\n📝 analysis_requirements:")
    print("-" * 80)
    print(content.get("analysis_requirements", ""))
    print("-" * 80)

    print("\n📝 output_format:")
    print("-" * 80)
    print(content.get("output_format", ""))
    print("-" * 80)

    print("\n📝 constraints:")
    print("-" * 80)
    print(content.get("constraints", ""))
    print("-" * 80)
    
    # 检查是否包含辩论相关内容
    tool_guidance = content.get("tool_guidance", "")
    analysis_requirements = content.get("analysis_requirements", "")
    
    print("\n🔍 检查结果:")
    print(f"  - tool_guidance 包含 'history': {'history' in tool_guidance}")
    print(f"  - tool_guidance 包含 'current_response': {'current_response' in tool_guidance}")
    print(f"  - tool_guidance 包含 'past_memory_str': {'past_memory_str' in tool_guidance}")
    print(f"  - analysis_requirements 包含 '辩论': {'辩论' in analysis_requirements}")
    print(f"  - analysis_requirements 包含 '参与讨论': {'参与讨论' in analysis_requirements}")


if __name__ == "__main__":
    check_data()

