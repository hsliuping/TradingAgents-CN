"""
股票数据同步API路由
支持单个股票或批量股票的历史数据和财务数据同步
"""

from typing import Any, Dict, List, Literal, Optional
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field
from bson import ObjectId

from app.routers.auth_db import get_current_user
from app.core.response import ok
from app.core.database import get_mongo_db
from app.services.database.serialization import serialize_document
from app.worker.tushare_sync_service import get_tushare_sync_service
from app.worker.akshare_sync_service import get_akshare_sync_service
from app.worker.financial_data_sync_service import get_financial_sync_service
import logging
import asyncio
from datetime import datetime, timedelta

logger = logging.getLogger("webapi")

router = APIRouter(prefix="/api/stock-sync", tags=["股票数据同步"])
SYNC_HISTORY_COLLECTION = "stock_sync_history"
SYNC_DELETE_TYPE_LABELS = {
    "historical": "历史行情",
    "financial": "财务数据",
    "basic": "基础数据",
    "realtime_cache": "实时行情展示缓存",
}
SYNC_DELETE_TYPE_IMPACTS = {
    "historical": "影响K线和依赖历史行情的分析输入",
    "financial": "影响基本面分析和财务指标展示",
    "basic": "影响名称、板块、交易所等基础信息展示",
    "realtime_cache": "影响自选股页价格和涨跌幅展示",
}


def _normalize_user_id(current_user: dict) -> str:
    """统一同步历史里的 user_id 存储格式。"""
    return str(
        current_user.get("id")
        or current_user.get("_id")
        or current_user.get("user_id")
        or "anonymous"
    )


def _build_symbol_variants(symbol: str) -> List[str]:
    """为删除/查询构建兼容的代码候选值，兼容前导零和 .HK 后缀。"""
    raw = str(symbol or "").strip().upper()
    variants: List[str] = []

    def _add(value: Optional[str]) -> None:
        if value and value not in variants:
            variants.append(value)

    _add(raw)

    if raw.endswith(".HK"):
        raw = raw[:-3]
        _add(raw)

    if raw.isdigit():
        stripped = raw.lstrip("0") or "0"
        _add(stripped)
        _add(stripped.zfill(5))
        _add(stripped.zfill(6))

    return variants


def _build_symbol_delete_query(fields: List[str], symbol_variants: List[str]) -> Dict[str, Any]:
    return {
        "$or": [
            {field: {"$in": symbol_variants}}
            for field in fields
        ]
    }


def _get_delete_type_collections(delete_type: str) -> List[Dict[str, Any]]:
    if delete_type == "historical":
        return [
            {"collection": "stock_daily_quotes", "fields": ["symbol"]},
            {"collection": "historical_data", "fields": ["symbol"]},
        ]
    if delete_type == "financial":
        return [{"collection": "stock_financial_data", "fields": ["symbol"]}]
    if delete_type == "basic":
        return [{"collection": "stock_basic_info", "fields": ["code", "symbol"]}]
    if delete_type == "realtime_cache":
        return [{"collection": "market_quotes", "fields": ["code", "symbol"]}]
    raise ValueError(f"不支持的删除类型: {delete_type}")


def _merge_collection_plan(plan: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    merged: Dict[str, set] = {}
    for item in plan:
        merged.setdefault(item["collection"], set()).update(item["fields"])
    return [
        {"collection": collection, "fields": sorted(fields)}
        for collection, fields in merged.items()
    ]


def _build_delete_collection_plan(delete_types: List[str], delete_display_cache: bool) -> List[Dict[str, Any]]:
    plan: List[Dict[str, Any]] = []
    for delete_type in delete_types:
        plan.extend(_get_delete_type_collections(delete_type))
        if delete_display_cache and delete_type != "realtime_cache":
            plan.extend(_get_delete_type_collections("realtime_cache"))
    return _merge_collection_plan(plan)


async def _delete_sync_history_for_symbol(
    db,
    *,
    current_user: dict,
    symbol: str,
) -> int:
    query = _build_sync_history_query(
        current_user=current_user,
        symbol=str(symbol or "").strip().upper() or None,
    )
    result = await db[SYNC_HISTORY_COLLECTION].delete_many(query)
    return result.deleted_count


async def _delete_synced_data_for_symbol(
    db,
    *,
    symbol: str,
    delete_types: List[str],
    delete_display_cache: bool,
) -> Dict[str, Any]:
    symbol_input = str(symbol or "").strip().upper()
    symbol_variants = _build_symbol_variants(symbol_input)
    collection_plan = _build_delete_collection_plan(delete_types, delete_display_cache)

    delete_results: List[Dict[str, Any]] = []
    total_deleted = 0

    for item in collection_plan:
        query = _build_symbol_delete_query(item["fields"], symbol_variants)
        result = await db[item["collection"]].delete_many(query)
        delete_results.append({
            "collection": item["collection"],
            "deleted_count": result.deleted_count,
        })
        total_deleted += result.deleted_count

    return {
        "symbol": symbol_input,
        "symbol_variants": symbol_variants,
        "deleted_count": total_deleted,
        "details": delete_results,
    }


def _normalize_datetime_like(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def _parse_csv_values(value: Optional[str], *, case: Optional[str] = None) -> List[str]:
    if not value:
        return []

    parsed_values: List[str] = []
    for item in str(value).split(","):
        normalized = str(item or "").strip()
        if not normalized:
            continue
        if case == "upper":
            normalized = normalized.upper()
        elif case == "lower":
            normalized = normalized.lower()
        if normalized not in parsed_values:
            parsed_values.append(normalized)
    return parsed_values


def _build_case_variants(values: List[str]) -> List[str]:
    variants: List[str] = []
    for value in values:
        for candidate in [value, value.lower(), value.upper()]:
            if candidate and candidate not in variants:
                variants.append(candidate)
    return variants


def _build_sync_history_query(
    current_user: dict,
    symbol: Optional[str] = None,
    sync_types: Optional[List[str]] = None,
    data_sources: Optional[List[str]] = None,
    range_start: Optional[str] = None,
    range_end: Optional[str] = None,
) -> Dict[str, Any]:
    query: Dict[str, Any] = {
        "user_id": _normalize_user_id(current_user)
    }

    if symbol:
        query["symbols"] = {"$in": _build_symbol_variants(symbol)}

    if sync_types:
        query["sync_types"] = {"$in": _build_case_variants(sync_types)}

    if data_sources:
        query["data_sources_used"] = {"$in": _build_case_variants(data_sources)}

    range_conditions: List[Dict[str, Any]] = []
    if range_start:
        range_conditions.append({"historical_range.end_date": {"$gte": range_start}})
    if range_end:
        range_conditions.append({"historical_range.start_date": {"$lte": range_end}})
    if range_conditions:
        query["$and"] = range_conditions

    return query


async def _load_sync_history_records(
    db,
    *,
    current_user: dict,
    page: int = 1,
    page_size: int = 10,
    symbol: Optional[str] = None,
    sync_types: Optional[List[str]] = None,
    data_sources: Optional[List[str]] = None,
    range_start: Optional[str] = None,
    range_end: Optional[str] = None,
) -> Dict[str, Any]:
    page = max(page, 1)
    page_size = min(max(page_size, 1), 100)
    skip = (page - 1) * page_size

    query = _build_sync_history_query(
        current_user=current_user,
        symbol=symbol,
        sync_types=sync_types,
        data_sources=data_sources,
        range_start=range_start,
        range_end=range_end,
    )

    total = await db[SYNC_HISTORY_COLLECTION].count_documents(query)
    cursor = (
        db[SYNC_HISTORY_COLLECTION]
        .find(query)
        .sort("started_at", -1)
        .skip(skip)
        .limit(page_size)
    )
    records = await cursor.to_list(length=page_size)

    return {
        "records": [serialize_document(record) for record in records],
        "total": total,
        "page": page,
        "page_size": page_size,
        "has_more": skip + len(records) < total,
    }


async def _build_historical_summary(db, symbol_variants: List[str]) -> Dict[str, Any]:
    query = {"symbol": {"$in": symbol_variants}}
    daily_count = await db.stock_daily_quotes.count_documents(query)
    legacy_count = await db.historical_data.count_documents(query)
    total_count = daily_count + legacy_count

    sources: List[str] = []
    if daily_count > 0:
        sources.extend([str(item) for item in await db.stock_daily_quotes.distinct("data_source", query) if item])
    if legacy_count > 0:
        legacy_sources = [str(item) for item in await db.historical_data.distinct("data_source", query) if item]
        sources.extend(legacy_sources or ["legacy"])

    earliest_doc = await db.stock_daily_quotes.find_one(query, sort=[("trade_date", 1)])
    latest_doc = await db.stock_daily_quotes.find_one(query, sort=[("trade_date", -1)])
    if earliest_doc is None and legacy_count > 0:
        earliest_doc = await db.historical_data.find_one(query, sort=[("date", 1)])
    if latest_doc is None and legacy_count > 0:
        latest_doc = await db.historical_data.find_one(query, sort=[("date", -1)])

    return {
        "delete_type": "historical",
        "delete_type_label": SYNC_DELETE_TYPE_LABELS["historical"],
        "exists": total_count > 0,
        "record_count": total_count,
        "data_sources": list(dict.fromkeys(sources)),
        "latest_update": _normalize_datetime_like(
            (latest_doc or {}).get("updated_at")
            or (latest_doc or {}).get("trade_date")
            or (latest_doc or {}).get("date")
        ),
        "range_start": _normalize_datetime_like(
            (earliest_doc or {}).get("trade_date")
            or (earliest_doc or {}).get("date")
        ),
        "range_end": _normalize_datetime_like(
            (latest_doc or {}).get("trade_date")
            or (latest_doc or {}).get("date")
        ),
        "affects_favorites_display": False,
        "impact_hint": SYNC_DELETE_TYPE_IMPACTS["historical"],
        "target_collections": ["stock_daily_quotes", "historical_data"],
    }


async def _build_financial_summary(db, symbol_variants: List[str]) -> Dict[str, Any]:
    query = {"symbol": {"$in": symbol_variants}}
    total_count = await db.stock_financial_data.count_documents(query)
    latest_doc = await db.stock_financial_data.find_one(query, sort=[("updated_at", -1), ("report_period", -1)])
    earliest_doc = await db.stock_financial_data.find_one(query, sort=[("report_period", 1)])
    sources = [str(item) for item in await db.stock_financial_data.distinct("data_source", query) if item]

    return {
        "delete_type": "financial",
        "delete_type_label": SYNC_DELETE_TYPE_LABELS["financial"],
        "exists": total_count > 0,
        "record_count": total_count,
        "data_sources": list(dict.fromkeys(sources)),
        "latest_update": _normalize_datetime_like((latest_doc or {}).get("updated_at")),
        "range_start": _normalize_datetime_like((earliest_doc or {}).get("report_period")),
        "range_end": _normalize_datetime_like((latest_doc or {}).get("report_period")),
        "affects_favorites_display": False,
        "impact_hint": SYNC_DELETE_TYPE_IMPACTS["financial"],
        "target_collections": ["stock_financial_data"],
    }


async def _build_basic_summary(db, symbol_variants: List[str]) -> Dict[str, Any]:
    query = _build_symbol_delete_query(["code", "symbol"], symbol_variants)
    total_count = await db.stock_basic_info.count_documents(query)
    latest_doc = await db.stock_basic_info.find_one(query, sort=[("updated_at", -1)])
    sources = [str(item) for item in await db.stock_basic_info.distinct("source", query) if item]

    return {
        "delete_type": "basic",
        "delete_type_label": SYNC_DELETE_TYPE_LABELS["basic"],
        "exists": total_count > 0,
        "record_count": total_count,
        "data_sources": list(dict.fromkeys(sources)),
        "latest_update": _normalize_datetime_like((latest_doc or {}).get("updated_at")),
        "range_start": None,
        "range_end": None,
        "affects_favorites_display": False,
        "impact_hint": SYNC_DELETE_TYPE_IMPACTS["basic"],
        "target_collections": ["stock_basic_info"],
    }


async def _build_realtime_cache_summary(db, symbol_variants: List[str]) -> Dict[str, Any]:
    query = _build_symbol_delete_query(["code", "symbol"], symbol_variants)
    total_count = await db.market_quotes.count_documents(query)
    latest_doc = await db.market_quotes.find_one(query, sort=[("updated_at", -1), ("trade_date", -1)])
    sources = []
    sources.extend([str(item) for item in await db.market_quotes.distinct("data_source", query) if item])
    sources.extend([str(item) for item in await db.market_quotes.distinct("source", query) if item])

    return {
        "delete_type": "realtime_cache",
        "delete_type_label": SYNC_DELETE_TYPE_LABELS["realtime_cache"],
        "exists": total_count > 0,
        "record_count": total_count,
        "data_sources": list(dict.fromkeys(sources)),
        "latest_update": _normalize_datetime_like(
            (latest_doc or {}).get("updated_at")
            or (latest_doc or {}).get("trade_date")
        ),
        "range_start": None,
        "range_end": _normalize_datetime_like((latest_doc or {}).get("trade_date")),
        "affects_favorites_display": True,
        "impact_hint": SYNC_DELETE_TYPE_IMPACTS["realtime_cache"],
        "target_collections": ["market_quotes"],
    }


def _get_sync_types(
    sync_realtime: bool = False,
    sync_historical: bool = False,
    sync_financial: bool = False,
    sync_basic: bool = False,
) -> List[str]:
    sync_types: List[str] = []
    if sync_realtime:
        sync_types.append("realtime")
    if sync_historical:
        sync_types.append("historical")
    if sync_financial:
        sync_types.append("financial")
    if sync_basic:
        sync_types.append("basic")
    return sync_types


def _build_historical_range(sync_historical: bool, days: int) -> Optional[Dict[str, Any]]:
    if not sync_historical:
        return None

    end_date_dt = datetime.now()
    start_date_dt = end_date_dt - timedelta(days=days)
    return {
        "start_date": start_date_dt.strftime("%Y-%m-%d"),
        "end_date": end_date_dt.strftime("%Y-%m-%d"),
        "days": days,
    }


def _collect_data_sources_used(result: Dict[str, Any], requested_source: str) -> List[str]:
    sources: List[str] = []

    for key in ["realtime_sync", "historical_sync", "financial_sync", "basic_sync"]:
        item = result.get(key)
        if not isinstance(item, dict):
            continue

        actual_source = item.get("data_source_used")
        if actual_source:
            sources.append(str(actual_source))
        elif item.get("success") or item.get("success_count", 0) > 0:
            sources.append(requested_source)

    if not sources:
        sources.append(requested_source)

    return list(dict.fromkeys(sources))


def _determine_single_status(request: "SingleStockSyncRequest", result: Dict[str, Any]) -> str:
    selected_keys = []
    if request.sync_realtime:
        selected_keys.append("realtime_sync")
    if request.sync_historical:
        selected_keys.append("historical_sync")
    if request.sync_financial:
        selected_keys.append("financial_sync")
    if request.sync_basic:
        selected_keys.append("basic_sync")

    statuses: List[bool] = []
    for key in selected_keys:
        item = result.get(key)
        statuses.append(bool(item and item.get("success")))

    if statuses and all(statuses):
        return "success"
    if statuses and any(statuses):
        return "partial_success"
    return "failed"


def _determine_batch_status(request: "BatchStockSyncRequest", result: Dict[str, Any]) -> str:
    selected_items: List[Dict[str, Any]] = []
    if request.sync_historical and isinstance(result.get("historical_sync"), dict):
        selected_items.append(result["historical_sync"])
    if request.sync_financial and isinstance(result.get("financial_sync"), dict):
        selected_items.append(result["financial_sync"])
    if request.sync_basic and isinstance(result.get("basic_sync"), dict):
        selected_items.append(result["basic_sync"])

    if not selected_items:
        return "failed"

    success_flags = [item.get("success_count", 0) > 0 for item in selected_items]
    if all(success_flags):
        return "success"
    if any(success_flags):
        return "partial_success"
    return "failed"


def _build_single_summary(request: "SingleStockSyncRequest", result: Dict[str, Any]) -> str:
    summary_parts: List[str] = []

    if request.sync_realtime and isinstance(result.get("realtime_sync"), dict):
        item = result["realtime_sync"]
        summary_parts.append(f"实时行情{'成功' if item.get('success') else '失败'}")

    if request.sync_historical and isinstance(result.get("historical_sync"), dict):
        item = result["historical_sync"]
        if item.get("success"):
            summary_parts.append(f"历史行情 {item.get('records', 0)} 条")
        else:
            summary_parts.append("历史行情失败")

    if request.sync_financial and isinstance(result.get("financial_sync"), dict):
        item = result["financial_sync"]
        summary_parts.append(f"财务数据{'成功' if item.get('success') else '失败'}")

    if request.sync_basic and isinstance(result.get("basic_sync"), dict):
        item = result["basic_sync"]
        summary_parts.append(f"基础数据{'成功' if item.get('success') else '失败'}")

    return "；".join(summary_parts)


def _build_batch_summary(request: "BatchStockSyncRequest", result: Dict[str, Any]) -> str:
    summary_parts: List[str] = []

    if request.sync_historical and isinstance(result.get("historical_sync"), dict):
        item = result["historical_sync"]
        summary_parts.append(
            f"历史行情 {item.get('success_count', 0)}/{len(request.symbols)} 成功，{item.get('total_records', 0)} 条"
        )

    if request.sync_financial and isinstance(result.get("financial_sync"), dict):
        item = result["financial_sync"]
        summary_parts.append(
            f"财务数据 {item.get('success_count', 0)}/{item.get('total_symbols', len(request.symbols))} 成功"
        )

    if request.sync_basic and isinstance(result.get("basic_sync"), dict):
        item = result["basic_sync"]
        summary_parts.append(
            f"基础数据 {item.get('success_count', 0)}/{item.get('total_symbols', len(request.symbols))} 成功"
        )

    return "；".join(summary_parts)


def _collect_errors(result: Dict[str, Any]) -> List[str]:
    errors: List[str] = []
    for key in ["realtime_sync", "historical_sync", "financial_sync", "basic_sync"]:
        item = result.get(key)
        if not isinstance(item, dict):
            continue
        if item.get("error"):
            errors.append(str(item["error"]))
    return errors


def _resolve_single_stock_data_sources(
    request: "SingleStockSyncRequest",
) -> Dict[str, Optional[str]]:
    has_non_realtime_sync = any([request.sync_historical, request.sync_financial, request.sync_basic])

    if request.sync_realtime and not has_non_realtime_sync:
        if request.data_source != "akshare":
            raise HTTPException(
                status_code=400,
                detail="单独同步实时行情时仅支持 AKShare 数据源"
            )
        return {"realtime": "akshare", "non_realtime": None}

    if request.sync_realtime and has_non_realtime_sync:
        if request.data_source == "akshare":
            return {"realtime": "akshare", "non_realtime": "akshare"}
        if request.data_source == "mixed":
            return {"realtime": "akshare", "non_realtime": "tushare"}
        raise HTTPException(
            status_code=400,
            detail="同时同步实时行情和其他数据时，请选择 AKShare 或“实时AKShare+其他Tushare”"
        )

    if request.data_source == "mixed":
        raise HTTPException(
            status_code=400,
            detail="仅在同时同步实时行情和其他数据时才能使用 mixed 数据源"
        )

    return {"realtime": None, "non_realtime": request.data_source}


async def _save_single_sync_history(
    current_user: dict,
    request: "SingleStockSyncRequest",
    result: Dict[str, Any],
    started_at: datetime,
    finished_at: datetime,
) -> None:
    db = get_mongo_db()
    symbols = [str(request.symbol).upper()]
    status = _determine_single_status(request, result)
    errors = _collect_errors(result)

    history_doc = {
        "user_id": _normalize_user_id(current_user),
        "scope": "single",
        "symbol": symbols[0],
        "symbols": symbols,
        "symbol_count": 1,
        "sync_types": _get_sync_types(
            sync_realtime=request.sync_realtime,
            sync_historical=request.sync_historical,
            sync_financial=request.sync_financial,
            sync_basic=request.sync_basic,
        ),
        "historical_range": _build_historical_range(request.sync_historical, request.days),
        "data_source_requested": request.data_source,
        "data_sources_used": _collect_data_sources_used(result, request.data_source),
        "status": status,
        "overall_success": bool(result.get("overall_success")),
        "summary": _build_single_summary(request, result),
        "errors": errors,
        "result": result,
        "started_at": started_at,
        "finished_at": finished_at,
        "duration_seconds": round((finished_at - started_at).total_seconds(), 3),
        "created_at": finished_at,
    }

    await db[SYNC_HISTORY_COLLECTION].insert_one(history_doc)


async def _save_batch_sync_history(
    current_user: dict,
    request: "BatchStockSyncRequest",
    result: Dict[str, Any],
    started_at: datetime,
    finished_at: datetime,
) -> None:
    db = get_mongo_db()
    symbols = [str(symbol).upper() for symbol in request.symbols]
    status = _determine_batch_status(request, result)

    history_doc = {
        "user_id": _normalize_user_id(current_user),
        "scope": "batch",
        "symbol": None,
        "symbols": symbols,
        "symbol_count": len(symbols),
        "sync_types": _get_sync_types(
            sync_historical=request.sync_historical,
            sync_financial=request.sync_financial,
            sync_basic=request.sync_basic,
        ),
        "historical_range": _build_historical_range(request.sync_historical, request.days),
        "data_source_requested": request.data_source,
        "data_sources_used": [request.data_source],
        "status": status,
        "overall_success": result.get("total_success", 0) > 0,
        "summary": _build_batch_summary(request, result),
        "errors": [],
        "result": result,
        "started_at": started_at,
        "finished_at": finished_at,
        "duration_seconds": round((finished_at - started_at).total_seconds(), 3),
        "created_at": finished_at,
    }

    for key in ["historical_sync", "financial_sync", "basic_sync"]:
        item = result.get(key)
        if isinstance(item, dict) and item.get("error"):
            history_doc["errors"].append(str(item["error"]))

    await db[SYNC_HISTORY_COLLECTION].insert_one(history_doc)


async def _sync_latest_to_market_quotes(symbol: str) -> None:
    """
    将 stock_daily_quotes 中的最新数据同步到 market_quotes

    智能判断逻辑：
    - 如果 market_quotes 中已有更新的数据（trade_date 更新），则不覆盖
    - 如果 market_quotes 中没有数据或数据较旧，则更新

    Args:
        symbol: 股票代码（6位）
    """
    db = get_mongo_db()
    symbol6 = str(symbol).zfill(6)

    # 从 stock_daily_quotes 获取最新数据
    latest_doc = await db.stock_daily_quotes.find_one(
        {"symbol": symbol6},
        sort=[("trade_date", -1)]
    )

    if not latest_doc:
        logger.warning(f"⚠️ {symbol6}: stock_daily_quotes 中没有数据")
        return

    historical_trade_date = latest_doc.get("trade_date")

    # 🔥 检查 market_quotes 中是否已有更新的数据
    existing_quote = await db.market_quotes.find_one({"code": symbol6})

    if existing_quote:
        existing_trade_date = existing_quote.get("trade_date")

        # 如果 market_quotes 中的数据日期更新或相同，则不覆盖
        if existing_trade_date and historical_trade_date:
            # 比较日期字符串（格式：YYYY-MM-DD 或 YYYYMMDD）
            existing_date_str = str(existing_trade_date).replace("-", "")
            historical_date_str = str(historical_trade_date).replace("-", "")

            if existing_date_str >= historical_date_str:
                # 🔥 日期相同或更新时，都不覆盖（避免用历史数据覆盖实时数据）
                logger.info(
                    f"⏭️ {symbol6}: market_quotes 中的数据日期 >= 历史数据日期 "
                    f"(market_quotes: {existing_trade_date}, historical: {historical_trade_date})，跳过覆盖"
                )
                return

    # 提取需要的字段
    quote_data = {
        "code": symbol6,
        "symbol": symbol6,
        "close": latest_doc.get("close"),
        "open": latest_doc.get("open"),
        "high": latest_doc.get("high"),
        "low": latest_doc.get("low"),
        "volume": latest_doc.get("volume"),  # 已经转换过单位
        "amount": latest_doc.get("amount"),  # 已经转换过单位
        "pct_chg": latest_doc.get("pct_chg"),
        "pre_close": latest_doc.get("pre_close"),
        "trade_date": latest_doc.get("trade_date"),
        "updated_at": datetime.utcnow()
    }

    # 🔥 日志：记录同步的成交量
    logger.info(
        f"📊 [同步到market_quotes] {symbol6} - "
        f"volume={quote_data['volume']}, amount={quote_data['amount']}, trade_date={quote_data['trade_date']}"
    )

    # 更新 market_quotes
    await db.market_quotes.update_one(
        {"code": symbol6},
        {"$set": quote_data},
        upsert=True
    )


class SingleStockSyncRequest(BaseModel):
    """单股票同步请求"""
    symbol: str = Field(..., description="股票代码（6位）")
    sync_realtime: bool = Field(False, description="是否同步实时行情")
    sync_historical: bool = Field(True, description="是否同步历史数据")
    sync_financial: bool = Field(True, description="是否同步财务数据")
    sync_basic: bool = Field(False, description="是否同步基础数据")
    data_source: Literal["tushare", "akshare", "mixed"] = Field(
        "tushare",
        description="数据源: tushare/akshare/mixed"
    )
    days: int = Field(30, description="历史数据天数", ge=1, le=3650)


class BatchStockSyncRequest(BaseModel):
    """批量股票同步请求"""
    symbols: List[str] = Field(..., description="股票代码列表")
    sync_historical: bool = Field(True, description="是否同步历史数据")
    sync_financial: bool = Field(True, description="是否同步财务数据")
    sync_basic: bool = Field(False, description="是否同步基础数据")
    data_source: str = Field("tushare", description="数据源: tushare/akshare")
    days: int = Field(30, description="历史数据天数", ge=1, le=3650)


class DeleteSyncedDataRequest(BaseModel):
    """删除已同步数据请求"""
    symbol: str = Field(..., description="股票代码")
    delete_type: Literal["historical", "financial", "basic", "realtime_cache"] = Field(
        ...,
        description="删除类型"
    )
    delete_display_cache: bool = Field(False, description="是否同时删除自选股页展示缓存")


class DeleteSyncedDataBatchRequest(BaseModel):
    """批量删除已同步数据请求"""
    symbol: str = Field(..., description="股票代码")
    delete_types: List[Literal["historical", "financial", "basic", "realtime_cache"]] = Field(
        ...,
        description="删除类型列表"
    )
    delete_display_cache: bool = Field(False, description="是否同时删除自选股页展示缓存")


@router.post("/single")
async def sync_single_stock(
    request: SingleStockSyncRequest,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user)
):
    """
    同步单个股票的历史数据、财务数据和实时行情

    - **symbol**: 股票代码（6位）
    - **sync_realtime**: 是否同步实时行情
    - **sync_historical**: 是否同步历史数据
    - **sync_financial**: 是否同步财务数据
    - **data_source**: 数据源（tushare/akshare/mixed）
    - **days**: 历史数据天数
    """
    try:
        started_at = datetime.utcnow()
        logger.info(f"📊 开始同步单个股票: {request.symbol} (数据源: {request.data_source})")

        resolved_sources = _resolve_single_stock_data_sources(request)
        realtime_data_source = resolved_sources["realtime"]
        non_realtime_data_source = resolved_sources["non_realtime"]

        result = {
            "symbol": request.symbol,
            "realtime_sync": None,
            "historical_sync": None,
            "financial_sync": None,
            "basic_sync": None
        }

        # 同步实时行情
        if request.sync_realtime:
            try:
                actual_data_source = realtime_data_source or "akshare"
                service = await get_akshare_sync_service()

                # 同步实时行情（只同步指定的股票）
                realtime_result = await service.sync_realtime_quotes(
                    symbols=[request.symbol],
                    force=True  # 强制执行，跳过交易时间检查
                )

                success = realtime_result.get("success_count", 0) > 0

                message = f"实时行情同步{'成功' if success else '失败'}"

                result["realtime_sync"] = {
                    "success": success,
                    "message": message,
                    "data_source_used": actual_data_source
                }
                logger.info(f"✅ {request.symbol} 实时行情同步完成: {success}")

            except Exception as e:
                logger.error(f"❌ {request.symbol} 实时行情同步失败: {e}")
                result["realtime_sync"] = {
                    "success": False,
                    "error": str(e)
                }
        
        # 同步历史数据
        if request.sync_historical:
            try:
                if non_realtime_data_source == "tushare":
                    service = await get_tushare_sync_service()
                elif non_realtime_data_source == "akshare":
                    service = await get_akshare_sync_service()
                else:
                    raise ValueError(f"不支持的数据源: {non_realtime_data_source}")

                # 计算日期范围
                end_date = datetime.now().strftime('%Y-%m-%d')
                start_date = (datetime.now() - timedelta(days=request.days)).strftime('%Y-%m-%d')

                # 同步历史数据
                hist_result = await service.sync_historical_data(
                    symbols=[request.symbol],
                    start_date=start_date,
                    end_date=end_date,
                    incremental=False
                )

                result["historical_sync"] = {
                    "success": hist_result.get("success_count", 0) > 0,
                    "records": hist_result.get("total_records", 0),
                    "message": f"同步了 {hist_result.get('total_records', 0)} 条历史记录",
                    "data_source_used": non_realtime_data_source
                }
                logger.info(f"✅ {request.symbol} 历史数据同步完成: {hist_result.get('total_records', 0)} 条记录")

                # 🔥 同步最新历史数据到 market_quotes
                if hist_result.get("success_count", 0) > 0:
                    try:
                        await _sync_latest_to_market_quotes(request.symbol)
                        logger.info(f"✅ {request.symbol} 最新数据已同步到 market_quotes")
                    except Exception as e:
                        logger.warning(f"⚠️ {request.symbol} 同步到 market_quotes 失败: {e}")

                # 🔥 【已禁用】如果没有勾选实时行情，但在交易时间内，自动同步实时行情
                # 用户反馈：不希望自动同步实时行情，应该严格按照用户的选择
                # if not request.sync_realtime:
                #     from app.utils.trading_time import is_trading_time
                #     if is_trading_time():
                #         logger.info(f"📊 {request.symbol} 当前在交易时间内，自动同步实时行情")
                #         try:
                #             realtime_result = await service.sync_realtime_quotes(
                #                 symbols=[request.symbol],
                #                 force=True
                #             )
                #             if realtime_result.get("success_count", 0) > 0:
                #                 logger.info(f"✅ {request.symbol} 实时行情自动同步成功")
                #                 result["realtime_sync"] = {
                #                     "success": True,
                #                     "message": "实时行情自动同步成功（交易时间内）"
                #                 }
                #         except Exception as e:
                #             logger.warning(f"⚠️ {request.symbol} 实时行情自动同步失败: {e}")

            except Exception as e:
                logger.error(f"❌ {request.symbol} 历史数据同步失败: {e}")
                result["historical_sync"] = {
                    "success": False,
                    "error": str(e)
                }
        
        # 同步财务数据
        if request.sync_financial:
            try:
                financial_service = await get_financial_sync_service()
                
                # 同步财务数据
                fin_result = await financial_service.sync_single_stock(
                    symbol=request.symbol,
                    data_sources=[non_realtime_data_source]
                )
                
                success = fin_result.get(non_realtime_data_source, False)
                result["financial_sync"] = {
                    "success": success,
                    "message": "财务数据同步成功" if success else "财务数据同步失败",
                    "data_source_used": non_realtime_data_source
                }
                logger.info(f"✅ {request.symbol} 财务数据同步完成: {success}")
                
            except Exception as e:
                logger.error(f"❌ {request.symbol} 财务数据同步失败: {e}")
                result["financial_sync"] = {
                    "success": False,
                    "error": str(e)
                }

        # 同步基础数据
        if request.sync_basic:
            try:
                # 🔥 同步单个股票的基础数据
                # 参考 basics_sync_service 的实现逻辑
                if non_realtime_data_source == "tushare":
                    from app.services.basics_sync import (
                        fetch_stock_basic_df,
                        find_latest_trade_date,
                        fetch_daily_basic_mv_map,
                        fetch_latest_roe_map,
                    )

                    db = get_mongo_db()
                    symbol6 = str(request.symbol).zfill(6)

                    # Step 1: 获取股票基础信息
                    stock_df = await asyncio.to_thread(fetch_stock_basic_df)
                    if stock_df is None or stock_df.empty:
                        result["basic_sync"] = {
                            "success": False,
                            "error": "Tushare 返回空数据"
                        }
                    else:
                        # 筛选出目标股票
                        stock_row = None
                        for _, row in stock_df.iterrows():
                            ts_code = row.get("ts_code", "")
                            if isinstance(ts_code, str) and ts_code.startswith(symbol6):
                                stock_row = row
                                break

                        if stock_row is None:
                            result["basic_sync"] = {
                                "success": False,
                                "error": f"未找到股票 {symbol6} 的基础信息"
                            }
                        else:
                            # Step 2: 获取最新交易日和财务指标
                            latest_trade_date = await asyncio.to_thread(find_latest_trade_date)
                            daily_data_map = await asyncio.to_thread(fetch_daily_basic_mv_map, latest_trade_date)
                            roe_map = await asyncio.to_thread(fetch_latest_roe_map)

                            # Step 3: 构建文档（参考 basics_sync_service 的逻辑）
                            # 🔥 先获取当前时间，避免作用域问题
                            now_iso = datetime.utcnow().isoformat()

                            name = stock_row.get("name") or ""
                            area = stock_row.get("area") or ""
                            industry = stock_row.get("industry") or ""
                            market = stock_row.get("market") or ""
                            list_date = stock_row.get("list_date") or ""
                            ts_code = stock_row.get("ts_code") or ""

                            # 提取6位代码
                            if isinstance(ts_code, str) and "." in ts_code:
                                code = ts_code.split(".")[0]
                            else:
                                code = symbol6

                            # 判断交易所
                            if isinstance(ts_code, str):
                                if ts_code.endswith(".SH"):
                                    sse = "上海证券交易所"
                                elif ts_code.endswith(".SZ"):
                                    sse = "深圳证券交易所"
                                elif ts_code.endswith(".BJ"):
                                    sse = "北京证券交易所"
                                else:
                                    sse = "未知"
                            else:
                                sse = "未知"

                            # 生成 full_symbol
                            full_symbol = ts_code

                            # 提取财务指标
                            daily_metrics = {}
                            if isinstance(ts_code, str) and ts_code in daily_data_map:
                                daily_metrics = daily_data_map[ts_code]

                            # 市值转换（万元 -> 亿元）
                            total_mv_yi = None
                            circ_mv_yi = None
                            if "total_mv" in daily_metrics:
                                try:
                                    total_mv_yi = float(daily_metrics["total_mv"]) / 10000.0
                                except Exception:
                                    pass
                            if "circ_mv" in daily_metrics:
                                try:
                                    circ_mv_yi = float(daily_metrics["circ_mv"]) / 10000.0
                                except Exception:
                                    pass

                            # 构建文档
                            doc = {
                                "code": code,
                                "symbol": code,
                                "name": name,
                                "area": area,
                                "industry": industry,
                                "market": market,
                                "list_date": list_date,
                                "sse": sse,
                                "sec": "stock_cn",
                                "source": "tushare",
                                "updated_at": now_iso,
                                "full_symbol": full_symbol,
                            }

                            # 添加市值
                            if total_mv_yi is not None:
                                doc["total_mv"] = total_mv_yi
                            if circ_mv_yi is not None:
                                doc["circ_mv"] = circ_mv_yi

                            # 添加估值指标
                            for field in ["pe", "pb", "ps", "pe_ttm", "pb_mrq", "ps_ttm"]:
                                if field in daily_metrics:
                                    doc[field] = daily_metrics[field]

                            # 添加 ROE
                            if isinstance(ts_code, str) and ts_code in roe_map:
                                roe_val = roe_map[ts_code].get("roe")
                                if roe_val is not None:
                                    doc["roe"] = roe_val

                            # 添加交易指标
                            for field in ["turnover_rate", "volume_ratio"]:
                                if field in daily_metrics:
                                    doc[field] = daily_metrics[field]

                            # 添加股本信息
                            for field in ["total_share", "float_share"]:
                                if field in daily_metrics:
                                    doc[field] = daily_metrics[field]

                            # Step 4: 更新数据库
                            await db.stock_basic_info.update_one(
                                {"code": code, "source": "tushare"},
                                {"$set": doc},
                                upsert=True
                            )

                            result["basic_sync"] = {
                                "success": True,
                                "message": "基础数据同步成功",
                                "data_source_used": "tushare"
                            }
                            logger.info(f"✅ {request.symbol} 基础数据同步完成")

                elif non_realtime_data_source == "akshare":
                    # 🔥 AKShare 数据源的基础数据同步
                    db = get_mongo_db()
                    symbol6 = str(request.symbol).zfill(6)

                    # 获取 AKShare 同步服务
                    service = await get_akshare_sync_service()

                    # 获取股票基础信息
                    basic_info = await service.provider.get_stock_basic_info(symbol6)

                    if basic_info:
                        # 转换为字典格式
                        if hasattr(basic_info, 'model_dump'):
                            basic_data = basic_info.model_dump()
                        elif hasattr(basic_info, 'dict'):
                            basic_data = basic_info.dict()
                        else:
                            basic_data = basic_info

                        # 确保必要字段
                        basic_data["code"] = symbol6
                        basic_data["symbol"] = symbol6
                        basic_data["source"] = "akshare"
                        basic_data["updated_at"] = datetime.utcnow().isoformat()

                        # 更新到数据库
                        await db.stock_basic_info.update_one(
                            {"code": symbol6, "source": "akshare"},
                            {"$set": basic_data},
                            upsert=True
                        )

                        result["basic_sync"] = {
                            "success": True,
                            "message": "基础数据同步成功",
                            "data_source_used": "akshare"
                        }
                        logger.info(f"✅ {request.symbol} 基础数据同步完成 (AKShare)")
                    else:
                        result["basic_sync"] = {
                            "success": False,
                            "error": "未获取到基础数据"
                        }
                else:
                    result["basic_sync"] = {
                        "success": False,
                        "error": f"基础数据同步仅支持 Tushare/AKShare 数据源，当前数据源: {non_realtime_data_source}"
                    }

            except Exception as e:
                logger.error(f"❌ {request.symbol} 基础数据同步失败: {e}")
                result["basic_sync"] = {
                    "success": False,
                    "error": str(e)
                }

        # 判断整体是否成功
        overall_success = (
            (not request.sync_realtime or result["realtime_sync"].get("success", False)) and
            (not request.sync_historical or result["historical_sync"].get("success", False)) and
            (not request.sync_financial or result["financial_sync"].get("success", False)) and
            (not request.sync_basic or result["basic_sync"].get("success", False))
        )

        # 添加整体成功标志到结果中
        result["overall_success"] = overall_success
        finished_at = datetime.utcnow()
        await _save_single_sync_history(
            current_user=current_user,
            request=request,
            result=result,
            started_at=started_at,
            finished_at=finished_at,
        )

        return ok(
            data=result,
            message=f"股票 {request.symbol} 数据同步{'成功' if overall_success else '部分失败'}"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ 同步单个股票失败: {e}")
        raise HTTPException(status_code=500, detail=f"同步失败: {str(e)}")


@router.post("/batch")
async def sync_batch_stocks(
    request: BatchStockSyncRequest,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user)
):
    """
    批量同步多个股票的历史数据和财务数据
    
    - **symbols**: 股票代码列表
    - **sync_historical**: 是否同步历史数据
    - **sync_financial**: 是否同步财务数据
    - **data_source**: 数据源（tushare/akshare）
    - **days**: 历史数据天数
    """
    try:
        started_at = datetime.utcnow()
        logger.info(f"📊 开始批量同步 {len(request.symbols)} 只股票 (数据源: {request.data_source})")
        
        result = {
            "total": len(request.symbols),
            "symbols": request.symbols,
            "historical_sync": None,
            "financial_sync": None,
            "basic_sync": None
        }
        
        # 同步历史数据
        if request.sync_historical:
            try:
                if request.data_source == "tushare":
                    service = await get_tushare_sync_service()
                elif request.data_source == "akshare":
                    service = await get_akshare_sync_service()
                else:
                    raise ValueError(f"不支持的数据源: {request.data_source}")

                # 计算日期范围
                end_date = datetime.now().strftime('%Y-%m-%d')
                start_date = (datetime.now() - timedelta(days=request.days)).strftime('%Y-%m-%d')
                
                # 批量同步历史数据
                hist_result = await service.sync_historical_data(
                    symbols=request.symbols,
                    start_date=start_date,
                    end_date=end_date,
                    incremental=False
                )
                
                result["historical_sync"] = {
                    "success_count": hist_result.get("success_count", 0),
                    "error_count": hist_result.get("error_count", 0),
                    "total_records": hist_result.get("total_records", 0),
                    "message": f"成功同步 {hist_result.get('success_count', 0)}/{len(request.symbols)} 只股票，共 {hist_result.get('total_records', 0)} 条记录"
                }
                logger.info(f"✅ 批量历史数据同步完成: {hist_result.get('success_count', 0)}/{len(request.symbols)}")
                
            except Exception as e:
                logger.error(f"❌ 批量历史数据同步失败: {e}")
                result["historical_sync"] = {
                    "success_count": 0,
                    "error_count": len(request.symbols),
                    "error": str(e)
                }
        
        # 同步财务数据
        if request.sync_financial:
            try:
                financial_service = await get_financial_sync_service()
                
                # 批量同步财务数据
                fin_results = await financial_service.sync_financial_data(
                    symbols=request.symbols,
                    data_sources=[request.data_source],
                    batch_size=10
                )
                
                source_stats = fin_results.get(request.data_source)
                if source_stats:
                    result["financial_sync"] = {
                        "success_count": source_stats.success_count,
                        "error_count": source_stats.error_count,
                        "total_symbols": source_stats.total_symbols,
                        "message": f"成功同步 {source_stats.success_count}/{source_stats.total_symbols} 只股票的财务数据"
                    }
                else:
                    result["financial_sync"] = {
                        "success_count": 0,
                        "error_count": len(request.symbols),
                        "message": "财务数据同步失败"
                    }
                
                logger.info(f"✅ 批量财务数据同步完成: {result['financial_sync']['success_count']}/{len(request.symbols)}")
                
            except Exception as e:
                logger.error(f"❌ 批量财务数据同步失败: {e}")
                result["financial_sync"] = {
                    "success_count": 0,
                    "error_count": len(request.symbols),
                    "error": str(e)
                }

        # 同步基础数据
        if request.sync_basic:
            try:
                # 🔥 批量同步基础数据
                # 注意：基础数据同步服务目前只支持 Tushare 数据源
                if request.data_source == "tushare":
                    from tradingagents.dataflows.providers.china.tushare import TushareProvider

                    tushare_provider = TushareProvider()
                    if tushare_provider.is_available():
                        success_count = 0
                        error_count = 0

                        for symbol in request.symbols:
                            try:
                                basic_info = await tushare_provider.get_stock_basic_info(symbol)

                                if basic_info:
                                    # 保存到 MongoDB
                                    db = get_mongo_db()
                                    symbol6 = str(symbol).zfill(6)

                                    # 添加必要字段
                                    basic_info["code"] = symbol6
                                    basic_info["source"] = "tushare"
                                    basic_info["updated_at"] = datetime.utcnow()

                                    await db.stock_basic_info.update_one(
                                        {"code": symbol6, "source": "tushare"},
                                        {"$set": basic_info},
                                        upsert=True
                                    )

                                    success_count += 1
                                    logger.info(f"✅ {symbol} 基础数据同步成功")
                                else:
                                    error_count += 1
                                    logger.warning(f"⚠️ {symbol} 未获取到基础数据")
                            except Exception as e:
                                error_count += 1
                                logger.error(f"❌ {symbol} 基础数据同步失败: {e}")

                        result["basic_sync"] = {
                            "success_count": success_count,
                            "error_count": error_count,
                            "total_symbols": len(request.symbols),
                            "message": f"成功同步 {success_count}/{len(request.symbols)} 只股票的基础数据"
                        }
                        logger.info(f"✅ 批量基础数据同步完成: {success_count}/{len(request.symbols)}")
                    else:
                        result["basic_sync"] = {
                            "success_count": 0,
                            "error_count": len(request.symbols),
                            "error": "Tushare 数据源不可用"
                        }
                else:
                    result["basic_sync"] = {
                        "success_count": 0,
                        "error_count": len(request.symbols),
                        "error": f"基础数据同步仅支持 Tushare 数据源，当前数据源: {request.data_source}"
                    }

            except Exception as e:
                logger.error(f"❌ 批量基础数据同步失败: {e}")
                result["basic_sync"] = {
                    "success_count": 0,
                    "error_count": len(request.symbols),
                    "error": str(e)
                }

        # 判断整体是否成功
        hist_success = result["historical_sync"].get("success_count", 0) if request.sync_historical else 0
        fin_success = result["financial_sync"].get("success_count", 0) if request.sync_financial else 0
        basic_success = result["basic_sync"].get("success_count", 0) if request.sync_basic else 0
        total_success = max(hist_success, fin_success, basic_success)

        # 添加统计信息到结果中
        result["total_success"] = total_success
        result["total_symbols"] = len(request.symbols)
        finished_at = datetime.utcnow()
        await _save_batch_sync_history(
            current_user=current_user,
            request=request,
            result=result,
            started_at=started_at,
            finished_at=finished_at,
        )

        return ok(
            data=result,
            message=f"批量同步完成: {total_success}/{len(request.symbols)} 只股票成功"
        )
        
    except Exception as e:
        logger.error(f"❌ 批量同步失败: {e}")
        raise HTTPException(status_code=500, detail=f"批量同步失败: {str(e)}")


@router.get("/history")
async def get_sync_history(
    page: int = 1,
    page_size: int = 10,
    symbol: Optional[str] = None,
    sync_types: Optional[str] = None,
    data_sources: Optional[str] = None,
    range_start: Optional[str] = None,
    range_end: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    """获取当前用户的股票同步历史。"""
    try:
        db = get_mongo_db()
        symbol_input = str(symbol or "").strip().upper() or None
        sync_type_filters = _parse_csv_values(sync_types, case="lower")
        data_source_filters = _parse_csv_values(data_sources, case="lower")

        result = await _load_sync_history_records(
            db,
            current_user=current_user,
            page=page,
            page_size=page_size,
            symbol=symbol_input,
            sync_types=sync_type_filters,
            data_sources=data_source_filters,
            range_start=range_start,
            range_end=range_end,
        )

        return ok(data={
            **result,
            "filters": {
                "symbol": symbol_input,
                "sync_types": sync_type_filters,
                "data_sources": data_source_filters,
                "range_start": range_start,
                "range_end": range_end,
            }
        })
    except Exception as e:
        logger.error(f"❌ 获取同步历史失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取同步历史失败: {str(e)}")


@router.delete("/history/{record_id}")
async def delete_sync_history_record(
    record_id: str,
    current_user: dict = Depends(get_current_user)
):
    """删除一条同步历史记录。"""
    try:
        if not ObjectId.is_valid(record_id):
            raise HTTPException(status_code=400, detail="无效的历史记录ID")

        db = get_mongo_db()
        result = await db[SYNC_HISTORY_COLLECTION].delete_one({
            "_id": ObjectId(record_id),
            "user_id": _normalize_user_id(current_user)
        })

        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="同步历史记录不存在")

        return ok(data={"deleted": True, "record_id": record_id}, message="同步历史已删除")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ 删除同步历史失败: {e}")
        raise HTTPException(status_code=500, detail=f"删除同步历史失败: {str(e)}")


@router.delete("/history")
async def clear_sync_history(
    symbol: Optional[str] = None,
    sync_types: Optional[str] = None,
    data_sources: Optional[str] = None,
    range_start: Optional[str] = None,
    range_end: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    """清空当前用户的同步历史，可按股票代码过滤。"""
    try:
        db = get_mongo_db()
        symbol_input = str(symbol or "").strip().upper() or None
        sync_type_filters = _parse_csv_values(sync_types, case="lower")
        data_source_filters = _parse_csv_values(data_sources, case="lower")
        query = _build_sync_history_query(
            current_user=current_user,
            symbol=symbol_input,
            sync_types=sync_type_filters,
            data_sources=data_source_filters,
            range_start=range_start,
            range_end=range_end,
        )

        result = await db[SYNC_HISTORY_COLLECTION].delete_many(query)
        return ok(
            data={"deleted_count": result.deleted_count},
            message=f"已删除 {result.deleted_count} 条同步历史"
        )
    except Exception as e:
        logger.error(f"❌ 清空同步历史失败: {e}")
        raise HTTPException(status_code=500, detail=f"清空同步历史失败: {str(e)}")


@router.get("/data-summary")
async def get_synced_data_summary(
    symbol: str,
    sync_types: Optional[str] = None,
    data_sources: Optional[str] = None,
    range_start: Optional[str] = None,
    range_end: Optional[str] = None,
    related_history_limit: int = 5,
    current_user: dict = Depends(get_current_user)
):
    """获取单只股票当前已同步数据概览，便于按项删除。"""
    try:
        symbol_input = str(symbol or "").strip().upper()
        if not symbol_input:
            raise HTTPException(status_code=400, detail="股票代码不能为空")

        db = get_mongo_db()
        symbol_variants = _build_symbol_variants(symbol_input)
        sync_type_filters = _parse_csv_values(sync_types, case="lower")
        data_source_filters = _parse_csv_values(data_sources, case="lower")
        items = [
            await _build_historical_summary(db, symbol_variants),
            await _build_financial_summary(db, symbol_variants),
            await _build_basic_summary(db, symbol_variants),
            await _build_realtime_cache_summary(db, symbol_variants),
        ]
        related_history_limit = min(max(related_history_limit, 1), 20)
        related_history = await _load_sync_history_records(
            db,
            current_user=current_user,
            page=1,
            page_size=related_history_limit,
            symbol=symbol_input,
            sync_types=sync_type_filters,
            data_sources=data_source_filters,
            range_start=range_start,
            range_end=range_end,
        )

        return ok(data={
            "symbol": symbol_input,
            "symbol_variants": symbol_variants,
            "items": items,
            "related_history": related_history["records"],
            "related_history_total": related_history["total"],
            "query_context": {
                "symbol": symbol_input,
                "sync_types": sync_type_filters,
                "data_sources": data_source_filters,
                "range_start": range_start,
                "range_end": range_end,
            }
        })
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ 获取已同步数据概览失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取已同步数据概览失败: {str(e)}")


@router.post("/data/delete")
async def delete_synced_data(
    request: DeleteSyncedDataRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    删除单只股票的已同步数据。

    安全策略：
    - 一次只允许删除单一类型
    - 必须显式提供股票代码
    - 可选同时清理自选股页展示缓存（market_quotes）
    """
    try:
        symbol_input = str(request.symbol or "").strip().upper()
        if not symbol_input:
            raise HTTPException(status_code=400, detail="股票代码不能为空")

        db = get_mongo_db()
        delete_result = await _delete_synced_data_for_symbol(
            db,
            symbol=symbol_input,
            delete_types=[request.delete_type],
            delete_display_cache=request.delete_display_cache,
        )

        logger.info(
            "🧹 删除已同步数据: user_id=%s, symbol=%s, delete_type=%s, delete_display_cache=%s, deleted=%s",
            _normalize_user_id(current_user),
            symbol_input,
            request.delete_type,
            request.delete_display_cache,
            delete_result["deleted_count"],
        )

        return ok(
            data={
                "symbol": symbol_input,
                "delete_type": request.delete_type,
                "delete_type_label": SYNC_DELETE_TYPE_LABELS.get(request.delete_type, request.delete_type),
                "delete_display_cache": request.delete_display_cache,
                "symbol_variants": delete_result["symbol_variants"],
                "deleted_count": delete_result["deleted_count"],
                "details": delete_result["details"],
            },
            message=(
                f"已删除 {symbol_input} 的"
                f"{SYNC_DELETE_TYPE_LABELS.get(request.delete_type, request.delete_type)}相关数据"
                + (
                    "，并清理自选股展示缓存"
                    if request.delete_display_cache and request.delete_type != "realtime_cache"
                    else ""
                )
            )
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ 删除已同步数据失败: {e}")
        raise HTTPException(status_code=500, detail=f"删除已同步数据失败: {str(e)}")


@router.post("/data/delete-batch")
async def delete_synced_data_batch(
    request: DeleteSyncedDataBatchRequest,
    current_user: dict = Depends(get_current_user)
):
    """按多种类型批量删除单只股票的已同步数据。"""
    try:
        symbol_input = str(request.symbol or "").strip().upper()
        if not symbol_input:
            raise HTTPException(status_code=400, detail="股票代码不能为空")
        if not request.delete_types:
            raise HTTPException(status_code=400, detail="请至少选择一种删除类型")

        db = get_mongo_db()
        delete_types = list(dict.fromkeys(request.delete_types))
        delete_result = await _delete_synced_data_for_symbol(
            db,
            symbol=symbol_input,
            delete_types=delete_types,
            delete_display_cache=request.delete_display_cache,
        )

        logger.info(
            "🧹 批量删除已同步数据: user_id=%s, symbol=%s, delete_types=%s, delete_display_cache=%s, deleted=%s",
            _normalize_user_id(current_user),
            symbol_input,
            delete_types,
            request.delete_display_cache,
            delete_result["deleted_count"],
        )

        labels = [SYNC_DELETE_TYPE_LABELS.get(item, item) for item in delete_types]
        return ok(
            data={
                "symbol": symbol_input,
                "delete_types": delete_types,
                "delete_type_labels": labels,
                "delete_display_cache": request.delete_display_cache,
                "symbol_variants": delete_result["symbol_variants"],
                "deleted_count": delete_result["deleted_count"],
                "details": delete_result["details"],
            },
            message=(
                f"已删除 {symbol_input} 的{ '、'.join(labels) }"
                + (
                    "，并清理自选股展示缓存"
                    if request.delete_display_cache and "realtime_cache" not in delete_types
                    else ""
                )
            )
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ 批量删除已同步数据失败: {e}")
        raise HTTPException(status_code=500, detail=f"批量删除已同步数据失败: {str(e)}")


@router.get("/status/{symbol}")
async def get_sync_status(
    symbol: str,
    current_user: dict = Depends(get_current_user)
):
    """
    获取股票的同步状态
    
    返回最后同步时间、数据条数等信息
    """
    try:
        from app.core.database import get_mongo_db
        
        db = get_mongo_db()
        
        symbol_variants = _build_symbol_variants(symbol)

        # 历史数据优先读取当前实际使用的 stock_daily_quotes，兼容回退到 legacy historical_data
        hist_doc = await db.stock_daily_quotes.find_one(
            {"symbol": {"$in": symbol_variants}},
            sort=[("trade_date", -1)]
        )
        hist_count = await db.stock_daily_quotes.count_documents({"symbol": {"$in": symbol_variants}})

        if hist_doc is None and hist_count == 0:
            hist_doc = await db.historical_data.find_one(
                {"symbol": {"$in": symbol_variants}},
                sort=[("date", -1)]
            )
            hist_count = await db.historical_data.count_documents({"symbol": {"$in": symbol_variants}})

        # 查询财务数据最后同步时间
        fin_doc = await db.stock_financial_data.find_one(
            {"symbol": {"$in": symbol_variants}},
            sort=[("updated_at", -1)]
        )

        # 统计财务数据条数
        fin_count = await db.stock_financial_data.count_documents({"symbol": {"$in": symbol_variants}})
        
        return ok(data={
            "symbol": symbol,
            "historical_data": {
                "last_sync": hist_doc.get("updated_at") if hist_doc else None,
                "last_date": (
                    hist_doc.get("trade_date")
                    or hist_doc.get("date")
                    if hist_doc else None
                ),
                "total_records": hist_count
            },
            "financial_data": {
                "last_sync": fin_doc.get("updated_at") if fin_doc else None,
                "last_report_period": fin_doc.get("report_period") if fin_doc else None,
                "total_records": fin_count
            }
        })
        
    except Exception as e:
        logger.error(f"❌ 获取同步状态失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取同步状态失败: {str(e)}")
