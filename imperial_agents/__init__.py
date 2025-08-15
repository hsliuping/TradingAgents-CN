"""
帝国AI角色适配层初始化
Imperial Agents Initialization Module
"""

# 版本信息
__version__ = "1.0.0"
__author__ = "帝国AI团队"
__description__ = "帝国AI角色适配层 - 融合TradingAgents能力与帝国角色个性"

# 核心导入
from imperial_agents.core.imperial_agent_wrapper import (
    ImperialAgentWrapper,
    AnalysisResult,
    RoleConfig,
    AnalysisType,
    DecisionLevel,
    ImperialAgentFactory
)

from imperial_agents.config.role_config_manager import (
    RoleConfigManager,
    get_config_manager
)

# 导出主要接口
__all__ = [
    # 核心类
    'ImperialAgentWrapper',
    'AnalysisResult',
    'RoleConfig',
    'ImperialAgentFactory',
    
    # 枚举类型
    'AnalysisType',
    'DecisionLevel',
    
    # 配置管理
    'RoleConfigManager',
    'get_config_manager',
    
    # 版本信息
    '__version__',
    '__author__',
    '__description__'
]
