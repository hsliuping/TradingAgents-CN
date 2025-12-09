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
    
    def run_agent_with_tools(
        self,
        agent: Callable,
        state: Dict[str, Any],
        analyst_id: str,
        max_iterations: int = 3
    ) -> Dict[str, Any]:
        """
        运行 Agent 并处理工具调用循环

        现有的 Agent 设计为多轮迭代：
        1. 第一轮：LLM 返回工具调用请求
        2. 工具执行：执行工具，将结果添加到 messages
        3. 第二轮：LLM 看到工具结果后生成报告

        Args:
            agent: Agent 节点函数
            state: 初始状态
            analyst_id: 分析师 ID
            max_iterations: 最大迭代次数

        Returns:
            最终的 Agent 执行结果
        """
        from langchain_core.messages import AIMessage, ToolMessage

        current_state = state.copy()
        report_field = self.ANALYST_OUTPUT_MAP.get(analyst_id)

        for iteration in range(max_iterations):
            # 执行 Agent
            result = agent(current_state)

            # 检查是否已生成报告
            if report_field and report_field in result and result[report_field]:
                logger.info(f"✅ [AgentIntegrator] {analyst_id} 第 {iteration + 1} 轮生成报告")
                return result

            # 检查是否有工具调用请求
            messages = result.get("messages", [])
            if not messages:
                logger.warning(f"⚠️ [AgentIntegrator] {analyst_id} 未返回 messages")
                return result

            last_message = messages[-1] if messages else None
            if not last_message or not hasattr(last_message, 'tool_calls') or not last_message.tool_calls:
                # 没有工具调用，直接返回
                logger.info(f"📝 [AgentIntegrator] {analyst_id} 第 {iteration + 1} 轮无工具调用")
                return result

            # 执行工具调用
            logger.info(f"🔧 [AgentIntegrator] {analyst_id} 第 {iteration + 1} 轮执行工具调用")
            tool_results = self._execute_tool_calls(last_message.tool_calls)

            # 更新状态：添加 AI 消息和工具结果到历史
            current_state["messages"] = current_state.get("messages", []) + [last_message] + tool_results

            # 更新工具调用计数器
            counter_key = f"{analyst_id.replace('_analyst', '')}_tool_call_count"
            current_state[counter_key] = current_state.get(counter_key, 0) + 1

        logger.warning(f"⚠️ [AgentIntegrator] {analyst_id} 达到最大迭代次数 {max_iterations}")
        return result

    def _execute_tool_calls(self, tool_calls: list) -> list:
        """执行工具调用并返回 ToolMessage 列表"""
        from langchain_core.messages import ToolMessage

        tool_messages = []
        for tc in tool_calls:
            tool_name = tc.get('name', '')
            tool_args = tc.get('args', {})
            tool_id = tc.get('id', '')

            logger.info(f"🔧 [AgentIntegrator] 执行工具: {tool_name}")
            logger.debug(f"  参数: {tool_args}")

            try:
                # 从 toolkit 获取工具函数
                tool_func = self._get_tool_function(tool_name)
                if tool_func:
                    result = tool_func.invoke(tool_args)
                    tool_messages.append(ToolMessage(
                        content=str(result),
                        tool_call_id=tool_id,
                        name=tool_name
                    ))
                    logger.info(f"✅ [AgentIntegrator] 工具 {tool_name} 执行成功，结果长度: {len(str(result))}")
                else:
                    error_msg = f"工具 {tool_name} 不存在"
                    logger.warning(f"⚠️ [AgentIntegrator] {error_msg}")
                    tool_messages.append(ToolMessage(
                        content=error_msg,
                        tool_call_id=tool_id,
                        name=tool_name
                    ))
            except Exception as e:
                error_msg = f"工具执行失败: {str(e)}"
                logger.error(f"❌ [AgentIntegrator] {error_msg}")
                tool_messages.append(ToolMessage(
                    content=error_msg,
                    tool_call_id=tool_id,
                    name=tool_name
                ))

        return tool_messages

    def _get_tool_function(self, tool_name: str):
        """从 toolkit 获取工具函数"""
        # 尝试从不同的工具集获取
        tool_sets = [
            self.toolkit.get_general_tools,
            self.toolkit.get_market_analysis_tools,
            self.toolkit.get_social_media_tools,
            self.toolkit.get_fundamental_tools,
            self.toolkit.get_us_tools,
            self.toolkit.get_china_tools,
        ]

        for get_tools in tool_sets:
            try:
                tools = get_tools()
                for tool in tools:
                    if hasattr(tool, 'name') and tool.name == tool_name:
                        return tool
            except Exception:
                continue
        return None

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

