"""
检查风险辩论相关的提示词模板
"""

from pymongo import MongoClient
import json


def check_risk_templates():
    """检查风险辩论模板"""
    
    # 连接 MongoDB
    client = MongoClient(
        "mongodb://admin:tradingagents123@localhost:27017/",
        authSource="admin"
    )
    db = client["tradingagents"]
    collection = db["prompt_templates"]
    
    print("=" * 80)
    print("🔍 检查风险辩论相关的提示词模板")
    print("=" * 80)
    
    # 查询旧版的风险辩论模板
    print("\n📖 旧版模板 (v1.x):")
    print("-" * 80)
    
    old_templates = list(collection.find({
        "agent_type": {"$in": ["debators", "managers"]},
        "agent_name": {"$in": ["aggressive_debator", "conservative_debator", "neutral_debator", "risk_manager"]}
    }))
    
    for template in old_templates:
        print(f"\n📋 {template.get('template_name')}")
        print(f"   agent_type: {template.get('agent_type')}")
        print(f"   agent_name: {template.get('agent_name')}")
        print(f"   preference_id: {template.get('preference_id')}")
        
        content = template.get("content", {})
        print(f"   字段: {list(content.keys())}")
    
    # 查询新版的风险辩论模板
    print("\n" + "=" * 80)
    print("📖 新版模板 (v2.0):")
    print("-" * 80)
    
    new_templates = list(collection.find({
        "agent_type": {"$in": ["debators_v2", "managers_v2", "risk_analysts_v2"]},
    }))
    
    if new_templates:
        for template in new_templates:
            print(f"\n📋 {template.get('template_name')}")
            print(f"   agent_type: {template.get('agent_type')}")
            print(f"   agent_name: {template.get('agent_name')}")
            print(f"   preference_type: {template.get('preference_type')}")
            
            content = template.get("content", {})
            print(f"   字段: {list(content.keys())}")
    else:
        print("\n⚠️ 未找到新版模板")
    
    # 保存旧版模板内容
    print("\n" + "=" * 80)
    print("💾 保存旧版模板内容...")
    print("=" * 80)
    
    old_prompts = {}
    for template in old_templates:
        agent_name = template.get("agent_name")
        preference_id = template.get("preference_id", "neutral")
        content = template.get("content", {})
        
        if agent_name not in old_prompts:
            old_prompts[agent_name] = {}
        
        old_prompts[agent_name][preference_id] = {
            "system_prompt": content.get("system_prompt", ""),
            "tool_guidance": content.get("tool_guidance", ""),
            "analysis_requirements": content.get("analysis_requirements", ""),
            "output_format": content.get("output_format", ""),
            "constraints": content.get("constraints", "")
        }
    
    with open("old_risk_prompts.json", "w", encoding="utf-8") as f:
        json.dump(old_prompts, f, ensure_ascii=False, indent=2)
    
    print("✅ 已保存到 old_risk_prompts.json")


if __name__ == "__main__":
    check_risk_templates()

