"""
交易复盘数据模型
"""

from datetime import datetime
from typing import Optional, List
from enum import Enum
from pydantic import BaseModel, Field, ConfigDict
from bson import ObjectId

from app.utils.timezone import now_tz


class PyObjectId(ObjectId):
    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v, info=None):
        if not ObjectId.is_valid(v):
            raise ValueError("Invalid ObjectId")
        return ObjectId(v)

    @classmethod
    def __get_pydantic_json_schema__(cls, schema, handler):
        return {"type": "string"}


class ReviewType(str, Enum):
    """复盘类型"""
    SINGLE_TRADE = "single_trade"      # 单笔交易复盘
    COMPLETE_TRADE = "complete_trade"  # 完整交易复盘（买入到卖出）
    PERIODIC = "periodic"              # 阶段性复盘


class PeriodType(str, Enum):
    """阶段性复盘周期类型"""
    WEEK = "week"
    MONTH = "month"
    QUARTER = "quarter"
    YEAR = "year"


class ReviewStatus(str, Enum):
    """复盘状态"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


# ==================== 交易信息相关模型 ====================

class TradeRecord(BaseModel):
    """交易记录"""
    trade_id: Optional[str] = None
    side: str                           # buy/sell
    quantity: int
    price: float
    amount: float = 0.0
    commission: float = 0.0
    timestamp: str
    pnl: float = 0.0                    # 实现盈亏（卖出时）


class TradeInfo(BaseModel):
    """交易信息汇总"""
    code: str
    name: Optional[str] = None
    market: str = "CN"
    currency: str = "CNY"
    trades: List[TradeRecord] = Field(default_factory=list)
    
    # 汇总数据
    total_buy_quantity: int = 0
    total_buy_amount: float = 0.0
    avg_buy_price: float = 0.0
    total_sell_quantity: int = 0
    total_sell_amount: float = 0.0
    avg_sell_price: float = 0.0
    
    # 盈亏
    realized_pnl: float = 0.0           # 已实现盈亏（已卖出部分）
    realized_pnl_pct: float = 0.0       # 已实现盈亏百分比
    unrealized_pnl: float = 0.0         # 🆕 未实现盈亏（持仓部分）
    unrealized_pnl_pct: float = 0.0     # 🆕 未实现盈亏百分比
    total_commission: float = 0.0

    # 持仓状态
    is_holding: bool = False            # 🆕 是否还在持仓中
    current_price: Optional[float] = None  # 🆕 当前价格（持仓中时）
    remaining_quantity: int = 0         # 🆕 剩余持仓数量

    # 持仓周期
    first_buy_date: Optional[str] = None
    last_sell_date: Optional[str] = None
    holding_days: int = 0


class MarketSnapshot(BaseModel):
    """市场数据快照"""
    # 买入时行情
    buy_date_open: Optional[float] = None
    buy_date_high: Optional[float] = None
    buy_date_low: Optional[float] = None
    buy_date_close: Optional[float] = None
    
    # 卖出时行情
    sell_date_open: Optional[float] = None
    sell_date_high: Optional[float] = None
    sell_date_low: Optional[float] = None
    sell_date_close: Optional[float] = None
    
    # 持仓期间行情
    period_high: Optional[float] = None
    period_high_date: Optional[str] = None
    period_low: Optional[float] = None
    period_low_date: Optional[str] = None
    
    # 最优买卖点
    optimal_buy_price: Optional[float] = None
    optimal_sell_price: Optional[float] = None
    
    # K线数据（用于图表展示）
    kline_data: List[dict] = Field(default_factory=list)


# ==================== AI分析结果模型 ====================

class AITradeReview(BaseModel):
    """AI交易复盘结果"""
    overall_score: int = Field(0, ge=0, le=100, description="总评分")
    timing_score: int = Field(0, ge=0, le=100, description="时机评分")
    position_score: int = Field(0, ge=0, le=100, description="仓位评分")
    emotion_score: int = Field(0, ge=0, le=100, description="情绪评分")
    attribution_score: int = Field(0, ge=0, le=100, description="归因评分")
    discipline_score: int = Field(0, ge=0, le=100, description="纪律评分")  # 保留兼容性

    summary: str = ""                                # 总结
    strengths: List[str] = Field(default_factory=list)  # 做得好的地方
    weaknesses: List[str] = Field(default_factory=list) # 需要改进的地方
    suggestions: List[str] = Field(default_factory=list) # 具体建议

    timing_analysis: str = ""                        # 时机分析详情
    position_analysis: str = ""                      # 仓位分析详情
    emotion_analysis: str = ""                       # 情绪分析详情
    attribution_analysis: str = ""                   # 归因分析详情

    # 收益对比
    actual_pnl: float = 0.0                          # 实际收益
    optimal_pnl: float = 0.0                         # 理论最优收益
    missed_profit: float = 0.0                       # 错失的收益
    avoided_loss: float = 0.0                        # 避免的亏损

    # 🆕 交易计划执行情况（当关联了交易计划时）
    plan_adherence: Optional[str] = None             # 计划执行良好的地方
    plan_deviation: Optional[str] = None             # 偏离计划的地方


# ==================== 复盘报告模型 ====================

class TradeReviewReport(BaseModel):
    """交易复盘报告 (trade_reviews 集合)"""
    id: Optional[PyObjectId] = Field(default_factory=PyObjectId, alias="_id")
    review_id: str
    user_id: str
    review_type: ReviewType = ReviewType.COMPLETE_TRADE
    
    # 交易信息
    trade_info: TradeInfo = Field(default_factory=TradeInfo)
    
    # 市场数据快照
    market_snapshot: MarketSnapshot = Field(default_factory=MarketSnapshot)
    
    # AI分析结果
    ai_review: AITradeReview = Field(default_factory=AITradeReview)
    
    # 状态与元数据
    status: ReviewStatus = ReviewStatus.PENDING
    error_message: Optional[str] = None
    execution_time: float = 0.0
    
    # 案例相关
    is_case_study: bool = False
    tags: List[str] = Field(default_factory=list)
    source: str = Field(default="paper", description="数据源: paper(模拟交易) 或 position(持仓操作)")

    # 交易计划关联
    trading_system_id: Optional[str] = Field(None, description="关联的交易计划ID")
    trading_system_name: Optional[str] = Field(None, description="关联的交易计划名称")

    created_at: datetime = Field(default_factory=now_tz)
    
    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        json_encoders={ObjectId: str, datetime: lambda v: v.isoformat()}
    )


# ==================== 阶段性复盘模型 ====================

class TradingStatistics(BaseModel):
    """交易统计"""
    total_trades: int = 0                # 总交易次数
    winning_trades: int = 0              # 盈利次数
    losing_trades: int = 0               # 亏损次数
    win_rate: float = 0.0                # 胜率

    total_pnl: float = 0.0               # 总盈亏
    avg_profit: float = 0.0              # 平均盈利
    avg_loss: float = 0.0                # 平均亏损
    profit_loss_ratio: float = 0.0       # 盈亏比

    max_single_profit: float = 0.0       # 最大单笔盈利
    max_single_loss: float = 0.0         # 最大单笔亏损
    max_drawdown: float = 0.0            # 最大回撤

    avg_holding_days: float = 0.0        # 平均持仓天数
    total_commission: float = 0.0        # 总手续费


class AIPeriodicReview(BaseModel):
    """AI阶段性复盘结果"""
    overall_score: int = Field(0, ge=0, le=100)
    summary: str = ""

    trading_style: str = ""              # 交易风格分析
    common_mistakes: List[str] = Field(default_factory=list)   # 常见错误
    improvement_areas: List[str] = Field(default_factory=list) # 改进方向
    action_plan: List[str] = Field(default_factory=list)       # 下阶段行动计划

    best_trade: Optional[str] = None     # 最佳交易分析
    worst_trade: Optional[str] = None    # 最差交易分析


class TradeSummaryItem(BaseModel):
    """交易摘要项"""
    code: str
    name: Optional[str] = None
    side: str
    quantity: int
    price: float
    pnl: float = 0.0
    pnl_pct: float = 0.0
    timestamp: str


class PeriodicReviewReport(BaseModel):
    """阶段性复盘报告 (periodic_reviews 集合)"""
    id: Optional[PyObjectId] = Field(default_factory=PyObjectId, alias="_id")
    review_id: str
    user_id: str

    # 复盘周期
    period_type: PeriodType = PeriodType.MONTH
    period_start: datetime
    period_end: datetime

    # 数据源: paper(模拟交易) 或 position(持仓操作)
    source: str = "paper"

    # 交易统计
    statistics: TradingStatistics = Field(default_factory=TradingStatistics)

    # 交易明细摘要
    trades_summary: List[TradeSummaryItem] = Field(default_factory=list)

    # AI分析
    ai_review: AIPeriodicReview = Field(default_factory=AIPeriodicReview)

    # 状态与元数据
    status: ReviewStatus = ReviewStatus.PENDING
    error_message: Optional[str] = None
    execution_time: float = 0.0

    created_at: datetime = Field(default_factory=now_tz)

    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        json_encoders={ObjectId: str, datetime: lambda v: v.isoformat()}
    )


# ==================== API请求/响应模型 ====================

class CreateTradeReviewRequest(BaseModel):
    """创建交易复盘请求"""
    trade_ids: List[str] = Field(..., min_length=1, description="要复盘的交易ID列表")
    review_type: ReviewType = ReviewType.COMPLETE_TRADE
    code: Optional[str] = Field(None, description="股票代码（如果不提供则从交易记录推断）")
    source: str = Field("paper", description="数据源: paper(模拟交易) 或 position(持仓操作)")
    trading_system_id: Optional[str] = Field(None, description="关联的交易计划ID，如果提供则按照交易计划规则进行检查")
    use_workflow: Optional[bool] = Field(None, description="是否使用工作流引擎（v2.0）。None表示使用环境变量设置")


class CreatePeriodicReviewRequest(BaseModel):
    """创建阶段性复盘请求"""
    period_type: PeriodType = PeriodType.MONTH
    start_date: str = Field(..., description="开始日期 YYYY-MM-DD")
    end_date: str = Field(..., description="结束日期 YYYY-MM-DD")
    source: str = Field("paper", description="数据源: paper(模拟交易) 或 position(持仓操作)")


class SaveAsCaseRequest(BaseModel):
    """保存为案例请求"""
    review_id: str
    tags: List[str] = Field(default_factory=list)
    notes: Optional[str] = None


class TradeReviewResponse(BaseModel):
    """交易复盘响应"""
    review_id: str
    status: ReviewStatus
    trade_info: Optional[TradeInfo] = None
    ai_review: Optional[AITradeReview] = None
    market_snapshot: Optional[MarketSnapshot] = None
    execution_time: float = 0.0
    created_at: Optional[datetime] = None


class PeriodicReviewResponse(BaseModel):
    """阶段性复盘响应"""
    review_id: str
    status: ReviewStatus
    period_type: PeriodType
    period_start: Optional[datetime] = None
    period_end: Optional[datetime] = None
    statistics: Optional[TradingStatistics] = None
    ai_review: Optional[AIPeriodicReview] = None
    execution_time: float = 0.0
    created_at: Optional[datetime] = None


class ReviewListItem(BaseModel):
    """复盘列表项"""
    review_id: str
    review_type: str
    code: Optional[str] = None
    name: Optional[str] = None
    realized_pnl: float = 0.0
    overall_score: int = 0
    status: str
    is_case_study: bool = False
    created_at: Optional[datetime] = None

