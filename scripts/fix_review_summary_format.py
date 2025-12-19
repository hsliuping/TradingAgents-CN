"""
修复数据库中 ai_review.summary 字段的格式问题

问题：summary 字段可能是字典而非字符串，导致 Pydantic 验证失败
解决：将字典转换为字符串
"""

import asyncio
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import MongoClient
import json


async def fix_review_summaries():
    """修复复盘报告中的 summary 字段格式"""
    
    # 连接数据库
    client = AsyncIOMotorClient("mongodb://localhost:27017/")
    db = client["tradingagents"]
    collection = db["trade_reviews"]
    
    # 查找所有 ai_review.summary 是字典的文档
    cursor = collection.find({
        "ai_review.summary": {"$type": "object"}
    })
    
    fixed_count = 0
    async for doc in cursor:
        review_id = doc.get("review_id")
        summary = doc.get("ai_review", {}).get("summary", {})
        
        print(f"\n处理复盘: {review_id}")
        print(f"  原始 summary 类型: {type(summary)}")
        print(f"  原始 summary 内容: {summary}")
        
        # 转换为字符串
        if isinstance(summary, dict):
            # 尝试提取有意义的文本
            summary_str = (
                summary.get("overall_assessment") or 
                summary.get("综合评价") or 
                summary.get("核心结论") or 
                json.dumps(summary, ensure_ascii=False, indent=2)
            )
        else:
            summary_str = str(summary)
        
        print(f"  新 summary: {summary_str[:100]}...")
        
        # 更新数据库
        result = await collection.update_one(
            {"review_id": review_id},
            {"$set": {"ai_review.summary": summary_str}}
        )
        
        if result.modified_count > 0:
            fixed_count += 1
            print(f"  ✅ 已修复")
        else:
            print(f"  ⚠️ 未修改")
    
    print(f"\n总计修复: {fixed_count} 条记录")
    client.close()


async def fix_list_fields():
    """修复 strengths, weaknesses, suggestions 字段格式"""
    
    client = AsyncIOMotorClient("mongodb://localhost:27017/")
    db = client["tradingagents"]
    collection = db["trade_reviews"]
    
    # 查找所有文档
    cursor = collection.find({})
    
    fixed_count = 0
    async for doc in cursor:
        review_id = doc.get("review_id")
        ai_review = doc.get("ai_review", {})
        
        updates = {}
        
        # 检查并修复 strengths
        strengths = ai_review.get("strengths", [])
        if not isinstance(strengths, list):
            updates["ai_review.strengths"] = [str(strengths)] if strengths else []
        
        # 检查并修复 weaknesses
        weaknesses = ai_review.get("weaknesses", [])
        if not isinstance(weaknesses, list):
            updates["ai_review.weaknesses"] = [str(weaknesses)] if weaknesses else []
        
        # 检查并修复 suggestions
        suggestions = ai_review.get("suggestions", [])
        if not isinstance(suggestions, list):
            updates["ai_review.suggestions"] = [str(suggestions)] if suggestions else []
        
        if updates:
            print(f"\n修复复盘: {review_id}")
            print(f"  更新字段: {list(updates.keys())}")
            
            result = await collection.update_one(
                {"review_id": review_id},
                {"$set": updates}
            )
            
            if result.modified_count > 0:
                fixed_count += 1
                print(f"  ✅ 已修复")
    
    print(f"\n总计修复: {fixed_count} 条记录")
    client.close()


async def main():
    """主函数"""
    print("=" * 60)
    print("修复复盘报告数据格式")
    print("=" * 60)
    
    print("\n步骤 1: 修复 summary 字段...")
    await fix_review_summaries()
    
    print("\n步骤 2: 修复列表字段...")
    await fix_list_fields()
    
    print("\n✅ 所有修复完成！")


if __name__ == "__main__":
    asyncio.run(main())

