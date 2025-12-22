import time
import json

# 导入统一日志系统
from tradingagents.utils.logging_init import get_logger
logger = get_logger("default")


def create_neutral_debator(llm):
    def neutral_node(state) -> dict:
        risk_debate_state = state["risk_debate_state"]
        history = risk_debate_state.get("history", "")
        neutral_history = risk_debate_state.get("neutral_history", "")

        current_risky_response = risk_debate_state.get("current_risky_response", "")
        current_safe_response = risk_debate_state.get("current_safe_response", "")

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

        # 📊 记录所有输入数据的长度，用于性能分析
        logger.info(f"📊 [Neutral Analyst] 输入数据长度统计 (Index Mode: {is_index}):")
        if is_index:
             context_reports = f"""
宏观经济报告：{macro_report}
政策分析报告：{policy_report}
板块轮动报告：{sector_report}
国际新闻报告：{intl_news_report}
技术分析报告：{technical_report}
"""
             logger.info(f"  - macro: {len(macro_report)}, policy: {len(policy_report)}, sector: {len(sector_report)}")
        else:
             context_reports = f"""
市场研究报告：{market_research_report}
社交媒体情绪报告：{sentiment_report}
最新世界事务报告：{news_report}
公司基本面报告：{fundamentals_report}
"""
             logger.info(f"  - market_report: {len(market_research_report):,} 字符")
        
        logger.info(f"  - trader_decision: {len(trader_decision):,} 字符")
        logger.info(f"  - history: {len(history):,} 字符")
        
        prompt = f"""作为中性风险分析师，您的角色是提供平衡的视角，权衡交易员决策或计划的潜在收益和风险。您优先考虑全面的方法，评估上行和下行风险，同时考虑更广泛的市场趋势、潜在的经济变化和多元化策略。以下是交易员/策略顾问的决策：

{trader_decision}

您的任务是挑战激进和安全分析师，指出每种观点可能过于乐观或过于谨慎的地方。使用以下数据来源的见解来支持调整交易员决策的温和、可持续策略：

{context_reports}

以下是当前对话历史：{history} 以下是激进分析师的最后回应：{current_risky_response} 以下是安全分析师的最后回应：{current_safe_response}。如果其他观点没有回应，请不要虚构，只需提出您的观点。

通过批判性地分析双方来积极参与，解决激进和保守论点中的弱点，倡导更平衡的方法。挑战他们的每个观点，说明为什么适度风险策略可能提供两全其美的效果，既提供增长潜力又防范极端波动。专注于辩论而不是简单地呈现数据，旨在表明平衡的观点可以带来最可靠的结果。请用中文以对话方式输出，就像您在说话一样，不使用任何特殊格式。"""

        logger.info(f"⏱️ [Neutral Analyst] 开始调用LLM...")
        llm_start_time = time.time()

        response = llm.invoke(prompt)

        llm_elapsed = time.time() - llm_start_time
        logger.info(f"⏱️ [Neutral Analyst] LLM调用完成，耗时: {llm_elapsed:.2f}秒")
        logger.info(f"📝 [Neutral Analyst] 响应长度: {len(response.content):,} 字符")

        argument = f"Neutral Analyst: {response.content}"

        new_count = risk_debate_state["count"] + 1
        logger.info(f"⚖️ [中性风险分析师] 发言完成，计数: {risk_debate_state['count']} -> {new_count}")

        new_risk_debate_state = {
            "history": history + "\n" + argument,
            "risky_history": risk_debate_state.get("risky_history", ""),
            "safe_history": risk_debate_state.get("safe_history", ""),
            "neutral_history": neutral_history + "\n" + argument,
            "latest_speaker": "Neutral",
            "current_risky_response": risk_debate_state.get(
                "current_risky_response", ""
            ),
            "current_safe_response": risk_debate_state.get("current_safe_response", ""),
            "current_neutral_response": argument,
            "count": new_count,
        }

        return {"risk_debate_state": new_risk_debate_state}

    return neutral_node
