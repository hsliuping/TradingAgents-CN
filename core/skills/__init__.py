"""
Skill 系统模块

基于 Agent Skills 开放标准 + 扩展字段的混合 Skill 系统。

支持：
1. 标准 Agent Skills 格式（SKILL.md）的导入
2. 扩展字段支持 Function Calling（parameters, returns, implementation）
3. 多种执行协议（python, http, mcp）
4. 第三方开发者标准接口
"""

from .models import (
    SkillMetadata,
    SkillParameter,
    SkillReturns,
    ImplementationType,
    PythonImplementation,
    HttpImplementation,
    McpImplementation,
    SkillImplementation,
)
from .parser import SkillParser
from .converter import SkillConverter
from .executor import SkillExecutor

__all__ = [
    # Models
    "SkillMetadata",
    "SkillParameter",
    "SkillReturns",
    "ImplementationType",
    "PythonImplementation",
    "HttpImplementation",
    "McpImplementation",
    "SkillImplementation",
    # Parser
    "SkillParser",
    # Converter
    "SkillConverter",
    # Executor
    "SkillExecutor",
]

