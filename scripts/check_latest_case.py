"""
检查最新的案例数据
"""

from pymongo import MongoClient
from datetime import datetime

mongo_uri = 'mongodb://admin:tradingagents123@127.0.0.1:27017/tradingagents?authSource=admin'
client = MongoClient(mongo_uri)
db = client['tradingagents']

# 查找所有案例，按创建时间倒序
cases = db.trade_reviews.find({'is_case_study': True}).sort('created_at', -1).limit(5)

print('=== 最新的案例 ===')
for i, case in enumerate(cases, 1):
    created_at = case.get('created_at')
    if isinstance(created_at, datetime):
        created_str = created_at.strftime('%Y-%m-%d %H:%M:%S')
    else:
        created_str = str(created_at)
    
    print(f"\n{i}. review_id: {case.get('review_id')}")
    print(f"   code: {case.get('trade_info', {}).get('code')}")
    print(f"   source: {case.get('source', 'NOT SET')}")
    print(f"   is_case_study: {case.get('is_case_study')}")
    print(f"   created_at: {created_str}")
    print(f"   tags: {case.get('tags', [])}")

# 统计
print('\n=== 统计 ===')
total_cases = db.trade_reviews.count_documents({'is_case_study': True})
cases_paper = db.trade_reviews.count_documents({'is_case_study': True, 'source': 'paper'})
cases_position = db.trade_reviews.count_documents({'is_case_study': True, 'source': 'position'})
cases_no_source = db.trade_reviews.count_documents({'is_case_study': True, 'source': {'$exists': False}})

print(f'总案例数: {total_cases}')
print(f'source=paper: {cases_paper}')
print(f'source=position: {cases_position}')
print(f'没有source字段: {cases_no_source}')

client.close()

