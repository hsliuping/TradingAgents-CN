"""验证时间上下文说明是否已添加到提示词模板"""

import sys
import os

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from pymongo import MongoClient
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

def verify_time_context():
    """验证时间上下文说明"""
    
    # 连接数据库
    mongo_uri = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
    db_name = os.getenv("MONGODB_DB_NAME", "tradingagents")
    
    client = MongoClient(mongo_uri)
    db = client[db_name]
    collection = db.prompt_templates
    
    print("=" * 60)
    print("验证时间上下文说明")
    print("=" * 60)
    
    # 查询 research_manager_v2 的模板
    for preference in ["aggressive", "neutral", "conservative"]:
        template = collection.find_one({
            "agent_type": "managers_v2",
            "agent_name": "research_manager_v2",
            "preference_type": preference,
            "is_system": True
        })
        
        if not template:
            print(f"❌ 未找到模板: research_manager_v2 / {preference}")
            continue
        
        user_prompt = template.get("content", {}).get("user_prompt", "")
        
        # 检查是否包含时间上下文说明
        has_time_context = "⏰ 时间上下文说明" in user_prompt
        has_annual_report_guide = "等待财报" in user_prompt or "等待年报" in user_prompt
        
        print(f"\n📋 research_manager_v2 / {preference}:")
        print(f"  - 用户提示词长度: {len(user_prompt)} 字符")
        print(f"  - 包含时间上下文说明: {'✅' if has_time_context else '❌'}")
        print(f"  - 包含年报指导: {'✅' if has_annual_report_guide else '❌'}")
        
        if has_time_context:
            # 提取时间上下文部分
            start_idx = user_prompt.find("⏰ 时间上下文说明")
            if start_idx != -1:
                context_section = user_prompt[start_idx:start_idx+300]
                print(f"\n  📝 时间上下文说明片段:")
                for line in context_section.split('\n')[:6]:
                    print(f"     {line}")
    
    client.close()
    print("\n" + "=" * 60)

if __name__ == "__main__":
    try:
        verify_time_context()
    except Exception as e:
        print(f"\n❌ 验证失败: {e}")
        import traceback
        traceback.print_exc()

