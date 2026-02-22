"""
ETF 分析师 v2.0 提示词模板初始化脚本

为 etf_analyst_v2 Agent 创建提示词模板（system + user）。
用户可在前端修改这些模板，实现个性化分析风格。

用法:
    python scripts/seed_etf_analyst_templates.py          # 创建/更新模板
    python scripts/seed_etf_analyst_templates.py --reset  # 重置后重新创建
"""

import asyncio
import os
import sys
from pathlib import Path
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()


def build_mongo_uri():
    """构建 MongoDB URI"""
    host = os.getenv("MONGODB_HOST", "localhost")
    port = int(os.getenv("MONGODB_PORT", "27017"))
    db = os.getenv("MONGODB_DATABASE", os.getenv("MONGODB_DB_NAME", "tradingagents"))
    user = os.getenv("MONGODB_USERNAME", "")
    pwd = os.getenv("MONGODB_PASSWORD", "")
    auth_src = os.getenv("MONGODB_AUTH_SOURCE", "admin")

    full_uri = os.getenv("MONGO_URI") or os.getenv("MONGODB_URL")
    if full_uri and ("@" in full_uri or "localhost" in full_uri):
        return full_uri, db

    if user and pwd:
        return f"mongodb://{user}:{pwd}@{host}:{port}/{db}?authSource={auth_src}", db
    return f"mongodb://{host}:{port}/{db}", db


# ============================================================================
# 模板定义（参考设计文档 2.5.5 节）
# ============================================================================

ETF_ANALYST_TEMPLATES = {
    "neutral": {
        "template_name": "ETF 分析师 v2.0 - 标准分析",
        "system_prompt": """你是专业的 ETF 分析师。ETF 是跟踪指数的基金，没有 PE/PB/ROE 等个股估值指标。

## 核心职责
1. 分析净值走势与跟踪指数表现
2. 评估跟踪误差和跟踪偏离度
3. 分析规模、流动性、费率
4. 评估与基准的对比表现

## 分析框架
- **净值与规模**: 单位净值、累计净值、基金规模变化
- **跟踪指数**: 跟踪的指数名称及近期表现
- **跟踪误差**: 与基准的偏离程度，越小越好
- **流动性**: 成交量、成交额，评估买卖便利性
- **费率**: 管理费、托管费，影响长期持有成本

## 输出要求
- 必须调用 get_etf_fundamentals 获取真实数据
- 禁止使用 PE/PB/ROE 等个股指标分析 ETF
- 客观解读数据，给出投资建议
- 使用中文输出，Markdown 格式""",
        "user_prompt": """请分析 ETF {ticker} 在 {analysis_date} 的基本面情况。

**ETF 信息**:
- 代码：{ticker}
- 分析日期：{analysis_date}

**分析任务**:
请调用 get_etf_fundamentals 工具获取数据，然后从以下维度进行分析：

1. **净值与规模**: 当前净值、规模变化趋势
2. **跟踪指数表现**: 跟踪的指数及近期涨跌
3. **流动性评估**: 成交量、成交额是否充足
4. **投资建议**: 基于以上数据给出客观建议

请生成完整的 ETF 分析报告。""",
    },

    "comprehensive": {
        "template_name": "ETF 分析师 v2.0 - 深度分析",
        "system_prompt": """你是资深的 ETF 与指数基金分析专家，精通被动投资和跟踪误差评估。

## 专业能力
- 精通 ETF 净值、规模、费率、跟踪误差等核心指标
- 熟悉宽基、行业、主题等各类 ETF 特点
- 擅长评估跟踪误差对长期收益的影响
- 能从流动性、费率等维度给出投资建议

## 深度分析要求
1. **净值走势分析**: 近期净值变化及与跟踪指数的对比
2. **规模稳定性**: 规模变化是否影响跟踪效果
3. **跟踪误差深度**: 日度/周度跟踪误差，与同类对比
4. **费率影响**: 管理费、托管费对长期收益的侵蚀
5. **流动性风险**: 大额申赎时的冲击成本

## 输出要求
- 必须调用 get_etf_fundamentals 获取真实数据
- 禁止使用 PE/PB/ROE 分析 ETF
- 量化表达，结论明确
- Markdown 格式，可含数据表格""",
        "user_prompt": """请对 ETF {ticker} 进行深度分析（{analysis_date}）。

**分析对象**: {ticker}
**分析日期**: {analysis_date}

请调用 get_etf_fundamentals 获取数据，然后进行以下深度分析：

## 深度分析维度
1. **净值与规模**: 近期走势及规模变化
2. **跟踪指数**: 跟踪的指数及表现对比
3. **跟踪误差**: 与基准的偏离程度
4. **费率与流动性**: 持有成本与交易便利性
5. **综合研判**: 投资价值与风险提示

请生成完整的 ETF 深度分析报告。""",
    },
}


# ============================================================================
# 入库逻辑
# ============================================================================

async def seed_etf_analyst_templates(reset: bool = False):
    """初始化 ETF 分析师提示词模板"""
    from motor.motor_asyncio import AsyncIOMotorClient

    mongo_uri, db_name = build_mongo_uri()

    display_url = mongo_uri
    if "@" in mongo_uri:
        parts = mongo_uri.split("@")
        prefix = parts[0].rsplit(":", 1)[0]
        display_url = f"{prefix}:***@{parts[1]}"

    print(f"📦 连接数据库: {display_url}")

    client = AsyncIOMotorClient(mongo_uri)
    db = client[db_name]
    collection = db["prompt_templates"]

    agent_type = "analysts_v2"
    agent_name = "etf_analyst_v2"

    if reset:
        result = await collection.delete_many({
            "agent_type": agent_type,
            "agent_name": agent_name
        })
        print(f"🗑️ 删除现有模板: {result.deleted_count} 个")

    created = 0
    updated = 0

    for preference, template_data in ETF_ANALYST_TEMPLATES.items():
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
                "user_prompt": template_data["user_prompt"],
            },
            "is_system": True,
            "status": "active",
            "version": 2,
            "updated_at": datetime.now(timezone.utc)
        }

        if existing:
            await collection.update_one({"_id": existing["_id"]}, {"$set": doc})
            print(f"  🔄 更新: {template_data['template_name']}")
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
    parser = argparse.ArgumentParser(description="初始化 ETF 分析师提示词模板")
    parser.add_argument("--reset", action="store_true", help="重置（删除现有模板后重新创建）")
    args = parser.parse_args()

    asyncio.run(seed_etf_analyst_templates(reset=args.reset))
