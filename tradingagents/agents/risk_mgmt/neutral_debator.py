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

        market_research_report = state["market_report"]
        sentiment_report = state["sentiment_report"]
        news_report = state["news_report"]
        fundamentals_report = state["fundamentals_report"]

        trader_decision = state["trader_investment_plan"]

        prompt = f"""As a neutral risk analyst, your role is to provide a balanced perspective, weighing the potential benefits and risks of a trader's decision or plan. You prioritize a comprehensive approach, assessing both upside and downside risks, while considering broader market trends, potential economic changes, and diversified strategies. Here is the trader's decision:

{trader_decision}

Your task is to challenge aggressive and safe analysts, pointing out where each perspective might be overly optimistic or overly cautious. Use insights from the following data sources to support a moderate, sustainable strategy for adjusting the trader's decision:

Market Research Report: {market_research_report}
Social Media Sentiment Report: {sentiment_report}
Latest World Affairs Report: {news_report}
Company Fundamental Report: {fundamentals_report}
Here is the current conversation history: {history} Here is the last response from the aggressive analyst: {current_risky_response} Here is the last response from the safe analyst: {current_safe_response}. If no other perspectives have responded, please do not invent, just present your perspective.

By critically analyzing both sides, actively participate in resolving weaknesses in aggressive and conservative arguments, advocating for a more balanced approach. Challenge each of their perspectives, explaining why a moderate risk strategy might offer a win-win effect, providing growth potential while preventing extreme volatility. Focus on debates rather than simply presenting data, aiming to demonstrate that a balanced perspective can lead to the most reliable results. Please output in English in a conversational manner, as if you were speaking, without using any special formats. """

        response = llm.invoke(prompt)

        argument = f"Neutral Analyst: {response.content}"

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
            "count": risk_debate_state["count"] + 1,
        }

        return {"risk_debate_state": new_risk_debate_state}

    return neutral_node
