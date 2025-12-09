# TradingAgents/graph/setup.py

from typing import Dict, Any
from langchain_openai import ChatOpenAI
from langgraph.graph import END, StateGraph, START
from langgraph.prebuilt import ToolNode

from tradingagents.agents.analysts.dynamic_analyst import create_dynamic_analyst
from tradingagents.agents import *
from tradingagents.agents.utils.agent_states import AgentState
from tradingagents.agents.utils.agent_utils import Toolkit

from .conditional_logic import ConditionalLogic

# 导入统一日志系统
from tradingagents.utils.logging_init import get_logger
logger = get_logger("default")


class GraphSetup:
    """Handles the setup and configuration of the agent graph."""

    def __init__(
        self,
        quick_thinking_llm: ChatOpenAI,
        deep_thinking_llm: ChatOpenAI,
        toolkit: Toolkit,
        tool_nodes: Dict[str, ToolNode],
        bull_memory,
        bear_memory,
        trader_memory,
        invest_judge_memory,
        risk_manager_memory,
        conditional_logic: ConditionalLogic,
        config: Dict[str, Any] = None,
        react_llm = None,
    ):
        """Initialize with required components."""
        self.quick_thinking_llm = quick_thinking_llm
        self.deep_thinking_llm = deep_thinking_llm
        self.toolkit = toolkit
        self.tool_nodes = tool_nodes
        self.bull_memory = bull_memory
        self.bear_memory = bear_memory
        self.trader_memory = trader_memory
        self.invest_judge_memory = invest_judge_memory
        self.risk_manager_memory = risk_manager_memory
        self.conditional_logic = conditional_logic
        self.config = config or {}
        self.react_llm = react_llm

    def _format_analyst_name(self, internal_key: str) -> str:
        """Format analyst name from internal key (e.g., 'financial_news' -> 'Financial_News').
        Must match the logic in conditional_logic.py
        """
        return internal_key.replace('_', ' ').title().replace(' ', '_')

    def setup_graph(
        self, selected_analysts=None
    ):
        """Set up and compile the agent workflow graph.

        Args:
            selected_analysts (list): List of analyst types to include.
                支持多种输入格式：
                - 简短 ID: "market", "fundamentals", "news", "social"
                - 完整 slug: "market-analyst", "fundamentals-analyst"
                - 中文名称: "市场技术分析师", "基本面分析师"
                
                所有格式都会自动从配置文件 phase1_agents_config.yaml 中查找对应的智能体配置。
        """
        if not selected_analysts:
            raise ValueError(
                "Trading Agents Graph Setup Error: no analysts selected! 请先在 phase1 配置中选择分析师。"
            )

        # 导入动态分析师工厂
        from tradingagents.agents.analysts.dynamic_analyst import DynamicAnalystFactory
        
        # 从配置文件动态构建查找映射（不再使用硬编码）
        analyst_lookup = DynamicAnalystFactory.build_lookup_map()
        logger.debug(f"📋 [DEBUG] 从配置文件加载了 {len(analyst_lookup)} 个分析师映射")

        # Create analyst nodes
        analyst_nodes = {}
        delete_nodes = {}
        tool_nodes = {}

        # 用于存储规范化后的分析师列表（使用internal_key，保持顺序且去重）
        normalized_analysts = []
        seen_internal_keys = set()  # 用于去重
        
        # Dynamically create analyst nodes based on selected_analysts
        for input_key in selected_analysts:
            # 尝试从动态查找映射中获取配置
            if input_key in analyst_lookup:
                config_info = analyst_lookup[input_key]
                internal_key = config_info['internal_key']
                config_slug = config_info['slug']
                tool_key = config_info['tool_key']
                agent_name = config_info.get('name', input_key)
                
                # 跳过已经处理过的分析师（去重）
                if internal_key in seen_internal_keys:
                    logger.debug(f"⏭️ [DEBUG] Skipping duplicate analyst: {input_key} -> {internal_key} (already added)")
                    continue
                seen_internal_keys.add(internal_key)
                
                logger.debug(f"📈 [DEBUG] Creating dynamic analyst: {input_key} -> {config_slug} (internal: {internal_key})")
                
                analyst_nodes[internal_key] = create_dynamic_analyst(
                    config_slug, self.quick_thinking_llm, self.toolkit
                )
                delete_nodes[internal_key] = create_msg_delete()
                
                # 分配工具节点
                if tool_key in self.tool_nodes:
                    tool_nodes[internal_key] = self.tool_nodes[tool_key]
                    logger.debug(f"🛠️ [DEBUG] Assigned '{tool_key}' tools to {internal_key}")
                else:
                    logger.warning(f"⚠️ No specific tool node found for {internal_key}, using default 'market'")
                    if "market" in self.tool_nodes:
                        tool_nodes[internal_key] = self.tool_nodes["market"]
                
                normalized_analysts.append(internal_key)
            else:
                # 尝试直接从配置文件获取（支持新添加的智能体）
                agent_config = DynamicAnalystFactory.get_agent_config(input_key)
                
                if agent_config:
                    # 找到配置，使用配置中的 slug
                    config_slug = agent_config.get('slug', input_key)
                    agent_name = agent_config.get('name', input_key)
                    logger.info(f"📈 [动态分析师] 从配置文件找到: '{input_key}' -> slug='{config_slug}', name='{agent_name}'")
                else:
                    # 未找到配置
                    logger.error(f"❌ 未找到智能体配置: {input_key}")
                    raise ValueError(f"未找到智能体配置: {input_key}。请确保该智能体已在 phase1_agents_config.yaml 中配置。")
                
                # 生成internal_key（去除-analyst后缀，替换-为_）
                internal_key = config_slug.replace("-analyst", "").replace("-", "_")
                
                # 跳过已经处理过的分析师（去重）
                if internal_key in seen_internal_keys:
                    logger.debug(f"⏭️ [DEBUG] Skipping duplicate custom analyst: {input_key} -> {internal_key} (already added)")
                    continue
                seen_internal_keys.add(internal_key)
                
                logger.debug(f"📈 [DEBUG] Creating custom dynamic analyst: {input_key} -> {config_slug}")
                
                try:
                    analyst_nodes[internal_key] = create_dynamic_analyst(
                        config_slug, self.quick_thinking_llm, self.toolkit
                    )
                    delete_nodes[internal_key] = create_msg_delete()
                    
                    # 使用工厂方法推断工具类型
                    tool_key = DynamicAnalystFactory._infer_tool_key(config_slug, agent_name)
                    
                    if tool_key in self.tool_nodes:
                        tool_nodes[internal_key] = self.tool_nodes[tool_key]
                        logger.debug(f"🛠️ [DEBUG] Assigned '{tool_key}' tools to {internal_key}")
                    else:
                        logger.warning(f"⚠️ No tools assigned for {internal_key}, using default 'market'")
                        if "market" in self.tool_nodes:
                            tool_nodes[internal_key] = self.tool_nodes["market"]
                    
                    normalized_analysts.append(internal_key)
                except ValueError as e:
                    logger.error(f"❌ 创建动态分析师失败: {input_key} -> {e}")
                    raise ValueError(f"未找到智能体配置: {input_key}")
        
        # 使用规范化后的分析师列表
        selected_analysts = normalized_analysts

        # Create researcher and manager nodes
        bull_researcher_node = create_bull_researcher(
            self.quick_thinking_llm, self.bull_memory
        )
        bear_researcher_node = create_bear_researcher(
            self.quick_thinking_llm, self.bear_memory
        )
        research_manager_node = create_research_manager(
            self.deep_thinking_llm, self.invest_judge_memory
        )
        trader_node = create_trader(self.quick_thinking_llm, self.trader_memory)

        # Create risk analysis nodes
        risky_analyst = create_risky_debator(self.quick_thinking_llm)
        neutral_analyst = create_neutral_debator(self.quick_thinking_llm)
        safe_analyst = create_safe_debator(self.quick_thinking_llm)
        risk_manager_node = create_risk_manager(
            self.deep_thinking_llm, self.risk_manager_memory
        )

        # Create workflow
        workflow = StateGraph(AgentState)

        # Add analyst nodes to the graph
        for analyst_type, node in analyst_nodes.items():
            workflow.add_node(f"{self._format_analyst_name(analyst_type)} Analyst", node)
            workflow.add_node(
                f"Msg Clear {self._format_analyst_name(analyst_type)}", delete_nodes[analyst_type]
            )
            workflow.add_node(f"tools_{analyst_type}", tool_nodes[analyst_type])

        # Add other nodes
        workflow.add_node("Bull Researcher", bull_researcher_node)
        workflow.add_node("Bear Researcher", bear_researcher_node)
        workflow.add_node("Research Manager", research_manager_node)
        workflow.add_node("Trader", trader_node)
        workflow.add_node("Risky Analyst", risky_analyst)
        workflow.add_node("Neutral Analyst", neutral_analyst)
        workflow.add_node("Safe Analyst", safe_analyst)
        workflow.add_node("Risk Judge", risk_manager_node)

        # Define edges（阶段开关不再级联，完全由前端传入控制）
        enable_phase2 = bool(self.config.get("phase2_enabled", False))
        enable_phase3 = bool(self.config.get("phase3_enabled", False))
        enable_phase4 = bool(self.config.get("phase4_enabled", False))

        # Start with the first analyst
        first_analyst = selected_analysts[0]
        workflow.add_edge(START, f"{self._format_analyst_name(first_analyst)} Analyst")

        # Connect analysts in sequence
        if enable_phase2:
            next_entry_node = "Bull Researcher"
        elif enable_phase3:
            # 没有研究辩论时直接进入组合/风险团队
            next_entry_node = "Risky Analyst"
        elif enable_phase4:
            # 仅开启最终交易阶段时直接进入交易员
            next_entry_node = "Trader"
        else:
            next_entry_node = END
        for i, analyst_type in enumerate(selected_analysts):
            current_analyst = f"{self._format_analyst_name(analyst_type)} Analyst"
            current_tools = f"tools_{analyst_type}"
            current_clear = f"Msg Clear {self._format_analyst_name(analyst_type)}"

            # Add conditional edges for current analyst
            workflow.add_conditional_edges(
                current_analyst,
                getattr(self.conditional_logic, f"should_continue_{analyst_type}"),
                [current_tools, current_clear],
            )
            workflow.add_edge(current_tools, current_analyst)

            # Connect to next analyst or to Bull Researcher if this is the last analyst
            if i < len(selected_analysts) - 1:
                next_analyst = f"{self._format_analyst_name(selected_analysts[i+1])} Analyst"
                workflow.add_edge(current_clear, next_analyst)
            else:
                workflow.add_edge(current_clear, next_entry_node)

        # Add remaining edges（按阶段开关控制后续阶段是否参与，阶段顺序：辩论 -> 组合/风险 -> 交易员）
        if enable_phase2:
            workflow.add_conditional_edges(
                "Bull Researcher",
                self.conditional_logic.should_continue_debate,
                {
                    "Bear Researcher": "Bear Researcher",
                    "Research Manager": "Research Manager",
                },
            )
            workflow.add_conditional_edges(
                "Bear Researcher",
                self.conditional_logic.should_continue_debate,
                {
                    "Bull Researcher": "Bull Researcher",
                    "Research Manager": "Research Manager",
                },
            )

            research_manager_target = (
                "Risky Analyst"
                if enable_phase3
                else ("Trader" if enable_phase4 else END)
            )
            workflow.add_edge("Research Manager", research_manager_target)

        # 投资组合/风险团队（第三阶段）
        if enable_phase3:
            workflow.add_conditional_edges(
                "Risky Analyst",
                self.conditional_logic.should_continue_risk_analysis,
                {
                    "Safe Analyst": "Safe Analyst",
                    "Risk Judge": "Risk Judge",
                },
            )
            workflow.add_conditional_edges(
                "Safe Analyst",
                self.conditional_logic.should_continue_risk_analysis,
                {
                    "Neutral Analyst": "Neutral Analyst",
                    "Risk Judge": "Risk Judge",
                },
            )
            workflow.add_conditional_edges(
                "Neutral Analyst",
                self.conditional_logic.should_continue_risk_analysis,
                {
                    "Risky Analyst": "Risky Analyst",
                    "Risk Judge": "Risk Judge",
                },
            )
            workflow.add_edge("Risk Judge", "Trader" if enable_phase4 else END)

        # 最终交易阶段
        if enable_phase4:
            workflow.add_edge("Trader", END)

        # Compile and return
        return workflow.compile()
