"""检查 review_manager 的提示词模板"""
from pymongo import MongoClient
from urllib.parse import quote_plus
import json

def check_review_manager_prompt():
    """检查 review_manager 的提示词模板"""
    # 连接 MongoDB
    username = quote_plus("admin")
    password = quote_plus("tradingagents123")
    client = MongoClient(f"mongodb://{username}:{password}@localhost:27017/")
    db = client["tradingagents"]
    
    print("🔍 查询 review_manager 的提示词模板...")
    print("=" * 80)
    
    # 先查询所有 reviewer 相关的提示词
    print("📋 所有 reviewer 相关的提示词模板:")
    all_reviewers = list(db.prompt_templates.find({
        "$or": [
            {"agent_type": {"$regex": "review"}},
            {"agent_name": {"$regex": "review"}}
        ]
    }))

    for t in all_reviewers:
        print(f"  - agent_type: {t.get('agent_type')}, agent_name: {t.get('agent_name')}")

    print("\n" + "=" * 80)

    # 查询提示词模板 - 先尝试 v2，再尝试普通版本
    template = db.prompt_templates.find_one({
        "agent_type": "reviewers_v2",
        "agent_name": "review_manager_v2"
    })

    if not template:
        print("⚠️ 未找到 reviewers_v2/review_manager_v2，尝试查找其他版本...")
        template = db.prompt_templates.find_one({
            "agent_type": "reviewers",
            "agent_name": "review_manager"
        })

    if not template:
        print("❌ 未找到任何 review_manager 的提示词模板")
        return
    
    print(f"✅ 找到提示词模板: {template.get('_id')}")
    print(f"\n📋 模板信息:")
    print(f"  - agent_type: {template.get('agent_type')}")
    print(f"  - agent_name: {template.get('agent_name')}")
    print(f"  - user_id: {template.get('user_id')}")
    print(f"  - preference_id: {template.get('preference_id')}")
    print(f"  - created_at: {template.get('created_at')}")
    print(f"  - updated_at: {template.get('updated_at')}")
    
    print(f"\n📝 提示词内容:")
    print("=" * 80)
    prompt = template.get('prompt', '')
    print(prompt)
    print("=" * 80)
    
    # 检查提示词中是否包含所有必需的字段
    print(f"\n🔍 检查必需字段:")
    required_fields = [
        'overall_score',
        'timing_score',
        'position_score',
        'emotion_score',
        'attribution_score',
        'discipline_score',
        'timing_analysis',
        'position_analysis',
        'emotion_analysis',
        'attribution_analysis',
        'actual_pnl',
        'optimal_pnl',
        'missed_profit',
        'avoided_loss',
        'plan_adherence',
        'plan_deviation'
    ]
    
    for field in required_fields:
        if field in prompt:
            print(f"  ✅ {field}")
        else:
            print(f"  ❌ {field} - 缺失！")

if __name__ == "__main__":
    check_review_manager_prompt()

