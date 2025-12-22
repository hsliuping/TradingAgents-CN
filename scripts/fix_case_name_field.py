"""
修复案例库中缺失的股票名称
"""

from pymongo import MongoClient

mongo_uri = 'mongodb://admin:tradingagents123@127.0.0.1:27017/tradingagents?authSource=admin'
client = MongoClient(mongo_uri)
db = client['tradingagents']

# 查找所有 trade_info.name 为 None 的案例
cases = db.trade_reviews.find({
    'is_case_study': True,
    'trade_info.name': None
})

print('=== 需要修复的案例 ===')
fixed_count = 0

for case in cases:
    review_id = case.get('review_id')
    code = case.get('trade_info', {}).get('code')
    
    if not code:
        print(f"跳过 {review_id}：没有股票代码")
        continue
    
    # 从 position_changes 或 paper_trades 中查找股票名称
    source = case.get('source', 'paper')
    
    if source == 'position':
        # 从 position_changes 查找
        position = db.position_changes.find_one({'code': code})
        stock_name = position.get('name') if position else None
    else:
        # 从 paper_trades 查找
        trade = db.paper_trades.find_one({'code': code})
        stock_name = trade.get('name') if trade else None
    
    if stock_name:
        # 更新案例的 trade_info.name
        result = db.trade_reviews.update_one(
            {'review_id': review_id},
            {'$set': {'trade_info.name': stock_name}}
        )
        
        if result.modified_count > 0:
            print(f"✅ 已修复 {review_id}: {code} -> {stock_name}")
            fixed_count += 1
        else:
            print(f"⚠️ 更新失败 {review_id}")
    else:
        print(f"⚠️ 未找到股票名称: {code}")

print(f'\n总共修复了 {fixed_count} 个案例')

# 验证
print('\n=== 验证结果 ===')
cases_with_name = db.trade_reviews.count_documents({
    'is_case_study': True,
    'trade_info.name': {'$ne': None}
})
cases_without_name = db.trade_reviews.count_documents({
    'is_case_study': True,
    'trade_info.name': None
})

print(f'有股票名称的案例: {cases_with_name}')
print(f'没有股票名称的案例: {cases_without_name}')

client.close()

