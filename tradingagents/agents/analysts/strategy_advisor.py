#!/usr/bin/env python3
"""
策略顾问 (Strategy Advisor)

职责:
- 综合宏观、政策、板块三个维度的分析
- 计算加权情绪得分
- 给出仓位建议
- 识别关键风险和机会板块
"""

from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
import json

from tradingagents.utils.logging_manager import get_logger

logger = get_logger("agents")


def create_strategy_advisor(llm):
    """
    创建策略顾问节点
    
    注意: Strategy Advisor不需要toolkit，因为它不调用工具，
    只是综合上游的宏观、政策、板块三个报告
    
    Args:
        llm: 语言模型实例（通常使用deep_thinking_llm）
        
    Returns:
        策略顾问节点函数
    """
    
    def strategy_advisor_node(state):
        """策略顾问节点"""
        logger.info("🎯 [策略顾问] 节点开始")
        
        # 1. 获取上游报告
        macro_report = state.get("macro_report", "")
        policy_report = state.get("policy_report", "")
        sector_report = state.get("sector_report", "")
        
        logger.info(f"🎯 [策略顾问] 上游报告状态:")
        logger.info(f"   - 宏观报告: {len(macro_report)} 字符")
        logger.info(f"   - 政策报告: {len(policy_report)} 字符")
        logger.info(f"   - 板块报告: {len(sector_report)} 字符")
        
        # 2. 验证上游报告完整性
        if not (macro_report and policy_report and sector_report):
            logger.warning(f"⚠️ [策略顾问] 上游报告不完整，返回降级报告")
            fallback_report = json.dumps({
                "market_outlook": "中性",
                "recommended_position": 0.5,
                "key_risks": ["数据不完整"],
                "opportunity_sectors": ["无法确定"],
                "rationale": "由于上游分析数据不完整，无法给出有效的策略建议。建议等待数据完整后重新分析。",
                "final_sentiment_score": 0.0,
                "confidence": 0.3
            }, ensure_ascii=False)
            
            return {
                "messages": state["messages"],
                "strategy_report": fallback_report
            }
        
        # 3. 构建Prompt（包含加权计算公式）
        prompt = ChatPromptTemplate.from_messages([
            (
                "system",
                "你是一位资深的投资策略顾问，负责综合各维度分析，给出投资建议。\n"
                "\n"
                "📋 **分析任务**\n"
                "- 综合宏观、政策、板块三个维度的分析\n"
                "- 计算加权情绪得分\n"
                "- 给出仓位建议\n"
                "- 识别关键风险和机会板块\n"
                "\n"
                "📊 **三个维度的分析报告**\n"
                "\n"
                "### 1️⃣ 宏观经济分析\n"
                "{macro_report}\n"
                "\n"
                "### 2️⃣ 政策分析\n"
                "{policy_report}\n"
                "\n"
                "### 3️⃣ 板块轮动分析\n"
                "{sector_report}\n"
                "\n"
                "🧮 **加权情绪计算公式**\n"
                "```\n"
                "final_sentiment = (\n"
                "    macro_sentiment * 0.3 * macro_confidence +\n"
                "    policy_sentiment * 0.4 * policy_confidence +\n"
                "    sector_sentiment * 0.3 * sector_confidence\n"
                ") / (\n"
                "    0.3 * macro_confidence + 0.4 * policy_confidence + 0.3 * sector_confidence\n"
                ")\n"
                "```\n"
                "\n"
                "权重说明:\n"
                "- 宏观: 30%（长期趋势）\n"
                "- 政策: 40%（关键驱动因素）\n"
                "- 板块: 30%（市场表现）\n"
                "\n"
                "📍 **仓位建议映射**\n"
                "- final_sentiment > 0.5  → 仓位 0.7-1.0（激进）\n"
                "- final_sentiment 0.2~0.5 → 仓位 0.5-0.7（稳健）\n"
                "- final_sentiment -0.2~0.2 → 仓位 0.3-0.5（谨慎）\n"
                "- final_sentiment < -0.2  → 仓位 0.0-0.3（防御）\n"
                "\n"
                "🎯 **输出要求**\n"
                "必须返回严格的JSON格式报告:\n"
                "```json\n"
                "{{\n"
                "  \"market_outlook\": \"看多|中性|看空\",\n"
                "  \"recommended_position\": 0.0-1.0,\n"
                "  \"key_risks\": [\"流动性收紧风险\", \"政策不确定性\"],\n"
                "  \"opportunity_sectors\": [\"新能源\", \"半导体\", \"AI\"],\n"
                "  \"rationale\": \"200-300字的策略依据，说明为什么给出这个建议\",\n"
                "  \"final_sentiment_score\": -1.0到1.0,\n"
                "  \"confidence\": 0.0-1.0\n"
                "}}\n"
                "```\n"
                "\n"
                "⚠️ **注意事项**\n"
                "- 基于上游三个报告进行综合分析\n"
                "- final_sentiment_score必须使用加权公式计算\n"
                "- recommended_position必须与final_sentiment_score匹配\n"
                "- opportunity_sectors必须来自板块报告的hot_themes或top_sectors\n"
                "- key_risks必须结合宏观、政策、板块的潜在风险\n"
                "- rationale必须清晰说明依据\n"
                "- JSON格式必须严格\n"
            ),
            MessagesPlaceholder(variable_name="messages"),
        ])
        
        # 4. 设置prompt变量
        prompt = prompt.partial(
            macro_report=macro_report,
            policy_report=policy_report,
            sector_report=sector_report
        )
        
        # 5. 直接调用LLM（不绑定工具）
        logger.info(f"🎯 [策略顾问] 开始调用LLM（不使用工具）...")
        chain = prompt | llm
        result = chain.invoke({"messages": state["messages"]})
        logger.info(f"🎯 [策略顾问] LLM调用完成")
        
        # 6. Strategy Advisor理论上不应该调用工具
        if hasattr(result, 'tool_calls') and result.tool_calls:
            logger.warning(f"⚠️ [策略顾问] 检测到意外的工具调用，将忽略")
        
        # 7. 提取JSON报告
        report = _extract_json_report(result.content)
        
        if report:
            logger.info(f"✅ [策略顾问] JSON报告提取成功: {len(report)} 字符")
        else:
            logger.warning(f"⚠️ [策略顾问] JSON报告提取失败，使用原始内容")
            report = result.content
        
        # 8. 返回状态更新
        return {
            "messages": [result],
            "strategy_report": report
        }
    
    return strategy_advisor_node


def _extract_json_report(content: str) -> str:
    """从LLM回复中提取JSON报告"""
    try:
        if '{' in content and '}' in content:
            start_idx = content.index('{')
            end_idx = content.rindex('}') + 1
            json_str = content[start_idx:end_idx]
            
            # 验证JSON有效性
            json.loads(json_str)
            
            logger.info(f"✅ [策略顾问] JSON提取成功")
            return json_str
        else:
            logger.warning(f"⚠️ [策略顾问] 内容中未找到JSON标记")
            return ""
    
    except json.JSONDecodeError as e:
        logger.warning(f"⚠️ [策略顾问] JSON解析失败: {e}")
        return ""
    except Exception as e:
        logger.error(f"❌ [策略顾问] JSON提取异常: {e}")
        return ""
