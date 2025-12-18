"""
持仓分析相关数据模型
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict, field_serializer
from enum import Enum
from bson import ObjectId
from .user import PyObjectId
from app.utils.timezone import now_tz


class PositionSource(str, Enum):
    """持仓数据来源"""
    MANUAL = "manual"      # 手动录入
    IMPORT = "import"      # 批量导入
    PAPER = "paper"        # 从模拟交易同步


class PortfolioAnalysisStatus(str, Enum):
    """持仓分析状态"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class PositionAction(str, Enum):
    """持仓操作建议"""
    ADD = "add"           # 加仓
    REDUCE = "reduce"     # 减仓
    HOLD = "hold"         # 持有
    CLEAR = "clear"       # 清仓


class CapitalTransactionType(str, Enum):
    """资金交易类型"""
    INITIAL = "initial"       # 初始资金
    DEPOSIT = "deposit"       # 入金
    WITHDRAW = "withdraw"     # 出金
    DIVIDEND = "dividend"     # 股息分红
    ADJUSTMENT = "adjustment" # 手动调整


class PositionChangeType(str, Enum):
    """持仓变动类型"""
    BUY = "buy"               # 买入（新建持仓）
    ADD = "add"               # 加仓
    REDUCE = "reduce"         # 减仓
    SELL = "sell"             # 卖出（清仓）
    ADJUST = "adjust"         # 调整（修改成本价等）


# ==================== 持仓变动记录模型 ====================

class PositionChange(BaseModel):
    """持仓变动记录"""
    id: Optional[PyObjectId] = Field(default_factory=PyObjectId, alias="_id")
    user_id: str
    position_id: Optional[str] = None          # 关联的持仓ID（清仓后可能为空）
    code: str                                  # 股票代码
    name: str                                  # 股票名称
    market: str                                # 市场
    currency: str = "CNY"                      # 货币
    change_type: PositionChangeType            # 变动类型

    # 变动前
    quantity_before: int = 0                   # 变动前数量
    cost_price_before: float = 0.0             # 变动前成本价
    cost_value_before: float = 0.0             # 变动前成本金额

    # 变动后
    quantity_after: int = 0                    # 变动后数量
    cost_price_after: float = 0.0              # 变动后成本价
    cost_value_after: float = 0.0              # 变动后成本金额

    # 变动量
    quantity_change: int = 0                   # 数量变化（正数买入/加仓，负数减仓/卖出）
    cash_change: float = 0.0                   # 资金变化（正数释放资金，负数占用资金）

    # 如果是卖出/减仓，记录卖出价格和盈亏
    trade_price: Optional[float] = None        # 交易价格
    realized_profit: Optional[float] = None    # 已实现盈亏

    description: Optional[str] = None          # 说明/备注
    trade_time: Optional[datetime] = None      # 交易时间（实际交易发生的时间，由用户手工录入）
    created_at: datetime = Field(default_factory=now_tz)  # 记录创建时间

    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True
    )

    @field_serializer('id')
    def serialize_id(self, v):
        return str(v) if v else None


class PositionChangeResponse(BaseModel):
    """持仓变动响应"""
    id: str
    position_id: Optional[str] = None
    code: str
    name: str
    market: str
    currency: str
    change_type: str
    quantity_before: int
    cost_price_before: float
    cost_value_before: float
    quantity_after: int
    cost_price_after: float
    cost_value_after: float
    quantity_change: int
    cash_change: float
    trade_price: Optional[float] = None
    realized_profit: Optional[float] = None
    description: Optional[str] = None
    created_at: datetime


# ==================== 资金账户数据模型 ====================

class CapitalTransaction(BaseModel):
    """资金交易记录"""
    id: Optional[PyObjectId] = Field(default_factory=PyObjectId, alias="_id")
    user_id: str
    transaction_type: CapitalTransactionType
    amount: float                              # 金额（正数为入金，负数为出金）
    currency: str = "CNY"                      # 货币
    balance_before: float                      # 交易前余额
    balance_after: float                       # 交易后余额
    description: Optional[str] = None          # 说明
    created_at: datetime = Field(default_factory=now_tz)

    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True
    )

    @field_serializer('id')
    def serialize_id(self, v):
        return str(v) if v else None


class RealAccount(BaseModel):
    """真实持仓资金账户 (real_accounts 集合)"""
    id: Optional[PyObjectId] = Field(default_factory=PyObjectId, alias="_id")
    user_id: str

    # 多货币现金账户
    cash: Dict[str, float] = Field(default_factory=lambda: {
        "CNY": 0.0,
        "HKD": 0.0,
        "USD": 0.0
    })

    # 初始资金记录（用于计算收益率）
    initial_capital: Dict[str, float] = Field(default_factory=lambda: {
        "CNY": 0.0,
        "HKD": 0.0,
        "USD": 0.0
    })

    # 累计入金
    total_deposit: Dict[str, float] = Field(default_factory=lambda: {
        "CNY": 0.0,
        "HKD": 0.0,
        "USD": 0.0
    })

    # 累计出金
    total_withdraw: Dict[str, float] = Field(default_factory=lambda: {
        "CNY": 0.0,
        "HKD": 0.0,
        "USD": 0.0
    })

    # 账户设置
    settings: Dict[str, Any] = Field(default_factory=lambda: {
        "default_market": "CN",
        "max_position_pct": 30.0,      # 单股最大仓位比例
        "max_loss_pct": 10.0           # 最大亏损容忍度
    })

    created_at: datetime = Field(default_factory=now_tz)
    updated_at: datetime = Field(default_factory=now_tz)

    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True
    )

    @field_serializer('id')
    def serialize_id(self, v):
        return str(v) if v else None


# ==================== 资金账户请求/响应模型 ====================

class AccountInitRequest(BaseModel):
    """初始化资金账户请求"""
    initial_capital: float = Field(..., gt=0, description="初始资金金额")
    currency: str = Field("CNY", description="货币类型")


class AccountTransactionRequest(BaseModel):
    """资金交易请求（入金/出金）"""
    transaction_type: CapitalTransactionType
    amount: float = Field(..., gt=0, description="金额（正数）")
    currency: str = Field("CNY", description="货币类型")
    description: Optional[str] = None


class AccountSettingsRequest(BaseModel):
    """更新账户设置请求"""
    max_position_pct: Optional[float] = Field(None, ge=5, le=100)
    max_loss_pct: Optional[float] = Field(None, ge=1, le=50)
    default_market: Optional[str] = None


class AccountSummary(BaseModel):
    """账户摘要"""
    # 现金
    cash: Dict[str, float]
    # 初始资金
    initial_capital: Dict[str, float]
    # 累计入金
    total_deposit: Dict[str, float]
    # 累计出金
    total_withdraw: Dict[str, float]
    # 净入金 = 初始 + 入金 - 出金
    net_capital: Dict[str, float]
    # 持仓市值
    positions_value: Dict[str, float]
    # 总资产 = 现金 + 持仓市值
    total_assets: Dict[str, float]
    # 收益 = 总资产 - 净入金
    profit: Dict[str, float]
    # 收益率 = 收益 / 净入金
    profit_pct: Dict[str, float]
    # 账户设置
    settings: Dict[str, Any]


# ==================== 持仓数据模型 ====================

class RealPosition(BaseModel):
    """真实持仓数据模型 (real_positions 集合)"""
    id: Optional[PyObjectId] = Field(default_factory=PyObjectId, alias="_id")
    user_id: str
    code: str                              # 股票代码
    name: Optional[str] = None             # 股票名称
    market: str = "CN"                     # 市场: CN/HK/US
    currency: str = "CNY"                  # 货币: CNY/HKD/USD
    quantity: int                          # 持仓数量
    cost_price: float                      # 成本价
    buy_date: Optional[datetime] = None    # 买入日期
    industry: Optional[str] = None         # 所属行业
    notes: Optional[str] = None            # 备注
    source: PositionSource = PositionSource.MANUAL
    created_at: datetime = Field(default_factory=now_tz)
    updated_at: datetime = Field(default_factory=now_tz)

    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True
    )


class PositionSnapshot(BaseModel):
    """持仓快照（用于分析报告）"""
    code: str
    name: Optional[str] = None
    market: str = "CN"
    quantity: int
    cost_price: float
    current_price: Optional[float] = None
    market_value: Optional[float] = None
    unrealized_pnl: Optional[float] = None
    unrealized_pnl_pct: Optional[float] = None
    industry: Optional[str] = None
    holding_days: Optional[int] = None
    # 资金相关（可选，用于风险分析）
    total_capital: Optional[float] = None          # 用户资金总量
    position_pct: Optional[float] = None           # 仓位占比（%）
    # 资金占用相关
    cost_value: Optional[float] = None             # 资金占用金额（成本价*数量）
    cost_pct: Optional[float] = None               # 资金占用比例（占总资产%）


class AccountSnapshot(BaseModel):
    """资金账户快照（用于分析报告）"""
    total_assets: float = 0.0                      # 总资产（现金+持仓市值）
    cash: float = 0.0                              # 可用现金
    positions_value: float = 0.0                   # 持仓市值
    position_ratio: float = 0.0                    # 仓位比例（持仓市值/总资产 %）
    cash_ratio: float = 0.0                        # 现金比例（%）
    initial_capital: float = 0.0                   # 初始资金
    net_capital: float = 0.0                       # 净投入资金
    total_profit: float = 0.0                      # 总盈亏
    total_profit_pct: float = 0.0                  # 总收益率（%）
    currency: str = "CNY"                          # 主要货币


class PortfolioSnapshot(BaseModel):
    """组合持仓快照"""
    total_positions: int = 0
    total_value: float = 0.0
    total_cost: float = 0.0
    unrealized_pnl: float = 0.0
    unrealized_pnl_pct: float = 0.0
    positions: List[PositionSnapshot] = Field(default_factory=list)
    # 资金账户信息
    account: Optional[AccountSnapshot] = None


# ==================== 分析结果模型 ====================

class IndustryDistribution(BaseModel):
    """行业分布"""
    industry: str
    value: float
    percentage: float
    count: int


class ConcentrationAnalysis(BaseModel):
    """集中度分析"""
    top1_pct: float = 0.0           # 第一大持仓占比
    top3_pct: float = 0.0           # 前三大持仓占比
    top5_pct: float = 0.0           # 前五大持仓占比
    hhi_index: float = 0.0          # 赫芬达尔指数
    industry_count: int = 0         # 涉及行业数


class AIAnalysisResult(BaseModel):
    """AI分析结果"""
    summary: str = ""                          # 分析摘要
    strengths: List[str] = Field(default_factory=list)   # 优势
    weaknesses: List[str] = Field(default_factory=list)  # 劣势
    suggestions: List[str] = Field(default_factory=list) # 建议
    detailed_report: str = ""                  # 详细报告


class PortfolioAnalysisReport(BaseModel):
    """持仓分析报告 (portfolio_analysis_reports 集合)"""
    id: Optional[PyObjectId] = Field(default_factory=PyObjectId, alias="_id")
    analysis_id: str                           # 唯一分析ID
    user_id: str
    analysis_type: str = "portfolio_health"    # 分析类型
    analysis_date: str                         # 分析日期 YYYY-MM-DD
    timestamp: datetime = Field(default_factory=now_tz)
    
    # 持仓快照
    portfolio_snapshot: PortfolioSnapshot = Field(default_factory=PortfolioSnapshot)
    
    # 分析结果
    health_score: float = 0.0                  # 健康度评分 0-100
    risk_level: str = "中"                     # 风险等级: 低/中/高
    industry_distribution: List[IndustryDistribution] = Field(default_factory=list)
    concentration_analysis: ConcentrationAnalysis = Field(default_factory=ConcentrationAnalysis)
    
    # AI分析
    ai_analysis: AIAnalysisResult = Field(default_factory=AIAnalysisResult)
    
    # 执行信息
    status: PortfolioAnalysisStatus = PortfolioAnalysisStatus.PENDING
    execution_time: float = 0.0
    tokens_used: int = 0
    error_message: Optional[str] = None
    created_at: datetime = Field(default_factory=now_tz)

    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True
    )


# ==================== API请求/响应模型 ====================

class PositionCreate(BaseModel):
    """创建持仓请求"""
    code: str = Field(..., description="股票代码")
    name: Optional[str] = Field(None, description="股票名称")
    market: str = Field("CN", description="市场: CN/HK/US")
    quantity: int = Field(..., gt=0, description="持仓数量")
    cost_price: float = Field(..., gt=0, description="成本价")
    buy_date: Optional[datetime] = Field(None, description="买入日期")
    notes: Optional[str] = Field(None, description="备注")


class PositionUpdate(BaseModel):
    """更新持仓请求"""
    name: Optional[str] = None
    quantity: Optional[int] = Field(None, gt=0)
    cost_price: Optional[float] = Field(None, gt=0)
    buy_date: Optional[datetime] = None
    notes: Optional[str] = None


class PositionOperationType(str, Enum):
    """持仓操作类型"""
    ADD = "add"              # 加仓
    REDUCE = "reduce"        # 减仓
    DIVIDEND = "dividend"    # 分红
    SPLIT = "split"          # 拆股
    MERGE = "merge"          # 合股
    ADJUST = "adjust"        # 调整成本价


class PositionOperationRequest(BaseModel):
    """持仓操作请求"""
    operation_type: PositionOperationType = Field(..., description="操作类型")
    code: str = Field(..., description="股票代码")
    market: str = Field("CN", description="市场: CN/HK/US")
    # 加仓/减仓参数
    quantity: Optional[int] = Field(None, gt=0, description="数量")
    price: Optional[float] = Field(None, gt=0, description="价格")
    # 分红参数
    dividend_amount: Optional[float] = Field(None, ge=0, description="分红金额")
    # 拆股/合股参数
    ratio: Optional[str] = Field(None, description="比例，如 2:1")
    # 调整成本价参数
    new_cost_price: Optional[float] = Field(None, gt=0, description="新成本价")
    # 通用参数
    operation_date: Optional[datetime] = Field(None, description="操作日期")
    notes: Optional[str] = Field(None, description="备注")


class PositionImport(BaseModel):
    """批量导入持仓"""
    positions: List[PositionCreate] = Field(..., min_length=1, max_length=50)


class PortfolioAnalysisRequest(BaseModel):
    """持仓分析请求"""
    include_paper: bool = Field(True, description="是否包含模拟交易持仓")
    research_depth: str = Field("标准", description="分析深度")


class PositionResponse(BaseModel):
    """持仓响应"""
    id: str
    code: str
    name: Optional[str] = None
    market: str
    currency: str
    quantity: int
    cost_price: float
    current_price: Optional[float] = None
    market_value: Optional[float] = None
    unrealized_pnl: Optional[float] = None
    unrealized_pnl_pct: Optional[float] = None
    buy_date: Optional[datetime] = None
    industry: Optional[str] = None
    notes: Optional[str] = None
    source: str
    created_at: datetime
    updated_at: datetime

    @field_serializer('created_at', 'updated_at', 'buy_date')
    def serialize_datetime(self, dt: Optional[datetime], _info) -> Optional[str]:
        if dt:
            return dt.isoformat()
        return None


class PortfolioStatsResponse(BaseModel):
    """持仓统计响应"""
    total_positions: int = 0
    total_value: float = 0.0
    total_cost: float = 0.0
    unrealized_pnl: float = 0.0
    unrealized_pnl_pct: float = 0.0
    industry_distribution: List[IndustryDistribution] = Field(default_factory=list)
    market_distribution: Dict[str, float] = Field(default_factory=dict)


class PortfolioAnalysisResponse(BaseModel):
    """持仓分析响应"""
    analysis_id: str
    status: PortfolioAnalysisStatus
    health_score: float = 0.0
    risk_level: str = "中"
    portfolio_snapshot: PortfolioSnapshot
    industry_distribution: List[IndustryDistribution] = Field(default_factory=list)
    concentration_analysis: ConcentrationAnalysis = Field(default_factory=ConcentrationAnalysis)
    ai_analysis: AIAnalysisResult = Field(default_factory=AIAnalysisResult)
    execution_time: float = 0.0
    created_at: datetime

    @field_serializer('created_at')
    def serialize_datetime(self, dt: datetime, _info) -> str:
        return dt.isoformat()


# ==================== 单股持仓分析模型 ====================

class PositionAnalysisRequest(BaseModel):
    """单股持仓分析请求"""
    research_depth: str = "标准"              # 分析深度: 快速/标准/深度
    include_add_position: bool = True        # 是否分析加仓建议
    target_profit_pct: float = 20.0          # 目标收益率（%）
    # 资金总量相关（用于风险分析）
    total_capital: Optional[float] = Field(None, description="投资资金总量")
    max_position_pct: float = Field(30.0, description="单只股票最大仓位比例（%）")
    max_loss_pct: float = Field(10.0, description="最大可接受亏损比例（%）")

    # 投资偏好设置（用于工作流引擎选择分析风格）
    risk_tolerance: str = Field("medium", description="风险偏好: low/medium/high")
    investment_horizon: str = Field("medium", description="投资期限: short(短线)/medium(中线)/long(长线)")
    analysis_focus: str = Field("comprehensive", description="分析重点: technical(技术面)/fundamental(基本面)/comprehensive(综合)")

    # 持仓类型（区分模拟交易和真实持仓）
    position_type: str = Field("real", description="持仓类型: real(真实持仓)/simulated(模拟交易)")


class PositionAnalysisByCodeRequest(BaseModel):
    """按股票代码分析持仓请求（汇总同一股票的所有持仓）"""
    code: str = Field(..., description="股票代码")
    market: str = Field("CN", description="市场: CN/HK/US")
    research_depth: str = "标准"
    include_add_position: bool = True
    target_profit_pct: float = 20.0
    total_capital: Optional[float] = None
    max_position_pct: float = 30.0
    max_loss_pct: float = 10.0

    # 投资偏好设置（用于工作流引擎选择分析风格）
    risk_tolerance: str = Field("medium", description="风险偏好: low/medium/high")
    investment_horizon: str = Field("medium", description="投资期限: short/medium/long")
    analysis_focus: str = Field("comprehensive", description="分析重点: technical/fundamental/comprehensive")

    # 持仓类型
    position_type: str = Field("real", description="持仓类型: real/simulated")


class PriceTarget(BaseModel):
    """价格目标"""
    stop_loss_price: Optional[float] = None      # 止损价
    stop_loss_pct: Optional[float] = None        # 止损比例
    take_profit_price: Optional[float] = None    # 止盈价
    take_profit_pct: Optional[float] = None      # 止盈比例
    breakeven_price: Optional[float] = None      # 回本价


class PositionRiskMetrics(BaseModel):
    """持仓风险指标"""
    position_pct: Optional[float] = None          # 仓位占比（%）
    position_value: Optional[float] = None        # 持仓市值
    max_loss_amount: Optional[float] = None       # 最大可能亏损金额
    max_loss_impact_pct: Optional[float] = None   # 最大亏损对总资金影响（%）
    available_add_amount: Optional[float] = None  # 可加仓金额（基于最大仓位限制）
    risk_level: str = "unknown"                   # 风险等级: low/medium/high/critical
    risk_summary: str = ""                        # 风险概述


class PositionAnalysisResult(BaseModel):
    """单股持仓AI分析结果"""
    action: PositionAction = PositionAction.HOLD    # 操作建议
    action_reason: str = ""                         # 建议理由
    confidence: float = 0.0                         # 置信度 0-100
    price_targets: PriceTarget = Field(default_factory=PriceTarget)
    risk_assessment: str = ""                       # 风险评估
    opportunity_assessment: str = ""                # 机会评估
    suggested_quantity: Optional[int] = None        # 建议操作数量
    suggested_amount: Optional[float] = None        # 建议操作金额
    detailed_analysis: str = ""                     # 详细分析
    # 风险指标（基于资金总量计算）
    risk_metrics: Optional[PositionRiskMetrics] = None

    # 工作流引擎扩展字段
    summary: str = ""                               # 分析摘要（综合各智能体结果）
    recommendation: str = ""                        # 操作建议详情（操作建议师输出）
    source: str = "legacy"                          # 分析来源: legacy(旧版LLM)/workflow_engine_v2(工作流引擎)


class PositionAnalysisReport(BaseModel):
    """单股持仓分析报告 (position_analysis_reports 集合)"""
    id: Optional[PyObjectId] = Field(default_factory=PyObjectId, alias="_id")
    analysis_id: str
    user_id: str
    position_id: str                               # 关联的持仓ID

    # 持仓快照（可选，分析失败时可能为空）
    position_snapshot: Optional[PositionSnapshot] = None

    # 分析结果
    status: PortfolioAnalysisStatus = PortfolioAnalysisStatus.PENDING
    ai_analysis: PositionAnalysisResult = Field(default_factory=PositionAnalysisResult)

    # 关联的单股分析任务ID（方案2新增）
    stock_analysis_task_id: Optional[str] = Field(None, description="关联的单股分析任务ID")

    # 元数据
    execution_time: float = 0.0
    error_message: Optional[str] = None
    created_at: datetime = Field(default_factory=now_tz)

    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        json_encoders={ObjectId: str, datetime: lambda v: v.isoformat()}
    )


class PositionAnalysisResponse(BaseModel):
    """单股持仓分析响应"""
    analysis_id: str
    position_id: str
    code: str
    name: Optional[str] = None
    status: str
    action: str = "hold"
    action_reason: str = ""
    confidence: float = 0.0
    price_targets: PriceTarget = Field(default_factory=PriceTarget)
    risk_assessment: str = ""
    opportunity_assessment: str = ""
    detailed_analysis: str = ""
    execution_time: float = 0.0
    created_at: str = ""
