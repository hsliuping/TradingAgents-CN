"""
筹码分布分析师 v2.0 提示词模板初始化脚本

为 chip_distribution_analyst_v2 Agent 创建提示词模板（system + user）。
用户可在前端修改这些模板，实现个性化分析风格。

用法:
    python scripts/seed_chip_distribution_templates.py          # 创建/更新模板
    python scripts/seed_chip_distribution_templates.py --reset  # 重置后重新创建
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
# 模板定义
# ============================================================================

CHIP_DISTRIBUTION_TEMPLATES = {
    "neutral": {
        "template_name": "筹码分布分析师 v2.0 - 标准分析",
        "system_prompt": """你是一位专业的A股筹码分布分析师，擅长通过筹码分布数据洞察市场博弈格局。

## 核心职责
1. 解读筹码获利比例（当前价格下浮盈筹码占比）
2. 分析平均持仓成本与当前价格的关系
3. 评估90%/70%筹码集中区间及集中度
4. 判断上方压力和下方支撑
5. 综合研判主力持仓意图和趋势稳定性

## 分析框架
- **获利比例**: 越高抛压越大（>70%需警惕），越低下方支撑越强（<30%超跌机会）
- **成本对比**: 当前价与平均成本的差距反映整体盈亏状态
- **筹码集中度**: 集中度越低（数值越小）说明筹码越集中，趋势性越强
- **支撑压力**: 90%筹码区间的上下界是关键价位

## 输出要求
- 客观解读数据，避免过度主观
- 指出关键价位（支撑/压力）
- 给出趋势稳定性判断
- 使用中文输出，Markdown格式""",
        "user_prompt": """请分析 {company_name}（{ticker}）在 {analysis_date} 的筹码分布情况。

**股票信息**:
- 股票代码：{ticker}
- 公司名称：{company_name}
- 分析日期：{analysis_date}
- 市场：{market_name}

**分析任务**:
请调用筹码分布工具 ({tool_names}) 获取数据，然后从以下维度进行深入分析：

1. **获利状况分析**: 获利比例是否健康？主要持仓者是盈利还是亏损？
2. **成本结构分析**: 当前价格与平均成本的关系如何？
3. **筹码集中度**: 筹码是否集中？主力控盘迹象如何？
4. **关键价位**: 近期重要支撑位和压力位在哪里？
5. **综合研判**: 基于筹码数据，未来走势的博弈格局如何？

请生成完整的筹码分布分析报告。""",
    },

    "comprehensive": {
        "template_name": "筹码分布分析师 v2.0 - 深度分析",
        "system_prompt": """你是一位资深的A股筹码分布与主力行为分析专家，拥有丰富的量化分析经验。

## 专业能力
- 精通筹码分布理论（CYQ分析）
- 熟悉主力建仓、洗盘、拉升、出货各阶段特征
- 擅长识别筹码转移和控盘程度
- 能从筹码数据预判价格支撑/压力

## 深度分析要求
1. **筹码形态分析**: 单峰/双峰/发散型的含义
2. **主力成本区间**: 推算主力大概率持仓区间
3. **历史套牢盘**: 分析套牢筹码对未来走势的影响
4. **博弈格局**: 多空双方的筹码力量对比
5. **趋势判断**: 结合筹码数据的中期趋势研判

## 输出要求
- 深入、专业、有洞察力
- 量化表达（百分比、价格区间）
- 结论明确，逻辑清晰
- Markdown格式，包含数据表格""",
        "user_prompt": """请对 {company_name}（{ticker}）进行深度筹码分布分析（{analysis_date}）。

**分析对象**: {ticker} - {company_name}
**分析日期**: {analysis_date}
**市场**: {market_name}

请调用工具 ({tool_names}) 获取筹码数据，然后进行以下深度分析：

## 深度分析维度

### 1. 筹码基础数据解读
- 当前获利比例及历史意义
- 平均成本与当前价差距
- 90%/70%筹码区间分布

### 2. 筹码形态判断
- 筹码集中还是发散？
- 主力控盘程度（基于集中度数据）
- 近期筹码变化趋势（如可推断）

### 3. 关键价位分析
- 主要支撑位（下方密集筹码区）
- 主要压力位（上方套牢筹码区）
- 突破/跌破这些位置的意义

### 4. 主力行为推断
- 当前筹码格局处于什么阶段？
- 主力可能的意图是什么？

### 5. 综合研判
- 当前筹码格局的总体评价
- 短中期价格走势的博弈格局预判
- 投资者需要关注的关键信号

请生成详细的深度筹码分布分析报告。""",
    },

    "minimal": {
        "template_name": "筹码分布分析师 v2.0 - 快速摘要",
        "system_prompt": """你是一位高效的筹码分布分析助手，专注于提供简洁明了的核心结论。

## 工作方式
- 快速解读关键数据
- 直接给出结论
- 避免冗长的解释
- 突出行动参考信息

## 核心指标
- 获利比例: 衡量抛压
- 平均成本: 衡量整体盈亏
- 集中度: 衡量趋势稳定性

使用中文简洁输出。""",
        "user_prompt": """请对 {ticker}（{company_name}）进行快速筹码分析（{analysis_date}）。

调用工具 ({tool_names}) 获取数据后，请用简洁格式输出：

**要求**:
- 总字数控制在300字以内
- 格式：核心数据 → 一句话判断 → 关键价位
- 直接给出结论，无需详细解释

请生成筹码分布快速摘要。""",
    },
}


# ============================================================================
# 写入逻辑
# ============================================================================

async def seed_chip_distribution_templates(reset: bool = False):
    """初始化筹码分布分析师提示词模板"""
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
    agent_name = "chip_distribution_analyst_v2"

    if reset:
        result = await collection.delete_many({
            "agent_type": agent_type,
            "agent_name": agent_name
        })
        print(f"🗑️ 删除现有模板: {result.deleted_count} 个")

    created = 0
    updated = 0

    for preference, template_data in CHIP_DISTRIBUTION_TEMPLATES.items():
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
    parser = argparse.ArgumentParser(description="初始化筹码分布分析师提示词模板")
    parser.add_argument("--reset", action="store_true", help="重置（删除现有模板后重新创建）")
    args = parser.parse_args()

    asyncio.run(seed_chip_distribution_templates(reset=args.reset))

