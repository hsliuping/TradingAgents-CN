#!/usr/bin/env python3
"""
普查 stock_financial_data 集合的真实字段结构。

用途：
1. 统计顶层字段出现频次
2. 统计常见嵌套对象字段出现频次
3. 查看指定股票或指定数据源的样例文档
4. 快速判断数据库里“有哪些字段已经落库”

使用方法：
    python scripts/inspect_stock_financial_data_fields.py
    python scripts/inspect_stock_financial_data_fields.py --limit 10
    python scripts/inspect_stock_financial_data_fields.py --code 600036
    python scripts/inspect_stock_financial_data_fields.py --data-source tushare
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

from pymongo import MongoClient


PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from app.core.config import settings  # noqa: E402


NESTED_OBJECT_FIELDS = [
    "income_statement",
    "balance_sheet",
    "cash_flow",
    "financial_indicators",
    "main_business",
]


def print_section(title: str) -> None:
    print(f"\n{'=' * 100}")
    print(title)
    print(f"{'=' * 100}")


def build_query(code: str | None, data_source: str | None) -> dict[str, Any]:
    query: dict[str, Any] = {}
    if code:
        query["code"] = code
    if data_source:
        query["data_source"] = data_source
    return query


def normalize_value(value: Any, max_length: int = 160) -> str:
    if isinstance(value, (dict, list)):
        text = json.dumps(value, ensure_ascii=False, default=str)
    else:
        text = repr(value)
    if len(text) > max_length:
        return text[: max_length - 3] + "..."
    return text


def print_counter(title: str, counter: Counter[str], total_docs: int, top_n: int) -> None:
    print(f"\n{title}:")
    if not counter:
        print("  - 无数据")
        return
    for key, count in counter.most_common(top_n):
        ratio = (count / total_docs * 100) if total_docs else 0
        print(f"  - {key}: {count} ({ratio:.1f}%)")


def inspect_collection(db, query: dict[str, Any], sample_limit: int, top_n: int) -> None:
    collection = db["stock_financial_data"]
    total_docs = collection.count_documents(query)

    print_section("集合概览")
    print(f"查询条件: {query or '{}'}")
    print(f"命中文档数: {total_docs}")

    if total_docs == 0:
        print("没有匹配文档。")
        return

    source_counter: Counter[str] = Counter()
    top_level_counter: Counter[str] = Counter()
    nested_counters = {field: Counter() for field in NESTED_OBJECT_FIELDS}

    cursor = collection.find(query, {"_id": 0}).limit(min(max(total_docs, sample_limit), 2000))
    sampled_docs: list[dict[str, Any]] = []
    for index, doc in enumerate(cursor, start=1):
        sampled_docs.append(doc)
        source_counter[str(doc.get("data_source", "<missing>"))] += 1
        for key, value in doc.items():
            top_level_counter[key] += 1
            if key in nested_counters and isinstance(value, dict):
                for nested_key in value.keys():
                    nested_counters[key][nested_key] += 1

    print_counter("按 data_source 分布（基于采样）", source_counter, len(sampled_docs), top_n)
    print_counter("顶层字段覆盖率（基于采样）", top_level_counter, len(sampled_docs), top_n)

    for field in NESTED_OBJECT_FIELDS:
        print_counter(f"{field} 子字段覆盖率（基于采样）", nested_counters[field], len(sampled_docs), top_n)

    print_section("样例文档")
    sample_docs = collection.find(
        query,
        {
            "_id": 0,
            "code": 1,
            "name": 1,
            "report_period": 1,
            "data_source": 1,
            "updated_at": 1,
            "revenue": 1,
            "net_profit": 1,
            "roe": 1,
            "dividend_yield": 1,
            "income_statement": 1,
            "balance_sheet": 1,
            "cash_flow": 1,
            "financial_indicators": 1,
            "main_business": 1,
        },
    ).sort([("report_period", -1), ("code", 1)]).limit(sample_limit)

    for index, doc in enumerate(sample_docs, start=1):
        print(f"\n样例 {index}:")
        for key in [
            "code", "name", "report_period", "data_source", "updated_at",
            "revenue", "net_profit", "roe", "dividend_yield",
        ]:
            if key in doc:
                print(f"  {key}: {normalize_value(doc.get(key))}")

        for nested_key in NESTED_OBJECT_FIELDS:
            nested_value = doc.get(nested_key)
            if isinstance(nested_value, dict):
                nested_keys = list(nested_value.keys())
                preview_keys = nested_keys[:20]
                print(f"  {nested_key}.keys({len(nested_keys)}): {preview_keys}")
            elif nested_value is not None:
                print(f"  {nested_key}: {normalize_value(nested_value)}")


def main() -> int:
    parser = argparse.ArgumentParser(description="普查 stock_financial_data 集合字段结构")
    parser.add_argument("--code", type=str, default="", help="只查看指定股票代码，例如 600036")
    parser.add_argument("--data-source", type=str, default="", help="只查看指定数据源，例如 tushare")
    parser.add_argument("--limit", type=int, default=5, help="输出样例文档数量")
    parser.add_argument("--top", type=int, default=30, help="每类字段统计最多输出多少项")
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

        query = build_query(args.code.strip() or None, args.data_source.strip() or None)
        inspect_collection(db, query, args.limit, args.top)
        return 0
    except Exception as exc:
        print_section("执行失败")
        print(f"错误: {exc}")
        return 1
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())