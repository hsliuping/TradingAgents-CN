"""调试失败的复盘记录"""
from pymongo import MongoClient
from urllib.parse import quote_plus
import json
from bson import ObjectId
from datetime import datetime

def json_serialize(obj):
    """自定义 JSON 序列化函数，处理 ObjectId 和 datetime"""
    if isinstance(obj, ObjectId):
        return str(obj)
    elif isinstance(obj, datetime):
        return obj.isoformat()
    elif isinstance(obj, dict):
        return {k: json_serialize(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [json_serialize(item) for item in obj]
    else:
        return obj

def check_failed_review():
    """检查失败的复盘记录"""
    # 连接 MongoDB
    username = quote_plus("admin")
    password = quote_plus("tradingagents123")
    client = MongoClient(f"mongodb://{username}:{password}@localhost:27017/")
    db = client["tradingagents"]

    review_id = "9a9cb985-b8fc-4c67-a8f2-55cbb322cda7"

    print(f"🔍 查询复盘记录: {review_id}")
    print("=" * 80)

    # 查询复盘记录
    review = db.trade_reviews.find_one({"review_id": review_id})

    if not review:
        print(f"❌ 未找到复盘记录: {review_id}")
        return

    print(f"✅ 找到复盘记录")
    print(f"\n📋 基本信息:")
    print(f"  - review_id: {review.get('review_id')}")
    print(f"  - status: {review.get('status')}")
    print(f"  - error_message: {review.get('error_message')}")
    print(f"  - execution_time: {review.get('execution_time')}")
    print(f"  - created_at: {review.get('created_at')}")

    print(f"\n📊 交易信息:")
    trade_info = review.get('trade_info', {})
    print(f"  - code: {trade_info.get('code')}")
    print(f"  - name: {trade_info.get('name')}")
    print(f"  - realized_pnl: {trade_info.get('realized_pnl')}")
    print(f"  - realized_pnl_pct: {trade_info.get('realized_pnl_pct')}")

    print(f"\n📈 市场快照:")
    market_snapshot = review.get('market_snapshot', {})
    print(f"  - buy_date_close: {market_snapshot.get('buy_date_close')}")
    print(f"  - sell_date_close: {market_snapshot.get('sell_date_close')}")
    print(f"  - period_high: {market_snapshot.get('period_high')}")
    print(f"  - period_low: {market_snapshot.get('period_low')}")
    print(f"  - kline_data 数量: {len(market_snapshot.get('kline_data', []))}")

    print(f"\n🤖 AI 复盘:")
    ai_review = review.get('ai_review', {})
    print(f"  - overall_score: {ai_review.get('overall_score')}")
    print(f"  - summary: {ai_review.get('summary')}")
    print(f"  - strengths: {ai_review.get('strengths')}")
    print(f"  - weaknesses: {ai_review.get('weaknesses')}")

    # 查询关联的任务
    print(f"\n🔍 查询关联的任务...")
    task = db.unified_analysis_tasks.find_one(
        {"task_params.review_id": review_id}
    )

    if task:
        print(f"✅ 找到关联任务")
        print(f"  - task_id: {task.get('task_id')}")
        print(f"  - status: {task.get('status')}")
        print(f"  - error_message: {task.get('error_message')}")
        print(f"  - execution_time: {task.get('execution_time')}")

        # 🔥 使用自定义序列化函数处理 ObjectId
        result = task.get('result')
        if result:
            serialized_result = json_serialize(result)
            print(f"\n📦 任务结果:")
            print(json.dumps(serialized_result, indent=2, ensure_ascii=False))
        else:
            print(f"  - result: None")
    else:
        print(f"❌ 未找到关联任务")

if __name__ == "__main__":
    check_failed_review()

