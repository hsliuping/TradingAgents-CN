"""
验证最终的提示词内容
"""

from pymongo import MongoClient


def verify_prompts():
    """验证提示词"""
    
    # 连接 MongoDB
    client = MongoClient(
        "mongodb://admin:tradingagents123@localhost:27017/",
        authSource="admin"
    )
    db = client["tradingagents"]
    collection = db["prompt_templates"]
    
    print("=" * 80)
    print("🔍 验证最终提示词内容")
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
    
    content = template.get("content", {})
    
    print("\n" + "=" * 80)
    print("📝 user_prompt (应该来自旧版 tool_guidance):")
    print("=" * 80)
    print(content.get("user_prompt", ""))
    
    print("\n" + "=" * 80)
    print("📝 tool_guidance (应该保持新版内容):")
    print("=" * 80)
    print(content.get("tool_guidance", ""))
    
    print("\n" + "=" * 80)
    print("🔍 检查结果:")
    print("=" * 80)
    
    user_prompt = content.get("user_prompt", "")
    tool_guidance = content.get("tool_guidance", "")
    
    # 检查 user_prompt 是否包含旧版的辩论变量
    has_old_vars = (
        "{market_research_report}" in user_prompt and
        "{history}" in user_prompt and
        "{current_response}" in user_prompt
    )
    
    # 检查 tool_guidance 是否是新版的简短内容
    is_new_guidance = (
        "基于已有的分析报告" in tool_guidance and
        len(tool_guidance) < 100
    )
    
    print(f"✅ user_prompt 包含旧版辩论变量: {has_old_vars}")
    print(f"✅ tool_guidance 保持新版简短内容: {is_new_guidance}")
    
    if has_old_vars and is_new_guidance:
        print("\n🎉 验证通过！提示词更新正确")
    else:
        print("\n⚠️ 验证失败！需要检查更新逻辑")


if __name__ == "__main__":
    verify_prompts()

