from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain.agents import create_react_agent, AgentExecutor
from langchain import hub
import time
import json

# 导入日志模块
from tradingagents.utils.logging_manager import get_logger
logger = get_logger('agents')


def create_market_analyst_react(llm, toolkit):
    """使用ReAct Agent模式的市场分析师（适用于通义千问）"""
    def market_analyst_react_node(state):
        logger.debug(f"📈 [DEBUG] ===== ReAct market analyst node started =====")

        current_date = state["trade_date"]
        ticker = state["company_of_interest"]

        logger.debug(f"📈 [DEBUG] Input parameters: ticker={ticker}, date={current_date}")

        # TODO: Add English comment
        def is_china_stock(ticker_code):
            import re
            return re.match(r'^\d{6}$', str(ticker_code))

        is_china = is_china_stock(ticker)
        logger.debug(f"📈 [DEBUG] Stock type check: {ticker} -> Chinese A-share: {is_china}")

        if toolkit.config["online_tools"]:
            # TODO: Add English comment
            if is_china:
                logger.info(f"📈 [Market analyst] Using ReAct Agent to analyze Chinese stocks")

                # TODO: Add English comment
                from langchain_core.tools import BaseTool

                class ChinaStockDataTool(BaseTool):
                    name: str = "get_china_stock_data"
                    description: str = f"Get market data and technical indicators for Chinese A-share stock {ticker} (optimized cache version). Direct call, no parameters required."

                    def _run(self, query: str = "") -> str:
                        try:
                            logger.debug(f"📈 [DEBUG] ChinaStockDataTool called, stock code: {ticker}")
                            # TODO: Add English comment
                            from tradingagents.dataflows.optimized_china_data import get_china_stock_data_cached
                            return get_china_stock_data_cached(
                                symbol=ticker,
                                start_date='2025-05-28',
                                end_date=current_date,
                                force_refresh=False
                            )
                        except Exception as e:
                            logger.error(f"❌ Optimized A-share data acquisition failed: {e}")
                            # TODO: Add English comment
                            try:
                                return toolkit.get_china_stock_data.invoke({
                                    'stock_code': ticker,
                                    'start_date': '2025-05-28',
                                    'end_date': current_date
                                })
                            except Exception as e2:
                                return f"Failed to get stock data: {str(e2)}"

                tools = [ChinaStockDataTool()]
                query = f"""Please perform a detailed technical analysis of Chinese A-share stock {ticker}.

Execution steps:
1. Use the get_china_stock_data tool to obtain stock market data
2. Perform in-depth technical indicator analysis based on the obtained real data
3. Directly output the complete technical analysis report content

Important requirements:
- Must output a complete technical analysis report content, do not just describe that the report is complete
- The report must be analyzed based on real data obtained by tools
- The report length must be at least 800 characters
- Must include specific data, indicator values, and professional analysis

The report format should include:
## TODO: Add English comment
## TODO: Add English comment
## TODO: Add English comment
## TODO: Add English comment
## TODO: Add English comment
## TODO: Add English comment
"""
            else:
                logger.info(f"📈 [Market analyst] Using ReAct Agent to analyze US/HK stocks")

                # TODO: Add English comment
                from langchain_core.tools import BaseTool

                class USStockDataTool(BaseTool):
                    name: str = "get_us_stock_data"
                    description: str = f"Get market data and technical indicators for US/HK stocks {ticker} (optimized cache version). Direct call, no parameters required."

                    def _run(self, query: str = "") -> str:
                        try:
                            logger.debug(f"📈 [DEBUG] USStockDataTool called, stock code: {ticker}")
                            # TODO: Add English comment
                            from tradingagents.dataflows.optimized_us_data import get_us_stock_data_cached
                            return get_us_stock_data_cached(
                                symbol=ticker,
                                start_date='2025-05-28',
                                end_date=current_date,
                                force_refresh=False
                            )
                        except Exception as e:
                            logger.error(f"❌ Optimized US stock data acquisition failed: {e}")
                            # TODO: Add English comment
                            try:
                                return toolkit.get_YFin_data_online.invoke({
                                    'symbol': ticker,
                                    'start_date': '2025-05-28',
                                    'end_date': current_date
                                })
                            except Exception as e2:
                                return f"Failed to get stock data: {str(e2)}"

                class FinnhubNewsTool(BaseTool):
                    name: str = "get_finnhub_news"
                    description: str = f"Get the latest news and market sentiment for US stock {ticker} (via FINNHUB API). Direct call, no parameters required."

                    def _run(self, query: str = "") -> str:
                        try:
                            logger.debug(f"📈 [DEBUG] FinnhubNewsTool called, stock code: {ticker}")
                            return toolkit.get_finnhub_news.invoke({
                                'ticker': ticker,
                                'start_date': '2025-05-28',
                                'end_date': current_date
                            })
                        except Exception as e:
                            return f"Failed to get news data: {str(e)}"

                tools = [USStockDataTool(), FinnhubNewsTool()]
                query = f"""Please perform a detailed technical analysis of US stock {ticker}.

Execution steps:
1. Use the get_us_stock_data tool to obtain stock market data and technical indicators (via FINNHUB API)
2. Use the get_finnhub_news tool to obtain the latest news and market sentiment
3. Perform in-depth technical indicator analysis based on the obtained real data
4. Directly output the complete technical analysis report content

Important requirements:
- Must output a complete technical analysis report content, do not just describe that the report is complete
- The report must be analyzed based on real data obtained by tools
- The report length must be at least 800 characters
- Must include specific data, indicator values, and professional analysis
- Combine news information to analyze market sentiment

The report format should include:
## TODO: Add English comment
## TODO: Add English comment
## TODO: Add English comment
## TODO: Add English comment
## TODO: Add English comment
## TODO: Add English comment
"""

            try:
                # TODO: Add English comment
                prompt = hub.pull("hwchase17/react")
                agent = create_react_agent(llm, tools, prompt)
                agent_executor = AgentExecutor(
                    agent=agent,
                    tools=tools,
                    verbose=True,
                    handle_parsing_errors=True,
                    max_iterations=10,  # TODO: Add English comment
                    max_execution_time=180  # TODO: Add English comment
                )

                logger.debug(f"📈 [DEBUG] Executing ReAct Agent query...")
                result = agent_executor.invoke({'input': query})

                report = result['output']
                logger.info(f"📈 [Market analyst] ReAct Agent completed, report length: {len(report)}")

            except Exception as e:
                logger.error(f"❌ [DEBUG] ReAct Agent failed: {str(e)}")
                report = f"ReAct Agent market analysis failed: {str(e)}"
        else:
            # TODO: Add English comment
            report = "Offline mode, not supported"

        logger.debug(f"📈 [DEBUG] ===== ReAct market analyst node ended =====")

        return {
            "messages": [("assistant", report)],
            "market_report": report,
        }

    return market_analyst_react_node


def create_market_analyst(llm, toolkit):

    def market_analyst_node(state):
        logger.debug(f"📈 [DEBUG] ===== Market analyst node started =====")

        current_date = state["trade_date"]
        ticker = state["company_of_interest"]
        company_name = state["company_of_interest"]

        logger.debug(f"📈 [DEBUG] Input parameters: ticker={ticker}, date={current_date}")
        logger.debug(f"📈 [DEBUG] Number of messages in current state: {len(state.get('messages', []))}")
        logger.debug(f"📈 [DEBUG] Existing market report: {state.get('market_report', 'None')[:100]}...")

        # TODO: Add English comment
        def is_china_stock(ticker_code):
            """Check if it is a Chinese A-share code"""
            import re

            # A-share code format: 6 digits
            return re.match(r'^\d{6}$', str(ticker_code))

        if toolkit.config["online_tools"]:
            if is_china_stock(ticker):
                # TODO: Add English comment
                tools = [
                    toolkit.get_china_stock_data,
                ]
            else:
                # TODO: Add English comment
                tools = [
                    toolkit.get_YFin_data_online,
                    toolkit.get_stockstats_indicators_report_online,
                ]
        else:
            tools = [
                toolkit.get_YFin_data,
                toolkit.get_stockstats_indicators_report,
            ]

        system_message = (
            """You are a professional trading assistant responsible for analyzing financial markets. Your role is to select the **most relevant indicators** from the following list to analyze the given market conditions or trading strategies. The goal is to select up to **8 indicators** to provide complementary insights without repetition. Categories and their indicators are as follows:

Moving Averages:
- close_50_sma: 50-day simple moving average: mid-term trend indicator. Purpose: Identify trend direction and serve as dynamic support/resistance. Hint: Lag behind price; combine with faster indicators for timely signals.
- close_200_sma: 200-day simple moving average: long-term trend benchmark. Purpose: Confirm overall market trend and identify golden/dead cross settings. Hint: Slow reaction; best for strategic trend confirmation rather than frequent trading entry.
- close_10_ema: 10-day exponential moving average: responsive short-term average. Purpose: Capture rapid momentum changes and potential entry points. Hint: Easy to generate noise in volatile markets; combine with longer averages to filter false signals.

MACD related indicators:
- macd: MACD: Momentum calculated by EMA difference. Purpose: Seek crossovers and divergences as trend change signals. Hint: Other indicators are needed for confirmation in low volatility or flat markets.
- macds: MACD signal line: EMA smoothed MACD line. Purpose: Use crossovers with the MACD line to trigger trades. Hint: Should be part of a broader strategy to avoid false signals.
- macdh: MACD histogram: Shows the gap between the MACD line and its signal line. Purpose: Visualize momentum strength and detect divergences early. Hint: May be volatile; additional filters are needed in fast-moving markets.

Momentum indicators:
- rsi: RSI: Measures momentum to mark overbought/oversold conditions. Purpose: Apply 70/30 thresholds and observe divergences for signal reversals. Hint: In strong trends, RSI may maintain extreme values; always cross-validate with trend analysis.

Volatility indicators:
- boll: Bollinger Band middle line: 20-day SMA as the base of the Bollinger Bands. Purpose: Dynamic benchmark for price movement. Hint: Combine with upper and lower bands for effective breakout or reversal detection.
- boll_ub: Bollinger Band upper line: Usually 2 standard deviations above the middle line. Purpose: Signal potential overbought conditions and breakout areas. Hint: Use other tools to confirm signals; in strong trends, price may run along the track.
- boll_lb: Bollinger Band lower line: Usually 2 standard deviations below the middle line. Purpose: Indicate potential oversold conditions. Hint: Use additional analysis to avoid false reversal signals.
- atr: ATR: Average True Range to measure volatility. Purpose: Set stop-loss levels and adjust position sizes based on current market volatility. Hint: This is a reactive indicator and should be part of a broader risk management strategy.

Volume indicators:
- vwma: VWMA: Volume-weighted moving average. Purpose: Confirm trends by integrating price behavior and volume data. Hint: Pay attention to skewed results due to increased volume; combine with other volume analysis.

- Select indicators that provide diverse and complementary information. Avoid redundancy (e.g., do not select both rsi and stochrsi simultaneously). Also briefly explain why they are suitable for the given market environment. When calling tools, please use the exact names of the indicators provided above, as they are defined parameters, otherwise your call will fail. Please ensure that get_YFin_data is called first to retrieve the CSV required for generating indicators. Write a very detailed and meticulous trend observation report. Do not simply say the trend is mixed, provide detailed and granular analysis and insights that may help traders make decisions.

Please ensure all analyses are in English and append a Markdown table at the end of the report to organize the key points, making it organized and easy to read."""
        )

        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "You are a helpful AI assistant, collaborating with other assistants."
                    "Use the provided tools to answer questions."
                    "If you cannot fully answer, it's okay; another assistant with different tools"
                    "will continue to help from where you stopped. Take actions you can do to make progress."
                    "If you or any other assistant has a final trading suggestion: **Buy/Hold/Sell** or deliverable, "
                    "please add 'Final trading suggestion: **Buy/Hold/Sell**' before your reply, so the team knows to stop."
                    "You can use the following tools: {tool_names}. \n{system_message}"
                    "For your reference, the current date is {current_date}. We are analyzing company {ticker}. Please ensure all analyses are in English.",
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

        # TODO: Add English comment
        if len(result.tool_calls) == 0:
            # TODO: Add English comment
            report = result.content
        else:
            # TODO: Add English comment
            report = f"Market analyst is calling tools for analysis: {[call.get('name', 'unknown') for call in result.tool_calls]}"
            logger.info(f"📊 [Market analyst] Tool calls: {[call.get('name', 'unknown') for call in result.tool_calls]}")

        return {
            "messages": [result],
            "market_report": report,
        }

    return market_analyst_node
