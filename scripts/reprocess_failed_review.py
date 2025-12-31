"""重新处理失败的复盘记录"""
import asyncio
from pymongo import MongoClient
from urllib.parse import quote_plus
import re
import json

async def reprocess_failed_review():
    """重新处理失败的复盘记录"""
    # 连接 MongoDB
    username = quote_plus("admin")
    password = quote_plus("tradingagents123")
    client = MongoClient(f"mongodb://{username}:{password}@localhost:27017/")
    db = client["tradingagents"]
    
    review_id = "9a9cb985-b8fc-4c67-a8f2-55cbb322cda7"
    
    print(f"🔍 查询复盘记录: {review_id}")
    print("=" * 80)
    
    # 1. 查询复盘记录
    review = db.trade_reviews.find_one({"review_id": review_id})
    if not review:
        print(f"❌ 未找到复盘记录: {review_id}")
        return
    
    print(f"✅ 找到复盘记录，当前状态: {review.get('status')}")
    
    # 2. 查询关联的任务
    task = db.unified_analysis_tasks.find_one(
        {"task_params.review_id": review_id}
    )
    
    if not task:
        print(f"❌ 未找到关联任务")
        return
    
    print(f"✅ 找到关联任务: {task.get('task_id')}")
    print(f"   任务状态: {task.get('status')}")
    
    # 3. 从任务结果中提取 review_summary
    result = task.get('result', {})
    if 'review_summary' not in result:
        print(f"❌ 任务结果中没有 review_summary 字段")
        print(f"   可用字段: {list(result.keys())}")
        return
    
    review_summary = result['review_summary']
    print(f"\n📦 提取 review_summary:")
    print(f"   长度: {len(review_summary)} 字符")
    print(f"   前 200 字符: {review_summary[:200]}")
    
    # 4. 解析 JSON
    json_match = re.search(r'```json\s*\n(.*?)\n```', review_summary, re.DOTALL)
    if not json_match:
        print(f"❌ 无法从 review_summary 中提取 JSON")
        return
    
    review_data = json.loads(json_match.group(1))
    print(f"\n✅ 成功解析 JSON:")
    print(f"   overall_score: {review_data.get('overall_score')}")
    print(f"   summary: {review_data.get('summary')}")
    print(f"   strengths: {len(review_data.get('strengths', []))} 条")
    print(f"   weaknesses: {len(review_data.get('weaknesses', []))} 条")
    
    # 5. 更新复盘记录
    print(f"\n🔄 更新复盘记录...")
    update_result = db.trade_reviews.update_one(
        {"review_id": review_id},
        {"$set": {
            "ai_review": review_data,
            "status": "completed",
            "error_message": None
        }}
    )
    
    if update_result.modified_count > 0:
        print(f"✅ 复盘记录已更新")
    else:
        print(f"⚠️ 复盘记录未更新（可能已经是最新状态）")
    
    # 6. 验证更新
    updated_review = db.trade_reviews.find_one({"review_id": review_id})
    print(f"\n📊 验证更新结果:")
    print(f"   status: {updated_review.get('status')}")
    print(f"   ai_review.overall_score: {updated_review.get('ai_review', {}).get('overall_score')}")
    print(f"   ai_review.summary: {updated_review.get('ai_review', {}).get('summary')}")

if __name__ == "__main__":
    asyncio.run(reprocess_failed_review())

