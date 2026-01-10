"""从 MongoDB 查询 trader_v2 和相关模板"""
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

def query_templates():
    """查询提示词模板"""
    # 构建连接字符串
    if MONGODB_USERNAME and MONGODB_PASSWORD:
        connection_string = f"mongodb://{MONGODB_USERNAME}:{MONGODB_PASSWORD}@{MONGODB_HOST}:{MONGODB_PORT}/?authSource={MONGODB_AUTH_SOURCE}"
    else:
        connection_string = f"mongodb://{MONGODB_HOST}:{MONGODB_PORT}/"

    # 同步连接
    client = MongoClient(connection_string)
    db = client[MONGODB_DATABASE]
    collection = db["prompt_templates"]
    
    print(f"连接到 MongoDB: {MONGODB_HOST}:{MONGODB_PORT}/{MONGODB_DATABASE}")
    print(f"查询集合: prompt_templates\n")
    
    # 1. 查询 trader_v2 模板
    print("=" * 80)
    print("1. trader_v2 模板")
    print("=" * 80)
    
    trader_v2_templates = list(collection.find({
        "agent_type": "trader_v2",
        "agent_name": "trader_v2",
        "status": "active"
    }).sort("preference_type", 1))
    
    print(f"找到 {len(trader_v2_templates)} 个 trader_v2 模板\n")
    
    for t in trader_v2_templates:
        preference = t.get('preference_type', 'N/A')
        content = t.get('content', {})
        
        print(f"\n{'=' * 80}")
        print(f"偏好: {preference}")
        print(f"{'=' * 80}")
        print(f"\n系统提示词:")
        print(f"{'-' * 80}")
        print(content.get('system_prompt', ''))
        print(f"\n{'-' * 80}")
        print(f"输出格式:")
        print(f"{'-' * 80}")
        print(content.get('output_format', ''))
        print(f"\n{'-' * 80}")
        print(f"分析要求:")
        print(f"{'-' * 80}")
        print(content.get('analysis_requirements', ''))
        print()
    
    # 2. 查询旧版 trader 模板作为参考
    print("\n" + "=" * 80)
    print("2. 旧版 trader 模板（参考）")
    print("=" * 80)
    
    trader_templates = list(collection.find({
        "agent_type": "trader",
        "agent_name": "trader",
        "status": "active",
        "preference_type": "neutral"
    }).limit(1))
    
    if trader_templates:
        t = trader_templates[0]
        content = t.get('content', {})
        
        print(f"\n系统提示词（前500字符）:")
        print(f"{'-' * 80}")
        print(content.get('system_prompt', '')[:500])
        print(f"\n{'-' * 80}")
        print(f"输出格式（前500字符）:")
        print(f"{'-' * 80}")
        print(content.get('output_format', '')[:500])
        print(f"\n{'-' * 80}")
        print(f"分析要求（前500字符）:")
        print(f"{'-' * 80}")
        print(content.get('analysis_requirements', '')[:500])
    
    # 3. 查询 research_manager_v2 模板作为参考
    print("\n" + "=" * 80)
    print("3. research_manager_v2 模板（参考）")
    print("=" * 80)
    
    rm_v2_templates = list(collection.find({
        "agent_type": "research_manager_v2",
        "status": "active",
        "preference_type": "neutral"
    }).limit(1))
    
    print(f"找到 {len(rm_v2_templates)} 个 research_manager_v2 模板\n")
    
    if rm_v2_templates:
        t = rm_v2_templates[0]
        content = t.get('content', {})
        
        print(f"\n系统提示词（前500字符）:")
        print(f"{'-' * 80}")
        print(content.get('system_prompt', '')[:500])
        print(f"\n{'-' * 80}")
        print(f"输出格式（前500字符）:")
        print(f"{'-' * 80}")
        print(content.get('output_format', '')[:500])
    
    client.close()

if __name__ == "__main__":
    query_templates()

