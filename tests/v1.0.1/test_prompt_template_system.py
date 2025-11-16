"""
提示词模板系统测试
"""

import pytest
import asyncio
from app.services.prompt_template_service import PromptTemplateService
from app.services.analysis_preference_service import AnalysisPreferenceService
from app.services.user_template_config_service import UserTemplateConfigService
from app.services.template_history_service import TemplateHistoryService
from app.models.prompt_template import PromptTemplateCreate, TemplateContent
from app.models.analysis_preference import AnalysisPreferenceCreate
from app.models.user_template_config import UserTemplateConfigCreate


@pytest.fixture
def template_service():
    """创建模板服务实例"""
    service = PromptTemplateService()
    yield service
    service.close()


@pytest.fixture
def preference_service():
    """创建偏好服务实例"""
    service = AnalysisPreferenceService()
    yield service
    service.close()


@pytest.fixture
def config_service():
    """创建配置服务实例"""
    service = UserTemplateConfigService()
    yield service
    service.close()


@pytest.fixture
def history_service():
    """创建历史服务实例"""
    service = TemplateHistoryService()
    yield service
    service.close()


@pytest.mark.asyncio
async def test_create_system_template(template_service):
    """测试创建系统模板"""
    content = TemplateContent(
        system_prompt="You are a market analyst",
        tool_guidance="Use market data tools",
        analysis_requirements="Provide detailed analysis"
    )
    
    template_data = PromptTemplateCreate(
        agent_type="analysts",
        agent_name="market_analyst",
        template_name="Market Analysis Template",
        preference_type="neutral",
        content=content
    )
    
    template = await template_service.create_template(
        template_data,
        is_system=True
    )
    
    assert template is not None
    assert template.agent_type == "analysts"
    assert template.is_system is True
    assert template.status == "active"


@pytest.mark.asyncio
async def test_create_user_preference(preference_service):
    """测试创建用户偏好"""
    user_id = "test_user_123"
    
    pref_data = AnalysisPreferenceCreate(
        preference_type="aggressive",
        risk_level=0.8,
        confidence_threshold=0.6,
        position_size_multiplier=1.5,
        decision_speed="fast"
    )
    
    preference = await preference_service.create_preference(user_id, pref_data)
    
    assert preference is not None
    assert preference.user_id == user_id
    assert preference.preference_type == "aggressive"
    assert preference.risk_level == 0.8


@pytest.mark.asyncio
async def test_get_user_preferences(preference_service):
    """测试获取用户所有偏好"""
    user_id = "test_user_456"

    # 创建多个偏好
    for pref_type in ["aggressive", "neutral", "conservative"]:
        pref_data = AnalysisPreferenceCreate(
            preference_type=pref_type,
            risk_level=0.5,
            confidence_threshold=0.6,
            position_size_multiplier=1.0,
            decision_speed="normal"
        )
        await preference_service.create_preference(user_id, pref_data)

    preferences = await preference_service.get_user_preferences(user_id)

    assert len(preferences) >= 3
    assert any(p.preference_type == "aggressive" for p in preferences)
    assert any(p.preference_type == "neutral" for p in preferences)
    assert any(p.preference_type == "conservative" for p in preferences)


@pytest.mark.asyncio
async def test_complete_workflow(template_service, preference_service, config_service):
    """测试完整工作流"""
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

    # 4. 获取活跃配置
    active_config = await config_service.get_active_config(
        user_id,
        "analysts",
        "market_analyst",
        preference_id
    )

    assert active_config is not None
    assert active_config.template_id == system_template_id


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

