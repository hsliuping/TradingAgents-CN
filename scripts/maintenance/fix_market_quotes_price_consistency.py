#!/usr/bin/env python3
"""
对齐 market_quotes 中的 close / price / current_price 字段。

默认仅检查并输出统计；传入 --apply 后才会写库。
"""

from __future__ import annotations

import argparse
import math
import os
from typing import Iterable, Optional

from dotenv import load_dotenv
from pymongo import MongoClient, UpdateOne


def build_mongo_uri() -> str:
    host = os.getenv("MONGODB_HOST", "localhost")
    port = int(os.getenv("MONGODB_PORT", "27017"))
    database = os.getenv("MONGODB_DATABASE", "tradingagents")
    username = os.getenv("MONGODB_USERNAME", "")
    password = os.getenv("MONGODB_PASSWORD", "")
    auth_source = os.getenv("MONGODB_AUTH_SOURCE", "admin")
    if username and password:
        return f"mongodb://{username}:{password}@{host}:{port}/{database}?authSource={auth_source}"
    return f"mongodb://{host}:{port}/{database}"


def to_float(value: object) -> Optional[float]:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        numeric = float(value)
        if math.isnan(numeric):
            return None
        return numeric
    try:
        numeric = float(str(value).strip())
    except (TypeError, ValueError):
        return None
    if math.isnan(numeric):
        return None
    return numeric


def same_price(left: Optional[float], right: Optional[float], tolerance: float = 1e-6) -> bool:
    if left is None or right is None:
        return False
    return abs(left - right) <= tolerance


def batched(items: list[UpdateOne], size: int) -> Iterable[list[UpdateOne]]:
    for start in range(0, len(items), size):
        yield items[start:start + size]


def inspect_and_fix(apply: bool = False, sample_limit: int = 10, batch_size: int = 500) -> bool:
    print("检查 market_quotes 的价格一致性")
    print("=" * 60)

    load_dotenv()
    database_name = os.getenv("MONGODB_DATABASE", "tradingagents")
    mongo_uri = build_mongo_uri()
    client = MongoClient(mongo_uri)

    try:
        db = client[database_name]
        collection = db.market_quotes

        total_docs = collection.count_documents({})
        print(f"总文档数: {total_docs}")

        cursor = collection.find(
            {"close": {"$exists": True, "$ne": None}},
            {
                "code": 1,
                "symbol": 1,
                "name": 1,
                "trade_date": 1,
                "close": 1,
                "price": 1,
                "current_price": 1,
            },
        )

        mismatch_count = 0
        sample_rows: list[dict] = []
        operations: list[UpdateOne] = []

        for doc in cursor:
            close = to_float(doc.get("close"))
            if close is None or close <= 0:
                continue

            price = to_float(doc.get("price"))
            current_price = to_float(doc.get("current_price"))

            price_ok = same_price(price, close)
            current_ok = same_price(current_price, close)
            if price_ok and current_ok:
                continue

            mismatch_count += 1
            if len(sample_rows) < sample_limit:
                sample_rows.append({
                    "code": doc.get("code") or doc.get("symbol"),
                    "name": doc.get("name"),
                    "trade_date": doc.get("trade_date"),
                    "close": close,
                    "price": price,
                    "current_price": current_price,
                })

            operations.append(
                UpdateOne(
                    {"_id": doc["_id"]},
                    {"$set": {"price": close, "current_price": close}},
                )
            )

        print(f"发现不一致文档数: {mismatch_count}")
        if sample_rows:
            print("\n样本:")
            for row in sample_rows:
                print(
                    f"- {row['code']} {row.get('name') or ''} trade_date={row.get('trade_date')} "
                    f"close={row['close']} price={row['price']} current_price={row['current_price']}"
                )

        if not apply:
            print("\n当前为检查模式，未写入数据库。")
            print("使用 --apply 执行修复。")
            return True

        if not operations:
            print("\n没有需要修复的文档。")
            return True

        print(f"\n开始修复，共 {len(operations)} 条更新...")
        modified_count = 0
        for batch in batched(operations, batch_size):
            result = collection.bulk_write(batch, ordered=False)
            modified_count += result.modified_count

        print(f"修复完成，modified_count={modified_count}")
        return True
    except Exception as exc:
        print(f"修复失败: {exc}")
        return False
    finally:
        client.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="修复 market_quotes 的价格字段一致性")
    parser.add_argument("--apply", action="store_true", help="执行修复写入数据库")
    parser.add_argument("--sample-limit", type=int, default=10, help="检查模式输出的样本数量")
    args = parser.parse_args()
    return 0 if inspect_and_fix(apply=args.apply, sample_limit=args.sample_limit) else 1


if __name__ == "__main__":
    raise SystemExit(main())