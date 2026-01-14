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
            ToolParameter(name="ticker", type="string", description="股票代码"),
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
    # ❌ 已删除：get_north_flow（未实现）
    # ❌ 已删除：get_margin_trading（未实现）
    # ❌ 已删除：get_limit_stats（未实现）
    # ❌ 已删除：get_index_technical（未实现）
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

