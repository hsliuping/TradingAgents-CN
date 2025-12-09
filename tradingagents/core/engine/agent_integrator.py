# tradingagents/core/engine/agent_integrator.py
"""
Agent 集成器

桥接 StockAnalysisEngine 与现有的 Agent 实现：
- 创建 Agent 实例（使用现有的 create_xxx 工厂函数）
- 转换 AnalysisContext 与 AgentState
- 调用 Agent 并提取结果
"""

from typing import Any, Dict, Optional, Callable, Tuple

from tradingagents.utils.logging_init import get_logger

from .analysis_context import AnalysisContext
from .data_contract import DataLayer

logger = get_logger("default")


class AgentIntegrator:
    """
    Agent 集成器
    
    负责：
    1. 创建和管理 Agent 实例
    2. 转换 AnalysisContext <-> AgentState
    3. 执行 Agent 并提取结果
    """
    
    # 分析师 ID 到工厂函数名的映射
    ANALYST_FACTORY_MAP = {
        "market_analyst": "create_market_analyst",
        "news_analyst": "create_news_analyst",
        "sentiment_analyst": "create_social_media_analyst",
        "fundamentals_analyst": "create_fundamentals_analyst",
    }
    
    # 分析师输出字段映射
    ANALYST_OUTPUT_MAP = {
        "market_analyst": "market_report",
        "news_analyst": "news_report",
        "sentiment_analyst": "sentiment_report",
        "fundamentals_analyst": "fundamentals_report",
        "sector_analyst": "sector_report",
        "index_analyst": "index_report",
    }
    
    def __init__(self, llm: Any, toolkit: Any):
        """
        初始化 Agent 集成器
        
        Args:
            llm: LLM 实例
            toolkit: 工具集实例
        """
        self.llm = llm
        self.toolkit = toolkit
        self._agent_cache: Dict[str, Callable] = {}
        
    def get_agent(self, analyst_id: str) -> Optional[Callable]:
        """
        获取分析师 Agent 节点函数
        
        Args:
            analyst_id: 分析师 ID
            
        Returns:
            Agent 节点函数或 None
        """
        if analyst_id in self._agent_cache:
            return self._agent_cache[analyst_id]
        
        # 创建 Agent
        agent = self._create_agent(analyst_id)
        if agent:
            self._agent_cache[analyst_id] = agent
        return agent
    
    def _create_agent(self, analyst_id: str) -> Optional[Callable]:
        """创建分析师 Agent"""
        factory_name = self.ANALYST_FACTORY_MAP.get(analyst_id)
        if not factory_name:
            # 检查扩展分析师（sector, index）
            return self._create_extension_agent(analyst_id)
        
        try:
            # 动态导入工厂函数
            from tradingagents import agents
            factory = getattr(agents, factory_name, None)
            if factory:
                agent = factory(self.llm, self.toolkit)
                logger.debug(f"🔧 [AgentIntegrator] 创建 Agent: {analyst_id}")
                return agent
        except Exception as e:
            logger.error(f"❌ [AgentIntegrator] 创建 Agent 失败 {analyst_id}: {e}")
        return None
    
    def _create_extension_agent(self, analyst_id: str) -> Optional[Callable]:
        """创建扩展分析师（从 AnalystRegistry）"""
        try:
            from core.agents.analyst_registry import AnalystRegistry
            registry = AnalystRegistry()
            
            if registry.is_registered(analyst_id):
                agent_class = registry.get_analyst_class(analyst_id)
                if agent_class:
                    agent = agent_class()
                    if hasattr(agent, 'set_dependencies'):
                        agent.set_dependencies(self.llm, self.toolkit)
                    logger.debug(f"🔧 [AgentIntegrator] 创建扩展 Agent: {analyst_id}")
                    return lambda state, a=agent: a.execute(state)
        except Exception as e:
            logger.debug(f"⚠️ [AgentIntegrator] 扩展 Agent 不可用 {analyst_id}: {e}")
        return None
    
    def context_to_state(self, context: AnalysisContext) -> Dict[str, Any]:
        """
        将 AnalysisContext 转换为 AgentState 格式
        
        Args:
            context: 分析上下文
            
        Returns:
            AgentState 兼容的字典
        """
        ticker = context.get(DataLayer.CONTEXT, "ticker") or ""
        trade_date = context.get(DataLayer.CONTEXT, "trade_date") or ""
        
        # 构建基础状态
        state = {
            "company_of_interest": ticker,
            "trade_date": trade_date,
            "messages": [],
            # 初始化工具调用计数器
            "market_tool_call_count": 0,
            "news_tool_call_count": 0,
            "sentiment_tool_call_count": 0,
            "fundamentals_tool_call_count": 0,
        }
        
        # 添加已有的报告（供后续 Agent 读取）
        for report_field in self.ANALYST_OUTPUT_MAP.values():
            existing_report = context.get(DataLayer.REPORTS, report_field)
            if existing_report:
                state[report_field] = existing_report
        
        return state
    
    def extract_report(
        self,
        analyst_id: str,
        result: Dict[str, Any]
    ) -> Tuple[Optional[str], Optional[str]]:
        """
        从 Agent 执行结果中提取报告
        
        Args:
            analyst_id: 分析师 ID
            result: Agent 执行结果
            
        Returns:
            (report_field, report_content) 元组
        """
        report_field = self.ANALYST_OUTPUT_MAP.get(analyst_id)
        if report_field and report_field in result:
            return report_field, result[report_field]
        return report_field, None

