#!/usr/bin/env python3
"""
宏观经济分析师 (Macro Analyst)

职责:
- 分析宏观经济指标（GDP、CPI、PMI、M2、LPR等）
- 判断经济周期阶段（复苏/扩张/滞胀/衰退）
- 评估流动性状况（宽松/中性/紧缩）
- 给出宏观情绪评分
"""

from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
import json

from tradingagents.utils.logging_manager import get_logger

logger = get_logger("agents")


def create_macro_analyst(llm, toolkit):
    """
    创建宏观经济分析师节点
    
    Args:
        llm: 语言模型实例
        toolkit: 工具包，包含fetch_macro_data等工具
        
    Returns:
        宏观分析师节点函数
    """
    
    def macro_analyst_node(state):
        """宏观经济分析师节点"""
        logger.info("🌍 [宏观分析师] 节点开始")
        
        # 1. 工具调用计数器 - 防止死循环
        tool_call_count = state.get("macro_tool_call_count", 0)
        max_tool_calls = 5  # 增加最大调用次数到5次
        logger.info(f"🔧 [死循环修复] 宏观分析师工具调用次数: {tool_call_count}/{max_tool_calls}")
        
        # 2. 检查是否已有报告
        existing_report = state.get("macro_report", "")
        if existing_report and len(existing_report) > 100:
            logger.info(f"✅ [宏观分析师] 已有报告，跳过分析")
            return {
                "messages": state["messages"],
                "macro_report": existing_report,
                "macro_tool_call_count": tool_call_count
            }
        
        # 3. 降级方案：达到最大次数时返回降级报告
        if tool_call_count >= max_tool_calls:
            logger.warning(f"⚠️ [宏观分析师] 达到最大工具调用次数，返回降级报告")
            fallback_report = json.dumps({
                "economic_cycle": "中性",
                "liquidity": "中性",
                "key_indicators": ["数据获取受限"],
                "analysis_summary": "由于数据获取限制，无法进行完整的宏观分析。建议稍后重试。",
                "confidence": 0.3,
                "sentiment_score": 0.0,
                "data_note": "注意：宏观数据通常为历史数据，非实时数据。GDP、CPI等数据更新频率较低。"
            }, ensure_ascii=False)
            
            return {
                "messages": state["messages"],
                "macro_report": fallback_report,
                "macro_tool_call_count": tool_call_count
            }
        
        # 4. 获取当前日期
        current_date = state.get("trade_date", "")
        index_code = state.get("company_of_interest", "")
        
        logger.info(f"🌍 [宏观分析师] 分析指数: {index_code}, 日期: {current_date}")
        
        # 5. 构建Prompt
        prompt = ChatPromptTemplate.from_messages([
            (
                "system",
                "你是一位专业的宏观经济分析师，专注于指数分析。\n"
                "\n"
                "📋 **分析任务**\n"
                "- 获取最新的宏观经济数据\n"
                "- 分析经济周期阶段\n"
                "- 评估流动性环境\n"
                "- 提炼关键指标\n"
                "- 给出宏观情绪评分\n"
                "\n"
                "📊 **分析维度**\n"
                "1. **经济周期判断**（基于GDP、PMI）\n"
                "   - 复苏: GDP增速回升 + PMI > 50\n"
                "   - 扩张: GDP高速增长 + PMI > 52\n"
                "   - 滞胀: GDP增速下降 + CPI高企\n"
                "   - 衰退: GDP负增长 + PMI < 50\n"
                "\n"
                "2. **流动性评估**（基于M2、LPR）\n"
                "   - 宽松: M2增速 > 10% 且 LPR下降\n"
                "   - 中性: M2增速 8-10%\n"
                "   - 紧缩: M2增速 < 8% 且 LPR上升\n"
                "\n"
                "3. **情绪评分规则**\n"
                "   - 经济扩张 + 流动性宽松: 0.6 ~ 0.8\n"
                "   - 经济复苏 + 流动性中性: 0.3 ~ 0.5\n"
                "   - 经济衰退 + 流动性紧缩: -0.8 ~ -0.5\n"
                "\n"
                "🎯 **输出要求**\n"
                "必须返回严格的JSON格式报告，包含以下字段:\n"
                "``json\n"
                "{{\n"
                "  \"economic_cycle\": \"复苏|扩张|滞胀|衰退\",\n"
                "  \"liquidity\": \"宽松|中性|紧缩\",\n"
                "  \"key_indicators\": [\"GDP增速X%\", \"CPI同比X%\", \"PMI=XX\"],\n"
                "  \"analysis_summary\": \"100-200字的分析总结\",\n"
                "  \"confidence\": 0.0-1.0,\n"
                "  \"sentiment_score\": -1.0到1.0,\n"
                "  \"data_note\": \"关于数据时效性的说明\"\n"
                "}}\n"
                "```\n"
                "\n"
                "⚠️ **注意事项**\n"
                "- 先调用fetch_macro_data工具获取数据\n"
                "- 基于数据进行客观分析\n"
                "- JSON格式必须严格\n"
                "- confidence和sentiment_score必须在有效范围内\n"
                "- 请注意：宏观数据（GDP、CPI、PMI等）通常是历史数据，更新频率较低，需要在报告中说明\n"
            ),
            MessagesPlaceholder(variable_name="messages"),
        ])
        
        # 6. 绑定工具
        from tradingagents.tools.index_tools import fetch_macro_data
        tools = [fetch_macro_data]
        
        logger.info(f"🌍 [宏观分析师] 绑定工具: fetch_macro_data")
        
        chain = prompt | llm.bind_tools(tools)
        
        # 7. 调用LLM
        logger.info(f"🌍 [宏观分析师] 开始调用LLM...")
        result = chain.invoke({"messages": state["messages"]})
        logger.info(f"🌍 [宏观分析师] LLM调用完成")
        
        # 8. 处理结果
        logger.info(f"🌍 [宏观分析师] 响应类型: {type(result).__name__}")
        logger.info(f"🌍 [宏观分析师] 响应内容前500字符: {str(result.content)[:500]}")
        
        # 检查是否有工具调用
        has_tool_calls = hasattr(result, 'tool_calls') and result.tool_calls and len(result.tool_calls) > 0
        
        if has_tool_calls:
            logger.info(f"🌍 [宏观分析师] 检测到工具调用，返回等待工具执行")
            return {
                "messages": [result],
                "macro_tool_call_count": tool_call_count + 1
            }
        
        # 9. 提取JSON报告
        report = _extract_json_report(result.content)
        
        if report:
            logger.info(f"✅ [宏观分析师] JSON报告提取成功: {len(report)} 字符")
        else:
            logger.warning(f"⚠️ [宏观分析师] JSON报告提取失败，使用原始内容")
            report = result.content
        
        # 10. 返回状态更新
        return {
            "messages": [result],
            "macro_report": report,
            "macro_tool_call_count": tool_call_count + 1
        }
    
    return macro_analyst_node


def _extract_json_report(content: str) -> str:
    """
    从LLM回复中提取JSON报告
    
    Args:
        content: LLM的回复内容
        
    Returns:
        str: JSON字符串，如果提取失败则返回空字符串
    """
    try:
        # 查找JSON块
        if '{' in content and '}' in content:
            start_idx = content.index('{')
            end_idx = content.rindex('}') + 1
            json_str = content[start_idx:end_idx]
            
            # 验证JSON有效性
            json.loads(json_str)
            
            logger.info(f"✅ [宏观分析师] JSON提取成功: {json_str[:200]}...")
            return json_str
        else:
            logger.warning(f"⚠️ [宏观分析师] 内容中未找到JSON标记")
            return ""
    
    except json.JSONDecodeError as e:
        logger.warning(f"⚠️ [宏观分析师] JSON解析失败: {e}")
        return ""
    except Exception as e:
        logger.error(f"❌ [宏观分析师] JSON提取异常: {e}")
        return ""
