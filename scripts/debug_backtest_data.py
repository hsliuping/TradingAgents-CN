#!/usr/bin/env python3
"""
回测数据诊断：检查 MongoDB stock_daily_quotes 中的实际数据格式
帮助排查「无数据」问题
"""
import os
import sys

# 添加 backtest-service 到 path 以使用其 config
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backtest-service"))

from pymongo import MongoClient


def main():
    uri = os.getenv("MONGO_URI", "mongodb://admin:tradingagents123@localhost:27017/tradingagents?authSource=admin")
    db_name = os.getenv("MONGO_DB", "tradingagents")

    print(f"连接: {uri.split('@')[-1] if '@' in uri else uri}")
    print(f"数据库: {db_name}\n")

    client = MongoClient(uri)
    db = client[db_name]
    coll = db["stock_daily_quotes"]

    # 1. 总数
    total = coll.count_documents({})
    print(f"1. 集合总记录数: {total}")

    # 2. 抽样 600519 相关
    samples = list(
        coll.find(
            {"$or": [{"symbol": "600519"}, {"symbol": "600519.SH"}, {"code": "600519"}, {"full_symbol": "600519.SH"}]}
        ).limit(5)
    )
    print(f"\n2. 600519 相关记录数（limit 5）: {len(samples)}")
    if samples:
        for i, doc in enumerate(samples):
            print(f"   [{i+1}] symbol={doc.get('symbol')!r} code={doc.get('code')!r} full_symbol={doc.get('full_symbol')!r} "
                  f"trade_date={doc.get('trade_date')!r} ({type(doc.get('trade_date')).__name__}) "
                  f"data_source={doc.get('data_source')} period={doc.get('period')}")
    else:
        print("   无 600519 数据")
        # 看看都有哪些 symbol
        distinct = coll.distinct("symbol", limit=10)
        print(f"   集合中存在的 symbol 示例: {distinct[:10]}")

    # 3. 模拟 data_feed 的查询
    sd = "2016-01-01"
    ed = "2025-12-31"
    q = {
        "$and": [
            {"$or": [{"symbol": "600519"}, {"symbol": "600519"}, {"code": "600519"}]},
            {"trade_date": {"$gte": sd, "$lte": ed}},
            {"$or": [{"period": "daily"}, {"period": {"$exists": False}}]},
        ]
    }
    matches = list(coll.find(q).limit(3))
    print(f"\n3. data_feed 查询结果 (symbol=600519, {sd}~{ed}): {len(matches)} 条")
    if matches:
        for m in matches:
            print(f"   trade_date={m.get('trade_date')} close={m.get('close')}")
    else:
        print("   无匹配记录")
        # 放宽条件再试
        q2 = {"$or": [{"symbol": "600519"}, {"symbol": "600519.SH"}, {"code": "600519"}]}
        any_count = coll.count_documents(q2)
        print(f"   仅按 symbol/code 查询 600519 总数: {any_count}")
        if any_count > 0:
            one = coll.find_one(q2)
            print(f"   样例 trade_date 格式: {one.get('trade_date')!r}")

    # 4. trade_date 格式分布
    pipeline = [
        {"$match": {"symbol": {"$in": ["600519", "600519.SH"]}}},
        {"$project": {"fmt": {"$cond": [
            {"$eq": [{"$strLenCP": "$trade_date"}, 10]}, "YYYY-MM-DD",
            {"$cond": [
                {"$eq": [{"$strLenCP": "$trade_date"}, 8]}, "YYYYMMDD",
                "OTHER"
            ]}
        ]}}},
        {"$group": {"_id": "$fmt", "count": {"$sum": 1}}},
    ]
    try:
        dist = list(coll.aggregate(pipeline))
        print(f"\n4. 600519 trade_date 格式分布: {dist}")
    except Exception as e:
        print(f"\n4. 格式分布聚合失败: {e}")

    client.close()
    print("\n诊断完成。")


if __name__ == "__main__":
    main()
