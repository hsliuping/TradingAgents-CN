"""index_dailybasic 能力：大盘指数每日指标

粒度 index_daily：指数粒度，按日。
单位口径：total_mv/float_mv=万元（tushare index_dailybasic 原始单位，
工具展示层 /1e8 归一到万亿）、pe/pe_ttm/pb=倍、turnover_rate=%。
接入对侧数据源时必须核对单位并在实现内归一到本 Schema 声明单位。
"""

from ..schema import (
    GRAIN_INDEX_DAILY,
    CapabilityField,
    CapabilityParam,
    CapabilitySchema,
)
from . import register_schema

INDEX_DAILYBASIC_SCHEMA = CapabilitySchema(
    capability_id="index_dailybasic",
    grain=GRAIN_INDEX_DAILY,
    description="大盘指数每日指标（估值/换手/市值快照）",
    fields=[
        CapabilityField("ts_code", "str", True, "指数代码（TS 格式，如 000001.SH）"),
        CapabilityField("trade_date", "str", True, "交易日期 YYYYMMDD"),
        CapabilityField("pe", "float", False, "市盈率（倍）"),
        CapabilityField("pe_ttm", "float", False, "市盈率TTM（倍）"),
        CapabilityField("pb", "float", False, "市净率（倍）"),
        CapabilityField("turnover_rate", "float", False, "换手率（%）"),
        CapabilityField("total_mv", "float", False, "总市值（万元）"),
        CapabilityField("float_mv", "float", False, "流通市值（万元）"),
    ],
    params=[
        CapabilityParam("ts_code", "str", False, "指数代码（TS 格式，如 000001.SH）"),
        CapabilityParam("trade_date", "str", False, "交易日期 YYYYMMDD"),
    ],
)

register_schema(INDEX_DAILYBASIC_SCHEMA)
