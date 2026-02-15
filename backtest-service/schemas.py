"""
回测策略 DSL 数据模型
结构化 JSON，LLM 生成，不执行任意代码
"""
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class UniverseConfig(BaseModel):
    """股票池配置"""
    type: str = Field(..., description="类型: static | dividend_screen")
    params: Optional[Dict[str, Any]] = Field(default_factory=dict)
    symbols: Optional[List[str]] = Field(None, description="static 类型的股票列表")


class RuleConfig(BaseModel):
    """规则配置（买入/卖出条件）"""
    type: str = Field(..., description="规则类型")
    # 通用字段
    months: Optional[List[int]] = None  # calendar_month
    days: Optional[int] = None          # holding_days
    field: Optional[str] = None        # indicator: pe, dividend_yield
    op: Optional[str] = None           # indicator: <, >, <=, >=
    value: Optional[float] = None      # indicator 值
    pct: Optional[float] = None        # profit_target, stop_loss


class StrategyConfig(BaseModel):
    """策略 DSL"""
    name: str = Field(..., description="策略名称")
    description: str = Field("", description="策略描述")
    universe: UniverseConfig = Field(...)
    entry_rules: List[RuleConfig] = Field(default_factory=list)
    exit_rules: List[RuleConfig] = Field(default_factory=list)
    config: Dict[str, Any] = Field(
        default_factory=lambda: {
            "start_year": 2016,
            "end_year": 2025,
            "initial_capital": 1000000,
            "position_size": "equal_weight",
            "max_positions": 10,
            "benchmark": "000300",
            "market": "CN",
            "data_source": "tushare",  # 数据源筛选，避免 stock_daily_quotes 多源重复
        }
    )
