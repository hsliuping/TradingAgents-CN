"""
共享的文档指标处理函数
- add_financial_metrics: 将日度基础指标（市值/估值/交易）追加到文档中
"""
from typing import Dict, List, Optional


# daily_basic 请求字段 -> stock_basic_info 文档字段
# 与 basics_sync/utils.fetch_daily_basic_mv_map 的 fields 列表保持一致。
# 关键用途：亏损股的 pe_ttm/ps_ttm 等会被上游置空（NaN），同步时必须 $unset
# 历史残留的正值，否则页面会一直显示旧估值（如牧原 2026-07 的 pe_ttm=23.19）。
DAILY_BASIC_FIELD_MAP = {
    "total_mv": "total_mv",
    "circ_mv": "circ_mv",
    "pe": "pe",
    "pb": "pb",
    "ps": "ps",
    "pe_ttm": "pe_ttm",
    "pb_mrq": "pb_mrq",
    "ps_ttm": "ps_ttm",
    "turnover_rate": "turnover_rate",
    "volume_ratio": "volume_ratio",
    "total_share": "total_share",
    "float_share": "float_share",
    "dv_ratio": "dividend_yield",
    "dv_ttm": "dividend_yield_ttm",
}


def _is_missing_number(value) -> bool:
    if value is None:
        return True
    try:
        f = float(value)
    except (ValueError, TypeError):
        return True
    return f != f  # NaN


def add_financial_metrics(
    doc: Dict,
    daily_metrics: Dict,
    stale_fields: Optional[List[str]] = None,
    available_fields: Optional[set] = None,
) -> None:
    """
    将财务与交易指标写入 doc（就地修改）。
    - 市值：total_mv/circ_mv（从万元转换为亿元）
    - 估值：pe/pb/pe_ttm/pb_mrq/ps/ps_ttm（过滤 NaN/None）
    - 交易：turnover_rate/volume_ratio（过滤 NaN/None）
    - 股本：total_share/float_share（万股，过滤 NaN/None）
    - 分红：dv_ratio/dv_ttm -> dividend_yield/dividend_yield_ttm（过滤 NaN/None）

    Args:
        stale_fields: 传入空列表时，函数会把"该股票在当日批次中存在、但上游显式
            返回空值"的文档字段名收集进去，供调用方拼 ``$unset`` 清理历史脏值。
            仅当该股票确实出现在当日 daily_basic 批次中时才应传入（停牌缺行勿传）。
        available_fields: 本次批次上游实际返回的列名集合。None 表示全量
            （Tushare 路径，fields 固定请求 14 个字段）；多数据源路径应传
            DataFrame 的实际列，避免把该源不提供的字段误判为置空。
    """
    can_unset = stale_fields is not None
    api_fields = DAILY_BASIC_FIELD_MAP.keys() if available_fields is None else available_fields

    for api_field in api_fields:
        doc_field = DAILY_BASIC_FIELD_MAP.get(api_field)
        if doc_field is None:
            continue
        raw = daily_metrics.get(api_field)
        if _is_missing_number(raw):
            if can_unset:
                stale_fields.append(doc_field)
            continue

        value = float(raw)
        if api_field in ("total_mv", "circ_mv"):
            doc[doc_field] = value / 10000  # 万元 -> 亿元
        else:
            doc[doc_field] = value
