"""
定时任务管理类工具

提供定时分析配置的查询、创建和启用/禁用功能。
用户身份通过 core.tools.context 获取。
"""

import logging
from typing import Annotated, Optional

from langchain_core.tools import tool

from core.tools.base import register_tool
from core.tools.context import require_current_user_id

logger = logging.getLogger(__name__)


@tool
@register_tool(
    tool_id="list_scheduled_configs",
    name="查看定时分析配置",
    description="列出用户已创建的所有定时分析配置，显示名称、CRON 时间段、启用/禁用状态。注意：定时分析配置不同于股票关注列表（股票关注列表）和股票关注列表分组；前者决定自动分析任务，后者只是股票池或组织方式。",
    category="assistant_ops",
    is_online=True,
    auto_register=True,
    timeout_tier="light",
    data_source_handling="local_only",
    capability_tags=["schedule", "scheduled_analysis", "config", "list", "query", "assistant_ops", "cron", "scheduled_task", "task_config", "automation_config", "schedule_query"],
    tool_role_hint="primary",
    output_shape="text",
    preferred_for=["查看定时配置", "定时任务列表", "计划任务查询", "自动分析配置查看"],
    when_to_use="当用户想查看自己已创建的定时分析配置列表、了解有哪些自动分析计划时使用。",
    returns="返回文本格式的定时分析配置列表，每条含配置ID、名称、启用状态和 CRON 时间段摘要。",
)
async def list_scheduled_configs() -> str:
    """列出当前用户的所有定时分析配置摘要。"""
    from app.core.database import get_mongo_db

    user_id = require_current_user_id()
    db = get_mongo_db()

    cursor = db.scheduled_analysis_configs.find({"user_id": user_id}).sort("created_at", -1)

    configs = []
    async for doc in cursor:
        config_id = str(doc["_id"])
        name = doc.get("name", "未命名")
        enabled = "✅ 启用" if doc.get("enabled") else "⏸️ 禁用"
        slots = doc.get("time_slots", [])
        slot_summary = ", ".join(
            f"{s.get('name', '?')}({s.get('cron_expression', '?')})"
            for s in slots[:3]
        )
        if len(slots) > 3:
            slot_summary += f" +{len(slots) - 3}个"
        configs.append(f"  [{config_id[:8]}] {name} | {enabled} | {slot_summary}")

    if not configs:
        return "📋 暂无定时分析配置。你可以让我帮你创建一个。"
    return f"📋 共 {len(configs)} 个定时分析配置：\n" + "\n".join(configs)


@tool
@register_tool(
    tool_id="create_scheduled_analysis",
    name="创建定时分析",
    description="创建一个定时自动分析计划：指定名称、CRON 时间表达式和要分析的股票关注列表分组，系统将按计划自动触发分析。注意：只有被配置到这里的分组才会进入定时分析。",
    category="assistant_ops",
    is_online=True,
    auto_register=True,
    timeout_tier="light",
    data_source_handling="local_only",
    capability_tags=["schedule", "scheduled_analysis", "create", "config", "cron", "assistant_ops", "automation", "scheduled_task", "task_creation", "analysis_plan", "cron_expression"],
    tool_role_hint="primary",
    output_shape="text",
    preferred_for=["创建定时分析", "设置自动分析", "定时任务创建", "CRON计划配置"],
    when_to_use="当用户想新建一个定时自动分析计划、指定 CRON 时间和股票关注列表分组时使用。",
    returns="返回文本消息，包含新建配置的名称、配置ID、时间段、分析深度和启用状态。",
)
async def create_scheduled_analysis(
    name: Annotated[str, "配置名称，如「每日早盘分析」"],
    cron_expression: Annotated[str, "CRON表达式，如 0 9 * * 1-5 表示工作日早9点"],
    group_ids: Annotated[str, "股票关注列表分组ID列表，逗号分隔"],
    slot_name: Annotated[str, "时间段名称，如「开盘前」"] = "默认时段",
    depth: Annotated[int, "分析深度 1-5，默认3"] = 3,
) -> str:
    """创建一个新的定时分析配置，包含一个时间段。"""
    from app.core.database import get_mongo_db
    from app.utils.timezone import now_tz

    user_id = require_current_user_id()
    db = get_mongo_db()

    # 检查名称重复
    existing = await db.scheduled_analysis_configs.find_one({"user_id": user_id, "name": name})
    if existing:
        return f"❌ 已存在同名配置「{name}」，请使用其他名称。"

    gid_list = [g.strip() for g in group_ids.split(",") if g.strip()]
    if not gid_list:
        return "❌ 请提供至少一个股票关注列表分组ID。可以先用「查看股票关注列表分组」获取分组列表。"

    config_doc = {
        "user_id": user_id,
        "name": name,
        "description": "",
        "enabled": True,
        "time_slots": [{
            "name": slot_name,
            "cron_expression": cron_expression,
            "enabled": True,
            "group_ids": gid_list,
            "analysis_depth": depth,
        }],
        "default_group_ids": gid_list,
        "default_analysis_depth": depth,
        "default_quick_analysis_model": "",
        "default_deep_analysis_model": "",
        "default_prompt_template_id": None,
        "notify_on_complete": True,
        "notify_on_error": True,
        "send_email": False,
        "created_at": now_tz(),
        "updated_at": now_tz(),
    }

    result = await db.scheduled_analysis_configs.insert_one(config_doc)
    config_id = str(result.inserted_id)

    # 注册到调度器
    try:
        from app.pro.routers.scheduled_analysis import _register_scheduled_tasks
        config_doc["id"] = config_id
        await _register_scheduled_tasks(config_doc)
    except Exception as e:
        logger.warning(f"注册调度任务失败（配置已保存）: {e}")

    return (
        f"✅ 定时分析配置已创建\n"
        f"- 名称: {name}\n"
        f"- 配置ID: {config_id}\n"
        f"- 时间段: {slot_name}（{cron_expression}）\n"
        f"- 分析深度: {depth}\n"
        f"- 状态: 已启用\n"
        f"配置将按计划自动执行分析。"
    )


@tool
@register_tool(
    tool_id="toggle_scheduled_config",
    name="启用或禁用定时分析",
    description="启用或禁用已有的定时分析配置（不删除配置本身）。返回操作结果，并同步注册或取消调度器任务。",
    category="assistant_ops",
    is_online=True,
    auto_register=True,
    timeout_tier="light",
    data_source_handling="local_only",
    capability_tags=["schedule", "scheduled_analysis", "toggle", "enable", "disable", "config", "assistant_ops", "scheduled_task", "automation_control", "task_status", "schedule_management"],
    tool_role_hint="primary",
    output_shape="text",
    preferred_for=["启用定时分析", "禁用定时分析", "切换任务状态", "暂停自动分析"],
    when_to_use="当用户想启用或禁用一个已有的定时分析配置、暂停或恢复自动分析计划时使用。",
    returns="返回文本消息，提示配置的启用/禁用操作结果。",
)
async def toggle_scheduled_config(
    config_id: Annotated[str, "定时分析配置ID"],
    enabled: Annotated[bool, "True=启用, False=禁用"],
) -> str:
    """启用或禁用指定的定时分析配置，同时注册或取消调度器任务。"""
    from bson import ObjectId
    from app.core.database import get_mongo_db
    from app.utils.timezone import now_tz

    user_id = require_current_user_id()
    db = get_mongo_db()

    try:
        oid = ObjectId(config_id)
    except Exception:
        return "❌ 无效的配置ID"

    config = await db.scheduled_analysis_configs.find_one({"_id": oid, "user_id": user_id})
    if not config:
        return f"❌ 未找到配置: {config_id}"

    if config.get("enabled") == enabled:
        status = "启用" if enabled else "禁用"
        return f"ℹ️ 配置「{config.get('name', '')}」已经是{status}状态。"

    await db.scheduled_analysis_configs.update_one(
        {"_id": oid},
        {"$set": {"enabled": enabled, "updated_at": now_tz()}},
    )

    # 更新调度器
    try:
        from app.pro.routers.scheduled_analysis import _register_scheduled_tasks, _unregister_scheduled_tasks
        if enabled:
            config["id"] = str(config.pop("_id"))
            config["enabled"] = True
            await _register_scheduled_tasks(config)
        else:
            await _unregister_scheduled_tasks(config_id)
    except Exception as e:
        logger.warning(f"调度器更新失败（数据库已更新）: {e}")

    action = "启用" if enabled else "禁用"
    return f"✅ 已{action}定时分析配置「{config.get('name', '')}」"
