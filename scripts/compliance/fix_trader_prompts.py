"""
修复 trader_v2 模板中的术语问题

问题：
1. "建议价格" 应改为 "参考价格"
2. "风险控制风险控制参考价格" 重复替换错误
3. "偏多观点/看跌的数量" 表述不清
"""

import asyncio
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from app.core.database import init_database, get_mongo_db, close_database


# 需要修复的替换规则
FIXES = [
    ("**建议价格**", "**参考价格**"),
    ("风险控制风险控制参考价格", "风险控制参考价格"),
    ("偏多观点/看跌的数量", "看涨/看跌观点的数量"),
]


async def fix_templates():
    """修复数据库中的模板"""
    
    await init_database()
    db = get_mongo_db()
    
    # 查找所有包含问题术语的模板
    templates = await db.prompt_templates.find({
        "$or": [
            {"content.user_prompt": {"$regex": "建议价格"}},
            {"content.user_prompt": {"$regex": "风险控制风险控制"}},
            {"content.user_prompt": {"$regex": "偏多观点/看跌"}},
            {"content.system_prompt": {"$regex": "建议价格"}},
            {"content.system_prompt": {"$regex": "风险控制风险控制"}},
        ]
    }).to_list(length=None)
    
    print(f"找到 {len(templates)} 个需要修复的模板")
    
    fixed_count = 0
    for t in templates:
        agent_type = t.get("agent_type", "unknown")
        agent_name = t.get("agent_name", "unknown")
        pref = t.get("preference_type", "")
        
        update_doc = {}
        
        # 检查并修复 user_prompt
        user_prompt = t.get("content", {}).get("user_prompt", "")
        if user_prompt:
            new_text = user_prompt
            for old, new in FIXES:
                new_text = new_text.replace(old, new)
            if new_text != user_prompt:
                update_doc["content.user_prompt"] = new_text
        
        # 检查并修复 system_prompt
        system_prompt = t.get("content", {}).get("system_prompt", "")
        if system_prompt:
            new_text = system_prompt
            for old, new in FIXES:
                new_text = new_text.replace(old, new)
            if new_text != system_prompt:
                update_doc["content.system_prompt"] = new_text
        
        if update_doc:
            await db.prompt_templates.update_one(
                {"_id": t["_id"]},
                {"$set": update_doc}
            )
            print(f"  ✅ 修复: {agent_type}/{agent_name} ({pref})")
            fixed_count += 1
    
    print(f"\n总共修复了 {fixed_count} 个模板")
    await close_database()


if __name__ == "__main__":
    asyncio.run(fix_templates())

