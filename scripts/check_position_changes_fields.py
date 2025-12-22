"""
检查 position_changes 集合中的字段
"""

from pymongo import MongoClient

mongo_uri = 'mongodb://admin:tradingagents123@127.0.0.1:27017/tradingagents?authSource=admin'
client = MongoClient(mongo_uri)
db = client['tradingagents']

# 查找 300750 的持仓变动记录
changes = db.position_changes.find({'code': '300750'}).limit(3)

print('=== 300750 的持仓变动记录 ===')
for change in changes:
    print(f"\n_id: {change.get('_id')}")
    print(f"code: {change.get('code')}")
    print(f"name: {change.get('name', 'NOT SET')}")
    print(f"stock_name: {change.get('stock_name', 'NOT SET')}")
    print(f"side: {change.get('side')}")
    print(f"quantity: {change.get('quantity')}")
    print(f"price: {change.get('price')}")
    
    # 打印所有字段名
    print(f"\n所有字段: {list(change.keys())}")

client.close()

