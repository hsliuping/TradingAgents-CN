#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
定时任务管理服务
提供定时任务的查询、暂停、恢复、手动触发等功能
"""

import asyncio
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta, timezone
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.job import Job
from apscheduler.events import (
    EVENT_JOB_EXECUTED,
    EVENT_JOB_ERROR,
    EVENT_JOB_MISSED,
    JobExecutionEvent
)

from app.core.database import get_mongo_db
from tradingagents.utils.logging_manager import get_logger
from app.utils.timezone import now_tz

logger = get_logger(__name__)

# UTC+8 时区
UTC_8 = timezone(timedelta(hours=8))


def get_utc8_now():
    """
    获取 UTC+8 当前时间（naive datetime）

    注意：返回 naive datetime（不带时区信息），MongoDB 会按原样存储本地时间值
    这样前端可以直接添加 +08:00 后缀显示
    """
    return now_tz().replace(tzinfo=None)


class TaskCancelledException(Exception):
    """任务被取消异常"""
    pass


class SchedulerService:
    """定时任务管理服务"""

    def __init__(self, scheduler: AsyncIOScheduler):
        """
        初始化服务

        Args:
            scheduler: APScheduler调度器实例
        """
        self.scheduler = scheduler
        self.db = None

        # 添加事件监听器，监控任务执行
        self._setup_event_listeners()
    
    def _get_db(self):
        """获取数据库连接"""
        if self.db is None:
            self.db = get_mongo_db()
        return self.db
    
    async def list_jobs(self) -> List[Dict[str, Any]]:
        """
        获取所有定时任务列表

        Returns:
            任务列表（包含挂起的任务信息）
        """
        db = self._get_db()
        
        # 🔥 获取所有挂起的执行记录（只查询suspended状态，不包括已恢复的running状态）
        # 注意：只查询状态为suspended的记录，已恢复为running的记录不会显示
        suspended_executions = await db.scheduler_executions.find({
            "status": "suspended"
        }).sort("timestamp", -1).to_list(length=100)
        
        # 🔥 调试日志：记录查询到的挂起任务数量
        if suspended_executions:
            logger.debug(f"📊 查询到 {len(suspended_executions)} 个挂起任务: {[str(e.get('_id')) + ':' + e.get('job_id', '') + ':' + e.get('status', '') for e in suspended_executions[:5]]}")
        
        # 🔥 按job_id分组，每个job_id只保留最新的一个挂起记录（用于前端显示）
        suspended_by_job = {}
        for exec_record in suspended_executions:
            job_id = exec_record.get("job_id")
            if job_id:
                # 🔥 每个job_id只保留最新的一个挂起记录（按timestamp排序，第一个就是最新的）
                if job_id not in suspended_by_job:
                    suspended_by_job[job_id] = exec_record  # 只保存最新的一个
                # 如果已经有记录，由于是按timestamp倒序排序，第一个就是最新的，不需要更新
        
        jobs = []
        for job in self.scheduler.get_jobs():
            job_dict = self._job_to_dict(job)
            # 获取任务元数据（触发器名称和备注）
            metadata = await self._get_job_metadata(job.id)
            if metadata:
                job_dict["display_name"] = metadata.get("display_name")
                job_dict["description"] = metadata.get("description")
            
            # 🔥 检查是否有挂起的执行记录
            # 注意：只显示状态为suspended的记录，已恢复为running的记录不会显示
            # 每个job_id只显示最新的一个挂起记录
            if job.id in suspended_by_job:
                latest_suspended = suspended_by_job[job.id]  # 已经是按timestamp排序的最新记录
                # 再次确认状态是suspended（防止数据不一致）
                if latest_suspended.get("status") == "suspended":
                    job_dict["has_suspended_execution"] = True
                    job_dict["suspended_execution"] = {
                        "execution_id": str(latest_suspended["_id"]),
                        "progress": latest_suspended.get("progress", 0),
                        "processed_items": latest_suspended.get("processed_items"),
                        "total_items": latest_suspended.get("total_items"),
                        "current_item": latest_suspended.get("current_item"),
                        "started_at": latest_suspended.get("timestamp").isoformat() if latest_suspended.get("timestamp") else None,
                        "message": latest_suspended.get("progress_message")
                    }
                else:
                    # 如果状态不是suspended，不显示挂起提示
                    job_dict["has_suspended_execution"] = False
            else:
                job_dict["has_suspended_execution"] = False
            
            jobs.append(job_dict)

        logger.info(f"📋 获取到 {len(jobs)} 个定时任务")
        return jobs
    
    async def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        """
        获取任务详情

        Args:
            job_id: 任务ID

        Returns:
            任务详情，如果不存在则返回None
        """
        job = self.scheduler.get_job(job_id)
        if job:
            job_dict = self._job_to_dict(job, include_details=True)
            # 获取任务元数据
            metadata = await self._get_job_metadata(job_id)
            if metadata:
                job_dict["display_name"] = metadata.get("display_name")
                job_dict["description"] = metadata.get("description")
            return job_dict
        return None
    
    async def pause_job(self, job_id: str) -> bool:
        """
        暂停任务
        
        Args:
            job_id: 任务ID
            
        Returns:
            是否成功
        """
        try:
            self.scheduler.pause_job(job_id)
            logger.info(f"⏸️ 任务 {job_id} 已暂停")
            
            # 记录操作历史
            await self._record_job_action(job_id, "pause", "success")
            return True
        except Exception as e:
            logger.error(f"❌ 暂停任务 {job_id} 失败: {e}")
            await self._record_job_action(job_id, "pause", "failed", str(e))
            return False
    
    async def resume_job(self, job_id: str) -> bool:
        """
        恢复任务

        Args:
            job_id: 任务ID

        Returns:
            是否成功
        """
        try:
            self.scheduler.resume_job(job_id)
            logger.info(f"▶️ 任务 {job_id} 已恢复")

            # 记录操作历史
            await self._record_job_action(job_id, "resume", "success")
            return True
        except Exception as e:
            logger.error(f"❌ 恢复任务 {job_id} 失败: {e}")
            await self._record_job_action(job_id, "resume", "failed", str(e))
            return False

    async def reschedule_job(self, job_id: str, cron_expression: str) -> bool:
        """
        修改任务的CRON表达式

        Args:
            job_id: 任务ID
            cron_expression: 新的CRON表达式，如 "0 8 * * 1-5"

        Returns:
            是否成功
        """
        from apscheduler.triggers.cron import CronTrigger
        from app.core.config import settings

        try:
            job = self.scheduler.get_job(job_id)
            if not job:
                logger.error(f"❌ 任务 {job_id} 不存在")
                return False

            # 验证CRON表达式格式
            try:
                new_trigger = CronTrigger.from_crontab(cron_expression, timezone=settings.TIMEZONE)
            except Exception as e:
                logger.error(f"❌ 无效的CRON表达式 '{cron_expression}': {e}")
                return False

            # 记录旧的触发器信息
            old_trigger_str = str(job.trigger)

            # 修改任务的触发器
            self.scheduler.reschedule_job(job_id, trigger=new_trigger)

            logger.info(f"🔄 任务 {job_id} CRON已更新: {old_trigger_str} -> {cron_expression}")

            # 记录操作历史
            await self._record_job_action(
                job_id,
                "reschedule",
                "success",
                f"CRON表达式已更新: {cron_expression}"
            )
            return True

        except Exception as e:
            logger.error(f"❌ 修改任务 {job_id} CRON失败: {e}")
            await self._record_job_action(job_id, "reschedule", "failed", str(e))
            return False

    async def trigger_job(self, job_id: str, kwargs: Optional[Dict[str, Any]] = None, force: bool = False) -> bool:
        """
        手动触发任务执行

        注意：如果任务处于暂停状态，会先临时恢复任务，执行一次后不会自动暂停

        Args:
            job_id: 任务ID
            kwargs: 传递给任务函数的关键字参数（可选）
            force: 是否强制执行（即使有running记录也执行），默认 False

        Returns:
            是否成功
            
        Raises:
            HTTPException: 如果有running记录且force=False，抛出409状态码，提示用户是否强制执行
        """
        from fastapi import HTTPException
        # 🔥 手动触发时，添加标记，允许任务函数跳过并发检查
        if kwargs is None:
            kwargs = {}
        kwargs["_manual_trigger"] = True  # 标记这是手动触发，允许执行
        if force:
            kwargs["_force_execute"] = True  # 标记是否强制执行
        try:
            job = self.scheduler.get_job(job_id)
            if not job:
                logger.error(f"❌ 任务 {job_id} 不存在")
                return False

            # 检查任务是否被暂停（next_run_time 为 None 表示暂停）
            was_paused = job.next_run_time is None
            if was_paused:
                logger.warning(f"⚠️ 任务 {job_id} 处于暂停状态，临时恢复以执行一次")
                self.scheduler.resume_job(job_id)
                # 重新获取 job 对象（恢复后状态已改变）
                job = self.scheduler.get_job(job_id)
                logger.info(f"✅ 任务 {job_id} 已临时恢复")

            # 如果提供了 kwargs，合并到任务的 kwargs 中
            # 🔥 初始化 merged_kwargs，避免在 kwargs 为空时未定义
            original_kwargs = job.kwargs.copy() if job.kwargs else {}
            merged_kwargs = original_kwargs.copy()
            
            if kwargs:
                # 🔥 先移除内部标记（_resume_execution_id），这些不应该传递给任务函数
                clean_kwargs = {k: v for k, v in kwargs.items() if not k.startswith("_")}
                # 合并新的 kwargs（只包含任务函数能接受的参数）
                merged_kwargs = {**original_kwargs, **clean_kwargs}
                # 修改任务的 kwargs（这样update_job_progress才能读取到正确的参数）
                job.modify(kwargs=merged_kwargs)
                logger.info(f"📝 任务 {job_id} 参数已更新: {clean_kwargs} -> 合并后: {merged_kwargs}")

            # 🔥 先创建执行记录并保存kwargs，确保恢复时能读取到正确的参数
            # 这样即使任务立即执行，update_job_progress也能读取到正确的kwargs
            try:
                db = self._get_db()
                # 获取最终的kwargs（合并后的）
                final_kwargs = job.kwargs.copy() if job.kwargs else {}
                if kwargs:
                    final_kwargs.update(kwargs)
                
                # 🔥 检查是否是恢复操作（通过_resume_execution_id标记）
                # 注意：_resume_execution_id 需要传递给任务函数，以便任务函数知道这是恢复执行，允许执行
                resume_execution_id = final_kwargs.pop("_resume_execution_id", None)
                
                if resume_execution_id:
                    # 这是恢复操作，复用挂起的执行记录
                    from bson import ObjectId
                    existing_record = await db.scheduler_executions.find_one({"_id": ObjectId(resume_execution_id)})
                    if existing_record:
                        # 🔥 从执行记录中读取进度信息，并添加到kwargs中
                        processed_items = existing_record.get("processed_items")
                        if processed_items is not None:
                            final_kwargs["_resume_from_index"] = processed_items
                            logger.info(f"📊 恢复操作: 从执行记录读取 processed_items={processed_items}，已添加到kwargs")
                        else:
                            logger.warning(f"⚠️ 执行记录中没有 processed_items，将从0开始")
                        
                        # 🔥 将 _resume_execution_id 也添加到 final_kwargs，以便任务函数知道这是恢复执行
                        final_kwargs["_resume_execution_id"] = resume_execution_id
                        
                        # 更新现有记录的kwargs和状态（注意：final_kwargs包含了_resume_from_index和_resume_execution_id）
                        await db.scheduler_executions.update_one(
                            {"_id": ObjectId(resume_execution_id)},
                            {
                                "$set": {
                                    "job_kwargs": final_kwargs,  # 保存kwargs（包含_resume_from_index和_resume_execution_id）
                                    "status": "running",
                                    "is_manual": True,  # 🔥 恢复执行时，标记为手动操作
                                    "updated_at": get_utc8_now()
                                }
                            }
                        )
                        logger.info(f"📝 已复用执行记录 {resume_execution_id} 并更新kwargs: {final_kwargs} (is_manual=True)")
                    else:
                        logger.warning(f"⚠️ 指定的执行记录 {resume_execution_id} 不存在，将创建新记录")
                        resume_execution_id = None  # 标记为None，后续创建新记录
                
                if not resume_execution_id:
                    # 🔥 不是恢复操作，查找是否有挂起的任务（suspended状态，不限时间）
                    # 优先查找 suspended 状态的记录（挂起任务应该恢复执行）
                    suspended_record = await db.scheduler_executions.find_one(
                        {
                            "job_id": job_id,
                            "status": "suspended"
                        },
                        sort=[("timestamp", -1)]
                    )
                    
                    # 🔥 如果没有挂起任务，再查找是否有running记录（5分钟内）
                    if not suspended_record:
                        five_minutes_ago = get_utc8_now() - timedelta(minutes=5)
                        running_record = await db.scheduler_executions.find_one(
                            {
                                "job_id": job_id,
                                "status": "running",
                                "timestamp": {"$gte": five_minutes_ago}
                            },
                            sort=[("timestamp", -1)]
                        )
                        existing_record = running_record
                    else:
                        existing_record = suspended_record
                    
                    if existing_record:
                        # 🔥 如果是suspended状态，自动恢复执行（手动触发时）
                        if existing_record.get("status") == "suspended":
                            resume_execution_id = str(existing_record["_id"])
                            # 从执行记录中读取进度信息
                            processed_items = existing_record.get("processed_items")
                            if processed_items is not None:
                                final_kwargs["_resume_from_index"] = processed_items
                                logger.info(f"📊 手动触发恢复挂起任务: 从执行记录读取 processed_items={processed_items}，已添加到kwargs")
                            else:
                                logger.warning(f"⚠️ 执行记录中没有 processed_items，将从0开始")
                            
                            # 将 _resume_execution_id 添加到 final_kwargs
                            final_kwargs["_resume_execution_id"] = resume_execution_id
                            
                            # 更新现有记录的状态为running，并设置 is_manual=True（手动触发恢复）
                            await db.scheduler_executions.update_one(
                                {"_id": existing_record["_id"]},
                                {
                                    "$set": {
                                        "job_kwargs": final_kwargs,
                                        "status": "running",
                                        "is_manual": True,  # 🔥 手动触发恢复时，标记为手动操作
                                        "updated_at": get_utc8_now()
                                    }
                                }
                            )
                            logger.info(f"🔄 手动触发时检测到挂起任务，自动恢复执行: {resume_execution_id} (is_manual=True)")
                        else:
                            # 🔥 如果是running状态，检查是否需要用户确认
                            if not force:
                                # 有running记录且未强制，需要用户确认
                                running_instance_id = str(existing_record["_id"])
                                running_start_time = existing_record.get("timestamp")
                                running_progress = existing_record.get("progress", 0)
                                
                                logger.warning(f"⚠️ 任务 {job_id} 已有实例在运行（_id={running_instance_id}），需要用户确认是否强制执行")
                                
                                # 抛出409 Conflict，提示前端显示确认对话框
                                raise HTTPException(
                                    status_code=409,
                                    detail={
                                        "code": "TASK_ALREADY_RUNNING",
                                        "message": f"任务 {job_id} 已有实例正在运行中",
                                        "running_instance_id": running_instance_id,
                                        "running_start_time": running_start_time.isoformat() if running_start_time else None,
                                        "running_progress": running_progress,
                                        "suggestion": "是否强制执行？强制执行将跳过并发检查，可能导致重复执行。"
                                    }
                                )
                            
                            # 强制执行时，更新kwargs并继续执行
                            await db.scheduler_executions.update_one(
                                {"_id": existing_record["_id"]},
                                {"$set": {"job_kwargs": final_kwargs}}
                            )
                            logger.info(f"🔧 强制执行：已更新执行记录 {existing_record['_id']} 的kwargs: {final_kwargs}")
                    else:
                        # 创建新的执行记录（任务刚开始）
                        # 🔥 手动触发时，设置 is_manual=True
                        execution_record = {
                            "job_id": job_id,
                            "job_name": job.name if job else job_id,
                            "status": "running",
                            "timestamp": get_utc8_now(),
                            "scheduled_time": get_utc8_now(),
                            "is_manual": True,  # 🔥 手动触发时标记为手动操作
                            "job_kwargs": final_kwargs  # 🔥 保存kwargs（已清理，不包含_resume_execution_id）
                        }
                        await db.scheduler_executions.insert_one(execution_record)
                        logger.info(f"📝 已创建执行记录并保存kwargs: {final_kwargs} (is_manual=True)")
            except Exception as record_error:
                logger.warning(f"⚠️ 保存执行记录kwargs失败（不影响任务执行）: {record_error}")
            
            # 🔥 立即执行任务（不等待APScheduler调度）
            # 这样可以确保任务立即执行，而不是等待下一个调度周期
            try:
                import asyncio
                import inspect
                
                # 🔥 清理kwargs中的内部标记（这些不应该传递给任务函数）
                # 但保留 _resume_from_index、_resume_execution_id、_manual_trigger 和 _force_execute，因为任务函数需要它们来判断是否允许执行
                # 🔥 使用 final_kwargs 而不是 merged_kwargs，因为 final_kwargs 包含了恢复位置信息
                clean_kwargs_for_execution = {}
                for k, v in final_kwargs.items():
                    if k.startswith("_") and k not in ["_resume_from_index", "_resume_execution_id", "_manual_trigger", "_force_execute"]:
                        # 跳过内部标记（除了 _resume_from_index、_resume_execution_id、_manual_trigger 和 _force_execute）
                        continue
                    clean_kwargs_for_execution[k] = v
                
                # 🔥 如果是恢复执行，将 _resume_execution_id 也添加到 kwargs 中
                if resume_execution_id:
                    clean_kwargs_for_execution["_resume_execution_id"] = resume_execution_id
                
                # 🔥 手动触发标记已经包含在 final_kwargs 中（通过 kwargs["_manual_trigger"] = True）
                
                logger.info(f"🔍 构建执行参数: merged_kwargs={merged_kwargs}, final_kwargs={final_kwargs}, clean_kwargs_for_execution={clean_kwargs_for_execution}")
                
                # 获取任务函数和参数
                func = job.func
                
                # 🔥 检查函数签名，只传递函数接受的参数
                sig = inspect.signature(func)
                func_params = set(sig.parameters.keys())
                
                # 过滤 kwargs，只保留函数接受的参数
                filtered_kwargs = {}
                for k, v in clean_kwargs_for_execution.items():
                    # 如果函数有 **kwargs 参数，或者参数名在函数签名中，则传递
                    if k in func_params or any(p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values()):
                        filtered_kwargs[k] = v
                    else:
                        logger.debug(f"⏭️ 跳过参数 {k}（函数 {func.__name__} 不接受此参数）")
                
                # 🔥 使用过滤后的kwargs（只包含函数接受的参数）
                logger.info(f"⚡ 立即执行任务 {job_id} (协程函数, kwargs={filtered_kwargs})")
                
                # 检查任务函数是否是协程
                if inspect.iscoroutinefunction(func):
                    # 协程函数，立即执行（在后台）
                    asyncio.create_task(func(**filtered_kwargs))
                    logger.info(f"✅ 任务 {job_id} 已立即执行（协程函数，后台执行中）")
                else:
                    # 同步函数，使用线程池执行
                    import concurrent.futures
                    logger.info(f"⚡ 立即执行任务 {job_id} (同步函数, kwargs={filtered_kwargs})")
                    # 使用线程池执行同步函数
                    executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
                    executor.submit(func, **filtered_kwargs)
                    logger.info(f"✅ 任务 {job_id} 已提交到线程池执行")
                
                # 🔥 立即执行成功，不需要再调用 job.modify(next_run_time=now)
                # 因为这会触发 APScheduler 再次调度任务，导致重复执行
                logger.info(f"🚀 任务 {job_id} 已立即执行 (was_paused={was_paused}, kwargs={clean_kwargs_for_execution})")
            except Exception as immediate_exec_error:
                # 立即执行失败，回退到APScheduler调度
                logger.warning(f"⚠️ 立即执行任务 {job_id} 失败，回退到APScheduler调度: {immediate_exec_error}", exc_info=True)
                # 手动触发任务 - 使用带时区的当前时间
                from datetime import timezone
                now = datetime.now(timezone.utc)
                job.modify(next_run_time=now)
                logger.info(f"🚀 通过APScheduler调度任务 {job_id} (next_run_time={now})")

            # 记录操作历史
            action_note = f"手动触发执行 (暂停状态: {was_paused}"
            if kwargs:
                action_note += f", 参数: {kwargs}"
            action_note += ")"
            await self._record_job_action(job_id, "trigger", "success", action_note)

            # 🔥 注意：不再在这里调用 _record_job_execution
            # 原因：
            # 1. 已经在第352-361行创建了执行记录（如果不存在）
            # 2. 如果这里再创建，会导致重复记录
            # 3. update_job_progress 会在任务开始时创建或更新记录
            # 4. 如果记录已存在，update_job_progress 会更新它；如果不存在，会创建它
            logger.info(f"📝 任务 {job_id} 已触发，执行记录将在任务开始时由 update_job_progress 创建或更新")

            return True
        except Exception as e:
            logger.error(f"❌ 触发任务 {job_id} 失败: {e}")
            import traceback
            logger.error(f"详细错误: {traceback.format_exc()}")
            await self._record_job_action(job_id, "trigger", "failed", str(e))
            return False
    
    async def get_job_history(
        self,
        job_id: str,
        limit: int = 20,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        获取任务执行历史
        
        Args:
            job_id: 任务ID
            limit: 返回数量限制
            offset: 偏移量
            
        Returns:
            执行历史记录
        """
        try:
            db = self._get_db()
            cursor = db.scheduler_history.find(
                {"job_id": job_id}
            ).sort("timestamp", -1).skip(offset).limit(limit)
            
            history = []
            async for doc in cursor:
                doc.pop("_id", None)
                history.append(doc)
            
            return history
        except Exception as e:
            logger.error(f"❌ 获取任务 {job_id} 执行历史失败: {e}")
            return []
    
    async def count_job_history(self, job_id: str) -> int:
        """
        统计任务执行历史数量
        
        Args:
            job_id: 任务ID
            
        Returns:
            历史记录数量
        """
        try:
            db = self._get_db()
            count = await db.scheduler_history.count_documents({"job_id": job_id})
            return count
        except Exception as e:
            logger.error(f"❌ 统计任务 {job_id} 执行历史失败: {e}")
            return 0
    
    async def get_all_history(
        self,
        limit: int = 50,
        offset: int = 0,
        job_id: Optional[str] = None,
        status: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        获取所有任务执行历史
        
        Args:
            limit: 返回数量限制
            offset: 偏移量
            job_id: 任务ID过滤
            status: 状态过滤
            
        Returns:
            执行历史记录
        """
        try:
            db = self._get_db()
            
            # 构建查询条件
            query = {}
            if job_id:
                query["job_id"] = job_id
            if status:
                query["status"] = status
            
            cursor = db.scheduler_history.find(query).sort("timestamp", -1).skip(offset).limit(limit)
            
            history = []
            async for doc in cursor:
                doc.pop("_id", None)
                history.append(doc)
            
            return history
        except Exception as e:
            logger.error(f"❌ 获取执行历史失败: {e}")
            return []
    
    async def count_all_history(
        self,
        job_id: Optional[str] = None,
        status: Optional[str] = None
    ) -> int:
        """
        统计所有任务执行历史数量

        Args:
            job_id: 任务ID过滤
            status: 状态过滤

        Returns:
            历史记录数量
        """
        try:
            db = self._get_db()

            # 构建查询条件
            query = {}
            if job_id:
                query["job_id"] = job_id
            if status:
                query["status"] = status

            count = await db.scheduler_history.count_documents(query)
            return count
        except Exception as e:
            logger.error(f"❌ 统计执行历史失败: {e}")
            return 0

    async def get_job_executions(
        self,
        job_id: Optional[str] = None,
        status: Optional[str] = None,
        is_manual: Optional[bool] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        获取任务执行历史

        Args:
            job_id: 任务ID（可选，不指定则返回所有任务）
            status: 状态过滤（success/failed/missed/running）
            is_manual: 是否手动触发（True=手动，False=自动，None=全部）
            limit: 返回数量限制
            offset: 偏移量

        Returns:
            执行历史列表
        """
        try:
            db = self._get_db()

            # 构建查询条件
            query = {}
            if job_id:
                query["job_id"] = job_id
            if status:
                query["status"] = status

            # 处理 is_manual 过滤
            if is_manual is not None:
                if is_manual:
                    # 手动触发：is_manual 必须为 true
                    query["is_manual"] = True
                else:
                    # 自动触发：is_manual 字段不存在或为 false
                    # 使用 $ne (not equal) 来排除 is_manual=true 的记录
                    query["is_manual"] = {"$ne": True}

            cursor = db.scheduler_executions.find(query).sort("timestamp", -1).skip(offset).limit(limit)

            executions = []
            async for doc in cursor:
                # 转换 _id 为字符串
                if "_id" in doc:
                    doc["_id"] = str(doc["_id"])

                # 格式化时间（MongoDB 存储的是 naive datetime，表示本地时间）
                # 直接序列化为 ISO 格式字符串，前端会自动添加 +08:00 后缀
                for time_field in ["scheduled_time", "timestamp", "updated_at"]:
                    if doc.get(time_field):
                        dt = doc[time_field]
                        # 如果是 datetime 对象，转换为 ISO 格式字符串
                        if hasattr(dt, 'isoformat'):
                            doc[time_field] = dt.isoformat()

                executions.append(doc)

            return executions
        except Exception as e:
            logger.error(f"❌ 获取任务执行历史失败: {e}")
            return []

    async def count_job_executions(
        self,
        job_id: Optional[str] = None,
        status: Optional[str] = None,
        is_manual: Optional[bool] = None
    ) -> int:
        """
        统计任务执行历史数量

        Args:
            job_id: 任务ID（可选）
            status: 状态过滤（可选）
            is_manual: 是否手动触发（可选）

        Returns:
            执行历史数量
        """
        try:
            db = self._get_db()

            # 构建查询条件
            query = {}
            if job_id:
                query["job_id"] = job_id
            if status:
                query["status"] = status

            # 处理 is_manual 过滤
            if is_manual is not None:
                if is_manual:
                    # 手动触发：is_manual 必须为 true
                    query["is_manual"] = True
                else:
                    # 自动触发：is_manual 字段不存在或为 false
                    query["is_manual"] = {"$ne": True}

            count = await db.scheduler_executions.count_documents(query)
            return count
        except Exception as e:
            logger.error(f"❌ 统计任务执行历史失败: {e}")
            return 0

    async def cancel_job_execution(self, execution_id: str) -> bool:
        """
        取消/终止任务执行

        对于正在执行的任务，设置取消标记；
        对于已经退出但数据库中仍为running的任务，直接标记为failed

        Args:
            execution_id: 执行记录ID（MongoDB _id）

        Returns:
            是否成功
        """
        try:
            from bson import ObjectId
            db = self._get_db()

            # 查找执行记录
            execution = await db.scheduler_executions.find_one({"_id": ObjectId(execution_id)})
            if not execution:
                logger.error(f"❌ 执行记录不存在: {execution_id}")
                return False

            if execution.get("status") != "running":
                logger.warning(f"⚠️ 执行记录状态不是running: {execution_id} (status={execution.get('status')})")
                return False

            # 设置取消标记
            await db.scheduler_executions.update_one(
                {"_id": ObjectId(execution_id)},
                {
                    "$set": {
                        "cancel_requested": True,
                        "updated_at": get_utc8_now()
                    }
                }
            )

            logger.info(f"✅ 已设置取消标记: {execution.get('job_name', execution.get('job_id'))} (execution_id={execution_id})")
            return True

        except Exception as e:
            logger.error(f"❌ 取消任务执行失败: {e}")
            return False

    async def mark_execution_as_failed(self, execution_id: str, reason: str = "用户手动标记为失败") -> bool:
        """
        将执行记录标记为失败状态

        用于处理已经退出但数据库中仍为running的任务

        Args:
            execution_id: 执行记录ID（MongoDB _id）
            reason: 失败原因

        Returns:
            是否成功
        """
        try:
            from bson import ObjectId
            db = self._get_db()

            # 查找执行记录
            execution = await db.scheduler_executions.find_one({"_id": ObjectId(execution_id)})
            if not execution:
                logger.error(f"❌ 执行记录不存在: {execution_id}")
                return False

            # 更新为failed状态
            await db.scheduler_executions.update_one(
                {"_id": ObjectId(execution_id)},
                {
                    "$set": {
                        "status": "failed",
                        "error_message": reason,
                        "updated_at": get_utc8_now()
                    }
                }
            )

            logger.info(f"✅ 已标记为失败: {execution.get('job_name', execution.get('job_id'))} (execution_id={execution_id}, reason={reason})")
            return True

        except Exception as e:
            logger.error(f"❌ 标记执行记录为失败失败: {e}")
            return False

    async def delete_execution(self, execution_id: str) -> bool:
        """
        删除执行记录

        Args:
            execution_id: 执行记录ID（MongoDB _id）

        Returns:
            是否成功
        """
        try:
            from bson import ObjectId
            db = self._get_db()

            # 查找执行记录
            execution = await db.scheduler_executions.find_one({"_id": ObjectId(execution_id)})
            if not execution:
                logger.error(f"❌ 执行记录不存在: {execution_id}")
                return False

            # 不允许删除正在执行的任务
            if execution.get("status") == "running":
                logger.error(f"❌ 不能删除正在执行的任务: {execution_id}")
                return False

            # 删除记录
            result = await db.scheduler_executions.delete_one({"_id": ObjectId(execution_id)})

            if result.deleted_count > 0:
                logger.info(f"✅ 已删除执行记录: {execution.get('job_name', execution.get('job_id'))} (execution_id={execution_id})")
                return True
            else:
                logger.error(f"❌ 删除执行记录失败: {execution_id}")
                return False

        except Exception as e:
            logger.error(f"❌ 删除执行记录失败: {e}")
            return False

    async def get_latest_execution(self, job_id: str) -> Optional[Dict[str, Any]]:
        """
        获取任务最新的执行记录

        Args:
            job_id: 任务ID

        Returns:
            最新的执行记录，如果没有则返回None
        """
        try:
            db = self._get_db()
            execution = await db.scheduler_executions.find_one(
                {"job_id": job_id},
                sort=[("timestamp", -1)]
            )
            
            if execution:
                # 转换 _id 为字符串
                if "_id" in execution:
                    execution["_id"] = str(execution["_id"])
                
                # 格式化时间
                for time_field in ["scheduled_time", "timestamp", "updated_at"]:
                    if execution.get(time_field):
                        dt = execution[time_field]
                        if hasattr(dt, 'isoformat'):
                            execution[time_field] = dt.isoformat()
            
            return execution
        except Exception as e:
            logger.error(f"❌ 获取最新执行记录失败: {e}")
            return None

    async def get_job_execution_stats(self, job_id: str) -> Dict[str, Any]:
        """
        获取任务执行统计信息

        Args:
            job_id: 任务ID

        Returns:
            统计信息
        """
        try:
            db = self._get_db()

            # 统计各状态的执行次数
            pipeline = [
                {"$match": {"job_id": job_id}},
                {"$group": {
                    "_id": "$status",
                    "count": {"$sum": 1},
                    "avg_execution_time": {"$avg": "$execution_time"}
                }}
            ]

            stats = {
                "total": 0,
                "success": 0,
                "failed": 0,
                "missed": 0,
                "avg_execution_time": 0
            }

            async for doc in db.scheduler_executions.aggregate(pipeline):
                status = doc["_id"]
                count = doc["count"]
                stats["total"] += count
                stats[status] = count

                if status == "success" and doc.get("avg_execution_time"):
                    stats["avg_execution_time"] = round(doc["avg_execution_time"], 2)

            # 获取最近一次执行
            last_execution = await db.scheduler_executions.find_one(
                {"job_id": job_id},
                sort=[("timestamp", -1)]
            )

            if last_execution:
                stats["last_execution"] = {
                    "status": last_execution.get("status"),
                    "timestamp": last_execution.get("timestamp").isoformat() if last_execution.get("timestamp") else None,
                    "execution_time": last_execution.get("execution_time")
                }

            return stats
        except Exception as e:
            logger.error(f"❌ 获取任务执行统计失败: {e}")
            return {}
    
    async def get_stats(self) -> Dict[str, Any]:
        """
        获取调度器统计信息
        
        Returns:
            统计信息
        """
        jobs = self.scheduler.get_jobs()
        
        total = len(jobs)
        running = sum(1 for job in jobs if job.next_run_time is not None)
        paused = total - running
        
        return {
            "total_jobs": total,
            "running_jobs": running,
            "paused_jobs": paused,
            "scheduler_running": self.scheduler.running,
            "scheduler_state": self.scheduler.state
        }
    
    async def health_check(self) -> Dict[str, Any]:
        """
        调度器健康检查
        
        Returns:
            健康状态
        """
        return {
            "status": "healthy" if self.scheduler.running else "stopped",
            "running": self.scheduler.running,
            "state": self.scheduler.state,
            "timestamp": get_utc8_now().isoformat()
        }
    
    def _job_to_dict(self, job: Job, include_details: bool = False) -> Dict[str, Any]:
        """
        将Job对象转换为字典
        
        Args:
            job: Job对象
            include_details: 是否包含详细信息
            
        Returns:
            字典表示
        """
        result = {
            "id": job.id,
            "name": job.name or job.id,
            "next_run_time": job.next_run_time.isoformat() if job.next_run_time else None,
            "paused": job.next_run_time is None,
            "trigger": str(job.trigger),
        }
        
        if include_details:
            result.update({
                "func": f"{job.func.__module__}.{job.func.__name__}",
                "args": job.args,
                "kwargs": job.kwargs,
                "misfire_grace_time": job.misfire_grace_time,
                "max_instances": job.max_instances,
            })
        
        return result
    
    def _setup_event_listeners(self):
        """设置APScheduler事件监听器"""
        # 监听任务执行成功事件
        self.scheduler.add_listener(
            self._on_job_executed,
            EVENT_JOB_EXECUTED
        )

        # 监听任务执行失败事件
        self.scheduler.add_listener(
            self._on_job_error,
            EVENT_JOB_ERROR
        )

        # 监听任务错过执行事件
        self.scheduler.add_listener(
            self._on_job_missed,
            EVENT_JOB_MISSED
        )

        logger.info("✅ APScheduler事件监听器已设置")

        # 添加定时任务，检测僵尸任务（长时间处于running状态）
        self.scheduler.add_job(
            self._check_zombie_tasks,
            'interval',
            minutes=5,
            id='check_zombie_tasks',
            name='检测僵尸任务',
            replace_existing=True
        )
        logger.info("✅ 僵尸任务检测定时任务已添加")

    async def check_suspended_tasks_on_startup(self):
        """
        服务启动时检测挂起的任务（服务重启前正在执行的任务）
        
        将遗留的running状态任务标记为suspended（挂起），用户可以继续执行
        """
        try:
            db = self._get_db()

            # 查找所有处于running状态的任务（这些是服务重启前正在执行的任务）
            suspended_tasks = await db.scheduler_executions.find({
                "status": "running"
            }).to_list(length=100)

            for task in suspended_tasks:
                job_id = task.get("job_id")
                
                # 🔥 尝试从Redis读取进度信息（如果存在）
                progress_data = {}
                try:
                    from app.core.database import get_redis_sync_client
                    from app.core.redis_client import RedisKeys
                    redis_sync = get_redis_sync_client()
                    if redis_sync:
                        progress_key = RedisKeys.SCHEDULER_JOB_PROGRESS.format(job_id=job_id)
                        progress_str = redis_sync.get(progress_key)
                        if progress_str:
                            import json
                            progress_data = json.loads(progress_str)
                            logger.info(f"📊 从Redis读取到挂起任务的进度: {job_id}, 进度: {progress_data.get('progress', 0)}%, 已处理: {progress_data.get('processed_items', 0)}")
                except Exception as e:
                    logger.warning(f"⚠️ 从Redis读取进度失败: {e}")
                
                # 构建更新数据，优先使用Redis中的进度信息
                update_data = {
                    "status": "suspended",
                    "error_message": "服务重启导致任务中断，可以继续执行",
                    "updated_at": get_utc8_now()
                }
                
                # 🔥 如果Redis中有进度信息，保存到MongoDB执行记录中
                if progress_data:
                    if "progress" in progress_data:
                        update_data["progress"] = progress_data["progress"]
                    if "processed_items" in progress_data:
                        update_data["processed_items"] = progress_data["processed_items"]
                    if "current_item" in progress_data:
                        update_data["current_item"] = progress_data["current_item"]
                    if "total_items" in progress_data:
                        update_data["total_items"] = progress_data["total_items"]
                    if "message" in progress_data:
                        update_data["progress_message"] = progress_data["message"]
                
                # 更新为suspended状态（挂起），而不是failed
                await db.scheduler_executions.update_one(
                    {"_id": task["_id"]},
                    {"$set": update_data}
                )
                
                progress_info = progress_data.get("progress", task.get("progress", 0))
                processed_info = progress_data.get("processed_items", task.get("processed_items", 0))
                logger.info(f"⏸️ 检测到挂起任务: {task.get('job_name', task.get('job_id'))} (开始时间: {task.get('timestamp')}, 进度: {progress_info}%, 已处理: {processed_info})")

            if suspended_tasks:
                logger.info(f"✅ 已标记 {len(suspended_tasks)} 个挂起任务（服务重启导致）")

        except Exception as e:
            logger.error(f"❌ 检测挂起任务失败: {e}")

    async def _check_zombie_tasks(self):
        """
        检测僵尸任务（长时间处于running状态的任务）
        
        注意：此方法只处理真正的超时任务，服务重启导致的挂起任务由check_suspended_tasks_on_startup处理
        """
        try:
            db = self._get_db()

            # 查找超过30分钟仍处于running状态的任务（这些是真正的超时任务）
            threshold_time = get_utc8_now() - timedelta(minutes=30)

            zombie_tasks = await db.scheduler_executions.find({
                "status": "running",
                "timestamp": {"$lt": threshold_time}
            }).to_list(length=100)

            for task in zombie_tasks:
                # 更新为failed状态
                await db.scheduler_executions.update_one(
                    {"_id": task["_id"]},
                    {
                        "$set": {
                            "status": "failed",
                            "error_message": "任务执行超时或进程异常终止",
                            "updated_at": get_utc8_now()
                        }
                    }
                )
                logger.warning(f"⚠️ 检测到僵尸任务: {task.get('job_name', task.get('job_id'))} (开始时间: {task.get('timestamp')})")

            if zombie_tasks:
                logger.info(f"✅ 已标记 {len(zombie_tasks)} 个僵尸任务为失败状态")

        except Exception as e:
            logger.error(f"❌ 检测僵尸任务失败: {e}")

    def _on_job_executed(self, event: JobExecutionEvent):
        """任务执行成功回调"""
        # 计算执行时间（处理时区问题）
        execution_time = None
        if event.scheduled_run_time:
            now = datetime.now(event.scheduled_run_time.tzinfo)
            execution_time = (now - event.scheduled_run_time).total_seconds()

        asyncio.create_task(self._record_job_execution(
            job_id=event.job_id,
            status="success",
            scheduled_time=event.scheduled_run_time,
            execution_time=execution_time,
            return_value=str(event.retval) if event.retval else None,
            progress=100  # 任务完成，进度100%
        ))

    def _on_job_error(self, event: JobExecutionEvent):
        """任务执行失败回调"""
        # 计算执行时间（处理时区问题）
        execution_time = None
        if event.scheduled_run_time:
            now = datetime.now(event.scheduled_run_time.tzinfo)
            execution_time = (now - event.scheduled_run_time).total_seconds()

        asyncio.create_task(self._record_job_execution(
            job_id=event.job_id,
            status="failed",
            scheduled_time=event.scheduled_run_time,
            execution_time=execution_time,
            error_message=str(event.exception) if event.exception else None,
            traceback=event.traceback if hasattr(event, 'traceback') else None,
            progress=None  # 失败时不设置进度
        ))

    def _on_job_missed(self, event: JobExecutionEvent):
        """任务错过执行回调"""
        asyncio.create_task(self._record_job_execution(
            job_id=event.job_id,
            status="missed",
            scheduled_time=event.scheduled_run_time,
            progress=None  # 错过时不设置进度
        ))

    async def _record_job_execution(
        self,
        job_id: str,
        status: str,
        scheduled_time: datetime = None,
        execution_time: float = None,
        return_value: str = None,
        error_message: str = None,
        traceback: str = None,
        progress: int = None,
        is_manual: bool = False
    ):
        """
        记录任务执行历史

        Args:
            job_id: 任务ID
            status: 状态 (running/success/failed/missed)
            scheduled_time: 计划执行时间
            execution_time: 实际执行时长（秒）
            return_value: 返回值
            error_message: 错误信息
            traceback: 错误堆栈
            progress: 执行进度（0-100）
            is_manual: 是否手动触发
        """
        try:
            db = self._get_db()

            # 获取任务名称和kwargs
            job = self.scheduler.get_job(job_id)
            job_name = job.name if job else job_id
            job_kwargs = job.kwargs.copy() if job and job.kwargs else {}

            # 如果是完成状态（success/failed），先查找是否有对应的 running 记录
            if status in ["success", "failed"]:
                # 查找最近的 running 记录（5分钟内）
                five_minutes_ago = get_utc8_now() - timedelta(minutes=5)
                existing_record = await db.scheduler_executions.find_one(
                    {
                        "job_id": job_id,
                        "status": "running",
                        "timestamp": {"$gte": five_minutes_ago}
                    },
                    sort=[("timestamp", -1)]
                )

                if existing_record:
                    # 更新现有记录
                    update_data = {
                        "status": status,
                        "execution_time": execution_time,
                        "updated_at": get_utc8_now()
                    }

                    if return_value:
                        update_data["return_value"] = return_value
                    if error_message:
                        update_data["error_message"] = error_message
                    if traceback:
                        update_data["traceback"] = traceback
                    if progress is not None:
                        update_data["progress"] = progress

                    await db.scheduler_executions.update_one(
                        {"_id": existing_record["_id"]},
                        {"$set": update_data}
                    )

                    # 记录日志
                    if status == "success":
                        logger.info(f"✅ [任务执行] {job_name} 执行成功，耗时: {execution_time:.2f}秒")
                    elif status == "failed":
                        logger.error(f"❌ [任务执行] {job_name} 执行失败: {error_message}")

                    # 🔥 更新Redis缓存（异步）
                    await self._update_redis_execution_cache(
                        job_id=job_id,
                        status=status,
                        progress=progress,
                        execution_time=execution_time,
                        error_message=error_message,
                        scheduled_time=existing_record.get("scheduled_time")
                    )

                    return

            # 如果没有找到 running 记录，或者是 running/missed 状态，插入新记录
            # scheduled_time 可能是 aware datetime（来自 APScheduler），需要转换为 naive datetime
            scheduled_time_naive = None
            if scheduled_time:
                if scheduled_time.tzinfo is not None:
                    # 转换为本地时区，然后移除时区信息
                    scheduled_time_naive = scheduled_time.astimezone(UTC_8).replace(tzinfo=None)
                else:
                    scheduled_time_naive = scheduled_time

            execution_record = {
                "job_id": job_id,
                "job_name": job_name,
                "status": status,
                "scheduled_time": scheduled_time_naive,
                "execution_time": execution_time,
                "timestamp": get_utc8_now(),
                "is_manual": is_manual,
                "job_kwargs": job_kwargs  # 🔥 保存任务的kwargs，用于恢复时传递参数
            }

            if return_value:
                execution_record["return_value"] = return_value
            if error_message:
                execution_record["error_message"] = error_message
            if traceback:
                execution_record["traceback"] = traceback
            if progress is not None:
                execution_record["progress"] = progress

            await db.scheduler_executions.insert_one(execution_record)

            # 记录日志
            if status == "success":
                logger.info(f"✅ [任务执行] {job_name} 执行成功，耗时: {execution_time:.2f}秒")
            elif status == "failed":
                logger.error(f"❌ [任务执行] {job_name} 执行失败: {error_message}")
            elif status == "missed":
                logger.warning(f"⚠️ [任务执行] {job_name} 错过执行时间")
            elif status == "running":
                trigger_type = "手动触发" if is_manual else "自动触发"
                logger.info(f"🔄 [任务执行] {job_name} 开始执行 ({trigger_type})，进度: {progress}%")

            # 🔥 更新Redis缓存（异步）
            await self._update_redis_execution_cache(
                job_id=job_id,
                status=status,
                progress=progress,
                execution_time=execution_time,
                error_message=error_message,
                scheduled_time=scheduled_time_naive
            )

        except Exception as e:
            logger.error(f"❌ 记录任务执行历史失败: {e}")

    async def _update_redis_execution_cache(
        self,
        job_id: str,
        status: str,
        progress: int = None,
        execution_time: float = None,
        error_message: str = None,
        scheduled_time: datetime = None
    ):
        """
        更新Redis中的任务执行缓存

        Args:
            job_id: 任务ID
            status: 状态
            progress: 进度
            execution_time: 执行时长
            error_message: 错误信息
            scheduled_time: 计划执行时间
        """
        try:
            import json
            from app.core.redis_client import RedisKeys
            from app.core.database import get_redis_client
            
            # 使用系统统一的异步Redis客户端
            redis_client = get_redis_client()
            
            # 构建执行数据
            execution_data = {
                "job_id": job_id,
                "status": status,
                "updated_at": get_utc8_now().isoformat()
            }
            
            if progress is not None:
                execution_data["progress"] = progress
            if execution_time is not None:
                execution_data["execution_time"] = execution_time
            if error_message:
                execution_data["error_message"] = error_message
            if scheduled_time:
                execution_data["scheduled_time"] = scheduled_time.isoformat() if isinstance(scheduled_time, datetime) else str(scheduled_time)
            
            # 存储执行记录
            execution_key = RedisKeys.SCHEDULER_JOB_EXECUTION.format(job_id=job_id)
            await redis_client.setex(
                execution_key,
                86400,  # 24小时TTL
                json.dumps(execution_data, ensure_ascii=False, default=str)
            )
            
            # 更新状态（简化版本）
            status_key = RedisKeys.SCHEDULER_JOB_STATUS.format(job_id=job_id)
            status_data = {
                "job_id": job_id,
                "status": status,
                "updated_at": get_utc8_now().isoformat()
            }
            if progress is not None:
                status_data["progress"] = progress
            
            await redis_client.setex(
                status_key,
                86400,
                json.dumps(status_data, ensure_ascii=False, default=str)
            )
            
            # 如果任务完成（success/failed），清理进度缓存
            if status in ["success", "failed"]:
                progress_key = RedisKeys.SCHEDULER_JOB_PROGRESS.format(job_id=job_id)
                await redis_client.delete(progress_key)
                
        except Exception as redis_error:
            # Redis更新失败不影响主流程，只记录日志
            logger.debug(f"⚠️ 更新Redis执行缓存失败（不影响主流程）: {redis_error}")

    async def _record_job_action(
        self,
        job_id: str,
        action: str,
        status: str,
        error_message: str = None
    ):
        """
        记录任务操作历史

        Args:
            job_id: 任务ID
            action: 操作类型 (pause/resume/trigger)
            status: 状态 (success/failed)
            error_message: 错误信息
        """
        try:
            db = self._get_db()
            await db.scheduler_history.insert_one({
                "job_id": job_id,
                "action": action,
                "status": status,
                "error_message": error_message,
                "timestamp": get_utc8_now()
            })
        except Exception as e:
            logger.error(f"❌ 记录任务操作历史失败: {e}")

    async def _get_job_metadata(self, job_id: str) -> Optional[Dict[str, Any]]:
        """
        获取任务元数据（触发器名称和备注）

        Args:
            job_id: 任务ID

        Returns:
            元数据字典，如果不存在则返回None
        """
        try:
            db = self._get_db()
            metadata = await db.scheduler_metadata.find_one({"job_id": job_id})
            if metadata:
                metadata.pop("_id", None)
                return metadata
            return None
        except Exception as e:
            logger.error(f"❌ 获取任务 {job_id} 元数据失败: {e}")
            return None

    async def update_job_metadata(
        self,
        job_id: str,
        display_name: Optional[str] = None,
        description: Optional[str] = None
    ) -> bool:
        """
        更新任务元数据

        Args:
            job_id: 任务ID
            display_name: 触发器名称
            description: 备注

        Returns:
            是否成功
        """
        try:
            # 检查任务是否存在
            job = self.scheduler.get_job(job_id)
            if not job:
                logger.error(f"❌ 任务 {job_id} 不存在")
                return False

            db = self._get_db()
            update_data = {
                "job_id": job_id,
                "updated_at": get_utc8_now()
            }

            if display_name is not None:
                update_data["display_name"] = display_name
            if description is not None:
                update_data["description"] = description

            # 使用 upsert 更新或插入
            await db.scheduler_metadata.update_one(
                {"job_id": job_id},
                {"$set": update_data},
                upsert=True
            )

            logger.info(f"✅ 任务 {job_id} 元数据已更新")
            return True
        except Exception as e:
            logger.error(f"❌ 更新任务 {job_id} 元数据失败: {e}")
            return False


# 全局服务实例
_scheduler_service: Optional[SchedulerService] = None
_scheduler_instance: Optional[AsyncIOScheduler] = None


def set_scheduler_instance(scheduler: AsyncIOScheduler):
    """
    设置调度器实例
    
    Args:
        scheduler: APScheduler调度器实例
    """
    global _scheduler_instance
    _scheduler_instance = scheduler
    logger.info("✅ 调度器实例已设置")


def get_scheduler_service() -> SchedulerService:
    """
    获取调度器服务实例

    Returns:
        调度器服务实例
    """
    global _scheduler_service, _scheduler_instance

    if _scheduler_instance is None:
        raise RuntimeError("调度器实例未设置，请先调用 set_scheduler_instance()")

    if _scheduler_service is None:
        _scheduler_service = SchedulerService(_scheduler_instance)
        logger.info("✅ 调度器服务实例已创建")

    return _scheduler_service


async def update_job_progress(
    job_id: str,
    progress: int,
    message: str = None,
    current_item: str = None,
    total_items: int = None,
    processed_items: int = None
):
    """
    更新任务执行进度（供定时任务内部调用）

    Args:
        job_id: 任务ID
        progress: 进度百分比（0-100）
        message: 进度消息
        current_item: 当前处理项
        total_items: 总项数
        processed_items: 已处理项数
    """
    try:
        import json
        from pymongo import MongoClient
        from app.core.config import settings
        from app.core.redis_client import RedisKeys

        # 使用同步客户端避免事件循环冲突
        sync_client = MongoClient(settings.MONGO_URI)
        sync_db = sync_client[settings.MONGODB_DATABASE]

        # 🔥 查找最近的执行记录（优先查找running/suspended状态，用于恢复）
        # 如果是恢复操作，应该复用挂起的执行记录
        # 先查找running/suspended状态的记录（恢复时需要复用）
        # 🔥 添加时间限制（最近10分钟），避免找到太旧的记录
        from datetime import timedelta
        ten_minutes_ago = get_utc8_now() - timedelta(minutes=10)
        
        latest_execution = sync_db.scheduler_executions.find_one(
            {
                "job_id": job_id,
                "status": {"$in": ["running", "suspended"]},
                "timestamp": {"$gte": ten_minutes_ago}
            },
            sort=[("timestamp", -1)]
        )
        # 如果没有running/suspended记录，再查找success/failed记录（最近10分钟）
        if not latest_execution:
            latest_execution = sync_db.scheduler_executions.find_one(
                {
                    "job_id": job_id,
                    "status": {"$in": ["success", "failed"]},
                    "timestamp": {"$gte": ten_minutes_ago}
                },
                sort=[("timestamp", -1)]
            )

        # 🔥 先确定开始时间，用于后续保存到Redis
        started_at = None
        execution_timestamp = None
        
        if latest_execution:
            # 检查是否有取消请求
            if latest_execution.get("cancel_requested"):
                sync_client.close()
                logger.warning(f"⚠️ 任务 {job_id} 收到取消请求，即将停止")
                raise TaskCancelledException(f"任务 {job_id} 已被用户取消")

            # 🔥 更新现有记录
            # 如果进度是100%，状态应该是success；否则保持running
            status = "success" if progress >= 100 else "running"
            update_data = {
                "progress": progress,
                "status": status,
                "updated_at": get_utc8_now()
            }
            
            # 🔥 如果任务完成，记录完成时间
            if progress >= 100:
                update_data["finished_at"] = get_utc8_now()
                logger.info(f"✅ 任务 {job_id} 已完成，状态更新为success")

            if message:
                update_data["progress_message"] = message
            if current_item:
                update_data["current_item"] = current_item
            if total_items is not None:
                update_data["total_items"] = total_items
            if processed_items is not None:
                update_data["processed_items"] = processed_items

            sync_db.scheduler_executions.update_one(
                {"_id": latest_execution["_id"]},
                {"$set": update_data}
            )
            
            # 从现有记录获取开始时间
            started_at = latest_execution.get("timestamp") or latest_execution.get("scheduled_time")
        else:
            # 创建新的执行记录（任务刚开始）
            from apscheduler.schedulers.asyncio import AsyncIOScheduler

            # 获取任务名称和kwargs
            job_name = job_id
            job_kwargs = {}
            if _scheduler_instance:
                job = _scheduler_instance.get_job(job_id)
                if job:
                    job_name = job.name
                    job_kwargs = job.kwargs.copy() if job.kwargs else {}

            # 🔥 记录开始时间
            execution_timestamp = get_utc8_now()
            started_at = execution_timestamp

            # 🔥 判断是否是手动触发（通过检查 job_kwargs 中是否有 _manual_trigger 标记）
            is_manual = job_kwargs.get("_manual_trigger", False) or job_kwargs.get("_force_execute", False)

            execution_record = {
                "job_id": job_id,
                "job_name": job_name,
                "status": "running",
                "progress": progress,
                "scheduled_time": execution_timestamp,
                "timestamp": execution_timestamp,
                "is_manual": is_manual,  # 🔥 根据 _manual_trigger 标记设置 is_manual
                "job_kwargs": job_kwargs  # 🔥 保存任务的kwargs，用于恢复时传递参数
            }

            if message:
                execution_record["progress_message"] = message
            if current_item:
                execution_record["current_item"] = current_item
            if total_items is not None:
                execution_record["total_items"] = total_items
            if processed_items is not None:
                execution_record["processed_items"] = processed_items

            sync_db.scheduler_executions.insert_one(execution_record)

        sync_client.close()

        # 🔥 同时更新Redis缓存（使用系统统一的同步Redis客户端）
        try:
            from app.core.database import get_redis_sync_client
            
            # 获取系统统一的同步Redis客户端
            redis_sync = get_redis_sync_client()
            
            # 🔥 如果还没有获取到开始时间，尝试从Redis获取（兼容旧数据）
            if not started_at:
                try:
                    from app.core.redis_client import RedisKeys
                    progress_key = RedisKeys.SCHEDULER_JOB_PROGRESS.format(job_id=job_id)
                    existing_progress_str = redis_sync.get(progress_key)
                    if existing_progress_str:
                        existing_progress = json.loads(existing_progress_str)
                        if existing_progress.get("started_at"):
                            started_at = existing_progress["started_at"]
                except Exception:
                    pass
            
            # 如果还是没有，使用当前时间（兜底方案）
            if not started_at:
                started_at = get_utc8_now()
            
            # 确保started_at是字符串格式
            if hasattr(started_at, 'isoformat'):
                started_at_str = started_at.isoformat()
            elif isinstance(started_at, str):
                started_at_str = started_at
            else:
                started_at_str = str(started_at)
            
            # 🔥 根据进度确定状态：如果进度是100%，状态应该是success；否则保持running
            # 注意：这里使用与MongoDB相同的逻辑，确保一致性
            redis_status = "success" if progress >= 100 else "running"
            
            progress_data = {
                "job_id": job_id,
                "progress": progress,
                "status": redis_status,  # 🔥 使用计算出的状态，而不是硬编码为running
                "started_at": started_at_str,
                "updated_at": get_utc8_now().isoformat()
            }
            if message:
                progress_data["message"] = message
            if current_item:
                progress_data["current_item"] = current_item
            if total_items is not None:
                progress_data["total_items"] = total_items
            if processed_items is not None:
                progress_data["processed_items"] = processed_items
            
            # 🔥 如果进度是100%，添加完成时间
            if progress >= 100:
                progress_data["finished_at"] = get_utc8_now().isoformat()
            
            # 存储到Redis，设置24小时过期（任务完成后会清理）
            progress_key = RedisKeys.SCHEDULER_JOB_PROGRESS.format(job_id=job_id)
            redis_sync.setex(
                progress_key,
                86400,  # 24小时TTL
                json.dumps(progress_data, ensure_ascii=False)
            )
            
            # 同时存储状态（简化版本，便于快速查询）
            status_key = RedisKeys.SCHEDULER_JOB_STATUS.format(job_id=job_id)
            status_data = {
                "job_id": job_id,
                "status": redis_status,  # 🔥 使用计算出的状态，而不是硬编码为running
                "progress": progress,
                "updated_at": get_utc8_now().isoformat()
            }
            redis_sync.setex(
                status_key,
                86400,
                json.dumps(status_data, ensure_ascii=False)
            )
            
        except Exception as redis_error:
            # Redis更新失败不影响主流程，只记录日志
            logger.debug(f"⚠️ 更新Redis缓存失败（不影响主流程）: {redis_error}")

    except Exception as e:
        logger.error(f"❌ 更新任务进度失败: {e}")


async def mark_job_completed(job_id: str, stats: Optional[Dict[str, Any]] = None, error_message: Optional[str] = None):
    """
    标记任务为已完成状态（通用函数）
    
    Args:
        job_id: 任务ID
        stats: 同步统计信息（可选）
        error_message: 错误消息（可选，如果有则标记为失败）
    """
    try:
        from pymongo import MongoClient
        from app.core.config import settings

        logger.info(f"✅ [任务完成] 开始标记任务 {job_id} 为已完成状态")

        # 使用同步 PyMongo 客户端（避免事件循环冲突）
        sync_client = MongoClient(settings.MONGO_URI)
        sync_db = sync_client[settings.MONGODB_DATABASE]

        # 🔥 改进查找逻辑：
        # 1. 优先查找 running 状态的记录
        # 2. 如果没有，查找最近的 suspended/running 记录（5分钟内，处理恢复挂起任务的情况）
        # 3. 如果还没有，查找最近的 success 记录（5分钟内，处理 update_job_progress 已将状态更新为 success 的情况）
        # 4. 如果还没有，查找最近的任何状态记录（10分钟内，作为最后的兜底方案）
        from datetime import timedelta
        five_minutes_ago = get_utc8_now() - timedelta(minutes=5)
        ten_minutes_ago = get_utc8_now() - timedelta(minutes=10)
        
        # 🔍 调试：先查询所有相关记录
        all_recent_records = list(sync_db.scheduler_executions.find(
            {
                "job_id": job_id,
                "timestamp": {"$gte": ten_minutes_ago}
            },
            sort=[("timestamp", -1)]
        ).limit(5))
        
        if all_recent_records:
            logger.info(f"🔍 [调试] 找到 {len(all_recent_records)} 条最近10分钟内的记录:")
            for idx, rec in enumerate(all_recent_records):
                logger.info(f"   [{idx+1}] _id={rec.get('_id')}, status={rec.get('status')}, timestamp={rec.get('timestamp')}, progress={rec.get('progress')}")
        else:
            logger.warning(f"🔍 [调试] 未找到任务 {job_id} 最近10分钟内的任何记录")
        
        # 首先尝试查找 running 状态的记录
        execution = sync_db.scheduler_executions.find_one(
            {"job_id": job_id, "status": "running"},
            sort=[("timestamp", -1)]
        )
        
        # 如果没有找到 running 记录，尝试查找最近的 suspended 或 running 记录（可能是刚恢复的）
        if not execution:
            execution = sync_db.scheduler_executions.find_one(
                {
                    "job_id": job_id,
                    "status": {"$in": ["running", "suspended"]},
                    "timestamp": {"$gte": five_minutes_ago}
                },
                sort=[("timestamp", -1)]
            )
            if execution:
                logger.info(f"📝 找到最近的 suspended/running 记录（可能是恢复的任务）: {execution.get('_id')}, status={execution.get('status')}")
        
        # 🔥 如果还没有找到，尝试查找最近的 success 记录（可能是 update_job_progress 已将状态更新为 success）
        if not execution:
            execution = sync_db.scheduler_executions.find_one(
                {
                    "job_id": job_id,
                    "status": "success",
                    "timestamp": {"$gte": five_minutes_ago}
                },
                sort=[("timestamp", -1)]
            )
            if execution:
                logger.info(f"📝 找到最近的 success 记录（可能是 update_job_progress 已更新状态）: {execution.get('_id')}, 将更新为最终状态")
        
        # 🔥 最后的兜底方案：查找最近10分钟内的任何记录（按时间戳倒序，取最新的）
        if not execution:
            execution = sync_db.scheduler_executions.find_one(
                {
                    "job_id": job_id,
                    "timestamp": {"$gte": ten_minutes_ago}
                },
                sort=[("timestamp", -1)]
            )
            if execution:
                logger.info(f"📝 [兜底] 找到最近10分钟内的记录: {execution.get('_id')}, status={execution.get('status')}, timestamp={execution.get('timestamp')}")

        if not execution:
            logger.warning(f"⚠️ 未找到任务 {job_id} 的运行记录，无法标记为已完成")
            sync_client.close()
            return

        # 确定状态：如果有错误消息或 stats 中有错误，标记为 failed
        if error_message:
            status = "failed"
            update_data = {
                "status": status,
                "finished_at": get_utc8_now(),
                "updated_at": get_utc8_now(),
                "error_message": error_message[:500]  # 限制错误消息长度
            }
        elif stats:
            error_count = stats.get("error_count", 0)
            status = "success" if error_count == 0 else "failed"
            update_data = {
                "status": status,
                "progress": 100,
                "finished_at": get_utc8_now(),
                "updated_at": get_utc8_now(),
                "progress_message": f"同步完成：成功 {stats.get('success_count', 0)}/{stats.get('total_processed', 0)} 只股票"
            }
            
            # 如果有错误，添加错误信息
            if error_count > 0:
                error_messages = [e.get("error", "") for e in stats.get("errors", [])[:5]]  # 只取前5个错误
                update_data["error_message"] = f"同步完成但有 {error_count} 个错误: {', '.join(error_messages)}"
        else:
            # 没有统计信息，默认标记为成功
            status = "success"
            update_data = {
                "status": status,
                "progress": 100,
                "finished_at": get_utc8_now(),
                "updated_at": get_utc8_now(),
                "progress_message": "任务完成"
            }

        result = sync_db.scheduler_executions.update_one(
            {"_id": execution["_id"]},
            {"$set": update_data}
        )

        logger.info(f"✅ [任务完成] 任务 {job_id} 状态已更新为 {status}: matched={result.matched_count}, modified={result.modified_count}")

        # 🔥 更新或删除 Redis 缓存，确保前端能获取到最新的状态
        try:
            from app.core.database import get_redis_sync_client
            from app.core.redis_client import RedisKeys
            import json
            
            redis_sync = get_redis_sync_client()
            if redis_sync:
                # 🔥 从执行记录中获取完整信息，确保前端能获取到所有必要字段
                started_at = execution.get("timestamp") or execution.get("scheduled_time")
                finished_at = update_data.get("finished_at") or execution.get("finished_at")
                
                # 更新进度缓存（包含所有前端需要的字段）
                progress_key = RedisKeys.SCHEDULER_JOB_PROGRESS.format(job_id=job_id)
                progress_data = {
                    "job_id": job_id,
                    "progress": update_data.get("progress", 100),
                    "status": status,
                    "updated_at": get_utc8_now().isoformat(),
                    "started_at": started_at.isoformat() if started_at and hasattr(started_at, 'isoformat') else (str(started_at) if started_at else None)
                }
                if finished_at:
                    progress_data["finished_at"] = finished_at.isoformat() if hasattr(finished_at, 'isoformat') else str(finished_at)
                if update_data.get("progress_message"):
                    progress_data["message"] = update_data["progress_message"]
                if execution.get("current_item"):
                    progress_data["current_item"] = execution.get("current_item")
                if execution.get("total_items"):
                    progress_data["total_items"] = execution.get("total_items")
                if execution.get("processed_items") is not None:
                    progress_data["processed_items"] = execution.get("processed_items")
                
                redis_sync.setex(
                    progress_key,
                    86400,  # 24小时TTL
                    json.dumps(progress_data, ensure_ascii=False, default=str)
                )
                
                # 更新状态缓存
                status_key = RedisKeys.SCHEDULER_JOB_STATUS.format(job_id=job_id)
                status_data = {
                    "job_id": job_id,
                    "status": status,
                    "progress": update_data.get("progress", 100),
                    "updated_at": get_utc8_now().isoformat()
                }
                redis_sync.setex(
                    status_key,
                    86400,
                    json.dumps(status_data, ensure_ascii=False, default=str)
                )
                
                logger.info(f"✅ [任务完成] Redis缓存已更新: job_id={job_id}, status={status}, progress={update_data.get('progress', 100)}")
        except Exception as redis_error:
            logger.warning(f"⚠️ 更新Redis缓存失败（不影响主流程）: {redis_error}")

        sync_client.close()

    except Exception as e:
        logger.error(f"❌ 标记任务完成失败: {e}", exc_info=True)

