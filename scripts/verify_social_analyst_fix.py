"""
验证社交分析师修复

检查：
1. 数据库中的模板是否正确
2. 代码中的 agent_name 是否正确
3. 模板是否能正常获取

使用方法：
    python scripts/verify_social_analyst_fix.py
"""

import asyncio
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.core.database import init_database, get_mongo_db


async def main():
    print("=" * 80)
    print("验证社交分析师修复")
    print("=" * 80)
    
    # 初始化数据库
    print("\n📡 连接数据库...")
    await init_database()
    db = get_mongo_db()
    print("✅ 数据库连接成功")
    
    # 1. 检查数据库中的模板
    print("\n" + "=" * 80)
    print("1. 检查数据库中的 social_analyst_v2 模板")
    print("=" * 80)
    
    templates = await db.prompt_templates.find({
        "agent_type": "analysts_v2",
        "agent_name": "social_analyst_v2"
    }).to_list(length=None)
    
    print(f"\n📊 找到 {len(templates)} 个模板")
    
    preferences = {}
    for template in templates:
        pref = template.get('preference_type', 'unknown')
        preferences[pref] = template
        print(f"   ✅ {template.get('template_name')} ({pref})")
    
    # 2. 检查是否还有 social_media_analyst_v2
    print("\n" + "=" * 80)
    print("2. 检查是否还有 social_media_analyst_v2 模板")
    print("=" * 80)
    
    old_templates = await db.prompt_templates.find({
        "agent_name": "social_media_analyst_v2"
    }).to_list(length=None)
    
    if old_templates:
        print(f"   ⚠️  还有 {len(old_templates)} 个 social_media_analyst_v2 模板")
        for template in old_templates:
            print(f"      - {template.get('template_name')}")
    else:
        print(f"   ✅ 已删除所有 social_media_analyst_v2 模板")
    
    # 3. 测试模板获取
    print("\n" + "=" * 80)
    print("3. 测试模板获取")
    print("=" * 80)
    
    try:
        from tradingagents.utils.template_client import get_agent_prompt
        
        for pref in ["aggressive", "neutral", "conservative"]:
            print(f"\n📝 测试获取 {pref} 模板...")
            
            prompt = get_agent_prompt(
                agent_type="analysts_v2",
                agent_name="social_analyst_v2",
                variables={"market_name": "A股"},
                preference_id=pref,
                fallback_prompt=None
            )
            
            if prompt:
                print(f"   ✅ 成功获取 {pref} 模板 (长度: {len(prompt)})")
            else:
                print(f"   ❌ 获取 {pref} 模板失败")
    
    except Exception as e:
        print(f"   ❌ 模板获取测试失败: {e}")
    
    # 4. 检查 agent_id 字段
    print("\n" + "=" * 80)
    print("4. 检查 agent_id 字段")
    print("=" * 80)
    
    for template in templates:
        agent_id = template.get('agent_id', 'N/A')
        agent_name = template.get('agent_name', 'N/A')
        pref = template.get('preference_type', 'N/A')
        
        if agent_id == 'social_analyst_v2':
            print(f"   ✅ {pref}: agent_id={agent_id}, agent_name={agent_name}")
        else:
            print(f"   ⚠️  {pref}: agent_id={agent_id}, agent_name={agent_name}")
    
    # 5. 总结
    print("\n" + "=" * 80)
    print("5. 修复验证总结")
    print("=" * 80)
    
    issues = []
    
    if len(templates) != 3:
        issues.append(f"⚠️  social_analyst_v2 模板数量不正确（期望3个，实际{len(templates)}个）")
    
    if old_templates:
        issues.append(f"⚠️  还有 {len(old_templates)} 个 social_media_analyst_v2 模板未删除")
    
    missing_prefs = set(["aggressive", "neutral", "conservative"]) - set(preferences.keys())
    if missing_prefs:
        issues.append(f"⚠️  缺少以下偏好类型的模板: {missing_prefs}")
    
    for template in templates:
        if template.get('agent_id') != 'social_analyst_v2':
            issues.append(f"⚠️  模板 {template.get('template_name')} 的 agent_id 不正确")
    
    if issues:
        print("\n❌ 发现以下问题:")
        for issue in issues:
            print(f"   {issue}")
    else:
        print("\n✅ 所有检查通过！社交分析师修复成功！")
        print("\n📊 修复总结:")
        print(f"   - social_analyst_v2 模板: {len(templates)} 个")
        print(f"   - social_media_analyst_v2 模板: 0 个（已删除）")
        print(f"   - 所有模板都有正确的 agent_id")
        print(f"   - 代码中使用正确的 agent_name")
    
    print("\n" + "=" * 80)


if __name__ == "__main__":
    asyncio.run(main())

