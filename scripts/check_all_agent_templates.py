"""检查所有 Agent 的模板内容"""
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv
import os

load_dotenv()

async def check_templates():
    """检查所有 Agent 的模板内容"""
    # 连接数据库
    mongo_uri = os.getenv("MONGO_URI", "mongodb://localhost:27017")
    client = AsyncIOMotorClient(mongo_uri)
    db = client["tradingagents"]

    # 🔧 查询正确的集合：prompt_templates
    templates = await db["prompt_templates"].find({
        "agent_type": "reviewers_v2",
        "version": 2
    }).to_list(length=100)

    print(f"\n📊 所有 reviewers_v2 的用户提示词模板（共 {len(templates)} 个）：\n")
    for i, template in enumerate(templates, 1):
        template_id = template.get("_id")
        agent_name = template.get("agent_name", "N/A")
        preference_type = template.get("preference_type", "N/A")
        content = template.get("content", "")

        print(f"{i}. agent_name: {agent_name}")
        print(f"   template_id: {template_id}")
        print(f"   preference_type: {preference_type}")
        print(f"   内容长度: {len(content)}")

        # 检查是否包含评分相关的内容
        has_10_scale = False
        has_100_scale = False

        if "1-10" in content or "1–10" in content:
            has_10_scale = True
            print(f"   ⚠️ 发现 10 分制评分要求！")
            # 打印相关行
            lines = content.split('\n')
            for j, line in enumerate(lines):
                if ("1-10" in line or "1–10" in line) and "score" in line.lower():
                    print(f"      第 {j+1} 行: {line.strip()}")

        if "0-100" in content or "0–100" in content or "百分制" in content:
            has_100_scale = True
            print(f"   ✅ 已使用百分制评分！")

        if not has_10_scale and not has_100_scale:
            print(f"   ℹ️ 未找到明确的评分制度说明")

        print()

    client.close()

if __name__ == "__main__":
    asyncio.run(check_templates())

