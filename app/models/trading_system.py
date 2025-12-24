"""
个人交易计划数据模型
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from enum import Enum


class TradingStyle(str, Enum):
    """交易风格"""
    SHORT_TERM = "short_term"      # 短线（1天-1周）
    MEDIUM_TERM = "medium_term"    # 中线（1周-1月）
    LONG_TERM = "long_term"        # 长线（1月-1年+）


class RiskProfile(str, Enum):
    """风险偏好"""
    CONSERVATIVE = "conservative"  # 保守
    BALANCED = "balanced"          # 稳健
    AGGRESSIVE = "aggressive"      # 激进


class StockSelectionRule(BaseModel):
    """选股规则模型"""
    analysis_config: Dict[str, Any] = Field(default_factory=dict, description="分析配置")
    must_have: List[Dict[str, Any]] = Field(default_factory=list, description="必备条件")
    exclude: List[Dict[str, Any]] = Field(default_factory=list, description="排除条件")
    bonus: List[Dict[str, Any]] = Field(default_factory=list, description="加分条件")


class TimingRule(BaseModel):
    """择时规则模型"""
    market_condition: Dict[str, Any] = Field(default_factory=dict, description="大盘条件")
    sector_condition: Dict[str, Any] = Field(default_factory=dict, description="行业条件")
    entry_signals: List[Dict[str, Any]] = Field(default_factory=list, description="买入信号")
    confirmation: List[Dict[str, Any]] = Field(default_factory=list, description="确认条件")


class PositionRule(BaseModel):
    """仓位规则模型"""
    total_position: Dict[str, float] = Field(
        default_factory=lambda: {"bull": 0.8, "range": 0.5, "bear": 0.2},
        description="总仓位控制（按市况）"
    )
    max_per_stock: float = Field(default=0.3, description="单只股票上限")
    max_holdings: int = Field(default=5, description="最大持股数量")
    min_holdings: int = Field(default=1, description="最小持股数量")
    scaling: Dict[str, Any] = Field(default_factory=dict, description="分批策略")


class HoldingRule(BaseModel):
    """持仓规则模型"""
    review_frequency: str = Field(default="daily", description="检视频率")
    add_conditions: List[Dict[str, Any]] = Field(default_factory=list, description="加仓条件")
    reduce_conditions: List[Dict[str, Any]] = Field(default_factory=list, description="减仓条件")
    switch_conditions: List[Dict[str, Any]] = Field(default_factory=list, description="换股条件")


class RiskManagementRule(BaseModel):
    """风险管理规则模型"""
    stop_loss: Dict[str, Any] = Field(default_factory=dict, description="止损设置")
    take_profit: Dict[str, Any] = Field(default_factory=dict, description="止盈设置")
    time_stop: Dict[str, Any] = Field(default_factory=dict, description="时间止损")
    logical_stop: Dict[str, Any] = Field(default_factory=dict, description="逻辑止损")


class ReviewRule(BaseModel):
    """复盘规则模型"""
    frequency: str = Field(default="weekly", description="复盘频率")
    checklist: List[str] = Field(default_factory=list, description="复盘内容")
    case_save: Dict[str, Any] = Field(default_factory=dict, description="案例保存规则")


class DisciplineRule(BaseModel):
    """纪律规则模型"""
    must_not: List[Dict[str, Any]] = Field(default_factory=list, description="绝对禁止")
    must_do: List[Dict[str, Any]] = Field(default_factory=list, description="必须做到")
    violation_actions: List[Dict[str, Any]] = Field(default_factory=list, description="违规处理")


class TradingSystem(BaseModel):
    """交易计划主模型"""
    id: Optional[str] = Field(None, description="系统ID")
    user_id: str = Field(..., description="所属用户ID")
    name: str = Field(..., description="系统名称")
    description: str = Field(default="", description="系统描述")
    style: TradingStyle = Field(default=TradingStyle.MEDIUM_TERM, description="交易风格")
    risk_profile: RiskProfile = Field(default=RiskProfile.BALANCED, description="风险偏好")
    version: str = Field(default="1.0.0", description="版本号")
    is_active: bool = Field(default=True, description="是否激活")

    # 六大模块规则
    stock_selection: StockSelectionRule = Field(default_factory=StockSelectionRule, description="选股规则")
    timing: TimingRule = Field(default_factory=TimingRule, description="择时规则")
    position: PositionRule = Field(default_factory=PositionRule, description="仓位规则")
    holding: HoldingRule = Field(default_factory=HoldingRule, description="持仓规则")
    risk_management: RiskManagementRule = Field(default_factory=RiskManagementRule, description="风险管理规则")
    review: ReviewRule = Field(default_factory=ReviewRule, description="复盘规则")
    discipline: DisciplineRule = Field(default_factory=DisciplineRule, description="纪律规则")

    # 元数据
    created_at: datetime = Field(default_factory=datetime.utcnow, description="创建时间")
    updated_at: datetime = Field(default_factory=datetime.utcnow, description="更新时间")

    class Config:
        populate_by_name = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class TradingSystemCreate(BaseModel):
    """创建交易计划请求模型"""
    name: str = Field(..., description="系统名称")
    description: str = Field(default="", description="系统描述")
    style: TradingStyle = Field(default=TradingStyle.MEDIUM_TERM, description="交易风格")
    risk_profile: RiskProfile = Field(default=RiskProfile.BALANCED, description="风险偏好")
    
    stock_selection: Optional[StockSelectionRule] = None
    timing: Optional[TimingRule] = None
    position: Optional[PositionRule] = None
    holding: Optional[HoldingRule] = None
    risk_management: Optional[RiskManagementRule] = None
    review: Optional[ReviewRule] = None
    discipline: Optional[DisciplineRule] = None


class TradingSystemUpdate(BaseModel):
    """更新交易计划请求模型"""
    name: Optional[str] = None
    description: Optional[str] = None
    style: Optional[TradingStyle] = None
    risk_profile: Optional[RiskProfile] = None
    is_active: Optional[bool] = None
    
    stock_selection: Optional[StockSelectionRule] = None
    timing: Optional[TimingRule] = None
    position: Optional[PositionRule] = None
    holding: Optional[HoldingRule] = None
    risk_management: Optional[RiskManagementRule] = None
    review: Optional[ReviewRule] = None
    discipline: Optional[DisciplineRule] = None

