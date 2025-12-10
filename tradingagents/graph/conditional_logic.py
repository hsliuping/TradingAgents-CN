# TradingAgents/graph/conditional_logic.py
"""
条件逻辑模块 - 处理 LangGraph 工作流中的条件判断

1阶段智能体的条件判断方法通过 __getattr__ 动态生成，
无需为每个分析师单独编写硬编码的方法。
"""

from tradingagents.agents.utils.agent_states import AgentState

# 导入统一日志系统
from tradingagents.utils.logging_init import get_logger
logger = get_logger("default")


class ConditionalLogic:
    """Handles conditional logic for determining graph flow."""

    def __init__(self, max_debate_rounds=1, max_risk_discuss_rounds=1):
        """Initialize with configuration parameters."""
        self.max_debate_rounds = max_debate_rounds
        self.max_risk_discuss_rounds = max_risk_discuss_rounds

    # ========== 1阶段智能体条件判断 ==========
    # 所有1阶段智能体的条件判断都通过 _generic_should_continue 和 __getattr__ 动态处理
    # 不再需要为每个分析师单独编写硬编码的方法

    def _generic_should_continue(self, state: AgentState, analyst_type: str):
        """
        通用的条件判断方法，用于判断任意1阶段分析师是否应该继续
        
        所有1阶段智能体共享此逻辑，通过 __getattr__ 动态调用。
        
        Args:
            state: 当前状态
            analyst_type: 分析师类型（internal_key，如 "market", "fundamentals", "china_market"）
            
        Returns:
            下一个节点名称
        """
        from tradingagents.utils.logging_init import get_logger
        logger = get_logger("agents")

        messages = state["messages"]
        last_message = messages[-1]

        # 死循环修复: 添加工具调用次数检查
        tool_call_count_key = f"{analyst_type}_tool_call_count"
        tool_call_count = state.get(tool_call_count_key, 0)
        max_tool_calls = 3

        # 检查是否已经有分析报告
        report_key = f"{analyst_type}_report"
        report = state.get(report_key, "")

        # 生成节点名称（首字母大写）
        capitalized_type = analyst_type.replace('_', ' ').title().replace(' ', '_')
        clear_node = f"Msg Clear {capitalized_type}"
        tools_node = f"tools_{analyst_type}"

        logger.info(f"🔀 [条件判断] should_continue_{analyst_type}")
        logger.info(f"🔀 [条件判断] - 消息数量: {len(messages)}")
        logger.info(f"🔀 [条件判断] - 报告长度: {len(report)}")
        logger.info(f"🔧 [死循环修复] - 工具调用次数: {tool_call_count}/{max_tool_calls}")
        logger.info(f"🔀 [条件判断] - 最后消息类型: {type(last_message).__name__}")

        # 🔍 [调试日志] 打印tool_calls的详细信息
        if hasattr(last_message, 'tool_calls'):
            logger.info(f"🔀 [条件判断] - tool_calls数量: {len(last_message.tool_calls) if last_message.tool_calls else 0}")
            if last_message.tool_calls:
                for i, tc in enumerate(last_message.tool_calls):
                    logger.info(f"🔀 [条件判断] - tool_call[{i}]: {tc.get('name', 'unknown')}")

        # 死循环修复: 如果达到最大工具调用次数，强制结束
        if tool_call_count >= max_tool_calls:
            logger.warning(f"🔧 [死循环修复] 达到最大工具调用次数，强制结束: {clear_node}")
            return clear_node

        # 如果已经有报告内容，说明分析已完成，不再循环
        if report and len(report) > 100:
            logger.info(f"� [条件 判断] ✅ 报告已完成，返回: {clear_node}")
            return clear_node

        # 只有AIMessage才有tool_calls属性
        if hasattr(last_message, 'tool_calls') and last_message.tool_calls:
            logger.info(f"🔀 [条件判断] 🔧 检测到tool_calls，返回: {tools_node}")
            return tools_node

        logger.info(f"🔀 [条件判断] ✅ 无tool_calls，返回: {clear_node}")
        return clear_node

    # ========== 2阶段：投资辩论 ==========

    def should_continue_debate(self, state: AgentState) -> str:
        """Determine if debate should continue."""
        current_count = state["investment_debate_state"]["count"]
        max_count = 2 * self.max_debate_rounds
        current_speaker = state["investment_debate_state"]["current_response"]

        # 🔍 详细日志
        logger.info(f"🔍 [投资辩论控制] 当前发言次数: {current_count}, 最大次数: {max_count} (配置轮次: {self.max_debate_rounds})")
        logger.info(f"🔍 [投资辩论控制] 当前发言者: {current_speaker}")

        if current_count >= max_count:
            # 检查是否有 phase4_enabled (Trader)
            phase4_enabled = state.get("phase4_enabled", False)
            phase3_enabled = state.get("phase3_enabled", False)
            
            logger.info(f"✅ [投资辩论控制] 达到最大次数，结束辩论")
            
            # 根据配置决定下一个节点
            if phase4_enabled:
                logger.info(f"👉 下一站: Trader")
                return "Trader"
            elif phase3_enabled:
                logger.info(f"👉 下一站: Risky Analyst")
                return "Risky Analyst"
            else:
                logger.info(f"👉 下一站: Summary Agent")
                return "Summary Agent"

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

    # ========== 动态方法处理 ==========

    def __getattr__(self, name: str):
        """
        动态处理未定义的 should_continue_xxx 方法
        
        当访问 should_continue_xxx 时，如果没有显式定义，
        会自动创建一个使用通用逻辑的方法。
        
        这样可以支持动态添加的分析师，无需为每个分析师单独编写条件判断方法。
        """
        if name.startswith("should_continue_"):
            analyst_type = name.replace("should_continue_", "")
            
            def dynamic_should_continue(state: AgentState):
                return self._generic_should_continue(state, analyst_type)
            
            return dynamic_should_continue
        
        raise AttributeError(f"'{type(self).__name__}' object has no attribute '{name}'")
