"""stock_daily_basic 能力：个股每日估值基础指标（区间序列）

粒度 stock_daily：单只股票按日估值指标序列（Tushare daily_basic 按个股区间查询）。

单位与口径：pe/pe_ttm/pb/ps_ttm 为估值倍数；trade_date 为 YYYYMMDD 字符串。
排序约定：trade_date 降序（最新在前）。

注意：与市场级 daily_basic 能力（全市场单日快照，按 trade_date 查全市场）签名不同，
按"粒度不同的数据源不允许注册到同一能力"原则分立。
"""

from ..schema import (
    GRAIN_STOCK_DAILY,
    CapabilityField,
    CapabilityParam,
    CapabilitySchema,
)
from . import register_schema

STOCK_DAILY_BASIC_SCHEMA = CapabilitySchema(
    capability_id="stock_daily_basic",
    grain=GRAIN_STOCK_DAILY,
    description="Tushare-个股-每日估值基础指标区间序列（单股按日）",
    fields=[
        CapabilityField("ts_code", "str", True, "股票代码（含交易所后缀，如 600519.SH）"),
        CapabilityField("trade_date", "str", True, "交易日期 YYYYMMDD"),
        CapabilityField("pe", "float", False, "市盈率（倍）"),
        CapabilityField("pe_ttm", "float", False, "市盈率 TTM（倍）"),
        CapabilityField("pb", "float", False, "市净率（倍）"),
        CapabilityField("ps_ttm", "float", False, "市销率 TTM（倍）"),
    ],
    params=[
        CapabilityParam("symbol", "str", True, "股票代码（6位数字或带交易所后缀）"),
        CapabilityParam("start_date", "str", False, "开始日期 YYYYMMDD"),
        CapabilityParam("end_date", "str", False, "结束日期 YYYYMMDD"),
    ],
)

register_schema(STOCK_DAILY_BASIC_SCHEMA)
