"""
报告模板初始化脚本

创建预设的报告模板，用于不同类型的工作流。
"""
import asyncio
import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from datetime import datetime


# 预设报告模板
BUILTIN_REPORT_TEMPLATES = [
    {
        "template_id": "screening_report",
        "name": "选股初选报告",
        "description": "用于选股初选流程，输出简洁的通过/不通过判断",
        "workflow_id": "screening",
        "output_schema": [
            {
                "name": "conclusion",
                "type": "string",
                "description": "初选结论",
                "required": True,
                "enum": ["pass", "reject", "hold"]
            },
            {
                "name": "score",
                "type": "number",
                "description": "综合评分（0-100）",
                "required": True,
                "min_value": 0,
                "max_value": 100
            },
            {
                "name": "key_factors",
                "type": "array",
                "description": "关键判断因素（3-5个）",
                "required": True
            },
            {
                "name": "summary",
                "type": "string",
                "description": "一句话总结（不超过100字）",
                "required": True
            },
            {
                "name": "next_action",
                "type": "string",
                "description": "建议的下一步行动",
                "required": False,
                "enum": ["deep_analysis", "monitor", "ignore"]
            }
        ],
        "generator_prompt": """请根据分析结果生成初选报告：
1. conclusion: 判断是否值得深入分析（pass=通过初选, reject=不通过, hold=观望）
2. score: 给出综合评分（0-100分）
3. key_factors: 列出3-5个关键判断依据
4. summary: 用一句话总结初选结论
5. next_action: 建议的下一步（deep_analysis=进行深度分析, monitor=持续关注, ignore=暂不关注）""",
        "summary_fields": ["conclusion", "score", "summary"],
        "display_config": {
            "primary_field": "conclusion",
            "score_color_map": {
                "pass": "green",
                "reject": "red",
                "hold": "orange"
            }
        }
    },
    {
        "template_id": "deep_analysis_report",
        "name": "深度分析报告",
        "description": "用于深度分析流程，输出详细的投资分析报告",
        "workflow_id": "deep_analysis",
        "output_schema": [
            {
                "name": "recommendation",
                "type": "string",
                "description": "投资观点",
                "required": True,
                "enum": ["bullish", "bearish", "neutral"]
            },
            {
                "name": "confidence",
                "type": "number",
                "description": "置信度（0-1）",
                "required": True,
                "min_value": 0,
                "max_value": 1
            },
            {
                "name": "risk_level",
                "type": "string",
                "description": "风险等级",
                "required": True,
                "enum": ["low", "medium", "high"]
            },
            {
                "name": "price_analysis",
                "type": "object",
                "description": "价格分析区间",
                "required": False
            },
            {
                "name": "strengths",
                "type": "array",
                "description": "优势/看涨因素",
                "required": True
            },
            {
                "name": "weaknesses",
                "type": "array",
                "description": "劣势/风险因素",
                "required": True
            },
            {
                "name": "catalysts",
                "type": "array",
                "description": "潜在催化剂",
                "required": False
            },
            {
                "name": "detailed_analysis",
                "type": "string",
                "description": "详细分析报告",
                "required": True
            }
        ],
        "generator_prompt": """请根据各分析师的深度分析结果，生成一份完整的投资分析报告：
1. recommendation: 综合各方观点给出投资观点（bullish/bearish/neutral）
2. confidence: 观点的置信度（0-1之间）
3. risk_level: 风险等级评估
4. price_analysis: 包含 support_level（支撑位）和 resistance_level（压力位）
5. strengths: 列出主要看涨因素
6. weaknesses: 列出主要风险因素
7. catalysts: 列出可能影响股价的催化剂事件
8. detailed_analysis: 撰写一份详细的分析报告（500-1000字）""",
        "summary_fields": ["recommendation", "confidence", "risk_level"],
        "display_config": {
            "primary_field": "recommendation",
            "sections": ["price_analysis", "strengths", "weaknesses", "catalysts", "detailed_analysis"]
        }
    },
    {
        "template_id": "position_check_report",
        "name": "持仓检查报告",
        "description": "用于持仓检查流程，输出持仓风险评估",
        "workflow_id": "position_check",
        "output_schema": [
            {
                "name": "status",
                "type": "string",
                "description": "持仓状态",
                "required": True,
                "enum": ["safe", "warning", "danger"]
            },
            {
                "name": "health_score",
                "type": "number",
                "description": "持仓健康度评分（0-100）",
                "required": True
            },
            {
                "name": "risk_alerts",
                "type": "array",
                "description": "风险预警列表",
                "required": False
            },
            {
                "name": "action_suggestions",
                "type": "array",
                "description": "操作建议",
                "required": False
            }
        ],
        "generator_prompt": """请根据分析结果生成持仓检查报告：
1. status: 持仓当前状态（safe=安全, warning=需关注, danger=高风险）
2. health_score: 持仓健康度评分
3. risk_alerts: 列出需要关注的风险点
4. action_suggestions: 给出具体的建议""",
        "summary_fields": ["status", "health_score"],
        "display_config": {
            "primary_field": "status",
            "status_color_map": {
                "safe": "green",
                "warning": "orange",
                "danger": "red"
            }
        }
    }
]


def build_mongo_uri() -> str:
    """构建 MongoDB 连接 URI（支持认证）"""
    import os
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


async def seed_report_templates(reset: bool = False):
    """
    初始化报告模板

    Args:
        reset: 是否删除现有模板后重新创建
    """
    from dotenv import load_dotenv
    load_dotenv()

    from motor.motor_asyncio import AsyncIOMotorClient
    import os

    mongo_url, db_name = build_mongo_uri()

    # 隐藏密码显示
    display_url = mongo_url
    if "@" in mongo_url:
        parts = mongo_url.split("@")
        prefix = parts[0].rsplit(":", 1)[0]  # 隐藏密码
        display_url = f"{prefix}:***@{parts[1]}"

    client = AsyncIOMotorClient(mongo_url)
    db = client[db_name]
    collection = db.report_templates

    print(f"📦 连接数据库: {display_url}")

    if reset:
        print("🗑️ 删除现有模板...")
        result = await collection.delete_many({})
        print(f"   删除了 {result.deleted_count} 个模板")

    created_count = 0
    updated_count = 0
    skipped_count = 0

    for template in BUILTIN_REPORT_TEMPLATES:
        template_id = template["template_id"]

        # 检查是否已存在
        existing = await collection.find_one({"template_id": template_id})

        if existing:
            if reset:
                # reset 模式下已删除，直接插入
                pass
            else:
                # 更新现有模板
                template["updated_at"] = datetime.utcnow()
                await collection.update_one(
                    {"template_id": template_id},
                    {"$set": template}
                )
                print(f"   ✏️ 更新模板: {template_id}")
                updated_count += 1
                continue

        # 插入新模板
        template["created_at"] = datetime.utcnow()
        template["updated_at"] = datetime.utcnow()
        template["status"] = "active"

        await collection.insert_one(template)
        print(f"   ✅ 创建模板: {template_id} ({template['name']})")
        created_count += 1

    print(f"\n📊 完成: 创建 {created_count}, 更新 {updated_count}, 跳过 {skipped_count}")

    # 显示所有模板
    print("\n📋 当前报告模板列表:")
    async for doc in collection.find({}, {"template_id": 1, "name": 1, "workflow_id": 1}):
        print(f"   - {doc['template_id']}: {doc['name']} (workflow: {doc['workflow_id']})")

    client.close()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="初始化报告模板")
    parser.add_argument("--reset", action="store_true", help="删除现有模板后重新创建")
    args = parser.parse_args()

    asyncio.run(seed_report_templates(reset=args.reset))

