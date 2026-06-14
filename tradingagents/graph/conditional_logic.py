# TradingAgents/graph/conditional_logic.py

from tradingagents.agents.utils.agent_states import AgentState

# 导入统一日志系统
from tradingagents.utils.logging_init import get_logger
logger = get_logger("default")


# 死循环防护: 消息数量安全阈值，超过此数量强制退出分析师循环
MAX_MESSAGES = 100


class ConditionalLogic:
    """Handles conditional logic for determining graph flow."""

    def __init__(self, max_debate_rounds=1, max_risk_discuss_rounds=1):
        """Initialize with configuration parameters."""
        self.max_debate_rounds = max_debate_rounds
        self.max_risk_discuss_rounds = max_risk_discuss_rounds

    def should_continue_market(self, state: AgentState):
        """Determine if market analysis should continue."""
        from tradingagents.utils.logging_init import get_logger
        logger = get_logger("agents")

        messages = state["messages"]
        last_message = messages[-1]

        # 死循环修复: 添加工具调用次数检查
        tool_call_count = state.get("market_tool_call_count", 0)
        max_tool_calls = 300

        # 检查是否已经有市场分析报告
        market_report = state.get("market_report", "")

        logger.info(f"🔀 [条件判断] should_continue_market")
        logger.info(f"🔀 [条件判断] - 消息数量: {len(messages)}")
        logger.info(f"🔀 [条件判断] - 报告长度: {len(market_report)}")
        logger.info(f"🔧 [死循环修复] - 工具调用次数: {tool_call_count}/{max_tool_calls}")
        logger.info(f"🔀 [条件判断] - 最后消息类型: {type(last_message).__name__}")
        logger.info(f"🔀 [条件判断] - 是否有tool_calls: {hasattr(last_message, 'tool_calls')}")
        if hasattr(last_message, 'tool_calls'):
            logger.info(f"🔀 [条件判断] - tool_calls数量: {len(last_message.tool_calls) if last_message.tool_calls else 0}")
            if last_message.tool_calls:
                for i, tc in enumerate(last_message.tool_calls):
                    logger.info(f"🔀 [条件判断] - tool_call[{i}]: {tc.get('name', 'unknown')}")

        # 死循环修复: 如果达到最大工具调用次数，强制结束
        if tool_call_count >= max_tool_calls:
            logger.warning(f"🔧 [死循环修复] 达到最大工具调用次数，强制结束: Msg Clear Market")
            return "Msg Clear Market"

        # 死循环修复: 消息数量安全检查
        if len(messages) > MAX_MESSAGES:
            logger.warning(f"🔧 [死循环修复] 消息数量({len(messages)})超过安全阈值({MAX_MESSAGES})，强制结束: Msg Clear Market")
            return "Msg Clear Market"

        # 如果已经有报告内容，说明分析已完成，不再循环
        if market_report and len(market_report) > 100:
            logger.info(f"🔀 [条件判断] ✅ 报告已完成，返回: Msg Clear Market")
            return "Msg Clear Market"

        # 只有AIMessage才有tool_calls属性
        if hasattr(last_message, 'tool_calls') and last_message.tool_calls:
            logger.info(f"🔀 [条件判断] 🔧 检测到tool_calls，返回: tools_market")
            return "tools_market"

        logger.info(f"🔀 [条件判断] ✅ 无tool_calls，返回: Msg Clear Market")
        return "Msg Clear Market"

    def should_continue_social(self, state: AgentState):
        """Determine if social media analysis should continue."""
        from tradingagents.utils.logging_init import get_logger
        logger = get_logger("agents")

        messages = state["messages"]
        last_message = messages[-1]

        # 死循环修复: 添加工具调用次数检查
        tool_call_count = state.get("sentiment_tool_call_count", 0)
        max_tool_calls = 300

        # 检查是否已经有情绪分析报告
        sentiment_report = state.get("sentiment_report", "")

        logger.info(f"🔀 [条件判断] should_continue_social")
        logger.info(f"🔀 [条件判断] - 消息数量: {len(messages)}")
        logger.info(f"🔀 [条件判断] - 报告长度: {len(sentiment_report)}")
        logger.info(f"🔧 [死循环修复] - 工具调用次数: {tool_call_count}/{max_tool_calls}")

        # 死循环修复: 如果达到最大工具调用次数，强制结束
        if tool_call_count >= max_tool_calls:
            logger.warning(f"🔧 [死循环修复] 达到最大工具调用次数，强制结束: Msg Clear Social")
            return "Msg Clear Social"

        # 死循环修复: 消息数量安全检查
        if len(messages) > MAX_MESSAGES:
            logger.warning(f"🔧 [死循环修复] 消息数量({len(messages)})超过安全阈值({MAX_MESSAGES})，强制结束: Msg Clear Social")
            return "Msg Clear Social"

        # 如果已经有报告内容，说明分析已完成，不再循环
        if sentiment_report and len(sentiment_report) > 100:
            logger.info(f"🔀 [条件判断] ✅ 报告已完成，返回: Msg Clear Social")
            return "Msg Clear Social"

        # 只有AIMessage才有tool_calls属性
        if hasattr(last_message, 'tool_calls') and last_message.tool_calls:
            logger.info(f"🔀 [条件判断] 🔧 检测到tool_calls，返回: tools_social")
            return "tools_social"

        logger.info(f"🔀 [条件判断] ✅ 无tool_calls，返回: Msg Clear Social")
        return "Msg Clear Social"

    def should_continue_news(self, state: AgentState):
        """Determine if news analysis should continue."""
        from tradingagents.utils.logging_init import get_logger
        logger = get_logger("agents")

        messages = state["messages"]
        last_message = messages[-1]

        # 死循环修复: 添加工具调用次数检查
        tool_call_count = state.get("news_tool_call_count", 0)
        max_tool_calls = 300

        # 检查是否已经有新闻分析报告
        news_report = state.get("news_report", "")

        logger.info(f"🔀 [条件判断] should_continue_news")
        logger.info(f"🔀 [条件判断] - 消息数量: {len(messages)}")
        logger.info(f"🔀 [条件判断] - 报告长度: {len(news_report)}")
        logger.info(f"🔧 [死循环修复] - 工具调用次数: {tool_call_count}/{max_tool_calls}")

        # 死循环修复: 如果达到最大工具调用次数，强制结束
        if tool_call_count >= max_tool_calls:
            logger.warning(f"🔧 [死循环修复] 达到最大工具调用次数，强制结束: Msg Clear News")
            return "Msg Clear News"

        # 死循环修复: 消息数量安全检查
        if len(messages) > MAX_MESSAGES:
            logger.warning(f"🔧 [死循环修复] 消息数量({len(messages)})超过安全阈值({MAX_MESSAGES})，强制结束: Msg Clear News")
            return "Msg Clear News"

        # 如果已经有报告内容，说明分析已完成，不再循环
        if news_report and len(news_report) > 100:
            logger.info(f"🔀 [条件判断] ✅ 报告已完成，返回: Msg Clear News")
            return "Msg Clear News"

        # 只有AIMessage才有tool_calls属性
        if hasattr(last_message, 'tool_calls') and last_message.tool_calls:
            logger.info(f"🔀 [条件判断] 🔧 检测到tool_calls，返回: tools_news")
            return "tools_news"

        logger.info(f"🔀 [条件判断] ✅ 无tool_calls，返回: Msg Clear News")
        return "Msg Clear News"

    def should_continue_fundamentals(self, state: AgentState):
        """判断基本面分析是否应该继续"""
        from tradingagents.utils.logging_init import get_logger
        logger = get_logger("agents")

        messages = state["messages"]
        last_message = messages[-1]

        # 死循环修复: 添加工具调用次数检查
        tool_call_count = state.get("fundamentals_tool_call_count", 0)
        max_tool_calls = 300

        # 检查是否已经有基本面报告
        fundamentals_report = state.get("fundamentals_report", "")

        logger.info(f"🔀 [条件判断] should_continue_fundamentals")
        logger.info(f"🔀 [条件判断] - 消息数量: {len(messages)}")
        logger.info(f"🔀 [条件判断] - 报告长度: {len(fundamentals_report)}")
        logger.info(f"🔧 [死循环修复] - 工具调用次数: {tool_call_count}/{max_tool_calls}")
        logger.info(f"🔀 [条件判断] - 最后消息类型: {type(last_message).__name__}")
        
        # 🔍 [调试日志] 打印最后一条消息的详细内容
        logger.info(f"🤖 [条件判断] 最后一条消息详细内容:")
        logger.info(f"🤖 [条件判断] - 消息类型: {type(last_message).__name__}")
        if hasattr(last_message, 'content'):
            content_preview = last_message.content[:300] + "..." if len(last_message.content) > 300 else last_message.content
            logger.info(f"🤖 [条件判断] - 内容预览: {content_preview}")
        
        # 🔍 [调试日志] 打印tool_calls的详细信息
        logger.info(f"🔀 [条件判断] - 是否有tool_calls: {hasattr(last_message, 'tool_calls')}")
        if hasattr(last_message, 'tool_calls'):
            logger.info(f"🔀 [条件判断] - tool_calls数量: {len(last_message.tool_calls) if last_message.tool_calls else 0}")
            if last_message.tool_calls:
                logger.info(f"🔧 [条件判断] 检测到 {len(last_message.tool_calls)} 个工具调用:")
                for i, tc in enumerate(last_message.tool_calls):
                    logger.info(f"🔧 [条件判断] - 工具调用 {i+1}: {tc.get('name', 'unknown')} (ID: {tc.get('id', 'unknown')})")
                    if 'args' in tc:
                        logger.info(f"🔧 [条件判断] - 参数: {tc['args']}")
            else:
                logger.info(f"🔧 [条件判断] tool_calls为空列表")
        else:
            logger.info(f"🔧 [条件判断] 无tool_calls属性")

        # ✅ 优先级1: 如果已经有报告内容，说明分析已完成，不再循环
        if fundamentals_report and len(fundamentals_report) > 100:
            logger.info(f"🔀 [条件判断] ✅ 报告已完成，返回: Msg Clear Fundamentals")
            return "Msg Clear Fundamentals"

        # 死循环修复: 消息数量安全检查
        if len(messages) > MAX_MESSAGES:
            logger.warning(f"🔧 [死循环修复] 消息数量({len(messages)})超过安全阈值({MAX_MESSAGES})，强制结束: Msg Clear Fundamentals")
            return "Msg Clear Fundamentals"

        # ✅ 优先级2: 如果有tool_calls，去执行工具
        if hasattr(last_message, 'tool_calls') and last_message.tool_calls:
            # 检查是否超过最大调用次数
            if tool_call_count >= max_tool_calls:
                logger.warning(f"🔧 [死循环修复] 工具调用次数已达上限({tool_call_count}/{max_tool_calls})，但仍有tool_calls，强制结束")
                return "Msg Clear Fundamentals"

            logger.info(f"🔀 [条件判断] 🔧 检测到tool_calls，返回: tools_fundamentals")
            return "tools_fundamentals"

        # ✅ 优先级3: 没有tool_calls，正常结束
        logger.info(f"🔀 [条件判断] ✅ 无tool_calls，返回: Msg Clear Fundamentals")
        return "Msg Clear Fundamentals"

    def should_continue_debate(self, state: AgentState) -> str:
        """Determine if debate should continue."""
        current_count = state["investment_debate_state"]["count"]
        max_count = 2 * self.max_debate_rounds
        current_speaker = state["investment_debate_state"]["current_response"]

        # 🔍 详细日志
        logger.info(f"🔍 [投资辩论控制] 当前发言次数: {current_count}, 最大次数: {max_count} (配置轮次: {self.max_debate_rounds})")
        logger.info(f"🔍 [投资辩论控制] 当前发言者: {current_speaker}")

        if current_count >= max_count:
            logger.info(f"✅ [投资辩论控制] 达到最大次数，结束辩论 -> Research Manager")
            return "Research Manager"

        next_speaker = "Bear Researcher" if current_speaker.startswith("Bull") else "Bull Researcher"
        logger.info(f"🔄 [投资辩论控制] 继续辩论 -> {next_speaker}")
        return next_speaker

    def should_continue_risk_analysis(self, state: AgentState) -> str:
        """Determine if risk analysis should continue."""
        current_count = state["risk_debate_state"]["count"]
        max_count = 3 * self.max_risk_discuss_rounds
        latest_speaker = state["risk_debate_state"]["latest_speaker"]

        # 🔍 详细日志
        logger.info(f"🔍 [风险讨论控制] 当前发言次数: {current_count}, 最大次数: {max_count} (配置轮次: {self.max_risk_discuss_rounds})")
        logger.info(f"🔍 [风险讨论控制] 最后发言者: {latest_speaker}")

        if current_count >= max_count:
            logger.info(f"✅ [风险讨论控制] 达到最大次数，结束讨论 -> Risk Judge")
            return "Risk Judge"

        # 确定下一个发言者
        if latest_speaker.startswith("Risky"):
            next_speaker = "Safe Analyst"
        elif latest_speaker.startswith("Safe"):
            next_speaker = "Neutral Analyst"
        else:
            next_speaker = "Risky Analyst"

        logger.info(f"🔄 [风险讨论控制] 继续讨论 -> {next_speaker}")
        return next_speaker
