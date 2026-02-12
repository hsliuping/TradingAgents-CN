"""
示例 Skill 初始化脚本

向数据库写入 3 个示例 Skill：
1. Python 类型 — 包装已有的 get_stock_news_unified 工具
2. HTTP 类型   — 调用墨迹天气 API（免费、无需 Key、支持国内城市中文名）
3. 知识型      — 纯 Markdown 指令，无执行实现

用法:
    python scripts/seed_example_skills.py          # 写入数据库 + 注册到 ToolRegistry
    python scripts/seed_example_skills.py --dry-run # 仅打印，不写入
"""

import argparse
import asyncio
import json
import logging
import sys
import os

# 确保项目根目录在 sys.path 中
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

# ============================================================================
# 示例 Skill 定义
# ============================================================================

EXAMPLE_SKILLS = [
    # ── 1. Python 类型：包装已有的 get_stock_news_unified ──────────────
    {
        "name": "get-stock-news",
        "description": "获取股票相关新闻，支持A股、港股、美股。自动识别股票类型并调用对应数据源。",
        "version": "1.0.0",
        "author": "TradingAgents-CN",
        "category": "news",
        "tags": ["新闻", "A股", "港股", "美股"],
        "icon": "📰",
        "color": "#3498db",
        "when_to_use": "当用户需要了解某只股票的最新新闻、公告或市场动态时使用此工具。",
        "parameters": [
            {"name": "ticker", "type": "string", "description": "股票代码（如 000001、0700.HK、AAPL）", "required": True},
            {"name": "curr_date", "type": "string", "description": "当前日期，格式 YYYY-MM-DD", "required": True},
        ],
        "returns": {"type": "string", "description": "新闻分析报告文本"},
        "implementation": {
            "type": "python",
            "module": "core.tools.implementations.news.stock_news",
            "function": "get_stock_news_unified",
            "is_async": False,
        },
        "instructions": (
            "# 获取股票新闻\n\n"
            "当用户询问某只股票的新闻、公告、市场消息面时，调用此 Skill。\n\n"
            "## 示例\n"
            "- \"帮我查一下贵州茅台最近的新闻\"\n"
            "- \"600519 有什么最新公告？\"\n"
            "- \"AAPL 最近有什么消息？\"\n\n"
            "## 注意事项\n"
            "- A股代码请使用6位纯数字（如 000001）\n"
            "- 港股代码带 .HK 后缀\n"
            "- 美股代码直接使用字母代码\n"
        ),
        "enabled": True,
        "fc_enabled": True,
        "is_builtin": True,
    },
    # ── 2. HTTP 类型：调用外部天气 API（演示用） ──────────────────────
    {
        "name": "get-weather",
        "description": "获取指定城市的实时天气信息，包括温度、湿度、风力、空气质量等（演示外部 HTTP API 调用）",
        "version": "1.1.0",
        "author": "TradingAgents-CN",
        "category": "utility",
        "tags": ["天气", "HTTP", "演示"],
        "icon": "🌤️",
        "color": "#f39c12",
        "when_to_use": "当用户询问某个城市的天气情况时使用此工具。支持国内城市中文名称查询。",
        "parameters": [
            {"name": "city", "type": "string", "description": "城市名称（中文），如 北京、上海、广州、深圳", "required": True},
        ],
        "returns": {"type": "object", "description": "天气信息 JSON，包含 city/weather/temp/humidity/wind/airQuality 等字段"},
        "implementation": {
            "type": "http",
            "url": "http://autodev.openspeech.cn/csp/api/v2.1/weather?openId=aiuicus&clientType=android&sign=android&needMoreData=true&pageNo=1&pageSize=1",
            "method": "GET",
            "timeout": 10,
        },
        "instructions": (
            "# 获取天气信息\n\n"
            "调用墨迹天气免费 API 获取国内城市实时天气。\n\n"
            "## 示例\n"
            "- 查询北京天气: city=北京\n"
            "- 查询上海天气: city=上海\n"
            "- 查询广州天气: city=广州\n\n"
            "## 返回数据\n"
            "- city: 城市名\n"
            "- weather: 天气状况（晴、多云、阴、雨等）\n"
            "- temp: 当前温度\n"
            "- humidity: 湿度\n"
            "- wind: 风力风向\n"
            "- high/low: 最高/最低温度\n"
            "- airQuality: 空气质量\n\n"
            "## 说明\n"
            "这是一个演示 HTTP 类型 Skill 的示例，展示如何通过标准接口调用外部 API。\n"
        ),
        "enabled": True,
        "fc_enabled": True,
        "is_builtin": True,
    },
    # ── 3. 知识型：无执行实现，纯 Markdown 指令 ──────────────────────
    {
        "name": "a-share-analysis-guidelines",
        "description": "A股分析规范指南 — 提供合规的分析报告撰写规范",
        "version": "1.0.0",
        "author": "TradingAgents-CN",
        "category": "knowledge",
        "tags": ["合规", "A股", "规范", "指南"],
        "icon": "📋",
        "color": "#9b59b6",
        "instructions": (
            "# A股分析规范指南\n\n"
            "撰写A股分析报告时，请遵循以下合规规范：\n\n"
            "## 用词规范\n"
            "- ✅ 使用「参考价位」代替「目标价」\n"
            "- ✅ 使用「分析观点」代替「操作建议」\n"
            "- ✅ 使用「看多/看空」代替「买入/卖出」\n"
            "- ✅ 使用「值得关注」代替「强烈推荐」\n\n"
            "## 免责声明\n"
            "所有报告必须包含免责声明：\n"
            "> 本报告仅供学习参考，不构成任何投资建议。投资有风险，入市需谨慎。\n\n"
            "## 数据要求\n"
            "- 所有数据必须标注来源和时间\n"
            "- 技术指标需说明计算方法和参数\n"
            "- 财务数据需注明报告期\n"
        ),
        "enabled": True,
        "fc_enabled": False,
        "is_builtin": True,
    },
]


# ============================================================================
# 写入逻辑
# ============================================================================

async def seed_skills(dry_run: bool = False):
    """将示例 Skill 写入数据库并注册到 ToolRegistry"""
    from datetime import datetime

    if dry_run:
        logger.info("🔍 [DRY-RUN] 仅打印，不写入数据库\n")
        for skill in EXAMPLE_SKILLS:
            logger.info(f"  📦 {skill['name']}  ({skill.get('implementation', {}).get('type', 'knowledge')})")
            logger.info(f"     {skill['description']}")
        logger.info(f"\n共 {len(EXAMPLE_SKILLS)} 个示例 Skill")
        return

    # 连接数据库
    from app.core.database import init_database, get_mongo_db
    await init_database()
    db = get_mongo_db()
    collection = db.skills

    # 加载 ToolRegistry（用于注册可执行 Skill）
    from core.skills.models import SkillMetadata
    from core.skills.executor import SkillExecutor
    from core.tools.registry import get_tool_registry
    registry = get_tool_registry()

    created = 0
    skipped = 0

    for skill_data in EXAMPLE_SKILLS:
        name = skill_data["name"]

        # 检查是否已存在
        existing = await collection.find_one({"name": name})
        if existing:
            logger.info(f"  ⏭️  跳过已存在: {name}")
            skipped += 1
            continue

        # 添加时间戳
        now = datetime.utcnow().isoformat()
        doc = {**skill_data, "created_at": now, "updated_at": now}
        await collection.insert_one(doc)
        doc.pop("_id", None)

        # 注册到 ToolRegistry（可执行 Skill）
        impl = doc.get("implementation")
        params = doc.get("parameters", [])
        if impl and params:
            try:
                skill = SkillMetadata(**doc)
                wrapper = SkillExecutor.create_sync_wrapper(skill)
                tool_id = skill.name.replace("-", "_")
                registry.register_function(
                    tool_id=tool_id,
                    func=wrapper,
                    name=skill.description[:50],
                    category=skill.category,
                    description=skill.description,
                    is_online=True,
                    override=True,
                )
                logger.info(f"  ✅ 已创建并注册: {name}  →  tool_id={tool_id}")
            except Exception as e:
                logger.warning(f"  ⚠️  已写入但注册失败: {name} — {e}")
        else:
            logger.info(f"  ✅ 已创建(知识型): {name}")

        created += 1

    logger.info(f"\n📊 结果: 创建 {created} 个, 跳过 {skipped} 个")

    # 验证：列出 ToolRegistry 中已注册的 Skill
    logger.info("\n🔍 ToolRegistry 验证:")
    for skill_data in EXAMPLE_SKILLS:
        tool_id = skill_data["name"].replace("-", "_")
        has = registry.has_tool(tool_id)
        func = registry.get_function(tool_id) is not None
        marker = "✅" if (has and func) else ("📋" if not skill_data.get("implementation") else "❌")
        logger.info(f"  {marker} {tool_id}: metadata={has}, function={func}")


def main():
    parser = argparse.ArgumentParser(description="写入示例 Skill 到数据库")
    parser.add_argument("--dry-run", action="store_true", help="仅打印，不写入")
    args = parser.parse_args()

    logger.info("🚀 TradingAgents-CN Skill 示例初始化\n")
    asyncio.run(seed_skills(dry_run=args.dry_run))
    logger.info("\n✅ 完成！")


if __name__ == "__main__":
    main()



