#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
定时任务管理服务
提供定时任务的查询、暂停、恢复、手动触发等功能
"""

import asyncio
from typing import List, Dict, Any, Optional
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.job import Job

from app.core.database import get_mongo_db
from tradingagents.utils.logging_manager import get_logger

logger = get_logger(__name__)


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
    
    def _get_db(self):
        """获取数据库连接"""
        if self.db is None:
            self.db = get_mongo_db()
        return self.db
    
    async def list_jobs(self) -> List[Dict[str, Any]]:
        """
        获取所有定时任务列表

        Returns:
            任务列表
        """
        jobs = []
        for job in self.scheduler.get_jobs():
            job_dict = self._job_to_dict(job)
            # 获取任务元数据（触发器名称和备注）
            metadata = await self._get_job_metadata(job.id)
            if metadata:
                job_dict["display_name"] = metadata.get("display_name")
                job_dict["description"] = metadata.get("description")
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
    
    async def trigger_job(self, job_id: str, kwargs: Optional[Dict[str, Any]] = None) -> bool:
        """
        手动触发任务执行

        注意：如果任务处于暂停状态，会先临时恢复任务，执行一次后不会自动暂停

        Args:
            job_id: 任务ID
            kwargs: 传递给任务函数的关键字参数（可选）

        Returns:
            是否成功
        """
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
            if kwargs:
                # 获取任务原有的 kwargs
                original_kwargs = job.kwargs.copy() if job.kwargs else {}
                # 合并新的 kwargs
                merged_kwargs = {**original_kwargs, **kwargs}
                # 修改任务的 kwargs
                job.modify(kwargs=merged_kwargs)
                logger.info(f"📝 任务 {job_id} 参数已更新: {kwargs}")

            # 手动触发任务 - 使用带时区的当前时间
            from datetime import timezone
            now = datetime.now(timezone.utc)
            job.modify(next_run_time=now)
            logger.info(f"🚀 手动触发任务 {job_id} (next_run_time={now}, was_paused={was_paused}, kwargs={kwargs})")

            # 记录操作历史
            action_note = f"手动触发执行 (暂停状态: {was_paused}"
            if kwargs:
                action_note += f", 参数: {kwargs}"
            action_note += ")"
            await self._record_job_action(job_id, "trigger", "success", action_note)
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
            "timestamp": datetime.now().isoformat()
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
                "timestamp": datetime.now()
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
                "updated_at": datetime.now()
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

