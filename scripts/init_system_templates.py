"""
初始化系统模板
创建31个系统模板（13个Agent × 偏好类型）
"""

import asyncio
import sys
from pathlib import Path

# 添加项目根目录到Python路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.prompt_template_service import PromptTemplateService
from app.models.prompt_template import PromptTemplateCreate, TemplateContent


# 定义所有Agent和偏好类型
AGENTS = {
    "analysts": [
        "fundamentals_analyst",
        "market_analyst",
        "news_analyst",
        "social_media_analyst"
    ],
    "researchers": [
        "bull_researcher",
        "bear_researcher"
    ],
    "debators": [
        "aggressive_debator",
        "conservative_debator",
        "neutral_debator"
    ],
    "managers": [
        "research_manager",
        "risk_manager"
    ],
    "trader": [
        "trader"
    ]
}

PREFERENCE_TYPES = ["aggressive", "neutral", "conservative"]


async def create_system_templates():
    """创建所有系统模板"""
    service = PromptTemplateService()
    
    try:
        template_count = 0
        
        for agent_type, agent_names in AGENTS.items():
            for agent_name in agent_names:
                for preference_type in PREFERENCE_TYPES:
                    # 创建模板内容
                    content = TemplateContent(
                        system_prompt=f"You are a {agent_name} with {preference_type} preference",
                        user_prompt="",
                        tool_guidance=f"Use appropriate tools for {agent_name} analysis",
                        analysis_requirements=f"Provide {preference_type} level analysis",
                        output_format="Structured JSON format",
                        constraints=f"Follow {preference_type} risk management rules"
                    )
                    
                    # 创建模板
                    template_data = PromptTemplateCreate(
                        agent_type=agent_type,
                        agent_name=agent_name,
                        template_name=f"{agent_name.title()} - {preference_type.title()}",
                        preference_type=preference_type,
                        content=content
                    )
                    
                    # 保存为系统模板
                    template, operation = await service.upsert_system_template(
                        template_data,
                        remark_suffix="[2026-04-11] 幂等同步通用系统模板",
                    )
                    
                    if template:
                        template_count += 1
                        action_text = {"created": "创建", "updated": "更新", "unchanged": "保持"}.get(operation, operation)
                        print(f"✅ {action_text}: {agent_type}/{agent_name}/{preference_type}")
                    else:
                        print(f"❌ 同步模板失败: {agent_type}/{agent_name}/{preference_type}")
        
        print(f"\n🎉 成功创建 {template_count} 个系统模板")
        return True
        
    except Exception as e:
        print(f"❌ 初始化失败: {e}")
        return False
    finally:
        if hasattr(service, "close"):
            service.close()


if __name__ == "__main__":
    result = asyncio.run(create_system_templates())
    sys.exit(0 if result else 1)

