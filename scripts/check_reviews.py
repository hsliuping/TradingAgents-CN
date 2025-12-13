"""检查数据库中的复盘记录"""
from app.core.database import get_mongo_db
import asyncio

async def check_reviews():
    db = get_mongo_db()
    
    # 查询所有复盘记录
    total = await db['trade_reviews'].count_documents({})
    print(f'数据库中共有 {total} 条复盘记录')
    print()
    
    cursor = db['trade_reviews'].find({}).sort('created_at', -1).limit(5)
    reviews = await cursor.to_list(None)
    
    for i, review in enumerate(reviews, 1):
        review_id = review.get('review_id', 'N/A')
        review_type = review.get('review_type', 'N/A')
        trade_info = review.get('trade_info', {})
        code = trade_info.get('code', 'N/A')
        name = trade_info.get('name', 'N/A')
        status = review.get('status', 'N/A')
        ai_review = review.get('ai_review', {})
        overall_score = ai_review.get('overall_score', 0)
        created_at = review.get('created_at', 'N/A')
        
        print(f'记录 {i}:')
        print(f'  review_id: {review_id}')
        print(f'  review_type: {review_type}')
        print(f'  code: {code}')
        print(f'  name: {name}')
        print(f'  status: {status}')
        print(f'  overall_score: {overall_score}')
        print(f'  created_at: {created_at}')
        print()

if __name__ == '__main__':
    asyncio.run(check_reviews())

