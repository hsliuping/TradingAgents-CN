#!/usr/bin/env python3
"""
技术分析师 (Technical Analyst)

职责:
- 基于量化技术指标分析指数趋势
- 识别买卖点和风险信号
- 纯数据驱动，不带主观情绪
"""

from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
import json

from tradingagents.utils.logging_manager import get_logger

logger = get_logger("agents")


def create_technical_analyst(llm, toolkit):
    """
    创建技术分析师节点
    
    Args:
        llm: 语言模型实例
        toolkit: 工具包
        
    Returns:
        技术分析师节点函数
    """
    
    def technical_analyst_node(state):
        """技术分析师节点"""
        logger.info("📈 [技术分析师] 节点开始")
        
        # 1. 工具调用计数器
        tool_call_count = state.get("tech_tool_call_count", 0)
        max_tool_calls = 3
        
        # 2. 检查是否已有报告
        existing_report = state.get("technical_report", "")
        if existing_report and len(existing_report) > 100:
            logger.info(f"✅ [技术分析师] 已有报告，跳过分析")
            return {
                "messages": state["messages"],
                "technical_report": existing_report,
                "tech_tool_call_count": tool_call_count
            }
        
        # 3. 构建Prompt
        prompt = ChatPromptTemplate.from_messages([
            (
                "system",
                "你是一个严谨的量化技术分析师。你的任务是根据提供的技术指标报告，判断当前的市场趋势和潜在买卖点。\n"
                "\n"
                "📋 **分析任务**\n"
                "- 调用 fetch_technical_indicators 获取最新指标\n"
                "- 分析均线系统、动能指标、超买超卖状态\n"
                "- 给出明确的交易信号和仓位建议\n"
                "\n"
                "📊 **分析框架**\n"
                "1. **趋势识别**: 使用均线系统(MA5/20/60)判断当前是多头排列、空头排列还是震荡。\n"
                "2. **动能分析**: 使用 MACD 和成交量判断上涨/下跌的动能是否衰竭。\n"
                "3. **超买超卖**: 检查 RSI 和 KDJ 是否处于极端区域 (>80 或 <20)。\n"
                "4. **形态识别**: 识别关键的 K 线形态 (如启明星、吞噬、背离) (如果有描述)。\n"
                "\n"
                "🎯 **输出要求**\n"
                "必须返回严格的JSON格式报告:\n"
                "```json\n"
                "{{\n"
                "  \"trend_signal\": \"BULLISH (看多) / BEARISH (看空) / NEUTRAL (震荡)\",\n"
                "  \"position_suggestion\": 0.0-1.0, // 仅基于技术面的建议仓位\n"
                "  \"key_levels\": {{\n"
                "      \"support\": \"支撑位价格或描述\",\n"
                "      \"resistance\": \"压力位价格或描述\"\n"
                "  }},\n"
                "  \"risk_warning\": \"如：顶背离风险、跌破均线等\",\n"
                "  \"analysis_summary\": \"100字左右的技术面分析总结\"\n"
                "}}\n"
                "```\n"
                "\n"
                "⚠️ **注意事项**\n"
                "- 必须先调用 fetch_technical_indicators\n"
                "- 不要凭空猜测，一切基于数据\n"
                "- 这里的 position_suggestion 仅供参考，不作为最终决策\n"
            ),
            MessagesPlaceholder(variable_name="messages"),
        ])
        
        # 4. 绑定工具
        from tradingagents.tools.index_tools import fetch_technical_indicators
        tools = [fetch_technical_indicators]
        
        chain = prompt | llm.bind_tools(tools)
        
        # 5. 调用LLM
        result = chain.invoke({"messages": state["messages"]})
        
        # 6. 处理结果
        has_tool_calls = hasattr(result, 'tool_calls') and result.tool_calls and len(result.tool_calls) > 0
        
        if has_tool_calls:
            logger.info(f"📈 [技术分析师] 检测到工具调用，返回等待工具执行")
            return {
                "messages": [result],
                "tech_tool_call_count": tool_call_count + 1
            }
        
        # 7. 提取JSON报告
        report = _extract_json_report(result.content)
        
        if report:
            logger.info(f"✅ [技术分析师] JSON报告提取成功")
        else:
            logger.warning(f"⚠️ [技术分析师] JSON报告提取失败")
            report = result.content
        
        return {
            "messages": [result],
            "technical_report": report,
            "tech_tool_call_count": tool_call_count + 1
        }
    
    return technical_analyst_node


def _extract_json_report(content: str) -> str:
    """从LLM回复中提取JSON报告"""
    try:
        if '{' in content and '}' in content:
            start_idx = content.index('{')
            end_idx = content.rindex('}') + 1
            json_str = content[start_idx:end_idx]
            json.loads(json_str) # Validate
            return json_str
        return ""
    except Exception:
        return ""
