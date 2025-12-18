# tradingagents/core/engine/agent_integrator.py
"""
Agent 集成器

桥接 StockAnalysisEngine 与现有的 Agent 实现：
- 创建 Agent 实例（使用现有的 create_xxx 工厂函数）
- 转换 AnalysisContext 与 AgentState
- 调用 Agent 并提取结果

所有 Agent 配置统一从 core/agents/config.py 的 BUILTIN_AGENTS 读取
"""

from typing import Any, Dict, Optional, Callable, Tuple

from tradingagents.utils.logging_init import get_logger

from .analysis_context import AnalysisContext
from .data_contract import DataLayer

logger = get_logger("default")


# ========================================
# Agent 工厂函数映射 (从模块名到工厂函数名)
# 这是唯一需要维护的映射，配置信息从 BUILTIN_AGENTS 读取
# ========================================
AGENT_FACTORY_REGISTRY = {
    # 分析师 - 需要 (llm, toolkit)
    "market_analyst": ("tradingagents.agents", "create_market_analyst", "analyst"),
    "news_analyst": ("tradingagents.agents", "create_news_analyst", "analyst"),
    "sentiment_analyst": ("tradingagents.agents", "create_social_media_analyst", "analyst"),
    "social_analyst": ("tradingagents.agents", "create_social_media_analyst", "analyst"),  # 别名
    "fundamentals_analyst": ("tradingagents.agents", "create_fundamentals_analyst", "analyst"),
    # 研究员 - 需要 (llm, memory)
    "bull_researcher": ("tradingagents.agents.researchers.bull_researcher", "create_bull_researcher", "researcher"),
    "bear_researcher": ("tradingagents.agents.researchers.bear_researcher", "create_bear_researcher", "researcher"),
    "research_manager": ("tradingagents.agents.managers.research_manager", "create_research_manager", "manager"),
    # 交易员 - 需要 (llm, memory)
    "trader": ("tradingagents.agents.trader.trader", "create_trader", "trader"),
    # 风控 - 需要 (llm) 或 (llm, memory)
    "risky_analyst": ("tradingagents.agents.risk_mgmt.aggresive_debator", "create_risky_debator", "risk"),
    "safe_analyst": ("tradingagents.agents.risk_mgmt.conservative_debator", "create_safe_debator", "risk"),
    "neutral_analyst": ("tradingagents.agents.risk_mgmt.neutral_debator", "create_neutral_debator", "risk"),
    "risk_manager": ("tradingagents.agents.managers.risk_manager", "create_risk_manager", "manager"),
}


class AgentIntegrator:
    """
    Agent 集成器

    负责：
    1. 创建和管理 Agent 实例
    2. 转换 AnalysisContext <-> AgentState
    3. 执行 Agent 并提取结果

    配置来源：
    - Agent 元数据（output_field 等）从 core/agents/config.py 的 BUILTIN_AGENTS 读取
    - 工厂函数映射从 AGENT_FACTORY_REGISTRY 读取
    """

    def __init__(self, llm: Any, toolkit: Any, memory_config: Dict[str, Any] = None):
        """
        初始化 Agent 集成器

        Args:
            llm: LLM 实例
            toolkit: 工具集实例
            memory_config: 可选的 memory 配置字典，包含各类 memory 对象
        """
        self.llm = llm
        self.toolkit = toolkit
        self.memory_config = memory_config or {}
        self._agent_cache: Dict[str, Callable] = {}
        self._metadata_cache: Dict[str, Any] = {}

    def _get_agent_metadata(self, agent_id: str) -> Optional[Any]:
        """
        从 BUILTIN_AGENTS 配置获取 Agent 元数据

        Args:
            agent_id: Agent ID

        Returns:
            AgentMetadata 对象或 None
        """
        if agent_id in self._metadata_cache:
            return self._metadata_cache[agent_id]

        try:
            from core.agents.config import BUILTIN_AGENTS
            metadata = BUILTIN_AGENTS.get(agent_id)
            if metadata:
                self._metadata_cache[agent_id] = metadata
            return metadata
        except ImportError:
            logger.warning(f"⚠️ [AgentIntegrator] 无法导入 BUILTIN_AGENTS 配置")
            return None

    def get_output_field(self, agent_id: str) -> Optional[str]:
        """
        获取 Agent 的输出字段名

        Args:
            agent_id: Agent ID

        Returns:
            输出字段名，如 "market_report"
        """
        metadata = self._get_agent_metadata(agent_id)
        if metadata and hasattr(metadata, 'output_field') and metadata.output_field:
            return metadata.output_field
        # 回退：从 outputs 列表获取
        if metadata and hasattr(metadata, 'outputs') and metadata.outputs:
            return metadata.outputs[0].name
        return None
        
    def get_agent(self, agent_id: str) -> Optional[Callable]:
        """
        获取 Agent 节点函数

        Args:
            agent_id: Agent ID (如 market_analyst, bull_researcher, trader 等)

        Returns:
            Agent 节点函数或 None
        """
        if agent_id in self._agent_cache:
            return self._agent_cache[agent_id]

        # 创建 Agent
        agent = self._create_agent(agent_id)
        if agent:
            self._agent_cache[agent_id] = agent
        return agent

    def _create_agent(self, agent_id: str) -> Optional[Callable]:
        """
        创建 Agent 实例

        根据 AGENT_FACTORY_REGISTRY 中的配置动态创建 Agent
        """
        factory_info = AGENT_FACTORY_REGISTRY.get(agent_id)
        if not factory_info:
            # 尝试从扩展注册表创建
            return self._create_extension_agent(agent_id)

        module_path, factory_name, agent_type = factory_info

        try:
            # 动态导入模块
            import importlib
            module = importlib.import_module(module_path)
            factory = getattr(module, factory_name, None)

            if factory:
                # 根据 Agent 类型传递不同的参数
                if agent_type == "analyst":
                    # 分析师需要 (llm, toolkit)
                    agent = factory(self.llm, self.toolkit)
                elif agent_type in ("researcher", "manager", "trader"):
                    # 研究员、管理者、交易员需要 (llm, memory)
                    memory = self.memory_config.get(agent_id) or self.memory_config.get("default")
                    agent = factory(self.llm, memory)
                elif agent_type == "risk":
                    # 风控可能只需要 (llm) 或 (llm, memory)
                    memory = self.memory_config.get(agent_id)
                    if memory:
                        agent = factory(self.llm, memory)
                    else:
                        agent = factory(self.llm)
                else:
                    agent = factory(self.llm, self.toolkit)

                logger.debug(f"🔧 [AgentIntegrator] 创建 Agent: {agent_id} (类型: {agent_type})")
                return agent
        except Exception as e:
            logger.error(f"❌ [AgentIntegrator] 创建 Agent 失败 {agent_id}: {e}")
        return None

    def _create_extension_agent(self, agent_id: str) -> Optional[Callable]:
        """创建扩展 Agent（从 AgentRegistry 或 AnalystRegistry）"""
        try:
            from core.agents.analyst_registry import AnalystRegistry
            registry = AnalystRegistry()

            if registry.is_registered(agent_id):
                agent_class = registry.get_analyst_class(agent_id)
                if agent_class:
                    agent = agent_class()
                    if hasattr(agent, 'set_dependencies'):
                        agent.set_dependencies(self.llm, self.toolkit)
                    logger.debug(f"🔧 [AgentIntegrator] 创建扩展 Agent: {agent_id}")
                    return lambda state, a=agent: a.execute(state)
        except Exception as e:
            logger.debug(f"⚠️ [AgentIntegrator] 扩展 Agent 不可用 {agent_id}: {e}")
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

        # 从配置动态获取所有可能的报告字段
        try:
            from core.agents.config import BUILTIN_AGENTS
            for agent_id, metadata in BUILTIN_AGENTS.items():
                if hasattr(metadata, 'output_field') and metadata.output_field:
                    existing_report = context.get(DataLayer.REPORTS, metadata.output_field)
                    if existing_report:
                        state[metadata.output_field] = existing_report
        except ImportError:
            pass

        return state
    
    def run_agent_with_tools(
        self,
        agent: Callable,
        state: Dict[str, Any],
        agent_id: str,
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
            agent_id: Agent ID
            max_iterations: 最大迭代次数

        Returns:
            最终的 Agent 执行结果
        """
        from langchain_core.messages import ToolMessage

        current_state = state.copy()
        report_field = self.get_output_field(agent_id)

        for iteration in range(max_iterations):
            # 执行 Agent
            result = agent(current_state)

            # 检查是否已生成报告
            if report_field and report_field in result and result[report_field]:
                logger.info(f"✅ [AgentIntegrator] {agent_id} 第 {iteration + 1} 轮生成报告")
                return result

            # 检查是否有工具调用请求
            messages = result.get("messages", [])
            if not messages:
                logger.warning(f"⚠️ [AgentIntegrator] {agent_id} 未返回 messages")
                return result

            last_message = messages[-1] if messages else None
            if not last_message or not hasattr(last_message, 'tool_calls') or not last_message.tool_calls:
                # 没有工具调用，直接返回
                logger.info(f"📝 [AgentIntegrator] {agent_id} 第 {iteration + 1} 轮无工具调用")
                return result

            # 执行工具调用
            logger.info(f"🔧 [AgentIntegrator] {agent_id} 第 {iteration + 1} 轮执行工具调用")
            tool_results = self._execute_tool_calls(last_message.tool_calls)

            # 更新状态：添加 AI 消息和工具结果到历史
            current_state["messages"] = current_state.get("messages", []) + [last_message] + tool_results

            # 更新工具调用计数器
            counter_key = f"{agent_id.replace('_analyst', '')}_tool_call_count"
            current_state[counter_key] = current_state.get(counter_key, 0) + 1

        logger.warning(f"⚠️ [AgentIntegrator] {agent_id} 达到最大迭代次数 {max_iterations}")
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
        agent_id: str,
        result: Dict[str, Any]
    ) -> Tuple[Optional[str], Optional[str]]:
        """
        从 Agent 执行结果中提取报告

        Args:
            agent_id: Agent ID
            result: Agent 执行结果

        Returns:
            (report_field, report_content) 元组
        """
        report_field = self.get_output_field(agent_id)
        
        # v2.0 agent输出字段到标准报告字段的映射
        v2_field_mapping = {
            # research_manager_v2: investment_advice -> investment_plan
            'investment_advice': 'investment_plan',
            # trader_v2: trade_plan -> trader_investment_plan  
            'trade_plan': 'trader_investment_plan',
            # risk_manager_v2: risk_assessment -> risk_management_decision
            'risk_assessment': 'risk_management_decision',
            # 其他v2字段映射
            'bull_report': 'bull_researcher',
            'bear_report': 'bear_researcher',
            'risky_opinion': 'risky_analyst',
            'safe_opinion': 'safe_analyst',
            'neutral_opinion': 'neutral_analyst',
        }
        
        if report_field and report_field in result:
            # 如果是v2字段，映射到标准字段
            mapped_field = v2_field_mapping.get(report_field, report_field)
            return mapped_field, result[report_field]
        
        return report_field, None

