"""daily_basic 能力：全市场个股每日指标快照

粒度 stock_daily：个股粒度，按日。
单位口径：total_mv/circ_mv=万元（tushare daily_basic 原始单位），
pe/pb/pe_ttm/pb_mrq=倍、turnover_rate/volume_ratio=%。
当前 provider 实现按 trade_date 拉全市场单日快照（返回不含 trade_date 列，
查询维度由参数声明），接入对侧数据源时必须核对单位并在实现内归一。
"""

from ..schema import (
    GRAIN_STOCK_DAILY,
    CapabilityField,
    CapabilityParam,
    CapabilitySchema,
)
from . import register_schema

DAILY_BASIC_SCHEMA = CapabilitySchema(
    capability_id="daily_basic",
    grain=GRAIN_STOCK_DAILY,
    description="全市场个股每日指标快照（市值/估值/换手，按 trade_date 查单日）",
    fields=[
        CapabilityField("ts_code", "str", True, "股票代码（TS 格式，如 000001.SZ）"),
        CapabilityField("total_mv", "float", False, "总市值（万元）"),
        CapabilityField("circ_mv", "float", False, "流通市值（万元）"),
        CapabilityField("pe", "float", False, "市盈率（倍）"),
        CapabilityField("pb", "float", False, "市净率（倍）"),
        CapabilityField("turnover_rate", "float", False, "换手率（%）"),
        CapabilityField("volume_ratio", "float", False, "量比"),
        CapabilityField("pe_ttm", "float", False, "市盈率TTM（倍）"),
        CapabilityField("pb_mrq", "float", False, "市净率MRQ（倍）"),
        CapabilityField("close", "float", False, "收盘价（元）"),
    ],
    params=[
        CapabilityParam("trade_date", "str", True, "交易日期 YYYYMMDD（单日快照）"),
    ],
)

register_schema(DAILY_BASIC_SCHEMA)
