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
    UTILITY = "utility"         # 通用工具（Skill 扩展）
    KNOWLEDGE = "knowledge"     # 知识型（Skill 扩展）


class ToolParameter(BaseModel):
    """工具参数定义"""
    name: str
    type: str  # string, number, boolean, array, object
    description: str
    required: bool = True
    default: Optional[Any] = None
    enum: Optional[List[Any]] = None  # 可选值列表


class ToolMetadata(BaseModel):
    """工具元数据（与 Skill 元数据对齐，支持 Function Calling）"""
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
    
    # Function Calling 增强字段（与 Skill 对齐）
    when_to_use: str = ""             # 何时使用此工具
    when_not_to_use: str = ""         # 不应使用的场景
    returns: str = ""                 # 返回值描述
    example: str = ""                 # 调用示例
    related_tools: List[str] = Field(default_factory=list)  # 相关工具
    limitations: str = ""             # 限制说明
    fc_enabled: bool = True           # 是否启用 Function Calling
    
    class Config:
        use_enum_values = True


# 内置工具元数据
BUILTIN_TOOLS: Dict[str, ToolMetadata] = {
    # === 市场数据工具 ===
    "get_stock_market_data_unified": ToolMetadata(
        id="get_stock_market_data_unified",
        name="统一市场数据",
        description="获取股票的历史行情数据，包括开盘价、收盘价、最高价、最低价、成交量等。数据可扩展为包含技术指标。支持A股、港股、美股。",
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
        when_to_use="当需要分析股票价格走势、成交量、历史K线数据时使用。用户询问股票涨跌、近期走势、技术分析所需历史数据时调用。",
        when_not_to_use="不包含实时最新价（需结合行情接口）；不包含财务数据（应使用 get_stock_fundamentals_unified）。",
        returns="返回包含 open/high/low/close/volume 等字段的行情序列，可能包含技术指标。",
        example="get_stock_market_data_unified(ticker='600519', start_date='2024-01-01', end_date='2024-12-31')",
        related_tools=["get_technical_indicators", "get_stock_fundamentals_unified"],
    ),
    # ❌ 已删除：get_YFin_data_online（未实现，使用 get_yfin_data_online_legacy）
    # ❌ 已删除：get_YFin_data（未实现，使用 get_yfin_data_legacy）
    # ❌ 已删除：get_stockstats_indicators_report_online（未实现，使用 get_stockstats_indicators_report_online_legacy）
    # ❌ 已删除：get_stockstats_indicators_report（未实现，使用 get_stockstats_indicators_report_legacy）
    
    # === 基本面数据工具 ===
    "get_stock_fundamentals_unified": ToolMetadata(
        id="get_stock_fundamentals_unified",
        name="统一基本面数据",
        description="获取股票的核心财务指标，包括市盈率(PE)、市净率(PB)、净资产收益率(ROE)、营收增长率、净利润增长率、毛利率、资产负债率等。数据来源为最近公布的财报。",
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
        when_to_use="当需要判断股票基本面、估值水平、财务状况时使用。用户询问估值贵不贵、基本面好不好、财务健康度时调用。",
        when_not_to_use="不适用于判断短期走势（应使用 get_technical_indicators）；不包含实时价格（应使用行情接口）。",
        returns="返回包含 pe/pb/roe/营收增长率/利润增长率/毛利率/资产负债率 等字段的字典。",
        example="get_stock_fundamentals_unified(ticker='600519')",
        related_tools=["get_stock_market_data_unified", "get_peer_comparison"],
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
        description="获取与指定股票相关的最新新闻，包括公司公告、行业动态、政策影响等。支持A股、港股、美股。",
        category=ToolCategory.NEWS,
        data_source="finnhub/google",
        is_online=True,
        icon="📰",
        color="#9b59b6",
        parameters=[
            ToolParameter(name="ticker", type="string", description="股票代码（支持A股、港股、美股）", required=True),
            ToolParameter(name="curr_date", type="string", description="当前日期，格式：YYYY-MM-DD", required=True),
        ],
        when_to_use="当需要了解某只股票或某事件的新闻动态、利好利空消息时使用。用户询问发生了什么新闻、有什么利好利空时调用。",
        when_not_to_use="不适用于按关键词搜索新闻（部分数据源支持关键词）；不包含社交媒体讨论（应使用 get_stock_sentiment_unified）。",
        returns="返回新闻列表，每条包含标题、摘要、发布时间、来源等字段。",
        example="get_stock_news_unified(ticker='600519', curr_date='2024-12-31')",
        related_tools=["get_stock_sentiment_unified", "get_stock_fundamentals_unified"],
    ),
    # ❌ 已删除：get_global_news_openai（未实现，使用 get_global_news_openai_legacy）
    # ❌ 已删除：get_google_news（未实现，使用 get_google_news_legacy）
    # ❌ 已删除：get_finnhub_news（未实现，使用 get_finnhub_news_legacy）
    # ❌ 已删除：get_reddit_news（未实现，使用 get_reddit_news_legacy）

    # === 社交媒体工具 ===
    "get_stock_sentiment_unified": ToolMetadata(
        id="get_stock_sentiment_unified",
        name="统一情绪分析",
        description="获取股票在社交媒体（如雪球、股吧、Reddit等）上的讨论情绪和热度。用于了解市场情绪、散户关注度。",
        category=ToolCategory.SOCIAL,
        data_source="reddit/twitter",
        is_online=True,
        icon="💬",
        color="#e74c3c",
        parameters=[
            ToolParameter(name="ticker", type="string", description="股票代码（支持A股、港股、美股）", required=True),
            ToolParameter(name="curr_date", type="string", description="当前日期，格式：YYYY-MM-DD", required=True),
        ],
        when_to_use="当需要了解市场情绪、散户关注度、舆情热度时使用。用户询问这只股票讨论热度如何、市场情绪怎样时调用。",
        when_not_to_use="不适用于获取新闻（应使用 get_stock_news_unified）；情绪数据有滞后性。",
        returns="返回情绪指标、讨论热度、正负面比例等。",
        example="get_stock_sentiment_unified(ticker='600519', curr_date='2024-12-31')",
        related_tools=["get_stock_news_unified", "get_stock_market_data_unified"],
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
        description="获取主要指数（上证、深证、创业板、科创50等）的历史行情和均线走势。用于分析大盘技术面。",
        category=ToolCategory.MARKET,
        data_source="tushare",
        is_online=True,
        icon="📈",
        color="#1abc9c",
        parameters=[
            ToolParameter(name="trade_date", type="string", description="交易日期，格式：YYYY-MM-DD", required=True),
            ToolParameter(name="lookback_days", type="integer", description="回看天数，默认60天", required=False, default=60),
        ],
        when_to_use="当需要指数历史走势、均线数据、大盘技术分析时使用。用户询问上证指数走势、创业板近期表现时调用。",
        when_not_to_use="不适用于个股；快速概览用 get_china_market_overview。",
        returns="返回主要指数行情序列，含开高低收、成交量、均线等。",
        example="get_index_data(trade_date='2024-12-31', lookback_days=60)",
        related_tools=["get_china_market_overview", "get_index_technical", "get_market_overview"],
    ),
    "get_market_overview": ToolMetadata(
        id="get_market_overview",
        name="市场概览",
        description="获取整体市场环境概览，包括主要指数走势、涨跌家数统计、资金流向、市场情绪等综合数据。适用于判断大盘环境。",
        category=ToolCategory.MARKET,
        data_source="multiple",
        is_online=True,
        icon="🌍",
        color="#3498db",
        parameters=[
            ToolParameter(name="trade_date", type="string", description="交易日期，格式：YYYY-MM-DD", required=True),
        ],
        when_to_use="当需要了解大盘环境、市场整体表现、涨跌家数、资金流向时使用。用户询问市场怎么样、大盘好不好时调用。",
        when_not_to_use="不适用于单只股票分析；不适用于板块详细数据（应使用 get_sector_data）。",
        returns="返回市场概览数据，包含指数涨跌、涨跌家数、资金流向等。",
        example="get_market_overview(trade_date='2024-12-31')",
        related_tools=["get_china_market_overview", "get_index_data", "get_limit_stats"],
    ),
    # 新增大盘分析工具
    "get_north_flow": ToolMetadata(
        id="get_north_flow",
        name="北向资金流向",
        description="获取沪深港通北向资金（外资）流向数据，包括净流入/流出、沪股通、深股通明细。用于分析外资动向。",
        category=ToolCategory.MARKET,
        data_source="tushare",
        is_online=True,
        icon="💰",
        color="#3498db",
        parameters=[
            ToolParameter(name="trade_date", type="string", description="交易日期，格式：YYYY-MM-DD", required=True),
            ToolParameter(name="lookback_days", type="integer", description="回看天数，默认10天", required=False, default=10),
        ],
        when_to_use="当需要了解北向资金动向、外资是否流入/流出时使用。用户询问北向资金、外资动向时调用。",
        when_not_to_use="不适用于个股资金流向；不适用于两融资金（应使用 get_margin_trading）。",
        returns="返回北向资金净流入/流出序列，含沪股通、深股通。",
        example="get_north_flow(trade_date='2024-12-31')",
        related_tools=["get_margin_trading", "get_fund_flow_data", "get_market_overview"],
    ),
    "get_margin_trading": ToolMetadata(
        id="get_margin_trading",
        name="两融余额",
        description="获取融资融券余额数据，分析杠杆资金（融资买入、融券卖出）动向。反映市场情绪和杠杆水平。",
        category=ToolCategory.MARKET,
        data_source="tushare",
        is_online=True,
        icon="📊",
        color="#3498db",
        parameters=[
            ToolParameter(name="trade_date", type="string", description="交易日期，格式：YYYY-MM-DD", required=True),
            ToolParameter(name="lookback_days", type="integer", description="回看天数，默认10天", required=False, default=10),
        ],
        when_to_use="当需要了解融资融券、杠杆资金动向、市场风险偏好时使用。用户询问两融数据、融资余额时调用。",
        when_not_to_use="不适用于北向资金（应使用 get_north_flow）；不适用于个股资金流向。",
        returns="返回两融余额序列，含融资余额、融券余额及其变化。",
        example="get_margin_trading(trade_date='2024-12-31')",
        related_tools=["get_north_flow", "get_fund_flow_data"],
    ),
    "get_limit_stats": ToolMetadata(
        id="get_limit_stats",
        name="涨跌停统计",
        description="获取涨跌停家数、涨跌家数统计，用于评估市场情绪和赚钱效应。涨停多通常表示市场活跃。",
        category=ToolCategory.MARKET,
        data_source="tushare",
        is_online=True,
        icon="📈",
        color="#3498db",
        parameters=[
            ToolParameter(name="trade_date", type="string", description="交易日期，格式：YYYY-MM-DD", required=True),
        ],
        when_to_use="当需要评估市场情绪、赚钱效应、涨跌家数比时使用。用户询问今天涨停多少、市场情绪如何时调用。",
        when_not_to_use="不适用于单只股票涨停信息；不适用于指数数据。",
        returns="返回涨停家数、跌停家数、上涨/下跌家数等。",
        example="get_limit_stats(trade_date='2024-12-31')",
        related_tools=["get_market_overview", "get_market_breadth"],
    ),
    "get_index_technical": ToolMetadata(
        id="get_index_technical",
        name="指数技术指标",
        description="获取主要指数的技术指标（MACD、RSI、KDJ等），分析大盘技术面走势和信号。",
        category=ToolCategory.MARKET,
        data_source="tushare",
        is_online=True,
        icon="📉",
        color="#3498db",
        parameters=[
            ToolParameter(name="trade_date", type="string", description="交易日期，格式：YYYY-MM-DD", required=True),
            ToolParameter(name="lookback_days", type="integer", description="回看天数，默认60天", required=False, default=60),
        ],
        when_to_use="当需要分析大盘技术面、指数MACD/RSI/KDJ状态时使用。用户询问上证指数技术面、大盘RSI时调用。",
        when_not_to_use="不适用于个股技术指标（应使用 get_technical_indicators）；不适用于指数行情（应使用 get_index_data）。",
        returns="返回指数技术指标序列，如 macd、rsi、kdj 等。",
        example="get_index_technical(trade_date='2024-12-31')",
        related_tools=["get_index_data", "get_technical_indicators", "get_market_overview"],
    ),
    "get_market_breadth": ToolMetadata(
        id="get_market_breadth",
        name="市场宽度",
        description="分析市场宽度，包括成交量分布、市值分布、涨跌广度等，用于评估市场健康度。",
        category=ToolCategory.MARKET,
        data_source="tushare",
        is_online=True,
        icon="📊",
        color="#3498db",
        parameters=[
            ToolParameter(name="trade_date", type="string", description="交易日期，格式：YYYY-MM-DD", required=True),
        ],
        when_to_use="当需要分析市场广度、成交量结构、涨跌分布时使用。用于进阶市场环境分析。",
        when_not_to_use="快速概览用 get_market_overview；不适用于单股分析。",
        returns="返回市场宽度相关数据，含成交量、涨跌分布等。",
        example="get_market_breadth(trade_date='2024-12-31')",
        related_tools=["get_market_overview", "get_limit_stats", "get_market_environment"],
    ),
    "get_market_environment": ToolMetadata(
        id="get_market_environment",
        name="市场环境",
        description="综合评估市场环境，包括估值水平、波动率、情绪指标等，用于判断适不适合参与。",
        category=ToolCategory.MARKET,
        data_source="tushare",
        is_online=True,
        icon="🌐",
        color="#1abc9c",
        parameters=[
            ToolParameter(name="trade_date", type="string", description="交易日期", required=True),
        ],
        when_to_use="当需要综合评估市场环境、估值是否合理、波动率水平时使用。用于择时和仓位建议。",
        when_not_to_use="不适用于单股估值（应使用 get_stock_fundamentals_unified）；快速概览用 get_market_overview。",
        returns="返回市场环境评估数据，含估值、波动率等。",
        example="get_market_environment(trade_date='2024-12-31')",
        related_tools=["identify_market_cycle", "get_market_overview", "get_market_breadth"],
    ),
    "identify_market_cycle": ToolMetadata(
        id="identify_market_cycle",
        name="市场周期识别",
        description="识别当前市场所处的周期阶段（如牛市、熊市、震荡等），用于择时策略参考。",
        category=ToolCategory.MARKET,
        data_source="tushare",
        is_online=True,
        icon="🔄",
        color="#e67e22",
        parameters=[
            ToolParameter(name="trade_date", type="string", description="交易日期", required=True),
        ],
        when_to_use="当需要判断当前市场处于什么阶段、牛市还是熊市时使用。用于择时和仓位建议。",
        when_not_to_use="不适用于个股分析；不适用于短期预测。",
        returns="返回市场周期阶段判断及依据。",
        example="identify_market_cycle(trade_date='2024-12-31')",
        related_tools=["get_market_environment", "get_market_overview"],
    ),
    
    # === 板块分析工具 ===
    "get_sector_data": ToolMetadata(
        id="get_sector_data",
        name="板块数据",
        description="获取股票所属行业/板块的表现数据，包括板块涨跌幅、资金流向、板块内个股表现等。用于分析行业趋势和板块轮动。",
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
        when_to_use="当需要了解某只股票所属板块的表现、行业趋势、板块是否强势时使用。用户询问白酒板块怎么样、半导体板块最近如何时调用。",
        when_not_to_use="不适用于获取板块内股票列表（可结合 get_peer_comparison）；不适用于大盘整体（应使用 get_market_overview）。",
        returns="返回板块表现数据，含涨跌幅、资金流向、板块内龙头等。",
        example="get_sector_data(ticker='600519', trade_date='2024-12-31')",
        related_tools=["get_peer_comparison", "get_fund_flow_data", "analyze_sector"],
    ),
    "get_fund_flow_data": ToolMetadata(
        id="get_fund_flow_data",
        name="资金流向",
        description="获取板块/行业资金流向数据，分析主力资金净流入流出的板块。用于发现热点和资金轮动。",
        category=ToolCategory.MARKET,
        data_source="tushare",
        is_online=True,
        icon="💰",
        color="#3498db",
        parameters=[
            ToolParameter(name="trade_date", type="string", description="交易日期，格式：YYYY-MM-DD", required=True),
            ToolParameter(name="top_n", type="integer", description="返回前N个板块，默认10", required=False, default=10),
        ],
        when_to_use="当需要了解哪些板块资金流入、主力动向、热点板块时使用。用户询问资金流向、主力进了哪些板块时调用。",
        when_not_to_use="不适用于北向资金（应使用 get_north_flow）；不适用于个股资金。",
        returns="返回板块资金流向排名，含净流入、流入流出比等。",
        example="get_fund_flow_data(trade_date='2024-12-31', top_n=10)",
        related_tools=["get_sector_data", "get_north_flow", "get_margin_trading"],
    ),
    "get_peer_comparison": ToolMetadata(
        id="get_peer_comparison",
        name="同业对比",
        description="获取同行业股票对比数据，分析个股在行业中的相对位置。支持多维度对比：估值(PE/PB)、成长性、市值等。",
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
        when_to_use="当需要对比同行业股票、了解个股在行业中的位置、选股筛选时使用。用户询问茅台和五粮液哪个好、同板块有哪些股票时调用。",
        when_not_to_use="不适用于跨行业对比；不适用于单股深度分析。",
        returns="返回同业股票列表及对比数据，含PE、PB、市值、涨跌幅等。",
        example="get_peer_comparison(ticker='600519', trade_date='2024-12-31', top_n=10)",
        related_tools=["get_sector_data", "get_stock_fundamentals_unified"],
    ),
    "analyze_sector": ToolMetadata(
        id="analyze_sector",
        name="综合板块分析",
        description="综合分析股票所属板块，聚合板块表现、资金流向、同业对比等，提供一站式板块分析。",
        category=ToolCategory.MARKET,
        data_source="tushare",
        is_online=True,
        icon="🔍",
        color="#3498db",
        parameters=[
            ToolParameter(name="ticker", type="string", description="股票代码（如 000001 或 000001.SZ）", required=True),
            ToolParameter(name="trade_date", type="string", description="交易日期，格式：YYYY-MM-DD", required=True),
        ],
        when_to_use="当需要对某只股票做完整板块分析、结合板块+同业+资金时使用。可替代多次调用 get_sector_data 和 get_peer_comparison。",
        when_not_to_use="只需单一板块数据时用 get_sector_data 即可；只需同业对比时用 get_peer_comparison。",
        returns="返回综合板块分析结果，含板块表现、资金流向、同业对比等。",
        example="analyze_sector(ticker='600519', trade_date='2024-12-31')",
        related_tools=["get_sector_data", "get_peer_comparison", "get_fund_flow_data"],
    ),
    
    # === 技术指标工具 ===
    "get_technical_indicators": ToolMetadata(
        id="get_technical_indicators",
        name="统一技术指标分析",
        description="获取股票的各类技术指标，包括 MACD、RSI、KDJ、布林带(BOLL)等。用于判断短期走势、买卖信号、超买超卖。支持A股/港股/美股。",
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
        when_to_use="当需要判断股票短期走势、技术面信号、超买超卖时使用。用户询问技术面怎么样、MACD/RSI/KDJ 状态时调用。",
        when_not_to_use="不适用于基本面分析（应使用 get_stock_fundamentals_unified）；不适用于宏观市场环境（应使用 get_market_overview）。",
        returns="返回各技术指标的数值序列，如 macd/macd_signal/rsi/kdj 等。",
        example="get_technical_indicators(ticker='600519', indicators='macd,rsi_14,kdj')",
        related_tools=["get_stock_market_data_unified", "get_stock_fundamentals_unified"],
    ),
    
    # === 中国市场工具 ===
    "get_china_market_overview": ToolMetadata(
        id="get_china_market_overview",
        name="中国市场概览",
        description="获取中国股市主要指数行情概览，包括上证指数、深证成指、创业板指、科创50等。含涨跌幅和简要走势。",
        category=ToolCategory.CHINA,
        data_source="tushare",
        is_online=True,
        icon="🇨🇳",
        color="#e74c3c",
        parameters=[
            ToolParameter(name="curr_date", type="string", description="当前日期，格式：YYYY-MM-DD", required=True),
        ],
        when_to_use="当需要快速了解A股大盘表现、各主要指数涨跌时使用。用户询问今天大盘怎么样、上证指数涨了多少时调用。",
        when_not_to_use="不包含个股数据；不包含板块数据（应使用 get_sector_data）。",
        returns="返回主要指数行情，含指数代码、涨跌幅、收盘价等。",
        example="get_china_market_overview(curr_date='2024-12-31')",
        related_tools=["get_market_overview", "get_index_data"],
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

