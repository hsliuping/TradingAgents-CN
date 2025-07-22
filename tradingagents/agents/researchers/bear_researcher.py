from langchain_core.messages import AIMessage
import time
import json

# 导入统一日志系统
from tradingagents.utils.logging_init import get_logger
logger = get_logger("default")


def create_bear_researcher(llm, memory):
    def bear_node(state) -> dict:
        investment_debate_state = state["investment_debate_state"]
        history = investment_debate_state.get("history", "")
        bear_history = investment_debate_state.get("bear_history", "")

        current_response = investment_debate_state.get("current_response", "")
        market_research_report = state["market_report"]
        sentiment_report = state["sentiment_report"]
        news_report = state["news_report"]
        fundamentals_report = state["fundamentals_report"]

        # 使用统一的股票类型检测
        company_name = state.get('company_of_interest', 'Unknown')
        from tradingagents.utils.stock_utils import StockUtils
        market_info = StockUtils.get_market_info(company_name)
        is_china = market_info['is_china']
        is_hk = market_info['is_hk']
        is_us = market_info['is_us']

        currency = market_info['currency_name']
        currency_symbol = market_info['currency_symbol']

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

        prompt = f"""You are a bear analyst, responsible for arguing against investing in stock {company_name}.

⚠️ Important reminder: The current analysis is for {market_info['market_name']}, all prices and valuations should be in {currency} ({currency_symbol}).

Your goal is to propose reasonable arguments, emphasizing risks, challenges, and negative indicators. Use the provided research and data to highlight potential negative factors and effectively refute bullish arguments.

Please answer in English, focusing on the following aspects:

- Risks and Challenges: Highlight factors that may hinder stock performance, such as market saturation, financial instability, or macroeconomic threats.
- Competitive Disadvantage: Emphasize weaknesses such as weak market position, declining innovation, or threats from competitors.
- Negative Indicators: Use financial data, market trends, or evidence of recent unfavorable news to support your position.
- Refute Bullish Arguments: Critically analyze bullish arguments with specific data and rational reasoning, exposing weaknesses or overly optimistic assumptions.
- Participate in Discussion: Present your arguments in a conversational style, directly responding to bullish analysts' arguments and engaging in effective debate, rather than merely listing facts.

Available Resources:

Market Research Report: {market_research_report}
Social Media Sentiment Report: {sentiment_report}
Latest World Affairs News: {news_report}
Company Fundamental Report: {fundamentals_report}
Debate Conversation History: {history}
Last Bullish Argument: {current_response}
Reflections and Lessons from Similar Situations: {past_memory_str}

Please provide convincing bearish arguments to refute bullish statements, participate in dynamic debates, and demonstrate the risks and weaknesses of investing in this stock. You must also reflect and learn from past experiences and mistakes.

Please ensure all answers are in English.
"""

        response = llm.invoke(prompt)

        argument = f"Bear Analyst: {response.content}"

        new_investment_debate_state = {
            "history": history + "\n" + argument,
            "bear_history": bear_history + "\n" + argument,
            "bull_history": investment_debate_state.get("bull_history", ""),
            "current_response": argument,
            "count": investment_debate_state["count"] + 1,
        }

        return {"investment_debate_state": new_investment_debate_state}

    return bear_node
