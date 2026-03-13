"""
个人交易计划数据模型
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, model_validator
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


class TradingSystemStatus(str, Enum):
    """交易计划状态"""
    DRAFT = "draft"        # 草稿
    PUBLISHED = "published"  # 已发布


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

    @staticmethod
    def _sanitize_stop_loss(stop_loss: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        source = stop_loss or {}
        stop_type = source.get("type", "percentage")

        if stop_type == "technical":
            return {
                "type": "technical",
                "description": source.get("description", "")
            }

        if stop_type == "atr":
            return {
                "type": "atr",
                "atr_multiplier": float(source.get("atr_multiplier", 2.0))
            }

        return {
            "type": "percentage",
            "percentage": float(source.get("percentage", 0.08))
        }

    @staticmethod
    def _sanitize_take_profit(take_profit: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        source = take_profit or {}
        take_type = source.get("type", "percentage")

        if take_type == "trailing":
            return {
                "type": "trailing",
                "trailing_pullback_pct": float(source.get("trailing_pullback_pct", 0.08)),
                "activation_profit_pct": float(source.get("activation_profit_pct", 0.1)),
                "reference": source.get("reference", "highest_price")
            }

        if take_type == "scaled":
            levels = source.get("levels") if isinstance(source.get("levels"), list) else []
            if not levels:
                levels = [
                    {"target_profit_pct": 0.2, "sell_ratio": 0.3},
                    {"target_profit_pct": 0.35, "sell_ratio": 0.3},
                    {"target_profit_pct": 0.5, "sell_ratio": 0.4},
                ]
            return {
                "type": "scaled",
                "levels": levels
            }

        return {
            "type": "percentage",
            "percentage": float(source.get("percentage", 0.2))
        }

    @model_validator(mode="after")
    def normalize_exclusive_fields(self):
        self.stop_loss = self._sanitize_stop_loss(self.stop_loss)
        self.take_profit = self._sanitize_take_profit(self.take_profit)
        return self


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
    status: TradingSystemStatus = Field(default=TradingSystemStatus.DRAFT, description="状态：草稿/已发布")
    is_active: bool = Field(default=True, description="是否激活")

    # 六大模块规则（正式版本）
    stock_selection: StockSelectionRule = Field(default_factory=StockSelectionRule, description="选股规则")
    timing: TimingRule = Field(default_factory=TimingRule, description="择时规则")
    position: PositionRule = Field(default_factory=PositionRule, description="仓位规则")
    holding: HoldingRule = Field(default_factory=HoldingRule, description="持仓规则")
    risk_management: RiskManagementRule = Field(default_factory=RiskManagementRule, description="风险管理规则")
    review: ReviewRule = Field(default_factory=ReviewRule, description="复盘规则")
    discipline: DisciplineRule = Field(default_factory=DisciplineRule, description="纪律规则")

    # 草稿数据（仅在已发布版本中存在，保存草稿时使用）
    draft_data: Optional[Dict[str, Any]] = Field(None, description="草稿数据，包含修改后的规则")
    draft_updated_at: Optional[datetime] = Field(None, description="草稿更新时间")

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
    status: Optional[TradingSystemStatus] = None
    is_active: Optional[bool] = None
    
    stock_selection: Optional[StockSelectionRule] = None
    timing: Optional[TimingRule] = None
    position: Optional[PositionRule] = None
    holding: Optional[HoldingRule] = None
    risk_management: Optional[RiskManagementRule] = None
    review: Optional[ReviewRule] = None
    discipline: Optional[DisciplineRule] = None


class TradingSystemPublish(BaseModel):
    """发布交易计划请求模型"""
    improvement_summary: str = Field(..., description="改进总结（发布时必填）")
    new_version: Optional[str] = Field(None, description="新版本号，如果不提供则自动递增")
    # 可选的更新数据（如果有修改）
    update_data: Optional[TradingSystemUpdate] = Field(None, description="可选的更新数据")


class TradingSystemVersion(BaseModel):
    """交易计划版本模型"""
    id: Optional[str] = Field(None, description="版本ID")
    system_id: str = Field(..., description="关联的交易计划ID")
    version: str = Field(..., description="版本号，如 '1.0.0', '2.0.0'")
    improvement_summary: str = Field(default="", description="改进总结")
    
    # 完整的系统快照
    snapshot: TradingSystem = Field(..., description="该版本的完整系统快照")
    
    # 元数据
    created_at: datetime = Field(default_factory=datetime.utcnow, description="创建时间")
    created_by: str = Field(..., description="创建者用户ID")
    
    class Config:
        populate_by_name = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class TradingSystemVersionCreate(BaseModel):
    """创建交易计划版本请求模型"""
    improvement_summary: str = Field(..., description="改进总结")
    new_version: Optional[str] = Field(None, description="新版本号，如果不提供则自动递增")

