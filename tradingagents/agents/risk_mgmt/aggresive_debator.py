import time
import json

# 导入统一日志系统
from tradingagents.utils.logging_init import get_logger
logger = get_logger("default")


def create_risky_debator(llm):
    def risky_node(state) -> dict:
        risk_debate_state = state["risk_debate_state"]
        history = risk_debate_state.get("history", "")
        risky_history = risk_debate_state.get("risky_history", "")

        current_safe_response = risk_debate_state.get("current_safe_response", "")
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
        logger.info(f"📊 [Risky Analyst] 输入数据长度统计 (Index Mode: {is_index}):")
        
        # 获取研究深度
        research_depth = state.get("research_depth", "标准")
        depth_instruction = ""
        if research_depth in ["深度", "全面"]:
            depth_instruction = "当前为深度分析模式。请不仅给出结论，还要详细列出潜在的上涨逻辑链条，并引用具体数据支持你的激进观点。"

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
             prompt = f"""作为激进风格的宏观策略师，您的职责是敏锐地捕捉市场中的上涨机会，特别是在其他人犹豫不决时。您相信市场总是存在结构性机会，无论是政策红利、流动性宽松还是情绪修复。

以下是策略顾问的初步决策：
{trader_decision}

您的任务是：
1. **挖掘上行潜力**：基于提供的宏观和政策报告，指出被低估的利好因素（如政策转向宽松、经济数据超预期、外资流入等）。
2. **挑战保守观点**：直接反驳保守和中性分析师的担忧。告诉他们为什么他们的担忧是多余的，或者是已经被市场消化的。
3. **强调踏空风险**：在指数投资中，踏空牛市起点的代价往往比短期回调更昂贵。强调“此时不买，更待何时”。
4. **利用数据**：引用 {context_reports} 中的具体指标（如PMI回升、成交量放大、北向资金流入）来佐证你的观点。

{depth_instruction}

以下是当前对话历史：{history} 
保守分析师观点：{current_safe_response} 
中性分析师观点：{current_neutral_response}

请以激进、自信、富有感染力的语调进行辩论。不要害怕提出大胆的预测，只要有逻辑支持。
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
             prompt = f"""作为激进风险分析师，您的职责是积极倡导高回报、高风险的投资机会，强调大胆策略和竞争优势。在评估交易员的决策或计划时，请重点关注潜在的上涨空间、增长潜力和创新收益——即使这些伴随着较高的风险。使用提供的市场数据和情绪分析来加强您的论点，并挑战对立观点。具体来说，请直接回应保守和中性分析师提出的每个观点，用数据驱动的反驳和有说服力的推理进行反击。突出他们的谨慎态度可能错过的关键机会，或者他们的假设可能过于保守的地方。以下是交易员/策略顾问的决策：

{trader_decision}

您的任务是通过质疑和批评保守和中性立场来为决策创建一个令人信服的案例，证明为什么您的高回报视角提供了最佳的前进道路。将以下来源的见解纳入您的论点：

{context_reports}

{depth_instruction}

以下是当前对话历史：{history} 以下是保守分析师的最后论点：{current_safe_response} 以下是中性分析师的最后论点：{current_neutral_response}。如果其他观点没有回应，请不要虚构，只需提出您的观点。

积极参与，解决提出的任何具体担忧，反驳他们逻辑中的弱点，并断言承担风险的好处以超越市场常规。专注于辩论和说服，而不仅仅是呈现数据。挑战每个反驳点，强调为什么高风险方法是最优的。

⚠️ **输出格式要求**
请使用 Markdown 格式输出，使观点结构清晰：
1. 使用 **加粗** 强调核心观点。
2. 使用列表（- 或 1.）列举论据。
3. 针对保守和中性分析师的观点，可以单独分段反驳。
4. 语言要犀利、自信、有感染力。
"""

        logger.info(f"⏱️ [Risky Analyst] 开始调用LLM...")
        import time
        llm_start_time = time.time()

        response = llm.invoke(prompt)

        llm_elapsed = time.time() - llm_start_time
        logger.info(f"⏱️ [Risky Analyst] LLM调用完成，耗时: {llm_elapsed:.2f}秒")

        argument = f"Risky Analyst: {response.content}"

        new_count = risk_debate_state["count"] + 1
        logger.info(f"🔥 [激进风险分析师] 发言完成，计数: {risk_debate_state['count']} -> {new_count}")

        new_risk_debate_state = {
            "history": history + "\n" + argument,
            "risky_history": risky_history + "\n" + argument,
            "safe_history": risk_debate_state.get("safe_history", ""),
            "neutral_history": risk_debate_state.get("neutral_history", ""),
            "latest_speaker": "Risky",
            "current_risky_response": argument,
            "current_safe_response": risk_debate_state.get("current_safe_response", ""),
            "current_neutral_response": risk_debate_state.get(
                "current_neutral_response", ""
            ),
            "count": new_count,
        }

        return {"risk_debate_state": new_risk_debate_state}

    return risky_node
