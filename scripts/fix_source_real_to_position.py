"""
修复数据库中 source='real' 的数据，改为 source='position'
"""

from pymongo import MongoClient

mongo_uri = 'mongodb://admin:tradingagents123@127.0.0.1:27017/tradingagents?authSource=admin'
client = MongoClient(mongo_uri)
db = client['tradingagents']

print('=== 修复前 ===')
real_count = db.trade_reviews.count_documents({'source': 'real'})
position_count = db.trade_reviews.count_documents({'source': 'position'})
paper_count = db.trade_reviews.count_documents({'source': 'paper'})

print(f'source=real: {real_count}')
print(f'source=position: {position_count}')
print(f'source=paper: {paper_count}')

# 更新所有 source='real' 的记录为 source='position'
result = db.trade_reviews.update_many(
    {'source': 'real'},
    {'$set': {'source': 'position'}}
)

print(f'\n✅ 已更新 {result.modified_count} 条记录')

print('\n=== 修复后 ===')
real_count = db.trade_reviews.count_documents({'source': 'real'})
position_count = db.trade_reviews.count_documents({'source': 'position'})
paper_count = db.trade_reviews.count_documents({'source': 'paper'})

print(f'source=real: {real_count}')
print(f'source=position: {position_count}')
print(f'source=paper: {paper_count}')

# 显示案例库统计
print('\n=== 案例库统计 ===')
cases_total = db.trade_reviews.count_documents({'is_case_study': True})
cases_position = db.trade_reviews.count_documents({'is_case_study': True, 'source': 'position'})
cases_paper = db.trade_reviews.count_documents({'is_case_study': True, 'source': 'paper'})

print(f'总案例数: {cases_total}')
print(f'持仓操作案例: {cases_position}')
print(f'模拟交易案例: {cases_paper}')

client.close()

