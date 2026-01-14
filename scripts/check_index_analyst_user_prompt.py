"""
检查 index_analyst_v2 用户提示词模板，查看是否有明确的日期使用说明
"""

import sys
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.core.database import get_mongo_db_sync

def check_user_prompt():
    """检查用户提示词模板"""
    print("=" * 80)
    print("检查 index_analyst_v2 用户提示词模板")
    print("=" * 80)
    
    db = get_mongo_db_sync()
    collection = db.prompt_templates
    
    # 查找所有 index_analyst_v2 的模板
    templates = list(collection.find({
        "agent_type": "analysts_v2",
        "agent_name": "index_analyst_v2",
        "preference_type": "neutral"  # 只看中性型
    }))
    
    if not templates:
        print("❌ 未找到 index_analyst_v2 模板")
        return
    
    template = templates[0]  # 只看第一个
    content = template.get("content", {})
    user_prompt = content.get("user_prompt", "")
    
    print(f"\n用户提示词内容:\n")
    print("=" * 80)
    print(user_prompt)
    print("=" * 80)
    
    # 检查是否包含日期相关的说明
    print("\n检查日期相关说明:")
    print("-" * 80)
    
    keywords = ["current_date", "analysis_date", "trade_date", "日期", "2026", "2024"]
    for keyword in keywords:
        if keyword in user_prompt:
            # 找到关键词的位置
            idx = user_prompt.find(keyword)
            context_start = max(0, idx - 100)
            context_end = min(len(user_prompt), idx + len(keyword) + 100)
            context = user_prompt[context_start:context_end]
            print(f"\n✅ 找到关键词: {keyword}")
            print(f"   上下文: ...{context}...")
    
    # 检查是否有明确的工具调用示例
    if "get_china_market_overview" in user_prompt:
        idx = user_prompt.find("get_china_market_overview")
        context_start = max(0, idx - 150)
        context_end = min(len(user_prompt), idx + len("get_china_market_overview") + 150)
        context = user_prompt[context_start:context_end]
        print(f"\n✅ 找到工具调用示例:")
        print(f"   上下文: ...{context}...")

if __name__ == "__main__":
    check_user_prompt()

