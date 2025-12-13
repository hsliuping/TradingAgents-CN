"""
智能体工厂

负责创建和配置智能体实例

v2.0 新特性:
- 支持从配置或数据库动态加载工具
- 支持 LangChain LLM 集成
"""

import logging
from typing import Any, Dict, Optional, Type, List

from langchain_core.language_models import BaseChatModel

from .base import BaseAgent
from .config import AgentConfig, AgentMetadata
from .registry import AgentRegistry, get_registry

logger = logging.getLogger(__name__)


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
        llm: Optional[BaseChatModel] = None,
        tool_ids: Optional[List[str]] = None,
        **config_overrides
    ) -> BaseAgent:
        """
        创建智能体实例

        Args:
            agent_id: 智能体 ID
            config: 智能体配置（旧版）
            llm: LangChain LLM 实例（新版）
            tool_ids: 工具 ID 列表（新版，可选）
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

        # v2.0: 如果提供了 llm 和 tool_ids，使用新版初始化
        if llm is not None:
            logger.info(f"使用 v2.0 方式创建 Agent: {agent_id}")
            agent = agent_class(config=config, llm=llm, tool_ids=tool_ids)
        else:
            # 旧版初始化
            logger.info(f"使用旧版方式创建 Agent: {agent_id}")
            agent = agent_class(config)

        # 初始化（如果需要）
        if hasattr(agent, 'initialize'):
            agent.initialize()

        return agent

    def create_with_dynamic_tools(
        self,
        agent_id: str,
        llm: BaseChatModel,
        config: Optional[AgentConfig] = None
    ) -> BaseAgent:
        """
        v2.0: 创建智能体实例，自动从配置加载工具

        Args:
            agent_id: 智能体 ID
            llm: LangChain LLM 实例
            config: 智能体配置（可选）

        Returns:
            初始化后的智能体实例
        """
        # 从配置加载工具列表
        from core.config.binding_manager import BindingManager
        tool_ids = BindingManager().get_tools_for_agent(agent_id)

        if not tool_ids:
            # 降级：使用元数据中的默认工具
            metadata = self.registry.get_metadata(agent_id)
            if metadata:
                tool_ids = getattr(metadata, 'default_tools', None) or getattr(metadata, 'tools', [])

        logger.info(f"为 Agent '{agent_id}' 加载工具: {tool_ids}")

        return self.create(
            agent_id=agent_id,
            config=config,
            llm=llm,
            tool_ids=tool_ids
        )
    
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
    llm: Optional[BaseChatModel] = None,
    tool_ids: Optional[List[str]] = None,
    **kwargs
) -> BaseAgent:
    """
    便捷函数: 创建智能体

    用法:
        from core.agents import create_agent

        # 旧版
        agent = create_agent("market_analyst", llm_provider="deepseek")

        # 新版（v2.0）
        from langchain_openai import ChatOpenAI
        llm = ChatOpenAI(model="gpt-4")
        agent = create_agent("market_analyst", llm=llm, tool_ids=["get_stock_market_data_unified"])
    """
    factory = AgentFactory()
    return factory.create(agent_id, config, llm=llm, tool_ids=tool_ids, **kwargs)


def create_agent_with_dynamic_tools(
    agent_id: str,
    llm: BaseChatModel,
    config: Optional[AgentConfig] = None
) -> BaseAgent:
    """
    v2.0 便捷函数: 创建智能体，自动从配置加载工具

    用法:
        from langchain_openai import ChatOpenAI
        from core.agents import create_agent_with_dynamic_tools

        llm = ChatOpenAI(model="gpt-4")
        agent = create_agent_with_dynamic_tools("market_analyst", llm)
    """
    factory = AgentFactory()
    return factory.create_with_dynamic_tools(agent_id, llm, config)

