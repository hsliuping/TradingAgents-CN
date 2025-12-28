"""
任务分析服务

基于 UnifiedAnalysisTask 模型的分析任务管理服务
提供统一的任务创建、执行、查询接口
"""

from typing import Dict, Any, Optional, List, Callable
import logging
import uuid
from datetime import datetime

from app.models.analysis import (
    UnifiedAnalysisTask,
    AnalysisTaskType,
    AnalysisStatus
)
from app.models.user import PyObjectId
from app.services.unified_analysis_engine import UnifiedAnalysisEngine
from app.services.workflow_registry import AnalysisWorkflowRegistry
from app.core.database import get_mongo_db
from app.utils.timezone import now_tz

logger = logging.getLogger(__name__)


class TaskAnalysisService:
    """任务分析服务
    
    基于 UnifiedAnalysisTask 模型的分析任务管理
    
    使用示例:
        service = TaskAnalysisService()
        
        # 创建并执行任务
        task = await service.create_and_execute_task(
            user_id=user_id,
            task_type=AnalysisTaskType.STOCK_ANALYSIS,
            task_params={"symbol": "000858", "market_type": "cn"}
        )
        
        # 查询任务
        task = await service.get_task(task_id)
        
        # 查询用户的所有任务
        tasks = await service.list_user_tasks(user_id)
    """
    
    def __init__(self):
        """初始化服务"""
        self.engine = UnifiedAnalysisEngine()
        self.db = get_mongo_db()
        self.collection = self.db.unified_analysis_tasks
        self.logger = logger
    
    async def create_task(
        self,
        user_id: PyObjectId,
        task_type: AnalysisTaskType,
        task_params: Dict[str, Any],
        engine_type: str = "auto",
        preference_type: str = "neutral",
        workflow_id: Optional[str] = None,
        batch_id: Optional[str] = None
    ) -> UnifiedAnalysisTask:
        """创建分析任务
        
        Args:
            user_id: 用户ID
            task_type: 任务类型
            task_params: 任务参数
            engine_type: 引擎类型 (auto/workflow/legacy/llm)
            preference_type: 分析偏好 (aggressive/neutral/conservative)
            workflow_id: 工作流ID（可选）
            batch_id: 批次ID（可选）
            
        Returns:
            创建的任务对象
        """
        # 生成任务ID
        task_id = str(uuid.uuid4())
        
        # 创建任务对象
        task = UnifiedAnalysisTask(
            task_id=task_id,
            user_id=user_id,
            task_type=task_type,
            task_params=task_params,
            engine_type=engine_type,
            preference_type=preference_type,
            workflow_id=workflow_id,
            batch_id=batch_id,
            status=AnalysisStatus.PENDING,
            created_at=now_tz()
        )
        
        # 保存到数据库
        await self._save_task(task)
        
        self.logger.info(f"✅ 创建任务: {task_id} (类型: {task_type})")
        
        return task
    
    async def execute_task(
        self,
        task: UnifiedAnalysisTask,
        progress_callback: Optional[Callable[[int, str], None]] = None
    ) -> UnifiedAnalysisTask:
        """执行分析任务
        
        Args:
            task: 任务对象
            progress_callback: 进度回调函数
            
        Returns:
            更新后的任务对象
        """
        self.logger.info(f"🚀 执行任务: {task.task_id}")
        
        try:
            # 执行任务
            result = await self.engine.execute_task(task, progress_callback)
            
            # 更新任务状态
            task.status = AnalysisStatus.COMPLETED
            task.result = result
            
            # 保存到数据库
            await self._update_task(task)
            
            self.logger.info(f"✅ 任务完成: {task.task_id}")
            
        except Exception as e:
            # 更新任务状态为失败
            task.status = AnalysisStatus.FAILED
            task.error_message = str(e)
            
            # 保存到数据库
            await self._update_task(task)
            
            self.logger.error(f"❌ 任务失败: {task.task_id} - {e}")
            raise
        
        return task
    
    async def create_and_execute_task(
        self,
        user_id: PyObjectId,
        task_type: AnalysisTaskType,
        task_params: Dict[str, Any],
        engine_type: str = "auto",
        preference_type: str = "neutral",
        workflow_id: Optional[str] = None,
        progress_callback: Optional[Callable] = None
    ) -> UnifiedAnalysisTask:
        """创建并执行任务（一步到位）
        
        Args:
            user_id: 用户ID
            task_type: 任务类型
            task_params: 任务参数
            engine_type: 引擎类型
            preference_type: 分析偏好
            workflow_id: 工作流ID
            progress_callback: 进度回调
            
        Returns:
            完成的任务对象
        """
        # 创建任务
        task = await self.create_task(
            user_id=user_id,
            task_type=task_type,
            task_params=task_params,
            engine_type=engine_type,
            preference_type=preference_type,
            workflow_id=workflow_id
        )
        
        # 执行任务
        task = await self.execute_task(task, progress_callback)

        return task

    async def get_task(self, task_id: str) -> Optional[UnifiedAnalysisTask]:
        """获取任务

        Args:
            task_id: 任务ID

        Returns:
            任务对象，如果不存在则返回 None
        """
        doc = await self.collection.find_one({"task_id": task_id})
        if not doc:
            return None

        return UnifiedAnalysisTask(**doc)

    async def list_user_tasks(
        self,
        user_id: PyObjectId,
        task_type: Optional[AnalysisTaskType] = None,
        status: Optional[AnalysisStatus] = None,
        limit: int = 50,
        skip: int = 0
    ) -> List[UnifiedAnalysisTask]:
        """列出用户的任务

        Args:
            user_id: 用户ID
            task_type: 任务类型过滤（可选）
            status: 状态过滤（可选）
            limit: 返回数量限制
            skip: 跳过数量

        Returns:
            任务列表
        """
        query = {"user_id": user_id}

        if task_type:
            query["task_type"] = task_type

        if status:
            query["status"] = status

        cursor = self.collection.find(query).sort("created_at", -1).skip(skip).limit(limit)

        tasks = []
        async for doc in cursor:
            tasks.append(UnifiedAnalysisTask(**doc))

        return tasks

    async def cancel_task(self, task_id: str) -> bool:
        """取消任务

        Args:
            task_id: 任务ID

        Returns:
            是否成功取消
        """
        result = await self.collection.update_one(
            {"task_id": task_id, "status": {"$in": [AnalysisStatus.PENDING, AnalysisStatus.PROCESSING]}},
            {"$set": {"status": AnalysisStatus.CANCELLED, "completed_at": now_tz()}}
        )

        return result.modified_count > 0

    async def _save_task(self, task: UnifiedAnalysisTask) -> None:
        """保存任务到数据库

        Args:
            task: 任务对象
        """
        doc = task.model_dump(by_alias=True)
        await self.collection.insert_one(doc)
        self.logger.debug(f"💾 任务已保存: {task.task_id}")

    async def _update_task(self, task: UnifiedAnalysisTask) -> None:
        """更新任务到数据库

        Args:
            task: 任务对象
        """
        doc = task.model_dump(by_alias=True, exclude={"_id"})
        await self.collection.update_one(
            {"task_id": task.task_id},
            {"$set": doc}
        )
        self.logger.debug(f"💾 任务已更新: {task.task_id}")

    async def get_task_statistics(self, user_id: PyObjectId) -> Dict[str, Any]:
        """获取用户的任务统计

        Args:
            user_id: 用户ID

        Returns:
            统计信息字典
        """
        pipeline = [
            {"$match": {"user_id": user_id}},
            {"$group": {
                "_id": "$status",
                "count": {"$sum": 1}
            }}
        ]

        cursor = self.collection.aggregate(pipeline)

        stats = {
            "total": 0,
            "pending": 0,
            "processing": 0,
            "completed": 0,
            "failed": 0,
            "cancelled": 0
        }

        async for doc in cursor:
            status = doc["_id"]
            count = doc["count"]
            stats[status] = count
            stats["total"] += count

        return stats


# 单例实例
_task_service: Optional[TaskAnalysisService] = None


def get_task_analysis_service() -> TaskAnalysisService:
    """获取任务分析服务单例"""
    global _task_service
    if _task_service is None:
        _task_service = TaskAnalysisService()
    return _task_service

