"""
Google 工具处理器的外部集成测试。

依赖：
- langchain_google_genai
- GOOGLE_API_KEY

默认标记为 integration，不进入常规测试套件。
"""

import pytest
from langchain.schema import AIMessage, HumanMessage

from tests.conftest import require_env

pytestmark = pytest.mark.integration


def test_google_tool_handler_identifies_google_model() -> None:
    langchain_google_genai = pytest.importorskip("langchain_google_genai")
    require_env("GOOGLE_API_KEY")

    from tradingagents.agents.utils.google_tool_handler import GoogleToolCallHandler

    llm = langchain_google_genai.ChatGoogleGenerativeAI(
        model="gemini-1.5-flash",
        temperature=0.1,
    )

    assert GoogleToolCallHandler.is_google_model(llm) is True


def test_google_tool_handler_handles_message_without_tool_calls() -> None:
    langchain_google_genai = pytest.importorskip("langchain_google_genai")
    require_env("GOOGLE_API_KEY")

    from tradingagents.agents.utils.google_tool_handler import GoogleToolCallHandler
    from tradingagents.agents.utils.agent_utils import Toolkit

    llm = langchain_google_genai.ChatGoogleGenerativeAI(
        model="gemini-1.5-flash",
        temperature=0.1,
    )

    state = {
        "messages": [HumanMessage(content="请分析贵州茅台(600519)的市场情况")],
        "trade_date": "2026-03-27",
        "company_of_interest": "贵州茅台",
        "ticker": "600519",
    }

    result, messages = GoogleToolCallHandler.handle_google_tool_calls(
        result=AIMessage(content="我需要获取股票数据来进行分析"),
        llm=llm,
        tools=[Toolkit.get_stock_market_data_unified],
        state=state,
        analysis_prompt_template="请基于以上数据生成详细的市场分析报告",
        analyst_name="市场分析师",
    )

    assert isinstance(result, str)
    assert isinstance(messages, list)
