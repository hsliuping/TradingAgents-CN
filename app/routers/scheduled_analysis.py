"""
定时分析配置管理 API

[PRO功能] 此模块为专业版功能，需要专业版授权
- 支持多时段定时分析配置
- 每个时段可配置不同的分组和分析参数
- 自动注册/取消注册调度任务
"""

from fastapi import APIRouter, Depends, HTTPException
from typing import List, Optional
from bson import ObjectId

from app.core.database import get_mongo_db
from app.core.response import ok, fail
from app.core.permissions import require_pro
from app.routers.auth_db import get_current_user
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime, timedelta
from app.models.scheduled_analysis import (
    ScheduledAnalysisConfig,
    ScheduledAnalysisConfigCreate,
    ScheduledAnalysisConfigUpdate,
    ScheduledAnalysisTimeSlot,
    ScheduledAnalysisHistory
)

from pydantic import BaseModel
from app.utils.timezone import now_tz
import logging

logger = logging.getLogger("app.routers.scheduled_analysis")

# 整个路由器都需要 PRO 权限
router = APIRouter(
    prefix="/api/scheduled-analysis",
    tags=["定时分析配置"],
    dependencies=[Depends(require_pro)]
)

class CronPreviewRequest(BaseModel):
    cron_expression: str

@router.post("/preview-cron")
async def preview_cron(request: CronPreviewRequest):
    """预览 CRON 表达式的下几次执行时间"""
    try:
        # 解析 CRON 表达式
        # 格式: minute hour day month day_of_week
        parts = request.cron_expression.split()
        if len(parts) != 5:
            return fail("无效的 CRON 表达式格式，应包含 5 个部分")

        minute, hour, day, month, day_of_week = parts
        
        trigger = CronTrigger(
            minute=minute,
            hour=hour,
            day=day,
            month=month,
            day_of_week=day_of_week,
            timezone=now_tz().tzinfo
        )
        
        next_runs = []
        next_time = now_tz()
        
        for _ in range(5):
            next_time = trigger.get_next_fire_time(None, next_time)
            if not next_time:
                break
            next_runs.append(next_time.strftime("%Y-%m-%d %H:%M:%S"))
            
        return ok({"next_runs": next_runs})
        
    except Exception as e:
        return fail(f"CRON 表达式解析失败: {str(e)}")


@router.get("/configs")
async def list_configs(user: dict = Depends(get_current_user)):
    """获取用户的所有定时分析配置"""
    db = get_mongo_db()
    user_id = str(user["id"])
    
    cursor = db.scheduled_analysis_configs.find({"user_id": user_id})
    configs = []
    
    async for doc in cursor:
        doc["id"] = str(doc.pop("_id"))
        configs.append(doc)
    
    return ok({"configs": configs})


@router.post("/configs")
async def create_config(
    config_data: ScheduledAnalysisConfigCreate,
    user: dict = Depends(get_current_user)
):
    """创建新的定时分析配置"""
    db = get_mongo_db()
    user_id = str(user["id"])
    
    # 检查配置名称是否已存在
    existing = await db.scheduled_analysis_configs.find_one({
        "user_id": user_id,
        "name": config_data.name
    })
    
    if existing:
        return fail("配置名称已存在")
    
    # 创建配置
    config_doc = {
        "user_id": user_id,
        "name": config_data.name,
        "description": config_data.description,
        "enabled": config_data.enabled,
        "time_slots": [slot.model_dump() for slot in config_data.time_slots],
        "default_group_ids": config_data.default_group_ids,
        "default_analysis_depth": config_data.default_analysis_depth,
        "default_quick_analysis_model": config_data.default_quick_analysis_model,
        "default_deep_analysis_model": config_data.default_deep_analysis_model,
        "default_prompt_template_id": config_data.default_prompt_template_id,
        "notify_on_complete": config_data.notify_on_complete,
        "notify_on_error": config_data.notify_on_error,
        "send_email": config_data.send_email,
        "created_at": now_tz(),
        "updated_at": now_tz(),
        "last_run_at": None
    }
    
    result = await db.scheduled_analysis_configs.insert_one(config_doc)
    config_doc["id"] = str(result.inserted_id)
    config_doc.pop("_id", None)
    
    logger.info(f"✅ 创建定时分析配置: {config_data.name} (用户: {user_id})")
    
    # 如果配置已启用，需要注册到调度器
    if config_data.enabled:
        await _register_scheduled_tasks(config_doc)
    
    return ok({"config": config_doc, "message": "配置创建成功"})


@router.get("/configs/{config_id}")
async def get_config(config_id: str, user: dict = Depends(get_current_user)):
    """获取配置详情"""
    db = get_mongo_db()
    user_id = str(user["id"])
    
    try:
        config = await db.scheduled_analysis_configs.find_one({
            "_id": ObjectId(config_id),
            "user_id": user_id
        })
    except Exception:
        return fail("无效的配置ID")
    
    if not config:
        return fail("配置不存在")
    
    config["id"] = str(config.pop("_id"))
    return ok({"config": config})


@router.put("/configs/{config_id}")
async def update_config(
    config_id: str,
    config_data: ScheduledAnalysisConfigUpdate,
    user: dict = Depends(get_current_user)
):
    """更新配置信息"""
    db = get_mongo_db()
    user_id = str(user["id"])
    
    try:
        oid = ObjectId(config_id)
    except Exception:
        return fail("无效的配置ID")
    
    # 检查配置是否存在
    config = await db.scheduled_analysis_configs.find_one({"_id": oid, "user_id": user_id})
    if not config:
        return fail("配置不存在")
    
    # 如果修改了名称，检查新名称是否已存在
    if config_data.name and config_data.name != config["name"]:
        existing = await db.scheduled_analysis_configs.find_one({
            "user_id": user_id,
            "name": config_data.name,
            "_id": {"$ne": oid}
        })
        if existing:
            return fail("配置名称已存在")
    
    # 构建更新数据
    update_data = config_data.model_dump(exclude_unset=True)
    
    # 处理 time_slots
    if config_data.time_slots is not None:
        update_data["time_slots"] = [slot.model_dump() for slot in config_data.time_slots]
    
    update_data["updated_at"] = now_tz()
    
    await db.scheduled_analysis_configs.update_one(
        {"_id": oid},
        {"$set": update_data}
    )
    
    # 获取更新后的配置
    updated_config = await db.scheduled_analysis_configs.find_one({"_id": oid})
    updated_config["id"] = str(updated_config.pop("_id"))
    
    logger.info(f"✅ 更新定时分析配置: {config_id} (用户: {user_id})")
    
    # 如果启用状态改变，需要更新调度器
    if config_data.enabled is not None:
        if config_data.enabled:
            await _register_scheduled_tasks(updated_config)
        else:
            await _unregister_scheduled_tasks(config_id)
    elif updated_config.get("enabled"):
        # 如果配置已启用，重新注册任务
        await _unregister_scheduled_tasks(config_id)
        await _register_scheduled_tasks(updated_config)
    
    return ok({"message": "配置更新成功"})


@router.delete("/configs/{config_id}")
async def delete_config(config_id: str, user: dict = Depends(get_current_user)):
    """删除配置"""
    db = get_mongo_db()
    user_id = str(user["id"])

    try:
        oid = ObjectId(config_id)
    except Exception:
        return fail("无效的配置ID")

    # 检查配置是否存在
    config = await db.scheduled_analysis_configs.find_one({"_id": oid, "user_id": user_id})
    if not config:
        return fail("配置不存在")

    # 如果配置已启用，先取消注册任务
    if config.get("enabled"):
        await _unregister_scheduled_tasks(config_id)

    result = await db.scheduled_analysis_configs.delete_one({"_id": oid})

    logger.info(f"✅ 删除定时分析配置: {config_id} (用户: {user_id})")
    return ok({"message": "配置删除成功"})


@router.post("/configs/{config_id}/enable")
async def enable_config(config_id: str, user: dict = Depends(get_current_user)):
    """启用配置"""
    db = get_mongo_db()
    user_id = str(user["id"])

    try:
        oid = ObjectId(config_id)
    except Exception:
        return fail("无效的配置ID")

    config = await db.scheduled_analysis_configs.find_one({"_id": oid, "user_id": user_id})
    if not config:
        return fail("配置不存在")

    await db.scheduled_analysis_configs.update_one(
        {"_id": oid},
        {"$set": {"enabled": True, "updated_at": now_tz()}}
    )

    # 注册调度任务
    config["id"] = str(config.pop("_id"))
    config["enabled"] = True
    await _register_scheduled_tasks(config)

    logger.info(f"✅ 启用定时分析配置: {config_id} (用户: {user_id})")
    return ok({"message": "配置已启用"})


@router.post("/configs/{config_id}/disable")
async def disable_config(config_id: str, user: dict = Depends(get_current_user)):
    """禁用配置"""
    db = get_mongo_db()
    user_id = str(user["id"])

    try:
        oid = ObjectId(config_id)
    except Exception:
        return fail("无效的配置ID")

    config = await db.scheduled_analysis_configs.find_one({"_id": oid, "user_id": user_id})
    if not config:
        return fail("配置不存在")

    await db.scheduled_analysis_configs.update_one(
        {"_id": oid},
        {"$set": {"enabled": False, "updated_at": now_tz()}}
    )

    # 取消注册调度任务
    await _unregister_scheduled_tasks(config_id)

    logger.info(f"✅ 禁用定时分析配置: {config_id} (用户: {user_id})")
    return ok({"message": "配置已禁用"})


@router.post("/configs/{config_id}/test")
async def test_config(config_id: str, user: dict = Depends(get_current_user)):
    """
    测试执行定时分析配置

    立即执行配置中的第一个启用的时间段，用于测试配置是否正确
    """
    db = get_mongo_db()
    user_id = str(user["id"])

    try:
        oid = ObjectId(config_id)
    except Exception:
        return fail("无效的配置ID")

    config = await db.scheduled_analysis_configs.find_one({"_id": oid, "user_id": user_id})
    if not config:
        return fail("配置不存在")

    # 查找第一个启用的时间段
    time_slots = config.get("time_slots", [])
    enabled_slot_index = None

    for idx, slot in enumerate(time_slots):
        if slot.get("enabled", True):
            enabled_slot_index = idx
            break

    if enabled_slot_index is None:
        return fail("没有启用的时间段可供测试")

    logger.info(f"🧪 测试执行定时分析配置: {config_id}, 时间段索引: {enabled_slot_index} (用户: {user_id})")

    # 异步执行测试任务（不阻塞响应）
    import asyncio
    from app.worker.watchlist_analysis_task import run_scheduled_analysis_slot

    asyncio.create_task(
        run_scheduled_analysis_slot(
            config_id=config_id,
            user_id=user_id,
            slot_index=enabled_slot_index
        )
    )

    slot_name = time_slots[enabled_slot_index].get("name", f"时间段 {enabled_slot_index + 1}")

    return ok({
        "message": f"测试任务已启动，正在执行时间段: {slot_name}",
        "slot_index": enabled_slot_index,
        "slot_name": slot_name
    })


@router.get("/configs/{config_id}/history")
async def get_config_history(
    config_id: str,
    limit: int = 20,
    user: dict = Depends(get_current_user)
):
    """获取配置的执行历史"""
    db = get_mongo_db()
    user_id = str(user["id"])
    
    try:
        oid = ObjectId(config_id)
    except Exception:
        return fail("无效的配置ID")
    
    # 验证配置归属
    config = await db.scheduled_analysis_configs.find_one({
        "_id": oid,
        "user_id": user_id
    })
    
    if not config:
        return fail("配置不存在")
        
    cursor = db.scheduled_analysis_history.find(
        {"config_id": config_id}
    ).sort("created_at", -1).limit(limit)
    
    history = []
    async for doc in cursor:
        doc["id"] = str(doc.pop("_id"))
        history.append(doc)
        
    return ok({"history": history})


async def _register_scheduled_tasks(config: dict):
    """注册定时任务到调度器"""
    from app.services.scheduler_service import get_scheduler_service
    from apscheduler.triggers.cron import CronTrigger
    from app.core.config import settings

    try:
        scheduler_service = get_scheduler_service()
        scheduler = scheduler_service.scheduler

        config_id = config["id"]
        user_id = config["user_id"]

        # 为每个时间段创建一个调度任务
        for idx, slot in enumerate(config.get("time_slots", [])):
            if not slot.get("enabled", True):
                continue

            job_id = f"scheduled_analysis_{config_id}_{idx}"

            # 创建触发器
            trigger = CronTrigger.from_crontab(slot["cron_expression"], timezone=settings.TIMEZONE)

            # 添加任务
            from app.worker.watchlist_analysis_task import run_scheduled_analysis_slot
            scheduler.add_job(
                run_scheduled_analysis_slot,
                trigger,
                id=job_id,
                name=f"{config['name']} - {slot['name']}",
                kwargs={
                    "config_id": config_id,
                    "user_id": user_id,
                    "slot_index": idx
                },
                replace_existing=True
            )

            logger.info(f"✅ 注册定时任务: {job_id} - {slot['cron_expression']}")

    except Exception as e:
        logger.error(f"❌ 注册定时任务失败: {e}")


async def _unregister_scheduled_tasks(config_id: str):
    """取消注册定时任务"""
    from app.services.scheduler_service import get_scheduler_service

    try:
        scheduler_service = get_scheduler_service()
        scheduler = scheduler_service.scheduler

        # 查找并删除所有相关的任务
        jobs = scheduler.get_jobs()
        for job in jobs:
            if job.id.startswith(f"scheduled_analysis_{config_id}_"):
                scheduler.remove_job(job.id)
                logger.info(f"✅ 取消注册定时任务: {job.id}")

    except Exception as e:
        logger.error(f"❌ 取消注册定时任务失败: {e}")

