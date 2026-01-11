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
            ToolParameter(name="ticker", type="string", description="股票代码"),
            ToolParameter(name="trade_date", type="string", description="交易日期", required=False),
        ],
    ),
    "get_YFin_data_online": ToolMetadata(
        id="get_YFin_data_online",
        name="Yahoo Finance 数据（在线）",
        description="从 Yahoo Finance 获取实时股票数据",
        category=ToolCategory.MARKET,
        data_source="yfinance",
        is_online=True,
        icon="📊",
        color="#3498db",
        parameters=[
            ToolParameter(name="ticker", type="string", description="股票代码"),
        ],
    ),
    "get_YFin_data": ToolMetadata(
        id="get_YFin_data",
        name="Yahoo Finance 数据（离线）",
        description="从本地缓存获取 Yahoo Finance 股票数据",
        category=ToolCategory.MARKET,
        data_source="yfinance",
        is_online=False,
        icon="💾",
        color="#7f8c8d",
        parameters=[
            ToolParameter(name="ticker", type="string", description="股票代码"),
        ],
    ),
    "get_stockstats_indicators_report_online": ToolMetadata(
        id="get_stockstats_indicators_report_online",
        name="技术指标报告（在线）",
        description="实时计算股票技术指标（MA、MACD、RSI等）",
        category=ToolCategory.TECHNICAL,
        data_source="stockstats",
        is_online=True,
        icon="📉",
        color="#9b59b6",
        parameters=[
            ToolParameter(name="ticker", type="string", description="股票代码"),
        ],
    ),
    "get_stockstats_indicators_report": ToolMetadata(
        id="get_stockstats_indicators_report",
        name="技术指标报告（离线）",
        description="从缓存计算股票技术指标",
        category=ToolCategory.TECHNICAL,
        data_source="stockstats",
        is_online=False,
        icon="📉",
        color="#7f8c8d",
        parameters=[
            ToolParameter(name="ticker", type="string", description="股票代码"),
        ],
    ),
    
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
            ToolParameter(name="ticker", type="string", description="股票代码"),
        ],
    ),
    "get_finnhub_company_insider_sentiment": ToolMetadata(
        id="get_finnhub_company_insider_sentiment",
        name="内部人情绪",
        description="获取公司内部人交易情绪数据",
        category=ToolCategory.FUNDAMENTALS,
        data_source="finnhub",
        is_online=False,
        icon="👔",
        color="#e67e22",
        parameters=[
            ToolParameter(name="ticker", type="string", description="股票代码"),
        ],
    ),
    "get_finnhub_company_insider_transactions": ToolMetadata(
        id="get_finnhub_company_insider_transactions",
        name="内部人交易",
        description="获取公司内部人交易记录",
        category=ToolCategory.FUNDAMENTALS,
        data_source="finnhub",
        is_online=False,
        icon="💼",
        color="#e74c3c",
        parameters=[
            ToolParameter(name="ticker", type="string", description="股票代码"),
        ],
    ),
    "get_simfin_balance_sheet": ToolMetadata(
        id="get_simfin_balance_sheet",
        name="资产负债表",
        description="获取公司资产负债表数据",
        category=ToolCategory.FUNDAMENTALS,
        data_source="simfin",
        is_online=False,
        icon="📋",
        color="#1abc9c",
        parameters=[
            ToolParameter(name="ticker", type="string", description="股票代码"),
        ],
    ),
    "get_simfin_cashflow": ToolMetadata(
        id="get_simfin_cashflow",
        name="现金流量表",
        description="获取公司现金流量表数据",
        category=ToolCategory.FUNDAMENTALS,
        data_source="simfin",
        is_online=False,
        icon="💰",
        color="#f1c40f",
        parameters=[
            ToolParameter(name="ticker", type="string", description="股票代码"),
        ],
    ),
    "get_simfin_income_stmt": ToolMetadata(
        id="get_simfin_income_stmt",
        name="利润表",
        description="获取公司利润表数据",
        category=ToolCategory.FUNDAMENTALS,
        data_source="simfin",
        is_online=False,
        icon="📈",
        color="#27ae60",
        parameters=[
            ToolParameter(name="ticker", type="string", description="股票代码"),
        ],
    ),

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
            ToolParameter(name="ticker", type="string", description="股票代码"),
        ],
    ),
    "get_global_news_openai": ToolMetadata(
        id="get_global_news_openai",
        name="全球新闻（AI增强）",
        description="获取全球财经新闻并用AI增强分析",
        category=ToolCategory.NEWS,
        data_source="openai",
        is_online=True,
        icon="🌍",
        color="#3498db",
        parameters=[
            ToolParameter(name="query", type="string", description="搜索关键词"),
        ],
    ),
    "get_google_news": ToolMetadata(
        id="get_google_news",
        name="Google 新闻",
        description="从 Google News 获取相关新闻",
        category=ToolCategory.NEWS,
        data_source="google",
        is_online=True,
        icon="🔍",
        color="#4285f4",
        parameters=[
            ToolParameter(name="query", type="string", description="搜索关键词"),
        ],
    ),
    "get_finnhub_news": ToolMetadata(
        id="get_finnhub_news",
        name="Finnhub 新闻",
        description="从 Finnhub 获取公司新闻",
        category=ToolCategory.NEWS,
        data_source="finnhub",
        is_online=False,
        icon="📄",
        color="#7f8c8d",
        parameters=[
            ToolParameter(name="ticker", type="string", description="股票代码"),
        ],
    ),
    "get_reddit_news": ToolMetadata(
        id="get_reddit_news",
        name="Reddit 新闻",
        description="从 Reddit 获取股票相关讨论",
        category=ToolCategory.NEWS,
        data_source="reddit",
        is_online=False,
        icon="🔴",
        color="#ff4500",
        parameters=[
            ToolParameter(name="ticker", type="string", description="股票代码"),
        ],
    ),

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
            ToolParameter(name="ticker", type="string", description="股票代码"),
        ],
    ),
    "get_stock_news_openai": ToolMetadata(
        id="get_stock_news_openai",
        name="AI 新闻分析",
        description="使用 AI 分析股票新闻情绪",
        category=ToolCategory.SOCIAL,
        data_source="openai",
        is_online=True,
        icon="🤖",
        color="#10a37f",
        parameters=[
            ToolParameter(name="ticker", type="string", description="股票代码"),
        ],
    ),
    "get_reddit_stock_info": ToolMetadata(
        id="get_reddit_stock_info",
        name="Reddit 股票讨论",
        description="获取 Reddit 上的股票讨论和情绪",
        category=ToolCategory.SOCIAL,
        data_source="reddit",
        is_online=False,
        icon="🔴",
        color="#ff4500",
        parameters=[
            ToolParameter(name="ticker", type="string", description="股票代码"),
        ],
    ),

    # === 中国市场工具 ===
    "get_china_stock_data": ToolMetadata(
        id="get_china_stock_data",
        name="中国股票数据",
        description="获取 A股/港股 市场数据",
        category=ToolCategory.CHINA,
        data_source="tushare/akshare",
        is_online=True,
        icon="🇨🇳",
        color="#de2910",
        parameters=[
            ToolParameter(name="ticker", type="string", description="股票代码（如 600519.SH）"),
        ],
    ),
    "get_china_fundamentals": ToolMetadata(
        id="get_china_fundamentals",
        name="中国公司基本面",
        description="获取中国上市公司基本面数据",
        category=ToolCategory.CHINA,
        data_source="tushare",
        is_online=True,
        icon="📊",
        color="#de2910",
        parameters=[
            ToolParameter(name="ticker", type="string", description="股票代码"),
        ],
    ),
    "get_sector_performance": ToolMetadata(
        id="get_sector_performance",
        name="板块表现",
        description="获取行业板块表现数据",
        category=ToolCategory.MARKET,
        data_source="tushare/yfinance",
        is_online=True,
        icon="🏭",
        color="#f39c12",
        parameters=[
            ToolParameter(name="sector", type="string", description="板块名称", required=False),
        ],
    ),
    "get_industry_comparison": ToolMetadata(
        id="get_industry_comparison",
        name="行业对比",
        description="对比同行业公司表现",
        category=ToolCategory.MARKET,
        data_source="yfinance",
        is_online=True,
        icon="📊",
        color="#e67e22",
        parameters=[
            ToolParameter(name="ticker", type="string", description="股票代码"),
        ],
    ),
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
            ToolParameter(name="trade_date", type="string", description="交易日期", required=True),
            ToolParameter(name="lookback_days", type="integer", description="回看天数", required=False),
        ],
    ),
    "get_market_overview": ToolMetadata(
        id="get_market_overview",
        name="市场概览",
        description="获取整体市场环境概览",
        category=ToolCategory.MARKET,
        data_source="multiple",
        is_online=True,
        icon="🌍",
        color="#3498db",
        parameters=[],
    ),
    # 新增大盘分析工具
    "get_north_flow": ToolMetadata(
        id="get_north_flow",
        name="北向资金流向",
        description="获取沪深港通北向资金流向数据",
        category=ToolCategory.MARKET,
        data_source="tushare",
        is_online=True,
        icon="💰",
        color="#e74c3c",
        parameters=[
            ToolParameter(name="trade_date", type="string", description="交易日期", required=True),
            ToolParameter(name="lookback_days", type="integer", description="回看天数", required=False),
        ],
    ),
    "get_margin_trading": ToolMetadata(
        id="get_margin_trading",
        name="两融余额",
        description="获取融资融券余额数据",
        category=ToolCategory.MARKET,
        data_source="tushare",
        is_online=True,
        icon="📊",
        color="#9b59b6",
        parameters=[
            ToolParameter(name="trade_date", type="string", description="交易日期", required=True),
            ToolParameter(name="lookback_days", type="integer", description="回看天数", required=False),
        ],
    ),
    "get_limit_stats": ToolMetadata(
        id="get_limit_stats",
        name="涨跌停统计",
        description="获取涨跌停家数和涨跌家数统计",
        category=ToolCategory.MARKET,
        data_source="tushare",
        is_online=True,
        icon="📈",
        color="#f39c12",
        parameters=[
            ToolParameter(name="trade_date", type="string", description="交易日期", required=True),
        ],
    ),
    "get_index_technical": ToolMetadata(
        id="get_index_technical",
        name="指数技术指标",
        description="获取指数技术指标（MACD、RSI、KDJ）",
        category=ToolCategory.MARKET,
        data_source="tushare",
        is_online=True,
        icon="📉",
        color="#27ae60",
        parameters=[
            ToolParameter(name="trade_date", type="string", description="交易日期", required=True),
            ToolParameter(name="lookback_days", type="integer", description="回看天数", required=False),
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
            ToolParameter(name="trade_date", type="string", description="交易日期", required=True),
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
}

