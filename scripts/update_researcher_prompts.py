"""
更新 v2.0 研究员提示词

从旧版（v1.x）读取提示词内容，完整更新到新版（v2.0）的所有提示词模板

更新规则：
1. system_prompt: 使用旧版的 system_prompt
2. user_prompt: 使用旧版的 tool_guidance（因为旧版没有 user_prompt）
3. tool_guidance: 保持新版不变（不更新，避免与 user_prompt 重复）
4. analysis_requirements: 使用旧版的 analysis_requirements
5. output_format: 使用旧版的 output_format
6. constraints: 使用旧版的 constraints
"""

import sys
from pymongo import MongoClient


def update_prompts():
    """更新提示词模板"""

    # 连接 MongoDB
    client = MongoClient(
        "mongodb://admin:tradingagents123@localhost:27017/",
        authSource="admin"
    )
    db = client["tradingagents"]
    collection = db["prompt_templates"]

    print("=" * 80)
    print("📝 更新 v2.0 研究员提示词 - 从旧版完整迁移")
    print("=" * 80)

    # 1. 读取旧版的提示词
    print("\n📖 读取旧版提示词...")

    old_bull = collection.find_one({
        "agent_type": "researchers",
        "agent_name": "bull_researcher",
        "template_name": "System Neutral Template"
    })

    old_bear = collection.find_one({
        "agent_type": "researchers",
        "agent_name": "bear_researcher",
        "template_name": "System Neutral Template"
    })

    if not old_bull or not old_bear:
        print("❌ 未找到旧版提示词模板")
        return

    print("✅ 成功读取旧版提示词")
    print(f"  - Bull: {old_bull.get('template_name')}")
    print(f"  - Bear: {old_bear.get('template_name')}")

    # 提取旧版的所有内容字段
    old_bull_content = old_bull.get("content", {})
    old_bear_content = old_bear.get("content", {})

    print("\n📋 旧版提示词包含的字段:")
    print(f"  Bull: {list(old_bull_content.keys())}")
    print(f"  Bear: {list(old_bear_content.keys())}")

    # 2. 查询所有新版的提示词
    print("\n🔍 查询所有新版提示词...")

    new_templates = list(collection.find({
        "agent_type": "researchers_v2"
    }))

    print(f"找到 {len(new_templates)} 个新版模板")

    # 3. 更新每个新版模板
    updated_count = 0

    for template in new_templates:
        agent_name = template.get("agent_name")
        preference_type = template.get("preference_type")
        template_name = template.get("template_name")

        print(f"\n📝 处理: {template_name}")
        print(f"   Agent: {agent_name}, 偏好: {preference_type}")

        # 确定使用哪个旧版模板作为参考
        if "bull" in agent_name:
            old_content = old_bull_content
        else:
            old_content = old_bear_content

        # 构建更新字段（用旧版内容替换，但保留新版的 tool_guidance）
        update_fields = {
            "content.system_prompt": old_content.get("system_prompt", ""),
            "content.user_prompt": old_content.get("tool_guidance", ""),  # 旧版没有 user_prompt，用 tool_guidance 代替
            # content.tool_guidance 不更新，保持新版不变
            "content.analysis_requirements": old_content.get("analysis_requirements", ""),
            "content.output_format": old_content.get("output_format", ""),
            "content.constraints": old_content.get("constraints", "")
        }

        print(f"   📝 更新字段:")
        print(f"      - system_prompt: {len(update_fields['content.system_prompt'])} 字符")
        print(f"      - user_prompt: {len(update_fields['content.user_prompt'])} 字符 (来自旧版 tool_guidance)")
        print(f"      - tool_guidance: 保持新版不变")
        print(f"      - analysis_requirements: {len(update_fields['content.analysis_requirements'])} 字符")
        print(f"      - output_format: {len(update_fields['content.output_format'])} 字符")
        print(f"      - constraints: {len(update_fields['content.constraints'])} 字符")

        # 执行更新
        result = collection.update_one(
            {"_id": template["_id"]},
            {"$set": update_fields}
        )

        if result.modified_count > 0:
            print(f"   ✅ 更新成功")
            updated_count += 1
        else:
            print(f"   ⚠️ 未修改（内容可能相同）")

    # 4. 打印总结
    print("\n" + "=" * 80)
    print("✅ 更新完成")
    print("=" * 80)
    print(f"  - 总共处理: {len(new_templates)} 个模板")
    print(f"  - 更新成功: {updated_count} 个")
    print("=" * 80)


if __name__ == "__main__":
    update_prompts()
