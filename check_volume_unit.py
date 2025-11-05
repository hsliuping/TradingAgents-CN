"""检查成交量单位"""
from pymongo import MongoClient

# 连接 MongoDB
mongo_uri = "mongodb://admin:tradingagents123@localhost:27017/"
client = MongoClient(mongo_uri)

db = client["tradingagents"]

print("=" * 60)
print("🔍 检查 300750 成交量数据")
print("=" * 60)

# 查询 market_quotes
q = db.market_quotes.find_one({"code": "300750"}, {"_id": 0})

if q:
    volume = q.get("volume")
    print(f"\n📊 数据库中的成交量:")
    print(f"  原始值: {volume}")
    print(f"  单位推测: 股")
    print(f"")
    print(f"📈 转换后:")
    print(f"  {volume / 100:,.2f} 手")
    print(f"  {volume / 100 / 10000:,.2f} 万手")
    print(f"")
    print(f"🌐 东方财富显示: 23.94万手")
    print(f"")
    
    # 验证
    expected = 23.94  # 万手
    actual = volume / 100 / 10000
    diff = abs(expected - actual)
    
    if diff < 0.1:
        print(f"✅ 单位推测正确！数据库存储的是【股】，需要除以100转换为【手】")
    else:
        print(f"❌ 单位推测可能有误，差异: {diff:.2f}万手")
else:
    print("❌ 未找到数据")

client.close()

