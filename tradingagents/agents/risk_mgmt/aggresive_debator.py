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

        market_research_report = state["market_report"]
        sentiment_report = state["sentiment_report"]
        news_report = state["news_report"]
        fundamentals_report = state["fundamentals_report"]

        trader_decision = state["trader_investment_plan"]

        prompt = f"""As an aggressive risk analyst, your role is to actively advocate for high-return, high-risk investment opportunities, emphasizing bold strategies and competitive advantages. When evaluating a trader's decision or plan, please focus on potential upside, growth potential, and innovative returns - even if they come with higher risks. Use the provided market data and sentiment analysis to strengthen your argument and challenge opposing views. Specifically, please directly respond to each conservative and neutral analyst's point, using data-driven rebuttals and persuasive reasoning. Highlight the key opportunities they might miss with their cautious attitude or overly conservative assumptions. Below is the trader's decision:

{trader_decision}

Your task is to create a compelling case for the trader's decision by questioning and critiquing conservative and neutral positions, demonstrating why your high-return perspective provides the optimal path forward. The following insights will be incorporated into your argument:

Market Research Report: {market_research_report}
Social Media Sentiment Report: {sentiment_report}
Latest World Affairs Report: {news_report}
Company Fundamentals Report: {fundamentals_report}
Below is the current conversation history: {history} Below is the last argument from the conservative analyst: {current_safe_response} Below is the last argument from the neutral analyst: {current_neutral_response}. If no other points are addressed, please do not invent, just present your point.

Participate actively, resolve any specific concerns raised, refute their logical weaknesses, and assert the benefits of taking risks to surpass market conventions. Focus on debate and persuasion, not just presenting data. Challenge each rebuttal point, emphasizing why a high-risk approach is optimal. Please output in Chinese in a conversational manner, as if you were speaking, without using any special formatting. """

        response = llm.invoke(prompt)

        argument = f"Risky Analyst: {response.content}"

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
            "count": risk_debate_state["count"] + 1,
        }

        return {"risk_debate_state": new_risk_debate_state}

    return risky_node
