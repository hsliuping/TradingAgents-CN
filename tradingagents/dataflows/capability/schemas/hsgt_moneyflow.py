"""hsgt_moneyflow 能力：沪深港通资金流向（北向/南向净流入）

粒度 market_daily：全市场按日汇总。
单位口径：金额为 tushare moneyflow_hsgt 原始单位（百万元），未换算；
接入对侧数据源时必须核对单位并在实现内归一到本 Schema 声明单位。
north_net_flow / south_net_flow 为同源派生合计（沪+深），非跨源推算。
"""

from ..schema import (
    GRAIN_MARKET_DAILY,
    CapabilityField,
    CapabilityParam,
    CapabilitySchema,
)
from . import register_schema

HSGT_MONEYFLOW_SCHEMA = CapabilitySchema(
    capability_id="hsgt_moneyflow",
    grain=GRAIN_MARKET_DAILY,
    description="沪深港通资金流向（北向/南向净流入，按日汇总）",
    fields=[
        CapabilityField("trade_date", "str", True, "交易日期 YYYYMMDD"),
        CapabilityField("north_sh_flow", "float", False, "沪股通净流入（百万元，tushare 原始口径）"),
        CapabilityField("north_sz_flow", "float", False, "深股通净流入（百万元，tushare 原始口径）"),
        CapabilityField("south_sh_flow", "float", False, "港股通（沪）净流入（百万元，tushare 原始口径）"),
        CapabilityField("south_sz_flow", "float", False, "港股通（深）净流入（百万元，tushare 原始口径）"),
        CapabilityField("north_net_flow", "float", True, "北向净流入合计（百万元）= 沪股通 + 深股通"),
        CapabilityField("south_net_flow", "float", True, "南向净流入合计（百万元）= 港股通沪 + 港股通深"),
    ],
    params=[
        CapabilityParam("trade_date", "str", False, "交易日期 YYYYMMDD"),
        CapabilityParam("start_date", "str", False, "开始日期 YYYYMMDD"),
        CapabilityParam("end_date", "str", False, "结束日期 YYYYMMDD"),
    ],
)

register_schema(HSGT_MONEYFLOW_SCHEMA)
