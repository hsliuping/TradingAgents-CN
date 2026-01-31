"""
修复数据库中重复的免责声明

问题：
1. 免责声明被重复添加多次
2. 免责声明中的"投资建议"被错误替换为"分析观点"

解决方案：
1. 移除所有重复的免责声明
2. 保留一个正确的免责声明
"""

import asyncio
import re
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from app.core.database import init_database, get_mongo_db, close_database

# 正确的免责声明（不应被术语替换影响）
CORRECT_DISCLAIMER = """
**免责声明**：
本分析报告仅供参考，不构成投资建议。所有价格区间、市场观点均为分析参考，
不构成买卖操作建议。投资有风险，决策需谨慎。投资者应根据自身情况，结合
专业投资顾问意见，独立做出投资决策。"""

# 可能出现的错误免责声明模式
DISCLAIMER_PATTERNS = [
    r'\*\*免责声明\*\*[：:]\s*本分析报告仅供参考.*?独立做出投资决策。',
]


def fix_disclaimers(text: str) -> str:
    """修复文本中的免责声明"""
    if not text:
        return text
    
    # 1. 移除所有免责声明（包括错误的和重复的）
    result = text
    for pattern in DISCLAIMER_PATTERNS:
        # 使用 re.DOTALL 让 . 匹配换行符
        result = re.sub(pattern, '', result, flags=re.DOTALL)
    
    # 2. 清理多余的空行
    result = re.sub(r'\n{3,}', '\n\n', result)
    result = result.rstrip()
    
    # 3. 添加一个正确的免责声明
    result = result + CORRECT_DISCLAIMER
    
    return result


async def fix_prompt_templates():
    """修复数据库中的提示词模板"""
    
    # 初始化数据库连接
    try:
        await init_database()
        db = get_mongo_db()
        collection = db.prompt_templates
    except Exception as e:
        print(f"❌ 数据库连接失败: {e}")
        return
    
    # 查找所有模板
    templates = await collection.find({}).to_list(length=None)
    print(f"📊 找到 {len(templates)} 个模板")
    
    fixed_count = 0
    
    for template in templates:
        template_id = template.get("_id")
        agent_type = template.get("agent_type", "unknown")
        agent_name = template.get("agent_name", "unknown")
        
        update_doc = {}
        needs_update = False
        
        # 检查 system_prompt
        if "content" in template and "system_prompt" in template["content"]:
            old_text = template["content"]["system_prompt"]
            
            # 检查是否有重复的免责声明
            disclaimer_count = old_text.count("**免责声明**")
            if disclaimer_count > 1 or "不构成分析观点" in old_text:
                new_text = fix_disclaimers(old_text)
                update_doc["content.system_prompt"] = new_text
                needs_update = True
                print(f"  📝 {agent_type}/{agent_name}: 修复 system_prompt (原有 {disclaimer_count} 个免责声明)")
        
        # 执行更新
        if needs_update:
            await collection.update_one(
                {"_id": template_id},
                {"$set": update_doc}
            )
            fixed_count += 1
    
    print(f"\n✅ 修复了 {fixed_count} 个模板")
    
    # 关闭数据库连接
    await close_database()


async def preview_fix():
    """预览修复效果"""
    
    try:
        await init_database()
        db = get_mongo_db()
        collection = db.prompt_templates
    except Exception as e:
        print(f"❌ 数据库连接失败: {e}")
        return
    
    # 查找一个有问题的模板
    template = await collection.find_one({
        "content.system_prompt": {"$regex": "不构成分析观点|免责声明.*免责声明"}
    })
    
    if not template:
        print("✅ 没有找到需要修复的模板")
        await close_database()
        return
    
    old_text = template["content"]["system_prompt"]
    new_text = fix_disclaimers(old_text)
    
    print("=" * 80)
    print(f"模板: {template.get('agent_type')}/{template.get('agent_name')}")
    print("=" * 80)
    print(f"\n【修复前】(最后800字符)")
    print("-" * 80)
    print(old_text[-800:])
    print(f"\n【修复后】(最后500字符)")
    print("-" * 80)
    print(new_text[-500:])
    
    await close_database()


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "preview":
        print("🔍 预览模式")
        asyncio.run(preview_fix())
    elif len(sys.argv) > 1 and sys.argv[1] == "--yes":
        print("🚀 自动确认模式，开始修复...")
        asyncio.run(fix_prompt_templates())
    else:
        print("⚠️  这将修复数据库中重复的免责声明")
        print("   预览: python fix_duplicate_disclaimers.py preview")
        print("   执行: python fix_duplicate_disclaimers.py --yes")

