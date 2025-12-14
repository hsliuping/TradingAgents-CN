#!/usr/bin/env python3
"""
政策分析师 (Policy Analyst)

职责（遵循职责分离原则）:
- 分析货币政策、财政政策、产业政策
- 识别长期战略政策（5-10年）
- 政策分层（长期/中期/短期）
- 评估政策支持强度（强/中/弱）
- ❌ 不给出基础仓位建议（由Strategy Advisor统一决策）

设计原则:
- 信息分析层：只负责政策分析和强度评估
- 输出政策支持强度（强/中/弱），不输出仓位数值
- 决策由Strategy Advisor统一制定
"""

from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
import json

from tradingagents.utils.logging_manager import get_logger

logger = get_logger("agents")


def create_policy_analyst(llm, toolkit):
    """
    创建政策分析师节点
    
    Args:
        llm: 语言模型实例
        toolkit: 工具包，包含fetch_policy_news等工具
        
    Returns:
        政策分析师节点函数
    """
    
    def policy_analyst_node(state):
        """政策分析师节点"""
        logger.info("📰 [政策分析师] 节点开始")
        
        # 1. 工具调用计数器
        tool_call_count = state.get("policy_tool_call_count", 0)
        max_tool_calls = 3
        logger.info(f"🔧 [死循环修复] 政策分析师工具调用次数: {tool_call_count}/{max_tool_calls}")
        
        # 2. 检查是否已有报告
        existing_report = state.get("policy_report", "")
        if existing_report and len(existing_report) > 100:
            logger.info(f"✅ [政策分析师] 已有报告，跳过分析")
            return {
                "messages": state["messages"],
                "policy_report": existing_report,
                "policy_tool_call_count": tool_call_count
            }
        
        # 3. 降级方案
        if tool_call_count >= max_tool_calls:
            logger.warning(f"⚠️ [政策分析师] 达到最大工具调用次数，返回降级报告")
            fallback_report = json.dumps({
                "monetary_policy": "中性",
                "fiscal_policy": "稳健",
                "industry_policy": ["数据获取受限"],
                "long_term_policies": [],  # 🆕 长期政策列表
                "overall_support_strength": "弱",  # 🆕 政策支持强度
                "long_term_confidence": 0.3,  # 🆕 长期政策置信度
                "key_events": ["无法获取政策数据"],
                "market_impact": "中性",
                "analysis_summary": "由于数据获取限制，无法进行完整的政策分析。建议稍后重试。",
                "confidence": 0.3,
                "sentiment_score": 0.0
            }, ensure_ascii=False)
            
            return {
                "messages": state["messages"],
                "policy_report": fallback_report,
                "policy_tool_call_count": tool_call_count
            }
        
        # 4. 构建Prompt（扩展版 - 支持长期政策识别和强度评估）
        prompt = ChatPromptTemplate.from_messages([
            (
                "system",
                "你是一位专业的政策分析师，专注于经济金融政策分析。\n"
                "\n"
                "📋 **分析任务**\n"
                "- 获取最近的政策新闻\n"
                "- 分析货币政策、财政政策、产业政策\n"
                "- **🆕 识别长期战略政策**（5-10年）\n"
                "- **🆕 政策分层**（长期/中期/短期）\n"
                "- 识别关键政策事件\n"
                "- 评估政策支持强度\n"
                "- 识别政策受益板块\n"
                "\n"
                "📊 **分析维度**\n"
                "1. **货币政策**\n"
                "   - 宽松: 降息、降准、MLF降息\n"
                "   - 中性: 维持利率不变\n"
                "   - 紧缩: 加息、提高准备金率\n"
                "\n"
                "2. **财政政策**\n"
                "   - 积极: 减税降费、增加支出、专项债扩容\n"
                "   - 稳健: 保持财政平衡\n"
                "   - 紧缩: 增税、削减支出\n"
                "\n"
                "3. **产业政策映射**\n"
                "   - 自主可控 → 半导体、国防军工、操作系统\n"
                "   - 新能源 → 光伏、储能、新能源车\n"
                "   - 新质生产力 → AI、先进制造、生物医药\n"
                "   - 消费升级 → 高端消费、服务业\n"
                "   - 数字经济 → AI、云计算、大数据\n"
                "\n"
                "4. **🆕 政策分层标准** (重要)\n"
                "   **长期战略政策** (5-10年)\n"
                "   - 特征: 国家战略、五年规划、产业扶持\n"
                "   - 示例: '自主可控'、'新质生产力'、'碳中和'\n"
                "   - 识别关键词: 战略、规划、自主、创新、转型\n"
                "   - 持续期: 5-10年\n"
                "   \n"
                "   **中期政策措施** (1-3年)\n"
                "   - 特征: 阶段性政策、专项基金、税收优惠\n"
                "   - 示例: '新能源汽车补贴延长2年'\n"
                "   - 持续期: 1-3年\n"
                "   \n"
                "   **短期调控政策** (数月)\n"
                "   - 特征: 降息降准、临时性补贴\n"
                "   - 示例: '央行降准25BP'\n"
                "   - 持续期: 数月\n"
                "   - 注意: 短期政策由International News Analyst处理\n"
                "\n"
                "5. **🆕 政策支持强度评估标准**\n"
                "   **强** (Strong)\n"
                "   - 条件: 多个长期战略政策叠加 + 政策连续性高(0.8+)\n"
                "   - 示例: 自主可控连续多年强调 + 专项资金支持\n"
                "   \n"
                "   **中** (Medium)\n"
                "   - 条件: 单一长期政策 或 多个中期政策\n"
                "   - 示例: 阶段性产业支持政策\n"
                "   \n"
                "   **弱** (Weak)\n"
                "   - 条件: 仅短期政策 或 政策连续性低\n"
                "   - 示例: 政策提及少，无明确支持\n"
                "\n"
                "6. **市场影响评估**\n"
                "   - 正面: 多项宽松政策、产业政策支持\n"
                "   - 中性: 政策真空期、影响不明确\n"
                "   - 负面: 紧缩政策、监管趋严\n"
                "\n"
                "7. **情绪评分规则**\n"
                "   - 多项宽松政策叠加: 0.6 ~ 0.9\n"
                "   - 单一宽松政策: 0.3 ~ 0.5\n"
                "   - 政策真空期: -0.1 ~ 0.1\n"
                "   - 紧缩政策出台: -0.7 ~ -0.3\n"
                "\n"
                "🎯 **输出格式** (严格JSON - 扩展版)\n"
                "```json\n"
                "{{\n"
                "  \"monetary_policy\": \"宽松|中性|紧缩\",\n"
                "  \"fiscal_policy\": \"积极|稳健|紧缩\",\n"
                "  \"industry_policy\": [\"新能源\", \"半导体\", \"AI\"],\n"
                "  \n"
                "  // 🆕 长期政策识别\n"
                "  \"long_term_policies\": [\n"
                "    {{\n"
                "      \"name\": \"自主可控\",\n"
                "      \"duration\": \"长期 (5-10年)\",\n"
                "      \"support_strength\": \"强\",\n"
                "      \"beneficiary_sectors\": [\"半导体\", \"军工\"],\n"
                "      \"policy_continuity\": 0.9\n"
                "    }}\n"
                "  ],\n"
                "  \n"
                "  // 🆕 政策支持强度评估（不是仓位）\n"
                "  \"overall_support_strength\": \"强|中|弱\",\n"
                "  \"long_term_confidence\": 0.85,\n"
                "  \n"
                "  // 原有字段\n"
                "  \"key_events\": [\"降准0.5个百分点\", \"减税降费政策\"],\n"
                "  \"market_impact\": \"正面|中性|负面\",\n"
                "  \"analysis_summary\": \"100-200字的政策分析总结\",\n"
                "  \"confidence\": 0.0-1.0,\n"
                "  \"sentiment_score\": -1.0到1.0\n"
                "}}\n"
                "```\n"
                "\n"
                "⚠️ **职责分离原则 - 重要提醒**:\n"
                "- ❌ 不要输出 base_position_recommendation 字段\n"
                "- ❌ 不要输出 recommended_position 字段\n"
                "- ❌ 不要输出 position_adjustment 字段\n"
                "- ✅ 只评估政策支持强度(强/中/弱),不给出仓位建议\n"
                "- ✅ 仓位决策由Strategy Advisor统一制定\n"
                "\n"
                "⚠️ **注意事项**\n"
                "- 先调用fetch_policy_news工具获取政策新闻\n"
                "- 基于新闻内容识别长期战略政策\n"
                "- 评估政策支持强度(强/中/弱)\n"
                "- 识别具体的受益板块\n"
                "- JSON格式必须严格\n"
            ),
            MessagesPlaceholder(variable_name="messages"),
        ])
        
        # 5. 绑定工具
        from tradingagents.tools.index_tools import fetch_policy_news
        tools = [fetch_policy_news]
        
        logger.info(f"📰 [政策分析师] 绑定工具: fetch_policy_news")
        
        chain = prompt | llm.bind_tools(tools)
        
        # 6. 调用LLM
        logger.info(f"📰 [政策分析师] 开始调用LLM...")
        result = chain.invoke({"messages": state["messages"]})
        logger.info(f"📰 [政策分析师] LLM调用完成")
        
        # 7. 处理结果
        has_tool_calls = hasattr(result, 'tool_calls') and result.tool_calls and len(result.tool_calls) > 0
        
        if has_tool_calls:
            logger.info(f"📰 [政策分析师] 检测到工具调用，返回等待工具执行")
            return {
                "messages": [result],
                "policy_tool_call_count": tool_call_count + 1
            }
        
        # 8. 提取JSON报告
        report = _extract_json_report(result.content)
        
        if report:
            logger.info(f"✅ [政策分析师] JSON报告提取成功: {len(report)} 字符")
        else:
            logger.warning(f"⚠️ [政策分析师] JSON报告提取失败，使用原始内容")
            report = result.content
        
        # 9. 返回状态更新
        return {
            "messages": [result],
            "policy_report": report,
            "policy_tool_call_count": tool_call_count + 1
        }
    
    return policy_analyst_node


def _extract_json_report(content: str) -> str:
    """从LLM回复中提取JSON报告"""
    try:
        if '{' in content and '}' in content:
            start_idx = content.index('{')
            end_idx = content.rindex('}') + 1
            json_str = content[start_idx:end_idx]
            
            # 验证JSON有效性
            json.loads(json_str)
            
            logger.info(f"✅ [政策分析师] JSON提取成功")
            return json_str
        else:
            logger.warning(f"⚠️ [政策分析师] 内容中未找到JSON标记")
            return ""
    
    except json.JSONDecodeError as e:
        logger.warning(f"⚠️ [政策分析师] JSON解析失败: {e}")
        return ""
    except Exception as e:
        logger.error(f"❌ [政策分析师] JSON提取异常: {e}")
        return ""
