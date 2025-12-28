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
                "analysis_summary": "【宏观分析降级】由于数据获取限制，无法进行完整的宏观分析。建议稍后重试。",
                "confidence": 0.3,
                "sentiment_score": 0.0,
                "data_note": "注意：宏观数据通常为历史数据，非实时数据。GDP、CPI等数据更新频率较低。"
            }, ensure_ascii=False)
            
            return {
                "messages": state["messages"],
                "macro_report": fallback_report,
                "macro_tool_call_count": tool_call_count
            }
        
        # 4. 获取指数信息
        index_info = state.get("index_info", {})
        index_symbol = index_info.get("symbol", state.get("company_of_interest", "000001.SH"))
        index_name = index_info.get("name", "未知指数")
        current_date = state.get("trade_date", "")
        
        logger.info(f"🌍 [宏观分析师] 分析目标: {index_name} ({index_symbol}), 日期: {current_date}")
        
        # 5. 构建Prompt
        prompt = ChatPromptTemplate.from_messages([
            (
                "system",
                "你是一位专业的宏观经济分析师，专注于指数分析。\n"
                "\n"
                "⚠️ **核心规则 - 违反将导致系统错误**\n"
                "1. **禁止闲聊**：绝对禁止输出'我理解您希望...'、'我很抱歉...'等任何解释性文字。\n"
                "2. **强制JSON**：如果因为任何原因（如数据缺失、工具失败）无法生成分析，必须直接输出预定义的JSON降级报告（格式见下文）。\n"
                "3. **语言要求**：报告内容必须使用简体中文。\n"
                "\n"
                "📋 **分析任务**\n"
                "- 获取最新的宏观经济数据\n"
                "- 获取指数估值数据\n"
                "- 获取全市场资金流向\n"
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
                "2. **流动性评估**（基于M2、LPR、资金流向）\n"
                "   - 宽松: M2增速 > 10% 或 北向资金大幅净流入\n"
                "   - 中性: M2增速 8-10%\n"
                "   - 紧缩: M2增速 < 8% 或 主力资金大幅净流出\n"
                "\n"
                "3. **估值分析**\n"
                "   - 低估: PE/PB处于历史20%分位以下\n"
                "   - 合理: PE/PB处于历史20%-80%分位\n"
                "   - 高估: PE/PB处于历史80%分位以上\n"
                "\n"
                "4. **情绪评分规则**\n"
                "   - 经济扩张 + 流动性宽松 + 低估值: 0.7 ~ 1.0\n"
                "   - 经济复苏 + 流动性中性 + 合理估值: 0.3 ~ 0.6\n"
                "   - 经济衰退 + 流动性紧缩 + 高估值: -0.8 ~ -0.5\n"
                "\n"
                "🎯 **输出要求**\n"
                "请输出两部分内容：\n"
                "\n"
                "### 第一部分：深度宏观分析报告（Markdown格式）\n"
                "请撰写一份不少于400字的专业宏观分析报告，包含：\n"
                "1. **宏观经济现状**：基于GDP、PMI等数据分析当前经济所处周期阶段，并给出逻辑依据。\n"
                "2. **流动性环境分析**：基于M2、社融、资金流向等数据，深入分析市场流动性状况。\n"
                "3. **估值水平评估**：结合PE/PB历史分位，评估当前市场的投资性价比。\n"
                "4. **风险与机会**：指出当前宏观环境下的主要风险点和潜在机会。\n"
                "\n"
                "### 第二部分：结构化数据总结（JSON格式）\n"
                "请在报告末尾，将核心指标提取为JSON格式，包裹在 ```json 代码块中。字段要求如下：\n"
                "```json\n"
                "{{\n"
                "  \"economic_cycle\": \"复苏|扩张|滞胀|衰退\",\n"
                "  \"liquidity\": \"宽松|中性|紧缩\",\n"
                "  \"key_indicators\": [\"GDP增速X%\", \"CPI同比X%\", \"PMI=XX\"],\n"
                "  \"analysis_summary\": \"100字以内的精炼总结\",\n"
                "  \"confidence\": 0.0-1.0,\n"
                "  \"sentiment_score\": -1.0到1.0,\n"
                "  \"data_note\": \"关于数据时效性的说明\"\n"
                "}}\n"
                "```\n"
                "\n"
                "⚠️ **注意事项**\n"
                "- 务必先进行深度分析，展现你的思考过程，供人类投资者参考。\n"
                "- JSON部分必须严格符合格式，供下游决策模型使用。\n"
                "- 请注意：宏观数据（GDP、CPI、PMI等）通常是历史数据，更新频率较低，请在报告中说明。\n"
            ),
            MessagesPlaceholder(variable_name="messages"),
        ])
        
        # 6. 设置prompt变量
        prompt = prompt.partial(
            index_symbol=index_symbol,
            index_name=index_name
        )
        
        # 7. 绑定工具
        from tradingagents.tools.index_tools import fetch_macro_data
        tools = [fetch_macro_data]
        
        logger.info(f"🌍 [宏观分析师] 绑定工具: fetch_macro_data")
        
        chain = prompt | llm.bind_tools(tools)
        
        # 8. 调用LLM
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
        
        # 10. 直接使用完整回复作为报告（包含Markdown分析和JSON总结）
        # 下游的 Strategy Advisor 会使用 extract_json_block 自动提取 JSON 部分
        # 前端的 Report Exporter 会自动识别混合内容并进行展示
        report = result.content
        
        logger.info(f"✅ [宏观分析师] 生成完整分析报告: {len(report)} 字符")
        
        # 11. 返回状态更新
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
