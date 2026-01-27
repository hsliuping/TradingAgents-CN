"""
更新 v2.0 版本的系统提示词模板，在所有系统提示词中添加当前股价信息

使用方法:
    python scripts/update_v2_system_prompts_with_price.py --preview  # 预览修改
    python scripts/update_v2_system_prompts_with_price.py --apply    # 应用修改
"""

import asyncio
import sys
import os
from pathlib import Path
from datetime import datetime

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.database import init_database, get_mongo_db
from motor.motor_asyncio import AsyncIOMotorDatabase
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def preview_templates(agent_name: str = None):
    """预览当前的 v2.0 提示词模板"""
    await init_database()
    db: AsyncIOMotorDatabase = get_mongo_db()
    
    # 构建查询条件
    query = {"is_system": True}
    if agent_name:
        query["agent_name"] = agent_name
    else:
        # 如果没有指定，查找所有 v2.0 版本的系统模板
        query["$or"] = [
            {"agent_type": {"$regex": "_v2$"}},
            {"agent_name": {"$regex": "_v2$"}},
            {"version": {"$in": [2.0, "2.0", "2.0.0"]}}
        ]
    
    templates = await db.prompt_templates.find(
        query,
        {
            "agent_name": 1,
            "agent_type": 1,
            "version": 1,
            "content.system_prompt": 1
        }
    ).to_list(length=200)
    
    logger.info(f"\n📋 找到 {len(templates)} 个 v2.0 系统模板\n")
    
    for template in templates:
        agent_name = template.get("agent_name", "未知")
        agent_type = template.get("agent_type", "未知")
        version = template.get("version", "未知")
        system_prompt = template.get("content", {}).get("system_prompt", "")
        
        logger.info(f"{'='*60}")
        logger.info(f"Agent: {agent_name} ({agent_type})")
        logger.info(f"Version: {version}")
        logger.info(f"{'='*60}")
        
        if system_prompt:
            # 检查是否已包含股价信息
            has_price = (
                "current_price" in system_prompt or 
                "{{current_price}}" in system_prompt or
                "当前价格" in system_prompt or 
                "最新价" in system_prompt or
                "当前股价" in system_prompt
            )
            logger.info(f"包含股价信息: {'✅ 是' if has_price else '❌ 否'}")
            logger.info(f"\n系统提示词 (前300字符):\n{system_prompt[:300]}...\n")
        else:
            logger.info("⚠️ 没有系统提示词\n")


async def update_templates(dry_run=True, agent_name: str = None):
    """更新 v2.0 提示词模板，在系统提示词中添加股价信息"""
    await init_database()
    db: AsyncIOMotorDatabase = get_mongo_db()
    
    # 要添加的股价信息文本（添加到系统提示词中）
    price_info_text = """
**当前股价信息**：
- 最新价: {{current_price}} {{currency_symbol}}
- 市场: {{market_name}}
- 行业: {{industry}}
"""
    
    # 构建查询条件
    query = {"is_system": True}
    if agent_name:
        query["agent_name"] = agent_name
        logger.info(f"🎯 指定更新 Agent: {agent_name}")
    else:
        # 如果没有指定，查找所有 v2.0 版本的系统模板
        query["$or"] = [
            {"agent_type": {"$regex": "_v2$"}},
            {"agent_name": {"$regex": "_v2$"}},
            {"version": {"$in": [2.0, "2.0", "2.0.0"]}}
        ]
        logger.info(f"🔄 更新所有 v2.0 系统模板")
    
    templates = await db.prompt_templates.find(query).to_list(length=200)
    
    logger.info(f"\n🔄 准备更新 {len(templates)} 个 v2.0 系统模板\n")
    
    updated_count = 0
    skipped_count = 0
    
    for template in templates:
        agent_name = template.get("agent_name", "未知")
        agent_type = template.get("agent_type", "未知")
        content = template.get("content", {})
        system_prompt = content.get("system_prompt", "")
        
        # 检查是否已包含股价信息
        if (
            "current_price" in system_prompt or 
            "{{current_price}}" in system_prompt or
            "当前价格" in system_prompt or 
            "最新价" in system_prompt or
            "当前股价" in system_prompt
        ):
            logger.info(f"⏭️  跳过 {agent_name} ({agent_type}): 已包含股价信息")
            skipped_count += 1
            continue
        
        # 在系统提示词中添加股价信息
        # v2.0 模板的标准格式：**分析目标** 和 **分析日期** 之后
        # 优先在 **分析日期** 之后插入，如果没有则在 **分析目标** 之后插入
        
        if "**分析日期**" in system_prompt:
            # 在分析日期之后插入（最理想的位置）
            parts = system_prompt.split("**分析日期**", 1)
            if len(parts) == 2:
                date_section = parts[1]
                # 查找分析日期行的结束位置（换行符）
                insert_pos = date_section.find("\n")
                if insert_pos == -1:
                    insert_pos = len(date_section)
                
                # 在分析日期行之后插入股价信息
                new_system_prompt = (
                    parts[0] + 
                    "**分析日期**" + 
                    date_section[:insert_pos] + 
                    "\n" + price_info_text.strip() + 
                    date_section[insert_pos:]
                )
            else:
                # 如果分割失败，在开头添加
                new_system_prompt = price_info_text.strip() + "\n\n" + system_prompt
        elif "**分析目标**" in system_prompt:
            # 在分析目标之后插入
            parts = system_prompt.split("**分析目标**", 1)
            if len(parts) == 2:
                target_section = parts[1]
                # 查找分析目标行的结束位置（换行符或下一个**标题）
                insert_pos = target_section.find("\n")
                if insert_pos == -1:
                    insert_pos = target_section.find("\n**")
                if insert_pos == -1:
                    insert_pos = len(target_section)
                
                new_system_prompt = (
                    parts[0] + 
                    "**分析目标**" + 
                    target_section[:insert_pos] + 
                    "\n" + price_info_text.strip() + 
                    target_section[insert_pos:]
                )
            else:
                # 如果分割失败，在开头添加
                new_system_prompt = price_info_text.strip() + "\n\n" + system_prompt
        else:
            # 如果没有找到标准格式，在开头添加
            new_system_prompt = price_info_text.strip() + "\n\n" + system_prompt
        
        logger.info(f"✏️  更新 {agent_name} ({agent_type})")
        logger.info(f"   添加内容: {price_info_text.strip()[:50]}...")
        
        if not dry_run:
            # 更新数据库
            result = await db.prompt_templates.update_one(
                {"_id": template["_id"]},
                {
                    "$set": {
                        "content.system_prompt": new_system_prompt,
                        "updated_at": datetime.utcnow()
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
    
    parser = argparse.ArgumentParser(description="更新 v2.0 系统提示词模板，添加股价信息")
    parser.add_argument("--preview", action="store_true", help="预览当前模板")
    parser.add_argument("--apply", action="store_true", help="应用修改到数据库")
    parser.add_argument("--agent", type=str, help="指定要更新的 Agent 名称（如：social_analyst_v2）")
    
    args = parser.parse_args()
    
    if args.preview:
        await preview_templates(agent_name=args.agent)
    elif args.apply:
        logger.info("⚠️  即将修改数据库，请确认...")
        await update_templates(dry_run=False, agent_name=args.agent)
    else:
        # 默认：预览修改
        await update_templates(dry_run=True, agent_name=args.agent)


if __name__ == "__main__":
    asyncio.run(main())
