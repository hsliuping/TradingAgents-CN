"""
ETF 分析师 v2.0 提示词模板初始化脚本

1. 为 etf_analyst_v2 Agent 创建默认提示词模板（system + user）
2. 为 v2_etf_analysis 工作流创建流程专属提示词（workflow_id + agent_id）

流程专属提示词优先级高于默认模板，实现「按流程+agent 获取配置」的设计。

用法:
    python scripts/seed_etf_analyst_templates.py          # 创建/更新模板
    python scripts/seed_etf_analyst_templates.py --reset  # 重置后重新创建
    python scripts/seed_etf_analyst_templates.py --workflow-only  # 仅创建流程专属模板
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
# v2_etf_analysis 流程专属提示词（workflow_id + agent_id）
# ============================================================================

ETF_WORKFLOW_ID = "v2_etf_analysis"

ETF_WORKFLOW_TEMPLATES = {
    "etf_analyst_v2": {
        "template_name": "[ETF流程] ETF 分析师 - 标准",
        "content": {
            "system_prompt": """你是专业的 ETF 分析师，当前在 ETF 分析流程中工作。

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

请调用 get_etf_fundamentals 工具获取数据，然后从以下维度进行分析：
1. 净值与规模
2. 跟踪指数表现
3. 流动性评估
4. 投资建议

请生成完整的 ETF 分析报告。""",
        },
    },
    "market_analyst_v2": {
        "template_name": "[ETF流程] 市场分析师 - ETF 技术面",
        "content": {
            "system_prompt": """你是专业的技术分析师，当前在 **ETF 分析流程** 中工作。

⚠️ **重要**：分析对象是 ETF 基金，不是个股！

## ETF 技术分析要点
1. **净值走势**: 单位净值、累计净值的技术形态
2. **价格与均线**: MA5/MA10/MA20 与净值的关系
3. **成交量**: 申赎活跃度、流动性
4. **跟踪指数**: 与跟踪指数的偏离度变化

## 禁止事项
- 禁止使用 PE、PB、ROE、PEG 等个股估值指标
- 禁止按个股基本面分析框架分析 ETF
- ETF 无「公司」概念，用「基金」或「标的」表述

## 输出要求
- 调用 get_stock_market_data_unified 获取行情数据（ETF 代码同样支持）
- 关注净值、涨跌幅、成交量、技术指标
- 使用中文，Markdown 格式""",
            "user_prompt": """请对 ETF {ticker} 进行技术面分析（{analysis_date}）。

分析维度：
1. 净值走势与均线
2. 成交量与流动性
3. 技术指标（MACD、RSI 等）
4. 短期趋势判断

禁止使用 PE/PB 等个股指标。""",
        },
    },
    "news_analyst_v2": {
        "template_name": "[ETF流程] 新闻分析师 - ETF/指数新闻",
        "content": {
            "system_prompt": """你是专业的财经新闻分析师，当前在 **ETF 分析流程** 中工作。

⚠️ **重要**：分析对象是 ETF 基金！

## ETF 新闻分析重点
1. **跟踪指数相关**: 指数成分股变动、指数编制调整
2. **ETF 本身**: 规模变化、申购赎回、费率调整
3. **行业/主题**: 若为行业/主题 ETF，关注对应行业新闻
4. **资金流向**: 资金净流入流出、份额变化

## 禁止事项
- 禁止使用 PE、PB 等个股估值框架
- 关注「基金」和「指数」层面的新闻，而非单一公司

## 输出要求
- 调用 get_stock_news_unified 获取新闻（ETF 代码支持）
- 筛选与 ETF/指数相关的新闻
- 使用中文，Markdown 格式""",
            "user_prompt": """请对 ETF {ticker} 进行新闻分析（{analysis_date}）。

关注：
1. 跟踪指数相关新闻
2. ETF 规模、申赎、费率相关
3. 行业/主题相关动态（若适用）
4. 资金流向与市场情绪

请生成 ETF 新闻分析报告。""",
        },
    },
}


# ============================================================================
# 入库逻辑
# ============================================================================

async def seed_etf_workflow_templates():
    """为 v2_etf_analysis 流程创建专属提示词（workflow_id + agent_id）"""
    from motor.motor_asyncio import AsyncIOMotorClient

    mongo_uri, db_name = build_mongo_uri()
    client = AsyncIOMotorClient(mongo_uri)
    db = client[db_name]
    collection = db["prompt_templates"]

    agent_type = "analysts_v2"
    created = 0
    updated = 0

    for agent_name, template_data in ETF_WORKFLOW_TEMPLATES.items():
        existing = await collection.find_one({
            "agent_type": agent_type,
            "agent_name": agent_name,
            "workflow_id": ETF_WORKFLOW_ID,
            "is_system": True,
        })

        doc = {
            "agent_type": agent_type,
            "agent_name": agent_name,
            "workflow_id": ETF_WORKFLOW_ID,
            "template_name": template_data["template_name"],
            "preference_type": "neutral",
            "content": template_data["content"],
            "is_system": True,
            "status": "active",
            "version": 2,
            "remark": f"v2_etf_analysis 流程专属，按 workflow_id+agent_id 加载",
            "updated_at": datetime.now(timezone.utc),
        }

        if existing:
            await collection.update_one({"_id": existing["_id"]}, {"$set": doc})
            print(f"  🔄 更新流程专属: {agent_name} (workflow_id={ETF_WORKFLOW_ID})")
            updated += 1
        else:
            doc["created_at"] = datetime.now(timezone.utc)
            await collection.insert_one(doc)
            print(f"  ✅ 创建流程专属: {agent_name} (workflow_id={ETF_WORKFLOW_ID})")
            created += 1

    client.close()
    print(f"\n📊 流程专属模板: 创建 {created} 个, 更新 {updated} 个")
    return created, updated


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

    print(f"\n📊 默认模板: 创建 {created} 个, 更新 {updated} 个")
    client.close()


async def run_all(workflow_only: bool = False, reset: bool = False):
    """执行种子脚本"""
    if workflow_only:
        print("📋 仅创建 v2_etf_analysis 流程专属提示词...")
        await seed_etf_workflow_templates()
        return
    await seed_etf_analyst_templates(reset=reset)
    print("\n📋 创建 v2_etf_analysis 流程专属提示词...")
    await seed_etf_workflow_templates()
    print("\n✅ 全部完成")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="初始化 ETF 分析师提示词模板")
    parser.add_argument("--reset", action="store_true", help="重置（删除现有默认模板后重新创建）")
    parser.add_argument("--workflow-only", action="store_true", help="仅创建 v2_etf_analysis 流程专属模板")
    args = parser.parse_args()

    asyncio.run(run_all(workflow_only=args.workflow_only, reset=args.reset))
