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

        market_research_report = state["market_report"]
        sentiment_report = state["sentiment_report"]
        news_report = state["news_report"]
        fundamentals_report = state["fundamentals_report"]

        trader_decision = state["trader_investment_plan"]

        prompt = f"""As a safe/conservative risk analyst, your primary goal is to protect assets, minimize volatility, and ensure stable, reliable growth. You prioritize stability, safety, and risk mitigation, carefully assessing potential losses, economic downturns, and market volatility. When reviewing a trader's decision or plan, please critically examine high-risk elements, identify places where a decision might expose the company to inappropriate risks, and how more cautious alternatives could ensure long-term returns. Below is the trader's decision:

{trader_decision}

Your task is to actively counter aggressive and neutral analysts' arguments, highlighting potential threats or areas where their views might have overlooked sustainable development. Directly respond to their arguments, using the following data sources to establish a convincing case for adjusting the low-risk approach to the trader's decision:

Market research report: {market_research_report}
Social media sentiment report: {sentiment_report}
Latest world affairs report: {news_report}
Company fundamentals report: {fundamentals_report}
Below is the current conversation history: {history} Below is the last response from the aggressive analyst: {current_risky_response} Below is the last response from the neutral analyst: {current_neutral_response}. If other viewpoints are not addressed, please do not invent, just present your viewpoint.

Participate in the discussion by questioning their optimistic attitude and emphasizing potential downside risks they might have overlooked. Solve each of their rebuttals, demonstrating why a conservative stance ultimately represents the safest path for company assets. Focus on debating and critically examining their arguments, proving the advantages of low-risk strategies over their methods. Please output in English onversational manner, as if you were speaking, without using any special formats. """

        response = llm.invoke(prompt)

        argument = f"Safe Analyst: {response.content}"

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
            "count": risk_debate_state["count"] + 1,
        }

        return {"risk_debate_state": new_risk_debate_state}

    return safe_node
