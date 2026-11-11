"""financial_cashflow 能力：个股现金流量表（按报告期）

粒度 stock_period：一行一个报告期（end_date），按报告期降序返回。
单位口径：金额字段单位=元（与 tushare 原生一致）。
标准字段名沿用 tushare 现金流量表原生字段名，akshare（东财 EM）经 field_mapping 映射。

多源口径说明：
- tushare（主源）：cashflow 接口逐报告期拉取，字段齐全；
  历史实现存在 'n_cashflow_fin_act' 误写（筹资活动净额真实字段名为
  'n_cash_flows_fnc_act'），tushare 源经 field_mapping 防御映射兜底；
- akshare（降级源）：东财 EM 现金流量表（stock_cash_flow_sheet_by_report_em），
  大写字段经 field_mapping 映射为标准名（含期初/期末现金及等价物 BEGIN_CCE/END_CCE），
  未覆盖字段门面补 NaN，消费方需容错；
- local（降级源）：MongoDB stock_financial_data 缓存的 cash_flow/cashflow_statement 桶，
  字段名经 field_mapping 对齐 tushare 口径。
"""

from ..schema import (
    GRAIN_STOCK_PERIOD,
    CapabilityField,
    CapabilityParam,
    CapabilitySchema,
)
from . import register_schema

FINANCIAL_CASHFLOW_SCHEMA = CapabilitySchema(
    capability_id="financial_cashflow",
    grain=GRAIN_STOCK_PERIOD,
    description="个股现金流量表（按报告期：经营/投资/筹资活动现金流净额、期初期末现金及等价物）",
    fields=[
        CapabilityField("end_date", "str", True, "报告期 YYYYMMDD（如 20260930）"),
        CapabilityField("ann_date", "str", False, "公告日期 YYYYMMDD"),
        CapabilityField("f_ann_date", "str", False, "实际公告日期 YYYYMMDD"),
        CapabilityField("n_cashflow_act", "float", False, "经营活动产生的现金流量净额（元）"),
        CapabilityField("n_cashflow_inv_act", "float", False, "投资活动产生的现金流量净额（元）"),
        CapabilityField("n_cash_flows_fnc_act", "float", False, "筹资活动产生的现金流量净额（元）"),
        CapabilityField("c_cash_equ_beg_period", "float", False, "期初现金及现金等价物余额（元）"),
        CapabilityField("c_cash_equ_end_period", "float", False, "期末现金及现金等价物余额（元）"),
    ],
    params=[
        CapabilityParam("symbol", "str", True, "股票代码（6位数字，如 600519）"),
        CapabilityParam("limit", "int", False, "返回最近 N 个报告期（默认全部可用）"),
    ],
)

register_schema(FINANCIAL_CASHFLOW_SCHEMA)
