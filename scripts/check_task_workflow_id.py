"""检查任务的 workflow_id"""
from pymongo import MongoClient
from urllib.parse import quote_plus

def check_task_workflow_id():
    """检查最近的交易复盘任务的 workflow_id"""
    # 连接 MongoDB
    username = quote_plus("admin")
    password = quote_plus("tradingagents123")
    client = MongoClient(f"mongodb://{username}:{password}@localhost:27017/")
    db = client["tradingagents"]
    
    print("🔍 查询最近的交易复盘任务...")
    print("=" * 80)
    
    # 查询最近的交易复盘任务
    task = db.unified_analysis_tasks.find_one(
        {"task_type": "trade_review"},
        sort=[("created_at", -1)]
    )
    
    if not task:
        print("❌ 未找到交易复盘任务")
        return
    
    print(f"✅ 找到任务: {task.get('task_id')}")
    print(f"\n📋 任务信息:")
    print(f"  - task_type: {task.get('task_type')}")
    print(f"  - workflow_id: {task.get('workflow_id')}")
    print(f"  - engine_type: {task.get('engine_type')}")
    print(f"  - status: {task.get('status')}")
    print(f"  - created_at: {task.get('created_at')}")
    
    print(f"\n📦 任务参数:")
    task_params = task.get('task_params', {})
    print(f"  - review_id: {task_params.get('review_id')}")
    print(f"  - code: {task_params.get('code')}")
    
    print(f"\n📊 任务结果字段:")
    result = task.get('result', {})
    if result:
        print(f"  - 可用字段: {list(result.keys())}")
        print(f"  - 是否有 review_summary: {'review_summary' in result}")
        print(f"  - 是否有 ai_review: {'ai_review' in result}")
        print(f"  - 是否有 stock_symbol: {'stock_symbol' in result}")

        # 🔥 显示 review_summary 的内容
        if 'review_summary' in result:
            review_summary = result['review_summary']
            print(f"\n📝 review_summary 内容:")
            print(f"  - 类型: {type(review_summary)}")
            print(f"  - 长度: {len(review_summary) if isinstance(review_summary, str) else 'N/A'}")
            print(f"  - 前 500 字符:")
            print("=" * 80)
            if isinstance(review_summary, str):
                print(review_summary[:500])
            else:
                import json
                print(json.dumps(review_summary, ensure_ascii=False, indent=2)[:500])
            print("=" * 80)
    else:
        print(f"  - 结果为空")

if __name__ == "__main__":
    check_task_workflow_id()

