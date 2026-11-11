"""sector_stocks_daily_basic 能力：行业成分股每日指标

粒度 stock_daily：个股粒度，按日（单日快照，按行业过滤）。
单位口径：total_mv/circ_mv=万元（tushare daily_basic 原始单位），
pe/pe_ttm/pb=倍、turnover_rate=%。
实现为复合查询（行业成分 + 全市场 daily_basic 过滤合并 name），
接入对侧数据源时需提供等价的行业过滤能力。
"""

from ..schema import (
    GRAIN_STOCK_DAILY,
    CapabilityField,
    CapabilityParam,
    CapabilitySchema,
)
from . import register_schema

SECTOR_STOCKS_DAILY_BASIC_SCHEMA = CapabilitySchema(
    capability_id="sector_stocks_daily_basic",
    grain=GRAIN_STOCK_DAILY,
    description="行业成分股每日指标快照（市值/估值/换手，按 industry+trade_date 查询）",
    fields=[
        CapabilityField("ts_code", "str", True, "股票代码（TS 格式，如 000001.SZ）"),
        CapabilityField("name", "str", False, "股票名称（实现内合并）"),
        CapabilityField("trade_date", "str", False, "交易日期 YYYYMMDD"),
        CapabilityField("close", "float", False, "收盘价（元）"),
        CapabilityField("pe", "float", False, "市盈率（倍）"),
        CapabilityField("pe_ttm", "float", False, "市盈率TTM（倍）"),
        CapabilityField("pb", "float", False, "市净率（倍）"),
        CapabilityField("total_mv", "float", False, "总市值（万元）"),
        CapabilityField("circ_mv", "float", False, "流通市值（万元）"),
        CapabilityField("turnover_rate", "float", False, "换手率（%）"),
    ],
    params=[
        CapabilityParam("industry", "str", True, "行业名称（如 银行，精确匹配）"),
        CapabilityParam("trade_date", "str", True, "交易日期 YYYYMMDD"),
    ],
)

register_schema(SECTOR_STOCKS_DAILY_BASIC_SCHEMA)
