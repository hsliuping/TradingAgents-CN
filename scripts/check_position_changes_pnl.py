"""检查 position_changes 中的 688111 数据和 realized_profit 字段"""
from pymongo import MongoClient
from urllib.parse import quote_plus

password = quote_plus('tradingagents123')
client = MongoClient(f'mongodb://admin:{password}@localhost:27017/tradingagents?authSource=admin')
db = client['tradingagents']

# 查询 688111 的持仓变化记录
print("=== position_changes 中的 688111 记录 ===")
changes = list(db['position_changes'].find({'code': '688111'}).sort('trade_time', 1))
print(f"找到 {len(changes)} 条记录\n")

for i, c in enumerate(changes):
    print(f"{i+1}. user_id: {c.get('user_id')}")
    print(f"   change_type: {c.get('change_type')}")
    print(f"   quantity_change: {c.get('quantity_change')}")
    print(f"   trade_price: {c.get('trade_price')}")
    print(f"   realized_profit: {c.get('realized_profit')}")
    print(f"   trade_time: {c.get('trade_time')}")
    print()

# 计算总收益
if changes:
    total_realized_profit = sum(float(c.get('realized_profit', 0) or 0) for c in changes if c.get('change_type') in ['sell', 'reduce'])
    print(f"\n总已实现收益: {total_realized_profit}")

    # 检查每笔卖出的 realized_profit
    print("\n=== 卖出记录的 realized_profit ===")
    for c in changes:
        if c.get('change_type') in ['sell', 'reduce']:
            print(f"change_type={c.get('change_type')}, realized_profit={c.get('realized_profit')}")

