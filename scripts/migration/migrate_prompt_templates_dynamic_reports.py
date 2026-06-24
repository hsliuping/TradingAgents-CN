"""
数据库提示词模板迁移：dynamic-stage-reports-v1

功能：
1. 将 8 个 v2 agent 的提示词模板从旧字段迁移到动态聚合变量
2. 归档旧模板，创建新模板
3. 记录迁移历史，支持回退

迁移范围：
- bull_researcher_v2 / bear_researcher_v2：新增 {analyst_reports}
- research_manager_v2：新增 {analyst_reports}、{research_reports}
- risky_analyst_v2 / safe_analyst_v2 / neutral_analyst_v2：新增 {analyst_reports}、{research_reports}
- risk_manager_v2：新增 {research_reports}、{risk_reports}
- trader_v2：新增 {analyst_reports}、{research_reports}、{risk_reports}

每个 agent 覆盖 3 种 preference：aggressive / neutral / conservative
共 24 个模板

使用方法：
    python scripts/migration/migrate_prompt_templates_dynamic_reports.py [--dry-run] [--rollback]

参数：
    --dry-run：仅预览，不执行实际迁移
    --rollback：回退迁移，恢复旧模板
"""

import asyncio
import sys
import argparse
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any
from copy import deepcopy

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from app.core.database import init_database, get_mongo_db
from motor.motor_asyncio import AsyncIOMotorDatabase


MIGRATION_ID = "dynamic-stage-reports-v1"

# 迁移配置：每个 agent 需要新增的聚合变量
AGENT_VARIABLE_MAPPING = {
    "bull_researcher_v2": ["analyst_reports"],
    "bear_researcher_v2": ["analyst_reports"],
    "research_manager_v2": ["analyst_reports", "research_reports"],
    "risky_analyst_v2": ["analyst_reports", "research_reports"],
    "safe_analyst_v2": ["analyst_reports", "research_reports"],
    "neutral_analyst_v2": ["analyst_reports", "research_reports"],
    "risk_manager_v2": ["research_reports", "risk_reports"],
    "trader_v2": ["analyst_reports", "research_reports", "risk_reports"],
}

# 需要替换的旧字段 → 聚合变量映射
OLD_FIELD_REPLACEMENTS = {
    # analyst 阶段报告 → analyst_reports
    "market_research_report": "analyst_reports",
    "market_report": "analyst_reports",
    "fundamentals_report": "analyst_reports",
    "fundamentals_analysis": "analyst_reports",
    "news_report": "analyst_reports",
    "sentiment_report": "analyst_reports",
    "social_report": "analyst_reports",
    "sector_report": "analyst_reports",
    "index_report": "analyst_reports",
    "chip_report": "analyst_reports",
    # research 阶段报告 → research_reports
    "bull_report": "research_reports",
    "bear_report": "research_reports",
    "research_report": "research_reports",
    "investment_plan": "research_reports",
    # risk 阶段报告 → risk_reports
    "risky_opinion": "risk_reports",
    "safe_opinion": "risk_reports",
    "neutral_opinion": "risk_reports",
    "risk_assessment": "risk_reports",
}


def generate_new_user_prompt(old_prompt: str, new_vars: List[str]) -> str:
    """
    生成新的 user_prompt，替换旧字段为聚合变量

    Args:
        old_prompt: 原始 user_prompt
        new_vars: 需要新增的聚合变量列表

    Returns:
        新的 user_prompt
    """
    # 先替换旧字段
    new_prompt = old_prompt
    for old_field, new_var in OLD_FIELD_REPLACEMENTS.items():
        # 替换 {old_field} 为 {new_var}
        # 注意：同一个聚合变量可能对应多个旧字段，需要全部替换
        new_prompt = new_prompt.replace(f"{{{old_field}}}", f"{{{new_var}}}")

    # 构建聚合变量描述
    var_descriptions = {
        "analyst_reports": "分析师阶段报告汇总（包含市场、基本面、新闻、情绪、板块、指数、筹码等所有分析师输出）",
        "research_reports": "研究阶段报告汇总（包含多空辩论、投资计划等研究输出）",
        "risk_reports": "风险阶段报告汇总（包含风险三方评估、风险结论等风险输出）",
    }

    # 在 user_prompt 开头添加聚合变量说明
    var_intro_lines = ["\n📊 **动态聚合报告**："]
    for var in new_vars:
        if var in var_descriptions:
            var_intro_lines.append(f"- `{var}`：{var_descriptions[var]}")

    var_intro = "\n".join(var_intro_lines) + "\n\n"

    # 检查是否已经包含聚合变量说明（避免重复添加）
    if "动态聚合报告" not in new_prompt and any(f"{{{var}}}" in new_prompt for var in new_vars):
        new_prompt = var_intro + new_prompt

    return new_prompt


async def migrate_templates(db: AsyncIOMotorDatabase, dry_run: bool = False) -> Dict[str, Any]:
    """
    执行模板迁移

    Args:
        db: MongoDB 数据库实例
        dry_run: 是否仅预览

    Returns:
        迁移统计结果
    """
    collection = db.prompt_templates
    history_collection = db.template_history

    stats = {
        "total_found": 0,
        "archived": 0,
        "created": 0,
        "history_records": 0,
        "errors": [],
        "details": [],
    }

    print("\n" + "=" * 80)
    print(f"数据库提示词模板迁移：{MIGRATION_ID}")
    print("=" * 80)

    # 遍历每个 agent
    for agent_name, new_vars in AGENT_VARIABLE_MAPPING.items():
        print(f"\n📋 处理 Agent: {agent_name}")
        print(f"   新增聚合变量: {new_vars}")

        # 查询该 agent 的所有 active 模板
        templates = await collection.find({
            "agent_name": agent_name,
            "status": "active",
        }).to_list(length=None)

        stats["total_found"] += len(templates)
        print(f"   找到 {len(templates)} 个 active 模板")

        for template in templates:
            preference = template.get("preference_type", "unknown")
            template_id = str(template.get("_id"))
            template_name = template.get("template_name", "")

            print(f"\n   📄 处理模板: {template_name} ({preference})")

            # 获取原始 user_prompt
            content = template.get("content", {})
            old_user_prompt = content.get("user_prompt", "")

            if not old_user_prompt:
                print(f"      ⚠️ 模板无 user_prompt，跳过")
                continue

            # 生成新的 user_prompt
            new_user_prompt = generate_new_user_prompt(old_user_prompt, new_vars)

            # 检查是否有变化
            if new_user_prompt == old_user_prompt:
                print(f"      ℹ️ 模板无需修改（已使用聚合变量或无旧字段）")
                continue

            if dry_run:
                print(f"      [DRY-RUN] 预览修改:")
                print(f"         旧: {old_user_prompt[:100]}...")
                print(f"         新: {new_user_prompt[:100]}...")
                stats["details"].append({
                    "agent": agent_name,
                    "preference": preference,
                    "template_id": template_id,
                    "action": "preview",
                })
                continue

            try:
                # 1. 归档旧模板
                archive_result = await collection.update_one(
                    {"_id": template["_id"]},
                    {
                        "$set": {
                            "status": "archived",
                            "archived_by_migration": MIGRATION_ID,
                            "archived_at": datetime.utcnow().isoformat(),
                            "updated_at": datetime.utcnow().isoformat(),
                        }
                    }
                )
                stats["archived"] += archive_result.modified_count

                # 2. 创建新模板
                new_template = deepcopy(template)
                new_template["_id"] = None  # 移除 _id，让 MongoDB 生成新 ID
                new_template["content"]["user_prompt"] = new_user_prompt
                new_template["status"] = "active"
                new_template["migration_id"] = MIGRATION_ID
                new_template["base_template_id"] = template_id
                new_template["base_version"] = template.get("version", 1)
                new_template["created_at"] = datetime.utcnow().isoformat()
                new_template["updated_at"] = datetime.utcnow().isoformat()
                new_template["version"] = template.get("version", 1) + 1
                new_template["change_description"] = f"迁移到动态聚合变量（{MIGRATION_ID}）"

                # 移除归档标记
                new_template.pop("archived_by_migration", None)
                new_template.pop("archived_at", None)

                insert_result = await collection.insert_one(new_template)
                stats["created"] += 1
                new_template_id = str(insert_result.inserted_id)

                # 3. 记录迁移历史
                history_record = {
                    "migration_id": MIGRATION_ID,
                    "agent_name": agent_name,
                    "preference_type": preference,
                    "old_template_id": template_id,
                    "new_template_id": new_template_id,
                    "old_status": "active",
                    "new_status": "active",
                    "action": "migrate",
                    "timestamp": datetime.utcnow().isoformat(),
                    "details": {
                        "old_user_prompt_preview": old_user_prompt[:200],
                        "new_user_prompt_preview": new_user_prompt[:200],
                        "new_vars": new_vars,
                    }
                }
                await history_collection.insert_one(history_record)
                stats["history_records"] += 1

                print(f"      ✅ 归档旧模板: {template_id}")
                print(f"      ✅ 创建新模板: {new_template_id}")

                stats["details"].append({
                    "agent": agent_name,
                    "preference": preference,
                    "old_template_id": template_id,
                    "new_template_id": new_template_id,
                    "action": "migrated",
                })

            except Exception as e:
                error_msg = f"迁移失败 ({agent_name}/{preference}): {e}"
                stats["errors"].append(error_msg)
                print(f"      ❌ {error_msg}")

    return stats


async def rollback_migration(db: AsyncIOMotorDatabase) -> Dict[str, Any]:
    """
    回退迁移：恢复旧模板

    Args:
        db: MongoDB 数据库实例

    Returns:
        回退统计结果
    """
    collection = db.prompt_templates
    history_collection = db.template_history

    stats = {
        "restored": 0,
        "archived_new": 0,
        "deleted_history": 0,
        "errors": [],
    }

    print("\n" + "=" * 80)
    print(f"回退迁移：{MIGRATION_ID}")
    print("=" * 80)

    # 1. 归档新模板（migration_id = MIGRATION_ID）
    new_templates = await collection.find({
        "migration_id": MIGRATION_ID,
        "status": "active",
    }).to_list(length=None)

    print(f"\n找到 {len(new_templates)} 个新模板需要归档")

    for template in new_templates:
        try:
            await collection.update_one(
                {"_id": template["_id"]},
                {
                    "$set": {
                        "status": "archived",
                        "rollback_at": datetime.utcnow().isoformat(),
                        "updated_at": datetime.utcnow().isoformat(),
                    }
                }
            )
            stats["archived_new"] += 1
            print(f"   ✅ 归档新模板: {template.get('template_name', '')}")
        except Exception as e:
            stats["errors"].append(f"归档新模板失败: {e}")
            print(f"   ❌ 归档失败: {e}")

    # 2. 恢复旧模板（archived_by_migration = MIGRATION_ID）
    old_templates = await collection.find({
        "archived_by_migration": MIGRATION_ID,
        "status": "archived",
    }).to_list(length=None)

    print(f"\n找到 {len(old_templates)} 个旧模板需要恢复")

    for template in old_templates:
        try:
            await collection.update_one(
                {"_id": template["_id"]},
                {
                    "$set": {
                        "status": "active",
                        "restored_at": datetime.utcnow().isoformat(),
                        "updated_at": datetime.utcnow().isoformat(),
                    },
                    "$unset": {
                        "archived_by_migration": "",
                        "archived_at": "",
                    }
                }
            )
            stats["restored"] += 1
            print(f"   ✅ 恢复旧模板: {template.get('template_name', '')}")
        except Exception as e:
            stats["errors"].append(f"恢复旧模板失败: {e}")
            print(f"   ❌ 恢复失败: {e}")

    # 3. 删除迁移历史记录
    try:
        result = await history_collection.delete_many({"migration_id": MIGRATION_ID})
        stats["deleted_history"] = result.deleted_count
        print(f"\n✅ 删除 {stats['deleted_history']} 条迁移历史记录")
    except Exception as e:
        stats["errors"].append(f"删除历史记录失败: {e}")
        print(f"   ❌ 删除历史记录失败: {e}")

    return stats


async def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="数据库提示词模板迁移")
    parser.add_argument("--dry-run", action="store_true", help="仅预览，不执行实际迁移")
    parser.add_argument("--rollback", action="store_true", help="回退迁移")
    args = parser.parse_args()

    print("=" * 80)
    print("TradingAgentsCN 提示词模板迁移工具")
    print("=" * 80)

    # 初始化数据库连接
    await init_database()
    db = get_mongo_db()

    if args.rollback:
        stats = await rollback_migration(db)
        print("\n" + "=" * 80)
        print("回退完成")
        print("=" * 80)
        print(f"归档新模板: {stats['archived_new']}")
        print(f"恢复旧模板: {stats['restored']}")
        print(f"删除历史记录: {stats['deleted_history']}")
        if stats["errors"]:
            print(f"\n❌ 错误: {len(stats['errors'])}")
            for err in stats["errors"]:
                print(f"   - {err}")
    else:
        stats = await migrate_templates(db, dry_run=args.dry_run)
        print("\n" + "=" * 80)
        if args.dry_run:
            print("预览完成（DRY-RUN）")
        else:
            print("迁移完成")
        print("=" * 80)
        print(f"找到模板: {stats['total_found']}")
        print(f"归档旧模板: {stats['archived']}")
        print(f"创建新模板: {stats['created']}")
        print(f"历史记录: {stats['history_records']}")
        if stats["errors"]:
            print(f"\n❌ 错误: {len(stats['errors'])}")
            for err in stats["errors"]:
                print(f"   - {err}")

        if args.dry_run:
            print("\n💡 提示: 使用 --dry-run=false 执行实际迁移")


if __name__ == "__main__":
    asyncio.run(main())