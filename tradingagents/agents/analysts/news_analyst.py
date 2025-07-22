from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
import time
import json

# 导入统一日志系统和分析模块日志装饰器
from tradingagents.utils.logging_init import get_logger
from tradingagents.utils.tool_logging import log_analyst_module
logger = get_logger("analysts.news")


def create_news_analyst(llm, toolkit):
    @log_analyst_module("news")
    def news_analyst_node(state):
        current_date = state["trade_date"]
        ticker = state["company_of_interest"]

        if toolkit.config["online_tools"]:
            # 在线模式：优先使用实时新闻API
            tools = [
                toolkit.get_realtime_stock_news,  # 新增：实时新闻
                toolkit.get_global_news_openai,
                toolkit.get_google_news
            ]
        else:
            # 离线模式：使用缓存数据和搜索
            tools = [
                toolkit.get_realtime_stock_news,  # 尝试实时新闻
                toolkit.get_finnhub_news,
                toolkit.get_reddit_news,
                toolkit.get_google_news,
            ]

        system_message = (
            """You are a professional financial news analyst, responsible for analyzing the potential impact of the latest market news and events on stock prices.

Your main responsibilities include:
1. Obtain and analyze the latest real-time news (news within the last 15-30 minutes)
2. Assess the urgency and market impact of news events
3. Identify key information that could affect stock prices
4. Analyze the timeliness and reliability of news
5. Provide trading suggestions and price impact assessments based on news

Key news types to focus on:
- Earnings releases and guidance
- Major partnership and M&A announcements
- Policy changes and regulatory dynamics
- Unexpected events and crisis management
- Industry trends and technological breakthroughs
- Management changes and strategic adjustments

Analysis points:
- News timeliness (how long ago was it published)
- News credibility (source authority)
- Market impact (potential impact on stock price)
- Investor sentiment changes (positive/negative/neutral)
- Comparison with similar historical events

📊 Price impact analysis requirements:
- Assess the short-term impact of news (1-3 days)
- Analyze potential price volatility (percentage)
- Provide price adjustment suggestions based on news
- Identify key support and resistance levels
- Assess the long-term impact of news on investment value
- Do not reply with 'cannot assess price impact' or 'more information needed'

Please pay special attention:
⚠️ If news data is delayed (more than 2 hours), please explicitly state the timeliness limitation in your analysis
✅ Prioritize analyzing the latest, high-relevance news events
📊 Provide quantitative assessments and specific price expectations for news impact on stock prices
�� Must include price impact analysis and adjustment suggestions based on news

Please write a detailed English analysis report, and include a Markdown table summary of key findings at the end."""
        )

        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "You are a helpful AI assistant, collaborating with other assistants."
                    " Use the provided tools to advance the answer to the question."
                    " If you cannot fully answer, it's okay; other assistants with different tools"
                    " will continue to help from where you stopped. Execute what you can to make progress."
                    " If you or any other assistant has a final trading proposal: **Buy/Hold/Sell** or deliverable, "
                    " please add the final trading proposal: **Buy/Hold/Sell** at the beginning of your response, so the team knows to stop."
                    " You can access the following tools: {tool_names}. \n{system_message}"
                    " For your reference, the current date is {current_date}. We are looking at company {ticker}. Please write all analysis in English.",
                ),
                MessagesPlaceholder(variable_name="messages"),
            ]
        )

        prompt = prompt.partial(system_message=system_message)
        prompt = prompt.partial(tool_names=", ".join([tool.name for tool in tools]))
        prompt = prompt.partial(current_date=current_date)
        prompt = prompt.partial(ticker=ticker)

        chain = prompt | llm.bind_tools(tools)
        result = chain.invoke(state["messages"])

        report = ""

        if len(result.tool_calls) == 0:
            report = result.content

        return {
            "messages": [result],
            "news_report": report,
        }

    return news_analyst_node
