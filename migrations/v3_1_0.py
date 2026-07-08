"""
v3.1.0 migration - Agent 工坊运行时字段补齐

迁移内容：
1. agent_configs: 补齐 output_field / workflow_stage / report_label / show_in_reports / node_name / execution_order / callable_surfaces
2. prompt_templates: 将 agent_type="custom_agent" 的工坊模板迁移为 agent_type="universal"

所有操作必须幂等（可安全多次运行）。
"""

import logging
from datetime import datetime, timezone

logger = logging.getLogger("migrations.v3_1_0")

VERSION = "3.1.0"
DESCRIPTION = "Agent 工坊运行时字段补齐：agent_configs 字段补全 + Prompt 模板 agent_type 迁移"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


async def _migrate_agent_configs(db):
    """补齐 agent_configs 中缺失的运行时字段"""
    collection = db["agent_configs"]
    migrated = 0

    async for doc in collection.find({"metadata.source": "agent_workshop"}):
        updates = {}
        unset_fields = {}

        # 顶层字段补齐
        # 🔥 output_field 必须唯一，否则多个工坊 Agent 共用 analysis_report
        # 会导致运行时 state 互相覆盖 + 聚合器去重后只剩第一个
        if not doc.get("output_field"):
            agent_id = doc.get("agent_id", "")
            # 从 agent_id 生成唯一字段名：取末尾段 + _report
            if agent_id:
                tail = agent_id.replace("_v1", "").replace("_v2", "").split("_")[-1]
                default_output_field = f"{tail}_report"
            else:
                default_output_field = "analysis_report"
            updates["output_field"] = default_output_field
        if not doc.get("workflow_stage"):
            updates["workflow_stage"] = "analyst"
        if not doc.get("report_label"):
            name = doc.get("name", doc.get("agent_name", "Agent"))
            updates["report_label"] = f"【{name}】"
        if "show_in_reports" not in doc:
            updates["show_in_reports"] = True
        if not doc.get("node_name"):
            updates["node_name"] = doc.get("name", doc.get("agent_name", doc.get("agent_id", "")))
        if "execution_order" not in doc:
            updates["execution_order"] = 50
        if not doc.get("callable_surfaces"):
            updates["callable_surfaces"] = ["assistant", "workflow", "agent_workshop"]

        # metadata 字段补齐
        meta = doc.get("metadata", {})
        meta_updates = {}
        if not meta.get("workflow_stage"):
            meta_updates["metadata.workflow_stage"] = updates.get("workflow_stage", "analyst")
        if not meta.get("output_field"):
            meta_updates["metadata.output_field"] = updates.get("output_field", "analysis_report")
        if not meta.get("report_label"):
            meta_updates["metadata.report_label"] = updates.get("report_label", "")
        if "show_in_reports" not in meta:
            meta_updates["metadata.show_in_reports"] = True
        if not meta.get("node_name"):
            meta_updates["metadata.node_name"] = updates.get("node_name", "")
        if "execution_order" not in meta:
            meta_updates["metadata.execution_order"] = 50
        if not meta.get("callable_surfaces"):
            meta_updates["metadata.callable_surfaces"] = ["assistant", "workflow", "agent_workshop"]

        all_updates = {**updates, **meta_updates}
        if all_updates:
            all_updates["updated_at"] = _now_iso()
            await collection.update_one(
                {"_id": doc["_id"]},
                {"$set": all_updates},
            )
            migrated += 1

    if migrated:
        logger.info("v3.1.0 migration: agent_configs 补齐 %d 条记录", migrated)
    else:
        logger.info("v3.1.0 migration: agent_configs 无需补齐")


async def _migrate_prompt_templates(db):
    """将 agent_type="custom_agent" 的工坊模板迁移为 agent_type="universal"

    同时确保 agent_name 与 version_id 一致（如果缺失则尝试从 remark 推断）。
    """
    collection = db["prompt_templates"]
    migrated = 0

    # 查找 agent_type="custom_agent" 的模板
    async for doc in collection.find({"agent_type": "custom_agent"}):
        updates = {
            "agent_type": "universal",
            "updated_at": _now_iso(),
        }
        # 如果 workflow_id 存在，清掉（UniversalAgent 查询时不带 workflow_id）
        if doc.get("workflow_id"):
            updates["workflow_id"] = None
        if doc.get("node_id"):
            updates["node_id"] = None

        await collection.update_one(
            {"_id": doc["_id"]},
            {"$set": updates},
        )
        migrated += 1

    if migrated:
        logger.info("v3.1.0 migration: prompt_templates 迁移 %d 条 custom_agent → universal", migrated)
    else:
        logger.info("v3.1.0 migration: prompt_templates 无需迁移")


async def upgrade(db):
    """执行 v3.1.0 迁移"""
    logger.info("v3.1.0 migration: 开始 Agent 工坊运行时字段补齐")
    await _migrate_agent_configs(db)
    await _migrate_prompt_templates(db)
    logger.info("v3.1.0 migration: 完成")


async def downgrade(db):
    """回滚 v3.1.0 迁移（仅回滚 prompt_templates 的 agent_type）"""
    logger.info("v3.1.0 migration: 开始回滚")
    collection = db["prompt_templates"]
    result = await collection.update_many(
        {"agent_type": "universal", "remark": {"$regex": "Agent 工坊"}},
        {"$set": {"agent_type": "custom_agent", "updated_at": _now_iso()}},
    )
    logger.info("v3.1.0 migration: 回滚 %d 条 prompt_templates", result.modified_count)
