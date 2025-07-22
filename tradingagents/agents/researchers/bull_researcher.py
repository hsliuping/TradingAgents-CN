from langchain_core.messages import AIMessage
import time
import json

# 导入统一日志系统
from tradingagents.utils.logging_init import get_logger
logger = get_logger("default")


def create_bull_researcher(llm, memory):
    def bull_node(state) -> dict:
        logger.debug(f"🐂 [DEBUG] ===== Bull Researcher Node Start =====")

        investment_debate_state = state["investment_debate_state"]
        history = investment_debate_state.get("history", "")
        bull_history = investment_debate_state.get("bull_history", "")

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

        logger.debug(f"🐂 [DEBUG] Received reports:")
        logger.debug(f"🐂 [DEBUG] - Market report length: {len(market_research_report)}")
        logger.debug(f"🐂 [DEBUG] - Sentiment report length: {len(sentiment_report)}")
        logger.debug(f"🐂 [DEBUG] - News report length: {len(news_report)}")
        logger.debug(f"🐂 [DEBUG] - Fundamentals report length: {len(fundamentals_report)}")
        logger.debug(f"🐂 [DEBUG] - First 200 characters of fundamentals report: {fundamentals_report[:200]}...")
        logger.debug(f"🐂 [DEBUG] - Stock code: {company_name}, Type: {market_info['market_name']}, Currency: {currency}")
        logger.debug(f"🐂 [DEBUG] - Market details: China A-shares={is_china}, HK={is_hk}, US={is_us}")

        curr_situation = f"{market_research_report}\n\n{sentiment_report}\n\n{news_report}\n\n{fundamentals_report}"

        # 安全检查：确保memory不为None
        if memory is not None:
            past_memories = memory.get_memories(curr_situation, n_matches=2)
        else:
            logger.warning(f"⚠️ [DEBUG] memory is None, skipping historical memory retrieval")
            past_memories = []

        past_memory_str = ""
        for i, rec in enumerate(past_memories, 1):
            past_memory_str += rec["recommendation"] + "\n\n"

        prompt = f"""You are a bullish analyst responsible for establishing a strong case for investing in stock {company_name}.

⚠️ Important reminder: The current analysis is for {'China A-shares' if is_china else 'overseas stocks'}, all prices and valuations should use {currency} ({currency_symbol}) as the unit.

Your task is to build a strong case based on evidence, emphasizing growth potential, competitive advantages, and positive market indicators. Use the provided research and data to address concerns and effectively refute bearish arguments.

Please answer in English, focusing on the following aspects:
- Growth potential: Highlight the company's market opportunities, revenue forecasts, and scalability
- Competitive advantage: Emphasize unique products, strong brands, or dominant market positions
- Positive indicators: Use financial health, industry trends, and the latest positive news as evidence
- Refute bearish arguments: Critically analyze bearish arguments with specific data and rational reasoning, comprehensively address concerns, and explain why bullish arguments are more convincing
- Participate in discussion: Present your arguments in a conversational style, directly respond to bearish analyst arguments, and engage in effective debate, not just listing data

Available resources:
Market research report: {market_research_report}
Social media sentiment report: {sentiment_report}
Latest world affairs news: {news_report}
Company fundamentals report: {fundamentals_report}
Debate conversation history: {history}
Last bearish argument: {current_response}
Reflection and lessons learned from similar situations: {past_memory_str}

Please provide convincing bullish arguments, refute bearish concerns, and participate in dynamic debates, demonstrating the advantages of the bullish position. You must also reflect and learn from past experiences and mistakes.

Please ensure all answers are in English.
"""

        response = llm.invoke(prompt)

        argument = f"Bull Analyst: {response.content}"

        new_investment_debate_state = {
            "history": history + "\n" + argument,
            "bull_history": bull_history + "\n" + argument,
            "bear_history": investment_debate_state.get("bear_history", ""),
            "current_response": argument,
            "count": investment_debate_state["count"] + 1,
        }

        return {"investment_debate_state": new_investment_debate_state}

    return bull_node
