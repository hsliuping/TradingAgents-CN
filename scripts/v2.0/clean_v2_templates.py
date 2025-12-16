"""
清理v2.0系统模板脚本
删除所有v2.0 agent的模板，以便重新创建
"""

import asyncio
import sys
from pathlib import Path
from dotenv import load_dotenv

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# 加载环境变量
load_dotenv()

from app.core.database import init_database, close_database, get_mongo_db


async def clean_v2_templates():
    """清理v2.0系统模板"""
    # 初始化MongoDB连接
    await init_database()
    
    db = get_mongo_db()
    templates_collection = db.prompt_templates
    
    # v2.0 agent名称列表
    v2_agent_names = [
        "fundamentals_analyst_v2",
        "market_analyst_v2",
        "news_analyst_v2",
        "social_analyst_v2",
        "sector_analyst_v2",
        "index_analyst_v2",
        "bull_researcher_v2",
        "bear_researcher_v2",
        "research_manager_v2",
        "risk_manager_v2",
        "trader_v2",
        "risky_analyst_v2",
        "safe_analyst_v2",
        "neutral_analyst_v2",
        "timing_analyst_v2",
        "position_analyst_v2",
        "emotion_analyst_v2",
        "attribution_analyst_v2",
        "review_manager_v2",
        "pa_technical_v2",
        "pa_fundamental_v2",
        "pa_risk_v2",
        "pa_advisor_v2",
    ]
    
    print("=" * 80)
    print("开始清理v2.0系统模板")
    print("=" * 80)
    
    total_deleted = 0
    
    for agent_name in v2_agent_names:
        result = await templates_collection.delete_many({
            "agent_name": agent_name,
            "is_system": True
        })
        
        if result.deleted_count > 0:
            print(f"✅ 删除 {agent_name}: {result.deleted_count} 个模板")
            total_deleted += result.deleted_count
    
    print("\n" + "=" * 80)
    print("清理完成")
    print("=" * 80)
    print(f"总共删除: {total_deleted} 个模板")
    print("=" * 80)
    
    # 关闭MongoDB连接
    await close_database()


if __name__ == "__main__":
    asyncio.run(clean_v2_templates())

