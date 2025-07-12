import time
import json


def create_research_manager(llm, memory):
    def research_manager_node(state) -> dict:
        history = state["investment_debate_state"].get("history", "")
        market_research_report = state["market_report"]
        sentiment_report = state["sentiment_report"]
        news_report = state["news_report"]
        fundamentals_report = state["fundamentals_report"]

        investment_debate_state = state["investment_debate_state"]

        curr_situation = f"{market_research_report}\n\n{sentiment_report}\n\n{news_report}\n\n{fundamentals_report}"
        
        # 检查内存是否可用
        past_memories = []
        if memory is not None:
            try:
                past_memories = memory.get_memories(curr_situation, n_matches=2)
            except Exception as e:
                print(f"🔬 [DEBUG] 研究管理器内存获取失败: {e}")
                past_memories = []
        else:
            print(f"🔬 [DEBUG] 研究管理器内存系统未启用")

        past_memory_str = ""
        for i, rec in enumerate(past_memories, 1):
            past_memory_str += rec["recommendation"] + "\n\n"

        prompt = f"""As the portfolio manager and debate facilitator, your role is to critically evaluate this round of debate and make a definitive decision: align with the bear analyst, the bull analyst, or choose Hold only if it is strongly justified based on the arguments presented.

Summarize the key points from both sides concisely, focusing on the most compelling evidence or reasoning. Your recommendation—Buy, Sell, or Hold—must be clear and actionable. Avoid defaulting to Hold simply because both sides have valid points; commit to a stance grounded in the debate's strongest arguments.

Additionally, develop a detailed investment plan for the trader. This should include:

Your Recommendation: A decisive stance supported by the most convincing arguments.
Rationale: An explanation of why these arguments lead to your conclusion.
Strategic Actions: Concrete steps for implementing the recommendation.
📊 Target Price Analysis: Based on all available reports (fundamentals, news, sentiment), provide a comprehensive target price range and specific price targets. Consider:
- Fundamental valuation from the fundamentals report
- News impact on price expectations
- Sentiment-driven price adjustments
- Technical support/resistance levels
- Risk-adjusted price scenarios (conservative, base case, optimistic)
- Time horizon for price targets (1 month, 3 months, 6 months)
💰 You MUST provide specific target prices - do not reply with "unable to determine" or "need more information".

Take into account your past mistakes on similar situations. Use these insights to refine your decision-making and ensure you are learning and improving. Present your analysis conversationally, as if speaking naturally, without special formatting. 

Here are your past reflections on mistakes:
\"{past_memory_str}\"

Here are the comprehensive analysis reports:
Market Research: {market_research_report}

Sentiment Analysis: {sentiment_report}

News Analysis: {news_report}

Fundamentals Analysis: {fundamentals_report}

Here is the debate:
Debate History:
{history}"""
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
