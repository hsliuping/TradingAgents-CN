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
    ASSISTANT_OPS = "assistant_ops"  # 助理操作（分析触发、报告查询、定时任务、股票关注列表管理）
    SCREENING = "screening"     # 筛选工具（批量筛选、盈利验证）
    UTILITY = "utility"         # 通用工具（Skill 扩展）
    KNOWLEDGE = "knowledge"     # 知识型（Skill 扩展）
    MCP = "mcp"                 # MCP 外部工具
    EXTERNAL = "external"       # AI 生成的外部 Skill


class ToolTimeoutTier(str, Enum):
    """工具超时分层：按执行耗时分为轻量/中等/重型"""
    LIGHT = "light"    # DB 查询、列表操作等（15 秒）
    MEDIUM = "medium"  # 外部 API 调用（45 秒）
    HEAVY = "heavy"    # 子 Agent / 工作流引擎执行（180 秒）


TOOL_TIMEOUT_SECONDS: Dict[str, int] = {
    ToolTimeoutTier.LIGHT: 15,
    ToolTimeoutTier.MEDIUM: 45,
    ToolTimeoutTier.HEAVY: 180,
}


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
    
    # 来源标识
    source: str = "builtin"           # builtin / generated / mcp / skill
    
    # 数据源信息
    data_source: str = ""             # 数据来源
    is_online: bool = True            # 是否需要在线访问
    # 数据源处理方式标签（供 Skill 工坊 LLM 判断是否需要补充数据源）：
    #   "self_contained" - 工具自包含，内部已封装数据源调用（项目数据访问层 / 直接外部 API / 混合多源 / 纯计算 / 旧版桥接），LLM 直接调用即可
    #   "local_only"     - 工具只查本地 MongoDB，若本地无数据 LLM 可能需要自己调外部数据源补充
    #   "partial"        - 工具覆盖部分需求，LLM 可能需要补充其它数据源或计算
    data_source_handling: str = "self_contained"
    
    # 配置
    timeout: int = 30                 # 超时时间（秒）—— 旧字段，保留兼容
    timeout_tier: str = ToolTimeoutTier.MEDIUM  # 超时分层：light / medium / heavy
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

    # Agent Builder 工具路由元数据：用于区分主入口、专项、补充、通用和降级工具。
    capability_tags: List[str] = Field(default_factory=list)
    tool_role_hint: str = ""          # primary / specialized / supporting / generic / fallback
    output_shape: str = ""            # structured_metrics / structured_records / report / text
    preferred_for: List[str] = Field(default_factory=list)
    not_replacement_for: List[str] = Field(default_factory=list)
    
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
        when_not_to_use="不包含实时最新价（需结合行情接口）；不包含财务数据（应使用 get_stock_fundamentals_unified）；不适用于商誉减值/应收账款异常/现金流质量/风险事件等基本面风险检测。",
        returns="返回包含 open/high/low/close/volume 等字段的行情序列，可能包含技术指标(MA/MACD/RSI等)。不包含财务科目（商誉、应收账款周转率、现金流明细等）。",
        example="get_stock_market_data_unified(ticker='600519', start_date='2024-01-01', end_date='2024-12-31')",
        related_tools=["get_technical_indicators", "get_stock_fundamentals_unified"],
        capability_tags=["price", "volume", "ohlcv", "technical_indicators", "market_data"],
        tool_role_hint="supporting",
        output_shape="report",
        preferred_for=["价格走势分析", "成交量分析", "技术指标计算"],
        not_replacement_for=["goodwill_impairment", "accounts_receivable_anomaly", "cashflow_quality", "risk_event_detection"],
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
        when_not_to_use="不适用于判断短期走势（应使用 get_technical_indicators）；不包含实时价格（应使用行情接口）；不适用于商誉减值/应收账款异常/风险事件专项检测。",
        returns="返回包含 pe/pb/roe/营收增长率/利润增长率/毛利率/资产负债率 等字段的字典。不包含 goodwill、应收账款周转率/账龄明细、商誉减值历史。",
        example="get_stock_fundamentals_unified(ticker='600519')",
        related_tools=["get_stock_market_data_unified", "get_peer_comparison"],
        capability_tags=["valuation", "profitability", "growth", "financial_health", "overview"],
        tool_role_hint="generic",
        output_shape="structured_metrics",
        preferred_for=["基本面快速概览", "估值水平判断", "核心财务指标查询"],
        not_replacement_for=["goodwill_impairment", "accounts_receivable_anomaly", "risk_event_detection", "cashflow_quality"],
    ),
    # ❌ 已删除：get_finnhub_company_insider_sentiment（未实现，使用 get_finnhub_company_insider_sentiment_legacy）
    # ❌ 已删除：get_finnhub_company_insider_transactions（未实现，使用 get_finnhub_company_insider_transactions_legacy）
    # ❌ 已删除：get_simfin_balance_sheet（未实现，使用 get_simfin_balance_sheet_legacy）
    # ❌ 已删除：get_simfin_cashflow（未实现，使用 get_simfin_cashflow_legacy）
    # ❌ 已删除：get_simfin_income_stmt（未实现，使用 get_simfin_income_stmt_legacy）

    # === 专项财务分析工具（Tushare 数据） ===
    "get_income_analysis": ToolMetadata(
        id="get_income_analysis",
        name="利润表分析",
        description="分析股票的营收、利润、费用等利润表核心指标及多期趋势。数据来源为 Tushare 利润表和财务指标。",
        category=ToolCategory.FUNDAMENTALS,
        data_source="tushare",
        is_online=True,
        icon="📊",
        color="#3498db",
        parameters=[
            ToolParameter(name="ticker", type="string", description="股票代码，6位数字（如 600519、000001）", required=True),
            ToolParameter(name="periods", type="integer", description="分析期数（最近几个季度），默认8", required=False, default=8),
        ],
        when_to_use="当用户询问营收利润增长、利润趋势、盈利能力时使用。如'茅台营收利润增长怎么样'、'最近几年利润趋势'、'毛利率净利率多少'。",
        when_not_to_use="不适用于资产负债分析（应使用 get_balance_sheet_analysis）；不适用于现金流分析（应使用 get_cashflow_analysis）；不适用于商誉减值/应收账款异常/风险事件检测。",
        returns="返回 Markdown 格式的利润表分析报告，包含最新一期营收/利润/毛利率/净利率/费用结构概览、多期收入利润趋势表格、盈利能力趋势。不包含商誉减值、应收账款周转率/账龄分析。",
        example="get_income_analysis(ticker='600519', periods=8)",
        related_tools=["get_balance_sheet_analysis", "get_cashflow_analysis", "get_stock_fundamentals_unified"],
        capability_tags=["revenue", "profit", "margin", "expense_structure", "earnings_trend"],
        tool_role_hint="supporting",
        output_shape="report",
        preferred_for=["利润趋势分析", "盈利能力评估", "费用结构分析"],
        not_replacement_for=["goodwill_impairment", "accounts_receivable_anomaly", "risk_event_detection", "cashflow_quality"],
    ),
    "get_balance_sheet_analysis": ToolMetadata(
        id="get_balance_sheet_analysis",
        name="资产负债表分析",
        description="分析股票的资产负债结构、偿债能力、财务健康度。包含资产负债率、流动比率、速动比率等。",
        category=ToolCategory.FUNDAMENTALS,
        data_source="tushare",
        is_online=True,
        icon="🏦",
        color="#2ecc71",
        parameters=[
            ToolParameter(name="ticker", type="string", description="股票代码，6位数字（如 600519、000001）", required=True),
            ToolParameter(name="periods", type="integer", description="分析期数（最近几个季度），默认8", required=False, default=8),
        ],
        when_to_use="当用户询问资产负债率、财务是否健康、偿债能力、现金储备时使用。如'资产负债率高不高'、'现金储备够不够'、'财务是否安全'。",
        when_not_to_use="不适用于利润分析（应使用 get_income_analysis）；不适用于现金流分析（应使用 get_cashflow_analysis）；不适用于商誉减值风险评估（本工具不返回 goodwill 字段）；不适用于应收账款异常检测（本工具仅返回应收账款余额，不做周转率/账龄/坏账覆盖深度分析）。",
        returns="返回 Markdown 格式的资产负债表分析报告，包含总资产、总负债、净资产、货币资金、应收账款、存货、固定资产、商誉（年报数据，季报可能为空）、商誉/净资产比率、资产负债率、流动比率、速动比率、现金比率、权益乘数、流动资产/非流动资产占比、多期资产趋势表。",
        example="get_balance_sheet_analysis(ticker='600519', periods=8)",
        related_tools=["get_income_analysis", "get_cashflow_analysis", "get_stock_fundamentals_unified"],
        capability_tags=["solvency", "liquidity", "asset_structure", "debt_ratio", "goodwill"],
        tool_role_hint="supporting",
        output_shape="report",
        preferred_for=["偿债能力评估", "流动性分析", "资产负债结构概览", "商誉规模查询（年报）"],
        not_replacement_for=["accounts_receivable_anomaly", "cashflow_quality", "profit_analysis"],
    ),
    "get_cashflow_analysis": ToolMetadata(
        id="get_cashflow_analysis",
        name="现金流量表分析",
        description="分析股票的经营/投资/筹资现金流，评估现金流健康度和利润含金量。包含自由现金流估算。",
        category=ToolCategory.FUNDAMENTALS,
        data_source="tushare",
        is_online=True,
        icon="💰",
        color="#f39c12",
        parameters=[
            ToolParameter(name="ticker", type="string", description="股票代码，6位数字（如 600519、000001）", required=True),
            ToolParameter(name="periods", type="integer", description="分析期数（最近几个季度），默认8", required=False, default=8),
        ],
        when_to_use="当用户询问经营现金流、自由现金流、利润含金量、现金流是否健康时使用。如'经营现金流好不好'、'自由现金流充裕吗'、'利润质量怎么样'。",
        when_not_to_use="不适用于利润分析（应使用 get_income_analysis）；不适用于资产负债分析（应使用 get_balance_sheet_analysis）；不适用于商誉减值/应收账款异常/风险事件检测。",
        returns="返回 Markdown 格式的现金流分析报告，包含三类现金流（经营/投资/筹资）状况、自由现金流估算、现金流质量评估、多期趋势。不包含商誉、应收账款周转率/账龄、风险事件标签。",
        example="get_cashflow_analysis(ticker='600519', periods=8)",
        related_tools=["get_income_analysis", "get_balance_sheet_analysis", "get_stock_fundamentals_unified"],
        capability_tags=["cashflow", "fcf", "operating_cashflow", "earnings_quality"],
        tool_role_hint="supporting",
        output_shape="report",
        preferred_for=["现金流健康度评估", "利润含金量分析", "自由现金流估算"],
        not_replacement_for=["goodwill_impairment", "accounts_receivable_anomaly", "risk_event_detection"],
    ),
    "get_goodwill_analysis": ToolMetadata(
        id="get_goodwill_analysis",
        name="商誉分析",
        description="分析股票的商誉规模、占比及变动趋势，评估商誉减值风险。从年报资产负债表提取 goodwill 字段，计算商誉/净资产比率和同比变化。",
        category=ToolCategory.FUNDAMENTALS,
        data_source="tushare",
        is_online=True,
        icon="💎",
        color="#e74c3c",
        parameters=[
            ToolParameter(name="ticker", type="string", description="股票代码，6位数字（如 002230、600519、000001）", required=True),
            ToolParameter(name="years", type="integer", description="回溯年数，默认5年", required=False, default=5),
        ],
        when_to_use="当用户询问商誉减值风险、商誉规模、商誉占比时使用。如'商誉高不高'、'商誉减值风险大不大'、'商誉占净资产比例多少'。⚠️ 本工具专门从年报中提取商誉数据，不会像资产负债表分析那样因季报空值导致数据缺失。",
        when_not_to_use="不适用于利润分析（应使用 get_income_analysis）；不适用于现金流分析（应使用 get_cashflow_analysis）；不适用于应收账款异常检测。",
        returns="返回 Markdown 格式的商誉分析报告，包含最新年度商誉金额、商誉/净资产比率、商誉/总资产比率、风险信号（红/黄/绿）、多年趋势表格、减值信号检测（同比降幅>20%自动标记）。",
        example="get_goodwill_analysis(ticker='002230', years=5)",
        related_tools=["get_balance_sheet_analysis", "get_risk_event_flags_tool", "get_financial_risk_factors"],
        capability_tags=["goodwill", "acquisition_premium", "impairment_risk", "annual_report"],
        tool_role_hint="specialized",
        output_shape="report",
        preferred_for=["商誉减值风险评估", "商誉规模查询", "商誉/净资产比率检查"],
        not_replacement_for=["profit_analysis", "accounts_receivable_anomaly", "cashflow_quality"],
    ),
    "get_dupont_analysis": ToolMetadata(
        id="get_dupont_analysis",
        name="杜邦分析",
        description="对股票进行杜邦分析，拆解ROE为三因子（净利率×资产周转率×权益乘数）和五因子（税负×利息负担×经营利润率×资产周转率×权益乘数），支持多年趋势对比，识别ROE的核心驱动因素。",
        category=ToolCategory.FUNDAMENTALS,
        data_source="tushare",
        is_online=True,
        icon="🔍",
        color="#9b59b6",
        parameters=[
            ToolParameter(name="ticker", type="string", description="股票代码，6位数字（如 600519、000001、002230）", required=True),
            ToolParameter(name="years", type="integer", description="回溯年数，默认5年", required=False, default=5),
        ],
        when_to_use="当用户询问ROE拆解、杜邦分析、盈利质量时使用。如'ROE高是怎么做到的'、'杜邦分析一下'、'盈利靠的是利润率还是杠杆'、'资产周转效率如何'。",
        when_not_to_use="不适用于单期利润查询（应使用 get_income_analysis）；不适用于估值（应使用 get_value_factor_bundle_tool）。",
        returns="返回 Markdown 格式的杜邦分析报告，包含三因子拆解表格+ROE验证、ROE驱动因素判断（利润率/周转率/杠杆）、五因子拆解（如有营业利润数据）、多年趋势表格。",
        example="get_dupont_analysis(ticker='600519', years=5)",
        related_tools=["get_income_analysis", "get_balance_sheet_analysis", "get_stock_fundamentals_unified"],
        capability_tags=["roe_decomposition", "profitability", "asset_efficiency", "financial_leverage", "dupont"],
        tool_role_hint="specialized",
        output_shape="report",
        preferred_for=["ROE拆解", "杜邦分析", "盈利质量评估", "经营效率分析"],
        not_replacement_for=["valuation", "cashflow_analysis", "goodwill_impairment"],
    ),
    "get_dividend_data": ToolMetadata(
        id="get_dividend_data",
        name="分红送股数据",
        description="获取股票的历史分红送股记录，包括每股现金分红、送股转增比例、分红年度、实施进度等。需要 Tushare 2000+ 积分权限。",
        category=ToolCategory.FUNDAMENTALS,
        data_source="tushare",
        is_online=True,
        icon="🎁",
        color="#e74c3c",
        parameters=[
            ToolParameter(name="ticker", type="string", description="股票代码，6位数字（如 600519、000001）", required=True),
            ToolParameter(name="years", type="integer", description="查询最近几年的分红记录，默认5", required=False, default=5),
        ],
        when_to_use="当用户询问分红情况、股息率、送股转增、分红比例时使用。如'最近几年分红情况'、'股息率多少'、'分红比例怎么样'、'有没有送股'。",
        when_not_to_use="不适用于利润分析（应使用 get_income_analysis）；不适用于基本面快速概览（应使用 get_stock_fundamentals_unified）；不适用于商誉减值/应收账款异常/现金流质量/风险事件等风险检测。",
        returns="返回 Markdown 格式的分红送股报告，包含分红概览、每年分红明细（税前/税后分红、送股、转增、除权日）、分红趋势判断。不包含商誉、应收账款周转率、现金流明细、风险事件标签。",
        example="get_dividend_data(ticker='600519', years=5)",
        related_tools=["get_income_analysis", "get_stock_fundamentals_unified"],
        capability_tags=["dividend", "split", "dividend_yield", "shareholder_return"],
        tool_role_hint="supporting",
        output_shape="report",
        preferred_for=["分红历史查询", "股息率分析", "股东回报评估"],
        not_replacement_for=["goodwill_impairment", "accounts_receivable_anomaly", "cashflow_quality", "risk_event_detection"],
    ),
    "get_main_business": ToolMetadata(
        id="get_main_business",
        name="主营业务构成",
        description="获取股票的主营业务收入构成，按产品/地区维度展示各业务线的收入、成本、毛利率和占比。",
        category=ToolCategory.FUNDAMENTALS,
        data_source="tushare",
        is_online=True,
        icon="🏢",
        color="#9b59b6",
        parameters=[
            ToolParameter(name="ticker", type="string", description="股票代码，6位数字（如 600519、000001）", required=True),
            ToolParameter(name="periods", type="integer", description="分析期数（最近几个报告期），默认4", required=False, default=4),
        ],
        when_to_use="当用户询问主营业务构成、收入来源结构、各产品线占比时使用。如'主营业务是什么'、'收入来源构成'、'哪个产品贡献最大'。",
        when_not_to_use="不适用于利润趋势分析（应使用 get_income_analysis）；不适用于综合基本面概览（应使用 get_stock_fundamentals_unified）；不适用于商誉减值/应收账款异常/现金流质量/风险事件等风险检测。",
        returns="返回 Markdown 格式的主营业务构成报告，按报告期分组展示各业务/产品的收入、成本、毛利率和占比。不包含商誉、应收账款周转率/账龄、现金流明细、风险事件标签。",
        example="get_main_business(ticker='600519', periods=4)",
        related_tools=["get_income_analysis", "get_stock_fundamentals_unified"],
        capability_tags=["revenue_composition", "business_segment", "product_mix", "regional_breakdown"],
        tool_role_hint="supporting",
        output_shape="report",
        preferred_for=["收入结构分析", "业务分部评估", "产品/地区占比查询"],
        not_replacement_for=["goodwill_impairment", "accounts_receivable_anomaly", "cashflow_quality", "risk_event_detection"],
    ),

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
    
    # === 汽车行业数据工具 ===
    "get_auto_brand_monthly_sales": ToolMetadata(
        id="get_auto_brand_monthly_sales",
        name="汽车品牌月度销量",
        description="查询指定汽车品牌在某个月份下全部车型的销量（懂车帝全国月度销量榜），返回车型排名、月销量、售价区间与名次变化。",
        category=ToolCategory.MARKET,
        data_source="dongchedi",
        is_online=True,
        icon="🚗",
        color="#e67e22",
        parameters=[
            ToolParameter(name="brand", type="string", description="汽车品牌名称，如“问界”“比亚迪”“理想汽车”，支持模糊匹配", required=True),
            ToolParameter(name="month", type="string", description="统计月份，格式 YYYYMM（如 202608）；也可传 500（近半年）/1000（近一年）聚合；留空则取最近一个完整月份", required=False, default=""),
        ],
        when_to_use="当需要了解某汽车品牌（或旗下车型）的月度销量、判断整车厂商终端销量景气度时使用。适用于汽车产业链（整车/零部件）相关个股的基本面与景气度研究。可用于多品牌销量横向对比。",
        when_not_to_use="不提供股价、估值或财务数据（应使用 get_stock_fundamentals_unified）；不覆盖非乘用车（如商用车、卡车）的完整口径；不适用于非汽车行业。",
        returns="返回 markdown 报告：品牌合计销量 + 车型明细表（排名 / 车型 / 月销量 / 售价区间 / 上期排名 / 名次变化），按车型销量排名排序。",
        example="get_auto_brand_monthly_sales(brand='问界', month='202608')",
        related_tools=["get_sector_data", "get_stock_fundamentals_unified"],
        limitations="数据来自懂车帝公开榜单，覆盖乘用车车型零售销量；榜单仅收录有销量的车型，销量极低或未上市的车型可能缺失。",
        capability_tags=["auto_sales", "brand_sales", "monthly_sales", "auto_industry", "dongchedi"],
        tool_role_hint="specialized",
        output_shape="report",
        preferred_for=["汽车品牌月度销量查询", "品牌旗下车型销量对比", "整车厂商销量跟踪"],
        not_replacement_for=["price_volume_analysis", "financial_statement_analysis"],
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
        when_to_use="当已知具体股票代码，需要了解该股票所属板块的表现时使用。注意：此工具需要 ticker（股票代码），如果用户只提到板块/概念名称而未指定个股，应优先使用 analyze_sector_by_name 或 get_sector_daily（它们直接接受板块名称关键词）。",
        when_not_to_use="用户只问板块走势但没提到具体个股时，不要用此工具（应使用 analyze_sector_by_name）；不适用于大盘整体（应使用 get_market_overview）。",
        returns="返回板块表现数据，含涨跌幅、资金流向、板块内龙头等。",
        example="get_sector_data(ticker='600519', trade_date='2024-12-31')",
        related_tools=["get_peer_comparison", "get_fund_flow_data", "analyze_sector",
                       "analyze_sector_by_name", "get_sector_daily"],
    ),
    "get_fund_flow_data": ToolMetadata(
        id="get_fund_flow_data",
        name="板块资金流向",
        description="获取行业板块和概念板块的资金流向数据，分析主力资金净流入流出的板块排名。返回的是板块级别（不是个股级别）的资金流向，含行业板块TOP和概念板块TOP。支持单日快照和多日累计聚合两种模式。",
        category=ToolCategory.MARKET,
        data_source="tushare",
        is_online=True,
        icon="💰",
        color="#3498db",
        parameters=[
            ToolParameter(name="trade_date", type="string", description="截止交易日期，格式：YYYY-MM-DD", required=True),
            ToolParameter(name="top_n", type="integer", description="返回前N个板块，默认10", required=False, default=10),
            ToolParameter(name="lookback_days", type="integer",
                         description="回溯天数：1=仅当天快照，7=最近一周累计，30=最近一个月累计。用户问'最近一周/一个月'时应传对应天数。默认1",
                         required=False, default=1),
        ],
        when_to_use="当用户问'哪些板块资金流入最多'、'板块资金净流入排名'、'热点板块'、'资金流向'时使用。如果用户问'最近一周/一个月板块轮动'，应将 lookback_days 设为 7 或 30，获取多日累计数据。返回行业板块和概念板块两个维度的资金流向排名。",
        when_not_to_use="不适用于北向资金（应使用 get_north_flow）；不适用于个股级别资金流向；不适用于两融数据（应使用 get_margin_trading）。",
        returns="单日模式：返回当天板块资金流向排名（板块名、净流入亿元、涨跌幅、领涨股）。多日模式：返回累计净流入排名（板块名、累计净流入亿元、日均净流入、净流入天数/总天数、平均涨跌幅），可分析板块轮动趋势和资金持续性。",
        example="get_fund_flow_data(trade_date='2026-02-13', top_n=10, lookback_days=30)",
        related_tools=["get_sector_data", "get_north_flow", "get_margin_trading",
                       "analyze_sector_by_name", "get_sector_daily"],
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
        when_not_to_use="不适用于跨行业对比；不适用于单股深度分析；不适用于商誉减值/应收账款异常/现金流质量/风险事件等基本面风险检测。",
        returns="返回同业股票列表及对比数据，含PE、PB、市值、涨跌幅等估值与市场指标。不包含商誉、应收账款周转率、现金流明细、风险事件标签。",
        example="get_peer_comparison(ticker='600519', trade_date='2024-12-31', top_n=10)",
        related_tools=["get_sector_data", "get_stock_fundamentals_unified"],
        capability_tags=["peer_comparison", "valuation", "market_cap", "sector_ranking"],
        tool_role_hint="supporting",
        output_shape="report",
        preferred_for=["同业估值对比", "行业排名", "选股筛选"],
        not_replacement_for=["goodwill_impairment", "accounts_receivable_anomaly", "cashflow_quality", "risk_event_detection"],
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
        related_tools=["get_sector_data", "get_peer_comparison", "get_fund_flow_data",
                       "analyze_sector_by_name"],
    ),

    # === 板块级别工具（以板块名称为入口，无需 ticker） ===
    "search_sector": ToolMetadata(
        id="search_sector",
        name="板块搜索",
        description="按名称关键词搜索A股板块（行业/概念/地域），返回匹配的板块列表及代码。支持模糊匹配，如搜索'小米'可找到'小米概念'和'小米汽车'。",
        category=ToolCategory.MARKET,
        data_source="tushare",
        is_online=True,
        icon="🔍",
        color="#9b59b6",
        parameters=[
            ToolParameter(name="keyword", type="string", description="板块名称关键词（如 光伏、半导体、白酒、小米、华为）", required=True),
            ToolParameter(name="sector_type", type="string", description="板块类型: N=行业（含概念板块）, S=统计概念, R=地域，默认N", required=False, default="N"),
        ],
        when_to_use="当需要查找板块代码、确认板块是否存在、模糊搜索板块名称时使用。通常作为其他板块工具的前置步骤，但 get_sector_daily/get_sector_constituents/analyze_sector_by_name 内部已自动搜索，一般无需单独调用。",
        when_not_to_use="不需要先调此工具再调 analyze_sector_by_name，后者已内置搜索。不适用于获取板块行情或成分股（应使用对应工具）。",
        returns="返回匹配的板块列表，含板块代码(ts_code)、板块名称、成分股数量。",
        example="search_sector(keyword='小米', sector_type='N')",
        related_tools=["get_sector_daily", "get_sector_constituents", "analyze_sector_by_name"],
    ),
    "get_sector_daily": ToolMetadata(
        id="get_sector_daily",
        name="板块行情",
        description="获取板块指数的日线行情数据（按板块名称），包括收盘价、涨跌幅、成交量、换手率、总市值等。直接反映板块整体走势，无需逐只查询个股。",
        category=ToolCategory.MARKET,
        data_source="tushare",
        is_online=True,
        icon="📊",
        color="#9b59b6",
        parameters=[
            ToolParameter(name="sector_name", type="string", description="板块名称关键词（如 光伏、半导体、白酒、小米汽车）", required=True),
            ToolParameter(name="trade_date", type="string", description="交易日期，格式：YYYY-MM-DD", required=True),
            ToolParameter(name="lookback_days", type="integer", description="回看天数，默认20天", required=False, default=20),
        ],
        when_to_use="当用户问'XX板块/概念/行业最近走势如何'、'XX板块涨了多少'时使用。板块有自己的指数行情（涨跌幅、成交量、换手率），直接调此工具即可获取板块整体走势，不需要逐只查询个股行情。",
        when_not_to_use="不适用于查询板块成分股列表（应使用 get_sector_constituents）；不适用于个股行情（应使用 get_stock_market_data_unified）。如需一站式板块分析（行情+成分股+资金），用 analyze_sector_by_name 更高效。",
        returns="返回板块指数行情报告，含最新收盘价、涨跌幅、成交量、换手率、总市值，以及近期走势汇总。",
        example="get_sector_daily(sector_name='小米汽车', trade_date='2026-02-13')",
        related_tools=["search_sector", "get_sector_constituents", "analyze_sector_by_name", "get_fund_flow_data"],
    ),
    "get_sector_constituents": ToolMetadata(
        id="get_sector_constituents",
        name="板块成分股",
        description="获取板块的成分股列表及其市值、估值排名（按板块名称）。用于查看某个行业/概念板块有哪些股票、龙头股是谁。",
        category=ToolCategory.MARKET,
        data_source="tushare",
        is_online=True,
        icon="📋",
        color="#9b59b6",
        parameters=[
            ToolParameter(name="sector_name", type="string", description="板块名称关键词（如 光伏、半导体、白酒、小米汽车）", required=True),
            ToolParameter(name="trade_date", type="string", description="交易日期，格式：YYYY-MM-DD", required=True),
            ToolParameter(name="top_n", type="integer", description="返回前N只成分股（按市值排序），默认15", required=False, default=15),
        ],
        when_to_use="当用户问'XX概念股有哪些'、'XX板块龙头股'、'XX概念股列表'时使用。直接传入概念关键词即可，无需 ticker。",
        when_not_to_use="不适用于查看板块整体走势（应使用 get_sector_daily）；如需行情+成分股一起，用 analyze_sector_by_name。",
        returns="返回板块成分股列表，含股票代码、名称、市值、PE/PB估值等，按市值排序。",
        example="get_sector_constituents(sector_name='小米汽车', trade_date='2026-02-13', top_n=15)",
        related_tools=["search_sector", "get_sector_daily", "analyze_sector_by_name"],
    ),
    "analyze_sector_by_name": ToolMetadata(
        id="analyze_sector_by_name",
        name="板块综合分析（按名称）",
        description="按板块名称进行一站式综合分析，整合板块指数行情（涨跌幅/成交量/换手率）、龙头成分股、全市场资金流向。一次调用即可回答'XX板块/概念怎么样'类问题，无需多次调用其他工具。",
        category=ToolCategory.MARKET,
        data_source="tushare",
        is_online=True,
        icon="🏷️",
        color="#9b59b6",
        parameters=[
            ToolParameter(name="sector_name", type="string", description="板块名称关键词（如 光伏、半导体、白酒、小米汽车、华为概念）", required=True),
            ToolParameter(name="trade_date", type="string", description="交易日期，格式：YYYY-MM-DD", required=True),
        ],
        when_to_use="当用户问'XX板块/概念/行业怎么样'、'XX概念股走势'、'XX板块投资机会'、'XX行业前景'时优先使用。这是板块分析的首选一站式工具，一次调用返回板块行情+龙头股+资金流向，避免多次调用浪费工具轮次。",
        when_not_to_use="不适用于个股深度分析（应使用个股工具）；如果只需要成分股列表不需要行情，可以单独用 get_sector_constituents。",
        returns="返回板块综合分析报告，包含：板块指数行情（收盘价、涨跌幅、成交量、换手率、市值）、近期走势趋势、龙头成分股列表（市值排序）、全市场板块资金流向排名。",
        example="analyze_sector_by_name(sector_name='小米汽车', trade_date='2026-02-13')",
        related_tools=["search_sector", "get_sector_daily", "get_sector_constituents", "get_fund_flow_data"],
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
        when_not_to_use="不适用于基本面分析（应使用 get_stock_fundamentals_unified）；不适用于宏观市场环境（应使用 get_market_overview）；不适用于商誉减值/应收账款异常/现金流质量/风险事件等基本面风险检测。",
        returns="返回各技术指标的数值序列，如 macd/macd_signal/rsi/kdj 等。不包含财务科目（商誉、应收账款周转率、现金流等）和风险事件标签。",
        example="get_technical_indicators(ticker='600519', indicators='macd,rsi_14,kdj')",
        related_tools=["get_stock_market_data_unified", "get_stock_fundamentals_unified"],
        capability_tags=["macd", "rsi", "kdj", "bollinger", "technical_analysis"],
        tool_role_hint="supporting",
        output_shape="report",
        preferred_for=["短期走势判断", "买卖信号识别", "超买超卖评估"],
        not_replacement_for=["goodwill_impairment", "accounts_receivable_anomaly", "cashflow_quality", "risk_event_detection"],
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
        timeout_tier=ToolTimeoutTier.LIGHT,
        data_source_handling="local_only",
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
        timeout_tier=ToolTimeoutTier.LIGHT,
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
        timeout_tier=ToolTimeoutTier.LIGHT,
        data_source_handling="local_only",
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

    # === 筹码分布工具 ===
    "get_chip_distribution": ToolMetadata(
        id="get_chip_distribution",
        name="筹码分布",
        description="获取股票筹码分布数据，分析获利比例、平均成本和筹码集中度。数据来源：AkShare（优先）→ Tushare（备用）。",
        category=ToolCategory.MARKET,
        data_source="akshare/tushare",
        is_online=True,
        icon="📊",
        color="#e74c3c",
        parameters=[
            ToolParameter(name="ticker", type="string", description="股票代码（如 000001 或 000001.SZ）", required=True),
            ToolParameter(name="trade_date", type="string", description="交易日期，格式：YYYY-MM-DD", required=True),
        ],
        when_to_use="当用户需要了解股票筹码分布、持仓成本结构、获利比例、套牢盘分布时使用。分析市场博弈、主力成本、支撑压力时调用。",
        when_not_to_use="不适用于分析实时价格走势（应使用 get_stock_market_data_unified）；不包含财务数据（应使用基本面工具）。",
        returns="返回筹码分布分析报告，包含获利比例、平均成本、90%/70%筹码区间和集中度指标。",
        example="get_chip_distribution(ticker='000001', trade_date='2024-01-05')",
        related_tools=["get_stock_market_data_unified", "get_technical_indicators"],
    ),
    "get_chip_distribution_akshare": ToolMetadata(
        id="get_chip_distribution_akshare",
        name="筹码分布(AkShare)",
        description="通过 AkShare 东方财富数据接口获取股票筹码分布数据（免费数据源）。",
        category=ToolCategory.MARKET,
        data_source="akshare",
        is_online=True,
        icon="📊",
        color="#e74c3c",
        parameters=[
            ToolParameter(name="ticker", type="string", description="股票代码（如 000001 或 000001.SZ）", required=True),
            ToolParameter(name="trade_date", type="string", description="交易日期，格式：YYYY-MM-DD", required=True),
        ],
        when_to_use="当需要使用免费数据源获取A股筹码分布数据时使用。",
        returns="返回包含获利比例、平均成本、筹码集中度等字段的JSON字符串。",
    ),
    "get_chip_distribution_tushare": ToolMetadata(
        id="get_chip_distribution_tushare",
        name="筹码分布(Tushare)",
        description="通过 Tushare 官方 API 获取股票筹码分布数据（需要5000积分权限）。",
        category=ToolCategory.MARKET,
        data_source="tushare",
        is_online=True,
        icon="📊",
        color="#e74c3c",
        parameters=[
            ToolParameter(name="ticker", type="string", description="股票代码（如 000001 或 000001.SZ）", required=True),
            ToolParameter(name="trade_date", type="string", description="交易日期，格式：YYYY-MM-DD", required=True),
        ],
        when_to_use="当需要使用Tushare官方数据获取A股筹码分布数据时使用（需要5000积分）。",
        returns="返回包含获利比例、加权平均成本、各百分位成本价格的JSON字符串。",
    ),
}

