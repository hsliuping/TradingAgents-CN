"""能力标准 Schema 注册表

每种数据能力在此登记标准 Schema；注册装饰器（register_capability）
在挂载时会按 capability_id 查表强制校验。
"""

from typing import Dict

from ..schema import CapabilitySchema

SCHEMAS: Dict[str, CapabilitySchema] = {}


def register_schema(schema: CapabilitySchema) -> None:
    if schema.capability_id in SCHEMAS:
        raise ValueError(f"能力 Schema 重复注册: '{schema.capability_id}'")
    SCHEMAS[schema.capability_id] = schema


def get_schema(capability_id: str) -> CapabilitySchema:
    if capability_id not in SCHEMAS:
        raise ValueError(
            f"未知数据能力: '{capability_id}'。"
            f"请先在 tradingagents/dataflows/capability/schemas/ 中定义标准 Schema。"
            f"已注册能力: {sorted(SCHEMAS)}"
        )
    return SCHEMAS[capability_id]


# 内置能力 Schema（import 即注册）
from . import margin  # noqa: E402,F401
from . import hsgt_moneyflow  # noqa: E402,F401
from . import index_daily  # noqa: E402,F401
from . import index_dailybasic  # noqa: E402,F401
from . import daily_info  # noqa: E402,F401
from . import daily_basic  # noqa: E402,F401
from . import daily_stats  # noqa: E402,F401
from . import limit_list  # noqa: E402,F401
from . import stk_limit  # noqa: E402,F401
from . import pledge_detail  # noqa: E402,F401
from . import audit_opinion  # noqa: E402,F401
from . import disclosure_rating  # noqa: E402,F401
from . import equity_incentive  # noqa: E402,F401
from . import management_penalties  # noqa: E402,F401
from . import ths_index  # noqa: E402,F401
from . import ths_member  # noqa: E402,F401
from . import ths_daily  # noqa: E402,F401
from . import stock_industry  # noqa: E402,F401
from . import moneyflow_ind_ths  # noqa: E402,F401
from . import moneyflow_cnt_ths  # noqa: E402,F401
from . import sector_stocks_daily_basic  # noqa: E402,F401
from . import bond_china_yield  # noqa: E402,F401
from . import bond_yield_cn_us  # noqa: E402,F401
from . import stock_cyq  # noqa: E402,F401
from . import stock_dividend_cninfo  # noqa: E402,F401
from . import fund_etf_spot  # noqa: E402,F401
from . import fund_etf_nav_daily  # noqa: E402,F401
from . import fund_etf_nav_info  # noqa: E402,F401
from . import fund_etf_hist  # noqa: E402,F401
from . import fund_etf_basic  # noqa: E402,F401
from . import financial_income  # noqa: E402,F401
from . import financial_balance  # noqa: E402,F401
from . import financial_cashflow  # noqa: E402,F401
from . import financial_indicators  # noqa: E402,F401
from . import stock_daily_basic  # noqa: E402,F401
from . import stock_dividend  # noqa: E402,F401
from . import stock_daily  # noqa: E402,F401
from . import stock_news_cn  # noqa: E402,F401
from . import trade_cal  # noqa: E402,F401
