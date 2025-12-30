"""
查看数据库中现有的持仓分析模板
"""

import asyncio
import sys
from pathlib import Path
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 添加项目根目录到Python路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.database import init_database, get_mongo_db


async def check_templates():
    """查看现有的持仓分析模板"""
    print("🚀 开始查询持仓分析模板...")
    print("🔄 正在初始化数据库连接...")
    
    await init_database()
    db = await get_mongo_db()
    
    print("✅ 数据库连接初始化完成\n")
    
    # 查询所有可能的 agent_type 和 agent_name 组合
    agent_types = ["position_analysis", "position_analysts"]
    agent_names = ["pa_technical", "pa_technical_v2", "pa_fundamental", "pa_fundamental_v2", 
                   "pa_risk", "pa_risk_v2", "pa_advisor", "pa_advisor_v2"]
    
    print("=" * 80)
    print("📋 查询结果：")
    print("=" * 80)
    
    total_count = 0
    
    for agent_type in agent_types:
        for agent_name in agent_names:
            # 查询该组合的所有模板
            templates = await db.prompt_templates.find({
                "agent_type": agent_type,
                "agent_name": agent_name
            }).to_list(None)
            
            if templates:
                print(f"\n📌 {agent_type} / {agent_name}:")
                print(f"   找到 {len(templates)} 个模板")
                total_count += len(templates)
                
                for template in templates:
                    preference_type = template.get("preference_type", "null")
                    template_name = template.get("template_name", "N/A")
                    version = template.get("version", 1)
                    is_system = template.get("is_system", False)
                    
                    print(f"   - preference_type: {preference_type}")
                    print(f"     template_name: {template_name}")
                    print(f"     version: {version}")
                    print(f"     is_system: {is_system}")
                    
                    # 检查是否有 user_prompt 字段
                    content = template.get("content", {})
                    has_user_prompt = "user_prompt" in content
                    print(f"     has_user_prompt: {has_user_prompt}")
                    print()
    
    print("=" * 80)
    print(f"📊 总计找到 {total_count} 个模板")
    print("=" * 80)
    
    # 额外查询：查看所有 preference_type 的值
    print("\n📋 所有 preference_type 值：")
    distinct_preferences = await db.prompt_templates.distinct("preference_type")
    print(f"   {distinct_preferences}")


if __name__ == "__main__":
    asyncio.run(check_templates())

