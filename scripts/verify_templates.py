#!/usr/bin/env python3
"""
验证新创建的智能体模板
"""

import asyncio
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.prompt_template_service import PromptTemplateService
from app.core.database import init_database


async def verify_templates():
    """验证模板是否正确创建"""
    print("🔍 开始验证智能体模板...")
    
    # 初始化数据库
    await init_database()
    
    service = PromptTemplateService()
    
    # 要验证的智能体
    agents_to_verify = [
        ("index_analyst", "大盘/指数分析师"),
        ("sector_analyst", "行业/板块分析师")
    ]
    
    for agent_id, agent_name in agents_to_verify:
        print(f"\n📊 验证 {agent_name} ({agent_id})...")
        
        # 检查每个偏好类型的模板
        for preference in ["aggressive", "neutral", "conservative"]:
            templates = await service.get_system_templates(
                agent_type="analysts",
                agent_name=agent_id,
                preference_type=preference
            )
            
            if templates:
                template = templates[0]
                print(f"  ✅ {preference}: 找到模板 (ID: {template.id})")
                print(f"     - 系统提示词长度: {len(template.content.system_prompt)} 字符")
                print(f"     - 工具指导长度: {len(template.content.tool_guidance)} 字符")
                print(f"     - 分析要求长度: {len(template.content.analysis_requirements)} 字符")
            else:
                print(f"  ❌ {preference}: 未找到模板")
    
    print("\n🎉 验证完成！")


if __name__ == "__main__":
    asyncio.run(verify_templates())
