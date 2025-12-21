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

    def setup_graph(
        self, 
        selected_analysts=["market", "social", "news", "fundamentals"],
        analysis_type="stock"
    ):
        """Set up and compile the agent workflow graph.

        Args:
            selected_analysts (list): List of analyst types to include (for stock analysis).
            analysis_type (str): "stock" for individual stock analysis, "index" for index analysis.
        """
        if analysis_type == "stock":
            return self._setup_stock_graph(selected_analysts)
        elif analysis_type == "index":
            return self._setup_index_graph()
        else:
            raise ValueError(f"Unknown analysis_type: {analysis_type}")
    
    def _setup_stock_graph(
        self, selected_analysts=["market", "social", "news", "fundamentals"]
    ):
        """Set up stock analysis workflow graph (existing logic).
        
        Args:
            selected_analysts (list): List of analyst types to include. Options are:
                - "market": Market analyst
                - "social": Social media analyst
                - "news": News analyst
                - "fundamentals": Fundamentals analyst
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
            workflow.add_node(f"{analyst_type.capitalize()} Analyst", node)
            workflow.add_node(
                f"Msg Clear {analyst_type.capitalize()}", delete_nodes[analyst_type]
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

        # Define edges
        # Start with the first analyst
        first_analyst = selected_analysts[0]
        workflow.add_edge(START, f"{first_analyst.capitalize()} Analyst")

        # Connect analysts in sequence
        for i, analyst_type in enumerate(selected_analysts):
            current_analyst = f"{analyst_type.capitalize()} Analyst"
            current_tools = f"tools_{analyst_type}"
            current_clear = f"Msg Clear {analyst_type.capitalize()}"

            # Add conditional edges for current analyst
            workflow.add_conditional_edges(
                current_analyst,
                getattr(self.conditional_logic, f"should_continue_{analyst_type}"),
                [current_tools, current_clear],
            )
            workflow.add_edge(current_tools, current_analyst)

            # Connect to next analyst or to Bull Researcher if this is the last analyst
            if i < len(selected_analysts) - 1:
                next_analyst = f"{selected_analysts[i+1].capitalize()} Analyst"
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
    
    def _setup_index_graph(self):
        """
        Set up index analysis workflow graph (v2.2).
        
        Index analysis flow:
        START → Macro Analyst → Policy Analyst → International News Analyst → Sector Analyst → Technical Analyst → Strategy Advisor → END
        """
        from tradingagents.agents.analysts.macro_analyst import create_macro_analyst
        from tradingagents.agents.analysts.policy_analyst import create_policy_analyst
        from tradingagents.agents.analysts.international_news_analyst import create_international_news_analyst  # v2.1新增
        from tradingagents.agents.analysts.sector_analyst import create_sector_analyst
        from tradingagents.agents.analysts.technical_analyst import create_technical_analyst  # v2.2新增
        from tradingagents.agents.analysts.strategy_advisor import create_strategy_advisor
        from tradingagents.agents.researchers.index_bull_researcher import create_index_bull_researcher  # v2.3新增
        from tradingagents.agents.researchers.index_bear_researcher import create_index_bear_researcher  # v2.3新增
        from tradingagents.agents.utils.agent_utils import create_msg_delete
        
        logger.info("🏗️ [图构建] 开始构建指数分析工作流")
        
        # 1. 创建分析师节点
        macro_analyst_node = create_macro_analyst(self.quick_thinking_llm, self.toolkit)
        policy_analyst_node = create_policy_analyst(self.quick_thinking_llm, self.toolkit)
        international_news_analyst_node = create_international_news_analyst(self.quick_thinking_llm, self.toolkit)  # v2.1新增
        sector_analyst_node = create_sector_analyst(self.quick_thinking_llm, self.toolkit)
        technical_analyst_node = create_technical_analyst(self.quick_thinking_llm, self.toolkit)  # v2.2新增
        strategy_advisor_node = create_strategy_advisor(self.deep_thinking_llm)
        index_bull_researcher_node = create_index_bull_researcher(self.quick_thinking_llm)  # v2.3新增
        index_bear_researcher_node = create_index_bear_researcher(self.quick_thinking_llm)  # v2.3新增
        
        # 2. 创建消息清理节点
        macro_clear = create_msg_delete()
        policy_clear = create_msg_delete()
        international_news_clear = create_msg_delete()  # v2.1新增
        sector_clear = create_msg_delete()
        technical_clear = create_msg_delete()  # v2.2新增
        strategy_clear = create_msg_delete()
        
        # 3. 创建工作流
        workflow = StateGraph(AgentState)
        
        # 4. 添加节点
        workflow.add_node("Macro Analyst", macro_analyst_node)
        workflow.add_node("Msg Clear Macro", macro_clear)
        workflow.add_node("tools_macro", self.tool_nodes.get("index_macro"))
        
        workflow.add_node("Policy Analyst", policy_analyst_node)
        workflow.add_node("Msg Clear Policy", policy_clear)
        workflow.add_node("tools_policy", self.tool_nodes.get("index_policy"))
        
        # v2.1新增: International News Analyst
        workflow.add_node("International News Analyst", international_news_analyst_node)
        workflow.add_node("Msg Clear International News", international_news_clear)
        workflow.add_node("tools_international_news", self.tool_nodes.get("index_international_news"))
        
        workflow.add_node("Sector Analyst", sector_analyst_node)
        workflow.add_node("Msg Clear Sector", sector_clear)
        workflow.add_node("tools_sector", self.tool_nodes.get("index_sector"))
        
        # v2.2新增: Technical Analyst
        workflow.add_node("Technical Analyst", technical_analyst_node)
        workflow.add_node("Msg Clear Technical", technical_clear)
        workflow.add_node("tools_technical", self.tool_nodes.get("index_technical"))
        
        workflow.add_node("Strategy Advisor", strategy_advisor_node)
        workflow.add_node("Msg Clear Strategy", strategy_clear)
        
        # v2.3新增: Index Researchers
        workflow.add_node("Index Bull Researcher", index_bull_researcher_node)
        workflow.add_node("Index Bear Researcher", index_bear_researcher_node)
        
        # 5. 定义边
        # START → Macro Analyst
        workflow.add_edge(START, "Macro Analyst")
        
        # Macro Analyst ↔ tools_macro
        workflow.add_conditional_edges(
            "Macro Analyst",
            self.conditional_logic.should_continue_macro,
            ["tools_macro", "Msg Clear Macro"],
        )
        workflow.add_edge("tools_macro", "Macro Analyst")
        workflow.add_edge("Msg Clear Macro", "Policy Analyst")
        
        # Policy Analyst ↔ tools_policy
        workflow.add_conditional_edges(
            "Policy Analyst",
            self.conditional_logic.should_continue_policy,
            ["tools_policy", "Msg Clear Policy"],
        )
        workflow.add_edge("tools_policy", "Policy Analyst")
        workflow.add_edge("Msg Clear Policy", "International News Analyst")  # v2.1: 转到International News
        
        # v2.1新增: International News Analyst ↔ tools_international_news
        workflow.add_conditional_edges(
            "International News Analyst",
            self.conditional_logic.should_continue_international_news,
            ["tools_international_news", "Msg Clear International News"],
        )
        workflow.add_edge("tools_international_news", "International News Analyst")
        workflow.add_edge("Msg Clear International News", "Sector Analyst")  # v2.1: 然后转到Sector
        
        # Sector Analyst ↔ tools_sector
        workflow.add_conditional_edges(
            "Sector Analyst",
            self.conditional_logic.should_continue_sector,
            ["tools_sector", "Msg Clear Sector"],
        )
        workflow.add_edge("tools_sector", "Sector Analyst")
        workflow.add_edge("Msg Clear Sector", "Technical Analyst")  # v2.2: 转到 Technical Analyst
        
        # v2.2新增: Technical Analyst ↔ tools_technical
        workflow.add_conditional_edges(
            "Technical Analyst",
            self.conditional_logic.should_continue_technical,
            ["tools_technical", "Msg Clear Technical"],
        )
        workflow.add_edge("tools_technical", "Technical Analyst")
        workflow.add_edge("Msg Clear Technical", "Index Bull Researcher")  # v2.3: 转到多头研究员 (开始辩论)
        
        # v2.3: 多空辩论循环
        workflow.add_conditional_edges(
            "Index Bull Researcher",
            self.conditional_logic.should_continue_debate,
            {
                "Bear Researcher": "Index Bear Researcher", # 注意：这里为了复用should_continue_debate的返回值映射，需要匹配返回值
                "Research Manager": "Strategy Advisor",      # 将Research Manager映射到Strategy Advisor
            },
        )
        
        workflow.add_conditional_edges(
            "Index Bear Researcher",
            self.conditional_logic.should_continue_debate,
            {
                "Bull Researcher": "Index Bull Researcher",
                "Research Manager": "Strategy Advisor",
            },
        )
        
        # Strategy Advisor → END
        workflow.add_conditional_edges(
            "Strategy Advisor",
            self.conditional_logic.should_continue_strategy,
            ["Msg Clear Strategy"],
        )
        workflow.add_edge("Msg Clear Strategy", END)
        
        # 6. 编译图
        logger.info("✅ [图构建] 指数分析工作流构建完成")
        return workflow.compile()
