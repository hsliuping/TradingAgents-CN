"""数据能力协议（CapabilitySchema）

每种数据能力（如融资融券 margin）一份标准定义：
标准字段集合、标准查询参数、数据粒度。

设计文档：docs/05-design/v4.0/data-architecture-problems-and-optimization.md 5.4
"""

from dataclasses import dataclass, field
from typing import List

# 能力粒度常量（必须显式声明，防止降级语义漂移：
# 粒度不同的数据源不允许注册到同一能力，而是拆成不同能力）
GRAIN_MARKET_DAILY = "market_daily"   # 全市场汇总，按日（如两融交易汇总）
GRAIN_STOCK_DAILY = "stock_daily"     # 个股粒度，按日（如个股两融明细）
GRAIN_STOCK_EVENT = "stock_event"     # 个股事件流（如龙虎榜、审计意见）
GRAIN_INDEX_DAILY = "index_daily"     # 指数粒度，按日（如指数日线行情）
GRAIN_FUND_DAILY = "fund_daily"       # 基金粒度，按日（如 ETF 历史净值/日线）
GRAIN_REFERENCE = "reference"         # 参考快照，无时间粒度（列表/映射/属性类）
GRAIN_STOCK_PERIOD = "stock_period"   # 个股粒度，按报告期（如三大报表、财务指标）


@dataclass(frozen=True)
class CapabilityField:
    """能力标准字段定义"""
    name: str            # 标准字段名，如 margin_balance
    dtype: str           # float / int / str / date
    required: bool       # 是否必填（缺失时 quality 标记 partial）
    description: str     # 语义 + 单位（元/股/亿元），禁止隐式约定


@dataclass(frozen=True)
class CapabilityParam:
    """能力标准查询参数定义"""
    name: str
    dtype: str
    required: bool = False
    description: str = ""


@dataclass(frozen=True)
class CapabilitySchema:
    """数据能力标准协议"""
    capability_id: str              # 能力 ID，如 'margin'
    fields: List[CapabilityField]   # 标准输出字段
    params: List[CapabilityParam]   # 标准查询参数
    grain: str                      # 粒度：GRAIN_* 常量
    description: str = ""

    def standard_field_names(self) -> List[str]:
        return [f.name for f in self.fields]

    def required_field_names(self) -> List[str]:
        return [f.name for f in self.fields if f.required]

    def validate_field_mapping(self, field_mapping: dict) -> None:
        """注册时强制校验：映射目标必须是标准字段（防止能力内字段口径发散）"""
        standard = set(self.standard_field_names())
        for raw_name, std_name in field_mapping.items():
            if std_name not in standard:
                raise ValueError(
                    f"能力 '{self.capability_id}' 的字段映射目标 '{std_name}' "
                    f"不在标准字段集合中（原始字段: '{raw_name}'）。"
                    f"标准字段: {sorted(standard)}。"
                    f"如需新增字段，请先扩展 {self.capability_id} 的 Schema 定义。"
                )
