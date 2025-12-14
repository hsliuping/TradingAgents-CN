"""
工作流配置管理器

管理工作流的定义、配置和状态
"""

import logging
from typing import Dict, Any, Optional, List
from datetime import datetime

logger = logging.getLogger(__name__)


class WorkflowConfigManager:
    """
    工作流配置管理器（v2.0 新版）
    
    管理：
    1. 工作流的启用/禁用状态
    2. 工作流的执行模式（sequential/parallel/conditional）
    3. 工作流的节点和边定义
    4. 工作流的并行组配置
    
    优先级：数据库配置 > 代码默认配置
    """
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self._db = None
        self._cache = {}  # workflow_id -> definition
        self._cache_ttl = 300  # 5分钟缓存
        self._cache_time = {}
        self._initialized = True
    
    def set_database(self, db):
        """设置数据库连接"""
        self._db = db
        self._clear_cache()
    
    def _clear_cache(self):
        """清空缓存"""
        self._cache = {}
        self._cache_time = {}
    
    def _is_cache_valid(self, workflow_id: str) -> bool:
        """检查缓存是否有效"""
        if workflow_id not in self._cache_time:
            return False
        elapsed = (datetime.utcnow() - self._cache_time[workflow_id]).total_seconds()
        return elapsed < self._cache_ttl
    
    def get_workflow_definition(self, workflow_id: str) -> Optional[Dict[str, Any]]:
        """
        获取工作流定义
        
        Args:
            workflow_id: 工作流ID
            
        Returns:
            工作流定义字典，包含：
            - workflow_id: 工作流ID
            - name: 显示名称
            - description: 描述
            - enabled: 是否启用
            - execution_mode: 执行模式
            - nodes: 节点列表
            - edges: 边列表
            - parallel_groups: 并行组
            - config: 其他配置
        """
        # 检查缓存
        if workflow_id in self._cache and self._is_cache_valid(workflow_id):
            return self._cache[workflow_id]
        
        definition = None
        
        # 从数据库加载
        if self._db is not None:
            try:
                definition = self._db.workflow_definitions.find_one({"workflow_id": workflow_id})
                if definition:
                    # 移除 MongoDB 的 _id 字段
                    definition.pop("_id", None)
            except Exception as e:
                logger.warning(f"从数据库加载工作流定义失败: {e}")
        
        # 更新缓存
        if definition:
            self._cache[workflow_id] = definition
            self._cache_time[workflow_id] = datetime.utcnow()
        
        return definition
    
    def save_workflow_definition(self, definition: Dict[str, Any]) -> bool:
        """
        保存工作流定义到数据库
        
        Args:
            definition: 工作流定义字典
            
        Returns:
            是否成功
        """
        if self._db is None:
            logger.error("数据库未连接")
            return False
        
        workflow_id = definition.get("workflow_id")
        if not workflow_id:
            logger.error("定义缺少 workflow_id")
            return False
        
        try:
            definition["updated_at"] = datetime.utcnow().isoformat()
            self._db.workflow_definitions.update_one(
                {"workflow_id": workflow_id},
                {
                    "$set": definition,
                    "$setOnInsert": {"created_at": datetime.utcnow().isoformat()}
                },
                upsert=True
            )
            
            # 清除缓存
            if workflow_id in self._cache:
                del self._cache[workflow_id]
            if workflow_id in self._cache_time:
                del self._cache_time[workflow_id]
            
            logger.info(f"✅ 工作流定义已保存: {workflow_id}")
            return True
        except Exception as e:
            logger.error(f"保存工作流定义失败: {e}")
            return False
    
    def is_workflow_enabled(self, workflow_id: str) -> bool:
        """检查工作流是否启用"""
        definition = self.get_workflow_definition(workflow_id)
        return definition.get("enabled", False) if definition else False

    def enable_workflow(self, workflow_id: str) -> bool:
        """启用工作流"""
        return self._set_workflow_enabled(workflow_id, True)

    def disable_workflow(self, workflow_id: str) -> bool:
        """禁用工作流"""
        return self._set_workflow_enabled(workflow_id, False)

    def _set_workflow_enabled(self, workflow_id: str, enabled: bool) -> bool:
        """设置工作流启用状态"""
        if self._db is None:
            logger.error("数据库未连接")
            return False

        try:
            self._db.workflow_definitions.update_one(
                {"workflow_id": workflow_id},
                {
                    "$set": {
                        "enabled": enabled,
                        "updated_at": datetime.utcnow().isoformat()
                    }
                },
                upsert=True
            )

            # 清除缓存
            if workflow_id in self._cache:
                del self._cache[workflow_id]

            logger.info(f"✅ 工作流 {workflow_id} 已{'启用' if enabled else '禁用'}")
            return True
        except Exception as e:
            logger.error(f"设置工作流状态失败: {e}")
            return False

    def get_all_workflow_definitions(self, category: Optional[str] = None, enabled_only: bool = False) -> List[Dict[str, Any]]:
        """
        获取所有工作流定义

        Args:
            category: 可选，按分类筛选
            enabled_only: 是否只返回启用的工作流

        Returns:
            工作流定义列表
        """
        result = []

        if self._db is not None:
            try:
                query = {}
                if category:
                    query["category"] = category
                if enabled_only:
                    query["enabled"] = True

                result = list(self._db.workflow_definitions.find(query))
                # 移除 _id 字段
                for definition in result:
                    definition.pop("_id", None)
            except Exception as e:
                logger.warning(f"获取工作流定义列表失败: {e}")

        return result

    def update_workflow_execution_mode(self, workflow_id: str, execution_mode: str) -> bool:
        """
        更新工作流的执行模式

        Args:
            workflow_id: 工作流ID
            execution_mode: 执行模式（sequential/parallel/conditional）

        Returns:
            是否成功
        """
        if self._db is None:
            logger.error("数据库未连接")
            return False

        if execution_mode not in ["sequential", "parallel", "conditional"]:
            logger.error(f"无效的执行模式: {execution_mode}")
            return False

        try:
            self._db.workflow_definitions.update_one(
                {"workflow_id": workflow_id},
                {
                    "$set": {
                        "execution_mode": execution_mode,
                        "updated_at": datetime.utcnow().isoformat()
                    }
                },
                upsert=True
            )

            # 清除缓存
            if workflow_id in self._cache:
                del self._cache[workflow_id]

            logger.info(f"✅ 工作流执行模式已更新: {workflow_id} -> {execution_mode}")
            return True
        except Exception as e:
            logger.error(f"更新工作流执行模式失败: {e}")
            return False

    def update_workflow_nodes(self, workflow_id: str, nodes: List[Dict[str, Any]]) -> bool:
        """
        更新工作流的节点定义

        Args:
            workflow_id: 工作流ID
            nodes: 节点列表

        Returns:
            是否成功
        """
        if self._db is None:
            logger.error("数据库未连接")
            return False

        try:
            self._db.workflow_definitions.update_one(
                {"workflow_id": workflow_id},
                {
                    "$set": {
                        "nodes": nodes,
                        "updated_at": datetime.utcnow().isoformat()
                    }
                },
                upsert=True
            )

            # 清除缓存
            if workflow_id in self._cache:
                del self._cache[workflow_id]

            logger.info(f"✅ 工作流节点已更新: {workflow_id}")
            return True
        except Exception as e:
            logger.error(f"更新工作流节点失败: {e}")
            return False

    def update_workflow_edges(self, workflow_id: str, edges: List[Dict[str, Any]]) -> bool:
        """
        更新工作流的边定义

        Args:
            workflow_id: 工作流ID
            edges: 边列表

        Returns:
            是否成功
        """
        if self._db is None:
            logger.error("数据库未连接")
            return False

        try:
            self._db.workflow_definitions.update_one(
                {"workflow_id": workflow_id},
                {
                    "$set": {
                        "edges": edges,
                        "updated_at": datetime.utcnow().isoformat()
                    }
                },
                upsert=True
            )

            # 清除缓存
            if workflow_id in self._cache:
                del self._cache[workflow_id]

            logger.info(f"✅ 工作流边已更新: {workflow_id}")
            return True
        except Exception as e:
            logger.error(f"更新工作流边失败: {e}")
            return False

    def delete_workflow_definition(self, workflow_id: str) -> bool:
        """
        删除工作流定义

        Args:
            workflow_id: 工作流ID

        Returns:
            是否成功
        """
        if self._db is None:
            logger.error("数据库未连接")
            return False

        try:
            result = self._db.workflow_definitions.delete_one({"workflow_id": workflow_id})

            # 清除缓存
            if workflow_id in self._cache:
                del self._cache[workflow_id]
            if workflow_id in self._cache_time:
                del self._cache_time[workflow_id]

            if result.deleted_count > 0:
                logger.info(f"✅ 工作流定义已删除: {workflow_id}")
                return True
            else:
                logger.warning(f"⚠️ 工作流定义不存在: {workflow_id}")
                return False
        except Exception as e:
            logger.error(f"删除工作流定义失败: {e}")
            return False

