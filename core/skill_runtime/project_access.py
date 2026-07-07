"""Skill 运行时项目访问公开门面。"""

from __future__ import annotations

from collections import Counter
from typing import Any, Dict, List, Optional, Sequence

from .catalog import (
    SUPPORTED_COLLECTIONS,
    list_configured_external_sources,
    list_supported_stock_collections,
)
from .data_access import _get_db
from .external_sources import (
    get_external_financial_data,
    get_external_historical_data,
    get_external_valuation_data,
    get_external_query_news,
    get_external_stock_news,
)


_SCALAR_PREVIEW_LIMIT = 160
_FIELD_PREVIEW_LIMIT = 20
_NESTED_KEY_PREVIEW_LIMIT = 12
_LIST_PREVIEW_LIMIT = 3
_SUMMARY_PRIORITY_FIELDS = (
    "symbol",
    "code",
    "name",
    "ts_code",
    "report_period",
    "report_date",
    "ann_date",
    "publish_time",
    "trade_date",
    "end_date",
    "industry",
    "pe",
    "pb",
    "peg",
    "roe",
    "market_value",
)


def _get_collection_metadata(collection: str) -> Dict[str, Any]:
    for item in list_supported_stock_collections():
        if item.get("collection") == collection:
            return item
    return {}


def _strip_object_id(doc: Dict[str, Any]) -> Dict[str, Any]:
    normalized = dict(doc or {})
    normalized.pop("_id", None)
    return normalized


def _is_non_empty_value(value: Any) -> bool:
    return value not in (None, "", [], {})


def _truncate_text(value: str, limit: int = _SCALAR_PREVIEW_LIMIT) -> str:
    if len(value) <= limit:
        return value
    return f"{value[:limit]}...({len(value)} chars)"


def _summarize_value(value: Any) -> Any:
    if isinstance(value, str):
        return _truncate_text(value)
    if isinstance(value, (int, float, bool)) or value is None:
        return value
    if isinstance(value, dict):
        keys = sorted(str(key) for key in value.keys())
        return {
            "type": "object",
            "key_count": len(keys),
            "sample_keys": keys[:_NESTED_KEY_PREVIEW_LIMIT],
        }
    if isinstance(value, list):
        item_types = sorted({type(item).__name__ for item in value[:_LIST_PREVIEW_LIMIT]})
        return {
            "type": "array",
            "length": len(value),
            "item_types": item_types,
        }
    return _truncate_text(str(value))


def _build_scalar_preview(doc: Dict[str, Any]) -> Dict[str, Any]:
    preview: Dict[str, Any] = {}

    for field_name in _SUMMARY_PRIORITY_FIELDS:
        if field_name in doc and _is_non_empty_value(doc.get(field_name)):
            preview[field_name] = _summarize_value(doc.get(field_name))

    if len(preview) >= _FIELD_PREVIEW_LIMIT:
        return preview

    for field_name in sorted(doc.keys()):
        if field_name in preview:
            continue
        value = doc.get(field_name)
        if not _is_non_empty_value(value):
            continue
        if isinstance(value, (dict, list)):
            continue
        preview[field_name] = _summarize_value(value)
        if len(preview) >= _FIELD_PREVIEW_LIMIT:
            break

    return preview


def _build_nested_field_summary(doc: Dict[str, Any]) -> Dict[str, Any]:
    nested_fields: Dict[str, Any] = {}
    for field_name, value in doc.items():
        if isinstance(value, dict):
            nested_fields[field_name] = _summarize_value(value)
        elif isinstance(value, list):
            nested_fields[field_name] = _summarize_value(value)
    return nested_fields


def _build_document_summary(doc: Dict[str, Any]) -> Dict[str, Any]:
    field_names = sorted(doc.keys())
    summary: Dict[str, Any] = {
        "field_count": len(field_names),
        "non_null_field_count": sum(1 for value in doc.values() if _is_non_empty_value(value)),
        "fields": field_names[:_FIELD_PREVIEW_LIMIT],
    }
    remaining_field_count = max(0, len(field_names) - _FIELD_PREVIEW_LIMIT)
    if remaining_field_count:
        summary["truncated_field_count"] = remaining_field_count

    scalar_preview = _build_scalar_preview(doc)
    if scalar_preview:
        summary["scalar_preview"] = scalar_preview

    nested_fields = _build_nested_field_summary(doc)
    if nested_fields:
        summary["nested_fields"] = nested_fields

    return summary


def _get_document_count(collection_ref: Any, filters: Dict[str, Any]) -> Dict[str, Any]:
    if filters:
        return {
            "matching_document_count": collection_ref.count_documents(filters),
            "matching_count_is_estimated": False,
        }
    return {
        "matching_document_count": collection_ref.estimated_document_count(),
        "matching_count_is_estimated": True,
    }


def query_stock_collection(
    collection: str,
    filters: Optional[Dict[str, Any]] = None,
    projection: Optional[Dict[str, Any]] = None,
    sort: Optional[Sequence[Sequence[Any]]] = None,
    limit: int = 100,
) -> List[Dict[str, Any]]:
    """同步查询已开放的股票集合。

    Args:
        collection: 集合名称，必须在 SUPPORTED_COLLECTIONS 中（如 "stock_basic_info" /
            "market_quotes" / "stock_daily_quotes" / "stock_financial_data" /
            "stock_financial_periods" / "stock_news"）
        filters: MongoDB 查询过滤条件，为 None 时等价于空 dict（查询全部），默认 None
        projection: MongoDB 投影规则，为 None 时默认排除 _id 字段（{"_id": 0}），默认 None
        sort: 排序规则，形如 [("trade_date", -1), ("symbol", 1)] 的二元组序列，为 None 时不排序，默认 None
        limit: 返回文档数量上限，会被截断到 [1, 500] 区间，默认 100

    Returns:
        list[dict]: 命中文档列表，每个元素为集合中的一条原始文档（dict）——
            - 默认已剔除 _id 字段（除非 projection 显式包含）
            - 列表长度 <= limit（经过 [1, 500] 截断后的值）
            - 文档字段结构依集合定义而异，常见字段如 symbol/code/name/trade_date 等
    """
    collection_name = str(collection or "").strip()
    if collection_name not in SUPPORTED_COLLECTIONS:
        raise ValueError(f"unsupported collection: {collection_name}")

    db = _get_db()
    cursor = db[collection_name].find(filters or {}, projection or {"_id": 0})
    if sort:
        cursor = cursor.sort(list(sort))
    return list(cursor.limit(max(1, min(int(limit), 500))))


def aggregate_stock_collection(
    collection: str,
    pipeline: Sequence[Dict[str, Any]],
    limit: int = 100,
) -> List[Dict[str, Any]]:
    """同步执行已开放股票集合的聚合查询。

    Args:
        collection: 集合名称，必须在 SUPPORTED_COLLECTIONS 中（如 "stock_basic_info" /
            "market_quotes" / "stock_daily_quotes" / "stock_financial_data" /
            "stock_financial_periods" / "stock_news"）
        pipeline: MongoDB 聚合管道阶段序列，形如 [{"$match": {...}}, {"$group": {...}}]，
            为空时返回全部文档
        limit: 返回结果数量上限，会被截断到 [1, 500] 区间，默认 100

    Returns:
        list[dict]: 聚合结果列表，每个元素为聚合管道输出的一条文档（dict）——
            - 已自动剔除每条结果中的 _id 字段
            - 列表长度 <= limit（经过 [1, 500] 截断后的值）
            - 字段结构由 pipeline 的 $group / $project 等阶段决定
    """
    collection_name = str(collection or "").strip()
    if collection_name not in SUPPORTED_COLLECTIONS:
        raise ValueError(f"unsupported collection: {collection_name}")

    db = _get_db()
    results = list(db[collection_name].aggregate(list(pipeline or [])))
    capped_results = results[: max(1, min(int(limit), 500))]
    for item in capped_results:
        item.pop("_id", None)
    return capped_results


def inspect_stock_collection_schema(
    collection: str,
    sample_size: int = 20,
    filters: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """返回集合样本中的顶层字段、覆盖率、条数和结构摘要。

    Args:
        collection: 集合名称，必须在 SUPPORTED_COLLECTIONS 中（如 "stock_basic_info" /
            "market_quotes" / "stock_daily_quotes" / "stock_financial_data" /
            "stock_financial_periods" / "stock_news"）
        sample_size: 采样文档数量，会被截断到 [1, 100] 区间，默认 20
        filters: MongoDB 查询过滤条件，为 None 时采样全部文档，默认 None

    Returns:
        dict: 字段说明（代码中使用 .get() 或 [] 访问这些 key）——
            collection: 实际查询的集合名称
            matching_document_count: 命中文档总数（filters 为空时为估算值）
            matching_count_is_estimated: 命中数是否为估算值（filters 为空时为 True，
                否则为 False 表示精确计数）
            sample_count: 实际采样到的文档数（<= sample_size 截断后的值）
            query_keys: 集合元数据中标记的常用查询字段列表（来自 catalog）
            preferred_access: 集合元数据中标记的推荐访问方式列表（来自 catalog）
            top_level_fields: 样本中出现的顶层字段名列表，按出现频次降序、字段名升序排列
            field_coverage: 字段覆盖率字典 {field_name: coverage_ratio}，coverage_ratio
                为 0-1 之间保留 4 位小数的浮点数，表示该字段在样本中的出现比例
            sample_document_summaries: 前 min(3, sample_count) 条文档的摘要列表，
                每个元素结构 — field_count(顶层字段总数),
                non_null_field_count(非空字段数), fields(顶层字段名列表，最多 20 个),
                truncated_field_count(被截断的字段数，可选),
                scalar_preview(标量字段预览字典，可选),
                nested_fields(嵌套对象/数组字段摘要字典，可选)
    """
    collection_name = str(collection or "").strip()
    if collection_name not in SUPPORTED_COLLECTIONS:
        raise ValueError(f"unsupported collection: {collection_name}")

    capped_sample_size = max(1, min(int(sample_size), 100))
    db = _get_db()
    collection_ref = db[collection_name]
    normalized_filters = filters or {}
    docs = [
        _strip_object_id(item)
        for item in collection_ref.find(normalized_filters, {"_id": 0}).limit(capped_sample_size)
    ]

    field_counter: Counter[str] = Counter()
    for item in docs:
        if not isinstance(item, dict):
            continue
        field_counter.update(item.keys())

    sample_count = len(docs)
    ordered_fields = sorted(
        field_counter.items(),
        key=lambda pair: (-pair[1], pair[0]),
    )
    field_coverage = {
        field_name: round(count / sample_count, 4)
        for field_name, count in ordered_fields
        if sample_count > 0
    }
    metadata = _get_collection_metadata(collection_name)
    sample_summaries = [_build_document_summary(item) for item in docs[: min(3, sample_count)]]
    count_summary = _get_document_count(collection_ref, normalized_filters)

    return {
        "collection": collection_name,
        **count_summary,
        "sample_count": sample_count,
        "query_keys": metadata.get("query_keys", []),
        "preferred_access": metadata.get("preferred_access", []),
        "top_level_fields": [field_name for field_name, _ in ordered_fields],
        "field_coverage": field_coverage,
        "sample_document_summaries": sample_summaries,
    }


def inspect_symbol_documents(
    collection: str,
    symbol: str,
    limit: int = 5,
) -> Dict[str, Any]:
    """返回指定 symbol 在集合中的样本文档摘要，而不是完整文档。

    Args:
        collection: 集合名称，必须在 SUPPORTED_COLLECTIONS 中（如 "stock_basic_info" /
            "market_quotes" / "stock_daily_quotes" / "stock_financial_data" /
            "stock_financial_periods" / "stock_news"）
        symbol: A 股股票代码（6 位数字或含交易所前后缀），内部会 zfill(6) 标准化，
            同时匹配 symbol 或 code 字段
        limit: 返回文档摘要数量上限，会被截断到 [1, 20] 区间，默认 5

    Returns:
        dict: 字段说明（代码中使用 .get() 或 [] 访问这些 key）——
            collection: 实际查询的集合名称
            symbol: 标准化后的 6 位股票代码
            matching_document_count: 集合中匹配该 symbol/code 的文档总数（精确计数）
            returned_summary_count: 实际返回的文档摘要数量（<= limit 截断后的值）
            documents: 文档摘要列表，每个元素结构 — field_count(顶层字段总数),
                non_null_field_count(非空字段数), fields(顶层字段名列表，最多 20 个),
                truncated_field_count(被截断的字段数，可选),
                scalar_preview(标量字段预览字典，可选),
                nested_fields(嵌套对象/数组字段摘要字典，可选)
            排序规则（按集合类型自动选择）：stock_daily_quotes 按 trade_date 倒序；
                stock_financial_data 按 (report_period, report_date) 倒序；
                stock_financial_periods 按 (report_period, ann_date) 倒序；
                stock_news 按 publish_time 倒序；其它集合不排序
    """
    collection_name = str(collection or "").strip()
    if collection_name not in SUPPORTED_COLLECTIONS:
        raise ValueError(f"unsupported collection: {collection_name}")

    normalized_symbol = str(symbol or "").strip().zfill(6)
    capped_limit = max(1, min(int(limit), 20))
    db = _get_db()

    filters: Dict[str, Any] = {"$or": [{"symbol": normalized_symbol}, {"code": normalized_symbol}]}
    collection_ref = db[collection_name]
    cursor = collection_ref.find(filters, {"_id": 0})

    if collection_name == "stock_daily_quotes":
        cursor = cursor.sort("trade_date", -1)
    elif collection_name == "stock_financial_data":
        cursor = cursor.sort([("report_period", -1), ("report_date", -1)])
    elif collection_name == "stock_financial_periods":
        cursor = cursor.sort([("report_period", -1), ("ann_date", -1)])
    elif collection_name == "stock_news":
        cursor = cursor.sort("publish_time", -1)

    docs = [_strip_object_id(item) for item in cursor.limit(capped_limit)]
    return {
        "collection": collection_name,
        "symbol": normalized_symbol,
        "matching_document_count": collection_ref.count_documents(filters),
        "returned_summary_count": len(docs),
        "documents": [_build_document_summary(item) for item in docs],
    }


def inspect_field_coverage(
    collection: str,
    fields: Sequence[str],
    filters: Optional[Dict[str, Any]] = None,
    sample_size: int = 50,
) -> Dict[str, Any]:
    """返回字段在样本文档中的出现率和非空覆盖率。

    Args:
        collection: 集合名称，必须在 SUPPORTED_COLLECTIONS 中（如 "stock_basic_info" /
            "market_quotes" / "stock_daily_quotes" / "stock_financial_data" /
            "stock_financial_periods" / "stock_news"）
        fields: 待统计覆盖率的字段名序列，空字符串/空白字段会被自动过滤
        filters: MongoDB 查询过滤条件，为 None 时采样全部文档，默认 None
        sample_size: 采样文档数量上限，会被截断到 [1, 200] 区间，默认 50

    Returns:
        dict: 字段说明（代码中使用 .get() 或 [] 访问这些 key）——
            collection: 实际查询的集合名称
            sample_count: 实际采样到的文档数（<= sample_size 截断后的值）
            fields: 字段覆盖率行列表，每个元素结构 —
                field(字段名), present_count(出现的文档数),
                non_null_count(非空文档数，None/""/[]/{} 视为空),
                present_coverage(出现率 0-1 保留 4 位小数),
                non_null_coverage(非空覆盖率 0-1 保留 4 位小数；
                    sample_count 为 0 时为 0.0)
    """
    collection_name = str(collection or "").strip()
    if collection_name not in SUPPORTED_COLLECTIONS:
        raise ValueError(f"unsupported collection: {collection_name}")

    normalized_fields = [str(field).strip() for field in fields if str(field).strip()]
    capped_sample_size = max(1, min(int(sample_size), 200))
    db = _get_db()
    docs = list(db[collection_name].find(filters or {}, {"_id": 0}).limit(capped_sample_size))
    sample_count = len(docs)

    coverage_rows: List[Dict[str, Any]] = []
    for field_name in normalized_fields:
        present_count = 0
        non_null_count = 0
        for item in docs:
            if not isinstance(item, dict):
                continue
            if field_name in item:
                present_count += 1
                if item.get(field_name) not in (None, "", [], {}):
                    non_null_count += 1
        coverage_rows.append(
            {
                "field": field_name,
                "present_count": present_count,
                "non_null_count": non_null_count,
                "present_coverage": round(present_count / sample_count, 4) if sample_count else 0.0,
                "non_null_coverage": round(non_null_count / sample_count, 4) if sample_count else 0.0,
            }
        )

    return {
        "collection": collection_name,
        "sample_count": sample_count,
        "fields": coverage_rows,
    }


PROJECT_DATA_ACCESS_DOC = """
【项目数据访问接口】

生成的 Skill 运行在独立 Python 子进程中，执行入口是同步函数。
因此：
- 不要在 Skill 里定义 async def
- 不要在 Skill 里使用 await
- 若需要外部 provider 的异步方法，优先调用本模块提供的同步 wrapper

说明：
- 本模块是 Skill 运行时的公开门面
- catalog.py / external_sources.py / sync_wrappers.py 属于内部实现细分层
- 生成的 Skill 代码应只导入本模块或 data_access.py，不要直接导入这些内部模块

允许导入：from core.skill_runtime.project_access import ...

可用同步接口：

1. list_supported_stock_collections() -> list[dict]
   - 查看当前允许 Skill 直接访问的本地集合目录

2. query_stock_collection(collection, filters=None, projection=None, sort=None, limit=100) -> list[dict]
   - 通用本地集合查询入口
    - 允许访问: stock_basic_info, market_quotes, stock_daily_quotes, stock_financial_data, stock_financial_periods, stock_news
   - 适用于需要直接按字段读库的 Skill

3. aggregate_stock_collection(collection, pipeline, limit=100) -> list[dict]
   - 通用本地聚合入口
   - 只有 data_access 的 helper 无法满足时再使用

侦察/诊断专用接口（前置分析可用，最终 Skill 主逻辑通常不应依赖）：

4. inspect_stock_collection_schema(collection, sample_size=20, filters=None) -> dict
    - 返回集合样本中的字段列表、字段覆盖率、估算/匹配条数和少量样本摘要

5. inspect_symbol_documents(collection, symbol, limit=5) -> dict
    - 返回指定 symbol 在集合中的最新样本文档摘要、命中条数和字段结构

6. inspect_field_coverage(collection, fields, filters=None, sample_size=50) -> dict
    - 返回给定字段的出现率和非空覆盖率

7. list_configured_external_sources(market_category="a_shares") -> list[str]
   - 返回当前系统启用的数据源优先级，已排除 local

8. get_external_stock_news(symbol, source=None, limit=10, market_category="a_shares") -> dict
   - 同步获取外部新闻，返回 {source, data}

9. get_external_historical_data(symbol, start_date, end_date, period="daily", source=None, market_category="a_shares") -> dict
   - 同步获取外部历史行情，内部已桥接异步 provider

10. get_external_financial_data(symbol, source=None, market_category="a_shares", report_type="quarterly", period=None, limit=4) -> dict
   - 同步获取外部财务数据，内部已桥接异步 provider

11. get_external_valuation_data(symbol, start_date, end_date, source=None, market_category="a_shares") -> dict
   - 同步获取外部历史估值序列（PE_TTM、PB_MRQ、PS_TTM、PCF_TTM），内部使用 BaoStock
   - 返回 {source: "baostock", data: [{date, close, pe_ttm, pb_mrq, ps_ttm, pcf_ttm}, ...]}
   - 估值类 Skill（历史分位数、安全边际、PE/PB 通道等）优先用这个函数，不要用 get_external_historical_data（那个只含 OHLCV 价格）

12. get_external_query_news(query, curr_date, look_back_days=7, source="google_news") -> dict
   - 通过项目已有接口获取 Google News / Finnhub 新闻

使用示例1：直接读本地集合
    from core.skill_runtime.project_access import query_stock_collection

    peers = query_stock_collection(
        "stock_basic_info",
        filters={"industry": {"$regex": "白酒", "$options": "i"}, "pb": {"$gt": 0}},
        projection={"_id": 0, "symbol": 1, "name": 1, "pb": 1, "industry": 1},
        limit=50,
    )

使用示例2：按当前配置自动选择外部历史数据源
    from core.skill_runtime.project_access import get_external_historical_data

    history = get_external_historical_data("600519", "2024-01-01", "2025-01-01")
    rows = history["data"]

使用示例3：显式指定外部财务源
    from core.skill_runtime.project_access import get_external_financial_data

    finance = get_external_financial_data("600519", source="tushare", report_type="quarterly", limit=4)

硬规则：
- 不要自行 import pymongo / MongoClient
- 不要硬编码数据库名
- 不要在 Skill 中直接 await provider.get_historical_data / get_financial_data
- inspect_* 系列接口主要用于前置侦察、调试和字段核验，不建议在最终 Skill 业务逻辑中依赖
- 优先复用 data_access.py 和本模块的同步接口，只有确有必要时再直接 import 第三方库
- 不要直接导入 core.skill_runtime.external_sources / sync_wrappers / catalog
"""