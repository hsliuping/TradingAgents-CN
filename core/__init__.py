"""
TradingAgents-CN Pro - 商业版核心模块

此模块包含 TradingAgents-CN Pro 的商业版功能，包括：
- 统一 LLM 客户端 (llm/)
- 智能体基类和注册表 (agents/)
- 工作流引擎 (workflow/)
- 提示词管理增强 (prompts/)
- 授权管理 (licensing/)

许可证: 专有软件 (Proprietary)
版权所有 (c) 2024-2025 TradingAgents-CN Pro

与开源组件的关系:
- 本模块构建在开源 'tradingagents' 包之上
- 开源包使用 Apache 2.0 许可证
- 本模块为专有扩展
"""

__version__ = "1.0.0"
__author__ = "TradingAgents-CN Pro Team"
__license__ = "Proprietary"

# 延迟导入，避免循环依赖
def get_version():
    """获取版本号"""
    return __version__


def get_llm_client():
    """获取统一 LLM 客户端"""
    from .llm import UnifiedLLMClient
    return UnifiedLLMClient


def get_workflow_engine():
    """获取工作流引擎"""
    from .workflow import WorkflowEngine
    return WorkflowEngine


def get_agent_registry():
    """获取智能体注册表"""
    from .agents import AgentRegistry
    return AgentRegistry


# 版本检查
def check_compatibility():
    """检查与开源 tradingagents 的兼容性"""
    try:
        import tradingagents
        ta_version = getattr(tradingagents, '__version__', '0.0.0')
        # 可以在这里添加版本兼容性检查
        return True, ta_version
    except ImportError:
        return False, None


def get_license_manager():
    """获取授权管理器"""
    from .licensing import LicenseManager
    return LicenseManager


def get_workflow_api():
    """获取工作流 API"""
    from .api import WorkflowAPI
    return WorkflowAPI


def get_agent_api():
    """获取智能体 API"""
    from .api import AgentAPI
    return AgentAPI


__all__ = [
    "__version__",
    "__author__",
    "__license__",
    "get_version",
    "get_llm_client",
    "get_workflow_engine",
    "get_agent_registry",
    "get_license_manager",
    "get_workflow_api",
    "get_agent_api",
    "check_compatibility",
]

