"""检查更新后的复盘模板内容"""
from pymongo import MongoClient

MONGO_URI = "mongodb://admin:tradingagents123@127.0.0.1:27017/tradingagents?authSource=admin"
DB_NAME = "tradingagents"

def check_templates():
    """检查更新后的模板"""
    client = MongoClient(MONGO_URI)
    db = client[DB_NAME]
    collection = db['prompt_templates']
    
    print("=" * 80)
    print("🔍 检查更新后的复盘模板")
    print("=" * 80)
    
    # 检查 review_manager_v2
    templates = list(collection.find({
        "agent_type": "reviewers_v2",
        "agent_name": "review_manager_v2"
    }))
    
    for template in templates:
        preference_type = template.get("preference_type", "null")
        content = template.get("content", {})
        user_prompt = content.get("user_prompt", "")
        
        print(f"\n📋 review_manager_v2 ({preference_type}):")
        print("-" * 80)
        
        # 检查是否包含新变量
        has_total_pnl = "{{total_pnl}}" in user_prompt
        has_unrealized_pnl = "{{unrealized_pnl}}" in user_prompt
        has_is_holding = "{{is_holding}}" in user_prompt
        
        print(f"   ✅ total_pnl: {has_total_pnl}")
        print(f"   ✅ unrealized_pnl: {has_unrealized_pnl}")
        print(f"   ✅ is_holding: {has_is_holding}")
        
        # 显示相关片段
        if has_total_pnl:
            lines = user_prompt.split('\n')
            for i, line in enumerate(lines):
                if "{{total_pnl}}" in line or "{{unrealized_pnl}}" in line:
                    print(f"      第 {i+1} 行: {line.strip()[:100]}")
    
    client.close()

if __name__ == "__main__":
    check_templates()
