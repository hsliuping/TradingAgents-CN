"""
筹码分布 Skill 初始化脚本

向数据库写入筹码分布相关 Skill：
1. get-chip-distribution      — 统一接口（AkShare优先，Tushare备用）
2. get-chip-distribution-akshare — AkShare 专用接口（免费）
3. get-chip-distribution-tushare — Tushare 专用接口（需5000积分）

用法:
    python scripts/seed_chip_distribution_skills.py          # 写入数据库
    python scripts/seed_chip_distribution_skills.py --dry-run # 仅打印
    python scripts/seed_chip_distribution_skills.py --overwrite # 覆盖已有记录
"""

import argparse
import asyncio
import logging
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

# ============================================================================
# 筹码分布 Skill 定义
# ============================================================================

CHIP_DISTRIBUTION_SKILLS = [
    {
        "name": "get-chip-distribution",
        "description": "获取股票筹码分布数据，分析获利比例、平均成本和筹码集中度（AkShare优先，Tushare备用）",
        "version": "1.0.0",
        "author": "TradingAgents-CN",
        "category": "market",
        "tags": ["筹码分布", "A股", "技术分析", "持仓成本"],
        "icon": "📊",
        "color": "#e74c3c",
        "when_to_use": (
            "当用户需要了解股票筹码分布、持仓成本结构、获利比例、套牢盘分布时使用此工具。"
            "分析市场博弈格局、主力成本、支撑压力位时调用。"
            "判断抛压轻重、趋势稳定性时非常有用。"
        ),
        "parameters": [
            {"name": "ticker", "type": "string", "description": "股票代码（如 000001 或 000001.SZ）", "required": True},
            {"name": "trade_date", "type": "string", "description": "交易日期，格式 YYYY-MM-DD", "required": True},
        ],
        "returns": {"type": "string", "description": "筹码分布分析报告，含获利比例、平均成本、集中度等"},
        "implementation": {
            "type": "python",
            "module": "core.tools.implementations.market.chip_distribution_tools",
            "function": "get_chip_distribution",
            "is_async": False,
        },
        "instructions": (
            "# 筹码分布分析\n\n"
            "调用此 Skill 获取A股股票的筹码分布数据。\n\n"
            "## 关键指标\n"
            "- **获利比例**: 当前价格下浮盈筹码占全部筹码的百分比\n"
            "- **平均成本**: 全市场持仓者的加权平均成本\n"
            "- **90%筹码区间**: 90%持仓者的成本分布范围\n"
            "- **70%筹码区间**: 70%持仓者的成本分布范围\n"
            "- **筹码集中度**: 集中度越低说明筹码越集中（趋势越稳定）\n\n"
            "## 分析要点\n"
            "- 获利比例高 → 抛压大，需注意压力\n"
            "- 获利比例低 → 下方支撑强，反弹动力足\n"
            "- 平均成本高于当前价 → 大多数人套牢\n"
            "- 筹码集中 → 主力控盘，趋势性强\n\n"
            "## 示例\n"
            "- 查询平安银行筹码: ticker=000001, trade_date=2024-01-05\n"
            "- 查询茅台筹码: ticker=600519, trade_date=2024-01-05\n"
        ),
        "enabled": True,
        "fc_enabled": True,
        "is_builtin": True,
    },
    {
        "name": "get-chip-distribution-akshare",
        "description": "通过 AkShare 东方财富接口获取A股股票筹码分布数据（免费数据源）",
        "version": "1.0.0",
        "author": "TradingAgents-CN",
        "category": "market",
        "tags": ["筹码分布", "AkShare", "东方财富", "免费"],
        "icon": "📊",
        "color": "#27ae60",
        "when_to_use": "当需要使用AkShare免费数据源获取A股筹码分布数据时使用。优先使用统一接口 get-chip-distribution。",
        "parameters": [
            {"name": "ticker", "type": "string", "description": "股票代码（如 000001 或 000001.SZ）", "required": True},
            {"name": "trade_date", "type": "string", "description": "交易日期，格式 YYYY-MM-DD", "required": True},
        ],
        "returns": {"type": "string", "description": "筹码分布数据（JSON格式）"},
        "implementation": {
            "type": "python",
            "module": "core.tools.implementations.market.chip_distribution_tools",
            "function": "get_chip_distribution_akshare_tool",
            "is_async": False,
        },
        "enabled": True,
        "fc_enabled": True,
        "is_builtin": True,
    },
    {
        "name": "get-chip-distribution-tushare",
        "description": "通过 Tushare 官方API获取A股股票筹码分布数据（需要5000积分权限）",
        "version": "1.0.0",
        "author": "TradingAgents-CN",
        "category": "market",
        "tags": ["筹码分布", "Tushare", "官方API", "专业版"],
        "icon": "📊",
        "color": "#2980b9",
        "when_to_use": "当AkShare数据不可用时，使用Tushare官方API获取更权威的筹码分布数据（需要5000积分）。",
        "parameters": [
            {"name": "ticker", "type": "string", "description": "股票代码（如 000001 或 000001.SZ）", "required": True},
            {"name": "trade_date", "type": "string", "description": "交易日期，格式 YYYY-MM-DD", "required": True},
        ],
        "returns": {"type": "string", "description": "筹码分布数据（JSON格式），含获利比例、加权均价、各百分位成本"},
        "implementation": {
            "type": "python",
            "module": "core.tools.implementations.market.chip_distribution_tools",
            "function": "get_chip_distribution_tushare_tool",
            "is_async": False,
        },
        "enabled": True,
        "fc_enabled": True,
        "is_builtin": True,
    },
]


# ============================================================================
# 写入逻辑
# ============================================================================

async def seed_skills(dry_run: bool = False, overwrite: bool = False):
    """将筹码分布 Skill 写入数据库并注册到 ToolRegistry"""
    from datetime import datetime

    if dry_run:
        logger.info("🔍 [DRY-RUN] 仅打印，不写入数据库\n")
        for skill in CHIP_DISTRIBUTION_SKILLS:
            logger.info(f"  📦 {skill['name']}")
            logger.info(f"     {skill['description']}")
        logger.info(f"\n共 {len(CHIP_DISTRIBUTION_SKILLS)} 个筹码分布 Skill")
        return

    # 连接数据库
    from app.core.database import init_database, get_mongo_db
    await init_database()
    db = get_mongo_db()
    collection = db.skills

    # 加载 ToolRegistry
    from core.skills.models import SkillMetadata
    from core.skills.executor import SkillExecutor
    from core.tools.registry import get_tool_registry
    registry = get_tool_registry()

    created = 0
    skipped = 0
    updated = 0

    for skill_data in CHIP_DISTRIBUTION_SKILLS:
        name = skill_data["name"]
        existing = await collection.find_one({"name": name})

        if existing and not overwrite:
            logger.info(f"  ⏭️  跳过已存在: {name}")
            skipped += 1
            continue

        now = datetime.utcnow().isoformat()
        doc = {**skill_data, "updated_at": now}

        if existing:
            await collection.update_one({"name": name}, {"$set": doc})
            logger.info(f"  🔄 已更新: {name}")
            updated += 1
        else:
            doc["created_at"] = now
            await collection.insert_one(doc)
            logger.info(f"  ✅ 已创建: {name}")
            created += 1

        # 注册到 ToolRegistry
        doc.pop("_id", None)
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
                logger.info(f"     ↳ 注册到 ToolRegistry: tool_id={tool_id}")
            except Exception as e:
                logger.warning(f"  ⚠️  注册失败: {name} — {e}")

    logger.info(f"\n📊 结果: 创建 {created} 个, 更新 {updated} 个, 跳过 {skipped} 个")

    # 验证
    logger.info("\n🔍 ToolRegistry 验证:")
    for skill_data in CHIP_DISTRIBUTION_SKILLS:
        tool_id = skill_data["name"].replace("-", "_")
        has = registry.has_tool(tool_id)
        func = registry.get_function(tool_id) is not None
        marker = "✅" if (has and func) else "❌"
        logger.info(f"  {marker} {tool_id}: metadata={has}, function={func}")


def main():
    parser = argparse.ArgumentParser(description="写入筹码分布 Skill 到数据库")
    parser.add_argument("--dry-run", action="store_true", help="仅打印，不写入")
    parser.add_argument("--overwrite", action="store_true", help="覆盖已有记录")
    args = parser.parse_args()

    logger.info("🚀 筹码分布 Skill 初始化\n")
    asyncio.run(seed_skills(dry_run=args.dry_run, overwrite=args.overwrite))
    logger.info("\n✅ 完成！")


if __name__ == "__main__":
    main()

