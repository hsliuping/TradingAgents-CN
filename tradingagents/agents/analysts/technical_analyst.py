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

        # 3. 降级方案：达到最大次数时返回降级报告
        if tool_call_count >= max_tool_calls:
            logger.warning(f"⚠️ [技术分析师] 达到最大工具调用次数，返回降级报告")
            fallback_report = json.dumps({
                "trend_signal": "NEUTRAL",
                "confidence": 0.0,
                "key_levels": {
                    "support": "数据获取受限",
                    "resistance": "数据获取受限"
                },
                "indicators": {
                    "ma_alignment": "未知",
                    "macd_signal": "未知",
                    "rsi_status": "未知"
                },
                "analysis_summary": "【技术分析降级】由于数据获取限制或工具调用失败，无法进行完整的技术分析。请检查指数代码是否正确或稍后重试。",
                "risk_warning": "数据不完整，无法评估风险"
            }, ensure_ascii=False)
            
            return {
                "messages": state["messages"],
                "technical_report": fallback_report,
                "tech_tool_call_count": tool_call_count
            }
        
        # 4. 获取指数信息
        index_info = state.get("index_info", {})
        index_symbol = index_info.get("symbol", state.get("company_of_interest", "000001.SH"))
        index_name = index_info.get("name", "未知指数")
        
        logger.info(f"📈 [技术分析师] 分析目标: {index_name} ({index_symbol})")
        
        # 5. 构建Prompt
        prompt = ChatPromptTemplate.from_messages([
            (
                "system",
                "你是一个严谨的量化技术分析师。你的任务是根据提供的技术指标报告，判断当前的市场趋势和潜在买卖点。\n"
                "\n"
                "⚠️ **核心规则 - 违反将导致系统错误**\n"
                "1. **禁止闲聊**：绝对禁止输出'我理解您希望...'、'我很抱歉...'等任何解释性文字。\n"
                "2. **强制JSON**：如果因为任何原因（如数据缺失、工具失败）无法生成分析，必须直接输出预定义的JSON降级报告（格式见下文）。\n"
                "3. **语言要求**：报告内容必须使用简体中文。\n"
                "\n"
                "📋 **分析任务**\n"
                f"- 分析目标: {index_name} ({index_symbol})\n"
                "- 必须调用工具 `fetch_technical_indicators` 获取最新指标\n"
                "- 分析均线系统、动能指标、超买超卖状态\n"
                "- 给出明确的交易信号和仓位建议\n"
                "\n"
                "📊 **分析框架**\n"
                "1. **趋势识别**: 使用均线系统(MA5/20/60)判断当前是多头排列、空头排列还是震荡。\n"
                "2. **动能分析**: 使用 MACD 和成交量判断上涨/下跌的动能是否衰竭。\n"
                "3. **超买超卖**: 检查 RSI 和 KDJ 是否处于极端区域 (>80 或 <20)。\n"
                "\n"
                "🎯 **输出格式要求**\n"
                "请直接输出JSON格式，不要包含Markdown代码块标记（如 ```json ... ```），也不要包含任何前言或后语。\n"
                "JSON结构如下：\n"
                "{{\n"
                '    "trend_signal": "BULLISH/BEARISH/NEUTRAL",\n'
                '    "confidence": 0.0-1.0,\n'
                '    "key_levels": {{\n'
                '        "support": "支撑位描述",\n'
                '        "resistance": "阻力位描述"\n'
                '    }},\n'
                '    "indicators": {{\n'
                '        "ma_alignment": "多头/空头/纠缠",\n'
                '        "macd_signal": "金叉/死叉/背离/无效",\n'
                '        "rsi_status": "超买/超卖/中性"\n'
                '    }},\n'
                '    "analysis_summary": "200字以内的核心分析摘要",\n'
                '    "risk_warning": "主要风险提示"\n'
                "}}\n"
                "\n"
                "⚠️ **异常处理**\n"
                "如果工具返回'数据获取受限'或无法进行有效分析，请输出以下JSON：\n"
                "{{\n"
                '    "trend_signal": "NEUTRAL",\n'
                '    "confidence": 0.0,\n'
                '    "key_levels": {{ "support": "未知", "resistance": "未知" }},\n'
                '    "indicators": {{ "ma_alignment": "未知", "macd_signal": "未知", "rsi_status": "未知" }},\n'
                '    "analysis_summary": "【技术分析降级】数据获取受限，无法生成报告。",\n'
                '    "risk_warning": "数据不完整"\n'
                "}}\n"
            ),
            MessagesPlaceholder(variable_name="messages"),
        ])
        
        # 5. 绑定工具
        from tradingagents.tools.index_tools import fetch_technical_indicators
        tools = [fetch_technical_indicators]
        
        chain = prompt | llm.bind_tools(tools)
        
        # 8. 调用LLM
        # v2.4 并行执行优化：使用独立的消息历史
        msg_history = state.get("technical_messages", [])
        result = chain.invoke({"messages": msg_history})
        
        # 9. 处理结果
        has_tool_calls = hasattr(result, 'tool_calls') and result.tool_calls and len(result.tool_calls) > 0
        
        # 增加兜底检查：如果既没有工具调用，也不是有效JSON，则强制替换为降级报告
        if not has_tool_calls:
            content = result.content.strip()
            # 简单检查是否看起来像JSON
            if not (content.startswith("{") and content.endswith("}")):
                logger.warning(f"⚠️ [技术分析师] 输出非JSON且无工具调用，强制降级。内容: {content[:100]}...")
                fallback_json = json.dumps({
                    "trend_signal": "NEUTRAL",
                    "confidence": 0.0,
                    "key_levels": {"support": "未知", "resistance": "未知"},
                    "indicators": {"ma_alignment": "未知", "macd_signal": "未知", "rsi_status": "未知"},
                    "analysis_summary": "【技术分析降级】无法生成有效JSON报告，输出格式错误。",
                    "risk_warning": "数据不完整"
                }, ensure_ascii=False)
                return {
                    "technical_messages": state.get("technical_messages", []),
                    "technical_report": fallback_json,
                    "tech_tool_call_count": tool_call_count
                }

        if has_tool_calls:
            logger.info(f"📈 [技术分析师] 检测到工具调用: {result.tool_calls}")
            logger.info(f"📈 [技术分析师] 返回等待工具执行")
            return {
                "technical_messages": [result],
                "tech_tool_call_count": tool_call_count + 1
            }
        
        # 8. 直接使用完整回复作为报告（包含Markdown分析和JSON总结）
        # 下游的 Strategy Advisor 会使用 extract_json_block 自动提取 JSON 部分
        # 前端的 Report Exporter 会自动识别混合内容并进行展示
        report = result.content
        
        logger.info(f"✅ [技术分析师] 生成完整分析报告: {len(report)} 字符")
        
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
