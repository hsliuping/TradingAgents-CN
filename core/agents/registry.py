"""
智能体注册表

管理所有可用智能体的注册和发现
"""

import threading
from typing import Dict, List, Optional, Type

from .base import BaseAgent
from .config import AgentCategory, AgentMetadata, LicenseTier, BUILTIN_AGENTS


class AgentRegistry:
    """
    智能体注册表 (单例模式)
    
    用法:
        registry = AgentRegistry()
        
        # 注册智能体
        registry.register(MyAgent)
        
        # 获取智能体
        agent_class = registry.get("market_analyst")
        
        # 列出所有智能体
        all_agents = registry.list_all()
    """
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(AgentRegistry, cls).__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if not self._initialized:
            self._agents: Dict[str, Type[BaseAgent]] = {}
            self._metadata: Dict[str, AgentMetadata] = {}
            self._load_builtin_metadata()
            self._initialized = True
    
    def _load_builtin_metadata(self) -> None:
        """加载内置智能体元数据"""
        for agent_id, metadata in BUILTIN_AGENTS.items():
            self._metadata[agent_id] = metadata
    
    def register(
        self,
        agent_class: Type[BaseAgent],
        override: bool = False
    ) -> None:
        """
        注册智能体类
        
        Args:
            agent_class: 智能体类
            override: 是否覆盖已存在的注册
        """
        metadata = agent_class.get_metadata()
        agent_id = metadata.id
        
        if agent_id in self._agents and not override:
            raise ValueError(f"智能体 '{agent_id}' 已注册，使用 override=True 覆盖")
        
        self._agents[agent_id] = agent_class
        self._metadata[agent_id] = metadata
    
    def unregister(self, agent_id: str) -> None:
        """注销智能体"""
        self._agents.pop(agent_id, None)
        # 不移除元数据，保留内置智能体的元数据
    
    def get(self, agent_id: str) -> Optional[Type[BaseAgent]]:
        """获取智能体类"""
        return self._agents.get(agent_id)
    
    def get_metadata(self, agent_id: str) -> Optional[AgentMetadata]:
        """获取智能体元数据"""
        return self._metadata.get(agent_id)
    
    def list_all(self) -> List[AgentMetadata]:
        """列出所有智能体元数据"""
        return list(self._metadata.values())
    
    def list_by_category(self, category: AgentCategory) -> List[AgentMetadata]:
        """按类别列出智能体"""
        cat_str = category.value if hasattr(category, 'value') else category
        return [
            m for m in self._metadata.values()
            if (m.category.value if hasattr(m.category, 'value') else m.category) == cat_str
        ]
    
    def list_by_tier(self, tier: LicenseTier) -> List[AgentMetadata]:
        """按许可证级别列出智能体"""
        tier_str = tier.value if hasattr(tier, 'value') else tier
        return [
            m for m in self._metadata.values()
            if (m.license_tier.value if hasattr(m.license_tier, 'value') else m.license_tier) == tier_str
        ]
    
    def list_available(self, current_tier: LicenseTier) -> List[AgentMetadata]:
        """
        列出当前许可证级别可用的智能体
        
        Args:
            current_tier: 当前许可证级别
            
        Returns:
            可用的智能体元数据列表
        """
        tier_order = ["free", "basic", "pro", "enterprise"]
        current_tier_str = current_tier.value if hasattr(current_tier, 'value') else current_tier
        current_index = tier_order.index(current_tier_str)

        def get_tier_index(metadata):
            tier = metadata.license_tier
            tier_str = tier.value if hasattr(tier, 'value') else tier
            return tier_order.index(tier_str)

        return [
            m for m in self._metadata.values()
            if get_tier_index(m) <= current_index
        ]
    
    def is_registered(self, agent_id: str) -> bool:
        """检查智能体是否已注册实现"""
        return agent_id in self._agents
    
    def has_metadata(self, agent_id: str) -> bool:
        """检查智能体元数据是否存在"""
        return agent_id in self._metadata
    
    def get_categories(self) -> List[AgentCategory]:
        """获取所有类别"""
        return list(set(m.category for m in self._metadata.values()))
    
    def clear(self) -> None:
        """清空注册表 (保留内置元数据)"""
        self._agents.clear()
        self._metadata.clear()
        self._load_builtin_metadata()


# 全局注册表实例
_global_registry: Optional[AgentRegistry] = None


def get_registry() -> AgentRegistry:
    """获取全局注册表实例"""
    global _global_registry
    if _global_registry is None:
        _global_registry = AgentRegistry()
    return _global_registry


def register_agent(agent_class: Type[BaseAgent]) -> Type[BaseAgent]:
    """
    装饰器: 注册智能体类
    
    用法:
        @register_agent
        class MyAgent(BaseAgent):
            metadata = AgentMetadata(...)
    """
    get_registry().register(agent_class)
    return agent_class

