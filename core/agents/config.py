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
    TRADER = "trader"         # 研究整合员
    RISK = "risk"             # 风险评估
    MANAGER = "manager"       # 管理者
    POST_PROCESSOR = "post_processor"  # 后处理器


class LicenseTier(str, Enum):
    """许可证级别"""
    FREE = "free"           # 免费版
    BASIC = "basic"         # 基础版
    PRO = "pro"             # 专业版
    ENTERPRISE = "enterprise"  # 企业版


class GrowthRole(str, Enum):
    """成长角色声明"""
    NONE = "none"
    EXTRACTOR = "extractor"
    REVIEWER = "reviewer"
    OPTIMIZER = "optimizer"


class GrowthMemoryScope(str, Enum):
    """成长产物的记忆范围提示"""
    NONE = "none"
    OBJECT_TRACKING = "object_tracking"
    PATTERN = "pattern"
    RESEARCH_ASSET = "research_asset"


class GrowthReviewLevel(str, Enum):
    """成长产物的审核等级"""
    AUTO_PENDING = "auto_pending"
    MANUAL_REQUIRED = "manual_required"


class GrowthSourceType(str, Enum):
    """成长产物来源类型"""
    NONE = "none"
    ANALYSIS_REPORT = "analysis_report"
    REVIEW_REPORT = "review_report"
    MANAGER_DECISION = "manager_decision"


class AgentMaturityLevel(str, Enum):
    """Agent 平台成熟度等级"""
    EXPERIMENTAL = "experimental"
    INTERNAL = "internal"
    STABLE = "stable"


class AgentInputMode(str, Enum):
    """Agent 输入模式声明"""
    STANDALONE = "standalone"
    UPSTREAM_DEPENDENT = "upstream-dependent"
    MIXED = "mixed"


class AgentDebugReplayMode(str, Enum):
    """Agent 调试重放模式"""
    DIRECT = "direct"
    REQUIRES_EXTRA_STATE = "requires_extra_state"
    REQUIRES_CHAIN_PREFILL = "requires_chain_prefill"


class AgentMaintenanceStatus(str, Enum):
    """Agent 维护状态声明"""
    MAINTAINED = "maintained"
    UNMAINTAINED = "unmaintained"
    DEPRECATED = "deprecated"  # 🔥 新增：已废弃，不应被新代码引用


class AgentInputSource(str, Enum):
    """Agent 输入来源声明"""
    REQUEST = "request"
    STATE = "state"
    CONTEXT = "context"


class AgentInput(BaseModel):
    """智能体输入定义"""
    name: str
    type: str  # string, number, boolean, object, array
    description: str
    required: bool = True
    default: Optional[Any] = None
    source: AgentInputSource = AgentInputSource.REQUEST
    state_field: Optional[str] = None
    source_state_fields: List[str] = Field(default_factory=list)
    producer_hint: Optional[str] = None


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
    show_in_reports: bool = True      # 是否在分析结果报告列表中展示此 agent 的输出
    node_name: str = ""               # 工作流节点名称，如 "Market Analyst"
    execution_order: int = 100        # 执行顺序（越小越先执行）
    workflow_stage: str = ""          # 工作流阶段：analyst/research/risk/manager/trader

    # 🆕 成长能力声明
    growth_role: GrowthRole = GrowthRole.NONE
    growth_outputs: List[str] = Field(default_factory=list)
    memory_scope_hint: GrowthMemoryScope = GrowthMemoryScope.NONE
    review_level: GrowthReviewLevel = GrowthReviewLevel.MANUAL_REQUIRED
    growth_source_type: GrowthSourceType = GrowthSourceType.NONE

    # 🆕 平台治理声明
    maturity_level: AgentMaturityLevel = AgentMaturityLevel.STABLE
    input_mode: AgentInputMode = AgentInputMode.STANDALONE
    debug_replay_mode: AgentDebugReplayMode = AgentDebugReplayMode.DIRECT
    maintenance_status: AgentMaintenanceStatus = AgentMaintenanceStatus.MAINTAINED
    callable_surfaces: List[str] = Field(default_factory=lambda: ["assistant", "workflow", "agent"])

    class Config:
        use_enum_values = True


class AgentConfig(BaseModel):
    """
    智能体运行时配置
    
    注意：llm_provider 和 llm_model 字段已废弃，不应使用。
    LLM 的 provider 和 model 应该由分析流程指定，而不是 Agent 配置。
    这些字段保留是为了向后兼容，但会在创建 Agent 时被排除。
    """
    # LLM 配置（已废弃，不应使用）
    llm_provider: Optional[str] = None  # 🔥 改为 Optional，默认 None，避免误导
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
        maintenance_status=AgentMaintenanceStatus.DEPRECATED,  # 🔥 v1 已废弃，请使用 v2 版本
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
        node_name="市场分析师",
        execution_order=10,
        workflow_stage="analyst",  # 🔥 新增：分析师阶段
    ),
    "fundamentals_analyst": AgentMetadata(
        id="fundamentals_analyst",
        name="基本面分析师",
        description="分析公司财务数据和基本面指标",
        category=AgentCategory.ANALYST,
        maintenance_status=AgentMaintenanceStatus.DEPRECATED,  # 🔥 v1 已废弃，请使用 v2 版本
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
        node_name="基本面分析师",
        execution_order=40,
        workflow_stage="analyst",  # 🔥 新增：分析师阶段
    ),
    "news_analyst": AgentMetadata(
        id="news_analyst",
        name="新闻分析师",
        description="分析财经新闻和事件影响",
        category=AgentCategory.ANALYST,
        maintenance_status=AgentMaintenanceStatus.DEPRECATED,  # 🔥 v1 已废弃，请使用 v2 版本
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
        node_name="新闻分析师",
        execution_order=30,
        workflow_stage="analyst",  # 🔥 新增：分析师阶段
    ),
    "social_analyst": AgentMetadata(
        id="social_analyst",
        name="社交媒体分析师",
        description="分析社交媒体情绪和舆论",
        category=AgentCategory.ANALYST,
        maintenance_status=AgentMaintenanceStatus.DEPRECATED,  # 🔥 v1 已废弃，请使用 v2 版本
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
        node_name="社交媒体分析师",
        execution_order=20,
        workflow_stage="analyst",  # 🔥 新增：分析师阶段
    ),
    "sector_analyst": AgentMetadata(
        id="sector_analyst",
        name="行业/板块分析师",
        description="分析行业趋势、板块轮动和行业对比",
        category=AgentCategory.ANALYST,
        maintenance_status=AgentMaintenanceStatus.DEPRECATED,  # 🔥 v1 已废弃，请使用 v2 版本
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
        node_name="板块分析师",
        execution_order=5,  # 在技术分析之前
        workflow_stage="analyst",  # 🔥 新增：分析师阶段
    ),
    "index_analyst": AgentMetadata(
        id="index_analyst",
        name="大盘/指数分析师",
        description="分析大盘指数、市场环境和系统性风险",
        category=AgentCategory.ANALYST,
        maintenance_status=AgentMaintenanceStatus.DEPRECATED,  # 🔥 v1 已废弃，请使用 v2 版本
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
        node_name="大盘分析师",
        execution_order=1,  # 最先执行
        workflow_stage="analyst",  # 🔥 新增：分析师阶段
    ),
    "bull_researcher": AgentMetadata(
        id="bull_researcher",
        name="积极证据研究员",
        description="从积极角度整理支持乐观解读的研究证据（输出研究观察，不构成投资建议）",
        category=AgentCategory.RESEARCHER,
        maintenance_status=AgentMaintenanceStatus.DEPRECATED,  # 🔥 v1 已废弃，请使用 v2 版本
        icon="🐂",
        color="#27ae60",
        tags=["积极", "证据"],
        tools=[],  # 研究员不直接调用工具，基于分析师报告
        max_tool_calls=0,
        workflow_stage="research",  # 🔥 新增：研究阶段
    ),
    "bear_researcher": AgentMetadata(
        id="bear_researcher",
        name="谨慎证据研究员",
        description="从谨慎角度整理支持审慎解读的研究证据（输出研究观察，不构成投资建议）",
        category=AgentCategory.RESEARCHER,
        maintenance_status=AgentMaintenanceStatus.DEPRECATED,  # 🔥 v1 已废弃，请使用 v2 版本
        icon="🐻",
        color="#c0392b",
        tags=["谨慎", "证据"],
        tools=[],
        max_tool_calls=0,
        workflow_stage="research",  # 🔥 新增：研究阶段
    ),
    "trader": AgentMetadata(
        id="trader",
        name="研究整合员",
        description="综合各维度研究证据，整理形成研究观察汇总（不构成投资建议）",
        category=AgentCategory.TRADER,
        maintenance_status=AgentMaintenanceStatus.DEPRECATED,  # 🔥 v1 已废弃，请使用 v2 版本
        icon="💰",
        color="#f1c40f",
        tags=["整合", "观察"],
        tools=[],
        max_tool_calls=0,
        workflow_stage="trader",  # 🔥 新增：研究整合阶段
    ),
    "position_advisor": AgentMetadata(
        id="position_advisor",
        name="持仓研究师",
        description="基于单股分析报告和持仓信息，整理持仓研究观察事项（不构成投资建议）",
        category=AgentCategory.TRADER,
        maintenance_status=AgentMaintenanceStatus.DEPRECATED,  # 🔥 v1 已废弃，请使用 v2 版本
        icon="💼",
        color="#2980b9",
        tags=["持仓", "研究观察", "风险评估"],
        tools=[],
        max_tool_calls=0,
        requires_tools=False,
        workflow_stage="trader",  # 🔥 新增：研究整合阶段
    ),
    "risky_analyst": AgentMetadata(
        id="risky_analyst",
        name="高弹性情景分析师",
        description="整理高弹性情景下的研究证据，关注潜在收益空间（输出研究观察，不构成投资建议）",
        category=AgentCategory.RISK,
        maintenance_status=AgentMaintenanceStatus.DEPRECATED,  # 🔥 v1 已废弃，请使用 v2 版本
        icon="🔥",
        color="#e74c3c",
        tags=["情景", "高弹性", "研究"],
        tools=[],
        max_tool_calls=0,
        workflow_stage="risk",  # 🔥 新增：风险研究阶段
    ),
    "safe_analyst": AgentMetadata(
        id="safe_analyst",
        name="防御情景分析师",
        description="整理防御情景下的研究证据，关注资本保护因素（输出研究观察，不构成投资建议）",
        category=AgentCategory.RISK,
        maintenance_status=AgentMaintenanceStatus.DEPRECATED,  # 🔥 v1 已废弃，请使用 v2 版本
        icon="🛡️",
        color="#27ae60",
        tags=["情景", "防御", "研究"],
        tools=[],
        max_tool_calls=0,
        workflow_stage="risk",  # 🔥 新增：风险研究阶段
    ),
    "neutral_analyst": AgentMetadata(
        id="neutral_analyst",
        name="基准情景分析师",
        description="整理基准情景下的研究证据，平衡多种视角（输出研究观察，不构成投资建议）",
        category=AgentCategory.RISK,
        maintenance_status=AgentMaintenanceStatus.DEPRECATED,  # 🔥 v1 已废弃，请使用 v2 版本
        icon="⚖️",
        color="#3498db",
        tags=["情景", "基准", "平衡"],
        tools=[],
        max_tool_calls=0,
        workflow_stage="risk",  # 🔥 新增：风险研究阶段
    ),
    "risk_manager": AgentMetadata(
        id="risk_manager",
        name="风险评估师",
        description="综合各情景研究证据，整理风险研究观察汇总（不构成投资建议）",
        category=AgentCategory.MANAGER,
        maintenance_status=AgentMaintenanceStatus.DEPRECATED,  # 🔥 v1 已废弃，请使用 v2 版本
        icon="👨‍⚖️",
        color="#9b59b6",
        tags=["风险", "研究", "评估"],
        tools=[],
        max_tool_calls=0,
        workflow_stage="manager",  # 🔥 新增：评估阶段
    ),
    "research_manager": AgentMetadata(
        id="research_manager",
        name="研究整合员",
        description="综合多视角研究证据，整理形成研究观察汇总（不构成投资建议）",
        category=AgentCategory.MANAGER,
        maintenance_status=AgentMaintenanceStatus.DEPRECATED,  # 🔥 v1 已废弃，请使用 v2 版本
        icon="👔",
        color="#9b59b6",
        tags=["整合", "研究", "观察"],
        tools=[],
        max_tool_calls=0,
        workflow_stage="manager",  # 🔥 新增：评估阶段
    ),
    # ==================== 交易复盘 Agent ====================
    "timing_analyst": AgentMetadata(
        id="timing_analyst",
        name="时机研究师",
        description="分析入场与退出时机，评估交易时机选择的研究观察（不构成投资建议）",
        category=AgentCategory.ANALYST,
        maintenance_status=AgentMaintenanceStatus.DEPRECATED,  # 🔥 v1 已废弃，请使用 v2 版本
        icon="⏰",
        color="#e67e22",
        tags=["复盘", "时机", "研究"],
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
        node_name="时机分析师",
        execution_order=10,
        workflow_stage="analyst",  # 🔥 新增：分析师阶段（复盘流程）
    ),
    "position_analyst": AgentMetadata(
        id="position_analyst",
        name="仓位分析师",
        description="分析仓位管理的研究观察，不输出加减仓等执行建议",
        category=AgentCategory.ANALYST,
        maintenance_status=AgentMaintenanceStatus.DEPRECATED,  # 🔥 v1 已废弃，请使用 v2 版本
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
        node_name="仓位分析师",
        execution_order=20,
        workflow_stage="analyst",  # 🔥 新增：分析师阶段（复盘流程）
    ),
    "emotion_analyst": AgentMetadata(
        id="emotion_analyst",
        name="情绪分析师",
        description="分析交易中的情绪化操作和纪律执行情况",
        category=AgentCategory.ANALYST,
        maintenance_status=AgentMaintenanceStatus.DEPRECATED,  # 🔥 v1 已废弃，请使用 v2 版本
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
        node_name="情绪分析师",
        execution_order=30,
        workflow_stage="analyst",  # 🔥 新增：分析师阶段（复盘流程）
    ),
    "attribution_analyst": AgentMetadata(
        id="attribution_analyst",
        name="归因分析师",
        description="分析收益来源，区分大盘/行业/个股Alpha贡献",
        category=AgentCategory.ANALYST,
        maintenance_status=AgentMaintenanceStatus.DEPRECATED,  # 🔥 v1 已废弃，请使用 v2 版本
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
        node_name="归因分析师",
        execution_order=40,
        workflow_stage="analyst",  # 🔥 新增：分析师阶段（复盘流程）
    ),
    "review_manager": AgentMetadata(
        id="review_manager",
        name="复盘总结师",
        description="综合所有分析维度，生成完整复盘报告和改进建议",
        category=AgentCategory.MANAGER,
        maintenance_status=AgentMaintenanceStatus.DEPRECATED,  # 🔥 v1 已废弃，请使用 v2 版本
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
        node_name="复盘总结师",
        execution_order=100,
        workflow_stage="manager",  # 🔥 新增：经理阶段（复盘流程）
    ),
    # ==================== 持仓分析 Agent ====================
    "pa_technical": AgentMetadata(
        id="pa_technical",
        name="持仓技术面分析师",
        description="分析K线走势、技术指标、支撑阻力位，评估技术面状态",
        category=AgentCategory.ANALYST,
        maintenance_status=AgentMaintenanceStatus.DEPRECATED,  # 🔥 v1 已废弃，请使用 v2 版本
        icon="📈",
        color="#2ecc71",
        tags=["持仓分析", "技术面", "趋势"],
        tools=["get_stock_market_data_unified", "get_technical_indicators"],
        max_tool_calls=3,
        requires_tools=False,
        output_field="technical_analysis",
        report_label="【技术面分析】",
        node_name="技术面分析师",
        execution_order=10,
        workflow_stage="analyst",  # 🔥 新增：分析师阶段（持仓分析流程）
    ),
    "pa_fundamental": AgentMetadata(
        id="pa_fundamental",
        name="持仓基本面分析师",
        description="分析财务数据、估值水平、行业地位，评估基本面价值",
        category=AgentCategory.ANALYST,
        maintenance_status=AgentMaintenanceStatus.DEPRECATED,  # 🔥 v1 已废弃，请使用 v2 版本
        icon="📊",
        color="#3498db",
        tags=["持仓分析", "基本面", "估值"],
        tools=["get_stock_fundamentals_unified", "get_stock_news_unified"],
        max_tool_calls=3,
        requires_tools=False,
        output_field="fundamental_analysis",
        report_label="【基本面分析】",
        node_name="基本面分析师",
        execution_order=20,
        workflow_stage="analyst",  # 🔥 新增：分析师阶段（持仓分析流程）
    ),
    "pa_risk": AgentMetadata(
        id="pa_risk",
        name="持仓风险评估师",
        description="评估持仓风险、分析仓位合理性、提供风险关注与收益关注参考",
        category=AgentCategory.ANALYST,
        maintenance_status=AgentMaintenanceStatus.DEPRECATED,  # 🔥 v1 已废弃，请使用 v2 版本
        icon="⚠️",
        color="#e74c3c",
        tags=["持仓分析", "风险", "止损"],
        tools=["get_stock_market_data_unified", "get_china_market_overview", "get_stock_sentiment_unified"],
        max_tool_calls=3,
        requires_tools=False,
        output_field="risk_analysis",
        report_label="【风险评估】",
        node_name="风险评估师",
        execution_order=30,
        workflow_stage="analyst",  # 🔥 新增：分析师阶段（持仓分析流程）
    ),
    "pa_advisor": AgentMetadata(
        id="pa_advisor",
        name="持仓研究整合师",
        description="综合技术面、基本面、风险评估，整理持仓研究观察汇总（不构成投资建议）",
        category=AgentCategory.MANAGER,
        maintenance_status=AgentMaintenanceStatus.DEPRECATED,  # 🔥 v1 已废弃，请使用 v2 版本
        icon="💡",
        color="#9b59b6",
        tags=["持仓分析", "研究", "观察"],
        tools=[],
        max_tool_calls=0,
        requires_tools=False,
        output_field="action_advice",
        report_label="【持仓研究观察】",
        node_name="持仓研究整合师",
        execution_order=100,
        # 🆕 读取其他 Agent 的输出
        reads_from=["technical_analysis", "fundamental_analysis", "risk_analysis"],
        workflow_stage="manager",  # 🔥 新增：研究阶段（持仓分析流程）
    ),
    # 🆕 v2.0 架构的 Agent
    "market_analyst_v2": AgentMetadata(
        id="market_analyst_v2",
        name="市场分析师 v2",
        description="分析股票价格走势、技术指标和市场数据，生成技术分析报告",
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
        node_name="市场分析师 v2",
        execution_order=10,
        growth_role="extractor",
        growth_outputs=["market_analysis"],
        memory_scope_hint="object_tracking",
        review_level="auto_pending",
        growth_source_type="analysis_report",
    ),
    "fundamentals_analyst_v2": AgentMetadata(
        id="fundamentals_analyst_v2",
        name="基本面分析师 v2",
        description="分析公司财务数据、盈利能力、成长性和基本面指标，涵盖护城河/竞争优势评估和管理层质量分析",
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
        node_name="基本面分析师 v2",
        execution_order=40,
        growth_role="extractor",
        growth_outputs=["fundamentals_report"],
        memory_scope_hint="object_tracking",
        review_level="auto_pending",
        growth_source_type="analysis_report",
    ),
    "etf_analyst_v2": AgentMetadata(
        id="etf_analyst_v2",
        name="ETF 分析师 v2",
        description="分析 ETF 净值、规模、费率、跟踪误差等。ETF 无 PE/PB/ROE，使用净值、规模、跟踪指数等指标。",
        category=AgentCategory.ANALYST,
        icon="📈",
        color="#27ae60",
        tags=["ETF", "基金", "净值", "v2.0"],
        tools=["get_etf_fundamentals"],
        default_tools=["get_etf_fundamentals"],
        max_tool_calls=3,
        inputs=[
            AgentInput(name="ticker", type="string", description="ETF 代码"),
            AgentInput(name="analysis_date", type="string", description="分析日期"),
        ],
        outputs=[
            AgentOutput(name="fundamentals_report", type="string", description="ETF 分析报告（复用 fundamentals_report 字段）"),
        ],
        requires_tools=True,
        output_field="fundamentals_report",
        report_label="【ETF 分析 v2】",
        node_name="ETF 分析师 v2",
        execution_order=40,
        growth_role="extractor",
        growth_outputs=["fundamentals_report"],
        memory_scope_hint="object_tracking",
        review_level="auto_pending",
        growth_source_type="analysis_report",
    ),
    "news_analyst_v2": AgentMetadata(
        id="news_analyst_v2",
        name="新闻分析师 v2",
        description="分析财经新闻、公告和事件对股票的影响，评估消息面驱动因素和市场情绪变化",
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
        node_name="新闻分析师 v2",
        execution_order=30,
        growth_role="extractor",
        growth_outputs=["news_report"],
        memory_scope_hint="object_tracking",
        review_level="manual_required",
        growth_source_type="analysis_report",
    ),
    "social_analyst_v2": AgentMetadata(
        id="social_analyst_v2",
        name="社交媒体分析师 v2",
        description="分析社交媒体情绪、舆论趋势和投资者关注度，评估非理性因素对股价的潜在影响",
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
        node_name="社交媒体分析师 v2",
        execution_order=20,
        growth_role="extractor",
        growth_outputs=["sentiment_report"],
        memory_scope_hint="object_tracking",
        review_level="manual_required",
        growth_source_type="analysis_report",
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
        node_name="大盘分析师 v2",
        execution_order=1,  # 最先执行
        growth_role="extractor",
        growth_outputs=["index_report"],
        memory_scope_hint="object_tracking",
        review_level="auto_pending",
        growth_source_type="analysis_report",
    ),

    # 🆕 筹码分布分析师 Agent
    "chip_distribution_analyst_v2": AgentMetadata(
        id="chip_distribution_analyst_v2",
        name="筹码分布分析师 v2.0",
        description="分析股票筹码分布，评估获利比例、平均成本和筹码集中度，生成筹码分布分析报告",
        category=AgentCategory.ANALYST,
        version="2.0.0",
        license_tier=LicenseTier.FREE,
        icon="🧮",
        color="#e74c3c",
        tags=["筹码分布", "持仓成本", "获利比例", "v2.0"],
        tools=["get_chip_distribution"],
        default_tools=["get_chip_distribution"],
        max_tool_calls=3,
        inputs=[
            AgentInput(name="ticker", type="string", description="股票代码"),
            AgentInput(name="analysis_date", type="string", description="分析日期"),
        ],
        outputs=[
            AgentOutput(name="chip_report", type="string", description="筹码分布分析报告"),
        ],
        requires_tools=True,
        output_field="chip_report",
        report_label="【筹码分布分析 v2】",
        node_name="筹码分布分析师 v2",
        execution_order=15,
    ),

    # 🆕 估值分析师 Agent
    "valuation_analyst_v2": AgentMetadata(
        id="valuation_analyst_v2",
        name="估值分析师 v2.0",
        description="分析股票估值水平，包括PE/PB/PS/PEG等指标、历史估值区间、同行业估值对比，评估当前估值合理性并给出合理估值区间",
        category=AgentCategory.ANALYST,
        version="2.0.0",
        license_tier=LicenseTier.FREE,
        icon="💎",
        color="#9b59b6",
        tags=["估值分析", "PE/PB", "DCF", "相对估值", "v2.0"],
        tools=["get_stock_fundamentals_unified", "get_industry_valuation_comparison", "get_historical_valuation_range"],
        default_tools=["get_stock_fundamentals_unified"],
        max_tool_calls=5,
        inputs=[
            AgentInput(name="ticker", type="string", description="股票代码"),
            AgentInput(name="analysis_date", type="string", description="分析日期"),
            AgentInput(name="valuation_method", type="string", description="估值方法（PE/PB/DCF/综合）", required=False, default="综合"),
        ],
        outputs=[
            AgentOutput(name="valuation_report", type="string", description="估值分析报告"),
            AgentOutput(name="fair_value_range", type="object", description="合理估值区间（低/中/高）"),
            AgentOutput(name="valuation_rating", type="string", description="估值评级（低估/合理/高估）"),
        ],
        requires_tools=True,
        output_field="valuation_report",
        report_label="【估值分析 v2】",
        node_name="估值分析师 v2",
        execution_order=45,  # 在基本面分析之后
        growth_role="extractor",
        growth_outputs=["valuation_report"],
        memory_scope_hint="object_tracking",
        review_level="auto_pending",
        growth_source_type="analysis_report",
    ),

    # ── v2.0 单股分析扩展：板块/辩论/决策 ──────────────────────────────

    "sector_analyst_v2": AgentMetadata(
        id="sector_analyst_v2",
        name="板块分析师 v2.0",
        description="分析行业趋势、板块轮动和同业对比，提炼结构变化与风险来源",
        category=AgentCategory.ANALYST,
        version="2.0.0",
        license_tier=LicenseTier.FREE,
        default_tools=["get_sector_analysis"],
        inputs=[
            AgentInput(name="ticker", type="string", description="股票代码"),
            AgentInput(name="analysis_date", type="string", description="分析日期"),
        ],
        outputs=[
            AgentOutput(name="sector_report", type="string", description="板块分析报告"),
        ],
        requires_tools=True,
        output_field="sector_report",
        report_label="【板块分析 v2】",
        node_name="板块分析师 v2",
        execution_order=5,
    ),

    "bull_researcher_v2": AgentMetadata(
        id="bull_researcher_v2",
        name="乐观情景研究员 v2.0",
        description="基于现有材料构建偏乐观但克制的研究论证，提炼成立前提、证据链与观察信号",
        category=AgentCategory.RESEARCHER,
        version="2.0.0",
        license_tier=LicenseTier.FREE,
        default_tools=[],
        inputs=[
            AgentInput(name="ticker", type="string", description="股票代码"),
            AgentInput(name="analysis_date", type="string", description="分析日期"),
            AgentInput(name="market_report", type="string", description="市场分析报告", required=False),
            AgentInput(name="news_report", type="string", description="新闻分析报告", required=False),
            AgentInput(name="fundamentals_report", type="string", description="基本面分析报告", required=False),
        ],
        outputs=[
            AgentOutput(name="bull_report", type="string", description="乐观情景研究报告"),
        ],
        requires_tools=False,
        output_field="bull_report",
        report_label="【乐观情景研究 v2】",
        node_name="乐观情景研究员 v2",
        execution_order=80,
    ),

    "bear_researcher_v2": AgentMetadata(
        id="bear_researcher_v2",
        name="审慎情景研究员 v2.0",
        description="基于现有材料构建偏审慎的研究论证，提炼风险、脆弱点与判断边界",
        category=AgentCategory.RESEARCHER,
        version="2.0.0",
        license_tier=LicenseTier.FREE,
        default_tools=[],
        inputs=[
            AgentInput(name="ticker", type="string", description="股票代码"),
            AgentInput(name="analysis_date", type="string", description="分析日期"),
            AgentInput(name="market_report", type="string", description="市场分析报告", required=False),
            AgentInput(name="news_report", type="string", description="新闻分析报告", required=False),
            AgentInput(name="fundamentals_report", type="string", description="基本面分析报告", required=False),
        ],
        outputs=[
            AgentOutput(name="bear_report", type="string", description="审慎情景研究报告"),
        ],
        requires_tools=False,
        output_field="bear_report",
        report_label="【审慎情景研究 v2】",
        node_name="审慎情景研究员 v2",
        execution_order=85,
    ),

    "research_manager_v2": AgentMetadata(
        id="research_manager_v2",
        name="研究整合员 v2.0",
        description="综合乐观与审慎情景研究，整理形成平衡的研究观察汇总（不构成投资建议）",
        category=AgentCategory.MANAGER,
        version="2.0.0",
        license_tier=LicenseTier.FREE,
        default_tools=[],
        inputs=[
            AgentInput(name="ticker", type="string", description="股票代码"),
            AgentInput(name="analysis_date", type="string", description="分析日期"),
            AgentInput(name="bull_report", type="string", description="乐观情景研究报告"),
            AgentInput(name="bear_report", type="string", description="审慎情景研究报告"),
        ],
        outputs=[
            AgentOutput(name="investment_advice", type="string", description="平衡研究观察汇总"),
        ],
        requires_tools=False,
        output_field="investment_advice",
        report_label="【平衡研究观察 v2】",
        node_name="研究整合员 v2",
        execution_order=90,
    ),

    "trader_v2": AgentMetadata(
        id="trader_v2",
        name="研究整合员 v2.0",
        description="根据风险审阅后的综合研究证据，整理形成用户版研究简报（不构成投资建议）",
        category=AgentCategory.TRADER,
        version="2.0.0",
        license_tier=LicenseTier.FREE,
        default_tools=[],
        inputs=[
            AgentInput(name="ticker", type="string", description="股票代码"),
            AgentInput(name="analysis_date", type="string", description="分析日期"),
            AgentInput(name="investment_plan", type="string", description="综合研究观察汇总"),
            AgentInput(name="market_report", type="string", description="市场分析报告", required=False),
            AgentInput(name="fundamentals_report", type="string", description="基本面分析报告", required=False),
            AgentInput(name="news_report", type="string", description="新闻分析报告", required=False),
            AgentInput(name="sentiment_report", type="string", description="情绪分析报告", required=False),
            AgentInput(name="index_report", type="string", description="大盘分析报告", required=False),
            AgentInput(name="sector_report", type="string", description="板块分析报告", required=False),
            AgentInput(name="bull_report", type="string", description="乐观情景研究报告", required=False),
            AgentInput(name="bear_report", type="string", description="审慎情景研究报告", required=False),
        ],
        outputs=[
            AgentOutput(name="trader_investment_plan", type="string", description="用户版研究简报（研究观察汇总，不构成投资建议）"),
        ],
        requires_tools=False,
        output_field="trader_investment_plan",
        report_label="【研究简报 v2】",
        node_name="研究整合员 v2",
        execution_order=200,
    ),

    # ── v2.0 风险研判扩展 ──────────────────────────────────────────────

    "risky_analyst_v2": AgentMetadata(
        id="risky_analyst_v2",
        name="高弹性情景分析师 v2.0",
        description="从研究结论能否上修的角度审阅，识别强化催化、高要求前提与额外验证信号",
        category=AgentCategory.RISK,
        version="2.0.0",
        license_tier=LicenseTier.FREE,
        default_tools=[],
        inputs=[
            AgentInput(name="ticker", type="string", description="股票代码"),
            AgentInput(name="analysis_date", type="string", description="分析日期"),
            AgentInput(name="investment_plan", type="string", description="综合研究结论"),
            AgentInput(name="bull_opinion", type="string", description="乐观情景观点", required=False),
            AgentInput(name="bear_opinion", type="string", description="审慎情景观点", required=False),
        ],
        outputs=[
            AgentOutput(name="risky_opinion", type="string", description="高弹性情景观点"),
        ],
        requires_tools=False,
        output_field="risky_opinion",
        report_label="【高弹性风险评估 v2】",
        node_name="高弹性情景分析师 v2",
        execution_order=100,
    ),

    "safe_analyst_v2": AgentMetadata(
        id="safe_analyst_v2",
        name="防御情景分析师 v2.0",
        description="从研究结论最易失效的角度审阅，识别脆弱前提、风险来源与下修触发条件",
        category=AgentCategory.RISK,
        version="2.0.0",
        license_tier=LicenseTier.FREE,
        default_tools=[],
        inputs=[
            AgentInput(name="ticker", type="string", description="股票代码"),
            AgentInput(name="analysis_date", type="string", description="分析日期"),
            AgentInput(name="investment_plan", type="string", description="综合研究结论"),
            AgentInput(name="bull_opinion", type="string", description="乐观情景观点", required=False),
            AgentInput(name="bear_opinion", type="string", description="审慎情景观点", required=False),
        ],
        outputs=[
            AgentOutput(name="safe_opinion", type="string", description="防御情景观点"),
        ],
        requires_tools=False,
        output_field="safe_opinion",
        report_label="【防御风险评估 v2】",
        node_name="防御情景分析师 v2",
        execution_order=105,
    ),

    "neutral_analyst_v2": AgentMetadata(
        id="neutral_analyst_v2",
        name="基准情景分析师 v2.0",
        description="平衡乐观与审慎材料，判断当前最稳妥的基准情景，识别共识、冲突点与信息缺口",
        category=AgentCategory.RISK,
        version="2.0.0",
        license_tier=LicenseTier.FREE,
        default_tools=[],
        inputs=[
            AgentInput(name="ticker", type="string", description="股票代码"),
            AgentInput(name="analysis_date", type="string", description="分析日期"),
            AgentInput(name="investment_plan", type="string", description="综合研究结论"),
            AgentInput(name="risky_opinion", type="string", description="高弹性情景观点", required=False),
            AgentInput(name="safe_opinion", type="string", description="防御情景观点", required=False),
        ],
        outputs=[
            AgentOutput(name="neutral_opinion", type="string", description="基准情景观点"),
        ],
        requires_tools=False,
        output_field="neutral_opinion",
        report_label="【基准风险评估 v2】",
        node_name="基准情景分析师 v2",
        execution_order=110,
    ),

    "risk_manager_v2": AgentMetadata(
        id="risk_manager_v2",
        name="风险评估师 v2.0",
        description="主持稳健性审阅，综合多方观点，形成风险审阅后的综合研究结论（输出研究观察，不构成投资建议）",
        category=AgentCategory.MANAGER,
        version="2.0.0",
        license_tier=LicenseTier.FREE,
        default_tools=[],
        inputs=[
            AgentInput(name="ticker", type="string", description="股票代码"),
            AgentInput(name="analysis_date", type="string", description="分析日期"),
            AgentInput(name="investment_plan", type="string", description="综合研究结论"),
            AgentInput(name="risky_opinion", type="string", description="高弹性情景观点", required=False),
            AgentInput(name="safe_opinion", type="string", description="防御情景观点", required=False),
            AgentInput(name="neutral_opinion", type="string", description="基准情景观点", required=False),
        ],
        outputs=[
            AgentOutput(name="risk_assessment", type="string", description="稳健性审阅与风险研究观察"),
        ],
        requires_tools=False,
        output_field="risk_assessment",
        report_label="【风险研究结论 v2】",
        node_name="风险评估师 v2",
        execution_order=120,
    ),

    # ── v2.0 持仓分析 ──────────────────────────────────────────────────

    "pa_technical_v2": AgentMetadata(
        id="pa_technical_v2",
        name="技术面分析师 v2.0",
        description="分析持仓股票的技术面，包括K线形态、技术指标、支撑阻力位",
        category=AgentCategory.ANALYST,
        version="2.0.0",
        license_tier=LicenseTier.FREE,
        default_tools=["get_stock_market_data_unified"],
        inputs=[
            AgentInput(name="portfolio_data", type="string", description="持仓数据"),
        ],
        outputs=[
            AgentOutput(name="technical_analysis", type="string", description="技术面分析结果"),
        ],
        requires_tools=True,
        output_field="technical_analysis",
        node_name="技术面分析师 v2",
        execution_order=10,
        workflow_stage="analyst",
    ),

    "pa_fundamental_v2": AgentMetadata(
        id="pa_fundamental_v2",
        name="基本面分析师 v2.0",
        description="分析持仓股票的基本面，包括财务数据、估值水平、行业地位",
        category=AgentCategory.ANALYST,
        version="2.0.0",
        license_tier=LicenseTier.FREE,
        default_tools=[],
        inputs=[
            AgentInput(name="portfolio_data", type="string", description="持仓数据"),
        ],
        outputs=[
            AgentOutput(name="fundamental_analysis", type="string", description="基本面分析结果"),
        ],
        requires_tools=False,
        output_field="fundamental_analysis",
        node_name="基本面分析师 v2",
        execution_order=20,
        workflow_stage="analyst",
    ),

    "pa_risk_v2": AgentMetadata(
        id="pa_risk_v2",
        name="风险评估师 v2.0",
        description="评估持仓风险，包括风险敞口、风险情景与波动性分析",
        category=AgentCategory.ANALYST,
        version="2.0.0",
        license_tier=LicenseTier.FREE,
        default_tools=[],
        inputs=[
            AgentInput(name="portfolio_data", type="string", description="持仓数据"),
        ],
        outputs=[
            AgentOutput(name="risk_analysis", type="string", description="风险评估结果"),
        ],
        requires_tools=False,
        output_field="risk_analysis",
        node_name="风险评估师 v2",
        execution_order=30,
        workflow_stage="analyst",
    ),

    "pa_advisor_v2": AgentMetadata(
        id="pa_advisor_v2",
        name="持仓研究整合师 v2.0",
        description="综合各维度分析，整理形成持仓研究观察与关注事项（不构成投资建议）",
        category=AgentCategory.MANAGER,
        version="2.0.0",
        license_tier=LicenseTier.FREE,
        default_tools=[],
        inputs=[
            AgentInput(name="portfolio_data", type="string", description="持仓数据"),
            AgentInput(name="technical_analysis", type="string", description="技术面分析结果", required=False),
            AgentInput(name="fundamental_analysis", type="string", description="基本面分析结果", required=False),
            AgentInput(name="risk_analysis", type="string", description="风险评估结果", required=False),
        ],
        outputs=[
            AgentOutput(name="action_advice", type="string", description="持仓研究观察汇总"),
        ],
        requires_tools=False,
        output_field="action_advice",
        node_name="持仓研究整合师 v2",
        execution_order=100,
        workflow_stage="manager",
    ),

    # ── v2.0 复盘分析 ──────────────────────────────────────────────────

    "timing_analyst_v2": AgentMetadata(
        id="timing_analyst_v2",
        name="时机分析师 v2.0",
        description="复盘入场与退出依据，评估交易时机选择的合理性",
        category=AgentCategory.ANALYST,
        version="2.0.0",
        license_tier=LicenseTier.FREE,
        default_tools=[],
        inputs=[
            AgentInput(name="ticker", type="string", description="股票代码"),
            AgentInput(name="trade_records", type="string", description="交易记录"),
            AgentInput(name="trade_info", type="dict", description="交易信息详情", required=False),
            AgentInput(name="market_data", type="dict", description="市场行情数据", required=False),
            AgentInput(name="benchmark_data", type="dict", description="基准数据", required=False),
        ],
        outputs=[
            AgentOutput(name="timing_analysis", type="string", description="时机分析结果"),
        ],
        requires_tools=False,
        output_field="timing_analysis",
        node_name="时机分析师 v2",
        execution_order=10,
        workflow_stage="analyst",
    ),

    "position_analyst_v2": AgentMetadata(
        id="position_analyst_v2",
        name="仓位分析师 v2.0",
        description="复盘仓位控制与仓位变化依据的合理性",
        category=AgentCategory.ANALYST,
        version="2.0.0",
        license_tier=LicenseTier.FREE,
        default_tools=[],
        inputs=[
            AgentInput(name="ticker", type="string", description="股票代码"),
            AgentInput(name="trade_records", type="string", description="交易记录"),
            AgentInput(name="trade_info", type="dict", description="交易信息详情", required=False),
            AgentInput(name="market_data", type="dict", description="市场行情数据", required=False),
            AgentInput(name="benchmark_data", type="dict", description="基准数据", required=False),
        ],
        outputs=[
            AgentOutput(name="position_analysis", type="string", description="仓位分析结果"),
        ],
        requires_tools=False,
        output_field="position_analysis",
        node_name="仓位分析师 v2",
        execution_order=20,
        workflow_stage="analyst",
    ),

    "emotion_analyst_v2": AgentMetadata(
        id="emotion_analyst_v2",
        name="情绪分析师 v2.0",
        description="分析交易中的情绪化操作和纪律执行情况",
        category=AgentCategory.ANALYST,
        version="2.0.0",
        license_tier=LicenseTier.FREE,
        default_tools=[],
        inputs=[
            AgentInput(name="ticker", type="string", description="股票代码"),
            AgentInput(name="trade_records", type="string", description="交易记录"),
            AgentInput(name="trade_info", type="dict", description="交易信息详情", required=False),
            AgentInput(name="market_data", type="dict", description="市场行情数据", required=False),
            AgentInput(name="benchmark_data", type="dict", description="基准数据", required=False),
        ],
        outputs=[
            AgentOutput(name="emotion_analysis", type="string", description="情绪分析结果"),
        ],
        requires_tools=False,
        output_field="emotion_analysis",
        node_name="情绪分析师 v2",
        execution_order=30,
        workflow_stage="analyst",
    ),

    "attribution_analyst_v2": AgentMetadata(
        id="attribution_analyst_v2",
        name="归因分析师 v2.0",
        description="分析收益来源，区分大盘/行业/个股Alpha贡献与可复制性",
        category=AgentCategory.ANALYST,
        version="2.0.0",
        license_tier=LicenseTier.FREE,
        default_tools=[],
        inputs=[
            AgentInput(name="ticker", type="string", description="股票代码"),
            AgentInput(name="trade_records", type="string", description="交易记录"),
            AgentInput(name="trade_info", type="dict", description="交易信息详情", required=False),
            AgentInput(name="market_data", type="dict", description="市场行情数据", required=False),
            AgentInput(name="benchmark_data", type="dict", description="基准数据", required=False),
        ],
        outputs=[
            AgentOutput(name="attribution_analysis", type="string", description="归因分析结果"),
        ],
        requires_tools=False,
        output_field="attribution_analysis",
        node_name="归因分析师 v2",
        execution_order=40,
        workflow_stage="analyst",
    ),

    "review_manager_v2": AgentMetadata(
        id="review_manager_v2",
        name="复盘总结师 v2.0",
        description="综合所有分析维度，生成完整复盘报告和改进方向",
        category=AgentCategory.MANAGER,
        version="2.0.0",
        license_tier=LicenseTier.FREE,
        default_tools=[],
        inputs=[
            AgentInput(name="ticker", type="string", description="股票代码"),
            AgentInput(name="trade_records", type="string", description="交易记录"),
            AgentInput(name="trade_info", type="dict", description="交易信息详情", required=False),
            AgentInput(name="market_data", type="dict", description="市场行情数据", required=False),
            AgentInput(name="benchmark_data", type="dict", description="基准数据", required=False),
            AgentInput(name="timing_analysis", type="string", description="时机分析结果", required=False),
            AgentInput(name="position_analysis", type="string", description="仓位分析结果", required=False),
            AgentInput(name="emotion_analysis", type="string", description="情绪分析结果", required=False),
            AgentInput(name="attribution_analysis", type="string", description="归因分析结果", required=False),
        ],
        outputs=[
            AgentOutput(name="review_summary", type="string", description="复盘总结报告"),
        ],
        requires_tools=False,
        output_field="review_summary",
        node_name="复盘总结师 v2",
        execution_order=100,
        workflow_stage="manager",
    ),

    # 🆕 报告生成器 Agent (智能报告生成)
    "report_generator_v2": AgentMetadata(
        id="report_generator_v2",
        name="报告生成器 v2",
        description="智能报告生成 Agent，通过 LLM 理解分析结果并生成格式化的综合报告",
        category=AgentCategory.ANALYST,  # 改为 ANALYST（因为调用 LLM）
        version="2.0.0",
        license_tier=LicenseTier.FREE,
        icon="📝",
        color="#9b59b6",
        tags=["报告", "生成", "汇总", "智能", "v2.0"],
        tools=[],  # 不需要工具，只处理已有数据
        default_tools=[],
        max_tool_calls=0,
        inputs=[
            AgentInput(name="ticker", type="string", description="股票代码", required=False),
            AgentInput(name="analysis_date", type="string", description="分析日期", required=False),
            AgentInput(name="report_style", type="string", description="报告样式（简洁/详细/投资者）", required=False),
        ],
        outputs=[
            AgentOutput(name="reports", type="dict", description="生成的报告字典"),
            AgentOutput(name="report_summary", type="string", description="报告摘要"),
        ],
        requires_tools=False,
        output_field="reports",
        report_label="【综合报告】",
        node_name="报告生成器 v2",
        execution_order=999,  # 最后执行
    ),

    # 🆕 数据准备器 Agent (智能数据准备)
    "data_preparer_v2": AgentMetadata(
        id="data_preparer_v2",
        name="数据准备器 v2",
        description="智能数据准备 Agent，通过 LLM 理解需求并调用工具获取数据，存储在 context 中供后续使用",
        category=AgentCategory.ANALYST,  # 改为 ANALYST，因为需要调用 LLM
        version="2.0.0",
        license_tier=LicenseTier.FREE,
        icon="🔧",
        color="#3498db",
        tags=["数据", "准备", "智能", "v2.0"],
        tools=["market", "fundamentals", "news", "social"],  # 绑定所有数据工具
        default_tools=["market", "fundamentals", "news", "social"],
        max_tool_calls=10,  # 允许多次工具调用
        inputs=[
            AgentInput(name="ticker", type="string", description="股票代码", required=True),
            AgentInput(name="analysis_date", type="string", description="分析日期", required=False),
            AgentInput(name="data_requirements", type="string", description="数据需求描述", required=False),
        ],
        outputs=[
            AgentOutput(name="context", type="string", description="准备好的数据上下文"),
            AgentOutput(name="data_summary", type="string", description="数据摘要"),
            AgentOutput(name="tools_used", type="array", description="使用的工具列表"),
        ],
        requires_tools=True,  # 需要工具
        output_field="context",
        report_label="【数据准备】",
        node_name="数据准备器 v2",
        execution_order=0,  # 最先执行
    ),
}

