"""
修复 news_analyst_v2 和 social_analyst_v2 数据库模板中的工具调用参数错误

将错误的参数：
- stock_code='{ticker}', max_news=10

修复为正确的参数：
- ticker='{ticker}', curr_date='{current_date}'
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

def fix_news_analyst_templates():
    """修复 news_analyst_v2 和 social_analyst_v2 模板中的工具调用参数"""
    client = MongoClient(get_connection_string())
    db = client[MONGODB_DATABASE]
    collection = db["prompt_templates"]
    
    print("=" * 80)
    print("修复 news_analyst_v2 和 social_analyst_v2 模板中的工具调用参数")
    print("=" * 80)
    
    updated_count = 0
    
    # 修复 news_analyst_v2 模板
    print("\n" + "=" * 80)
    print("修复 news_analyst_v2 模板")
    print("=" * 80)
    templates = list(collection.find({
        "agent_type": "analysts_v2",
        "agent_name": "news_analyst_v2",
        "status": "active"
    }).sort("preference_type", 1))
    
    print(f"\n找到 {len(templates)} 个 news_analyst_v2 模板\n")
    
    updated_count = 0
    
    for template in templates:
        preference = template.get('preference_type', 'neutral')
        content = template.get('content', {})
        tool_guidance = content.get('tool_guidance', '')
        
        print(f"\n{'=' * 80}")
        print(f"处理模板: preference_type={preference}")
        print(f"{'=' * 80}")
        
        # 检查是否包含错误的参数
        has_wrong_params = "stock_code" in tool_guidance or "max_news" in tool_guidance
        
        if has_wrong_params:
            print(f"  ⚠️ 发现错误的参数，需要修复")
            print(f"  当前 tool_guidance:")
            print(f"  {tool_guidance[:200]}...")
            
            # 修复参数
            fixed_tool_guidance = tool_guidance.replace(
                "stock_code='{ticker}', max_news=10",
                "ticker='{ticker}', curr_date='{current_date}'"
            )
            fixed_tool_guidance = fixed_tool_guidance.replace(
                "stock_code=\"{ticker}\", max_news=10",
                "ticker=\"{ticker}\", curr_date=\"{current_date}\""
            )
            
            # 更新模板
            collection.update_one(
                {"_id": template["_id"]},
                {"$set": {"content.tool_guidance": fixed_tool_guidance}}
            )
            
            print(f"  ✅ 已修复 tool_guidance")
            print(f"  修复后的 tool_guidance:")
            print(f"  {fixed_tool_guidance[:200]}...")
            updated_count += 1
        else:
            print(f"  ✅ 参数正确，无需修复")
    
    # 修复 social_analyst_v2 模板
    print("\n" + "=" * 80)
    print("修复 social_analyst_v2 模板")
    print("=" * 80)
    templates = list(collection.find({
        "agent_type": "analysts_v2",
        "agent_name": "social_analyst_v2",
        "status": "active"
    }).sort("preference_type", 1))
    
    print(f"\n找到 {len(templates)} 个 social_analyst_v2 模板\n")
    
    for template in templates:
        preference = template.get('preference_type', 'neutral')
        content = template.get('content', {})
        tool_guidance = content.get('tool_guidance', '')
        
        print(f"\n{'=' * 80}")
        print(f"处理模板: preference_type={preference}")
        print(f"{'=' * 80}")
        
        # 检查是否包含错误的参数或缺少参数说明
        has_wrong_params = "stock_code" in tool_guidance or "max_news" in tool_guidance
        missing_params = "get_stock_sentiment_unified" in tool_guidance and "ticker=" not in tool_guidance and "curr_date=" not in tool_guidance
        
        if has_wrong_params or missing_params:
            print(f"  ⚠️ 发现需要修复的问题")
            print(f"  当前 tool_guidance:")
            print(f"  {tool_guidance[:200]}...")
            
            # 修复参数
            fixed_tool_guidance = tool_guidance.replace(
                "stock_code='{ticker}', max_news=10",
                "ticker='{ticker}', curr_date='{current_date}'"
            )
            fixed_tool_guidance = fixed_tool_guidance.replace(
                "stock_code=\"{ticker}\", max_news=10",
                "ticker=\"{ticker}\", curr_date=\"{current_date}\""
            )
            
            # 如果没有参数说明，添加参数说明
            if "get_stock_sentiment_unified" in fixed_tool_guidance and "ticker=" not in fixed_tool_guidance:
                # 在工具名称后添加参数说明
                fixed_tool_guidance = fixed_tool_guidance.replace(
                    "get_stock_sentiment_unified",
                    "get_stock_sentiment_unified 工具获取情绪数据\n参数: ticker='{ticker}', curr_date='{current_date}'"
                )
            
            # 更新模板
            collection.update_one(
                {"_id": template["_id"]},
                {"$set": {"content.tool_guidance": fixed_tool_guidance}}
            )
            
            print(f"  ✅ 已修复 tool_guidance")
            print(f"  修复后的 tool_guidance:")
            print(f"  {fixed_tool_guidance[:200]}...")
            updated_count += 1
        else:
            print(f"  ✅ 参数正确，无需修复")
    
    print(f"\n{'=' * 80}")
    print(f"修复完成！共更新 {updated_count} 个模板")
    print(f"{'=' * 80}")
    
    client.close()

if __name__ == "__main__":
    fix_news_analyst_templates()

