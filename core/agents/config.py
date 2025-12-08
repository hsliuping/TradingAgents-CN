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

    class Config:
        use_enum_values = True


class AgentConfig(BaseModel):
    """
    智能体运行时配置
    """
    # LLM 配置
    llm_provider: str = "deepseek"
    llm_model: Optional[str] = None
    temperature: float = 0.7
    
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
}

