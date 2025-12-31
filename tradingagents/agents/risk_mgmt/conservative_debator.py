from langchain_core.messages import AIMessage
import time
import json

# 导入统一日志系统
from tradingagents.utils.logging_init import get_logger
logger = get_logger("default")


def create_safe_debator(llm):
    def safe_node(state) -> dict:
        risk_debate_state = state["risk_debate_state"]
        history = risk_debate_state.get("history", "")
        safe_history = risk_debate_state.get("safe_history", "")

        current_risky_response = risk_debate_state.get("current_risky_response", "")
        current_neutral_response = risk_debate_state.get("current_neutral_response", "")

        market_research_report = state.get("market_report", "")
        sentiment_report = state.get("sentiment_report", "")
        news_report = state.get("news_report", "")
        fundamentals_report = state.get("fundamentals_report", "")
        
        # 指数分析字段
        macro_report = state.get("macro_report", "")
        policy_report = state.get("policy_report", "")
        sector_report = state.get("sector_report", "")
        intl_news_report = state.get("international_news_report", "")
        technical_report = state.get("technical_report", "")
        
        is_index = state.get("is_index", False)

        trader_decision = state.get("trader_investment_plan") or state.get("strategy_report", "")

        # 📊 记录输入数据长度
        logger.info(f"📊 [Safe Analyst] 输入数据长度统计 (Index Mode: {is_index}):")
        
        # 获取研究深度
        research_depth = state.get("research_depth", "标准")
        depth_instruction = ""
        if research_depth in ["深度", "全面"]:
            depth_instruction = "当前为深度分析模式。请详细推演风险传导路径（例如：美联储加息 -> 汇率贬值 -> 资金外流），并引用历史案例作为警示。"

        if is_index:
             context_reports = f"""
宏观经济报告：{macro_report}
政策分析报告：{policy_report}
板块轮动报告：{sector_report}
国际新闻报告：{intl_news_report}
技术分析报告：{technical_report}
"""
             logger.info(f"  - macro: {len(macro_report)}, policy: {len(policy_report)}, sector: {len(sector_report)}")
             
             # 指数分析专用 Prompt
             prompt = f"""作为保守风格的宏观策略师，您的职责是识别市场中被忽视的系统性风险，保护本金安全。您深知“牛市赚的钱，熊市由于风险控制不当而亏回去”的教训。

以下是策略顾问的初步决策：
{trader_decision}

您的任务是：
1. **识别下行风险**：基于宏观和政策报告，指出潜在的利空因素（如通胀粘性、政策不及预期、经济衰退迹象、外部冲击）。
2. **挑战激进观点**：反驳激进分析师的盲目乐观。指出所谓的“机会”背后可能隐藏的陷阱（如诱多、流动性陷阱）。
3. **强调防守价值**：在指数投资中，保住本金比追求短期收益更重要。建议通过降低仓位、配置防御性板块或增加现金比例来应对不确定性。
4. **利用数据**：引用 {context_reports} 中的负面指标（如CPI高企、汇率贬值、技术指标顶背离）来佐证你的观点。

{depth_instruction}

以下是当前对话历史：{history} 
激进分析师观点：{current_risky_response} 
中性分析师观点：{current_neutral_response}

请以稳重、严谨、警示性的语调进行辩论。时刻提醒大家关注尾部风险。
输出格式要求：Markdown格式，重点加粗，条理清晰。"""

        else:
             context_reports = f"""
市场研究报告：{market_research_report}
社交媒体情绪报告：{sentiment_report}
最新世界事务报告：{news_report}
公司基本面报告：{fundamentals_report}
"""
             logger.info(f"  - market_report: {len(market_research_report):,} 字符")
             
             # 个股分析原有 Prompt
             prompt = f"""作为安全/保守风险分析师，您的主要目标是保护资产、最小化波动性，并确保稳定、可靠的增长。您优先考虑稳定性、安全性和风险缓解，仔细评估潜在损失、经济衰退和市场波动。在评估交易员的决策或计划时，请批判性地审查高风险要素，指出决策可能使公司面临不当风险的地方，以及更谨慎的替代方案如何能够确保长期收益。以下是交易员/策略顾问的决策：

{trader_decision}

您的任务是积极反驳激进和中性分析师的论点，突出他们的观点可能忽视的潜在威胁或未能优先考虑可持续性的地方。直接回应他们的观点，利用以下数据来源为交易员决策的低风险方法调整建立令人信服的案例：

{context_reports}

{depth_instruction}

以下是当前对话历史：{history} 以下是激进分析师的最后回应：{current_risky_response} 以下是中性分析师的最后回应：{current_neutral_response}。如果其他观点没有回应，请不要虚构，只需提出您的观点。

通过质疑他们的乐观态度并强调他们可能忽视的潜在下行风险来参与讨论。解决他们的每个反驳点，展示为什么保守立场最终是公司资产最安全的道路。专注于辩论和批评他们的论点，证明低风险策略相对于他们方法的优势。

⚠️ **输出格式要求**
请使用 Markdown 格式输出，使观点结构清晰：
1. 使用 **加粗** 强调核心观点。
2. 使用列表（- 或 1.）列举论据。
3. 针对激进和中性分析师的观点，可以单独分段反驳。
4. 语言要稳重、严谨、有说服力。
"""

        logger.info(f"⏱️ [Safe Analyst] 开始调用LLM...")
        llm_start_time = time.time()

        response = llm.invoke(prompt)

        llm_elapsed = time.time() - llm_start_time
        logger.info(f"⏱️ [Safe Analyst] LLM调用完成，耗时: {llm_elapsed:.2f}秒")

        argument = f"Safe Analyst: {response.content}"

        new_count = risk_debate_state["count"] + 1
        logger.info(f"🛡️ [保守风险分析师] 发言完成，计数: {risk_debate_state['count']} -> {new_count}")

        new_risk_debate_state = {
            "history": history + "\n" + argument,
            "risky_history": risk_debate_state.get("risky_history", ""),
            "safe_history": safe_history + "\n" + argument,
            "neutral_history": risk_debate_state.get("neutral_history", ""),
            "latest_speaker": "Safe",
            "current_risky_response": risk_debate_state.get(
                "current_risky_response", ""
            ),
            "current_safe_response": argument,
            "current_neutral_response": risk_debate_state.get(
                "current_neutral_response", ""
            ),
            "count": new_count,
        }

        return {"risk_debate_state": new_risk_debate_state}

    return safe_node
