"""trade_cal 能力：A 股交易日历（市场级，按日）

粒度 GRAIN_MARKET_DAILY：全市场级日历，无个股维度。

两源口径差异（消费方约定：取 is_open==1 子集即为交易日列表，两源等价）：
- tushare pro.trade_cal：返回区间内全部日历日（含休市日 is_open=0）
- akshare tool_trade_date_hist_sina：新浪历史交易日历仅含交易日、
  无休市行，实现内区间过滤后统一 is_open=1

标准字段：cal_date（datetime）、is_open（1=开市 0=休市）、exchange。
排序约定：cal_date 升序（最旧在前，最新在末）。
"""

from ..schema import (
    GRAIN_MARKET_DAILY,
    CapabilityField,
    CapabilityParam,
    CapabilitySchema,
)
from . import register_schema

TRADE_CAL_SCHEMA = CapabilitySchema(
    capability_id="trade_cal",
    grain=GRAIN_MARKET_DAILY,
    description=(
        "A 股交易日历（区间内日历日 + 开市标记，按 cal_date 升序；"
        "交易日列表取 is_open==1 子集——tushare 含休市行，akshare 仅含交易日）"
    ),
    fields=[
        CapabilityField("exchange", "str", False, "交易所（SSE/SZSE）"),
        CapabilityField("cal_date", "date", True, "日历日期（datetime 类型）"),
        CapabilityField(
            "is_open", "int", True,
            "是否开市（1=交易日，0=休市；akshare 新浪日历仅含交易日，统一为 1）",
        ),
    ],
    params=[
        CapabilityParam("start_date", "str", True, "开始日期 YYYY-MM-DD"),
        CapabilityParam(
            "end_date", "str", False, "结束日期 YYYY-MM-DD（缺省时实现内兜底为当天）"
        ),
    ],
)

register_schema(TRADE_CAL_SCHEMA)
