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
    get_external_query_news,
    get_external_stock_news,
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


def query_stock_collection(
    collection: str,
    filters: Optional[Dict[str, Any]] = None,
    projection: Optional[Dict[str, Any]] = None,
    sort: Optional[Sequence[Sequence[Any]]] = None,
    limit: int = 100,
) -> List[Dict[str, Any]]:
    """同步查询已开放的股票集合。"""
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
    """同步执行已开放股票集合的聚合查询。"""
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
    """返回集合样本中的顶层字段和覆盖率摘要。"""
    collection_name = str(collection or "").strip()
    if collection_name not in SUPPORTED_COLLECTIONS:
        raise ValueError(f"unsupported collection: {collection_name}")

    capped_sample_size = max(1, min(int(sample_size), 100))
    db = _get_db()
    docs = [
        _strip_object_id(item)
        for item in db[collection_name].find(filters or {}, {"_id": 0}).limit(capped_sample_size)
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

    return {
        "collection": collection_name,
        "sample_count": sample_count,
        "query_keys": metadata.get("query_keys", []),
        "preferred_access": metadata.get("preferred_access", []),
        "top_level_fields": [field_name for field_name, _ in ordered_fields],
        "field_coverage": field_coverage,
        "sample_documents": docs[: min(3, sample_count)],
    }


def inspect_symbol_documents(
    collection: str,
    symbol: str,
    limit: int = 5,
) -> List[Dict[str, Any]]:
    """返回指定 symbol 在集合中的样本文档。"""
    collection_name = str(collection or "").strip()
    if collection_name not in SUPPORTED_COLLECTIONS:
        raise ValueError(f"unsupported collection: {collection_name}")

    normalized_symbol = str(symbol or "").strip().zfill(6)
    capped_limit = max(1, min(int(limit), 20))
    db = _get_db()

    filters: Dict[str, Any] = {"$or": [{"symbol": normalized_symbol}, {"code": normalized_symbol}]}
    cursor = db[collection_name].find(filters, {"_id": 0})

    if collection_name == "stock_daily_quotes":
        cursor = cursor.sort("trade_date", -1)
    elif collection_name == "stock_financial_data":
        cursor = cursor.sort([("report_period", -1), ("report_date", -1)])
    elif collection_name == "stock_news":
        cursor = cursor.sort("publish_time", -1)

    return [_strip_object_id(item) for item in cursor.limit(capped_limit)]


def inspect_field_coverage(
    collection: str,
    fields: Sequence[str],
    filters: Optional[Dict[str, Any]] = None,
    sample_size: int = 50,
) -> Dict[str, Any]:
    """返回字段在样本文档中的出现率和非空覆盖率。"""
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
   - 允许访问: stock_basic_info, market_quotes, stock_daily_quotes, stock_financial_data, stock_news
   - 适用于需要直接按字段读库的 Skill

3. aggregate_stock_collection(collection, pipeline, limit=100) -> list[dict]
   - 通用本地聚合入口
   - 只有 data_access 的 helper 无法满足时再使用

侦察/诊断专用接口（前置分析可用，最终 Skill 主逻辑通常不应依赖）：

4. inspect_stock_collection_schema(collection, sample_size=20, filters=None) -> dict
    - 返回集合样本中的字段列表、字段覆盖率和少量样本文档

5. inspect_symbol_documents(collection, symbol, limit=5) -> list[dict]
    - 返回指定 symbol 在集合中的最新样本文档

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

11. get_external_query_news(query, curr_date, look_back_days=7, source="google_news") -> dict
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