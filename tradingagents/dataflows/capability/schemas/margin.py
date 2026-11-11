"""margin 能力：融资融券交易汇总（两融余额）

粒度 market_daily：全市场（可含交易所维度）按日汇总。
注意：个股粒度的两融明细（如 tushare margin_detail）粒度不同，
不允许注册到本能力，应另立 stock_margin 能力。

单位与口径：金额单位为元（原始口径，不换算亿元），数量单位为股。
"""

from ..schema import (
    GRAIN_MARKET_DAILY,
    CapabilityField,
    CapabilityParam,
    CapabilitySchema,
)
from . import register_schema

MARGIN_SCHEMA = CapabilitySchema(
    capability_id="margin",
    grain=GRAIN_MARKET_DAILY,
    description="融资融券交易汇总（两融余额，全市场按日汇总）",
    fields=[
        CapabilityField("trade_date", "str", True, "交易日期 YYYYMMDD"),
        CapabilityField(
            "exchange_id", "str", False,
            "交易所代码（SSE上交所/SZSE深交所/TOTAL全市场合计）。"
            "不同源返回粒度可能不同：tushare 返回交易所分项行，akshare 默认返回 "
            "TOTAL 合计行；按日取全市场两融余额时应按 trade_date 汇总全部行",
        ),
        CapabilityField("margin_balance", "float", True, "融资余额（元）"),
        CapabilityField("margin_buy_amount", "float", False, "融资买入额（元）"),
        CapabilityField("margin_repay_amount", "float", False, "融资偿还额（元）"),
        CapabilityField("short_balance", "float", False, "融券余额（元）"),
        CapabilityField("short_sell_volume", "float", False, "融券卖出量（股）"),
        CapabilityField("total_balance", "float", False, "融资融券余额（元）= 融资余额 + 融券余额"),
    ],
    params=[
        CapabilityParam("trade_date", "str", False, "交易日期 YYYYMMDD（精确查询）"),
        CapabilityParam("start_date", "str", False, "开始日期 YYYYMMDD"),
        CapabilityParam("end_date", "str", False, "结束日期 YYYYMMDD"),
        CapabilityParam("exchange_id", "str", False, "交易所代码 SSE/SZSE"),
    ],
)

register_schema(MARGIN_SCHEMA)
