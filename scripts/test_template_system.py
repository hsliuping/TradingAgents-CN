"""
提示词模板系统集成测试
验证系统的基本功能
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.prompt_template_service import PromptTemplateService
from app.services.analysis_preference_service import AnalysisPreferenceService
from app.services.user_template_config_service import UserTemplateConfigService
from app.models.prompt_template import PromptTemplateCreate, TemplateContent
from app.models.analysis_preference import AnalysisPreferenceCreate
from app.models.user_template_config import UserTemplateConfigCreate


async def test_system():
    """测试系统功能"""
    print("🧪 开始测试提示词模板系统...\n")
    
    template_service = PromptTemplateService()
    preference_service = AnalysisPreferenceService()
    config_service = UserTemplateConfigService()
    
    try:
        # 1. 创建系统模板
        print("1️⃣ 测试创建系统模板...")
        content = TemplateContent(
            system_prompt="You are a market analyst",
            tool_guidance="Use market data tools",
            analysis_requirements="Provide detailed analysis"
        )
        
        template_data = PromptTemplateCreate(
            agent_type="analysts",
            agent_name="market_analyst",
            template_name="Test Market Analysis",
            preference_type="neutral",
            content=content
        )
        
        template = await template_service.create_template(
            template_data,
            is_system=True
        )
        
        if template:
            print(f"   ✅ 系统模板创建成功: {template.id}\n")
            template_id = str(template.id)
        else:
            print("   ❌ 系统模板创建失败\n")
            return False
        
        # 2. 创建用户偏好
        print("2️⃣ 测试创建用户偏好...")
        user_id = "test_user_001"
        
        pref_data = AnalysisPreferenceCreate(
            preference_type="aggressive",
            risk_level=0.8,
            confidence_threshold=0.6,
            position_size_multiplier=1.5,
            decision_speed="fast"
        )
        
        preference = await preference_service.create_preference(user_id, pref_data)
        
        if preference:
            print(f"   ✅ 用户偏好创建成功: {preference.id}\n")
            preference_id = str(preference.id)
        else:
            print("   ❌ 用户偏好创建失败\n")
            return False
        
        # 3. 创建用户配置
        print("3️⃣ 测试创建用户配置...")
        config_data = UserTemplateConfigCreate(
            agent_type="analysts",
            agent_name="market_analyst",
            template_id=template_id,
            preference_id=preference_id,
            is_active=True
        )
        
        config = await config_service.create_config(user_id, config_data)
        
        if config:
            print(f"   ✅ 用户配置创建成功: {config.id}\n")
        else:
            print("   ❌ 用户配置创建失败\n")
            return False
        
        # 4. 获取活跃配置
        print("4️⃣ 测试获取活跃配置...")
        active_config = await config_service.get_active_config(
            user_id,
            "analysts",
            "market_analyst",
            preference_id
        )
        
        if active_config:
            print(f"   ✅ 活跃配置获取成功\n")
        else:
            print("   ❌ 活跃配置获取失败\n")
            return False
        
        # 5. 获取用户偏好列表
        print("5️⃣ 测试获取用户偏好列表...")
        preferences = await preference_service.get_user_preferences(user_id)
        
        if preferences:
            print(f"   ✅ 获取用户偏好成功，共{len(preferences)}个\n")
        else:
            print("   ❌ 获取用户偏好失败\n")
            return False
        
        print("🎉 所有测试通过！系统运行正常。\n")
        return True
        
    except Exception as e:
        print(f"❌ 测试失败: {e}\n")
        import traceback
        traceback.print_exc()
        return False
    finally:
        template_service.close()
        preference_service.close()
        config_service.close()


if __name__ == "__main__":
    result = asyncio.run(test_system())
    sys.exit(0 if result else 1)

