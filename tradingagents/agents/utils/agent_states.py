from typing import Annotated, Sequence
from datetime import date, timedelta, datetime
from typing_extensions import TypedDict, Optional
from langchain_openai import ChatOpenAI
from tradingagents.agents import *
from langgraph.prebuilt import ToolNode
from langgraph.graph import END, StateGraph, START, MessagesState

# 导入统一日志系统
from tradingagents.utils.logging_init import get_logger
logger = get_logger("default")


# Researcher team state
class InvestDebateState(TypedDict):
    bull_history: Annotated[
        str, "Bullish Conversation history"
    ]  # Bullish Conversation history
    bear_history: Annotated[
        str, "Bearish Conversation history"
    ]  # Bullish Conversation history
    history: Annotated[str, "Conversation history"]  # Conversation history
    current_response: Annotated[str, "Latest response"]  # Last response
    judge_decision: Annotated[str, "Final judge decision"]  # Last response
    count: Annotated[int, "Length of the current conversation"]  # Conversation length


# Risk management team state
class RiskDebateState(TypedDict):
    risky_history: Annotated[
        str, "Risky Agent's Conversation history"
    ]  # Conversation history
    safe_history: Annotated[
        str, "Safe Agent's Conversation history"
    ]  # Conversation history
    neutral_history: Annotated[
        str, "Neutral Agent's Conversation history"
    ]  # Conversation history
    history: Annotated[str, "Conversation history"]  # Conversation history
    latest_speaker: Annotated[str, "Analyst that spoke last"]
    current_risky_response: Annotated[
        str, "Latest response by the risky analyst"
    ]  # Last response
    current_safe_response: Annotated[
        str, "Latest response by the safe analyst"
    ]  # Last response
    current_neutral_response: Annotated[
        str, "Latest response by the neutral analyst"
    ]  # Last response
    judge_decision: Annotated[str, "Judge's decision"]
    count: Annotated[int, "Length of the current conversation"]  # Conversation length


def update_reports(existing: dict, new: dict) -> dict:
    """Reducer for merging reports dictionaries"""
    # 延迟导入以避免循环依赖
    from tradingagents.utils.logging_init import get_logger
    local_logger = get_logger("agent_states")
    
    # 记录合并操作
    keys_existing = list(existing.keys()) if existing else []
    keys_new = list(new.keys()) if new else []
    local_logger.info(f"🔄 [Reducer] 合并报告: 现有={keys_existing}, 新增={keys_new}")
    
    if not existing:
        return new
    if not new:
        return existing
    return {**existing, **new}


class AgentState(MessagesState):
    company_of_interest: Annotated[str, "Company that we are interested in trading"]
    trade_date: Annotated[str, "What date we are trading at"]

    sender: Annotated[str, "Agent that sent this message"]

    # research step - 核心分析师报告（保留兼容性）
    market_report: Annotated[str, "Report from the Market Analyst"]
    sentiment_report: Annotated[str, "Report from the Social Media Analyst"]
    news_report: Annotated[
        str, "Report from the News Researcher of current world affairs"
    ]
    fundamentals_report: Annotated[str, "Report from the Fundamentals Researcher"]
    china_market_report: Annotated[str, "Report from the China Market Analyst"]
    short_term_capital_report: Annotated[str, "Report from the Short Term Capital Analyst"]
    
    # 🔧 动态分析师报告字段（与 generic_agent.py 生成的 key 保持一致）
    financial_news_report: Annotated[str, "Report from the Financial News Analyst"]
    social_media_report: Annotated[str, "Report from the Social Media Analyst (dynamic)"]

    # 🔥 动态报告字段 - 支持前端添加的新智能体
    # LangGraph 会自动合并节点返回的字典到 State 中
    # 只要节点返回的 key 以 _report 结尾，就会被存储
    # 注意：这里不需要预定义所有字段，因为 MessagesState 继承自 TypedDict
    # 但为了类型安全，我们保留核心字段的定义
    reports: Annotated[dict, update_reports]

    # 🔧 死循环修复: 工具调用计数器
    market_tool_call_count: Annotated[int, "Market analyst tool call counter"]
    news_tool_call_count: Annotated[int, "News analyst tool call counter"]
    sentiment_tool_call_count: Annotated[int, "Social media analyst tool call counter"]
    fundamentals_tool_call_count: Annotated[int, "Fundamentals analyst tool call counter"]
    china_market_tool_call_count: Annotated[int, "China market analyst tool call counter"]
    short_term_capital_tool_call_count: Annotated[int, "Short term capital analyst tool call counter"]
    
    # 🔧 动态分析师工具调用计数器
    financial_news_tool_call_count: Annotated[int, "Financial news analyst tool call counter"]
    social_media_tool_call_count: Annotated[int, "Social media analyst tool call counter"]

    # researcher team discussion step
    investment_debate_state: Annotated[
        InvestDebateState, "Current state of the debate on if to invest or not"
    ]
    investment_plan: Annotated[str, "Plan generated by the Analyst"]

    trader_investment_plan: Annotated[str, "Plan generated by the Trader"]

    # risk management team discussion step
    risk_debate_state: Annotated[
        RiskDebateState, "Current state of the debate on evaluating risk"
    ]
    final_trade_decision: Annotated[str, "Final decision made by the Risk Analysts"]

    # 🔧 结构化总结字段 (用于前端展示)
    structured_summary: Annotated[dict, "Structured summary for frontend display"]
    
    # 🔧 阶段配置标志 (用于图路由)
    phase2_enabled: Annotated[bool, "Is phase 2 (Debate) enabled"]
    phase3_enabled: Annotated[bool, "Is phase 3 (Risk) enabled"]
    phase4_enabled: Annotated[bool, "Is phase 4 (Trader) enabled"]
