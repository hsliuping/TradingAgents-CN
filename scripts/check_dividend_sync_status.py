#!/usr/bin/env python3
"""
检查 MongoDB 中分红/股息率字段是否已同步。

用途：
1. 检查 stock_basic_info 是否存在 dividend_yield
2. 检查 stock_financial_data 是否存在 flat/nested dividend_yield
3. 检查 stock_screening_view 是否存在 dividend_yield
4. 打印样例数据，便于判断智能筛选为何查不到高分红股票

使用方法：
    python scripts/check_dividend_sync_status.py
    python scripts/check_dividend_sync_status.py --limit 10
    python scripts/check_dividend_sync_status.py --code 600036
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Iterable

from pymongo import MongoClient


PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from app.core.config import settings  # noqa: E402


def print_section(title: str) -> None:
    print(f"\n{'=' * 80}")
    print(title)
    print(f"{'=' * 80}")


def format_doc(doc: dict[str, Any], keys: Iterable[str]) -> str:
    parts = []
    for key in keys:
        parts.append(f"{key}={doc.get(key)!r}")
    return ", ".join(parts)


def print_samples(title: str, docs: list[dict[str, Any]], keys: list[str]) -> None:
    print(f"\n{title}:")
    if not docs:
        print("  - 无样例")
        return
    for index, doc in enumerate(docs, start=1):
        print(f"  {index}. {format_doc(doc, keys)}")


def inspect_stock_basic_info(db, limit: int, code: str | None) -> None:
    collection = db["stock_basic_info"]

    base_query: dict[str, Any] = {}
    if code:
        base_query["code"] = code

    total = collection.count_documents(base_query)
    non_null = collection.count_documents({**base_query, "dividend_yield": {"$exists": True, "$ne": None}})
    positive = collection.count_documents({**base_query, "dividend_yield": {"$exists": True, "$gt": 0}})

    print_section("stock_basic_info")
    print(f"总记录数: {total}")
    print(f"dividend_yield 非空: {non_null}")
    print(f"dividend_yield > 0: {positive}")

    pipeline = [
        {"$match": base_query},
        {"$group": {"_id": "$source", "total": {"$sum": 1}, "with_dividend": {
            "$sum": {"$cond": [{"$and": [
                {"$ne": [{"$type": "$dividend_yield"}, "missing"]},
                {"$ne": ["$dividend_yield", None]}
            ]}, 1, 0]}
        }}} ,
        {"$sort": {"total": -1}},
    ]
    source_stats = list(collection.aggregate(pipeline))
    print("\n按 source 统计:")
    if not source_stats:
        print("  - 无数据")
    for row in source_stats:
        print(f"  - source={row.get('_id')!r}, total={row.get('total', 0)}, with_dividend={row.get('with_dividend', 0)}")

    samples = list(
        collection.find(
            {**base_query, "dividend_yield": {"$exists": True, "$ne": None}},
            {"_id": 0, "code": 1, "name": 1, "industry": 1, "source": 1, "dividend_yield": 1},
        ).sort("dividend_yield", -1).limit(limit)
    )
    print_samples("dividend_yield 非空样例", samples, ["code", "name", "industry", "source", "dividend_yield"])


def inspect_stock_financial_data(db, limit: int, code: str | None) -> None:
    collection = db["stock_financial_data"]

    base_query: dict[str, Any] = {}
    if code:
        base_query["code"] = code

    total = collection.count_documents(base_query)
    flat_non_null = collection.count_documents({**base_query, "dividend_yield": {"$exists": True, "$ne": None}})
    nested_non_null = collection.count_documents({**base_query, "financial_indicators.dividend_yield": {"$exists": True, "$ne": None}})
    either_non_null = collection.count_documents({
        **base_query,
        "$or": [
            {"dividend_yield": {"$exists": True, "$ne": None}},
            {"financial_indicators.dividend_yield": {"$exists": True, "$ne": None}},
        ],
    })

    print_section("stock_financial_data")
    print(f"总记录数: {total}")
    print(f"flat dividend_yield 非空: {flat_non_null}")
    print(f"nested financial_indicators.dividend_yield 非空: {nested_non_null}")
    print(f"任一 dividend_yield 非空: {either_non_null}")

    pipeline = [
        {"$match": base_query},
        {"$group": {"_id": "$data_source", "total": {"$sum": 1}, "with_dividend": {
            "$sum": {"$cond": [{"$or": [
                {"$and": [{"$ne": [{"$type": "$dividend_yield"}, "missing"]}, {"$ne": ["$dividend_yield", None]}]},
                {"$and": [{"$ne": [{"$type": "$financial_indicators.dividend_yield"}, "missing"]}, {"$ne": ["$financial_indicators.dividend_yield", None]}]},
            ]}, 1, 0]}
        }}} ,
        {"$sort": {"total": -1}},
    ]
    source_stats = list(collection.aggregate(pipeline))
    print("\n按 data_source 统计:")
    if not source_stats:
        print("  - 无数据")
    for row in source_stats:
        print(f"  - data_source={row.get('_id')!r}, total={row.get('total', 0)}, with_dividend={row.get('with_dividend', 0)}")

    samples = list(
        collection.find(
            {
                **base_query,
                "$or": [
                    {"dividend_yield": {"$exists": True, "$ne": None}},
                    {"financial_indicators.dividend_yield": {"$exists": True, "$ne": None}},
                ],
            },
            {
                "_id": 0,
                "code": 1,
                "name": 1,
                "report_period": 1,
                "data_source": 1,
                "dividend_yield": 1,
                "financial_indicators.dividend_yield": 1,
            },
        ).sort([("report_period", -1), ("code", 1)]).limit(limit)
    )

    normalized_samples = []
    for item in samples:
        normalized_samples.append({
            "code": item.get("code"),
            "name": item.get("name"),
            "report_period": item.get("report_period"),
            "data_source": item.get("data_source"),
            "dividend_yield": item.get("dividend_yield"),
            "nested_dividend_yield": (item.get("financial_indicators") or {}).get("dividend_yield"),
        })
    print_samples(
        "财务数据样例",
        normalized_samples,
        ["code", "name", "report_period", "data_source", "dividend_yield", "nested_dividend_yield"],
    )


def inspect_stock_screening_view(db, limit: int, code: str | None) -> None:
    collection = db["stock_screening_view"]

    base_query: dict[str, Any] = {}
    if code:
        base_query["code"] = code

    print_section("stock_screening_view")
    try:
        total = collection.count_documents(base_query)
        non_null = collection.count_documents({**base_query, "dividend_yield": {"$exists": True, "$ne": None}})
        positive = collection.count_documents({**base_query, "dividend_yield": {"$exists": True, "$gt": 0}})
        print(f"总记录数: {total}")
        print(f"dividend_yield 非空: {non_null}")
        print(f"dividend_yield > 0: {positive}")
    except Exception as exc:
        print(f"统计失败: {exc}")
        return

    samples = list(
        collection.find(
            {**base_query, "dividend_yield": {"$exists": True, "$ne": None}},
            {"_id": 0, "code": 1, "name": 1, "industry": 1, "source": 1, "dividend_yield": 1},
        ).sort("dividend_yield", -1).limit(limit)
    )
    print_samples("视图样例", samples, ["code", "name", "industry", "source", "dividend_yield"])


def print_summary(db, code: str | None) -> None:
    print_section("结论建议")
    scope_text = f"股票 {code}" if code else "全库"
    basic_count = db["stock_basic_info"].count_documents({**({"code": code} if code else {}), "dividend_yield": {"$exists": True, "$ne": None}})
    financial_count = db["stock_financial_data"].count_documents({
        **({"code": code} if code else {}),
        "$or": [
            {"dividend_yield": {"$exists": True, "$ne": None}},
            {"financial_indicators.dividend_yield": {"$exists": True, "$ne": None}},
        ],
    })
    view_count = db["stock_screening_view"].count_documents({**({"code": code} if code else {}), "dividend_yield": {"$exists": True, "$ne": None}})

    print(f"检查范围: {scope_text}")
    print(f"stock_basic_info 命中数: {basic_count}")
    print(f"stock_financial_data 命中数: {financial_count}")
    print(f"stock_screening_view 命中数: {view_count}")

    if basic_count == 0 and financial_count == 0 and view_count == 0:
        print("结论: 当前数据库里基本可以判断没有同步到可用于筛选的股息率/分红字段。")
    elif view_count == 0 and (basic_count > 0 or financial_count > 0):
        print("结论: 底层集合可能已有分红/股息率数据，但 stock_screening_view 没有映射出来，需检查视图构建逻辑。")
    elif view_count > 0:
        print("结论: stock_screening_view 已有 dividend_yield，可进一步排查筛选条件是否过严或提示词是否没把高分红条件转成 dividend_yield。")
    else:
        print("结论: 需要继续结合样例数据判断同步链路哪里断了。")


def main() -> int:
    parser = argparse.ArgumentParser(description="检查 MongoDB 中股息率/分红字段同步情况")
    parser.add_argument("--limit", type=int, default=5, help="每个集合打印的样例数量")
    parser.add_argument("--code", type=str, default="", help="只检查指定股票代码，例如 600036")
    args = parser.parse_args()

    client = MongoClient(
        settings.MONGO_URI,
        serverSelectionTimeoutMS=settings.MONGO_SERVER_SELECTION_TIMEOUT_MS,
        connectTimeoutMS=settings.MONGO_CONNECT_TIMEOUT_MS,
        socketTimeoutMS=settings.MONGO_SOCKET_TIMEOUT_MS,
    )

    try:
        client.admin.command("ping")
        db = client[settings.MONGO_DB]

        print_section("MongoDB 连接信息")
        print(f"URI: {settings.MONGO_URI}")
        print(f"数据库: {settings.MONGO_DB}")

        code = args.code.strip() or None
        inspect_stock_basic_info(db, args.limit, code)
        inspect_stock_financial_data(db, args.limit, code)
        inspect_stock_screening_view(db, args.limit, code)
        print_summary(db, code)
        return 0
    except Exception as exc:
        print_section("执行失败")
        print(f"错误: {exc}")
        return 1
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())