from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain.agents import create_react_agent, AgentExecutor
from langchain import hub
import time
import json

# 导入日志模块
from tradingagents.utils.logging_manager import get_logger
logger = get_logger('agents')


def create_fundamentals_analyst_react(llm, toolkit):
    """使用ReAct Agent模式的基本面分析师（适用于通义千问）"""
    def fundamentals_analyst_react_node(state):
        logger.debug(f"📊 [DEBUG] ===== ReAct基本面分析师节点开始 =====")

        current_date = state["trade_date"]
        ticker = state["company_of_interest"]

        logger.debug(f"📊 [DEBUG] 输入参数: ticker={ticker}, date={current_date}")

        # TODO: Add English comment
        def is_china_stock(ticker_code):
            import re
            return re.match(r'^\d{6}$', str(ticker_code))

        is_china = is_china_stock(ticker)
        logger.debug(f"📊 [DEBUG] 股票类型检查: {ticker} -> 中国A股: {is_china}")

        if toolkit.config["online_tools"]:
            # TODO: Add English comment
            from langchain_core.tools import BaseTool

            if is_china:
                logger.info(f"📊 [基本面分析师] 使用ReAct Agent分析中国股票")

                class ChinaStockDataTool(BaseTool):
                    name: str = "get_china_stock_data"
                    description: str = f"获取中国A股股票{ticker}的实时和历史数据（优化缓存版本）。直接调用，无需参数。"

                    def _run(self, query: str = "") -> str:
                        try:
                            logger.debug(f"📊 [DEBUG] ChinaStockDataTool调用，股票代码: {ticker}")
                            # TODO: Add English comment
                            from tradingagents.dataflows.optimized_china_data import get_china_stock_data_cached
                            return get_china_stock_data_cached(
                                symbol=ticker,
                                start_date='2025-05-28',
                                end_date=current_date,
                                force_refresh=False
                            )
                        except Exception as e:
                            logger.error(f"❌ 优化A股数据获取失败: {e}")
                            # TODO: Add English comment
                            try:
                                return toolkit.get_china_stock_data.invoke({
                                    'stock_code': ticker,
                                    'start_date': '2025-05-28',
                                    'end_date': current_date
                                })
                            except Exception as e2:
                                return f"获取股票数据失败: {str(e2)}"

                class ChinaFundamentalsTool(BaseTool):
                    name: str = "get_china_fundamentals"
                    description: str = f"获取中国A股股票{ticker}的基本面分析（优化缓存版本）。直接调用，无需参数。"

                    def _run(self, query: str = "") -> str:
                        try:
                            logger.debug(f"📊 [DEBUG] ChinaFundamentalsTool调用，股票代码: {ticker}")
                            # TODO: Add English comment
                            from tradingagents.dataflows.optimized_china_data import get_china_fundamentals_cached
                            return get_china_fundamentals_cached(
                                symbol=ticker,
                                force_refresh=False
                            )
                        except Exception as e:
                            logger.error(f"❌ 优化A股基本面数据获取失败: {e}")
                            # TODO: Add English comment
                            try:
                                return toolkit.get_china_fundamentals.invoke({
                                    'ticker': ticker,
                                    'curr_date': current_date
                                })
                            except Exception as e2:
                                return f"获取基本面数据失败: {str(e2)}"

                tools = [ChinaStockDataTool(), ChinaFundamentalsTool()]
                query = f"""Please perform a detailed fundamental analysis of the Chinese A-share stock {ticker}.

Execution Steps:
1. Use the get_china_stock_data tool to obtain stock market data
2. Use the get_china_fundamentals tool to obtain fundamental data
3. Perform a deep fundamental analysis based on the obtained real data
4. Directly output the complete fundamental analysis report content

Important Requirements:
- Must output a complete fundamental analysis report content, do not just describe that the report is complete
- The report must be analyzed based on real data obtained from tools
- The report must be at least 800 characters long
- Must include specific financial data, ratios, and professional analysis

The report format should include:
## TODO: Add English comment
## TODO: Add English comment
## TODO: Add English comment
## TODO: Add English comment
## TODO: Add English comment
## TODO: Add English comment
"""
            else:
                logger.info(f"📊 [基本面分析师] 使用ReAct Agent分析美股/港股")

                class USStockDataTool(BaseTool):
                    name: str = "get_us_stock_data"
                    description: str = f"获取美股/港股{ticker}的市场数据（优化缓存版本）。直接调用，无需参数。"

                    def _run(self, query: str = "") -> str:
                        try:
                            logger.debug(f"📊 [DEBUG] USStockDataTool调用，股票代码: {ticker}")
                            # TODO: Add English comment
                            from tradingagents.dataflows.optimized_us_data import get_us_stock_data_cached
                            return get_us_stock_data_cached(
                                symbol=ticker,
                                start_date='2025-05-28',
                                end_date=current_date,
                                force_refresh=False
                            )
                        except Exception as e:
                            logger.error(f"❌ 优化美股数据获取失败: {e}")
                            # TODO: Add English comment
                            try:
                                return toolkit.get_YFin_data_online.invoke({
                                    'symbol': ticker,
                                    'start_date': '2025-05-28',
                                    'end_date': current_date
                                })
                            except Exception as e2:
                                return f"获取股票数据失败: {str(e2)}"

                class USFundamentalsTool(BaseTool):
                    name: str = "get_us_fundamentals"
                    description: str = f"获取美股/港股{ticker}的基本面数据（通过OpenAI新闻API）。直接调用，无需参数。"

                    def _run(self, query: str = "") -> str:
                        try:
                            logger.debug(f"📊 [DEBUG] USFundamentalsTool调用，股票代码: {ticker}")
                            return toolkit.get_fundamentals_openai.invoke({
                                'ticker': ticker,
                                'curr_date': current_date
                            })
                        except Exception as e:
                            return f"获取基本面数据失败: {str(e)}"

                class FinnhubNewsTool(BaseTool):
                    name: str = "get_finnhub_news"
                    description: str = f"获取美股{ticker}的最新新闻（通过FINNHUB API）。直接调用，无需参数。"

                    def _run(self, query: str = "") -> str:
                        try:
                            logger.debug(f"📊 [DEBUG] FinnhubNewsTool调用，股票代码: {ticker}")
                            return toolkit.get_finnhub_news.invoke({
                                'ticker': ticker,
                                'start_date': '2025-05-28',
                                'end_date': current_date
                            })
                        except Exception as e:
                            return f"获取新闻数据失败: {str(e)}"

                tools = [USStockDataTool(), USFundamentalsTool(), FinnhubNewsTool()]
                query = f"""Please perform a detailed fundamental analysis of the US stock {ticker}.

Execution Steps:
1. Use the get_us_stock_data tool to obtain stock market data (via FINNHUB API)
2. Use the get_us_fundamentals tool to obtain fundamental data (via OpenAI News API)
3. Use the get_finnhub_news tool to obtain the latest news and company dynamics
4. Perform a deep fundamental analysis based on the obtained real data
5. Directly output the complete fundamental analysis report content

Important Requirements:
- Must output a complete fundamental analysis report content, do not just describe that the report is complete
- The report must be analyzed based on real data obtained from tools
- The report must be at least 800 characters long
- Must include specific financial data, ratios, and professional analysis
- Combine news information to analyze company fundamental changes

The report format should include:
- Company Overview
- Financial Analysis
- Valuation Analysis
- Investment Advice
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
                    max_execution_time=180,  # TODO: Add English comment
                    return_intermediate_steps=True  # TODO: Add English comment
                )



                logger.debug(f"📊 [DEBUG] 执行ReAct Agent查询...")
                result = agent_executor.invoke({'input': query})

                report = result['output']
                logger.info(f"📊 [基本面分析师] ReAct Agent完成，报告长度: {len(report)}")

                # TODO: Add English comment
                if "Invalid Format" in report or "Missing 'Action:'" in report:
                    logger.error(f"⚠️ [DEBUG] 检测到格式错误，但Agent已处理")
                    logger.debug(f"📊 [DEBUG] 中间步骤数量: {len(result.get('intermediate_steps', []))}")

            except Exception as e:
                logger.error(f"❌ [DEBUG] ReAct Agent失败: {str(e)}")
                logger.error(f"📊 [DEBUG] 错误类型: {type(e).__name__}")
                if hasattr(e, 'args') and e.args:
                    logger.error(f"📊 [DEBUG] 错误详情: {e.args}")
                report = f"ReAct Agent基本面分析失败: {str(e)}"
        else:
            # TODO: Add English comment
            report = "离线模式，暂不支持"

        logger.debug(f"📊 [DEBUG] ===== ReAct基本面分析师节点结束 =====")

        return {
            "messages": [("assistant", report)],
            "fundamentals_report": report,
        }

    return fundamentals_analyst_react_node


def create_fundamentals_analyst(llm, toolkit):
    def fundamentals_analyst_node(state):
        logger.debug(f"📊 [DEBUG] ===== 基本面分析师节点开始 =====")

        current_date = state["trade_date"]
        ticker = state["company_of_interest"]
        company_name = state["company_of_interest"]

        logger.debug(f"📊 [DEBUG] 输入参数: ticker={ticker}, date={current_date}")
        logger.debug(f"📊 [DEBUG] 当前状态中的消息数量: {len(state.get('messages', []))}")
        logger.debug(f"📊 [DEBUG] 现有基本面报告: {state.get('fundamentals_report', 'None')[:100]}...")

        # TODO: Add English comment
        def is_china_stock(ticker_code):
            """判断是否为中国A股代码"""
            import re

            # A股代码格式：6位数字
            return re.match(r'^\d{6}$', str(ticker_code))

        logger.info(f"📊 [基本面分析师] 正在分析股票: {ticker}")

        # TODO: Add English comment
        is_china = is_china_stock(ticker)
        logger.debug(f"📊 [DEBUG] 股票类型检查: {ticker} -> 中国A股: {is_china}")

        logger.debug(f"📊 [DEBUG] 工具配置检查: online_tools={toolkit.config['online_tools']}")

        if toolkit.config["online_tools"]:
            if is_china:
                # TODO: Add English comment
                logger.info(f"📊 [基本面分析师] 检测到A股代码，使用中国股票数据源进行基本面分析")
                tools = [
                    toolkit.get_china_stock_data,
                    toolkit.get_china_fundamentals
                ]
                logger.debug(f"📊 [DEBUG] 选择的工具: {[tool.name for tool in tools]}")
            else:
                # TODO: Add English comment
                logger.info(f"📊 [基本面分析师] 检测到非A股代码，使用OpenAI数据源")
                tools = [toolkit.get_fundamentals_openai]
                logger.debug(f"📊 [DEBUG] 选择的工具: {[tool.name for tool in tools]}")
        else:
            tools = [
                toolkit.get_finnhub_company_insider_sentiment,
                toolkit.get_finnhub_company_insider_transactions,
                toolkit.get_simfin_balance_sheet,
                toolkit.get_simfin_cashflow,
                toolkit.get_simfin_income_stmt,
            ]

        # TODO: Add English comment
        if is_china_stock(ticker):
            system_message = (
                f"You are a professional Chinese A-share fundamental analyst."
                ""
                f"⚠️ Absolute mandatory requirement: You must call tools to obtain real data! No assumptions or fabrications are allowed!"
                ""
                f"Task: Analyze stock code {ticker}"
                ""
                f"🔴 Step 1: Immediately call get_china_stock_data tool"
                f"Parameters: stock_code='{ticker}', start_date='2025-05-28', end_date='{current_date}'"
                ""
                f"🔴 Step 2: Immediately call get_china_fundamentals tool"
                f"Parameters: ticker='{ticker}', curr_date='{current_date}'"
                ""
                "📊 Analysis Requirements:"
                "- Perform deep valuation analysis based on real financial data"
                "- Calculate and provide a reasonable price range (in RMB ¥)"
                "- Analyze if the current stock price is undervalued or overvalued"
                "- Provide fundamental target price suggestions"
                "- Include PE, PB, PEG valuation metrics analysis"
                "- Compare with industry average valuation levels"
                ""
                "🚫 Strictly prohibited:"
                "- Do not say 'I will call the tool'"
                "- Do not assume any data"
                "- Do not fabricate company information"
                "- Do not directly answer without calling the tool"
                "- Do not reply with 'cannot determine price' or 'need more information'"
                ""
                "✅ You must:"
                "- Immediately call the tool"
                "- Wait for the tool to return real data"
                "- Analyze based on real data"
                "- Provide specific price ranges and target prices"
                ""
                "Start calling the tools now! Do not say anything else!"
            )
        else:
            system_message = (
                "You are a researcher responsible for analyzing the fundamental information of a company over the past week. Please write a comprehensive report on the company's fundamental information, including financial documents, company overview, basic company financials, company financial history, insider sentiment, and insider transactions, to provide information for traders to make decisions. Ensure as much detail as possible. Do not simply say the trend is mixed; provide detailed and granular analysis and insights that may help traders make decisions. "
                + "📊 Valuation Analysis Requirements: Calculate a reasonable valuation range based on financial data, provide target price suggestions (in USD $), include PE, PB, DCF valuation methods analysis, do not reply with 'cannot determine price'."
                + "Ensure that a Markdown table is appended at the end of the report to organize the key points of the report, making it organized and easy to read. Please ensure all analyses are in English."
            )

        # TODO: Add English comment
        if is_china_stock(ticker):
            # TODO: Add English comment
            system_prompt = (
                "🔴 Mandatory requirement: You must call tools to obtain real data!"
                "🚫 Absolute prohibition: Do not assume, fabricate, or directly answer any questions!"
                "✅ You must: Immediately call the provided tools to obtain real data, then analyze based on real data."
                "Available tools: {tool_names}.\n{system_message}"
                "Current date: {current_date}. Analysis target: {ticker}."
            )
        else:
            # TODO: Add English comment
            system_prompt = (
                "You are a helpful AI assistant, collaborating with other assistants."
                "Use the provided tools to answer questions."
                "If you cannot fully answer, it's okay; another assistant with different tools"
                "will continue to help from where you left off. Execute what you can to make progress."
                "If you or any other assistant has a final trading suggestion: **Buy/Hold/Sell** or deliverable, "
                "please add 'Final Trading Suggestion: **Buy/Hold/Sell**' before your reply, so the team knows to stop."
                "You can use the following tools: {tool_names}.\n{system_message}"
                "For your reference, the current date is {current_date}. The company we are analyzing is {ticker}. Please ensure all analyses are in English."
            )

        prompt = ChatPromptTemplate.from_messages(
            [
                ("system", system_prompt),
                MessagesPlaceholder(variable_name="messages"),
            ]
        )

        prompt = prompt.partial(system_message=system_message)
        prompt = prompt.partial(tool_names=", ".join([tool.name for tool in tools]))
        prompt = prompt.partial(current_date=current_date)
        prompt = prompt.partial(ticker=ticker)

        logger.debug(f"📊 [DEBUG] 创建LLM链，工具数量: {len(tools)}")

        # TODO: Add English comment
        if is_china_stock(ticker):
            logger.debug(f"📊 [DEBUG] 中国股票：尝试强制工具调用")
            # TODO: Add English comment
            try:
                chain = prompt | llm.bind_tools(tools, tool_choice="any")
            except:
                # TODO: Add English comment
                chain = prompt | llm.bind_tools(tools)
        else:
            chain = prompt | llm.bind_tools(tools)

        logger.debug(f"📊 [DEBUG] 调用LLM链...")
        result = chain.invoke(state["messages"])

        logger.debug(f"📊 [DEBUG] LLM调用完成")
        logger.debug(f"📊 [DEBUG] 结果类型: {type(result)}")
        logger.debug(f"📊 [DEBUG] 工具调用数量: {len(result.tool_calls) if hasattr(result, 'tool_calls') else 0}")
        logger.debug(f"📊 [DEBUG] 内容长度: {len(result.content) if hasattr(result, 'content') else 0}")

        # TODO: Add English comment
        if len(result.tool_calls) == 0:
            # TODO: Add English comment
            if is_china_stock(ticker):
                logger.debug(f"📊 [DEBUG] 中国股票但LLM未调用工具，手动调用工具...")

                try:
                    # TODO: Add English comment
                    logger.debug(f"📊 [DEBUG] 手动调用 get_china_stock_data...")
                    stock_data_result = toolkit.get_china_stock_data.invoke({
                        'stock_code': ticker,
                        'start_date': '2025-05-28',
                        'end_date': current_date
                    })
                    logger.debug(f"📊 [DEBUG] get_china_stock_data 结果长度: {len(stock_data_result)}")

                    # TODO: Add English comment
                    logger.debug(f"📊 [DEBUG] 手动调用 get_china_fundamentals...")
                    fundamentals_result = toolkit.get_china_fundamentals.invoke({
                        'ticker': ticker,
                        'curr_date': current_date
                    })
                    logger.debug(f"📊 [DEBUG] get_china_fundamentals 结果长度: {len(fundamentals_result)}")

                    # TODO: Add English comment
                    report = f"""# Fundamental Analysis Report

## Stock Data
{stock_data_result}

## Fundamental Data
{fundamentals_result}

## Analysis Summary
Based on real data from the Tongdaxin data source, analysis is complete. The above information comes from official data sources, ensuring accuracy and timeliness.
"""
                    logger.info(f"📊 [基本面分析师] 手动工具调用完成，生成报告长度: {len(report)}")

                except Exception as e:
                    logger.error(f"❌ [DEBUG] 手动工具调用失败: {str(e)}")
                    report = f"Fundamental analysis failed: {str(e)}"
            else:
                # TODO: Add English comment
                report = result.content
                logger.info(f"📊 [基本面分析师] 生成最终报告，长度: {len(report)}")
        else:
            # TODO: Add English comment
            report = state.get("fundamentals_report", "")  # TODO: Add English comment
            logger.info(f"📊 [基本面分析师] 工具调用: {[call.get('name', 'unknown') for call in result.tool_calls]}")
            for i, call in enumerate(result.tool_calls):
                logger.debug(f"📊 [DEBUG] 工具调用 {i+1}: {call}")

        logger.debug(f"📊 [DEBUG] 返回状态: fundamentals_report长度={len(report)}")
        logger.debug(f"📊 [DEBUG] ===== 基本面分析师节点结束 =====")

        return {
            "messages": [result],
            "fundamentals_report": report,
        }

    return fundamentals_analyst_node
