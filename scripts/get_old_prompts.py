"""
获取旧版提示词的完整内容，用于更新代码中的降级提示词
"""

from pymongo import MongoClient
import json


def get_old_prompts():
    """获取旧版提示词"""
    
    # 连接 MongoDB
    client = MongoClient(
        "mongodb://admin:tradingagents123@localhost:27017/",
        authSource="admin"
    )
    db = client["tradingagents"]
    collection = db["prompt_templates"]
    
    print("=" * 80)
    print("📖 获取旧版提示词内容")
    print("=" * 80)
    
    # 读取旧版 Bull
    old_bull = collection.find_one({
        "agent_type": "researchers",
        "agent_name": "bull_researcher",
        "template_name": "System Neutral Template"
    })
    
    # 读取旧版 Bear
    old_bear = collection.find_one({
        "agent_type": "researchers",
        "agent_name": "bear_researcher",
        "template_name": "System Neutral Template"
    })
    
    if not old_bull or not old_bear:
        print("❌ 未找到旧版提示词")
        return
    
    bull_content = old_bull.get("content", {})
    bear_content = old_bear.get("content", {})
    
    print("\n" + "=" * 80)
    print("📝 Bull Researcher - system_prompt")
    print("=" * 80)
    print(bull_content.get("system_prompt", ""))
    
    print("\n" + "=" * 80)
    print("📝 Bull Researcher - tool_guidance (用作 user_prompt)")
    print("=" * 80)
    print(bull_content.get("tool_guidance", ""))
    
    print("\n" + "=" * 80)
    print("📝 Bear Researcher - system_prompt")
    print("=" * 80)
    print(bear_content.get("system_prompt", ""))
    
    print("\n" + "=" * 80)
    print("📝 Bear Researcher - tool_guidance (用作 user_prompt)")
    print("=" * 80)
    print(bear_content.get("tool_guidance", ""))
    
    # 保存到文件，方便复制
    output = {
        "bull": {
            "system_prompt": bull_content.get("system_prompt", ""),
            "user_prompt": bull_content.get("tool_guidance", ""),
        },
        "bear": {
            "system_prompt": bear_content.get("system_prompt", ""),
            "user_prompt": bear_content.get("tool_guidance", ""),
        }
    }
    
    with open("old_prompts_for_code.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    
    print("\n" + "=" * 80)
    print("✅ 已保存到 old_prompts_for_code.json")
    print("=" * 80)


if __name__ == "__main__":
    get_old_prompts()

