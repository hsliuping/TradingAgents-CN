"""
遗留工具桥接模块
自动将 tradingagents.agents.utils.agent_utils 中的旧版工具注册到新系统中。
"""
import logging
from typing import Annotated, Optional
from core.tools.base import register_tool
from tradingagents.agents.utils.agent_utils import Toolkit

logger = logging.getLogger(__name__)

def _invoke_legacy_tool(tool_func, **kwargs):
    """通用桥接调用逻辑"""
    try:
        # LangChain @tool 装饰后的对象通常有 invoke 方法
        if hasattr(tool_func, "invoke"):
            return tool_func.invoke(kwargs)
        # 如果是普通函数，直接调用
        return tool_func(**kwargs)
    except Exception as e:
        logger.error(f"调用旧版工具失败 {tool_func}: {e}")
        return f"Error executing legacy tool: {str(e)}"

# ==============================================================================
# 新闻类 (News)
# ==============================================================================

@register_tool(
    tool_id="get_reddit_news_legacy",
    name="Reddit 全球新闻 (Legacy)",
    description="获取 Reddit 上的全球新闻聚合（旧版接口）",
    category="news",
    is_online=True
)
def get_reddit_news_bridge(curr_date: str) -> str:
    return _invoke_legacy_tool(Toolkit.get_reddit_news, curr_date=curr_date)

@register_tool(
    tool_id="get_finnhub_news_legacy",
    name="Finnhub 财经新闻 (Legacy)",
    description="从 Finnhub 获取特定股票的新闻（旧版接口）",
    category="news",
    is_online=True
)
def get_finnhub_news_bridge(ticker: str, start_date: str, end_date: str) -> str:
    return _invoke_legacy_tool(Toolkit.get_finnhub_news, ticker=ticker, start_date=start_date, end_date=end_date)

@register_tool(
    tool_id="get_google_news_legacy",
    name="Google 新闻搜索 (Legacy)",
    description="通过 Google News 搜索特定关键词的新闻（旧版接口）",
    category="news",
    is_online=True
)
def get_google_news_bridge(query: str, curr_date: str) -> str:
    return _invoke_legacy_tool(Toolkit.get_google_news, query=query, curr_date=curr_date)

@register_tool(
    tool_id="get_realtime_stock_news_legacy",
    name="实时股票新闻 (Legacy)",
    description="获取股票的实时新闻分析（旧版接口）",
    category="news",
    is_online=True
)
def get_realtime_stock_news_bridge(ticker: str, curr_date: str) -> str:
    return _invoke_legacy_tool(Toolkit.get_realtime_stock_news, ticker=ticker, curr_date=curr_date)

@register_tool(
    tool_id="get_stock_news_openai_legacy",
    name="OpenAI 股票新闻分析 (Legacy)",
    description="使用 OpenAI 接口获取并分析股票新闻（旧版接口）",
    category="news",
    is_online=True
)
def get_stock_news_openai_bridge(ticker: str, curr_date: str) -> str:
    return _invoke_legacy_tool(Toolkit.get_stock_news_openai, ticker=ticker, curr_date=curr_date)

@register_tool(
    tool_id="get_global_news_openai_legacy",
    name="OpenAI 宏观新闻分析 (Legacy)",
    description="使用 OpenAI 接口获取并分析宏观经济新闻（旧版接口）",
    category="news",
    is_online=True
)
def get_global_news_openai_bridge(curr_date: str) -> str:
    return _invoke_legacy_tool(Toolkit.get_global_news_openai, curr_date=curr_date)

# ==============================================================================
# 社交情绪类 (Social)
# ==============================================================================

@register_tool(
    tool_id="get_reddit_stock_info_legacy",
    name="Reddit 股票讨论 (Legacy)",
    description="获取 Reddit 上关于特定股票的讨论信息（旧版接口）",
    category="social",
    is_online=True
)
def get_reddit_stock_info_bridge(ticker: str, curr_date: str) -> str:
    return _invoke_legacy_tool(Toolkit.get_reddit_stock_info, ticker=ticker, curr_date=curr_date)

@register_tool(
    tool_id="get_chinese_social_sentiment_legacy",
    name="中国社交情绪 (Legacy)",
    description="获取中国社交媒体（雪球、股吧等）的股票情绪（旧版接口）",
    category="social",
    is_online=True
)
def get_chinese_social_sentiment_bridge(ticker: str, curr_date: str) -> str:
    return _invoke_legacy_tool(Toolkit.get_chinese_social_sentiment, ticker=ticker, curr_date=curr_date)

# ==============================================================================
# 市场行情类 (Market)
# ==============================================================================

@register_tool(
    tool_id="get_china_market_overview_legacy",
    name="中国市场概览 (Legacy)",
    description="获取中国股市主要指数行情概览（旧版接口）",
    category="market",
    is_online=True
)
def get_china_market_overview_bridge(curr_date: str) -> str:
    return _invoke_legacy_tool(Toolkit.get_china_market_overview, curr_date=curr_date)

# ==============================================================================
# 技术分析类 (Technical)
# ==============================================================================

@register_tool(
    tool_id="get_stockstats_indicators_report_legacy",
    name="技术指标报告 (Stockstats/Legacy)",
    description="生成特定技术指标的分析报告（旧版接口）",
    category="technical",
    is_online=False
)
def get_stockstats_indicators_report_bridge(symbol: str, indicator: str, curr_date: str, look_back_days: int = 30) -> str:
    return _invoke_legacy_tool(Toolkit.get_stockstats_indicators_report, symbol=symbol, indicator=indicator, curr_date=curr_date, look_back_days=look_back_days)

@register_tool(
    tool_id="get_stockstats_indicators_report_online_legacy",
    name="实时技术指标报告 (Stockstats/Online/Legacy)",
    description="生成特定技术指标的实时分析报告（旧版接口）",
    category="technical",
    is_online=True
)
def get_stockstats_indicators_report_online_bridge(symbol: str, indicator: str, curr_date: str, look_back_days: int = 30) -> str:
    return _invoke_legacy_tool(Toolkit.get_stockstats_indicators_report_online, symbol=symbol, indicator=indicator, curr_date=curr_date, look_back_days=look_back_days)

@register_tool(
    tool_id="get_yfin_data_legacy",
    name="Yahoo Finance 数据 (Legacy)",
    description="从 Yahoo Finance 获取股票价格数据（旧版接口）",
    category="market",
    is_online=False
)
def get_yfin_data_bridge(symbol: str, start_date: str, end_date: str) -> str:
    return _invoke_legacy_tool(Toolkit.get_YFin_data, symbol=symbol, start_date=start_date, end_date=end_date)

@register_tool(
    tool_id="get_yfin_data_online_legacy",
    name="Yahoo Finance 实时数据 (Legacy)",
    description="从 Yahoo Finance 获取实时股票价格数据（旧版接口）",
    category="market",
    is_online=True
)
def get_yfin_data_online_bridge(symbol: str, start_date: str, end_date: str) -> str:
    return _invoke_legacy_tool(Toolkit.get_YFin_data_online, symbol=symbol, start_date=start_date, end_date=end_date)

# ==============================================================================
# 基本面类 (Fundamentals)
# ==============================================================================

@register_tool(
    tool_id="get_finnhub_company_insider_sentiment_legacy",
    name="内部人情绪 (Finnhub/Legacy)",
    description="获取公司内部人士的交易情绪（旧版接口）",
    category="fundamentals",
    is_online=True
)
def get_finnhub_company_insider_sentiment_bridge(ticker: str, curr_date: str) -> str:
    return _invoke_legacy_tool(Toolkit.get_finnhub_company_insider_sentiment, ticker=ticker, curr_date=curr_date)

@register_tool(
    tool_id="get_finnhub_company_insider_transactions_legacy",
    name="内部人交易 (Finnhub/Legacy)",
    description="获取公司内部人士的具体交易记录（旧版接口）",
    category="fundamentals",
    is_online=True
)
def get_finnhub_company_insider_transactions_bridge(ticker: str, curr_date: str) -> str:
    return _invoke_legacy_tool(Toolkit.get_finnhub_company_insider_transactions, ticker=ticker, curr_date=curr_date)

@register_tool(
    tool_id="get_simfin_income_stmt_legacy",
    name="利润表 (SimFin/Legacy)",
    description="获取公司利润表数据（旧版接口）",
    category="fundamentals",
    is_online=False
)
def get_simfin_income_stmt_bridge(ticker: str, freq: str, curr_date: str) -> str:
    return _invoke_legacy_tool(Toolkit.get_simfin_income_stmt, ticker=ticker, freq=freq, curr_date=curr_date)

@register_tool(
    tool_id="get_simfin_balance_sheet_legacy",
    name="资产负债表 (SimFin/Legacy)",
    description="获取公司资产负债表数据（旧版接口）",
    category="fundamentals",
    is_online=False
)
def get_simfin_balance_sheet_bridge(ticker: str, freq: str, curr_date: str) -> str:
    return _invoke_legacy_tool(Toolkit.get_simfin_balance_sheet, ticker=ticker, freq=freq, curr_date=curr_date)

@register_tool(
    tool_id="get_simfin_cashflow_legacy",
    name="现金流量表 (SimFin/Legacy)",
    description="获取公司现金流量表数据（旧版接口）",
    category="fundamentals",
    is_online=False
)
def get_simfin_cashflow_bridge(ticker: str, freq: str, curr_date: str) -> str:
    return _invoke_legacy_tool(Toolkit.get_simfin_cashflow, ticker=ticker, freq=freq, curr_date=curr_date)

logger.info("✅ 已加载所有遗留工具桥接 (Legacy Bridge Loaded)")
