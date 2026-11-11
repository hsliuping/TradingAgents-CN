"""pledge_detail 能力：股权质押明细

粒度 stock_event：个股质押事件流（按公告）。
单位口径：数量为万股、比例为 %（tushare pledge_detail 原始口径）。
"""

from ..schema import (
    GRAIN_STOCK_EVENT,
    CapabilityField,
    CapabilityParam,
    CapabilitySchema,
)
from . import register_schema

# 空结果状态标记（DataFrame.attrs 键）：
# facade 不暴露逐源结果，"成功但无数据"（空 DataFrame，不降级）与
# "全部源请求失败"（降级穷尽后返回结构化空表）在返回值上不可区分。
# 契约化适配器以本键在空 DataFrame.attrs 上标记逐源状态
# （如 {"akshare": "success_empty"}），调用方据此保持
# data_source_status 的 success/empty/error 三态语义。
SOURCE_STATUS_ATTR = "pledge_detail_source_status"

PLEDGE_DETAIL_SCHEMA = CapabilitySchema(
    capability_id="pledge_detail",
    grain=GRAIN_STOCK_EVENT,
    description="股权质押明细（个股质押事件流，按公告）",
    fields=[
        CapabilityField("ts_code", "str", True, "股票代码（TS 格式，如 600519.SH）"),
        CapabilityField("ann_date", "str", True, "公告日期 YYYYMMDD"),
        CapabilityField("holder_name", "str", False, "股东名称"),
        CapabilityField("pledge_amount", "float", False, "质押数量（万股）"),
        CapabilityField("start_date", "str", False, "质押开始日期 YYYYMMDD"),
        CapabilityField("end_date", "str", False, "质押结束日期 YYYYMMDD"),
        CapabilityField("is_released", "str", False, "是否已解押（0否 1是）"),
        CapabilityField("release_date", "str", False, "解押日期 YYYYMMDD"),
        CapabilityField("pledgor", "str", False, "质押方"),
        CapabilityField("holding_amount", "float", False, "持股总数（万股）"),
        CapabilityField("pledged_amount", "float", False, "质押总数（万股）"),
        CapabilityField("pledge_total_ratio", "float", False, "本次质押占总股本比例（%）"),
        CapabilityField("holding_total_ratio", "float", False, "持股总数占总股本比例（%）"),
        CapabilityField("is_buyback", "str", False, "是否回购（0否 1是）"),
    ],
    params=[
        CapabilityParam("ts_code", "str", False, "股票代码（TS 格式）"),
        CapabilityParam("ann_date", "str", False, "公告日期 YYYYMMDD"),
        CapabilityParam("start_date", "str", False, "公告开始日期 YYYYMMDD"),
        CapabilityParam("end_date", "str", False, "公告结束日期 YYYYMMDD"),
    ],
)

register_schema(PLEDGE_DETAIL_SCHEMA)
