"""
状态注册表

管理工作流状态 Schema 的缓存和查询
"""

import logging
import threading
from typing import Dict, List, Optional, Type

from .models import WorkflowStateSchema, AgentIODefinition
from .builder import StateSchemaBuilder

logger = logging.getLogger(__name__)


class StateRegistry:
    """
    状态注册表（单例模式）
    
    缓存和管理工作流状态 Schema
    
    用法:
        registry = StateRegistry()
        
        # 获取或构建状态 Schema
        schema = registry.get_or_build(
            workflow_id="position_analysis",
            agent_ids=["pa_technical", "pa_fundamental", "pa_risk", "pa_advisor"]
        )
        
        # 获取 TypedDict 类
        state_class = registry.get_state_class("position_analysis")
    """
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(StateRegistry, cls).__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if not self._initialized:
            self._schemas: Dict[str, WorkflowStateSchema] = {}
            self._state_classes: Dict[str, Type] = {}
            self._builder = StateSchemaBuilder()
            self._initialized = True
    
    def get_or_build(
        self,
        workflow_id: str,
        agent_ids: List[str],
        force_rebuild: bool = False,
    ) -> WorkflowStateSchema:
        """
        获取或构建工作流状态 Schema
        
        Args:
            workflow_id: 工作流 ID
            agent_ids: Agent ID 列表
            force_rebuild: 是否强制重建
            
        Returns:
            WorkflowStateSchema 实例
        """
        if workflow_id in self._schemas and not force_rebuild:
            return self._schemas[workflow_id]
        
        schema = self._builder.build_from_agents(workflow_id, agent_ids)
        self._schemas[workflow_id] = schema
        
        # 同时生成 TypedDict 类
        self._state_classes[workflow_id] = self._builder.generate_typed_dict(schema)
        
        return schema
    
    def get_schema(self, workflow_id: str) -> Optional[WorkflowStateSchema]:
        """获取已缓存的状态 Schema"""
        return self._schemas.get(workflow_id)
    
    def get_state_class(self, workflow_id: str) -> Optional[Type]:
        """获取工作流的 TypedDict 状态类"""
        return self._state_classes.get(workflow_id)
    
    def register_schema(self, schema: WorkflowStateSchema) -> None:
        """手动注册状态 Schema"""
        self._schemas[schema.workflow_id] = schema
        self._state_classes[schema.workflow_id] = self._builder.generate_typed_dict(schema)
    
    def clear(self, workflow_id: Optional[str] = None) -> None:
        """清除缓存"""
        if workflow_id:
            self._schemas.pop(workflow_id, None)
            self._state_classes.pop(workflow_id, None)
        else:
            self._schemas.clear()
            self._state_classes.clear()
    
    def list_workflows(self) -> List[str]:
        """列出所有已注册的工作流 ID"""
        return list(self._schemas.keys())
    
    def get_field_source(self, workflow_id: str, field_name: str) -> Optional[str]:
        """获取字段的来源 Agent"""
        schema = self._schemas.get(workflow_id)
        if schema and field_name in schema.fields:
            return schema.fields[field_name].source_agent
        return None


# 全局注册表实例
_global_registry: Optional[StateRegistry] = None


def get_state_registry() -> StateRegistry:
    """获取全局状态注册表"""
    global _global_registry
    if _global_registry is None:
        _global_registry = StateRegistry()
    return _global_registry

