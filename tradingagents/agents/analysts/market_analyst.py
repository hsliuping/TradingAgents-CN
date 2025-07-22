from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain.agents import create_react_agent, AgentExecutor
from langchain import hub
import time
import json
import traceback

# 导入分析模块日志装饰器
from tradingagents.utils.tool_logging import log_analyst_module

# 导入统一日志系统
from tradingagents.utils.logging_init import get_logger
logger = get_logger("default")


def _get_company_name(ticker: str, market_info: dict) -> str:
    """
    根据股票代码获取公司名称

    Args:
        ticker: 股票代码
        market_info: 市场信息字典

    Returns:
        str: 公司名称
    """
    try:
        if market_info['is_china']:
            # 中国A股：使用统一接口获取股票信息
            from tradingagents.dataflows.interface import get_china_stock_info_unified
            stock_info = get_china_stock_info_unified(ticker)

            # 解析股票名称
            if "股票名称:" in stock_info:
                company_name = stock_info.split("股票名称:")[1].split("\n")[0].strip()
                logger.debug(f"📊 [DEBUG] 从统一接口获取中国股票名称: {ticker} -> {company_name}")
                return company_name
            else:
                logger.warning(f"⚠️ [DEBUG] 无法从统一接口解析股票名称: {ticker}")
                return f"股票代码{ticker}"

        elif market_info['is_hk']:
            # 港股：使用改进的港股工具
            try:
                from tradingagents.dataflows.improved_hk_utils import get_hk_company_name_improved
                company_name = get_hk_company_name_improved(ticker)
                logger.debug(f"📊 [DEBUG] 使用改进港股工具获取名称: {ticker} -> {company_name}")
                return company_name
            except Exception as e:
                logger.debug(f"📊 [DEBUG] 改进港股工具获取名称失败: {e}")
                # 降级方案：生成友好的默认名称
                clean_ticker = ticker.replace('.HK', '').replace('.hk', '')
                return f"港股{clean_ticker}"

        elif market_info['is_us']:
            # 美股：使用简单映射或返回代码
            us_stock_names = {
                'AAPL': '苹果公司',
                'TSLA': '特斯拉',
                'NVDA': '英伟达',
                'MSFT': '微软',
                'GOOGL': '谷歌',
                'AMZN': '亚马逊',
                'META': 'Meta',
                'NFLX': '奈飞'
            }

            company_name = us_stock_names.get(ticker.upper(), f"美股{ticker}")
            logger.debug(f"📊 [DEBUG] 美股名称映射: {ticker} -> {company_name}")
            return company_name

        else:
            return f"股票{ticker}"

    except Exception as e:
        logger.error(f"❌ [DEBUG] 获取公司名称失败: {e}")
        return f"股票{ticker}"


def create_market_analyst_react(llm, toolkit):
    """使用ReAct Agent模式的市场分析师（适用于通义千问）"""
    @log_analyst_module("market_react")
    def market_analyst_react_node(state):
        logger.debug(f"📈 [DEBUG] ===== ReAct市场分析师节点开始 =====")

        current_date = state["trade_date"]
        ticker = state["company_of_interest"]

        logger.debug(f"📈 [DEBUG] 输入参数: ticker={ticker}, date={current_date}")

        # 检查是否为中国股票
        def is_china_stock(ticker_code):
            import re
            return re.match(r'^\d{6}$', str(ticker_code))

        is_china = is_china_stock(ticker)
        logger.debug(f"📈 [DEBUG] 股票类型检查: {ticker} -> 中国A股: {is_china}")

        if toolkit.config["online_tools"]:
            # 在线模式，使用ReAct Agent
            if is_china:
                logger.info(f"📈 [市场分析师] 使用ReAct Agent分析中国股票")

                # 创建中国股票数据工具
                from langchain_core.tools import BaseTool

                class ChinaStockDataTool(BaseTool):
                    name: str = "get_china_stock_data"
                    description: str = f"获取中国A股股票{ticker}的市场数据和技术指标（优化缓存版本）。直接调用，无需参数。"

                    def _run(self, query: str = "") -> str:
                        try:
                            logger.debug(f"📈 [DEBUG] ChinaStockDataTool调用，股票代码: {ticker}")
                            # 使用优化的缓存数据获取
                            from tradingagents.dataflows.optimized_china_data import get_china_stock_data_cached
                            return get_china_stock_data_cached(
                                symbol=ticker,
                                start_date='2025-05-28',
                                end_date=current_date,
                                force_refresh=False
                            )
                        except Exception as e:
                            logger.error(f"❌ 优化A股数据获取失败: {e}")
                            # 备用方案：使用原始API
                            try:
                                return toolkit.get_china_stock_data.invoke({
                                    'stock_code': ticker,
                                    'start_date': '2025-05-28',
                                    'end_date': current_date
                                })
                            except Exception as e2:
                                return f"获取股票数据失败: {str(e2)}"

                tools = [ChinaStockDataTool()]
                query = f"""Please analyze in detail the technical analysis of the Chinese A-share stock {ticker}.

Execution steps:
1. Use the get_china_stock_data tool to obtain stock market data
2. Perform in-depth technical indicator analysis based on the obtained real data
3. Directly output the complete technical analysis report content

Important requirements:
- Must output the complete technical analysis report content, do not just describe that the report is complete
- The report must be analyzed based on the real data obtained by the tool
- The report length must be at least 800 characters
- Must include specific data, indicator values, and professional analysis

Report format should include:
## Stock Basic Information
## Technical Indicator Analysis
## Price Trend Analysis
## Volume Analysis
## Market Sentiment Analysis
## Investment Advice"""
            else:
                logger.info(f"📈 [市场分析师] 使用ReAct Agent分析美股/港股")

                # 创建美股数据工具
                from langchain_core.tools import BaseTool

                class USStockDataTool(BaseTool):
                    name: str = "get_us_stock_data"
                    description: str = f"获取美股/港股{ticker}的市场数据和技术指标（优化缓存版本）。直接调用，无需参数。"

                    def _run(self, query: str = "") -> str:
                        try:
                            logger.debug(f"📈 [DEBUG] USStockDataTool调用，股票代码: {ticker}")
                            # 使用优化的缓存数据获取
                            from tradingagents.dataflows.optimized_us_data import get_us_stock_data_cached
                            return get_us_stock_data_cached(
                                symbol=ticker,
                                start_date='2025-05-28',
                                end_date=current_date,
                                force_refresh=False
                            )
                        except Exception as e:
                            logger.error(f"❌ 优化美股数据获取失败: {e}")
                            # 备用方案：使用原始API
                            try:
                                return toolkit.get_YFin_data_online.invoke({
                                    'symbol': ticker,
                                    'start_date': '2025-05-28',
                                    'end_date': current_date
                                })
                            except Exception as e2:
                                return f"获取股票数据失败: {str(e2)}"

                class FinnhubNewsTool(BaseTool):
                    name: str = "get_finnhub_news"
                    description: str = f"获取美股{ticker}的最新新闻和市场情绪（通过FINNHUB API）。直接调用，无需参数。"

                    def _run(self, query: str = "") -> str:
                        try:
                            logger.debug(f"📈 [DEBUG] FinnhubNewsTool调用，股票代码: {ticker}")
                            return toolkit.get_finnhub_news.invoke({
                                'ticker': ticker,
                                'start_date': '2025-05-28',
                                'end_date': current_date
                            })
                        except Exception as e:
                            return f"获取新闻数据失败: {str(e)}"

                tools = [USStockDataTool(), FinnhubNewsTool()]
                query = f"""Please analyze in detail the technical analysis of the US stock {ticker}.

Execution steps:
1. Use the get_us_stock_data tool to obtain stock market data and technical indicators (via FINNHUB API)
2. Use the get_finnhub_news tool to obtain the latest news and market sentiment
3. Perform in-depth technical indicator analysis based on the obtained real data
4. Directly output the complete technical analysis report content

Important requirements:
- Must output the complete technical analysis report content, do not just describe that the report is complete
- The report must be analyzed based on the real data obtained by the tool
- The report length must be at least 800 characters
- Must include specific data, indicator values, and professional analysis
- Combine news information to analyze market sentiment

Report format should include:
## Stock Basic Information
## Technical Indicator Analysis
## Price Trend Analysis
## Volume Analysis
## News and Market Sentiment Analysis
## Investment Advice"""

            try:
                # 创建ReAct Agent
                prompt = hub.pull("hwchase17/react")
                agent = create_react_agent(llm, tools, prompt)
                agent_executor = AgentExecutor(
                    agent=agent,
                    tools=tools,
                    verbose=True,
                    handle_parsing_errors=True,
                    max_iterations=10,  # 增加到10次迭代，确保有足够时间完成分析
                    max_execution_time=180  # 增加到3分钟，给更多时间生成详细报告
                )

                logger.debug(f"📈 [DEBUG] 执行ReAct Agent查询...")
                result = agent_executor.invoke({'input': query})

                report = result['output']
                logger.info(f"📈 [市场分析师] ReAct Agent完成，报告长度: {len(report)}")

            except Exception as e:
                logger.error(f"❌ [DEBUG] ReAct Agent失败: {str(e)}")
                report = f"ReAct Agent市场分析失败: {str(e)}"
        else:
            # 离线模式，使用原有逻辑
            report = "离线模式，暂不支持"

        logger.debug(f"📈 [DEBUG] ===== ReAct市场分析师节点结束 =====")

        return {
            "messages": [("assistant", report)],
            "market_report": report,
        }

    return market_analyst_react_node


def create_market_analyst(llm, toolkit):

    def market_analyst_node(state):
        logger.debug(f"📈 [DEBUG] ===== 市场分析师节点开始 =====")

        current_date = state["trade_date"]
        ticker = state["company_of_interest"]

        logger.debug(f"📈 [DEBUG] 输入参数: ticker={ticker}, date={current_date}")
        logger.debug(f"📈 [DEBUG] 当前状态中的消息数量: {len(state.get('messages', []))}")
        logger.debug(f"📈 [DEBUG] 现有市场报告: {state.get('market_report', 'None')}")

        # 根据股票代码格式选择数据源
        from tradingagents.utils.stock_utils import StockUtils

        market_info = StockUtils.get_market_info(ticker)

        logger.debug(f"📈 [DEBUG] 股票类型检查: {ticker} -> {market_info['market_name']} ({market_info['currency_name']})")

        # 获取公司名称
        company_name = _get_company_name(ticker, market_info)
        logger.debug(f"📈 [DEBUG] 公司名称: {ticker} -> {company_name}")

        if toolkit.config["online_tools"]:
            # 使用统一的市场数据工具，工具内部会自动识别股票类型
            logger.info(f"📊 [市场分析师] 使用统一市场数据工具，自动识别股票类型")
            tools = [toolkit.get_stock_market_data_unified]
            # 安全地获取工具名称用于调试
            tool_names_debug = []
            for tool in tools:
                if hasattr(tool, 'name'):
                    tool_names_debug.append(tool.name)
                elif hasattr(tool, '__name__'):
                    tool_names_debug.append(tool.__name__)
                else:
                    tool_names_debug.append(str(tool))
            logger.debug(f"📊 [DEBUG] 选择的工具: {tool_names_debug}")
            logger.debug(f"📊 [DEBUG] 🔧 统一工具将自动处理: {market_info['market_name']}")
        else:
            tools = [
                toolkit.get_YFin_data,
                toolkit.get_stockstats_indicators_report,
            ]

        # 统一的系统提示，适用于所有股票类型
        system_message = (
            f"""You are a professional stock technical analyst. You must perform a detailed technical analysis of {company_name} (Stock Code: {ticker}).

**Stock Information:**
- Company Name: {company_name}
- Stock Code: {ticker}
- Market: {market_info['market_name']}
- Currency: {market_info['currency_name']} ({market_info['currency_symbol']})

**Tool Usage Instructions:**
You have a tool called get_stock_market_data_unified. You must immediately call this tool to obtain market data for {company_name} ({ticker}).
Do not say you are about to call the tool, just call the tool.

**Analysis Requirements:**
1. After calling the tool, perform technical analysis based on the real data obtained.
2. Analyze moving averages, MACD, RSI, Bollinger Bands, etc.
3. Analyze based on the characteristics of the {market_info['market_name']} market.
4. Provide specific values and professional analysis.
5. Provide clear investment advice.
6. All price data is represented in {market_info['currency_name']} ({market_info['currency_symbol']}).

**Output Format:**
## 📊 Stock Basic Information
- Company Name: {company_name}
- Stock Code: {ticker}
- Market: {market_info['market_name']}

## 📈 Technical Indicator Analysis
## 📉 Price Trend Analysis
## 💭 Investment Advice

Please write all analysis in English. Ensure that in the analysis, you correctly distinguish between the company name "{company_name}" and the stock code "{ticker}"."""
        )


        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "You are a professional stock technical analyst, collaborating with other analysts. "
                    "Use the provided tools to obtain and analyze stock data. "
                    "If you cannot fully answer, it's okay; other analysts will continue analyzing from different angles. "
                    "Perform the technical analysis work you can do to make progress. "
                    "If you have a clear technical investment advice: **Buy/Hold/Sell**, "
                    "please clearly mark it in your reply, but do not use the 'Final Trading Advice' prefix, as the final decision needs to be based on the opinions of all analysts. "
                    "You can use the following tools: {tool_names}. \n{system_message}"
                    "For your reference, the current date is {current_date}. "
                    "We are analyzing {company_name} (Stock Code: {ticker}). "
                    "Please ensure all analysis is in English and correctly distinguishes between the company name and the stock code in the analysis.",
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
        prompt = prompt.partial(company_name=company_name)

        chain = prompt | llm.bind_tools(tools)

        result = chain.invoke(state["messages"])

        # 处理市场分析报告
        if len(result.tool_calls) == 0:
            # 没有工具调用，直接使用LLM的回复
            report = result.content
            logger.info(f"📊 [市场分析师] 直接回复，长度: {len(report)}")
        else:
            # 有工具调用，执行工具并生成完整分析报告
            logger.info(f"📊 [市场分析师] 工具调用: {[call.get('name', 'unknown') for call in result.tool_calls]}")

            try:
                # 执行工具调用
                from langchain_core.messages import ToolMessage, HumanMessage

                tool_messages = []
                for tool_call in result.tool_calls:
                    tool_name = tool_call.get('name')
                    tool_args = tool_call.get('args', {})
                    tool_id = tool_call.get('id')

                    logger.debug(f"📊 [DEBUG] 执行工具: {tool_name}, 参数: {tool_args}")

                    # 找到对应的工具并执行
                    tool_result = None
                    for tool in tools:
                        # 安全地获取工具名称进行比较
                        current_tool_name = None
                        if hasattr(tool, 'name'):
                            current_tool_name = tool.name
                        elif hasattr(tool, '__name__'):
                            current_tool_name = tool.__name__

                        if current_tool_name == tool_name:
                            try:
                                if tool_name == "get_china_stock_data":
                                    # 中国股票数据工具
                                    tool_result = tool.invoke(tool_args)
                                else:
                                    # 其他工具
                                    tool_result = tool.invoke(tool_args)
                                logger.debug(f"📊 [DEBUG] 工具执行成功，结果长度: {len(str(tool_result))}")
                                break
                            except Exception as tool_error:
                                logger.error(f"❌ [DEBUG] 工具执行失败: {tool_error}")
                                tool_result = f"工具执行失败: {str(tool_error)}"

                    if tool_result is None:
                        tool_result = f"未找到工具: {tool_name}"

                    # 创建工具消息
                    tool_message = ToolMessage(
                        content=str(tool_result),
                        tool_call_id=tool_id
                    )
                    tool_messages.append(tool_message)

                # 基于工具结果生成完整分析报告
                analysis_prompt = f"""Now, please generate a detailed technical analysis report based on the data obtained from the above tools.

Requirements:
1. The report must be analyzed based on the real data returned by the tool.
2. Must include specific technical indicator values and professional analysis.
3. Must provide clear investment advice and risk warnings.
4. The report length must be at least 800 characters.
5. Write in English.

Please analyze the technical aspects of stock {ticker}, including:
- Price trend analysis
- Technical indicator interpretation
- Support and resistance analysis
- Volume analysis
- Investment advice"""

                # 构建完整的消息序列
                messages = state["messages"] + [result] + tool_messages + [HumanMessage(content=analysis_prompt)]

                # 生成最终分析报告
                final_result = llm.invoke(messages)
                report = final_result.content

                logger.info(f"📊 [市场分析师] 生成完整分析报告，长度: {len(report)}")

                # 返回包含工具调用和最终分析的完整消息序列
                return {
                    "messages": [result] + tool_messages + [final_result],
                    "market_report": report,
                }

            except Exception as e:
                logger.error(f"❌ [市场分析师] 工具执行或分析生成失败: {e}")
                traceback.print_exc()

                # 降级处理：返回工具调用信息
                report = f"市场分析师调用了工具但分析生成失败: {[call.get('name', 'unknown') for call in result.tool_calls]}"

                return {
                    "messages": [result],
                    "market_report": report,
                }

        return {
            "messages": [result],
            "market_report": report,
        }

    return market_analyst_node
