"""
检查案例库中的字段数据
"""

from pymongo import MongoClient
import json

mongo_uri = 'mongodb://admin:tradingagents123@127.0.0.1:27017/tradingagents?authSource=admin'
client = MongoClient(mongo_uri)
db = client['tradingagents']

# 查找持仓操作的案例
cases = db.trade_reviews.find({'is_case_study': True, 'source': 'position'}).limit(5)

print('=== 持仓操作案例详情 ===')
for case in cases:
    print(f"\nreview_id: {case.get('review_id')}")
    print(f"code: {case.get('trade_info', {}).get('code')}")
    print(f"name: {case.get('trade_info', {}).get('name', 'NOT SET')}")
    print(f"tags: {case.get('tags', [])}")
    print(f"source: {case.get('source')}")
    print(f"realized_pnl: {case.get('trade_info', {}).get('realized_pnl', 0)}")
    print(f"overall_score: {case.get('ai_review', {}).get('overall_score', 0)}")
    
    # 打印 trade_info 的所有字段
    trade_info = case.get('trade_info', {})
    print(f"\ntrade_info 字段:")
    for key, value in trade_info.items():
        if key not in ['trades']:  # 跳过 trades 数组
            print(f"  {key}: {value}")

client.close()

