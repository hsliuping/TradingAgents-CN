"""
修复案例库中缺失的 source 字段
"""

from pymongo import MongoClient

mongo_uri = 'mongodb://admin:tradingagents123@127.0.0.1:27017/tradingagents?authSource=admin'
client = MongoClient(mongo_uri)
db = client['tradingagents']

# 查找所有没有 source 字段的案例
cases_without_source = db.trade_reviews.find({
    'is_case_study': True,
    'source': {'$exists': False}
})

print('=== 修复前 ===')
count = db.trade_reviews.count_documents({
    'is_case_study': True,
    'source': {'$exists': False}
})
print(f'没有source字段的案例数: {count}')

# 更新所有没有 source 字段的案例，默认设置为 'paper'
result = db.trade_reviews.update_many(
    {
        'is_case_study': True,
        'source': {'$exists': False}
    },
    {
        '$set': {'source': 'paper'}
    }
)

print(f'\n✅ 已更新 {result.modified_count} 个案例')

# 验证
print('\n=== 修复后 ===')
total_cases = db.trade_reviews.count_documents({'is_case_study': True})
cases_with_source = db.trade_reviews.count_documents({'is_case_study': True, 'source': {'$exists': True}})
cases_paper = db.trade_reviews.count_documents({'is_case_study': True, 'source': 'paper'})
cases_position = db.trade_reviews.count_documents({'is_case_study': True, 'source': 'position'})

print(f'总案例数: {total_cases}')
print(f'有source字段: {cases_with_source}')
print(f'source=paper: {cases_paper}')
print(f'source=position: {cases_position}')

# 显示修复后的案例
print('\n=== 案例列表 ===')
cases = db.trade_reviews.find({'is_case_study': True}).limit(5)
for case in cases:
    print(f"review_id: {case.get('review_id')}")
    print(f"  source: {case.get('source')}")
    print(f"  code: {case.get('trade_info', {}).get('code')}")
    print()

client.close()

