# TradingAgents/graph/setup.py

from typing import Dict, Any
from langchain_openai import ChatOpenAI
from langgraph.graph import END, StateGraph, START
from langgraph.prebuilt import ToolNode

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

        # 缓存扩展分析师注册表
        self._extension_registry = None
        self._no_tool_analysts = set()

        # 分析师名称映射
        self._analyst_name_mapping = {
            "market": "Market",
            "social": "Social",
            "news": "News",
            "fundamentals": "Fundamentals",
            "index_analyst": "Index Analyst",
            "sector_analyst": "Sector Analyst",
        }

    def _get_analyst_display_name(self, analyst_type: str) -> str:
        """获取分析师的显示名称"""
        return self._analyst_name_mapping.get(analyst_type, analyst_type.capitalize())

    def _get_extension_registry(self):
        """获取扩展分析师注册表（延迟加载）"""
        if self._extension_registry is None:
            try:
                from core.agents.analyst_registry import get_analyst_registry
                self._extension_registry = get_analyst_registry()
            except ImportError:
                logger.debug("📋 [DEBUG] core.agents.analyst_registry 不可用，跳过扩展分析师")
                self._extension_registry = False
        return self._extension_registry if self._extension_registry else None

    def _load_extension_analysts(
        self,
        selected_analysts: list,
        analyst_nodes: dict,
        delete_nodes: dict
    ):
        """
        从 AnalystRegistry 动态加载扩展分析师

        扩展分析师是指不需要工具调用循环的分析师，
        如 SectorAnalyst、IndexAnalyst 等
        """
        registry = self._get_extension_registry()
        if not registry:
            return

        for analyst_id in selected_analysts:
            # 跳过已处理的内置分析师
            if analyst_id in analyst_nodes:
                continue

            # 检查是否在注册表中
            if not registry.is_registered(analyst_id):
                continue

            # 获取元数据
            metadata = registry.get_analyst_metadata(analyst_id)
            if not metadata:
                continue

            # 只处理不需要工具调用的分析师
            if metadata.requires_tools:
                continue

            # 创建分析师实例
            agent_class = registry.get_analyst_class(analyst_id)
            if agent_class:
                agent = agent_class()
                if hasattr(agent, 'set_dependencies'):
                    agent.set_dependencies(self.quick_thinking_llm, self.toolkit)
                analyst_nodes[analyst_id] = lambda state, a=agent: a.execute(state)
                delete_nodes[analyst_id] = create_msg_delete()
                self._no_tool_analysts.add(analyst_id)
                logger.info(f"📋 [扩展] 已加载分析师: {metadata.name}")

    def setup_graph(
        self, selected_analysts=["market", "social", "news", "fundamentals"]
    ):
        """Set up and compile the agent workflow graph.

        Args:
            selected_analysts (list): List of analyst types to include. Options are:
                - "market": Market analyst
                - "social": Social media analyst
                - "news": News analyst
                - "fundamentals": Fundamentals analyst
                - "sector": Sector/Industry analyst (板块分析师)
                - "index": Index/Market analyst (大盘分析师)
        """
        if len(selected_analysts) == 0:
            raise ValueError("Trading Agents Graph Setup Error: no analysts selected!")

        # Create analyst nodes
        analyst_nodes = {}
        delete_nodes = {}
        tool_nodes = {}

        if "market" in selected_analysts:
            # 现在所有LLM都使用标准市场分析师（包括阿里百炼的OpenAI兼容适配器）
            llm_provider = self.config.get("llm_provider", "").lower()

            # 检查是否使用OpenAI兼容的阿里百炼适配器
            using_dashscope_openai = (
                "dashscope" in llm_provider and
                hasattr(self.quick_thinking_llm, '__class__') and
                'OpenAI' in self.quick_thinking_llm.__class__.__name__
            )

            if using_dashscope_openai:
                logger.debug(f"📈 [DEBUG] 使用标准市场分析师（阿里百炼OpenAI兼容模式）")
            elif "dashscope" in llm_provider or "阿里百炼" in self.config.get("llm_provider", ""):
                logger.debug(f"📈 [DEBUG] 使用标准市场分析师（阿里百炼原生模式）")
            elif "deepseek" in llm_provider:
                logger.debug(f"📈 [DEBUG] 使用标准市场分析师（DeepSeek）")
            else:
                logger.debug(f"📈 [DEBUG] 使用标准市场分析师")

            # 所有LLM都使用标准分析师
            analyst_nodes["market"] = create_market_analyst(
                self.quick_thinking_llm, self.toolkit
            )
            delete_nodes["market"] = create_msg_delete()
            tool_nodes["market"] = self.tool_nodes["market"]

        if "social" in selected_analysts:
            analyst_nodes["social"] = create_social_media_analyst(
                self.quick_thinking_llm, self.toolkit
            )
            delete_nodes["social"] = create_msg_delete()
            tool_nodes["social"] = self.tool_nodes["social"]

        if "news" in selected_analysts:
            analyst_nodes["news"] = create_news_analyst(
                self.quick_thinking_llm, self.toolkit
            )
            delete_nodes["news"] = create_msg_delete()
            tool_nodes["news"] = self.tool_nodes["news"]

        if "fundamentals" in selected_analysts:
            # 现在所有LLM都使用标准基本面分析师（包括阿里百炼的OpenAI兼容适配器）
            llm_provider = self.config.get("llm_provider", "").lower()

            # 检查是否使用OpenAI兼容的阿里百炼适配器
            using_dashscope_openai = (
                "dashscope" in llm_provider and
                hasattr(self.quick_thinking_llm, '__class__') and
                'OpenAI' in self.quick_thinking_llm.__class__.__name__
            )

            if using_dashscope_openai:
                logger.debug(f"📊 [DEBUG] 使用标准基本面分析师（阿里百炼OpenAI兼容模式）")
            elif "dashscope" in llm_provider or "阿里百炼" in self.config.get("llm_provider", ""):
                logger.debug(f"📊 [DEBUG] 使用标准基本面分析师（阿里百炼原生模式）")
            elif "deepseek" in llm_provider:
                logger.debug(f"📊 [DEBUG] 使用标准基本面分析师（DeepSeek）")
            else:
                logger.debug(f"📊 [DEBUG] 使用标准基本面分析师")

            # 所有LLM都使用标准分析师（包含强制工具调用机制）
            analyst_nodes["fundamentals"] = create_fundamentals_analyst(
                self.quick_thinking_llm, self.toolkit
            )
            delete_nodes["fundamentals"] = create_msg_delete()
            tool_nodes["fundamentals"] = self.tool_nodes["fundamentals"]

        # 🆕 大盘分析师和板块分析师使用自包含模式，不需要工具调用
        if "index_analyst" in selected_analysts:
            analyst_nodes["index_analyst"] = create_index_analyst(
                self.quick_thinking_llm, self.toolkit
            )
            delete_nodes["index_analyst"] = create_msg_delete()
            # 🔧 标记为无工具调用分析师
            self._no_tool_analysts.add("index_analyst")
            logger.info("📋 添加大盘分析师 (无工具调用模式)")

        if "sector_analyst" in selected_analysts:
            analyst_nodes["sector_analyst"] = create_sector_analyst(
                self.quick_thinking_llm, self.toolkit
            )
            delete_nodes["sector_analyst"] = create_msg_delete()
            # 🔧 标记为无工具调用分析师
            self._no_tool_analysts.add("sector_analyst")
            logger.info("📋 添加板块分析师 (无工具调用模式)")

        # 🆕 从 AnalystRegistry 动态加载扩展分析师（无工具调用类型）
        self._load_extension_analysts(
            selected_analysts, analyst_nodes, delete_nodes
        )

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
            display_name = self._get_analyst_display_name(analyst_type)
            workflow.add_node(f"{display_name} Analyst", node)
            workflow.add_node(
                f"Msg Clear {display_name}", delete_nodes[analyst_type]
            )
            # 只为需要工具的分析师添加工具节点（扩展分析师在 _no_tool_analysts 中）
            if analyst_type not in self._no_tool_analysts:
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

        # Define edges
        # Start with the first analyst
        first_analyst = selected_analysts[0]
        first_display_name = self._get_analyst_display_name(first_analyst)
        workflow.add_edge(START, f"{first_display_name} Analyst")

        # Connect analysts in sequence
        for i, analyst_type in enumerate(selected_analysts):
            display_name = self._get_analyst_display_name(analyst_type)
            current_analyst = f"{display_name} Analyst"
            current_tools = f"tools_{analyst_type}"
            current_clear = f"Msg Clear {display_name}"

            # 无工具调用的分析师直接连接到下一步（扩展分析师在 _no_tool_analysts 中）
            if analyst_type in self._no_tool_analysts:
                # 直接从分析师连接到消息清理节点
                workflow.add_edge(current_analyst, current_clear)
            else:
                # 有工具调用的分析师使用条件边
                workflow.add_conditional_edges(
                    current_analyst,
                    getattr(self.conditional_logic, f"should_continue_{analyst_type}"),
                    [current_tools, current_clear],
                )
                workflow.add_edge(current_tools, current_analyst)

            # Connect to next analyst or to Bull Researcher if this is the last analyst
            if i < len(selected_analysts) - 1:
                next_analyst_type = selected_analysts[i+1]
                next_display_name = self._get_analyst_display_name(next_analyst_type)
                next_analyst = f"{next_display_name} Analyst"
                workflow.add_edge(current_clear, next_analyst)
            else:
                workflow.add_edge(current_clear, "Bull Researcher")

        # Add remaining edges
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
        workflow.add_edge("Research Manager", "Trader")
        workflow.add_edge("Trader", "Risky Analyst")
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

        workflow.add_edge("Risk Judge", END)

        # Compile and return
        return workflow.compile()
