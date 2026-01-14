"""
检查 news_analyst_v2 模板中是否包含错误的日期示例
"""

from pymongo import MongoClient
import os
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# MongoDB 连接配置
MONGODB_HOST = os.getenv("MONGODB_HOST", "127.0.0.1")
MONGODB_PORT = int(os.getenv("MONGODB_PORT", "27017"))
MONGODB_DATABASE = os.getenv("MONGODB_DATABASE", "tradingagents")
MONGODB_USERNAME = os.getenv("MONGODB_USERNAME", "admin")
MONGODB_PASSWORD = os.getenv("MONGODB_PASSWORD", "tradingagents123")
MONGODB_AUTH_SOURCE = os.getenv("MONGODB_AUTH_SOURCE", "admin")

def get_connection_string():
    """构建 MongoDB 连接字符串"""
    if MONGODB_USERNAME and MONGODB_PASSWORD:
        return f"mongodb://{MONGODB_USERNAME}:{MONGODB_PASSWORD}@{MONGODB_HOST}:{MONGODB_PORT}/?authSource={MONGODB_AUTH_SOURCE}"
    return f"mongodb://{MONGODB_HOST}:{MONGODB_PORT}/"

def check_news_analyst_template():
    """检查 news_analyst_v2 模板"""
    client = MongoClient(get_connection_string())
    db = client[MONGODB_DATABASE]
    collection = db["prompt_templates"]
    
    print("=" * 80)
    print("检查 news_analyst_v2 模板中的日期问题")
    print("=" * 80)
    
    # 查找 news_analyst_v2 模板
    templates = list(collection.find({
        "agent_type": "analysts_v2",
        "agent_name": "news_analyst_v2",
        "status": "active"
    }).sort("preference_type", 1))
    
    print(f"\n找到 {len(templates)} 个 news_analyst_v2 模板\n")
    
    for template in templates:
        preference = template.get('preference_type', 'neutral')
        content = template.get('content', {})
        
        system_prompt = content.get('system_prompt', '')
        user_prompt = content.get('user_prompt', '')
        
        print(f"\n{'=' * 80}")
        print(f"模板: preference_type={preference}")
        print(f"{'=' * 80}")
        
        # 检查是否包含2024-04-27
        has_2024_04_27 = "2024-04-27" in system_prompt or "2024-04-27" in user_prompt
        has_2024_04 = "2024-04" in system_prompt or "2024-04" in user_prompt
        has_2024 = "2024" in system_prompt or "2024" in user_prompt
        
        print(f"\nSystem Prompt:")
        print(f"   长度: {len(system_prompt)} 字符")
        print(f"   包含 2024-04-27: {has_2024_04_27}")
        print(f"   包含 2024-04: {has_2024_04}")
        print(f"   包含 2024: {has_2024}")
        
        if has_2024_04_27 or has_2024_04:
            print(f"\n   ⚠️ 发现硬编码日期！")
            if "2024-04-27" in system_prompt:
                idx = system_prompt.find("2024-04-27")
                print(f"   System Prompt 中包含 2024-04-27 (位置: {idx})")
                print(f"   上下文: ...{system_prompt[max(0, idx-50):idx+100]}...")
            if "2024-04-27" in user_prompt:
                idx = user_prompt.find("2024-04-27")
                print(f"   User Prompt 中包含 2024-04-27 (位置: {idx})")
                print(f"   上下文: ...{user_prompt[max(0, idx-50):idx+100]}...")
        
        print(f"\nUser Prompt:")
        print(f"   长度: {len(user_prompt)} 字符")
        if user_prompt:
            print(f"   前500字符预览:")
            print(f"   {user_prompt[:500]}...")
    
    client.close()

if __name__ == "__main__":
    check_news_analyst_template()


