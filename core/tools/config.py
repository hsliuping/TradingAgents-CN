"""
工具配置和元数据定义
"""

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ToolCategory(str, Enum):
    """工具类别"""
    MARKET = "market"           # 市场数据
    FUNDAMENTALS = "fundamentals"  # 基本面数据
    NEWS = "news"               # 新闻数据
    SOCIAL = "social"           # 社交媒体数据
    TECHNICAL = "technical"     # 技术分析
    CHINA = "china"             # 中国市场数据
    TRADE_REVIEW = "trade_review"  # 交易复盘


class ToolParameter(BaseModel):
    """工具参数定义"""
    name: str
    type: str  # string, number, boolean, array, object
    description: str
    required: bool = True
    default: Optional[Any] = None
    enum: Optional[List[Any]] = None  # 可选值列表


class ToolMetadata(BaseModel):
    """工具元数据"""
    id: str                           # 工具唯一标识
    name: str                         # 显示名称
    description: str                  # 描述
    category: ToolCategory            # 工具类别
    
    # 参数定义
    parameters: List[ToolParameter] = Field(default_factory=list)
    
    # 数据源信息
    data_source: str = ""             # 数据来源
    is_online: bool = True            # 是否需要在线访问
    
    # 配置
    timeout: int = 30                 # 超时时间（秒）
    rate_limit: Optional[int] = None  # 频率限制（每分钟调用次数）
    
    # 显示
    icon: str = "🔧"
    color: str = "#95a5a6"
    
    class Config:
        use_enum_values = True


# 内置工具元数据
BUILTIN_TOOLS: Dict[str, ToolMetadata] = {
    # === 市场数据工具 ===
    "get_stock_market_data_unified": ToolMetadata(
        id="get_stock_market_data_unified",
        name="统一市场数据",
        description="获取股票市场数据（价格、成交量、技术指标）的统一接口",
        category=ToolCategory.MARKET,
        data_source="yfinance/tushare",
        is_online=True,
        icon="📈",
        color="#2ecc71",
        parameters=[
            ToolParameter(name="ticker", type="string", description="股票代码（支持A股、港股、美股）", required=True),
            ToolParameter(name="start_date", type="string", description="开始日期，格式：YYYY-MM-DD。注意：系统会自动扩展到配置的回溯天数（通常为365天），你只需要传递分析日期即可", required=True),
            ToolParameter(name="end_date", type="string", description="结束日期，格式：YYYY-MM-DD。通常与start_date相同，传递当前分析日期即可", required=True),
        ],
    ),
    # ❌ 已删除：get_YFin_data_online（未实现，使用 get_yfin_data_online_legacy）
    # ❌ 已删除：get_YFin_data（未实现，使用 get_yfin_data_legacy）
    # ❌ 已删除：get_stockstats_indicators_report_online（未实现，使用 get_stockstats_indicators_report_online_legacy）
    # ❌ 已删除：get_stockstats_indicators_report（未实现，使用 get_stockstats_indicators_report_legacy）
    
    # === 基本面数据工具 ===
    "get_stock_fundamentals_unified": ToolMetadata(
        id="get_stock_fundamentals_unified",
        name="统一基本面数据",
        description="获取公司基本面数据的统一接口",
        category=ToolCategory.FUNDAMENTALS,
        data_source="finnhub/simfin",
        is_online=True,
        icon="📊",
        color="#3498db",
        parameters=[
            ToolParameter(name="ticker", type="string", description="股票代码（支持A股、港股、美股）", required=True),
            ToolParameter(name="start_date", type="string", description="开始日期，格式：YYYY-MM-DD", required=False),
            ToolParameter(name="end_date", type="string", description="结束日期，格式：YYYY-MM-DD", required=False),
            ToolParameter(name="curr_date", type="string", description="当前日期，格式：YYYY-MM-DD", required=False),
        ],
    ),
    # ❌ 已删除：get_finnhub_company_insider_sentiment（未实现，使用 get_finnhub_company_insider_sentiment_legacy）
    # ❌ 已删除：get_finnhub_company_insider_transactions（未实现，使用 get_finnhub_company_insider_transactions_legacy）
    # ❌ 已删除：get_simfin_balance_sheet（未实现，使用 get_simfin_balance_sheet_legacy）
    # ❌ 已删除：get_simfin_cashflow（未实现，使用 get_simfin_cashflow_legacy）
    # ❌ 已删除：get_simfin_income_stmt（未实现，使用 get_simfin_income_stmt_legacy）

    # === 新闻数据工具 ===
    "get_stock_news_unified": ToolMetadata(
        id="get_stock_news_unified",
        name="统一新闻数据",
        description="获取股票相关新闻的统一接口",
        category=ToolCategory.NEWS,
        data_source="finnhub/google",
        is_online=True,
        icon="📰",
        color="#9b59b6",
        parameters=[
            ToolParameter(name="ticker", type="string", description="股票代码（支持A股、港股、美股）", required=True),
            ToolParameter(name="curr_date", type="string", description="当前日期，格式：YYYY-MM-DD", required=True),
        ],
    ),
    # ❌ 已删除：get_global_news_openai（未实现，使用 get_global_news_openai_legacy）
    # ❌ 已删除：get_google_news（未实现，使用 get_google_news_legacy）
    # ❌ 已删除：get_finnhub_news（未实现，使用 get_finnhub_news_legacy）
    # ❌ 已删除：get_reddit_news（未实现，使用 get_reddit_news_legacy）

    # === 社交媒体工具 ===
    "get_stock_sentiment_unified": ToolMetadata(
        id="get_stock_sentiment_unified",
        name="统一情绪分析",
        description="获取股票社交媒体情绪的统一接口",
        category=ToolCategory.SOCIAL,
        data_source="reddit/twitter",
        is_online=True,
        icon="💬",
        color="#e74c3c",
        parameters=[
            ToolParameter(name="ticker", type="string", description="股票代码（支持A股、港股、美股）", required=True),
            ToolParameter(name="curr_date", type="string", description="当前日期，格式：YYYY-MM-DD", required=True),
        ],
    ),
    # ❌ 已删除：get_stock_news_openai（未实现，使用 get_stock_news_openai_legacy）
    # ❌ 已删除：get_reddit_stock_info（未实现，使用 get_reddit_stock_info_legacy）

    # === 中国市场工具 ===
    # ❌ 已删除：get_china_stock_data（未实现，请使用 get_stock_market_data_unified）
    # ❌ 已删除：get_china_fundamentals（未实现，请使用 get_stock_fundamentals_unified）
    # ❌ 已删除：get_sector_performance（未实现，使用 get_sector_data 代替）
    # ❌ 已删除：get_industry_comparison（未实现，使用 get_peer_comparison 代替）
    "get_index_data": ToolMetadata(
        id="get_index_data",
        name="指数数据",
        description="获取主要指数数据（上证、深证、创业板等）和均线走势",
        category=ToolCategory.MARKET,
        data_source="tushare",
        is_online=True,
        icon="📈",
        color="#1abc9c",
        parameters=[
            ToolParameter(name="trade_date", type="string", description="交易日期，格式：YYYY-MM-DD", required=True),
            ToolParameter(name="lookback_days", type="integer", description="回看天数，默认60天", required=False, default=60),
        ],
    ),
    "get_market_overview": ToolMetadata(
        id="get_market_overview",
        name="市场概览",
        description="获取整体市场环境概览，包括指数走势、涨跌统计、资金流向等综合数据",
        category=ToolCategory.MARKET,
        data_source="multiple",
        is_online=True,
        icon="🌍",
        color="#3498db",
        parameters=[
            ToolParameter(name="trade_date", type="string", description="交易日期，格式：YYYY-MM-DD", required=True),
        ],
    ),
    # 新增大盘分析工具
    "get_north_flow": ToolMetadata(
        id="get_north_flow",
        name="北向资金流向",
        description="获取沪深港通北向资金流向数据，分析外资动向",
        category=ToolCategory.MARKET,
        data_source="tushare",
        is_online=True,
        icon="💰",
        color="#3498db",
        parameters=[
            ToolParameter(name="trade_date", type="string", description="交易日期，格式：YYYY-MM-DD", required=True),
            ToolParameter(name="lookback_days", type="integer", description="回看天数，默认10天", required=False, default=10),
        ],
    ),
    "get_margin_trading": ToolMetadata(
        id="get_margin_trading",
        name="两融余额",
        description="获取融资融券余额数据，分析杠杆资金动向",
        category=ToolCategory.MARKET,
        data_source="tushare",
        is_online=True,
        icon="📊",
        color="#3498db",
        parameters=[
            ToolParameter(name="trade_date", type="string", description="交易日期，格式：YYYY-MM-DD", required=True),
            ToolParameter(name="lookback_days", type="integer", description="回看天数，默认10天", required=False, default=10),
        ],
    ),
    "get_limit_stats": ToolMetadata(
        id="get_limit_stats",
        name="涨跌停统计",
        description="获取涨跌停家数和涨跌家数统计，评估市场情绪",
        category=ToolCategory.MARKET,
        data_source="tushare",
        is_online=True,
        icon="📈",
        color="#3498db",
        parameters=[
            ToolParameter(name="trade_date", type="string", description="交易日期，格式：YYYY-MM-DD", required=True),
        ],
    ),
    "get_index_technical": ToolMetadata(
        id="get_index_technical",
        name="指数技术指标",
        description="获取指数技术指标（MACD、RSI、KDJ），分析技术面走势",
        category=ToolCategory.MARKET,
        data_source="tushare",
        is_online=True,
        icon="📉",
        color="#3498db",
        parameters=[
            ToolParameter(name="trade_date", type="string", description="交易日期，格式：YYYY-MM-DD", required=True),
            ToolParameter(name="lookback_days", type="integer", description="回看天数，默认60天", required=False, default=60),
        ],
    ),
    "get_market_breadth": ToolMetadata(
        id="get_market_breadth",
        name="市场宽度",
        description="分析市场宽度（成交量、市值等）",
        category=ToolCategory.MARKET,
        data_source="tushare",
        is_online=True,
        icon="📊",
        color="#3498db",
        parameters=[
            ToolParameter(name="trade_date", type="string", description="交易日期，格式：YYYY-MM-DD", required=True),
        ],
    ),
    "get_market_environment": ToolMetadata(
        id="get_market_environment",
        name="市场环境",
        description="综合评估市场环境（估值、波动率等）",
        category=ToolCategory.MARKET,
        data_source="tushare",
        is_online=True,
        icon="🌐",
        color="#1abc9c",
        parameters=[
            ToolParameter(name="trade_date", type="string", description="交易日期", required=True),
        ],
    ),
    "identify_market_cycle": ToolMetadata(
        id="identify_market_cycle",
        name="市场周期识别",
        description="识别当前市场所处的周期阶段",
        category=ToolCategory.MARKET,
        data_source="tushare",
        is_online=True,
        icon="🔄",
        color="#e67e22",
        parameters=[
            ToolParameter(name="trade_date", type="string", description="交易日期", required=True),
        ],
    ),
    
    # === 板块分析工具 ===
    "get_sector_data": ToolMetadata(
        id="get_sector_data",
        name="板块数据",
        description="获取股票所属板块的表现数据，分析行业趋势",
        category=ToolCategory.MARKET,
        data_source="tushare",
        is_online=True,
        icon="📊",
        color="#3498db",
        parameters=[
            ToolParameter(name="ticker", type="string", description="股票代码（如 000001 或 000001.SZ）", required=True),
            ToolParameter(name="trade_date", type="string", description="交易日期，格式：YYYY-MM-DD", required=True),
            ToolParameter(name="lookback_days", type="integer", description="回看天数，默认20天", required=False, default=20),
        ],
    ),
    "get_fund_flow_data": ToolMetadata(
        id="get_fund_flow_data",
        name="资金流向",
        description="获取板块资金流向数据，分析主力资金动向",
        category=ToolCategory.MARKET,
        data_source="tushare",
        is_online=True,
        icon="💰",
        color="#3498db",
        parameters=[
            ToolParameter(name="trade_date", type="string", description="交易日期，格式：YYYY-MM-DD", required=True),
            ToolParameter(name="top_n", type="integer", description="返回前N个板块，默认10", required=False, default=10),
        ],
    ),
    "get_peer_comparison": ToolMetadata(
        id="get_peer_comparison",
        name="同业对比",
        description="获取同行业股票对比数据，分析个股在行业中的位置",
        category=ToolCategory.MARKET,
        data_source="tushare",
        is_online=True,
        icon="📈",
        color="#3498db",
        parameters=[
            ToolParameter(name="ticker", type="string", description="股票代码（如 000001 或 000001.SZ）", required=True),
            ToolParameter(name="trade_date", type="string", description="交易日期，格式：YYYY-MM-DD", required=True),
            ToolParameter(name="top_n", type="integer", description="返回前N个同业股票，默认10", required=False, default=10),
        ],
    ),
    "analyze_sector": ToolMetadata(
        id="analyze_sector",
        name="综合板块分析",
        description="综合分析股票所属板块，包括表现、轮动、同业对比等",
        category=ToolCategory.MARKET,
        data_source="tushare",
        is_online=True,
        icon="🔍",
        color="#3498db",
        parameters=[
            ToolParameter(name="ticker", type="string", description="股票代码（如 000001 或 000001.SZ）", required=True),
            ToolParameter(name="trade_date", type="string", description="交易日期，格式：YYYY-MM-DD", required=True),
        ],
    ),
    
    # === 技术指标工具 ===
    "get_technical_indicators": ToolMetadata(
        id="get_technical_indicators",
        name="统一技术指标分析",
        description="获取股票的各类技术指标（MACD, RSI, KDJ, BOLL等），支持A股/港股/美股",
        category=ToolCategory.TECHNICAL,
        data_source="multiple",
        is_online=True,
        icon="📉",
        color="#e74c3c",
        parameters=[
            ToolParameter(name="ticker", type="string", description="股票代码（支持A股、港股、美股）", required=True),
            ToolParameter(name="indicators", type="string", description="技术指标列表，用逗号分隔，如 'macd,rsi_14,boll,kdj'", required=True),
            ToolParameter(name="start_date", type="string", description="开始日期，格式：YYYY-MM-DD。通常为分析日期的前一年，以确保有足够数据计算指标", required=False),
            ToolParameter(name="end_date", type="string", description="结束日期，格式：YYYY-MM-DD。通常为分析日期", required=False),
        ],
    ),
    
    # === 中国市场工具 ===
    "get_china_market_overview": ToolMetadata(
        id="get_china_market_overview",
        name="中国市场概览",
        description="获取中国股市主要指数行情概览（上证、深证、创业板、科创50）",
        category=ToolCategory.CHINA,
        data_source="tushare",
        is_online=True,
        icon="🇨🇳",
        color="#e74c3c",
        parameters=[
            ToolParameter(name="curr_date", type="string", description="当前日期，格式：YYYY-MM-DD", required=True),
        ],
    ),
    
    # === 交易复盘工具 ===
    "get_trade_records": ToolMetadata(
        id="get_trade_records",
        name="获取交易记录",
        description="从数据库获取交易记录，支持用户持仓(position_changes)和模拟交易(paper_trades)",
        category=ToolCategory.TRADE_REVIEW,
        data_source="database",
        is_online=False,
        icon="📋",
        color="#95a5a6",
        parameters=[
            ToolParameter(name="user_id", type="string", description="用户ID", required=True),
            ToolParameter(name="trade_ids", type="array", description="交易ID列表", required=True),
            ToolParameter(name="source", type="string", description="数据源: 'real'(用户持仓) 或 'paper'(模拟交易)", required=False, default="real"),
        ],
    ),
    "build_trade_info": ToolMetadata(
        id="build_trade_info",
        name="构建交易信息",
        description="从交易记录构建完整的交易信息对象，包含统计数据和时间信息",
        category=ToolCategory.TRADE_REVIEW,
        data_source="internal",
        is_online=False,
        icon="🔧",
        color="#95a5a6",
        parameters=[
            ToolParameter(name="trade_records", type="array", description="交易记录列表", required=True),
            ToolParameter(name="code", type="string", description="股票代码（可选）", required=False),
        ],
    ),
    "get_account_info": ToolMetadata(
        id="get_account_info",
        name="获取账户信息",
        description="获取用户的资金账户信息，包括现金、持仓市值、总资产等",
        category=ToolCategory.TRADE_REVIEW,
        data_source="database",
        is_online=False,
        icon="💳",
        color="#95a5a6",
        parameters=[
            ToolParameter(name="user_id", type="string", description="用户ID", required=True),
        ],
    ),
    "get_market_snapshot_for_review": ToolMetadata(
        id="get_market_snapshot_for_review",
        name="获取市场快照",
        description="获取交易期间的K线数据和市场快照，用于复盘分析",
        category=ToolCategory.TRADE_REVIEW,
        data_source="multiple",
        is_online=True,
        icon="📸",
        color="#95a5a6",
        parameters=[
            ToolParameter(name="code", type="string", description="股票代码", required=True),
            ToolParameter(name="market", type="string", description="市场: 'CN'(A股) 或 'US'(美股)", required=True),
            ToolParameter(name="start_date", type="string", description="开始日期 YYYY-MM-DD", required=False),
            ToolParameter(name="end_date", type="string", description="结束日期 YYYY-MM-DD", required=False),
        ],
    ),
    
    # === Legacy 工具（兼容旧版接口）===
    # 新闻类
    "get_reddit_news_legacy": ToolMetadata(
        id="get_reddit_news_legacy",
        name="Reddit 全球新闻 (Legacy)",
        description="获取 Reddit 上的全球新闻聚合（旧版接口）",
        category=ToolCategory.NEWS,
        data_source="reddit",
        is_online=True,
        icon="📰",
        color="#9b59b6",
        parameters=[
            ToolParameter(name="curr_date", type="string", description="当前日期，格式：YYYY-MM-DD", required=True),
        ],
    ),
    "get_finnhub_news_legacy": ToolMetadata(
        id="get_finnhub_news_legacy",
        name="Finnhub 财经新闻 (Legacy)",
        description="从 Finnhub 获取特定股票的新闻（旧版接口）",
        category=ToolCategory.NEWS,
        data_source="finnhub",
        is_online=True,
        icon="📰",
        color="#9b59b6",
        parameters=[
            ToolParameter(name="ticker", type="string", description="股票代码", required=True),
            ToolParameter(name="start_date", type="string", description="开始日期，格式：YYYY-MM-DD", required=True),
            ToolParameter(name="end_date", type="string", description="结束日期，格式：YYYY-MM-DD", required=True),
        ],
    ),
    "get_google_news_legacy": ToolMetadata(
        id="get_google_news_legacy",
        name="Google 新闻搜索 (Legacy)",
        description="通过 Google News 搜索特定关键词的新闻（旧版接口）",
        category=ToolCategory.NEWS,
        data_source="google",
        is_online=True,
        icon="📰",
        color="#9b59b6",
        parameters=[
            ToolParameter(name="query", type="string", description="搜索关键词", required=True),
            ToolParameter(name="curr_date", type="string", description="当前日期，格式：YYYY-MM-DD", required=True),
        ],
    ),
    "get_realtime_stock_news_legacy": ToolMetadata(
        id="get_realtime_stock_news_legacy",
        name="实时股票新闻 (Legacy)",
        description="获取股票的实时新闻分析（旧版接口）",
        category=ToolCategory.NEWS,
        data_source="multiple",
        is_online=True,
        icon="📰",
        color="#9b59b6",
        parameters=[
            ToolParameter(name="ticker", type="string", description="股票代码", required=True),
            ToolParameter(name="curr_date", type="string", description="当前日期，格式：YYYY-MM-DD", required=True),
        ],
    ),
    "get_stock_news_openai_legacy": ToolMetadata(
        id="get_stock_news_openai_legacy",
        name="OpenAI 股票新闻分析 (Legacy)",
        description="使用 OpenAI 接口获取并分析股票新闻（旧版接口）",
        category=ToolCategory.NEWS,
        data_source="openai",
        is_online=True,
        icon="📰",
        color="#9b59b6",
        parameters=[
            ToolParameter(name="ticker", type="string", description="股票代码", required=True),
            ToolParameter(name="curr_date", type="string", description="当前日期，格式：YYYY-MM-DD", required=True),
        ],
    ),
    "get_global_news_openai_legacy": ToolMetadata(
        id="get_global_news_openai_legacy",
        name="OpenAI 宏观新闻分析 (Legacy)",
        description="使用 OpenAI 接口获取并分析宏观经济新闻（旧版接口）",
        category=ToolCategory.NEWS,
        data_source="openai",
        is_online=True,
        icon="📰",
        color="#9b59b6",
        parameters=[
            ToolParameter(name="curr_date", type="string", description="当前日期，格式：YYYY-MM-DD", required=True),
        ],
    ),
    
    # 社交情绪类
    "get_reddit_stock_info_legacy": ToolMetadata(
        id="get_reddit_stock_info_legacy",
        name="Reddit 股票讨论 (Legacy)",
        description="获取 Reddit 上关于特定股票的讨论信息（旧版接口）",
        category=ToolCategory.SOCIAL,
        data_source="reddit",
        is_online=True,
        icon="💬",
        color="#e74c3c",
        parameters=[
            ToolParameter(name="ticker", type="string", description="股票代码", required=True),
            ToolParameter(name="curr_date", type="string", description="当前日期，格式：YYYY-MM-DD", required=True),
        ],
    ),
    "get_chinese_social_sentiment_legacy": ToolMetadata(
        id="get_chinese_social_sentiment_legacy",
        name="中国社交情绪 (Legacy)",
        description="获取中国社交媒体（雪球、股吧等）的股票情绪（旧版接口）",
        category=ToolCategory.SOCIAL,
        data_source="chinese_social",
        is_online=True,
        icon="💬",
        color="#e74c3c",
        parameters=[
            ToolParameter(name="ticker", type="string", description="股票代码", required=True),
            ToolParameter(name="curr_date", type="string", description="当前日期，格式：YYYY-MM-DD", required=True),
        ],
    ),
    
    # 市场行情类
    "get_china_market_overview_legacy": ToolMetadata(
        id="get_china_market_overview_legacy",
        name="中国市场概览 (Legacy)",
        description="获取中国股市主要指数行情概览（旧版接口）",
        category=ToolCategory.MARKET,
        data_source="tushare",
        is_online=True,
        icon="📈",
        color="#2ecc71",
        parameters=[
            ToolParameter(name="curr_date", type="string", description="当前日期，格式：YYYY-MM-DD", required=True),
        ],
    ),
    "get_yfin_data_legacy": ToolMetadata(
        id="get_yfin_data_legacy",
        name="Yahoo Finance 数据 (Legacy)",
        description="从 Yahoo Finance 获取股票价格数据（旧版接口）",
        category=ToolCategory.MARKET,
        data_source="yfinance",
        is_online=False,
        icon="📈",
        color="#2ecc71",
        parameters=[
            ToolParameter(name="symbol", type="string", description="股票代码", required=True),
            ToolParameter(name="start_date", type="string", description="开始日期，格式：YYYY-MM-DD", required=True),
            ToolParameter(name="end_date", type="string", description="结束日期，格式：YYYY-MM-DD", required=True),
        ],
    ),
    "get_yfin_data_online_legacy": ToolMetadata(
        id="get_yfin_data_online_legacy",
        name="Yahoo Finance 实时数据 (Legacy)",
        description="从 Yahoo Finance 获取实时股票价格数据（旧版接口）",
        category=ToolCategory.MARKET,
        data_source="yfinance",
        is_online=True,
        icon="📈",
        color="#2ecc71",
        parameters=[
            ToolParameter(name="symbol", type="string", description="股票代码", required=True),
            ToolParameter(name="start_date", type="string", description="开始日期，格式：YYYY-MM-DD", required=True),
            ToolParameter(name="end_date", type="string", description="结束日期，格式：YYYY-MM-DD", required=True),
        ],
    ),
    
    # 技术分析类
    "get_stockstats_indicators_report_legacy": ToolMetadata(
        id="get_stockstats_indicators_report_legacy",
        name="技术指标报告 (Stockstats/Legacy)",
        description="生成特定技术指标的分析报告（旧版接口）",
        category=ToolCategory.TECHNICAL,
        data_source="stockstats",
        is_online=False,
        icon="📉",
        color="#e74c3c",
        parameters=[
            ToolParameter(name="symbol", type="string", description="股票代码", required=True),
            ToolParameter(name="indicator", type="string", description="技术指标名称", required=True),
            ToolParameter(name="curr_date", type="string", description="当前日期，格式：YYYY-MM-DD", required=True),
            ToolParameter(name="look_back_days", type="integer", description="回看天数，默认30天", required=False, default=30),
        ],
    ),
    "get_stockstats_indicators_report_online_legacy": ToolMetadata(
        id="get_stockstats_indicators_report_online_legacy",
        name="实时技术指标报告 (Stockstats/Online/Legacy)",
        description="生成特定技术指标的实时分析报告（旧版接口）",
        category=ToolCategory.TECHNICAL,
        data_source="stockstats",
        is_online=True,
        icon="📉",
        color="#e74c3c",
        parameters=[
            ToolParameter(name="symbol", type="string", description="股票代码", required=True),
            ToolParameter(name="indicator", type="string", description="技术指标名称", required=True),
            ToolParameter(name="curr_date", type="string", description="当前日期，格式：YYYY-MM-DD", required=True),
            ToolParameter(name="look_back_days", type="integer", description="回看天数，默认30天", required=False, default=30),
        ],
    ),
    
    # 基本面类
    "get_finnhub_company_insider_sentiment_legacy": ToolMetadata(
        id="get_finnhub_company_insider_sentiment_legacy",
        name="内部人情绪 (Finnhub/Legacy)",
        description="获取公司内部人士的交易情绪（旧版接口）",
        category=ToolCategory.FUNDAMENTALS,
        data_source="finnhub",
        is_online=True,
        icon="📊",
        color="#3498db",
        parameters=[
            ToolParameter(name="ticker", type="string", description="股票代码", required=True),
            ToolParameter(name="curr_date", type="string", description="当前日期，格式：YYYY-MM-DD", required=True),
        ],
    ),
    "get_finnhub_company_insider_transactions_legacy": ToolMetadata(
        id="get_finnhub_company_insider_transactions_legacy",
        name="内部人交易 (Finnhub/Legacy)",
        description="获取公司内部人士的具体交易记录（旧版接口）",
        category=ToolCategory.FUNDAMENTALS,
        data_source="finnhub",
        is_online=True,
        icon="📊",
        color="#3498db",
        parameters=[
            ToolParameter(name="ticker", type="string", description="股票代码", required=True),
            ToolParameter(name="curr_date", type="string", description="当前日期，格式：YYYY-MM-DD", required=True),
        ],
    ),
    "get_simfin_income_stmt_legacy": ToolMetadata(
        id="get_simfin_income_stmt_legacy",
        name="利润表 (SimFin/Legacy)",
        description="获取公司利润表数据（旧版接口）",
        category=ToolCategory.FUNDAMENTALS,
        data_source="simfin",
        is_online=False,
        icon="📊",
        color="#3498db",
        parameters=[
            ToolParameter(name="ticker", type="string", description="股票代码", required=True),
            ToolParameter(name="freq", type="string", description="频率: 'Q'(季度) 或 'A'(年度)", required=True),
            ToolParameter(name="curr_date", type="string", description="当前日期，格式：YYYY-MM-DD", required=True),
        ],
    ),
    "get_simfin_balance_sheet_legacy": ToolMetadata(
        id="get_simfin_balance_sheet_legacy",
        name="资产负债表 (SimFin/Legacy)",
        description="获取公司资产负债表数据（旧版接口）",
        category=ToolCategory.FUNDAMENTALS,
        data_source="simfin",
        is_online=False,
        icon="📊",
        color="#3498db",
        parameters=[
            ToolParameter(name="ticker", type="string", description="股票代码", required=True),
            ToolParameter(name="freq", type="string", description="频率: 'Q'(季度) 或 'A'(年度)", required=True),
            ToolParameter(name="curr_date", type="string", description="当前日期，格式：YYYY-MM-DD", required=True),
        ],
    ),
    "get_simfin_cashflow_legacy": ToolMetadata(
        id="get_simfin_cashflow_legacy",
        name="现金流量表 (SimFin/Legacy)",
        description="获取公司现金流量表数据（旧版接口）",
        category=ToolCategory.FUNDAMENTALS,
        data_source="simfin",
        is_online=False,
        icon="📊",
        color="#3498db",
        parameters=[
            ToolParameter(name="ticker", type="string", description="股票代码", required=True),
            ToolParameter(name="freq", type="string", description="频率: 'Q'(季度) 或 'A'(年度)", required=True),
            ToolParameter(name="curr_date", type="string", description="当前日期，格式：YYYY-MM-DD", required=True),
        ],
    ),
}

