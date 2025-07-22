import time
import json

# 导入统一日志系统
from tradingagents.utils.logging_init import get_logger
logger = get_logger("default")


def create_research_manager(llm, memory):
    def research_manager_node(state) -> dict:
        history = state["investment_debate_state"].get("history", "")
        market_research_report = state["market_report"]
        sentiment_report = state["sentiment_report"]
        news_report = state["news_report"]
        fundamentals_report = state["fundamentals_report"]

        investment_debate_state = state["investment_debate_state"]

        curr_situation = f"{market_research_report}\n\n{sentiment_report}\n\n{news_report}\n\n{fundamentals_report}"

        # 安全检查：确保memory不为None
        if memory is not None:
            past_memories = memory.get_memories(curr_situation, n_matches=2)
        else:
            logger.warning(f"⚠️ [DEBUG] memory为None，跳过历史记忆检索")
            past_memories = []

        past_memory_str = ""
        for i, rec in enumerate(past_memories, 1):
            past_memory_str += rec["recommendation"] + "\n\n"

        prompt = f"""As an investment portfolio manager and debate host, your role is to critically evaluate this debate round and make a clear decision: support bearish analysts, bullish analysts, or only choose to hold when there is a strong reason based on the arguments presented.

Briefly summarize the key points of both sides, focusing on the most convincing evidence or reasoning. Your suggestion - Buy, Sell, or Hold - must be clear and actionable. Avoid defaulting to holding simply because both sides have valid arguments; commit to your conclusion based on the strongest argument in the debate.

Additionally, develop a detailed investment plan for traders. This should include:

Your suggestion: A clear stance based on the most convincing argument.
Reasoning: Explain why these arguments lead to your conclusion.
Strategic action: Specific steps to implement the suggestion.
📊 Target price analysis: Based on all available reports (fundamental, news, sentiment), provide a comprehensive target price range and specific price targets. Consider:
- Basic valuation from fundamental reports
- Impact of news on price expectations
- Price adjustments driven by sentiment
- Technical support/resistance levels
- Risk-adjusted price scenarios (conservative, baseline, optimistic)
- Time horizon for price targets (1 month, 3 months, 6 months)
💰 You must provide specific price targets - do not reply with "cannot determine" or "more information needed".

Consider your past mistakes in similar situations. Use these insights to refine your decision-making, ensuring you learn and improve. Present your analysis in a conversational manner, as if you were speaking naturally, without using special formatting.

Here is your reflection on past mistakes:
\"{past_memory_str}\"

Here is the comprehensive analysis report:
Market Research: {market_research_report}

Sentiment Analysis: {sentiment_report}

News Analysis: {news_report}

Fundamental Analysis: {fundamentals_report}

Here is the debate:
Debate History:
{history}

Please write all analysis in English."""
        response = llm.invoke(prompt)

        new_investment_debate_state = {
            "judge_decision": response.content,
            "history": investment_debate_state.get("history", ""),
            "bear_history": investment_debate_state.get("bear_history", ""),
            "bull_history": investment_debate_state.get("bull_history", ""),
            "current_response": response.content,
            "count": investment_debate_state["count"],
        }

        return {
            "investment_debate_state": new_investment_debate_state,
            "investment_plan": response.content,
        }

    return research_manager_node
