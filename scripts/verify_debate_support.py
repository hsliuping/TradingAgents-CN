"""
验证所有 v2.0 研究员提示词是否包含辩论支持
"""

from pymongo import MongoClient


def verify_debate_support():
    """验证辩论支持"""
    
    # 连接 MongoDB
    client = MongoClient(
        "mongodb://admin:tradingagents123@localhost:27017/",
        authSource="admin"
    )
    db = client["tradingagents"]
    collection = db["prompt_templates"]
    
    print("=" * 80)
    print("🔍 验证 v2.0 研究员提示词的辩论支持")
    print("=" * 80)
    
    # 查询所有 v2.0 研究员模板
    templates = list(collection.find(
        {"agent_type": "researchers_v2"},
        {
            "agent_name": 1,
            "template_name": 1,
            "preference_type": 1,
            "content.tool_guidance": 1,
            "content.analysis_requirements": 1
        }
    ).sort([("agent_name", 1), ("preference_type", 1)]))
    
    print(f"\n找到 {len(templates)} 个模板\n")
    
    all_good = True
    
    for template in templates:
        agent_name = template.get("agent_name")
        preference_type = template.get("preference_type")
        template_name = template.get("template_name")
        content = template.get("content", {})
        
        tool_guidance = content.get("tool_guidance", "")
        analysis_requirements = content.get("analysis_requirements", "")
        
        print(f"📋 {template_name}")
        print(f"   Agent: {agent_name}, 偏好: {preference_type}")
        
        # 检查 tool_guidance 是否包含辩论上下文
        has_debate_context = (
            "history" in tool_guidance or 
            "current_response" in tool_guidance or
            "past_memory_str" in tool_guidance
        )
        
        # 检查 analysis_requirements 是否包含辩论要求
        has_debate_requirements = (
            "辩论" in analysis_requirements or
            "参与讨论" in analysis_requirements
        )
        
        if has_debate_context:
            print(f"   ✅ tool_guidance 包含辩论上下文")
        else:
            print(f"   ❌ tool_guidance 缺少辩论上下文")
            all_good = False
        
        if has_debate_requirements:
            print(f"   ✅ analysis_requirements 包含辩论要求")
        else:
            print(f"   ❌ analysis_requirements 缺少辩论要求")
            all_good = False
        
        print()
    
    print("=" * 80)
    if all_good:
        print("✅ 所有模板都包含辩论支持")
    else:
        print("⚠️ 部分模板缺少辩论支持")
    print("=" * 80)


if __name__ == "__main__":
    verify_debate_support()

