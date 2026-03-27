"""Skill 运行时项目访问公开门面。"""

from __future__ import annotations

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

4. list_configured_external_sources(market_category="a_shares") -> list[str]
   - 返回当前系统启用的数据源优先级，已排除 local

5. get_external_stock_news(symbol, source=None, limit=10, market_category="a_shares") -> dict
   - 同步获取外部新闻，返回 {source, data}

6. get_external_historical_data(symbol, start_date, end_date, period="daily", source=None, market_category="a_shares") -> dict
   - 同步获取外部历史行情，内部已桥接异步 provider

7. get_external_financial_data(symbol, source=None, market_category="a_shares", report_type="quarterly", period=None, limit=4) -> dict
   - 同步获取外部财务数据，内部已桥接异步 provider

8. get_external_query_news(query, curr_date, look_back_days=7, source="google_news") -> dict
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
- 优先复用 data_access.py 和本模块的同步接口，只有确有必要时再直接 import 第三方库
- 不要直接导入 core.skill_runtime.external_sources / sync_wrappers / catalog
"""