"""
检查案例库中的 source 字段
"""

from pymongo import MongoClient

mongo_uri = 'mongodb://admin:tradingagents123@127.0.0.1:27017/tradingagents?authSource=admin'
client = MongoClient(mongo_uri)
db = client['tradingagents']

# 查找案例库中的数据
cases = db.trade_reviews.find({'is_case_study': True}).limit(5)

print('=== 案例库数据 ===')
for case in cases:
    print(f"review_id: {case.get('review_id')}")
    print(f"  is_case_study: {case.get('is_case_study')}")
    print(f"  source: {case.get('source', 'NOT SET')}")
    print(f"  code: {case.get('trade_info', {}).get('code')}")
    print()

# 统计
total_cases = db.trade_reviews.count_documents({'is_case_study': True})
cases_with_source = db.trade_reviews.count_documents({'is_case_study': True, 'source': {'$exists': True}})
cases_paper = db.trade_reviews.count_documents({'is_case_study': True, 'source': 'paper'})
cases_position = db.trade_reviews.count_documents({'is_case_study': True, 'source': 'position'})

print(f'总案例数: {total_cases}')
print(f'有source字段: {cases_with_source}')
print(f'source=paper: {cases_paper}')
print(f'source=position: {cases_position}')

client.close()

