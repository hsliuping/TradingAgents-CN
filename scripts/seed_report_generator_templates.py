"""
报告生成器 v2.0 提示词模板初始化脚本

为 report_generator_v2 Agent 创建提示词模板。
"""
import asyncio
import os
import sys
from pathlib import Path
from datetime import datetime, timezone

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()


def build_mongo_uri():
    """构建 MongoDB URI（支持认证）"""
    host = os.getenv("MONGODB_HOST", "localhost")
    port = int(os.getenv("MONGODB_PORT", "27017"))
    db = os.getenv("MONGODB_DATABASE", os.getenv("MONGODB_DB_NAME", "tradingagents"))
    user = os.getenv("MONGODB_USERNAME", "")
    pwd = os.getenv("MONGODB_PASSWORD", "")
    auth_src = os.getenv("MONGODB_AUTH_SOURCE", "admin")

    # 也尝试从 MONGODB_URL 或 MONGO_URI 读取（如果已包含完整连接字符串）
    full_uri = os.getenv("MONGO_URI") or os.getenv("MONGODB_URL")
    if full_uri and ("@" in full_uri or "localhost" in full_uri):
        return full_uri, db

    if user and pwd:
        return f"mongodb://{user}:{pwd}@{host}:{port}/{db}?authSource={auth_src}", db
    return f"mongodb://{host}:{port}/{db}", db


# 报告生成器提示词模板
REPORT_GENERATOR_TEMPLATES = {
    "neutral": {
        "template_name": "报告生成器 v2.0 - 中性",
        "system_prompt": """你是一位专业的报告生成器，负责将多个分析师的输出整合为结构化的综合分析报告。

## 核心职责
1. 汇总各分析师的报告和观点
2. 提取关键信息和数据
3. 根据报告模板生成结构化输出
4. 确保报告内容客观、完整、有条理

## 工作原则
- 保持客观中立，如实呈现各方观点
- 不添加主观判断或新的分析内容
- 按照报告模板要求的格式输出
- 突出关键数据和重要结论

## 输出要求
- 结构清晰，层次分明
- 数据准确，引用明确
- 语言简洁，重点突出
- 符合报告模板定义的 schema""",
        "tool_guidance": """**报告生成指导**:

你将收到以下输入：
1. 【各分析师报告】- 来自工作流中各个分析师节点的输出
2. 【报告模板】- 定义了报告应该包含的字段和格式

请按照报告模板的要求，从分析师报告中提取相关信息，生成结构化报告。

**提取原则**：
- 市场分析 → 从 market_analyst 输出提取
- 基本面分析 → 从 fundamentals_analyst 输出提取
- 新闻分析 → 从 news_analyst 输出提取
- 情绪分析 → 从 social_analyst 输出提取
- 综合结论 → 整合所有分析师观点""",
        "analysis_requirements": """**报告生成要求**:

1. **内容完整性**
   - 确保报告模板要求的所有必填字段都有内容
   - 对于可选字段，有数据则填写，无数据则留空

2. **信息准确性**
   - 所有数据必须来自分析师报告，不可编造
   - 引用数据时注明来源分析师

3. **结构规范性**
   - 按照 output_schema 定义的字段顺序和类型输出
   - 数值类型字段确保类型正确
   - 枚举类型字段确保值在允许范围内

4. **摘要质量**
   - 摘要字段应简明扼要，突出重点
   - 避免重复冗余的表述""",
        "output_format": """**输出格式**:

请生成符合报告模板 output_schema 定义的 JSON 格式报告。

示例结构：
```json
{
  "summary": "一句话概述分析结论",
  "market_analysis": "市场分析摘要...",
  "fundamental_analysis": "基本面分析摘要...",
  "risk_factors": ["风险1", "风险2"],
  "conclusion": "综合结论...",
  "confidence": 75
}
```

注意：实际输出字段由具体报告模板决定。""",
        "constraints": """**重要约束**:

1. ⚠️ **禁止编造数据** - 所有内容必须来自分析师报告
2. ⚠️ **禁止主观判断** - 不添加自己的分析观点
3. ⚠️ **遵循模板** - 严格按照报告模板的字段定义输出
4. ⚠️ **格式正确** - 确保输出是有效的 JSON 格式
5. ⚠️ **中文输出** - 所有文本内容使用中文"""
    }
}


async def seed_report_generator_templates(reset: bool = False):
    """初始化报告生成器提示词模板"""
    from motor.motor_asyncio import AsyncIOMotorClient

    mongo_uri, db_name = build_mongo_uri()

    # 隐藏密码显示
    display_url = mongo_uri
    if "@" in mongo_uri:
        parts = mongo_uri.split("@")
        prefix = parts[0].rsplit(":", 1)[0]
        display_url = f"{prefix}:***@{parts[1]}"

    print(f"📦 连接数据库: {display_url}")

    client = AsyncIOMotorClient(mongo_uri)
    db = client[db_name]
    collection = db["prompt_templates"]
    
    agent_type = "post_processors"
    agent_name = "report_generator_v2"
    
    if reset:
        result = await collection.delete_many({
            "agent_type": agent_type,
            "agent_name": agent_name
        })
        print(f"🗑️ 删除现有模板: {result.deleted_count} 个")
    
    created = 0
    updated = 0
    
    for preference, template_data in REPORT_GENERATOR_TEMPLATES.items():
        existing = await collection.find_one({
            "agent_type": agent_type,
            "agent_name": agent_name,
            "preference_type": preference,
            "is_system": True
        })
        
        doc = {
            "agent_type": agent_type,
            "agent_name": agent_name,
            "template_name": template_data["template_name"],
            "preference_type": preference,
            "content": {
                "system_prompt": template_data["system_prompt"],
                "tool_guidance": template_data["tool_guidance"],
                "analysis_requirements": template_data["analysis_requirements"],
                "output_format": template_data["output_format"],
                "constraints": template_data["constraints"]
            },
            "is_system": True,
            "status": "active",
            "version": 2,
            "updated_at": datetime.now(timezone.utc)
        }
        
        if existing:
            await collection.update_one({"_id": existing["_id"]}, {"$set": doc})
            print(f"  ✅ 更新: {template_data['template_name']}")
            updated += 1
        else:
            doc["created_at"] = datetime.now(timezone.utc)
            await collection.insert_one(doc)
            print(f"  ✅ 创建: {template_data['template_name']}")
            created += 1
    
    print(f"\n📊 完成: 创建 {created} 个, 更新 {updated} 个")
    client.close()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="初始化报告生成器提示词模板")
    parser.add_argument("--reset", action="store_true", help="重置（删除现有模板后重新创建）")
    args = parser.parse_args()
    
    asyncio.run(seed_report_generator_templates(reset=args.reset))

