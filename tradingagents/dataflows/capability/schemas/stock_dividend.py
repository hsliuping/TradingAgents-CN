"""stock_dividend 能力：个股历史分红送股（Tushare）

粒度 stock_event：个股分红送股事件流（含预案/实施等各进度记录，div_proc 区分）。

单位与口径：stk_bo_rate/stk_co_rate/stk_div 为每股送转口径；cash_div 为每股股利（税后）、
cash_div_tax 为每股派息（税前），单位元；日期字段为源接口原生 YYYYMMDD 字符串（可能为空）。
排序约定：end_date 降序（最新在前）。

注意：与 stock_dividend_cninfo（巨潮，每10股比例口径、YYYY-MM-DD 日期）口径不同，分立两个能力。
"""

from ..schema import (
    GRAIN_STOCK_EVENT,
    CapabilityField,
    CapabilityParam,
    CapabilitySchema,
)
from . import register_schema

STOCK_DIVIDEND_SCHEMA = CapabilitySchema(
    capability_id="stock_dividend",
    grain=GRAIN_STOCK_EVENT,
    description="Tushare-个股-分红送股事件记录",
    fields=[
        CapabilityField("ts_code", "str", True, "股票代码（含交易所后缀）"),
        CapabilityField("end_date", "str", True, "分红年度截止日 YYYYMMDD"),
        CapabilityField("ann_date", "str", False, "公告日期 YYYYMMDD"),
        CapabilityField("div_proc", "str", False, "实施进度（预案/股东大会通过/实施等）"),
        CapabilityField("stk_div", "float", False, "每股送转股票数量（股）"),
        CapabilityField("stk_bo_rate", "float", False, "每股送股比例（股）"),
        CapabilityField("stk_co_rate", "float", False, "每股转增比例（股）"),
        CapabilityField("cash_div", "float", False, "每股现金股利（元，税后）"),
        CapabilityField("cash_div_tax", "float", False, "每股派息（元，税前）"),
        CapabilityField("record_date", "str", False, "股权登记日 YYYYMMDD"),
        CapabilityField("ex_date", "str", False, "除权除息日 YYYYMMDD"),
        CapabilityField("pay_date", "str", False, "派息日 YYYYMMDD"),
    ],
    params=[
        CapabilityParam("symbol", "str", True, "股票代码（6位数字或带交易所后缀）"),
        CapabilityParam("limit", "int", False, "返回记录条数上限（按 end_date 降序截断）"),
    ],
)

register_schema(STOCK_DIVIDEND_SCHEMA)
