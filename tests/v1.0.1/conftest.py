"""
v1.0.1 测试配置
"""

import pytest
import sys
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from app.services.prompt_template_service import PromptTemplateService
from app.services.analysis_preference_service import AnalysisPreferenceService
from app.services.user_template_config_service import UserTemplateConfigService
from app.services.template_history_service import TemplateHistoryService


@pytest.fixture
def template_service():
    """提示词模板服务fixture"""
    service = PromptTemplateService()
    yield service
    service.close()


@pytest.fixture
def preference_service():
    """分析偏好服务fixture"""
    service = AnalysisPreferenceService()
    yield service
    service.close()


@pytest.fixture
def config_service():
    """用户模板配置服务fixture"""
    service = UserTemplateConfigService()
    yield service
    service.close()


@pytest.fixture
def history_service():
    """模板历史服务fixture"""
    service = TemplateHistoryService()
    yield service
    service.close()

