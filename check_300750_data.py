"""检查 300750 的数据"""
from pymongo import MongoClient

# 连接 MongoDB
mongo_uri = "mongodb://admin:tradingagents123@localhost:27017/"
client = MongoClient(mongo_uri)

db = client["tradingagents"]

print("=" * 60)
print("🔍 检查 market_quotes 集合中的 300750 数据")
print("=" * 60)

# 查询 300750 的实时行情
quote = db.market_quotes.find_one({"symbol": "300750"})
if quote:
    print("✅ 找到 market_quotes 中的数据:")
    print(f"  - symbol: {quote.get('symbol')}")
    print(f"  - ts_code: {quote.get('ts_code')}")
    print(f"  - name: {quote.get('name')}")
    print(f"  - close: {quote.get('close')}")
    print(f"  - volume: {quote.get('volume')}")
    print(f"  - amount: {quote.get('amount')}")
    print(f"  - turnover_rate: {quote.get('turnover_rate')}")
    print(f"  - volume_ratio: {quote.get('volume_ratio')}")
    print(f"  - trade_date: {quote.get('trade_date')}")
    print(f"  - updated_at: {quote.get('updated_at')}")
    print()
    print("📋 完整数据:")
    for key, value in quote.items():
        if key != '_id':
            print(f"  {key}: {value}")
else:
    print("❌ market_quotes 中未找到 300750")

print()
print("=" * 60)
print("🔍 检查 stock_basic_info 集合中的 300750 数据")
print("=" * 60)

# 查询 300750 的基本信息
basic = db.stock_basic_info.find_one({"symbol": "300750"})
if basic:
    print("✅ 找到 stock_basic_info 中的数据:")
    print(f"  - symbol: {basic.get('symbol')}")
    print(f"  - ts_code: {basic.get('ts_code')}")
    print(f"  - name: {basic.get('name')}")
    print(f"  - close: {basic.get('close')}")
    print(f"  - volume: {basic.get('volume')}")
    print(f"  - amount: {basic.get('amount')}")
    print(f"  - turnover_rate: {basic.get('turnover_rate')}")
    print(f"  - volume_ratio: {basic.get('volume_ratio')}")
    print(f"  - trade_date: {basic.get('trade_date')}")
    print(f"  - updated_at: {basic.get('updated_at')}")
else:
    print("❌ stock_basic_info 中未找到 300750")

client.close()

