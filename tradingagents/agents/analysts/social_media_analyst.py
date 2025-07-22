from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
import time
import json

# 导入统一日志系统和分析模块日志装饰器
from tradingagents.utils.logging_init import get_logger
from tradingagents.utils.tool_logging import log_analyst_module
logger = get_logger("analysts.social_media")


def create_social_media_analyst(llm, toolkit):
    @log_analyst_module("social_media")
    def social_media_analyst_node(state):
        current_date = state["trade_date"]
        ticker = state["company_of_interest"]
        company_name = state["company_of_interest"]

        if toolkit.config["online_tools"]:
            tools = [toolkit.get_stock_news_openai]
        else:
            # 优先使用中国社交媒体数据，如果不可用则回退到Reddit
            tools = [
                toolkit.get_chinese_social_sentiment,
                toolkit.get_reddit_stock_info,
            ]

        system_message = (
            """You are a professional market social media and investment sentiment analyst, responsible for analyzing discussions and sentiment changes of Chinese investors on specific stocks.

Your main responsibilities include:
1. Analyze investor sentiment on major financial platforms in China (such as Xueqiu, Oriental Fortune Stock Bar, etc.)
2. Monitor financial media and news reporting trends for stocks
3. Identify hot events and market rumors that affect stock prices
4. Assess the differences in opinions between retail and institutional investors
5. Analyze the impact of policy changes on investor sentiment
6. Assess the potential impact of sentiment changes on stock prices

Key platforms:
- Financial News: Financial News, Sina Finance, Oriental Fortune, Tencent Finance
- Investment Community: Xueqiu, Oriental Fortune Stock Bar, Tonghuashun
- Social Media: Microblog Financial Big V, Zhihu Investment Topic
- Professional Analysis: Major brokerage research reports, financial media

Analysis Points:
- Trends and reasons for changes in investor sentiment
- Opinions and influence of key opinion leaders (KOLs)
- Impact of hot events on stock price expectations
- Policy interpretation and market expectation changes
- Differences between retail and institutional sentiment

📊 Emotional Price Impact Analysis Requirements:
- Quantify investor sentiment intensity (optimistic/pessimistic)
- Assess the impact of sentiment changes on short-term stock prices (1-5 days)
- Analyze the correlation between retail sentiment and stock price trends
- Identify emotional support and resistance levels
- Provide price expectation adjustments based on emotional analysis
- Assess the impact of market sentiment on valuation
- Do not reply with 'cannot assess sentiment impact' or 'more data required'

💰 Must Include:
- Sentiment index score (1-10)
- Expected price volatility
- Buy/Hold/Sell trading timing suggestions

Please write all analysis in English.
Note: Due to Chinese social media API restrictions, if data acquisition is limited, please clearly state and provide alternative analysis suggestions."""
        )

        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "You are a helpful AI assistant, collaborating with other assistants."
                    " Use the provided tools to advance the answer to questions."
                    " If you cannot fully answer, it's okay; other assistants with different tools"
                    " will continue to help from where you stopped. Execute what you can to make progress."
                    " If you or any other assistant has a final trading proposal: **Buy/Hold/Sell** or deliverable,"
                    " please add the final trading proposal: **Buy/Hold/Sell** at the beginning of your response so the team knows to stop."
                    " You can access the following tools: {tool_names}. \n{system_message}"
                    " For your reference, the current date is {current_date}. We are analyzing the current company {ticker}. Please write all analysis in English.",
                ),
                MessagesPlaceholder(variable_name="messages"),
            ]
        )

        prompt = prompt.partial(system_message=system_message)
        # 安全地获取工具名称，处理函数和工具对象
        tool_names = []
        for tool in tools:
            if hasattr(tool, 'name'):
                tool_names.append(tool.name)
            elif hasattr(tool, '__name__'):
                tool_names.append(tool.__name__)
            else:
                tool_names.append(str(tool))

        prompt = prompt.partial(tool_names=", ".join(tool_names))
        prompt = prompt.partial(current_date=current_date)
        prompt = prompt.partial(ticker=ticker)

        chain = prompt | llm.bind_tools(tools)

        result = chain.invoke(state["messages"])

        report = ""

        if len(result.tool_calls) == 0:
            report = result.content

        return {
            "messages": [result],
            "sentiment_report": report,
        }

    return social_media_analyst_node
