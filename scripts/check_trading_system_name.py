"""检查复盘报告中的 trading_system_name 字段"""
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv
import os

load_dotenv()

async def check_trading_system_name():
    """检查复盘报告中的 trading_system_name 字段"""
    # 连接数据库
    mongo_uri = os.getenv("MONGO_URI", "mongodb://localhost:27017")
    client = AsyncIOMotorClient(mongo_uri)
    db = client["tradingagents"]
    
    # 查询最近的复盘报告
    reports = await db["trade_reviews"].find().sort("created_at", -1).limit(5).to_list(length=5)
    
    print(f"\n📊 最近 5 条复盘报告的 trading_system_name 字段：\n")
    for i, report in enumerate(reports, 1):
        review_id = report.get("review_id", "N/A")
        trading_system_id = report.get("trading_system_id", "N/A")
        trading_system_name = report.get("trading_system_name", "N/A")
        code = report.get("trade_info", {}).get("code", "N/A")
        
        print(f"{i}. review_id: {review_id}")
        print(f"   股票代码: {code}")
        print(f"   trading_system_id: {trading_system_id}")
        print(f"   trading_system_name: {trading_system_name}")
        print()
    
    client.close()

if __name__ == "__main__":
    asyncio.run(check_trading_system_name())

