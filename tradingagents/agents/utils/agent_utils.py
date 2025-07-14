from langchain_core.messages import BaseMessage, HumanMessage, ToolMessage, AIMessage
from typing import List
from typing import Annotated
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import RemoveMessage
from langchain_core.tools import tool
from datetime import date, timedelta, datetime
import functools
import pandas as pd
import os
from dateutil.relativedelta import relativedelta
from langchain_openai import ChatOpenAI
import tradingagents.dataflows.interface as interface
from tradingagents.default_config import DEFAULT_CONFIG
from langchain_core.messages import HumanMessage


def create_msg_delete():
    def delete_messages(state):
        """Clear messages and add placeholder for Anthropic compatibility"""
        messages = state["messages"]
        
        # Remove all messages
        removal_operations = [RemoveMessage(id=m.id) for m in messages]
        
        # Add a minimal placeholder message
        placeholder = HumanMessage(content="Continue")
        
        return {"messages": removal_operations + [placeholder]}
    
    return delete_messages


class Toolkit:
    _config = DEFAULT_CONFIG.copy()

    @classmethod
    def update_config(cls, config):
        """Update the class-level configuration."""
        cls._config.update(config)

    @property
    def config(self):
        """Access the configuration."""
        return self._config

    def __init__(self, config=None):
        if config:
            self.update_config(config)

    @staticmethod
    @tool
    def get_reddit_news(
        curr_date: Annotated[str, "Date you want to get news for in yyyy-mm-dd format"],
    ) -> str:
        """
        Retrieve global news from Reddit within a specified time frame.
        Args:
            curr_date (str): Date you want to get news for in yyyy-mm-dd format
        Returns:
            str: A formatted dataframe containing the latest global news from Reddit in the specified time frame.
        """
        
        global_news_result = interface.get_reddit_global_news(curr_date, 7, 5)

        return global_news_result

    @staticmethod
    @tool
    def get_finnhub_news(
        ticker: Annotated[
            str,
            "Search query of a company, e.g. 'AAPL, TSM, etc.",
        ],
        start_date: Annotated[str, "Start date in yyyy-mm-dd format"],
        end_date: Annotated[str, "End date in yyyy-mm-dd format"],
    ):
        """
        Retrieve the latest news about a given stock from Finnhub within a date range
        Args:
            ticker (str): Ticker of a company. e.g. AAPL, TSM
            start_date (str): Start date in yyyy-mm-dd format
            end_date (str): End date in yyyy-mm-dd format
        Returns:
            str: A formatted dataframe containing news about the company within the date range from start_date to end_date
        """

        end_date_str = end_date

        end_date = datetime.strptime(end_date, "%Y-%m-%d")
        start_date = datetime.strptime(start_date, "%Y-%m-%d")
        look_back_days = (end_date - start_date).days

        finnhub_news_result = interface.get_finnhub_news(
            ticker, end_date_str, look_back_days
        )

        return finnhub_news_result

    @staticmethod
    @tool
    def get_reddit_stock_info(
        ticker: Annotated[
            str,
            "Ticker of a company. e.g. AAPL, TSM",
        ],
        curr_date: Annotated[str, "Current date you want to get news for"],
    ) -> str:
        """
        Retrieve the latest news about a given stock from Reddit, given the current date.
        Args:
            ticker (str): Ticker of a company. e.g. AAPL, TSM
            curr_date (str): current date in yyyy-mm-dd format to get news for
        Returns:
            str: A formatted dataframe containing the latest news about the company on the given date
        """

        stock_news_results = interface.get_reddit_company_news(ticker, curr_date, 7, 5)

        return stock_news_results

    @staticmethod
    @tool
    def get_chinese_social_sentiment(
        ticker: Annotated[str, "Ticker of a company. e.g. AAPL, TSM"],
        curr_date: Annotated[str, "Current date in yyyy-mm-dd format"],
    ) -> str:
        """
        获取中国社交媒体和财经平台上关于特定股票的情绪分析和讨论热度。
        整合雪球、东方财富股吧、新浪财经等中国本土平台的数据。
        Args:
            ticker (str): 股票代码，如 AAPL, TSM
            curr_date (str): 当前日期，格式为 yyyy-mm-dd
        Returns:
            str: 包含中国投资者情绪分析、讨论热度、关键观点的格式化报告
        """
        try:
            # 这里可以集成多个中国平台的数据
            chinese_sentiment_results = interface.get_chinese_social_sentiment(ticker, curr_date)
            return chinese_sentiment_results
        except Exception as e:
            # 如果中国平台数据获取失败，回退到原有的Reddit数据
            return interface.get_reddit_company_news(ticker, curr_date, 7, 5)

    @staticmethod
    @tool
    def get_china_stock_data(
        stock_code: Annotated[str, "中国股票代码，如 000001(平安银行), 600519(贵州茅台)"],
        start_date: Annotated[str, "开始日期，格式 yyyy-mm-dd"],
        end_date: Annotated[str, "结束日期，格式 yyyy-mm-dd"],
    ) -> str:
        """
        获取中国A股实时和历史数据，通过Tushare等高质量数据源提供专业的股票数据。
        支持实时行情、历史K线、技术指标等全面数据，自动使用最佳数据源。
        Args:
            stock_code (str): 中国股票代码，如 000001(平安银行), 600519(贵州茅台)
            start_date (str): 开始日期，格式 yyyy-mm-dd
            end_date (str): 结束日期，格式 yyyy-mm-dd
        Returns:
            str: 包含实时行情、历史数据、技术指标的完整股票分析报告
        """
        try:
            print(f"📊 [DEBUG] ===== agent_utils.get_china_stock_data 开始调用 =====")
            print(f"📊 [DEBUG] 参数: stock_code={stock_code}, start_date={start_date}, end_date={end_date}")

            from tradingagents.dataflows.interface import get_china_stock_data_unified
            print(f"📊 [DEBUG] 成功导入统一数据源接口")

            print(f"📊 [DEBUG] 正在调用统一数据源接口...")
            result = get_china_stock_data_unified(stock_code, start_date, end_date)

            print(f"📊 [DEBUG] 统一数据源接口调用完成")
            print(f"📊 [DEBUG] 返回结果类型: {type(result)}")
            print(f"📊 [DEBUG] 返回结果长度: {len(result) if result else 0}")
            print(f"📊 [DEBUG] 返回结果前200字符: {str(result)[:200]}...")
            print(f"📊 [DEBUG] ===== agent_utils.get_china_stock_data 调用结束 =====")

            return result
        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            print(f"❌ [DEBUG] ===== agent_utils.get_china_stock_data 异常 =====")
            print(f"❌ [DEBUG] 错误类型: {type(e).__name__}")
            print(f"❌ [DEBUG] 错误信息: {str(e)}")
            print(f"❌ [DEBUG] 详细堆栈:")
            print(error_details)
            print(f"❌ [DEBUG] ===== 异常处理结束 =====")
            return f"中国股票数据获取失败: {str(e)}。建议安装pytdx库: pip install pytdx"

    @staticmethod
    @tool
    def get_china_market_overview(
        curr_date: Annotated[str, "当前日期，格式 yyyy-mm-dd"],
    ) -> str:
        """
        获取中国股市整体概览，包括主要指数的实时行情。
        涵盖上证指数、深证成指、创业板指、科创50等主要指数。
        Args:
            curr_date (str): 当前日期，格式 yyyy-mm-dd
        Returns:
            str: 包含主要指数实时行情的市场概览报告
        """
        try:
            # 使用Tushare获取主要指数数据
            from tradingagents.dataflows.tushare_adapter import get_tushare_adapter

            adapter = get_tushare_adapter()
            if not adapter.provider or not adapter.provider.connected:
                # 如果Tushare不可用，回退到TDX
                print("⚠️ Tushare不可用，回退到TDX获取市场概览")
                from tradingagents.dataflows.tdx_utils import get_china_market_overview
                return get_china_market_overview()

            # 使用Tushare获取主要指数信息
            # 这里可以扩展为获取具体的指数数据
            return f"""# 中国股市概览 - {curr_date}

## 📊 主要指数
- 上证指数: 数据获取中...
- 深证成指: 数据获取中...
- 创业板指: 数据获取中...
- 科创50: 数据获取中...

## 💡 说明
市场概览功能正在从TDX迁移到Tushare，完整功能即将推出。
当前可以使用股票数据获取功能分析个股。

数据来源: Tushare专业数据源
更新时间: {curr_date}
"""

        except Exception as e:
            return f"中国市场概览获取失败: {str(e)}。正在从TDX迁移到Tushare数据源。"

    @staticmethod
    @tool
    def get_YFin_data(
        symbol: Annotated[str, "ticker symbol of the company"],
        start_date: Annotated[str, "Start date in yyyy-mm-dd format"],
        end_date: Annotated[str, "End date in yyyy-mm-dd format"],
    ) -> str:
        """
        Retrieve the stock price data for a given ticker symbol from Yahoo Finance.
        Args:
            symbol (str): Ticker symbol of the company, e.g. AAPL, TSM
            start_date (str): Start date in yyyy-mm-dd format
            end_date (str): End date in yyyy-mm-dd format
        Returns:
            str: A formatted dataframe containing the stock price data for the specified ticker symbol in the specified date range.
        """

        result_data = interface.get_YFin_data(symbol, start_date, end_date)

        return result_data

    @staticmethod
    @tool
    def get_YFin_data_online(
        symbol: Annotated[str, "ticker symbol of the company"],
        start_date: Annotated[str, "Start date in yyyy-mm-dd format"],
        end_date: Annotated[str, "End date in yyyy-mm-dd format"],
    ) -> str:
        """
        Retrieve the stock price data for a given ticker symbol from Yahoo Finance.
        Args:
            symbol (str): Ticker symbol of the company, e.g. AAPL, TSM
            start_date (str): Start date in yyyy-mm-dd format
            end_date (str): End date in yyyy-mm-dd format
        Returns:
            str: A formatted dataframe containing the stock price data for the specified ticker symbol in the specified date range.
        """

        result_data = interface.get_YFin_data_online(symbol, start_date, end_date)

        return result_data

    @staticmethod
    @tool
    def get_stockstats_indicators_report(
        symbol: Annotated[str, "ticker symbol of the company"],
        indicator: Annotated[
            str, "technical indicator to get the analysis and report of"
        ],
        curr_date: Annotated[
            str, "The current trading date you are trading on, YYYY-mm-dd"
        ],
        look_back_days: Annotated[int, "how many days to look back"] = 30,
    ) -> str:
        """
        Retrieve stock stats indicators for a given ticker symbol and indicator.
        Args:
            symbol (str): Ticker symbol of the company, e.g. AAPL, TSM
            indicator (str): Technical indicator to get the analysis and report of
            curr_date (str): The current trading date you are trading on, YYYY-mm-dd
            look_back_days (int): How many days to look back, default is 30
        Returns:
            str: A formatted dataframe containing the stock stats indicators for the specified ticker symbol and indicator.
        """

        result_stockstats = interface.get_stock_stats_indicators_window(
            symbol, indicator, curr_date, look_back_days, False
        )

        return result_stockstats

    @staticmethod
    @tool
    def get_stockstats_indicators_report_online(
        symbol: Annotated[str, "ticker symbol of the company"],
        indicator: Annotated[
            str, "technical indicator to get the analysis and report of"
        ],
        curr_date: Annotated[
            str, "The current trading date you are trading on, YYYY-mm-dd"
        ],
        look_back_days: Annotated[int, "how many days to look back"] = 30,
    ) -> str:
        """
        Retrieve stock stats indicators for a given ticker symbol and indicator.
        Args:
            symbol (str): Ticker symbol of the company, e.g. AAPL, TSM
            indicator (str): Technical indicator to get the analysis and report of
            curr_date (str): The current trading date you are trading on, YYYY-mm-dd
            look_back_days (int): How many days to look back, default is 30
        Returns:
            str: A formatted dataframe containing the stock stats indicators for the specified ticker symbol and indicator.
        """

        result_stockstats = interface.get_stock_stats_indicators_window(
            symbol, indicator, curr_date, look_back_days, True
        )

        return result_stockstats

    @staticmethod
    @tool
    def get_finnhub_company_insider_sentiment(
        ticker: Annotated[str, "ticker symbol for the company"],
        curr_date: Annotated[
            str,
            "current date of you are trading at, yyyy-mm-dd",
        ],
    ):
        """
        Retrieve insider sentiment information about a company (retrieved from public SEC information) for the past 30 days
        Args:
            ticker (str): ticker symbol of the company
            curr_date (str): current date you are trading at, yyyy-mm-dd
        Returns:
            str: a report of the sentiment in the past 30 days starting at curr_date
        """

        data_sentiment = interface.get_finnhub_company_insider_sentiment(
            ticker, curr_date, 30
        )

        return data_sentiment

    @staticmethod
    @tool
    def get_finnhub_company_insider_transactions(
        ticker: Annotated[str, "ticker symbol"],
        curr_date: Annotated[
            str,
            "current date you are trading at, yyyy-mm-dd",
        ],
    ):
        """
        Retrieve insider transaction information about a company (retrieved from public SEC information) for the past 30 days
        Args:
            ticker (str): ticker symbol of the company
            curr_date (str): current date you are trading at, yyyy-mm-dd
        Returns:
            str: a report of the company's insider transactions/trading information in the past 30 days
        """

        data_trans = interface.get_finnhub_company_insider_transactions(
            ticker, curr_date, 30
        )

        return data_trans

    @staticmethod
    @tool
    def get_simfin_balance_sheet(
        ticker: Annotated[str, "ticker symbol"],
        freq: Annotated[
            str,
            "reporting frequency of the company's financial history: annual/quarterly",
        ],
        curr_date: Annotated[str, "current date you are trading at, yyyy-mm-dd"],
    ):
        """
        Retrieve the most recent balance sheet of a company
        Args:
            ticker (str): ticker symbol of the company
            freq (str): reporting frequency of the company's financial history: annual / quarterly
            curr_date (str): current date you are trading at, yyyy-mm-dd
        Returns:
            str: a report of the company's most recent balance sheet
        """

        data_balance_sheet = interface.get_simfin_balance_sheet(ticker, freq, curr_date)

        return data_balance_sheet

    @staticmethod
    @tool
    def get_simfin_cashflow(
        ticker: Annotated[str, "ticker symbol"],
        freq: Annotated[
            str,
            "reporting frequency of the company's financial history: annual/quarterly",
        ],
        curr_date: Annotated[str, "current date you are trading at, yyyy-mm-dd"],
    ):
        """
        Retrieve the most recent cash flow statement of a company
        Args:
            ticker (str): ticker symbol of the company
            freq (str): reporting frequency of the company's financial history: annual / quarterly
            curr_date (str): current date you are trading at, yyyy-mm-dd
        Returns:
                str: a report of the company's most recent cash flow statement
        """

        data_cashflow = interface.get_simfin_cashflow(ticker, freq, curr_date)

        return data_cashflow

    @staticmethod
    @tool
    def get_simfin_income_stmt(
        ticker: Annotated[str, "ticker symbol"],
        freq: Annotated[
            str,
            "reporting frequency of the company's financial history: annual/quarterly",
        ],
        curr_date: Annotated[str, "current date you are trading at, yyyy-mm-dd"],
    ):
        """
        Retrieve the most recent income statement of a company
        Args:
            ticker (str): ticker symbol of the company
            freq (str): reporting frequency of the company's financial history: annual / quarterly
            curr_date (str): current date you are trading at, yyyy-mm-dd
        Returns:
                str: a report of the company's most recent income statement
        """

        data_income_stmt = interface.get_simfin_income_statements(
            ticker, freq, curr_date
        )

        return data_income_stmt

    @staticmethod
    @tool
    def get_google_news(
        query: Annotated[str, "Query to search with"],
        curr_date: Annotated[str, "Curr date in yyyy-mm-dd format"],
    ):
        """
        Retrieve the latest news from Google News based on a query and date range.
        Args:
            query (str): Query to search with
            curr_date (str): Current date in yyyy-mm-dd format
            look_back_days (int): How many days to look back
        Returns:
            str: A formatted string containing the latest news from Google News based on the query and date range.
        """

        google_news_results = interface.get_google_news(query, curr_date, 7)

        return google_news_results

    @staticmethod
    @tool
    def get_realtime_stock_news(
        ticker: Annotated[str, "Ticker of a company. e.g. AAPL, TSM"],
        curr_date: Annotated[str, "Current date in yyyy-mm-dd format"],
    ) -> str:
        """
        获取股票的实时新闻分析，解决传统新闻源的滞后性问题。
        整合多个专业财经API，提供15-30分钟内的最新新闻。
        Args:
            ticker (str): 股票代码，如 AAPL, TSM
            curr_date (str): 当前日期，格式为 yyyy-mm-dd
        Returns:
            str: 包含实时新闻分析、紧急程度评估、时效性说明的格式化报告
        """
        try:
            from tradingagents.dataflows.realtime_news_utils import get_realtime_stock_news
            return get_realtime_stock_news(ticker, curr_date, hours_back=6)
        except Exception as e:
            # 如果实时新闻获取失败，回退到Google新闻
            return interface.get_google_news(f"{ticker} stock news", curr_date, 1)

    @staticmethod
    @tool
    def get_stock_news_openai(
        ticker: Annotated[str, "the company's ticker"],
        curr_date: Annotated[str, "Current date in yyyy-mm-dd format"],
    ):
        """
        Retrieve the latest news about a given stock by using OpenAI's news API.
        Args:
            ticker (str): Ticker of a company. e.g. AAPL, TSM
            curr_date (str): Current date in yyyy-mm-dd format
        Returns:
            str: A formatted string containing the latest news about the company on the given date.
        """

        openai_news_results = interface.get_stock_news_openai(ticker, curr_date)

        return openai_news_results

    @staticmethod
    @tool
    def get_global_news_openai(
        curr_date: Annotated[str, "Current date in yyyy-mm-dd format"],
    ):
        """
        Retrieve the latest macroeconomics news on a given date using OpenAI's macroeconomics news API.
        Args:
            curr_date (str): Current date in yyyy-mm-dd format
        Returns:
            str: A formatted string containing the latest macroeconomic news on the given date.
        """

        openai_news_results = interface.get_global_news_openai(curr_date)

        return openai_news_results

    @staticmethod
    @tool
    def get_fundamentals_openai(
        ticker: Annotated[str, "the company's ticker"],
        curr_date: Annotated[str, "Current date in yyyy-mm-dd format"],
    ):
        """
        Retrieve the latest fundamental information about a given stock on a given date by using OpenAI's news API.
        Args:
            ticker (str): Ticker of a company. e.g. AAPL, TSM
            curr_date (str): Current date in yyyy-mm-dd format
        Returns:
            str: A formatted string containing the latest fundamental information about the company on the given date.
        """
        print(f"📊 [DEBUG] get_fundamentals_openai 被调用: ticker={ticker}, date={curr_date}")

        # 检查是否为中国股票
        import re
        if re.match(r'^\d{6}$', str(ticker)):
            print(f"📊 [DEBUG] 检测到中国A股代码: {ticker}")
            # 使用统一接口获取中国股票名称
            try:
                from tradingagents.dataflows.interface import get_china_stock_info_unified
                stock_info = get_china_stock_info_unified(ticker)

                # 解析股票名称
                if "股票名称:" in stock_info:
                    company_name = stock_info.split("股票名称:")[1].split("\n")[0].strip()
                else:
                    company_name = f"股票代码{ticker}"

                print(f"📊 [DEBUG] 中国股票名称映射: {ticker} -> {company_name}")
            except Exception as e:
                print(f"⚠️ [DEBUG] 从统一接口获取股票名称失败: {e}")
                company_name = f"股票代码{ticker}"

            # 修改查询以包含正确的公司名称
            modified_query = f"{company_name}({ticker})"
            print(f"📊 [DEBUG] 修改后的查询: {modified_query}")
        else:
            print(f"📊 [DEBUG] 检测到非中国股票: {ticker}")
            modified_query = ticker

        try:
            openai_fundamentals_results = interface.get_fundamentals_openai(
                modified_query, curr_date
            )
            print(f"📊 [DEBUG] OpenAI基本面分析结果长度: {len(openai_fundamentals_results) if openai_fundamentals_results else 0}")
            return openai_fundamentals_results
        except Exception as e:
            print(f"❌ [DEBUG] OpenAI基本面分析失败: {str(e)}")
            return f"基本面分析失败: {str(e)}"

    @staticmethod
    @tool
    def get_china_fundamentals(
        ticker: Annotated[str, "中国A股股票代码，如600036"],
        curr_date: Annotated[str, "当前日期，格式为yyyy-mm-dd"],
    ):
        """
        获取中国A股股票的基本面信息，使用中国股票数据源。
        Args:
            ticker (str): 中国A股股票代码，如600036, 000001
            curr_date (str): 当前日期，格式为yyyy-mm-dd
        Returns:
            str: 包含股票基本面信息的格式化字符串
        """
        print(f"📊 [DEBUG] get_china_fundamentals 被调用: ticker={ticker}, date={curr_date}")

        # 检查是否为中国股票
        import re
        if not re.match(r'^\d{6}$', str(ticker)):
            return f"错误：{ticker} 不是有效的中国A股代码格式"

        try:
            # 使用统一数据源接口获取股票数据（默认Tushare，支持备用数据源）
            from tradingagents.dataflows.interface import get_china_stock_data_unified
            print(f"📊 [DEBUG] 正在获取 {ticker} 的股票数据...")

            # 获取最近30天的数据用于基本面分析
            from datetime import datetime, timedelta
            end_date = datetime.strptime(curr_date, '%Y-%m-%d')
            start_date = end_date - timedelta(days=30)

            stock_data = get_china_stock_data_unified(
                ticker,
                start_date.strftime('%Y-%m-%d'),
                end_date.strftime('%Y-%m-%d')
            )

            print(f"📊 [DEBUG] 股票数据获取完成，长度: {len(stock_data) if stock_data else 0}")

            if not stock_data or "获取失败" in stock_data or "❌" in stock_data:
                return f"无法获取股票 {ticker} 的基本面数据：{stock_data}"

            # 调用真正的基本面分析
            from tradingagents.dataflows.optimized_china_data import OptimizedChinaDataProvider

            # 创建分析器实例
            analyzer = OptimizedChinaDataProvider()

            # 生成真正的基本面分析报告
            fundamentals_report = analyzer._generate_fundamentals_report(ticker, stock_data)

            print(f"📊 [DEBUG] 中国基本面分析报告生成完成")
            print(f"📊 [DEBUG] get_china_fundamentals 结果长度: {len(fundamentals_report)}")

            return fundamentals_report

        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            print(f"❌ [DEBUG] get_china_fundamentals 失败:")
            print(f"❌ [DEBUG] 错误: {str(e)}")
            print(f"❌ [DEBUG] 堆栈: {error_details}")
            return f"中国股票基本面分析失败: {str(e)}"
