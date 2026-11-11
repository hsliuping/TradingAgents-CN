"""stock_dividend_cninfo 能力：巨潮资讯个股历史分红

粒度 stock_event：个股分红事件流（已实施方案记录）。

单位与口径：送股/转增/派息比例为源接口原生口径（每10股比例）；
日期字段均为 YYYY-MM-DD 字符串（可能为空）。
"""

from ..schema import (
    GRAIN_STOCK_EVENT,
    CapabilityField,
    CapabilityParam,
    CapabilitySchema,
)
from . import register_schema

STOCK_DIVIDEND_CNINFO_SCHEMA = CapabilitySchema(
    capability_id="stock_dividend_cninfo",
    grain=GRAIN_STOCK_EVENT,
    description="巨潮资讯-个股-历史分红（已实施方案记录）",
    fields=[
        CapabilityField("announce_date", "str", False, "实施方案公告日期 YYYY-MM-DD"),
        CapabilityField("dividend_type", "str", False, "分红类型"),
        CapabilityField("stock_bonus_ratio", "float", False, "送股比例（每10股送X股）"),
        CapabilityField("transfer_ratio", "float", False, "转增比例（每10股转增X股）"),
        CapabilityField("cash_ratio", "float", False, "派息比例（每10股派X元）"),
        CapabilityField("record_date", "str", False, "股权登记日 YYYY-MM-DD"),
        CapabilityField("ex_date", "str", False, "除权日 YYYY-MM-DD"),
        CapabilityField("pay_date", "str", False, "派息日 YYYY-MM-DD"),
        CapabilityField("share_arrival_date", "str", False, "股份到账日 YYYY-MM-DD"),
        CapabilityField("plan_description", "str", False, "实施方案分红说明"),
        CapabilityField("report_period", "str", False, "报告时间"),
    ],
    params=[
        CapabilityParam("symbol", "str", True, "股票代码（6位数字，如 600009）"),
    ],
)

register_schema(STOCK_DIVIDEND_CNINFO_SCHEMA)
