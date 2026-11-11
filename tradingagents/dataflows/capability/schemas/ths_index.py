"""ths_index 能力：同花顺板块列表

粒度 reference：参考快照，无时间粒度（板块列表全量快照）。
接入对侧数据源时必须对齐字段语义（type: N=行业板块/S=概念板块/R=地域板块/I=行业指数）。
"""

from ..schema import (
    GRAIN_REFERENCE,
    CapabilityField,
    CapabilityParam,
    CapabilitySchema,
)
from . import register_schema

THS_INDEX_SCHEMA = CapabilitySchema(
    capability_id="ths_index",
    grain=GRAIN_REFERENCE,
    description="同花顺板块列表（行业/概念/地域/行业指数，全量快照）",
    fields=[
        CapabilityField("ts_code", "str", True, "板块代码（TS 格式，如 885691.TI）"),
        CapabilityField("name", "str", True, "板块名称（如 酿酒行业）"),
        CapabilityField("count", "int", False, "板块成分股数量"),
        CapabilityField("exchange", "str", False, "交易所（A=所有，其余为单市场）"),
        CapabilityField("list_date", "str", False, "板块纳入日期 YYYYMMDD"),
        CapabilityField("type", "str", False, "板块类型（N/S/R/I）"),
    ],
    params=[
        CapabilityParam("index_type", "str", True, "板块类型：N=行业/S=概念/R=地域/I=行业指数"),
    ],
)

register_schema(THS_INDEX_SCHEMA)
