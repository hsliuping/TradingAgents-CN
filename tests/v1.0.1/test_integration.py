"""
提示词模板系统集成测试
"""

import pytest
from app.models.prompt_template import PromptTemplateCreate, TemplateContent
from app.models.analysis_preference import AnalysisPreferenceCreate
from app.models.user_template_config import UserTemplateConfigCreate


@pytest.mark.asyncio
async def test_complete_workflow(template_service, preference_service, config_service):
    """测试完整工作流：创建系统模板 -> 创建偏好 -> 创建配置 -> 获取活跃配置"""
    user_id = "test_user_workflow"
    
    # 1. 创建系统模板
    content = TemplateContent(
        system_prompt="System template prompt",
        tool_guidance="Use system tools",
        analysis_requirements="System analysis"
    )
    
    system_template = await template_service.create_template(
        PromptTemplateCreate(
            agent_type="analysts",
            agent_name="market_analyst",
            template_name="System Template",
            preference_type="neutral",
            content=content
        ),
        is_system=True
    )
    
    assert system_template is not None
    assert system_template.is_system is True
    system_template_id = str(system_template.id)
    
    # 2. 创建用户偏好
    pref_data = AnalysisPreferenceCreate(
        preference_type="aggressive",
        risk_level=0.8,
        confidence_threshold=0.6,
        position_size_multiplier=1.5,
        decision_speed="fast"
    )
    
    preference = await preference_service.create_preference(user_id, pref_data)
    assert preference is not None
    assert preference.preference_type == "aggressive"
    preference_id = str(preference.id)
    
    # 3. 创建用户配置
    config_data = UserTemplateConfigCreate(
        agent_type="analysts",
        agent_name="market_analyst",
        template_id=system_template_id,
        preference_id=preference_id,
        is_active=True
    )
    
    config = await config_service.create_config(user_id, config_data)
    assert config is not None
    assert config.is_active is True
    
    # 4. 获取活跃配置
    active_config = await config_service.get_active_config(
        user_id,
        "analysts",
        "market_analyst",
        preference_id
    )
    
    assert active_config is not None
    assert str(active_config.template_id) == system_template_id


@pytest.mark.asyncio
async def test_user_template_priority(template_service, preference_service, config_service):
    """测试用户模板优先级：用户模板 > 系统模板"""
    user_id = "test_user_priority"
    
    # 1. 创建系统模板
    system_content = TemplateContent(
        system_prompt="System prompt",
        tool_guidance="System tools",
        analysis_requirements="System analysis"
    )
    
    system_template = await template_service.create_template(
        PromptTemplateCreate(
            agent_type="analysts",
            agent_name="market_analyst",
            template_name="System Template",
            preference_type="neutral",
            content=system_content
        ),
        is_system=True
    )
    
    # 2. 创建用户模板
    user_content = TemplateContent(
        system_prompt="User custom prompt",
        tool_guidance="User custom tools",
        analysis_requirements="User custom analysis"
    )
    
    user_template = await template_service.create_template(
        PromptTemplateCreate(
            agent_type="analysts",
            agent_name="market_analyst",
            template_name="User Template",
            preference_type="neutral",
            content=user_content
        ),
        user_id=user_id,
        base_template_id=str(system_template.id),
        base_version=1
    )
    
    assert user_template is not None
    assert user_template.is_system is False
    assert user_template.created_by == user_id
    assert user_template.base_template_id == str(system_template.id)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

