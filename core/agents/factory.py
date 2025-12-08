"""
智能体工厂

负责创建和配置智能体实例
"""

from typing import Any, Dict, Optional, Type

from .base import BaseAgent
from .config import AgentConfig, AgentMetadata
from .registry import AgentRegistry, get_registry


class AgentFactory:
    """
    智能体工厂
    
    用法:
        factory = AgentFactory()
        
        # 创建智能体实例
        agent = factory.create("market_analyst", config=my_config)
        
        # 批量创建
        agents = factory.create_many(["market_analyst", "news_analyst"])
    """
    
    def __init__(self, registry: Optional[AgentRegistry] = None):
        self.registry = registry or get_registry()
    
    def create(
        self,
        agent_id: str,
        config: Optional[AgentConfig] = None,
        **config_overrides
    ) -> BaseAgent:
        """
        创建智能体实例
        
        Args:
            agent_id: 智能体 ID
            config: 智能体配置
            **config_overrides: 配置覆盖参数
            
        Returns:
            初始化后的智能体实例
        """
        agent_class = self.registry.get(agent_id)
        
        if agent_class is None:
            raise ValueError(f"智能体 '{agent_id}' 未注册实现")
        
        # 合并配置
        if config is None:
            config = AgentConfig()
        
        for key, value in config_overrides.items():
            if hasattr(config, key):
                setattr(config, key, value)
        
        # 创建实例
        agent = agent_class(config)
        agent.initialize()
        
        return agent
    
    def create_many(
        self,
        agent_ids: list,
        shared_config: Optional[AgentConfig] = None,
        **config_overrides
    ) -> Dict[str, BaseAgent]:
        """
        批量创建智能体
        
        Args:
            agent_ids: 智能体 ID 列表
            shared_config: 共享配置
            **config_overrides: 配置覆盖
            
        Returns:
            {agent_id: agent_instance} 字典
        """
        agents = {}
        for agent_id in agent_ids:
            try:
                agents[agent_id] = self.create(
                    agent_id, 
                    config=shared_config, 
                    **config_overrides
                )
            except ValueError as e:
                # 记录警告但继续创建其他智能体
                print(f"警告: {e}")
        
        return agents
    
    def get_available_agents(self) -> list:
        """获取所有已注册实现的智能体 ID"""
        return [
            m.id for m in self.registry.list_all()
            if self.registry.is_registered(m.id)
        ]
    
    def get_agent_metadata(self, agent_id: str) -> Optional[AgentMetadata]:
        """获取智能体元数据"""
        return self.registry.get_metadata(agent_id)


# 便捷函数
def create_agent(
    agent_id: str,
    config: Optional[AgentConfig] = None,
    **kwargs
) -> BaseAgent:
    """
    便捷函数: 创建智能体
    
    用法:
        from core.agents import create_agent
        
        agent = create_agent("market_analyst", llm_provider="deepseek")
    """
    factory = AgentFactory()
    return factory.create(agent_id, config, **kwargs)

