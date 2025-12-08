"""
工作流构建器

从 WorkflowDefinition 构建 LangGraph 图

核心设计：
1. 辩论节点(DEBATE)不是一个执行节点，而是控制流程的标记
2. 辩论参与者(如 bull_researcher, bear_researcher)通过条件边连接
3. 条件边检查状态中的辩论计数来决定继续辩论还是结束
"""

import logging
import os
from typing import Any, Callable, Dict, List, Optional, Set

logger = logging.getLogger(__name__)

from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import ToolNode

from .models import (
    WorkflowDefinition,
    NodeDefinition,
    EdgeDefinition,
    NodeType,
    EdgeType,
)
from ..agents import AgentRegistry, AgentFactory, AgentConfig

# 分析师类型映射 - 需要工具节点支持的智能体
ANALYST_TOOL_MAPPING = {
    "market_analyst": "market",
    "news_analyst": "news",
    "fundamentals_analyst": "fundamentals",
    "social_analyst": "social",
}


class LegacyDependencyProvider:
    """
    遗留智能体依赖提供者

    为适配器提供 LLM 和 Toolkit 实例
    """

    _instance = None

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self._config = config or {}
        self._quick_llm = None
        self._deep_llm = None
        self._toolkit = None
        self._memories = {}

    @classmethod
    def get_instance(cls, config: Optional[Dict[str, Any]] = None) -> "LegacyDependencyProvider":
        """获取单例实例"""
        if cls._instance is None:
            cls._instance = cls(config)
        elif config:
            # 如果有新配置，重置实例以便重新创建 LLM
            cls._instance._config.update(config)
            cls._instance._quick_llm = None
            cls._instance._deep_llm = None
            cls._instance._toolkit = None
        return cls._instance

    @classmethod
    def reset_instance(cls):
        """重置单例实例（用于测试或重新配置）"""
        cls._instance = None

    def get_llm(self, llm_type: str = "quick"):
        """
        获取 LLM 实例

        Args:
            llm_type: "quick" 或 "deep"
        """
        if llm_type == "deep" and self._deep_llm:
            return self._deep_llm
        if self._quick_llm:
            return self._quick_llm

        # 懒加载创建 LLM
        self._create_llm_instances()
        return self._deep_llm if llm_type == "deep" else self._quick_llm

    def get_toolkit(self):
        """获取 Toolkit 实例"""
        if self._toolkit is None:
            self._create_toolkit()
        return self._toolkit

    def get_memory(self, memory_type: str):
        """获取 Memory 实例"""
        if memory_type not in self._memories:
            self._create_memory(memory_type)
        return self._memories.get(memory_type)

    def _create_llm_instances(self):
        """
        创建 LLM 实例

        支持两种模式：
        1. 单厂家模式：quick 和 deep 使用同一厂家
        2. 混合模式：quick 和 deep 使用不同厂家

        旧代码中的使用方式：
        - quick_thinking_llm: 用于分析师、研究员(Bull/Bear)、交易员、风险辩论者
        - deep_thinking_llm: 用于研究经理(Research Manager)、风险经理(Risk Judge)
        """
        from tradingagents.default_config import DEFAULT_CONFIG
        from tradingagents.graph.trading_graph import create_llm_by_provider

        # 如果没有传入配置，从数据库获取
        if not self._config:
            db_config = self._get_llm_config_from_db()
            config = {**DEFAULT_CONFIG, **db_config}
        else:
            config = {**DEFAULT_CONFIG, **self._config}

        # 检查是否为混合模式（quick 和 deep 使用不同厂家）
        quick_provider = config.get("quick_llm_provider") or config.get("llm_provider", "deepseek")
        deep_provider = config.get("deep_llm_provider") or config.get("llm_provider", "deepseek")

        quick_model = config.get("quick_think_llm", "deepseek-chat")
        deep_model = config.get("deep_think_llm", "deepseek-chat")

        # 获取 URL 配置
        quick_url = config.get("backend_url", "")
        deep_url = config.get("deep_backend_url") or quick_url

        # 获取 API Key
        quick_api_key = config.get("quick_api_key") or config.get("api_key")
        deep_api_key = config.get("deep_api_key") or config.get("api_key")

        logger.info(f"[依赖提供者] 创建 LLM:")
        logger.info(f"  - Quick: provider={quick_provider}, model={quick_model}")
        logger.info(f"  - Deep: provider={deep_provider}, model={deep_model}")

        try:
            # 创建快速模型
            self._quick_llm = create_llm_by_provider(
                provider=quick_provider,
                model=quick_model,
                backend_url=quick_url,
                temperature=config.get("quick_temperature", 0.1),
                max_tokens=config.get("quick_max_tokens", 2000),
                timeout=config.get("quick_timeout", 60),
                api_key=quick_api_key
            )

            # 创建深度模型
            self._deep_llm = create_llm_by_provider(
                provider=deep_provider,
                model=deep_model,
                backend_url=deep_url,
                temperature=config.get("deep_temperature", 0.1),
                max_tokens=config.get("deep_max_tokens", 4000),
                timeout=config.get("deep_timeout", 120),
                api_key=deep_api_key
            )

            logger.info(f"[依赖提供者] LLM 实例创建成功")
            logger.info(f"  - Quick LLM: {type(self._quick_llm).__name__}")
            logger.info(f"  - Deep LLM: {type(self._deep_llm).__name__}")
        except Exception as e:
            logger.error(f"[依赖提供者] LLM 创建失败: {e}")
            raise

    def _get_llm_config_from_db(self) -> Dict[str, Any]:
        """从数据库获取 LLM 配置"""
        try:
            from pymongo import MongoClient
            from app.core.config import settings

            client = MongoClient(settings.MONGO_URI)
            db = client[settings.MONGO_DB]

            # 1. 获取系统配置中的默认模型
            configs_collection = db.system_configs
            doc = configs_collection.find_one({"is_active": True}, sort=[("version", -1)])

            if not doc or "llm_configs" not in doc:
                logger.warning("[依赖提供者] 数据库中没有 LLM 配置，使用默认配置")
                return {}

            llm_configs = doc["llm_configs"]

            # 找到第一个启用的非 google 模型作为默认模型
            # （因为 google 模型不适合中国区域直接使用）
            default_config = None
            for cfg in llm_configs:
                if cfg.get("enabled", True):
                    provider = cfg.get("provider", "").lower()
                    # 优先选择阿里百炼或 DeepSeek
                    if provider in ["dashscope", "deepseek"]:
                        default_config = cfg
                        break

            # 如果没找到首选厂家，使用任何可用的配置
            if not default_config:
                for cfg in llm_configs:
                    if cfg.get("enabled", True):
                        default_config = cfg
                        break

            if not default_config:
                logger.warning("[依赖提供者] 没有找到启用的 LLM 配置")
                return {}

            # 2. 获取厂家配置（API Key 和 base_url）
            provider_name = default_config.get("provider", "")
            model_name = default_config.get("model_name", "")
            providers_collection = db.llm_providers
            provider_doc = providers_collection.find_one({"name": provider_name})

            api_key = None
            backend_url = default_config.get("api_base", "")

            if provider_doc:
                api_key = provider_doc.get("api_key", "")
                if not backend_url:
                    backend_url = provider_doc.get("default_base_url", "")

            # 如果数据库没有 API Key，尝试从环境变量获取
            if not api_key or api_key.startswith("sk-xxx"):
                api_key = self._get_env_api_key(provider_name)

            result = {
                "llm_provider": provider_name,
                "quick_think_llm": model_name,
                "deep_think_llm": model_name,
                "backend_url": backend_url,
                "api_key": api_key,
                "quick_temperature": default_config.get("temperature", 0.1),
                "quick_max_tokens": default_config.get("max_tokens", 2000),
                "quick_timeout": default_config.get("timeout", 30),
            }

            logger.info(f"[依赖提供者] 从数据库获取配置: provider={provider_name}, model={model_name}, url={backend_url[:50] if backend_url else 'None'}...")

            client.close()
            return result

        except Exception as e:
            logger.warning(f"[依赖提供者] 从数据库获取配置失败: {e}")
            return {}

    def _get_env_api_key(self, provider_name: str) -> Optional[str]:
        """从环境变量获取 API Key"""
        env_key_map = {
            "openai": "OPENAI_API_KEY",
            "deepseek": "DEEPSEEK_API_KEY",
            "dashscope": "DASHSCOPE_API_KEY",
            "google": "GOOGLE_API_KEY",
            "zhipu": "ZHIPU_API_KEY",
            "qianfan": "QIANFAN_API_KEY",
            "siliconflow": "SILICONFLOW_API_KEY",
        }
        env_name = env_key_map.get(provider_name.lower())
        if env_name:
            return os.getenv(env_name)
        return None

    def _create_toolkit(self):
        """创建 Toolkit 实例"""
        from tradingagents.agents.utils.agent_utils import Toolkit
        from tradingagents.default_config import DEFAULT_CONFIG

        config = {**DEFAULT_CONFIG, **self._config}
        self._toolkit = Toolkit(config=config)
        logger.info("[依赖提供者] Toolkit 创建成功")

    def _create_memory(self, memory_type: str):
        """创建 Memory 实例"""
        from tradingagents.agents.utils.memory import FinancialSituationMemory
        from tradingagents.default_config import DEFAULT_CONFIG

        config = {**DEFAULT_CONFIG, **self._config}

        if config.get("memory_enabled", True):
            self._memories[memory_type] = FinancialSituationMemory(memory_type, config)
        else:
            self._memories[memory_type] = None

    def get_tool_nodes(self) -> Dict[str, ToolNode]:
        """获取工具节点（用于分析师的工具调用循环）"""
        toolkit = self.get_toolkit()
        return {
            "market": ToolNode([
                toolkit.get_stock_market_data_unified,
                toolkit.get_YFin_data_online,
                toolkit.get_stockstats_indicators_report_online,
                toolkit.get_YFin_data,
                toolkit.get_stockstats_indicators_report,
            ]),
            "social": ToolNode([
                toolkit.get_stock_sentiment_unified,
                toolkit.get_stock_news_openai,
                toolkit.get_reddit_stock_info,
            ]),
            "news": ToolNode([
                toolkit.get_stock_news_unified,
                toolkit.get_global_news_openai,
                toolkit.get_google_news,
                toolkit.get_finnhub_news,
                toolkit.get_reddit_news,
            ]),
            "fundamentals": ToolNode([
                toolkit.get_stock_fundamentals_unified,
                toolkit.get_finnhub_company_insider_sentiment,
                toolkit.get_finnhub_company_insider_transactions,
                toolkit.get_simfin_balance_sheet,
                toolkit.get_simfin_cashflow,
                toolkit.get_simfin_income_stmt,
                toolkit.get_china_stock_data,
                toolkit.get_china_fundamentals,
            ]),
        }


class WorkflowBuilder:
    """
    工作流构建器

    将 WorkflowDefinition 转换为可执行的 LangGraph

    用法:
        builder = WorkflowBuilder()
        graph = builder.build(workflow_definition)
        result = graph.invoke({"ticker": "AAPL", "trade_date": "2024-01-15"})
    """

    def __init__(
        self,
        registry: Optional[AgentRegistry] = None,
        factory: Optional[AgentFactory] = None,
        default_config: Optional[AgentConfig] = None,
        legacy_config: Optional[Dict[str, Any]] = None,
    ):
        from ..agents.registry import get_registry

        self.registry = registry or get_registry()
        self.factory = factory or AgentFactory(self.registry)
        self.default_config = default_config or AgentConfig()

        # 遗留依赖提供者（用于适配原有智能体）
        self._legacy_provider = LegacyDependencyProvider.get_instance(legacy_config)

        self._agents: Dict[str, Any] = {}  # 缓存创建的智能体
    
    def build(
        self,
        definition: WorkflowDefinition,
        state_schema: Optional[type] = None,
    ):
        """
        构建 LangGraph 图

        Args:
            definition: 工作流定义
            state_schema: 状态模式 (默认使用通用字典)

        Returns:
            编译后的 LangGraph
        """
        # 使用默认状态模式
        if state_schema is None:
            state_schema = self._get_default_state_schema()

        # 创建图
        graph = StateGraph(state_schema)

        # 首先识别辩论配置
        debate_configs = self._identify_debate_configs(definition)

        # 构建辩论参与者集合及其对应的 debate_key
        participant_debate_keys: Dict[str, str] = {}
        for debate_id, config in debate_configs.items():
            debate_key = f"_debate_{debate_id}_count"
            for p in config["participants"]:
                participant_debate_keys[p] = debate_key

        # 识别分析师节点（需要工具节点支持）
        analyst_nodes_info: Dict[str, str] = {}  # node_id -> analyst_type
        for node in definition.nodes:
            if node.agent_id and node.agent_id in ANALYST_TOOL_MAPPING:
                analyst_type = ANALYST_TOOL_MAPPING[node.agent_id]
                analyst_nodes_info[node.id] = analyst_type
                logger.info(f"[工具节点] 识别分析师节点: {node.id} -> {analyst_type}")

        # 获取工具节点
        tool_nodes = {}
        if analyst_nodes_info:
            tool_nodes = self._legacy_provider.get_tool_nodes()
            logger.info(f"[工具节点] 创建工具节点: {list(tool_nodes.keys())}")

        # 添加节点
        for node in definition.nodes:
            if node.type in (NodeType.START, NodeType.END):
                continue

            # 如果是辩论参与者，使用包装函数
            if node.id in participant_debate_keys:
                debate_key = participant_debate_keys[node.id]
                node_func = self._create_debate_participant_wrapper(node, debate_key)
            else:
                node_func = self._create_node_function(node)

            graph.add_node(node.id, node_func)

            # 如果是分析师节点，添加对应的工具节点和消息清理节点
            if node.id in analyst_nodes_info:
                analyst_type = analyst_nodes_info[node.id]
                tools_node_id = f"tools_{node.id}"
                clear_node_id = f"msg_clear_{node.id}"

                # 添加工具节点（包装以使用独立消息历史）
                wrapped_tool_node = self._create_tool_node_wrapper(
                    tool_nodes[analyst_type], node.id, analyst_type
                )
                graph.add_node(tools_node_id, wrapped_tool_node)
                logger.info(f"[工具节点] 添加工具节点: {tools_node_id}")

                # 添加消息清理节点
                graph.add_node(clear_node_id, self._create_msg_clear_node(node.id, analyst_type))
                logger.info(f"[工具节点] 添加消息清理节点: {clear_node_id}")

        # 添加边（包括工具循环边）
        self._add_edges(graph, definition, debate_configs, analyst_nodes_info)

        # 编译
        return graph.compile()

    def _create_msg_clear_node(self, node_id: str, analyst_type: str) -> Callable:
        """
        创建消息清理节点

        清理分析师的独立消息历史，避免消息无限累积。
        """
        messages_key = f"_{analyst_type}_messages"

        def safe_msg_clear(state):
            """清理分析师的独立消息历史"""
            logger.info(f"[消息清理] {node_id} - 清理独立消息历史: {messages_key}")
            # 清空独立消息历史
            return {messages_key: []}

        return safe_msg_clear

    def _create_tool_node_wrapper(
        self,
        tool_node: ToolNode,
        analyst_node_id: str,
        analyst_type: str
    ) -> Callable:
        """
        为工具节点创建包装器，使用分析师的独立消息历史
        """
        messages_key = f"_{analyst_type}_messages"

        def wrapped_tool_node(state):
            logger.info(f"[工具节点] tools_{analyst_node_id} - 开始执行")

            # 获取分析师独立的消息历史
            analyst_messages = list(state.get(messages_key, []))
            if not analyst_messages:
                logger.warning(f"[工具节点] {analyst_node_id} - 独立消息历史为空，使用共享消息")
                analyst_messages = list(state.get("messages", []))

            # 创建工具节点专用的 state
            tool_state = {**state, "messages": analyst_messages}

            # 执行工具节点
            result = tool_node.invoke(tool_state)

            # 更新独立消息历史，移除共享 messages 字段
            if "messages" in result:
                new_messages = result["messages"]
                if isinstance(new_messages, list):
                    updated_messages = analyst_messages + new_messages
                else:
                    updated_messages = analyst_messages + [new_messages]
                # 存储到独立消息字段
                result[messages_key] = updated_messages
                # 移除共享 messages 字段
                del result["messages"]
                logger.info(f"[工具节点] {analyst_node_id} - 更新消息历史，消息数: {len(updated_messages)}")

            logger.info(f"[工具节点] tools_{analyst_node_id} - 执行完成")
            return result

        return wrapped_tool_node

    def _create_analyst_condition_func(self, node_id: str, analyst_type: str) -> Callable:
        """
        创建分析师节点的条件函数
        判断是否有工具调用，决定路由到工具节点还是消息清理节点
        使用分析师的独立消息历史
        """
        tools_node_id = f"tools_{node_id}"
        clear_node_id = f"msg_clear_{node_id}"
        messages_key = f"_{analyst_type}_messages"

        # 报告字段映射
        report_field_map = {
            "market": "market_report",
            "social": "sentiment_report",
            "news": "news_report",
            "fundamentals": "fundamentals_report",
        }
        report_field = report_field_map.get(analyst_type, f"{analyst_type}_report")

        # 工具计数字段映射
        tool_count_field_map = {
            "market": "market_tool_call_count",
            "social": "sentiment_tool_call_count",
            "news": "news_tool_call_count",
            "fundamentals": "fundamentals_tool_call_count",
        }
        tool_count_field = tool_count_field_map.get(analyst_type, f"{analyst_type}_tool_call_count")

        def condition_func(state):
            """判断是否继续工具调用循环（使用独立消息历史）"""
            # 使用分析师独立的消息历史
            messages = state.get(messages_key, [])
            if not messages:
                # 如果没有独立消息，回退到共享消息
                messages = state.get("messages", [])

            if not messages:
                logger.info(f"🔀 [{node_id}] 无消息，返回: {clear_node_id}")
                return clear_node_id

            last_message = messages[-1]
            report = state.get(report_field, "")
            tool_call_count = state.get(tool_count_field, 0)
            max_tool_calls = 3  # 最大工具调用次数

            logger.info(f"🔀 [{node_id}] 条件判断 (独立消息: {messages_key}):")
            logger.info(f"  - 消息数量: {len(messages)}")
            logger.info(f"  - 报告长度: {len(report)}")
            logger.info(f"  - 工具调用次数: {tool_call_count}/{max_tool_calls}")
            logger.info(f"  - 最后消息类型: {type(last_message).__name__}")

            # 如果已有报告，结束循环
            if report and len(report) > 100:
                logger.info(f"🔀 [{node_id}] ✅ 报告已完成，返回: {clear_node_id}")
                return clear_node_id

            # 如果达到最大工具调用次数，强制结束
            if tool_call_count >= max_tool_calls:
                logger.warning(f"🔀 [{node_id}] ⚠️ 达到最大调用次数，返回: {clear_node_id}")
                return clear_node_id

            # 检查是否有工具调用
            if hasattr(last_message, 'tool_calls') and last_message.tool_calls:
                logger.info(f"🔀 [{node_id}] 🔧 检测到工具调用，返回: {tools_node_id}")
                return tools_node_id

            logger.info(f"🔀 [{node_id}] ✅ 无工具调用，返回: {clear_node_id}")
            return clear_node_id

        return condition_func

    def _create_analyst_wrapper(
        self,
        analyst_node: Callable,
        node_id: str,
        node_label: str,
        agent_id: str,
        analyst_type: str
    ) -> Callable:
        """
        为分析师创建包装器，使用独立的消息历史

        这解决了多个分析师并行执行时共享 messages 字段导致的问题：
        - 每个分析师使用独立的消息字段（如 _fundamentals_messages）
        - 避免工具调用和响应混乱
        """
        from langchain_core.messages import HumanMessage, SystemMessage

        # 独立消息字段名
        messages_key = f"_{analyst_type}_messages"

        def wrapped_analyst(state):
            logger.info(f"[节点执行] 🚀 {node_id} ({node_label}) - 开始执行 (分析师: {agent_id})")

            # 打印调试信息
            logger.info(f"[分析师调试] {node_id} - 独立消息字段: {messages_key}")
            logger.info(f"[分析师调试] {node_id} - 共享messages数量: {len(state.get('messages', []))}")
            logger.info(f"[分析师调试] {node_id} - 独立messages数量: {len(state.get(messages_key, []))}")

            # 打印状态中的计数器
            for key in ["market_tool_call_count", "sentiment_tool_call_count", "news_tool_call_count", "fundamentals_tool_call_count"]:
                if key in state:
                    logger.info(f"[分析师调试] {node_id} - 状态中 {key}: {state.get(key)}")

            # 获取分析师独立的消息历史
            analyst_messages = list(state.get(messages_key, []))

            if not analyst_messages:
                # 第一次调用：从 state["messages"] 中提取基本消息
                base_messages = []
                for msg in state.get("messages", []):
                    if isinstance(msg, (HumanMessage, SystemMessage)):
                        base_messages.append(msg)
                analyst_messages = base_messages
                logger.info(f"[分析师] {node_id} - 初始化消息历史，基础消息数: {len(base_messages)}")
            else:
                logger.info(f"[分析师] {node_id} - 使用现有消息历史，消息数: {len(analyst_messages)}")
                # 打印消息类型
                for i, msg in enumerate(analyst_messages):
                    logger.info(f"[分析师] {node_id} - 消息[{i}]: {type(msg).__name__}")

            # 创建分析师专用的 state（使用独立消息）
            analyst_state = {**state, "messages": analyst_messages}

            # 调用分析师节点
            result = analyst_node(analyst_state)

            # 打印返回结果中的计数器
            for key in ["market_tool_call_count", "sentiment_tool_call_count", "news_tool_call_count", "fundamentals_tool_call_count"]:
                if key in result:
                    logger.info(f"[分析师] {node_id} - 返回结果包含 {key}: {result[key]}")

            # 更新独立消息历史，移除共享 messages 字段
            if "messages" in result:
                new_messages = result["messages"]
                if isinstance(new_messages, list):
                    updated_messages = analyst_messages + new_messages
                else:
                    updated_messages = analyst_messages + [new_messages]
                # 存储到独立消息字段
                result[messages_key] = updated_messages
                # 移除共享 messages 字段，避免污染
                del result["messages"]
                logger.info(f"[分析师] {node_id} - 更新消息历史，消息数: {len(updated_messages)}")

            logger.info(f"[节点执行] ✅ {node_id} ({node_label}) - 执行完成")
            return result

        return wrapped_analyst
    
    def _get_default_state_schema(self) -> type:
        """
        获取默认状态模式

        使用 TypedDict 但包含 __extra_items__ 来支持动态字段
        参考 tradingagents 的 AgentState 设计
        """
        from typing import Annotated, Any, List
        from typing_extensions import TypedDict
        from langgraph.graph import MessagesState
        import operator

        def merge_dict(left: dict, right: dict) -> dict:
            """合并两个字典，用于处理并发更新"""
            if left is None:
                return right
            if right is None:
                return left
            result = left.copy()
            result.update(right)
            return result

        class WorkflowState(MessagesState):
            # 基本信息
            company_of_interest: Annotated[str, "股票代码"]
            trade_date: Annotated[str, "交易日期"]

            # 分析报告
            market_report: Annotated[str, "市场分析报告"]
            fundamentals_report: Annotated[str, "基本面分析报告"]
            news_report: Annotated[str, "新闻分析报告"]
            sentiment_report: Annotated[str, "情绪分析报告"]

            # 研究结果
            bull_report: Annotated[str, "看多研究报告"]
            bear_report: Annotated[str, "看空研究报告"]
            investment_plan: Annotated[str, "投资计划"]
            trader_investment_plan: Annotated[str, "交易员投资计划"]

            # 最终决策
            final_decision: Annotated[str, "最终决策"]
            risk_assessment: Annotated[str, "风险评估"]
            final_trade_decision: Annotated[str, "最终交易决策"]

            # 辩论状态 - 使用 merge_dict reducer 来处理并发更新
            investment_debate_state: Annotated[dict, merge_dict]
            risk_debate_state: Annotated[dict, merge_dict]

            # 辩论计数 - 注意使用 operator.add 来处理并发更新
            _debate_debate_count: Annotated[int, operator.add]
            _debate_risk_debate_count: Annotated[int, operator.add]

            # 辩论配置
            _max_debate_rounds: Annotated[int, "最大辩论轮数"]
            _max_risk_rounds: Annotated[int, "最大风险讨论轮数"]

            # 分析师独立消息历史（避免并行执行时消息混乱）
            # 注意：这些字段用于工具调用循环，每个分析师使用自己的消息历史
            _market_messages: Annotated[List, "市场分析师消息历史"]
            _social_messages: Annotated[List, "社媒分析师消息历史"]
            _news_messages: Annotated[List, "新闻分析师消息历史"]
            _fundamentals_messages: Annotated[List, "基本面分析师消息历史"]

            # 分析师工具调用计数（防止死循环）
            market_tool_call_count: Annotated[int, "市场分析师工具调用次数"]
            sentiment_tool_call_count: Annotated[int, "社媒分析师工具调用次数"]
            news_tool_call_count: Annotated[int, "新闻分析师工具调用次数"]
            fundamentals_tool_call_count: Annotated[int, "基本面分析师工具调用次数"]

        return WorkflowState
    
    def _create_node_function(self, node: NodeDefinition) -> Callable:
        """为节点创建执行函数"""

        if node.type == NodeType.CONDITION:
            return self._create_condition_node(node)
        elif node.type == NodeType.PARALLEL:
            return self._create_parallel_node(node)
        elif node.type == NodeType.MERGE:
            return self._create_merge_node(node)
        elif node.type == NodeType.DEBATE:
            return self._create_debate_node(node)
        else:
            return self._create_agent_node(node)

    def _create_agent_node(self, node: NodeDefinition) -> Callable:
        """创建智能体节点"""
        agent_id = node.agent_id
        node_id = node.id
        node_label = node.label or node_id

        if agent_id is None:
            raise ValueError(f"节点 {node.id} 缺少 agent_id")

        # 合并节点配置
        config = AgentConfig(**{
            **self.default_config.model_dump(),
            **node.config
        })

        # 首先尝试使用新架构创建智能体
        if self.registry.is_registered(agent_id):
            agent = self.factory.create(agent_id, config)
            self._agents[node.id] = agent

            # 包装以添加日志
            def logged_agent(state, _agent=agent, _id=node_id, _label=node_label):
                logger.info(f"[节点执行] 🚀 {_id} ({_label}) - 开始执行")
                result = _agent(state)
                logger.info(f"[节点执行] ✅ {_id} ({_label}) - 执行完成")
                return result
            return logged_agent

        # 尝试使用遗留适配器
        legacy_node = self._try_create_legacy_agent(agent_id)
        if legacy_node is not None:
            self._agents[node.id] = legacy_node

            # 检查是否是分析师节点（需要独立消息历史）
            if agent_id in ANALYST_TOOL_MAPPING:
                analyst_type = ANALYST_TOOL_MAPPING[agent_id]
                return self._create_analyst_wrapper(legacy_node, node_id, node_label, agent_id, analyst_type)

            def logged_legacy(state, _node=legacy_node, _id=node_id, _label=node_label, _agent_id=agent_id):
                logger.info(f"[节点执行] 🚀 {_id} ({_label}) - 开始执行 (遗留适配器: {_agent_id})")
                result = _node(state)
                logger.info(f"[节点执行] ✅ {_id} ({_label}) - 执行完成")
                return result
            return logged_legacy

        # 智能体未实现，返回占位函数
        def placeholder_node(state, _id=node_id, _label=node_label, _agent_id=agent_id):
            logger.info(f"[节点执行] 🔸 {_id} ({_label}) - 占位执行 (智能体 {_agent_id} 未实现)")
            return {
                f"{_agent_id}_report": f"[{_agent_id}] 智能体未实现"
            }
        return placeholder_node

    def _try_create_legacy_agent(self, agent_id: str) -> Optional[Callable]:
        """
        尝试使用遗留适配器创建智能体

        Args:
            agent_id: 智能体 ID

        Returns:
            可调用的节点函数，如果不支持则返回 None
        """
        # 智能体到工厂函数的映射
        factory_map = {
            # 分析师
            "market_analyst": ("tradingagents.agents.analysts.market_analyst", "create_market_analyst", "toolkit"),
            "news_analyst": ("tradingagents.agents.analysts.news_analyst", "create_news_analyst", "toolkit"),
            "fundamentals_analyst": ("tradingagents.agents.analysts.fundamentals_analyst", "create_fundamentals_analyst", "toolkit"),
            "social_analyst": ("tradingagents.agents.analysts.social_media_analyst", "create_social_media_analyst", "toolkit"),
            # 研究员
            "bull_researcher": ("tradingagents.agents.researchers.bull_researcher", "create_bull_researcher", "bull_memory"),
            "bear_researcher": ("tradingagents.agents.researchers.bear_researcher", "create_bear_researcher", "bear_memory"),
            # 交易员
            "trader": ("tradingagents.agents.trader.trader", "create_trader", "trader_memory"),
            # 管理者
            "research_manager": ("tradingagents.agents.managers.research_manager", "create_research_manager", "invest_judge_memory"),
            "risk_manager": ("tradingagents.agents.managers.risk_manager", "create_risk_manager", "risk_manager_memory"),
            # 风险辩论者
            "risky_analyst": ("tradingagents.agents.risk_mgmt.aggresive_debator", "create_risky_debator", None),
            "safe_analyst": ("tradingagents.agents.risk_mgmt.conservative_debator", "create_safe_debator", None),
            "neutral_analyst": ("tradingagents.agents.risk_mgmt.neutral_debator", "create_neutral_debator", None),
        }

        if agent_id not in factory_map:
            return None

        module_path, func_name, dep_type = factory_map[agent_id]

        try:
            import importlib
            module = importlib.import_module(module_path)
            factory_func = getattr(module, func_name)

            # 获取 LLM
            llm = self._legacy_provider.get_llm("quick")

            # 根据依赖类型获取第二个参数
            if dep_type == "toolkit":
                second_arg = self._legacy_provider.get_toolkit()
            elif dep_type:
                second_arg = self._legacy_provider.get_memory(dep_type)
            else:
                second_arg = None

            # 创建节点函数
            if second_arg is not None:
                node_func = factory_func(llm, second_arg)
            else:
                # 风险辩论者只需要 LLM
                node_func = factory_func(llm)

            logger.info(f"[遗留适配器] 成功创建: {agent_id}")
            return node_func

        except Exception as e:
            logger.warning(f"[遗留适配器] 创建失败 {agent_id}: {e}")
            return None

    def _create_condition_node(self, node: NodeDefinition) -> Callable:
        """创建条件节点"""
        condition_expr = node.condition or "True"
        node_id = node.id
        node_label = node.label or node_id

        def condition_node(state):
            logger.info(f"[节点执行] 🔀 {node_id} ({node_label}) - 条件判断")
            # 评估条件
            try:
                result = eval(condition_expr, {"state": state})
                logger.info(f"[节点执行] 🔀 {node_id} 结果: {result}")
                return {"_condition_result": bool(result)}
            except Exception as e:
                logger.error(f"[节点执行] ❌ {node_id} 条件评估错误: {e}")
                return {"_condition_result": True, "_condition_error": str(e)}

        return condition_node

    def _create_parallel_node(self, node: NodeDefinition) -> Callable:
        """创建并行节点 (标记开始)"""
        node_id = node.id
        node_label = node.label or node_id

        def parallel_node(state):
            logger.info(f"[节点执行] ⚡ {node_id} ({node_label}) - 并行开始")
            return {"_parallel_start": node_id}
        return parallel_node

    def _create_merge_node(self, node: NodeDefinition) -> Callable:
        """创建合并节点"""
        node_id = node.id
        node_label = node.label or node_id

        def merge_node(state):
            logger.info(f"[节点执行] 🔗 {node_id} ({node_label}) - 合并完成")
            return {"_parallel_end": node_id}
        return merge_node

    def _create_debate_node(self, node: NodeDefinition) -> Callable:
        """
        创建辩论节点 - 协调多个参与者进行多轮辩论

        辩论节点本身不执行分析，而是初始化辩论状态。
        实际的辩论流程通过条件边控制。

        注意：使用 operator.add 作为 reducer，所以不需要初始化计数为0
        """
        participants = node.config.get("participants", [])
        rounds = node.config.get("rounds", 1)
        node_id = node.id
        node_label = node.label or node_id

        def debate_node(state):
            logger.info(f"[节点执行] 💬 {node_id} ({node_label}) - 辩论开始, 参与者: {participants}")
            return {
                f"{node_id}_status": "debate_started",
                "_debate_node": node_id,
                "_debate_participants": participants,
                "_debate_rounds": rounds,
            }
        return debate_node

    def _create_debate_participant_wrapper(
        self,
        node: NodeDefinition,
        debate_key: str
    ) -> Callable:
        """
        为辩论参与者包装执行函数，自动递增辩论计数

        使用 operator.add 作为 reducer，每次返回增量 1
        """
        original_func = self._create_agent_node(node)

        def wrapped(state):
            # 先执行原始函数（已包含日志）
            result = original_func(state)
            # 返回增量 1（会被 operator.add 累加到当前值）
            result[debate_key] = 1
            return result

        return wrapped

    def _add_edges(
        self,
        graph: StateGraph,
        definition: WorkflowDefinition,
        debate_configs: Optional[Dict[str, Dict[str, Any]]] = None,
        analyst_nodes_info: Optional[Dict[str, str]] = None
    ) -> None:
        """
        添加边到图

        辩论流程设计：
        - 辩论节点 → 第一个参与者（普通边）
        - 参与者之间使用条件边（检查计数决定继续或结束）
        - 最后一个参与者 → 下一阶段（通过条件边控制）

        分析师工具循环设计：
        - 分析师节点 → 条件边 → 工具节点/消息清理节点
        - 工具节点 → 分析师节点（循环）
        - 消息清理节点 → 下一个节点
        """
        start_node = definition.get_start_node()
        added_edges: Set[tuple] = set()

        if debate_configs is None:
            debate_configs = self._identify_debate_configs(definition)

        if analyst_nodes_info is None:
            analyst_nodes_info = {}

        # 收集所有辩论参与者
        all_participants: Set[str] = set()
        for config in debate_configs.values():
            all_participants.update(config["participants"])

        # 添加 START 边
        if start_node:
            for edge in definition.get_edges_from(start_node.id):
                graph.add_edge(START, edge.target)

        # 1. 先处理辩论流程的边
        for debate_id, config in debate_configs.items():
            participants = config["participants"]

            # 辩论节点 → 第一个参与者
            graph.add_edge(debate_id, participants[0])
            added_edges.add((debate_id, participants[0]))

            # 为每个参与者添加条件边
            for i, participant in enumerate(participants):
                self._add_participant_conditional_edge(
                    graph, participant, config, i, debate_id
                )
                # 标记所有从参与者出发的边为已处理
                for edge in definition.get_edges_from(participant):
                    added_edges.add((participant, edge.target))

        # 2. 处理分析师节点的工具循环边
        for node_id, analyst_type in analyst_nodes_info.items():
            tools_node_id = f"tools_{node_id}"
            clear_node_id = f"msg_clear_{node_id}"

            # 分析师节点 → 条件边 → 工具节点/消息清理节点
            condition_func = self._create_analyst_condition_func(node_id, analyst_type)
            graph.add_conditional_edges(
                node_id,
                condition_func,
                [tools_node_id, clear_node_id]
            )
            logger.info(f"[工具循环] 添加条件边: {node_id} -> [{tools_node_id}, {clear_node_id}]")

            # 工具节点 → 分析师节点（循环）
            graph.add_edge(tools_node_id, node_id)
            logger.info(f"[工具循环] 添加循环边: {tools_node_id} -> {node_id}")

            # 找到分析师节点的下一个目标节点
            for edge in definition.get_edges_from(node_id):
                target = edge.target
                target_node = definition.get_node(target)

                # 消息清理节点 → 原来的目标节点
                if target_node and target_node.type == NodeType.END:
                    graph.add_edge(clear_node_id, END)
                else:
                    graph.add_edge(clear_node_id, target)
                logger.info(f"[工具循环] 添加出边: {clear_node_id} -> {target}")

                # 标记边为已处理
                added_edges.add((node_id, target))

        # 3. 处理普通边
        for edge in definition.edges:
            source_node = definition.get_node(edge.source)
            target_node = definition.get_node(edge.target)

            if source_node is None or target_node is None:
                continue
            if source_node.type == NodeType.START:
                continue

            edge_key = (edge.source, edge.target)
            if edge_key in added_edges:
                continue

            # 跳过辩论节点的所有出边（已在上面处理）
            if source_node.type == NodeType.DEBATE:
                continue

            # 跳过参与者的边（已在上面处理）
            if source_node.id in all_participants:
                continue

            # 跳过分析师节点的边（已在上面处理）
            if source_node.id in analyst_nodes_info:
                continue

            # 普通边
            if target_node.type == NodeType.END:
                graph.add_edge(edge.source, END)
            elif edge.type == EdgeType.CONDITIONAL:
                self._add_conditional_edge(graph, edge, definition)
            else:
                graph.add_edge(edge.source, edge.target)
            added_edges.add(edge_key)

    def _add_participant_conditional_edge(
        self,
        graph: StateGraph,
        participant: str,
        debate_config: Dict[str, Any],
        participant_index: int,
        debate_id: str
    ) -> None:
        """为辩论参与者添加条件边"""
        participants = debate_config["participants"]
        max_rounds = int(debate_config["rounds"]) if debate_config["rounds"] else 1
        next_node = debate_config["next_node"]
        debate_key = debate_config["debate_key"]
        num_participants = len(participants)

        # 下一个参与者
        next_idx = (participant_index + 1) % num_participants
        next_participant = participants[next_idx]

        # 根据辩论类型选择动态轮数的 state key
        # "risk" 相关的辩论使用 _max_risk_rounds，其他使用 _max_debate_rounds
        is_risk_debate = "risk" in debate_id.lower()
        dynamic_rounds_key = "_max_risk_rounds" if is_risk_debate else "_max_debate_rounds"

        # 创建路由函数
        def create_router(
            _debate_key: str,
            _max_rounds: int,
            _next_participant: str,
            _next_node: str,
            _num_participants: int,
            _dynamic_rounds_key: str,
            _participant: str
        ):
            def router(state):
                count = state.get(_debate_key, 0)
                dynamic_rounds = state.get(_dynamic_rounds_key, _max_rounds)
                max_count = dynamic_rounds * _num_participants
                logger.info(
                    f"[辩论路由] {_participant}: count={count}, max={max_count} "
                    f"(rounds={dynamic_rounds}, participants={_num_participants})"
                )
                if count >= max_count:
                    logger.info(f"[辩论路由] {_participant} -> {_next_node} (辩论结束)")
                    return _next_node if _next_node else END
                logger.info(f"[辩论路由] {_participant} -> {_next_participant} (继续辩论)")
                return _next_participant
            return router

        router = create_router(
            debate_key, max_rounds, next_participant, next_node,
            num_participants, dynamic_rounds_key, participant
        )

        targets = [next_participant]
        if next_node and next_node != next_participant:
            targets.append(next_node)

        graph.add_conditional_edges(participant, router, targets)

    def _identify_debate_configs(
        self, definition: WorkflowDefinition
    ) -> Dict[str, Dict[str, Any]]:
        """识别工作流中的辩论配置"""
        debate_configs = {}

        for node in definition.nodes:
            if node.type == NodeType.DEBATE:
                participants = node.config.get("participants", [])
                rounds_raw = node.config.get("rounds", 1)

                # 处理 rounds 可能是字符串的情况（如 "auto", "1" 等）
                if isinstance(rounds_raw, str):
                    if rounds_raw.lower() == "auto" or not rounds_raw.isdigit():
                        rounds = 1  # 默认1轮，实际会从 state 读取
                    else:
                        rounds = int(rounds_raw)
                else:
                    rounds = int(rounds_raw) if rounds_raw else 1

                # 找到辩论后的下一个节点
                next_node = None
                for edge in definition.get_edges_from(node.id):
                    target = definition.get_node(edge.target)
                    if target and target.id not in participants:
                        next_node = edge.target
                        break

                debate_configs[node.id] = {
                    "participants": participants,
                    "rounds": rounds,
                    "next_node": next_node,
                    "debate_key": f"_debate_{node.id}_count"
                }

        return debate_configs

    def _add_conditional_edge(
        self,
        graph: StateGraph,
        edge: EdgeDefinition,
        definition: WorkflowDefinition
    ) -> None:
        """添加普通条件边"""
        all_edges = definition.get_edges_from(edge.source)

        def route(state):
            result = state.get("_condition_result", True)
            for e in all_edges:
                if e.condition == "true" and result:
                    return e.target
                if e.condition == "false" and not result:
                    return e.target
            return all_edges[0].target if all_edges else END

        targets = {e.target for e in all_edges}
        graph.add_conditional_edges(edge.source, route, list(targets))

