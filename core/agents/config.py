"""
智能体配置和元数据定义
"""

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class AgentCategory(str, Enum):
    """智能体类别"""
    ANALYST = "analyst"       # 分析师
    RESEARCHER = "researcher"  # 研究员
    TRADER = "trader"         # 交易员
    RISK = "risk"             # 风险评估
    MANAGER = "manager"       # 管理者
    POST_PROCESSOR = "post_processor"  # 后处理器


class LicenseTier(str, Enum):
    """许可证级别"""
    FREE = "free"           # 免费版
    BASIC = "basic"         # 基础版
    PRO = "pro"             # 专业版
    ENTERPRISE = "enterprise"  # 企业版


class AgentInput(BaseModel):
    """智能体输入定义"""
    name: str
    type: str  # string, number, boolean, object, array
    description: str
    required: bool = True
    default: Optional[Any] = None


class AgentOutput(BaseModel):
    """智能体输出定义"""
    name: str
    type: str
    description: str


class ToolMetadata(BaseModel):
    """工具元数据定义"""
    id: str                           # 工具唯一标识
    name: str                         # 显示名称
    description: str                  # 描述
    category: str                     # 工具类别: market, news, social, fundamentals, etc.

    # 参数定义
    parameters: List[Dict[str, Any]] = Field(default_factory=list)

    # 数据源信息
    data_source: str = ""             # 数据来源: yfinance, finnhub, reddit, etc.
    is_online: bool = True            # 是否需要在线访问

    # 配置
    timeout: int = 30                 # 超时时间（秒）
    rate_limit: Optional[int] = None  # 频率限制（每分钟调用次数）

    # 许可证
    license_tier: LicenseTier = LicenseTier.FREE

    # 显示
    icon: str = "🔧"
    color: str = "#95a5a6"


class AgentToolConfig(BaseModel):
    """Agent 工具配置"""
    tool_id: str                      # 工具 ID
    enabled: bool = True              # 是否启用
    priority: int = 0                 # 优先级（越高越优先）
    config: Dict[str, Any] = Field(default_factory=dict)  # 工具特定配置


class AgentMetadata(BaseModel):
    """
    智能体元数据 - 用于注册和发现
    """
    id: str                          # 唯一标识: market_analyst
    name: str                        # 显示名称: 市场分析师
    description: str                 # 描述
    category: AgentCategory          # 分类
    version: str = "1.0.0"

    # 输入输出定义
    inputs: List[AgentInput] = Field(default_factory=list)
    outputs: List[AgentOutput] = Field(default_factory=list)

    # 工具配置
    tools: List[str] = Field(default_factory=list)  # 可用工具 ID 列表
    default_tools: List[str] = Field(default_factory=list)  # 默认启用的工具
    max_tool_calls: int = 3          # 最大工具调用次数

    # 许可证
    license_tier: LicenseTier = LicenseTier.FREE

    # 标签和图标
    tags: List[str] = Field(default_factory=list)
    icon: str = "🤖"
    color: str = "#3498db"

    # 依赖
    depends_on: List[str] = Field(default_factory=list)  # 依赖的其他智能体

    # 🆕 状态层 IO 定义
    reads_from: List[str] = Field(default_factory=list)  # 读取其他 Agent 的输出字段

    # 🆕 工作流集成配置
    requires_tools: bool = True       # 是否需要工具调用（False 则直接执行）
    output_field: str = ""            # 输出到 state 的字段名，如 "market_report"
    report_label: str = ""            # 报告标签，如 "【市场分析】"
    node_name: str = ""               # 工作流节点名称，如 "Market Analyst"
    execution_order: int = 100        # 执行顺序（越小越先执行）

    class Config:
        use_enum_values = True


class AgentConfig(BaseModel):
    """
    智能体运行时配置
    """
    # LLM 配置
    llm_provider: str = "deepseek"
    llm_model: Optional[str] = None
    temperature: float = 0.2  # 股票分析推荐值：0.2-0.3（快速分析），0.1-0.2（深度分析）
    
    # 工具配置
    online_tools: bool = True
    available_tools: List[str] = Field(default_factory=list)
    
    # 提示词配置
    prompt_template: Optional[str] = None  # 使用的提示词模板 ID
    prompt_variables: Dict[str, Any] = Field(default_factory=dict)
    
    # 记忆配置
    memory_enabled: bool = True
    memory_type: str = "chromadb"  # chromadb, postgresql, none
    
    # 超时配置
    timeout: int = 60
    max_retries: int = 3
    
    # 调试配置
    debug: bool = False
    log_level: str = "INFO"


# 预定义的智能体元数据
BUILTIN_AGENTS: Dict[str, AgentMetadata] = {
    "market_analyst": AgentMetadata(
        id="market_analyst",
        name="市场分析师",
        description="分析市场数据、价格走势和技术指标",
        category=AgentCategory.ANALYST,
        icon="📈",
        color="#2ecc71",
        tags=["技术分析", "市场数据"],
        tools=["get_stock_market_data_unified", "get_YFin_data_online", "get_stockstats_indicators_report_online", "get_YFin_data", "get_stockstats_indicators_report"],
        default_tools=["get_stock_market_data_unified"],
        max_tool_calls=3,
        inputs=[
            AgentInput(name="ticker", type="string", description="股票代码"),
            AgentInput(name="trade_date", type="string", description="交易日期"),
        ],
        outputs=[
            AgentOutput(name="market_report", type="string", description="市场分析报告"),
        ],
        # 🆕 工作流配置
        requires_tools=True,
        output_field="market_report",
        report_label="【技术分析】",
        node_name="Market Analyst",
        execution_order=10,
    ),
    "fundamentals_analyst": AgentMetadata(
        id="fundamentals_analyst",
        name="基本面分析师",
        description="分析公司财务数据和基本面指标",
        category=AgentCategory.ANALYST,
        icon="📊",
        color="#3498db",
        tags=["基本面", "财务分析"],
        tools=["get_stock_fundamentals_unified", "get_finnhub_company_insider_sentiment", "get_finnhub_company_insider_transactions", "get_simfin_balance_sheet", "get_simfin_cashflow", "get_simfin_income_stmt", "get_china_stock_data", "get_china_fundamentals"],
        default_tools=["get_stock_fundamentals_unified"],
        max_tool_calls=3,
        # 🆕 工作流配置
        requires_tools=True,
        output_field="fundamentals_report",
        report_label="【基本面分析】",
        node_name="Fundamentals Analyst",
        execution_order=40,
    ),
    "news_analyst": AgentMetadata(
        id="news_analyst",
        name="新闻分析师",
        description="分析财经新闻和事件影响",
        category=AgentCategory.ANALYST,
        icon="📰",
        color="#9b59b6",
        tags=["新闻", "事件驱动"],
        tools=["get_stock_news_unified", "get_global_news_openai", "get_google_news", "get_finnhub_news", "get_reddit_news"],
        default_tools=["get_stock_news_unified"],
        max_tool_calls=3,
        # 🆕 工作流配置
        requires_tools=True,
        output_field="news_report",
        report_label="【新闻分析】",
        node_name="News Analyst",
        execution_order=30,
    ),
    "social_analyst": AgentMetadata(
        id="social_analyst",
        name="社交媒体分析师",
        description="分析社交媒体情绪和舆论",
        category=AgentCategory.ANALYST,
        icon="💬",
        color="#e74c3c",
        tags=["情绪分析", "舆情"],
        tools=["get_stock_sentiment_unified", "get_stock_news_openai", "get_reddit_stock_info"],
        default_tools=["get_stock_sentiment_unified"],
        max_tool_calls=3,
        # 🆕 工作流配置
        requires_tools=True,
        output_field="sentiment_report",
        report_label="【舆情分析】",
        node_name="Social Analyst",
        execution_order=20,
    ),
    "sector_analyst": AgentMetadata(
        id="sector_analyst",
        name="行业/板块分析师",
        description="分析行业趋势、板块轮动和行业对比",
        category=AgentCategory.ANALYST,
        license_tier=LicenseTier.PRO,
        icon="🏭",
        color="#f39c12",
        tags=["行业分析", "板块轮动"],
        tools=["get_sector_performance", "get_industry_comparison"],
        default_tools=["get_sector_performance"],
        max_tool_calls=3,
        # 🆕 工作流配置（无工具调用）
        requires_tools=False,
        output_field="sector_report",
        report_label="【行业板块分析】",
        node_name="Sector Analyst",
        execution_order=5,  # 在技术分析之前
    ),
    "index_analyst": AgentMetadata(
        id="index_analyst",
        name="大盘/指数分析师",
        description="分析大盘指数、市场环境和系统性风险",
        category=AgentCategory.ANALYST,
        license_tier=LicenseTier.PRO,
        icon="🌐",
        color="#1abc9c",
        tags=["大盘", "指数", "宏观"],
        tools=["get_index_data", "get_market_overview"],
        default_tools=["get_index_data"],
        max_tool_calls=3,
        # 🆕 工作流配置（无工具调用）
        requires_tools=False,
        output_field="index_report",
        report_label="【宏观大盘分析】",
        node_name="Index Analyst",
        execution_order=1,  # 最先执行
    ),
    "bull_researcher": AgentMetadata(
        id="bull_researcher",
        name="看涨研究员",
        description="从乐观角度分析投资机会",
        category=AgentCategory.RESEARCHER,
        icon="🐂",
        color="#27ae60",
        tags=["看涨", "机会"],
        tools=[],  # 研究员不直接调用工具，基于分析师报告
        max_tool_calls=0,
    ),
    "bear_researcher": AgentMetadata(
        id="bear_researcher",
        name="看跌研究员",
        description="从谨慎角度分析投资风险",
        category=AgentCategory.RESEARCHER,
        icon="🐻",
        color="#c0392b",
        tags=["看跌", "风险"],
        tools=[],
        max_tool_calls=0,
    ),
    "trader": AgentMetadata(
        id="trader",
        name="交易员",
        description="综合分析结果做出交易决策",
        category=AgentCategory.TRADER,
        icon="💰",
        color="#f1c40f",
        tags=["交易", "决策"],
        tools=[],
        max_tool_calls=0,
    ),
    "position_advisor": AgentMetadata(
        id="position_advisor",
        name="持仓分析师",
        description="基于单股分析报告和持仓信息，提供个性化的持仓操作建议",
        category=AgentCategory.TRADER,
        icon="💼",
        color="#2980b9",
        tags=["持仓", "操作建议", "风险评估"],
        tools=[],
        max_tool_calls=0,
        requires_tools=False,
    ),
    "risky_analyst": AgentMetadata(
        id="risky_analyst",
        name="激进风险分析师",
        description="从激进角度评估交易计划，关注高收益机会，容忍较高风险",
        category=AgentCategory.RISK,
        icon="🔥",
        color="#e74c3c",
        tags=["风险", "激进", "收益"],
        tools=[],
        max_tool_calls=0,
    ),
    "safe_analyst": AgentMetadata(
        id="safe_analyst",
        name="保守风险分析师",
        description="从保守角度评估交易计划，优先资本保护，规避潜在风险",
        category=AgentCategory.RISK,
        icon="🛡️",
        color="#27ae60",
        tags=["风险", "保守", "保护"],
        tools=[],
        max_tool_calls=0,
    ),
    "neutral_analyst": AgentMetadata(
        id="neutral_analyst",
        name="中性风险分析师",
        description="从中性角度评估交易计划，平衡收益与风险，寻求最优解",
        category=AgentCategory.RISK,
        icon="⚖️",
        color="#3498db",
        tags=["风险", "中性", "平衡"],
        tools=[],
        max_tool_calls=0,
    ),
    "risk_manager": AgentMetadata(
        id="risk_manager",
        name="风险经理",
        description="综合三方风险分析师观点，做出最终风险调整决策",
        category=AgentCategory.MANAGER,
        icon="👨‍⚖️",
        color="#9b59b6",
        tags=["风险", "裁决", "决策"],
        tools=[],
        max_tool_calls=0,
    ),
    "research_manager": AgentMetadata(
        id="research_manager",
        name="研究经理",
        description="综合多空研究员观点，形成投资建议",
        category=AgentCategory.MANAGER,
        icon="👔",
        color="#9b59b6",
        tags=["管理", "综合", "决策"],
        tools=[],
        max_tool_calls=0,
    ),
    # ==================== 交易复盘 Agent ====================
    "timing_analyst": AgentMetadata(
        id="timing_analyst",
        name="时机分析师",
        description="分析买入卖出时机，评估交易时机选择的合理性",
        category=AgentCategory.ANALYST,
        icon="⏰",
        color="#e67e22",
        tags=["复盘", "时机", "买卖点"],
        tools=[
            "get_stock_market_data_unified",
            "get_stockstats_indicators_report",
            "get_trade_records",
            "build_trade_info",
            "get_market_snapshot_for_review"
        ],
        default_tools=[
            "get_stock_market_data_unified",
            "build_trade_info"
        ],
        max_tool_calls=5,
        requires_tools=False,
        output_field="timing_analysis",
        report_label="【时机分析】",
        node_name="Timing Analyst",
        execution_order=10,
    ),
    "position_analyst": AgentMetadata(
        id="position_analyst",
        name="仓位分析师",
        description="分析仓位控制和加减仓策略的合理性",
        category=AgentCategory.ANALYST,
        icon="📊",
        color="#3498db",
        tags=["复盘", "仓位", "资金管理"],
        tools=[
            "get_stock_market_data_unified",
            "get_trade_records",
            "build_trade_info",
            "get_account_info",
            "get_market_snapshot_for_review"
        ],
        default_tools=[
            "build_trade_info",
            "get_account_info"
        ],
        max_tool_calls=5,
        requires_tools=False,
        output_field="position_analysis",
        report_label="【仓位分析】",
        node_name="Position Analyst",
        execution_order=20,
    ),
    "emotion_analyst": AgentMetadata(
        id="emotion_analyst",
        name="情绪分析师",
        description="分析交易中的情绪化操作和纪律执行情况",
        category=AgentCategory.ANALYST,
        icon="🧠",
        color="#9b59b6",
        tags=["复盘", "情绪", "纪律"],
        tools=[
            "get_stock_news_unified",
            "get_stock_sentiment_unified",
            "get_trade_records",
            "build_trade_info",
            "get_account_info"
        ],
        default_tools=[
            "build_trade_info",
            "get_account_info"
        ],
        max_tool_calls=5,
        requires_tools=True,
        output_field="emotion_analysis",
        report_label="【情绪分析】",
        node_name="Emotion Analyst",
        execution_order=30,
    ),
    "attribution_analyst": AgentMetadata(
        id="attribution_analyst",
        name="归因分析师",
        description="分析收益来源，区分大盘/行业/个股Alpha贡献",
        category=AgentCategory.ANALYST,
        icon="🎯",
        color="#1abc9c",
        tags=["复盘", "归因", "Alpha"],
        tools=[
            "get_stock_market_data_unified",
            "get_china_market_overview",
            "get_trade_records",
            "build_trade_info",
            "get_market_snapshot_for_review"
        ],
        default_tools=[
            "get_stock_market_data_unified",
            "build_trade_info"
        ],
        max_tool_calls=5,
        requires_tools=False,
        output_field="attribution_analysis",
        report_label="【归因分析】",
        node_name="Attribution Analyst",
        execution_order=40,
    ),
    "review_manager": AgentMetadata(
        id="review_manager",
        name="复盘总结师",
        description="综合所有分析维度，生成完整复盘报告和改进建议",
        category=AgentCategory.MANAGER,
        icon="📝",
        color="#2c3e50",
        tags=["复盘", "总结", "建议"],
        tools=[
            "get_trade_records",
            "build_trade_info",
            "get_account_info",
            "get_market_snapshot_for_review"
        ],
        default_tools=[
            "build_trade_info",
            "get_account_info"
        ],
        max_tool_calls=5,
        requires_tools=True,
        output_field="review_summary",
        report_label="【复盘总结】",
        node_name="Review Manager",
        execution_order=100,
    ),
    # ==================== 持仓分析 Agent ====================
    "pa_technical": AgentMetadata(
        id="pa_technical",
        name="持仓技术面分析师",
        description="分析K线走势、技术指标、支撑阻力位，评估技术面状态",
        category=AgentCategory.ANALYST,
        icon="📈",
        color="#2ecc71",
        tags=["持仓分析", "技术面", "趋势"],
        tools=["get_stock_market_data_unified", "get_technical_indicators"],
        max_tool_calls=3,
        requires_tools=False,
        output_field="technical_analysis",
        report_label="【技术面分析】",
        node_name="Technical Analyst",
        execution_order=10,
    ),
    "pa_fundamental": AgentMetadata(
        id="pa_fundamental",
        name="持仓基本面分析师",
        description="分析财务数据、估值水平、行业地位，评估基本面价值",
        category=AgentCategory.ANALYST,
        icon="📊",
        color="#3498db",
        tags=["持仓分析", "基本面", "估值"],
        tools=["get_stock_fundamentals_unified", "get_stock_news_unified"],
        max_tool_calls=3,
        requires_tools=False,
        output_field="fundamental_analysis",
        report_label="【基本面分析】",
        node_name="Fundamental Analyst",
        execution_order=20,
    ),
    "pa_risk": AgentMetadata(
        id="pa_risk",
        name="持仓风险评估师",
        description="评估持仓风险、设置止损止盈、分析仓位合理性",
        category=AgentCategory.ANALYST,
        icon="⚠️",
        color="#e74c3c",
        tags=["持仓分析", "风险", "止损"],
        tools=["get_stock_market_data_unified", "get_china_market_overview", "get_stock_sentiment_unified"],
        max_tool_calls=3,
        requires_tools=False,
        output_field="risk_analysis",
        report_label="【风险评估】",
        node_name="Risk Assessor",
        execution_order=30,
    ),
    "pa_advisor": AgentMetadata(
        id="pa_advisor",
        name="持仓操作建议师",
        description="综合技术面、基本面、风险评估，给出持仓操作建议",
        category=AgentCategory.MANAGER,
        icon="💡",
        color="#9b59b6",
        tags=["持仓分析", "建议", "决策"],
        tools=[],
        max_tool_calls=0,
        requires_tools=False,
        output_field="action_advice",
        report_label="【操作建议】",
        node_name="Action Advisor",
        execution_order=100,
        # 🆕 读取其他 Agent 的输出
        reads_from=["technical_analysis", "fundamental_analysis", "risk_analysis"],
    ),
    # 🆕 v2.0 架构的 Agent
    "market_analyst_v2": AgentMetadata(
        id="market_analyst_v2",
        name="市场分析师 v2",
        description="v2.0 架构的市场分析师，支持动态工具绑定",
        category=AgentCategory.ANALYST,
        icon="📈",
        color="#2ecc71",
        tags=["技术分析", "市场数据", "v2.0"],
        tools=["get_stock_market_data_unified"],
        default_tools=["get_stock_market_data_unified"],
        max_tool_calls=3,
        inputs=[
            AgentInput(name="ticker", type="string", description="股票代码"),
            AgentInput(name="start_date", type="string", description="开始日期"),
            AgentInput(name="end_date", type="string", description="结束日期"),
        ],
        outputs=[
            AgentOutput(name="market_analysis", type="string", description="市场分析报告"),
        ],
        requires_tools=True,
        output_field="market_analysis",
        report_label="【市场分析 v2】",
        node_name="Market Analyst v2",
        execution_order=10,
    ),
    "fundamentals_analyst_v2": AgentMetadata(
        id="fundamentals_analyst_v2",
        name="基本面分析师 v2",
        description="v2.0 架构的基本面分析师，支持动态工具绑定",
        category=AgentCategory.ANALYST,
        icon="📊",
        color="#3498db",
        tags=["基本面", "财务分析", "v2.0"],
        tools=["get_stock_fundamentals_unified"],
        default_tools=["get_stock_fundamentals_unified"],
        max_tool_calls=3,
        inputs=[
            AgentInput(name="ticker", type="string", description="股票代码"),
            AgentInput(name="analysis_date", type="string", description="分析日期"),
        ],
        outputs=[
            AgentOutput(name="fundamentals_report", type="string", description="基本面分析报告"),
        ],
        requires_tools=True,
        output_field="fundamentals_report",
        report_label="【基本面分析 v2】",
        node_name="Fundamentals Analyst v2",
        execution_order=40,
    ),
    "news_analyst_v2": AgentMetadata(
        id="news_analyst_v2",
        name="新闻分析师 v2",
        description="v2.0 架构的新闻分析师，支持动态工具绑定",
        category=AgentCategory.ANALYST,
        icon="📰",
        color="#9b59b6",
        tags=["新闻", "事件驱动", "v2.0"],
        tools=["get_stock_news_unified"],
        default_tools=["get_stock_news_unified"],
        max_tool_calls=3,
        inputs=[
            AgentInput(name="ticker", type="string", description="股票代码"),
            AgentInput(name="analysis_date", type="string", description="分析日期"),
        ],
        outputs=[
            AgentOutput(name="news_report", type="string", description="新闻分析报告"),
        ],
        requires_tools=True,
        output_field="news_report",
        report_label="【新闻分析 v2】",
        node_name="News Analyst v2",
        execution_order=30,
    ),
    "social_analyst_v2": AgentMetadata(
        id="social_analyst_v2",
        name="社交媒体分析师 v2",
        description="v2.0 架构的社交媒体分析师，支持动态工具绑定",
        category=AgentCategory.ANALYST,
        icon="💬",
        color="#e74c3c",
        tags=["情绪分析", "舆情", "v2.0"],
        tools=["get_stock_sentiment_unified"],
        default_tools=["get_stock_sentiment_unified"],
        max_tool_calls=3,
        inputs=[
            AgentInput(name="ticker", type="string", description="股票代码"),
            AgentInput(name="analysis_date", type="string", description="分析日期"),
        ],
        outputs=[
            AgentOutput(name="sentiment_report", type="string", description="社交媒体情绪分析报告"),
        ],
        requires_tools=True,
        output_field="sentiment_report",
        report_label="【舆情分析 v2】",
        node_name="Social Analyst v2",
        execution_order=20,
    ),
    "index_analyst_v2": AgentMetadata(
        id="index_analyst_v2",
        name="大盘分析师 v2.0",
        description="分析大盘指数走势，评估市场整体环境、资金流向和技术面",
        category=AgentCategory.ANALYST,
        version="2.0.0",
        license_tier=LicenseTier.FREE,
        default_tools=[
            "get_index_data",           # 指数走势和均线
            "get_market_breadth",       # 市场宽度（成交量、市值）
            "get_market_environment",   # 市场环境（估值、波动率）
            "identify_market_cycle",    # 市场周期识别
            "get_north_flow",           # 北向资金流向
            "get_margin_trading",       # 两融余额
            "get_limit_stats",          # 涨跌停统计
            "get_index_technical",      # 技术指标（MACD/RSI/KDJ）
        ],
        inputs=[
            AgentInput(name="ticker", type="string", description="股票代码"),
            AgentInput(name="analysis_date", type="string", description="分析日期"),
        ],
        outputs=[
            AgentOutput(name="index_report", type="string", description="大盘分析报告"),
        ],
        requires_tools=True,
        output_field="index_report",
        report_label="【大盘分析 v2】",
        node_name="Index Analyst v2",
        execution_order=1,  # 最先执行
    ),
}

