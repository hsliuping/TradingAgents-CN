#!/usr/bin/env python3
"""
检查导入的历史K线数据

验证数据是否真的保存到数据库中
"""
import asyncio
import sys
import os

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def check_kline_data():
    """检查历史K线数据"""
    print("=" * 80)
    print("检查导入的历史K线数据")
    print("=" * 80)

    try:
        # 使用同步 MongoDB 连接
        from pymongo import MongoClient

        # 使用默认连接字符串
        mongodb_url = "mongodb://admin:tradingagents2024@localhost:27017/tradingagents?authSource=admin"
        mongodb_db = "tradingagents"

        print(f"\n连接 MongoDB: {mongodb_url}")
        print(f"数据库: {mongodb_db}")

        client = MongoClient(mongodb_url)
        db = client[mongodb_db]

        print("✅ MongoDB 连接成功")
    except Exception as e:
        print(f"❌ MongoDB 连接失败: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # 检查 stock_daily_quotes 集合
    collection = db.stock_daily_quotes
    
    # 测试股票代码
    test_symbols = ["000001", "000002"]
    
    for symbol in test_symbols:
        print(f"\n{'=' * 80}")
        print(f"股票代码: {symbol}")
        print(f"{'=' * 80}")
        
        # 1. 检查所有数据源的数据
        print("\n📊 按数据源统计:")
        pipeline = [
            {"$match": {"symbol": symbol}},
            {"$group": {
                "_id": {
                    "data_source": "$data_source",
                    "period": "$period"
                },
                "count": {"$sum": 1},
                "min_date": {"$min": "$trade_date"},
                "max_date": {"$max": "$trade_date"}
            }},
            {"$sort": {"_id.data_source": 1, "_id.period": 1}}
        ]
        
        results = list(collection.aggregate(pipeline))
        
        if results:
            for doc in results:
                data_source = doc["_id"]["data_source"]
                period = doc["_id"]["period"]
                count = doc["count"]
                min_date = doc["min_date"]
                max_date = doc["max_date"]
                print(f"  - {data_source:10s} | {period:10s} | {count:5d} 条 | {min_date} ~ {max_date}")
        else:
            print(f"  ❌ 没有找到任何数据")
        
        # 2. 检查 local 数据源的详细信息
        print("\n📋 local 数据源详细信息:")
        local_count = collection.count_documents({
            "symbol": symbol,
            "data_source": "local",
            "period": "daily"
        })
        print(f"  总记录数: {local_count}")

        if local_count > 0:
            # 获取最早和最晚的记录
            earliest = collection.find_one(
                {"symbol": symbol, "data_source": "local", "period": "daily"},
                sort=[("trade_date", 1)]
            )
            latest = collection.find_one(
                {"symbol": symbol, "data_source": "local", "period": "daily"},
                sort=[("trade_date", -1)]
            )

            print(f"  最早日期: {earliest['trade_date']}")
            print(f"  最晚日期: {latest['trade_date']}")

            # 显示前5条记录
            print(f"\n  前5条记录:")
            cursor = collection.find(
                {"symbol": symbol, "data_source": "local", "period": "daily"},
                {"trade_date": 1, "open": 1, "close": 1, "volume": 1, "_id": 0}
            ).sort("trade_date", 1).limit(5)

            for doc in cursor:
                print(f"    {doc['trade_date']}: open={doc.get('open', 0):.2f}, close={doc.get('close', 0):.2f}, volume={doc.get('volume', 0)}")
        
        # 3. 检查是否有重复数据
        print("\n🔍 检查重复数据:")
        duplicate_pipeline = [
            {"$match": {"symbol": symbol, "data_source": "local", "period": "daily"}},
            {"$group": {
                "_id": "$trade_date",
                "count": {"$sum": 1}
            }},
            {"$match": {"count": {"$gt": 1}}},
            {"$sort": {"_id": 1}}
        ]
        
        duplicates = list(collection.aggregate(duplicate_pipeline))
        
        if duplicates:
            print(f"  ⚠️ 发现 {len(duplicates)} 个重复日期:")
            for doc in duplicates[:5]:  # 只显示前5个
                print(f"    {doc['_id']}: {doc['count']} 条记录")
        else:
            print(f"  ✅ 没有重复数据")
    
    print("\n" + "=" * 80)
    print("检查完成")
    print("=" * 80)


if __name__ == "__main__":
    check_kline_data()

