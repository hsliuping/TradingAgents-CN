"""daily_info 能力：交易所板块日度交易统计

粒度 market_daily：市场板块汇总，按日（SH_MARKET/SZ_MARKET 等板块行）。
单位口径：total_share/float_share=亿股、total_mv/float_mv/amount=亿元、
vol=亿股、trans_count=万笔、pe=倍、tr=%（tushare daily_info 原始单位，
与工具展示口径一致，接入对侧数据源时必须核对单位并在实现内归一）。
"""

from ..schema import (
    GRAIN_MARKET_DAILY,
    CapabilityField,
    CapabilityParam,
    CapabilitySchema,
)
from . import register_schema

DAILY_INFO_SCHEMA = CapabilitySchema(
    capability_id="daily_info",
    grain=GRAIN_MARKET_DAILY,
    description="交易所板块日度交易统计（挂牌数/成交/市值/换手，单日快照）",
    fields=[
        CapabilityField("trade_date", "str", True, "交易日期 YYYYMMDD"),
        CapabilityField("ts_code", "str", True, "市场板块代码（如 SH_MARKET/SZ_MARKET）"),
        CapabilityField("ts_name", "str", False, "市场板块名称"),
        CapabilityField("exchange", "str", False, "交易所（SH上交所 SZ深交所）"),
        CapabilityField("com_count", "int", False, "挂牌数（家）"),
        CapabilityField("total_share", "float", False, "总股本（亿股）"),
        CapabilityField("float_share", "float", False, "流通股本（亿股）"),
        CapabilityField("total_mv", "float", False, "总市值（亿元）"),
        CapabilityField("float_mv", "float", False, "流通市值（亿元）"),
        CapabilityField("amount", "float", False, "交易金额（亿元）"),
        CapabilityField("vol", "float", False, "成交量（亿股）"),
        CapabilityField("pe", "float", False, "平均市盈率（倍）"),
        CapabilityField("tr", "float", False, "换手率（%），深交所暂无此列"),
    ],
    params=[
        CapabilityParam("trade_date", "str", True, "交易日期 YYYYMMDD"),
        CapabilityParam("exchange", "str", False, "交易所（SH上交所 SZ深交所）"),
    ],
)

register_schema(DAILY_INFO_SCHEMA)
