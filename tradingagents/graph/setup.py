# TradingAgents/graph/setup.py

from typing import Dict, Any, List
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
        selected_analysts: List[str] = None,
        # 指数分析记忆
        index_bull_memory = None,
        index_bear_memory = None,
        strategy_advisor_memory = None,
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
        self.selected_analysts = selected_analysts or []
        # 指数分析记忆
        self.index_bull_memory = index_bull_memory
        self.index_bear_memory = index_bear_memory
        self.strategy_advisor_memory = strategy_advisor_memory

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
            return self._setup_index_graph(selected_analysts)
        else:
            raise ValueError(f"Unknown analysis_type: {analysis_type}")
    
    def _stock_barrier_node(self, state: AgentState):
        """Barrier node to synchronize parallel stock analysis branches."""
        # No operation needed, just a synchronization point
        return {}

    def _should_continue_stock_barrier(self, state: AgentState):
        """Check if all selected stock analysts have completed their reports."""
        selected = state.get("selected_analysts", [])
        if not selected:
            # Fallback default if not set
            selected = ["market", "social", "news", "fundamentals"]
        
        # Mapping: Analyst Type -> Report Field in AgentState
        mapping = {
            "market": "market_report",
            "social": "sentiment_report", # social analyst outputs sentiment_report
            "news": "news_report",
            "fundamentals": "fundamentals_report"
        }
        
        all_ready = True
        missing = []
        for analyst in selected:
            # Skip index analysts if present
            if analyst in ["macro", "policy", "sector", "technical_index", "intl_news", "bull_bear", "risk"]:
                continue
            
            field = mapping.get(analyst)
            if field:
                report = state.get(field)
                # Check if report exists and has content
                if not report or len(str(report)) < 5: 
                    all_ready = False
                    missing.append(analyst)
        
        if all_ready:
            logger.info("✅ [Barrier] 所有个股分析模块已完成，继续流程")
            return "continue"
        else:
            logger.info(f"⏳ [Barrier] 等待模块完成: {missing}")
            return "wait"

    def _setup_stock_graph(
        self, selected_analysts=["market", "social", "news", "fundamentals"]
    ):
        """Set up stock analysis workflow graph (Parallel Execution).
        
        Args:
            selected_analysts (list): List of analyst types to include.
        """
        if len(selected_analysts) == 0:
            raise ValueError("Trading Agents Graph Setup Error: no analysts selected!")
            
        from tradingagents.agents.utils.agent_utils import create_msg_delete, create_msg_pass

        # Create analyst nodes
        analyst_nodes = {}
        delete_nodes = {}
        tool_nodes = {}
        
        # 1. 准备节点配置
        analyst_config = {}
        
        # Market Analyst
        if "market" in selected_analysts:
            # 现在所有LLM都使用标准市场分析师（包括阿里百炼的OpenAI兼容适配器）
            llm_provider = self.config.get("llm_provider", "").lower()
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
                
            analyst_config["market"] = {
                "name": "Market Analyst",
                "creator": create_market_analyst,
                "tool_node": "tools_market",
                "tool_src": self.tool_nodes["market"],
                "clear_node": "Msg Clear Market",
                "condition": self.conditional_logic.should_continue_market
            }

        # Social Analyst
        if "social" in selected_analysts:
            analyst_config["social"] = {
                "name": "Social Analyst",
                "creator": create_social_media_analyst,
                "tool_node": "tools_social",
                "tool_src": self.tool_nodes["social"],
                "clear_node": "Msg Clear Social",
                "condition": self.conditional_logic.should_continue_social
            }

        # News Analyst
        if "news" in selected_analysts:
            analyst_config["news"] = {
                "name": "News Analyst",
                "creator": create_news_analyst,
                "tool_node": "tools_news",
                "tool_src": self.tool_nodes["news"],
                "clear_node": "Msg Clear News",
                "condition": self.conditional_logic.should_continue_news
            }

        # Fundamentals Analyst
        if "fundamentals" in selected_analysts:
            # Log debug info similar to original code
            llm_provider = self.config.get("llm_provider", "").lower()
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

            analyst_config["fundamentals"] = {
                "name": "Fundamentals Analyst",
                "creator": create_fundamentals_analyst,
                "tool_node": "tools_fundamentals",
                "tool_src": self.tool_nodes["fundamentals"],
                "clear_node": "Msg Clear Fundamentals",
                "condition": self.conditional_logic.should_continue_fundamentals
            }

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

        # Add analyst nodes to the graph (Parallel Nodes)
        for analyst_type, cfg in analyst_config.items():
            # Create node instances
            analyst_node = cfg["creator"](self.quick_thinking_llm, self.toolkit)
            # 使用 create_report_ensure_node 替代 create_msg_pass
            # 这样可以确保即使分析师失败（如死循环），也会生成一个占位符报告，防止 Barrier 阻塞整个流程
            clear_node = create_report_ensure_node(analyst_type)
            
            # Add nodes
            workflow.add_node(cfg["name"], analyst_node)
            workflow.add_node(cfg["clear_node"], clear_node)
            workflow.add_node(cfg["tool_node"], cfg["tool_src"])
            
            # Add edges
            # START -> Analyst (Parallel Start)
            workflow.add_edge(START, cfg["name"])
            
            # Analyst <-> Tools loop
            workflow.add_conditional_edges(
                cfg["name"],
                cfg["condition"],
                [cfg["tool_node"], cfg["clear_node"]]
            )
            workflow.add_edge(cfg["tool_node"], cfg["name"])
            
            # Clear -> Barrier (Converge)
            workflow.add_edge(cfg["clear_node"], "Stock Analysis Barrier")

        # Add other nodes
        workflow.add_node("Stock Analysis Barrier", self._stock_barrier_node)
        
        # Global Clear Node for Stock Context
        global_clear = create_msg_delete()
        workflow.add_node("Msg Clear Stock Context", global_clear)
        
        workflow.add_node("Bull Researcher", bull_researcher_node)
        workflow.add_node("Bear Researcher", bear_researcher_node)
        workflow.add_node("Research Manager", research_manager_node)
        workflow.add_node("Trader", trader_node)
        workflow.add_node("Risky Analyst", risky_analyst)
        workflow.add_node("Neutral Analyst", neutral_analyst)
        workflow.add_node("Safe Analyst", safe_analyst)
        workflow.add_node("Risk Judge", risk_manager_node)

        # Barrier -> Bull (Conditional: Wait for all)
        workflow.add_conditional_edges(
            "Stock Analysis Barrier",
            self._should_continue_stock_barrier,
            {
                "continue": "Msg Clear Stock Context",
                "wait": END
            }
        )
        
        workflow.add_edge("Msg Clear Stock Context", "Bull Researcher")

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
        
        logger.info("✅ [图构建] 个股分析并行工作流构建完成")
        return workflow.compile()
    
    def _index_barrier_node(self, state: AgentState):
        """Barrier node to synchronize parallel analysis branches."""
        # No operation needed, just a synchronization point
        return {}

    def _should_continue_barrier(self, state: AgentState):
        """Check if all selected analysts have completed their reports."""
        selected = state.get("selected_analysts", [])
        if not selected:
            # Fallback default if not set
            selected = ["macro", "policy", "news", "sector", "technical"]
        
        # Mapping: Analyst Type -> Report Field in AgentState
        mapping = {
            "macro": "macro_report",
            "policy": "policy_report",
            "news": "international_news_report",
            "sector": "sector_report",
            "technical": "technical_report"
        }
        
        all_ready = True
        missing = []
        for analyst in selected:
            # Handle potential mismatch in naming (e.g. "market" vs "macro" if mixed up)
            if analyst == "market": continue # Skip stock analysts if present
            if analyst == "fundamentals": continue
            
            field = mapping.get(analyst)
            if field:
                report = state.get(field)
                # Check if report exists and has content
                if not report or len(str(report)) < 5: 
                    all_ready = False
                    missing.append(analyst)
        
        if all_ready:
            logger.info("✅ [Barrier] 所有指数分析模块已完成，继续流程")
            return "continue"
        else:
            logger.info(f"⏳ [Barrier] 等待模块完成: {missing}")
            return "wait"

    def _setup_index_graph(self, selected_analysts=None):
        """
        Set up index analysis workflow graph (v2.4 - Parallel Execution).
        
        Index analysis flow:
        START → [Macro, Policy, News, Sector, Technical] (Parallel) 
              → Barrier → Index Bull Researcher ↔ Bear Researcher 
              → Strategy Advisor → END
        """
        from tradingagents.agents.analysts.macro_analyst import create_macro_analyst
        from tradingagents.agents.analysts.policy_analyst import create_policy_analyst
        from tradingagents.agents.analysts.international_news_analyst import create_international_news_analyst
        from tradingagents.agents.analysts.sector_analyst import create_sector_analyst
        from tradingagents.agents.analysts.technical_analyst import create_technical_analyst
        from tradingagents.agents.analysts.strategy_advisor import create_strategy_advisor
        from tradingagents.agents.researchers.index_bull_researcher import create_index_bull_researcher
        from tradingagents.agents.researchers.index_bear_researcher import create_index_bear_researcher
        from tradingagents.agents.utils.agent_utils import create_msg_delete, create_msg_pass, create_report_ensure_node
        
        # Risk Agents
        from tradingagents.agents.risk_mgmt.aggresive_debator import create_risky_debator
        from tradingagents.agents.risk_mgmt.conservative_debator import create_safe_debator
        from tradingagents.agents.risk_mgmt.neutral_debator import create_neutral_debator
        from tradingagents.agents.managers.risk_manager import create_risk_manager
        
        logger.info("🏗️ [图构建] 开始构建指数分析工作流 (并行版)")
        
        # Default analysts if none provided
        if not selected_analysts:
            selected_analysts = ["macro", "policy", "news", "sector", "technical"]
            
        logger.info(f"📋 [图构建] 选中的分析模块: {selected_analysts}")
        
        # 1. 创建工作流
        workflow = StateGraph(AgentState)
        
        # 新增：指数信息收集节点 (Index Info Collector)
        # 替代原有的 Symbol Validator，功能更强大
        def index_info_collector_node(state):
             code = state.get("company_of_interest")
             market_type = state.get("market_type", "A股")
             if not code:
                 return {}
             
             logger.info(f"🔍 [IndexInfoCollector] Collecting info for: {code} (market: {market_type})")
             
             try:
                 import asyncio
                 from tradingagents.utils.index_resolver import IndexResolver
                 
                 # 检查是否有正在运行的循环
                 try:
                     loop = asyncio.get_running_loop()
                 except RuntimeError:
                     loop = None
                 
                 if loop and loop.is_running():
                     logger.warning("⚠️ [IndexInfoCollector] Running in active loop, skipping async resolution")
                     return {}
                 else:
                     # 创建新循环运行
                     resolved = asyncio.run(IndexResolver.resolve(code, market_type))
                     
                     updates = {}
                     
                     # 如果解析出了不同的 symbol，更新 state
                     new_symbol = resolved.get("symbol")
                     if new_symbol and new_symbol != code:
                         logger.info(f"✅ [IndexInfoCollector] Updating symbol: {code} -> {new_symbol}")
                         updates["company_of_interest"] = new_symbol
                     
                     # 保存完整的指数信息到 state
                     if resolved:
                         logger.info(f"✅ [IndexInfoCollector] Info collected: {resolved.get('name')} ({resolved.get('source_type')})")
                         updates["index_info"] = resolved
                         
                     return updates
                     
             except Exception as e:
                 logger.error(f"❌ [IndexInfoCollector] Error: {e}")
             
             return {}

        workflow.add_node("Index Info Collector", index_info_collector_node)
        workflow.add_edge(START, "Index Info Collector")
        
        # 2. 定义映射表 (Analyst Type -> Node Config)
        # Config: (Node Name, Creator Func, Tool Node Name, Clear Node Name, Should Continue Func)
        analyst_config = {
            "macro": {
                "name": "Macro Analyst",
                "creator": create_macro_analyst,
                "tool_node": "tools_macro",
                "tool_src": self.tool_nodes.get("index_macro"),
                "clear_node": "Msg Clear Macro",
                "condition": self.conditional_logic.should_continue_macro
            },
            "policy": {
                "name": "Policy Analyst",
                "creator": create_policy_analyst,
                "tool_node": "tools_policy",
                "tool_src": self.tool_nodes.get("index_policy"),
                "clear_node": "Msg Clear Policy",
                "condition": self.conditional_logic.should_continue_policy
            },
            "news": {
                "name": "International News Analyst",
                "creator": create_international_news_analyst,
                "tool_node": "tools_international_news",
                "tool_src": self.tool_nodes.get("index_international_news"),
                "clear_node": "Msg Clear International News",
                "condition": self.conditional_logic.should_continue_international_news
            },
            "sector": {
                "name": "Sector Analyst",
                "creator": create_sector_analyst,
                "tool_node": "tools_sector",
                "tool_src": self.tool_nodes.get("index_sector"),
                "clear_node": "Msg Clear Sector",
                "condition": self.conditional_logic.should_continue_sector
            },
            "technical": {
                "name": "Technical Analyst",
                "creator": create_technical_analyst,
                "tool_node": "tools_technical",
                "tool_src": self.tool_nodes.get("index_technical"),
                "clear_node": "Msg Clear Technical",
                "condition": self.conditional_logic.should_continue_technical
            }
        }

        # 3. 动态添加并行分析节点
        active_analysts = []
        for analyst_type in selected_analysts:
            cfg = analyst_config.get(analyst_type)
            if not cfg:
                logger.warning(f"⚠️ 未知的分析类型: {analyst_type}，跳过")
                continue
                
            active_analysts.append(analyst_type)
            
            # Create nodes
            analyst_node = cfg["creator"](self.quick_thinking_llm, self.toolkit)
            # 使用 create_report_ensure_node 替代 create_msg_pass
            # 这样可以确保即使分析师失败（如死循环），也会生成一个占位符报告，防止 Barrier 阻塞整个流程
            clear_node = create_report_ensure_node(analyst_type)
            
            # Add to workflow
            workflow.add_node(cfg["name"], analyst_node)
            workflow.add_node(cfg["clear_node"], clear_node)
            workflow.add_node(cfg["tool_node"], cfg["tool_src"])
            
            # Add edges
            # Index Info Collector -> Analyst (Parallel Start)
            workflow.add_edge("Index Info Collector", cfg["name"])
            
            # Analyst <-> Tools loop
            workflow.add_conditional_edges(
                cfg["name"],
                cfg["condition"],
                [cfg["tool_node"], cfg["clear_node"]]
            )
            workflow.add_edge(cfg["tool_node"], cfg["name"])
            
            # Clear -> Barrier (Converge)
            workflow.add_edge(cfg["clear_node"], "Index Analysis Barrier")


        # 4. 添加汇聚与后续节点
        # Barrier Node
        workflow.add_node("Index Analysis Barrier", self._index_barrier_node)
        
        # Global Clear Node for Index Context
        global_clear = create_msg_delete()
        workflow.add_node("Msg Clear Index Context", global_clear)
        
        # Researchers & Strategy
        index_bull = create_index_bull_researcher(self.quick_thinking_llm, self.index_bull_memory)
        index_bear = create_index_bear_researcher(self.quick_thinking_llm, self.index_bear_memory)
        strategy = create_strategy_advisor(self.deep_thinking_llm, self.strategy_advisor_memory)
        strategy_clear = create_msg_delete()
        
        workflow.add_node("Index Bull Researcher", index_bull)
        workflow.add_node("Index Bear Researcher", index_bear)
        workflow.add_node("Strategy Advisor", strategy)
        workflow.add_node("Msg Clear Strategy", strategy_clear)
        
        # Risk Nodes
        risky_analyst = create_risky_debator(self.quick_thinking_llm)
        safe_analyst = create_safe_debator(self.quick_thinking_llm)
        neutral_analyst = create_neutral_debator(self.quick_thinking_llm)
        risk_manager = create_risk_manager(self.deep_thinking_llm, self.risk_manager_memory)
        
        workflow.add_node("Risky Analyst", risky_analyst)
        workflow.add_node("Safe Analyst", safe_analyst)
        workflow.add_node("Neutral Analyst", neutral_analyst)
        workflow.add_node("Risk Judge", risk_manager)
        
        # Barrier -> Bull (Conditional: Wait for all)
        workflow.add_conditional_edges(
            "Index Analysis Barrier",
            self._should_continue_barrier,
            {
                "continue": "Msg Clear Index Context",
                "wait": END  # End this parallel branch
            }
        )
        
        workflow.add_edge("Msg Clear Index Context", "Index Bull Researcher")
        
        # Bull <-> Bear Debate Loop
        workflow.add_conditional_edges(
            "Index Bull Researcher",
            self.conditional_logic.should_continue_debate,
            {
                "Bear Researcher": "Index Bear Researcher",
                "Research Manager": "Strategy Advisor",
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
        
        # Strategy -> Risk Layer
        workflow.add_conditional_edges(
            "Strategy Advisor",
            self.conditional_logic.should_continue_strategy,
            ["Msg Clear Strategy"],
        )
        workflow.add_edge("Msg Clear Strategy", "Risky Analyst")
        
        # Risk Loop
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
        
        logger.info("✅ [图构建] 指数分析并行工作流构建完成")
        return workflow.compile()
