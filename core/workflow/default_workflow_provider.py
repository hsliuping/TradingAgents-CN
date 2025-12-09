"""
默认工作流提供者

管理系统默认工作流和活动工作流的加载
"""

import logging
from datetime import datetime
from typing import Any, Dict, Optional

from .models import WorkflowDefinition
from .templates.default_workflow import DEFAULT_WORKFLOW
from .templates.simple_workflow import SIMPLE_WORKFLOW

logger = logging.getLogger(__name__)

# 系统默认工作流 ID
SYSTEM_DEFAULT_WORKFLOW_ID = "default_analysis"
SYSTEM_SIMPLE_WORKFLOW_ID = "simple_analysis"


class DefaultWorkflowProvider:
    """
    默认工作流提供者

    职责：
    1. 提供系统预置的默认工作流
    2. 确保默认工作流存在于数据库
    3. 获取当前活动工作流
    """

    # 系统预置工作流
    SYSTEM_WORKFLOWS = {
        SYSTEM_DEFAULT_WORKFLOW_ID: DEFAULT_WORKFLOW,
        SYSTEM_SIMPLE_WORKFLOW_ID: SIMPLE_WORKFLOW,
    }

    def __init__(self):
        self._db = None
        self._active_workflow_id: Optional[str] = None

    def _get_db(self):
        """获取数据库连接（懒加载）"""
        if self._db is None:
            try:
                from pymongo import MongoClient
                from app.core.config import settings
                client = MongoClient(settings.MONGO_URI)
                self._db = client[settings.MONGO_DB]
            except Exception as e:
                logger.warning(f"无法连接数据库: {e}")
                self._db = None
        return self._db

    def get_default_workflow(self) -> WorkflowDefinition:
        """获取系统默认工作流"""
        return DEFAULT_WORKFLOW

    def get_simple_workflow(self) -> WorkflowDefinition:
        """获取简单工作流"""
        return SIMPLE_WORKFLOW

    def get_system_workflow(self, workflow_id: str) -> Optional[WorkflowDefinition]:
        """获取系统预置工作流"""
        return self.SYSTEM_WORKFLOWS.get(workflow_id)

    def is_system_workflow(self, workflow_id: str) -> bool:
        """检查是否为系统预置工作流"""
        return workflow_id in self.SYSTEM_WORKFLOWS

    def get_active_workflow_id(self) -> str:
        """
        获取当前活动工作流 ID

        优先级：
        1. 数据库中的 system_configs.active_workflow_id
        2. 系统默认工作流
        """
        if self._active_workflow_id:
            return self._active_workflow_id

        db = self._get_db()
        if db is not None:
            try:
                config = db.system_configs.find_one(
                    {"is_active": True},
                    sort=[("version", -1)]
                )
                if config and config.get("active_workflow_id"):
                    self._active_workflow_id = config["active_workflow_id"]
                    logger.info(f"从数据库获取活动工作流: {self._active_workflow_id}")
                    return self._active_workflow_id
            except Exception as e:
                logger.warning(f"从数据库获取活动工作流失败: {e}")

        # 默认使用系统默认工作流
        self._active_workflow_id = SYSTEM_DEFAULT_WORKFLOW_ID
        return self._active_workflow_id

    def set_active_workflow_id(self, workflow_id: str) -> bool:
        """设置活动工作流 ID"""
        db = self._get_db()
        if db is None:
            logger.error("无法设置活动工作流: 数据库连接失败")
            return False

        try:
            db.system_configs.update_one(
                {"is_active": True},
                {
                    "$set": {
                        "active_workflow_id": workflow_id,
                        "updated_at": datetime.utcnow()
                    }
                },
                upsert=True
            )
            self._active_workflow_id = workflow_id
            logger.info(f"已设置活动工作流: {workflow_id}")
            return True
        except Exception as e:
            logger.error(f"设置活动工作流失败: {e}")
            return False

    def load_workflow(self, workflow_id: Optional[str] = None) -> WorkflowDefinition:
        """
        加载工作流

        Args:
            workflow_id: 工作流 ID，None 则加载活动工作流

        Returns:
            WorkflowDefinition
        """
        # 如果未指定，使用活动工作流
        if workflow_id is None:
            workflow_id = self.get_active_workflow_id()

        # 检查是否为系统预置工作流
        if self.is_system_workflow(workflow_id):
            logger.info(f"加载系统预置工作流: {workflow_id}")
            return self.SYSTEM_WORKFLOWS[workflow_id]

        # 从数据库加载
        db = self._get_db()
        if db is not None:
            try:
                doc = db.workflows.find_one({"id": workflow_id})
                if doc:
                    # 移除 MongoDB 的 _id 字段
                    doc.pop("_id", None)
                    logger.info(f"从数据库加载工作流: {workflow_id}")
                    return WorkflowDefinition.from_dict(doc)
            except Exception as e:
                logger.error(f"从数据库加载工作流失败: {e}")

        # 回退到默认工作流
        logger.warning(f"工作流 {workflow_id} 不存在，使用默认工作流")
        return DEFAULT_WORKFLOW

    def ensure_system_workflows_exist(self) -> Dict[str, bool]:
        """
        确保系统预置工作流存在于数据库

        Returns:
            Dict[workflow_id, created]: 是否新创建
        """
        results = {}
        db = self._get_db()

        if db is None:
            logger.warning("无法确保系统工作流存在: 数据库连接失败")
            return {wf_id: False for wf_id in self.SYSTEM_WORKFLOWS}

        for wf_id, workflow in self.SYSTEM_WORKFLOWS.items():
            try:
                existing = db.workflows.find_one({"id": wf_id})
                if existing:
                    results[wf_id] = False
                    logger.debug(f"系统工作流已存在: {wf_id}")
                else:
                    # 插入新工作流
                    doc = workflow.to_dict()
                    doc["created_at"] = datetime.utcnow().isoformat()
                    doc["updated_at"] = datetime.utcnow().isoformat()
                    doc["created_by"] = "system"
                    doc["is_system"] = True  # 标记为系统工作流
                    db.workflows.insert_one(doc)
                    results[wf_id] = True
                    logger.info(f"已创建系统工作流: {wf_id}")
            except Exception as e:
                logger.error(f"确保系统工作流存在失败 {wf_id}: {e}")
                results[wf_id] = False

        return results


# 单例实例
_default_provider: Optional[DefaultWorkflowProvider] = None


def get_default_workflow_provider() -> DefaultWorkflowProvider:
    """获取默认工作流提供者单例"""
    global _default_provider
    if _default_provider is None:
        _default_provider = DefaultWorkflowProvider()
    return _default_provider

