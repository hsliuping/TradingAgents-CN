"""
更新提示词模板，将当前股价信息添加到用户提示词中

使用方法:
    python scripts/update_prompts_with_price.py --preview  # 预览修改
    python scripts/update_prompts_with_price.py --apply    # 应用修改
"""

import asyncio
import sys
import os
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.database import init_database, get_mongo_db
from motor.motor_asyncio import AsyncIOMotorDatabase
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def preview_templates():
    """预览当前的提示词模板"""
    await init_database()
    db: AsyncIOMotorDatabase = get_mongo_db()
    
    templates = await db.prompt_templates.find(
        {"is_system": True, "agent_type": "analysts"},
        {"agent_name": 1, "content.user_prompt": 1}
    ).to_list(length=100)
    
    logger.info(f"\n📋 找到 {len(templates)} 个分析师系统模板\n")
    
    for template in templates:
        agent_name = template.get("agent_name", "未知")
        user_prompt = template.get("content", {}).get("user_prompt", "")
        
        logger.info(f"{'='*60}")
        logger.info(f"Agent: {agent_name}")
        logger.info(f"{'='*60}")
        
        if user_prompt:
            # 检查是否已包含股价信息
            has_price = "current_price" in user_prompt or "当前价格" in user_prompt or "最新价" in user_prompt
            logger.info(f"包含股价信息: {'✅ 是' if has_price else '❌ 否'}")
            logger.info(f"\n用户提示词 (前200字符):\n{user_prompt[:200]}...\n")
        else:
            logger.info("⚠️ 没有用户提示词\n")


async def update_templates(dry_run=True):
    """更新提示词模板，添加股价信息"""
    await init_database()
    db: AsyncIOMotorDatabase = get_mongo_db()
    
    # 要添加的股价信息文本
    price_info_text = """
当前股价信息：
- 最新价: {{current_price}} {{currency_symbol}}
- 市场: {{market_name}}
- 行业: {{industry}}
"""
    
    templates = await db.prompt_templates.find(
        {"is_system": True, "agent_type": "analysts"}
    ).to_list(length=100)
    
    logger.info(f"\n🔄 准备更新 {len(templates)} 个分析师模板\n")
    
    updated_count = 0
    skipped_count = 0
    
    for template in templates:
        agent_name = template.get("agent_name", "未知")
        content = template.get("content", {})
        user_prompt = content.get("user_prompt", "")
        
        # 检查是否已包含股价信息
        if "current_price" in user_prompt or "当前价格" in user_prompt or "最新价" in user_prompt:
            logger.info(f"⏭️  跳过 {agent_name}: 已包含股价信息")
            skipped_count += 1
            continue
        
        # 在用户提示词开头添加股价信息
        new_user_prompt = price_info_text.strip() + "\n\n" + user_prompt
        
        logger.info(f"✏️  更新 {agent_name}")
        logger.info(f"   添加内容: {price_info_text.strip()[:50]}...")
        
        if not dry_run:
            # 更新数据库
            result = await db.prompt_templates.update_one(
                {"_id": template["_id"]},
                {
                    "$set": {
                        "content.user_prompt": new_user_prompt,
                        "updated_at": "2026-01-27T00:00:00Z"
                    }
                }
            )
            
            if result.modified_count > 0:
                updated_count += 1
                logger.info(f"   ✅ 已更新")
            else:
                logger.info(f"   ❌ 更新失败")
        else:
            updated_count += 1
            logger.info(f"   🔍 预览模式 - 未实际修改")
    
    logger.info(f"\n{'='*60}")
    logger.info(f"📊 统计:")
    logger.info(f"   - 需要更新: {updated_count}")
    logger.info(f"   - 已跳过: {skipped_count}")
    logger.info(f"   - 总计: {len(templates)}")
    
    if dry_run:
        logger.info(f"\n💡 这是预览模式，未实际修改数据库")
        logger.info(f"   使用 --apply 参数应用修改")
    else:
        logger.info(f"\n✅ 数据库已更新")


async def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="更新提示词模板，添加股价信息")
    parser.add_argument("--preview", action="store_true", help="预览当前模板")
    parser.add_argument("--apply", action="store_true", help="应用修改到数据库")
    
    args = parser.parse_args()
    
    if args.preview:
        await preview_templates()
    elif args.apply:
        logger.info("⚠️  即将修改数据库，请确认...")
        await update_templates(dry_run=False)
    else:
        # 默认：预览修改
        await update_templates(dry_run=True)


if __name__ == "__main__":
    asyncio.run(main())

