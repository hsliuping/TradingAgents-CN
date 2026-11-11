"""financial_income 能力：个股利润表（按报告期）

粒度 stock_period：一行一个报告期（end_date），按报告期降序返回。
单位口径：金额字段单位=元（与 tushare 原生一致），basic_eps 单位=元/股。
标准字段名沿用 tushare 利润表原生字段名，akshare（东财 EM）经 field_mapping 映射。

多源口径说明：
- tushare（主源）：income 接口逐报告期拉取，字段齐全；
- akshare（降级源）：东财 EM 利润表（stock_profit_sheet_by_report_em），
  大写字段经 field_mapping 映射为标准名，未覆盖字段门面补 NaN，消费方需容错；
- local（降级源）：MongoDB stock_financial_data 缓存的 income_statement 桶，
  字段名经 field_mapping 对齐 tushare 口径。
"""

from ..schema import (
    GRAIN_STOCK_PERIOD,
    CapabilityField,
    CapabilityParam,
    CapabilitySchema,
)
from . import register_schema

FINANCIAL_INCOME_SCHEMA = CapabilitySchema(
    capability_id="financial_income",
    grain=GRAIN_STOCK_PERIOD,
    description="个股利润表（按报告期：营业总收入/营业收入/营业利润/净利润/归母净利润/基本EPS）",
    fields=[
        CapabilityField("end_date", "str", True, "报告期 YYYYMMDD（如 20260930）"),
        CapabilityField("ann_date", "str", False, "公告日期 YYYYMMDD"),
        CapabilityField("f_ann_date", "str", False, "实际公告日期 YYYYMMDD"),
        CapabilityField("total_revenue", "float", False, "营业总收入（元）"),
        CapabilityField("revenue", "float", False, "营业收入（元）"),
        CapabilityField("operate_profit", "float", False, "营业利润（元）"),
        CapabilityField("n_income_attr_p", "float", False, "归属母公司净利润（元）"),
        CapabilityField("n_income", "float", False, "净利润（含少数股东损益，元）"),
        CapabilityField("basic_eps", "float", False, "基本每股收益（元/股）"),
    ],
    params=[
        CapabilityParam("symbol", "str", True, "股票代码（6位数字，如 600519）"),
        CapabilityParam("limit", "int", False, "返回最近 N 个报告期（默认全部可用）"),
    ],
)

register_schema(FINANCIAL_INCOME_SCHEMA)
