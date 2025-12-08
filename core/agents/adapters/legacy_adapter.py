"""
遗留智能体适配器

将现有的函数式智能体包装为 BaseAgent 子类
"""

from typing import Any, Callable, Dict, Optional

from ..base import BaseAgent
from ..config import AgentMetadata, AgentConfig


class LegacyAgentAdapter(BaseAgent):
    """
    遗留智能体适配器
    
    将现有的函数式智能体（如 create_market_analyst）包装为 BaseAgent 子类
    
    用法:
        from tradingagents.agents.analysts.market_analyst import create_market_analyst
        
        adapter = LegacyAgentAdapter(
            metadata=BUILTIN_AGENTS["market_analyst"],
            factory_func=create_market_analyst,
            llm=my_llm,
            toolkit=my_toolkit
        )
        
        result = adapter.execute(state)
    """
    
    def __init__(
        self,
        metadata: AgentMetadata,
        factory_func: Callable,
        llm: Any,
        toolkit: Any,
        config: Optional[AgentConfig] = None
    ):
        """
        初始化适配器
        
        Args:
            metadata: 智能体元数据
            factory_func: 原始工厂函数 (如 create_market_analyst)
            llm: LLM 实例
            toolkit: 工具包实例
            config: 智能体配置
        """
        super().__init__(config)
        self._metadata = metadata
        self._factory_func = factory_func
        self._llm = llm
        self._toolkit = toolkit
        self._node_func: Optional[Callable] = None
    
    @classmethod
    def get_metadata(cls) -> AgentMetadata:
        """获取元数据 - 由实例提供"""
        raise NotImplementedError("LegacyAgentAdapter 的元数据由实例提供")
    
    def get_instance_metadata(self) -> AgentMetadata:
        """获取实例的元数据"""
        return self._metadata
    
    def initialize(self) -> None:
        """初始化适配器"""
        # 调用原始工厂函数创建节点函数
        self._node_func = self._factory_func(self._llm, self._toolkit)
    
    def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行智能体逻辑
        
        Args:
            state: 当前状态字典
            
        Returns:
            更新后的状态字典
        """
        if self._node_func is None:
            self.initialize()
        
        return self._node_func(state)
    
    @property
    def agent_id(self) -> str:
        """智能体 ID"""
        return self._metadata.id
    
    @property
    def agent_name(self) -> str:
        """智能体名称"""
        return self._metadata.name


def create_legacy_adapter(
    agent_id: str,
    llm: Any,
    toolkit: Any,
    config: Optional[AgentConfig] = None
) -> LegacyAgentAdapter:
    """
    便捷函数: 创建遗留智能体适配器
    
    Args:
        agent_id: 智能体 ID (如 "market_analyst")
        llm: LLM 实例
        toolkit: 工具包实例
        config: 智能体配置
        
    Returns:
        配置好的适配器实例
    """
    from ..config import BUILTIN_AGENTS
    
    # 获取元数据
    metadata = BUILTIN_AGENTS.get(agent_id)
    if metadata is None:
        raise ValueError(f"未知的智能体 ID: {agent_id}")
    
    # 获取工厂函数
    factory_func = _get_factory_func(agent_id)
    
    # 创建适配器
    adapter = LegacyAgentAdapter(
        metadata=metadata,
        factory_func=factory_func,
        llm=llm,
        toolkit=toolkit,
        config=config
    )
    
    adapter.initialize()
    return adapter


def _get_factory_func(agent_id: str) -> Callable:
    """获取智能体的工厂函数"""
    factory_map = {
        "market_analyst": "tradingagents.agents.analysts.market_analyst:create_market_analyst",
        "news_analyst": "tradingagents.agents.analysts.news_analyst:create_news_analyst",
        "fundamentals_analyst": "tradingagents.agents.analysts.fundamentals_analyst:create_fundamentals_analyst",
        "social_analyst": "tradingagents.agents.analysts.social_media_analyst:create_social_media_analyst",
        "bull_researcher": "tradingagents.agents.researchers.bull_researcher:create_bull_researcher",
        "bear_researcher": "tradingagents.agents.researchers.bear_researcher:create_bear_researcher",
        "trader": "tradingagents.agents.trader.trader:create_trader",
        "risk_manager": "tradingagents.agents.managers.risk_manager:create_risk_manager",
        "research_manager": "tradingagents.agents.managers.research_manager:create_research_manager",
    }
    
    if agent_id not in factory_map:
        raise ValueError(f"未找到智能体 '{agent_id}' 的工厂函数")
    
    module_path, func_name = factory_map[agent_id].rsplit(":", 1)
    
    import importlib
    module = importlib.import_module(module_path)
    return getattr(module, func_name)

