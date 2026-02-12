"""
Skill ↔ Function Calling 转换器

将 SkillMetadata 转换为：
1. OpenAI Function Calling 工具定义格式
2. ToolMetadata（兼容现有 ToolRegistry）
3. 从现有 ToolMetadata 转换为 SkillMetadata
"""

import logging
from typing import Any, Dict, List, Optional

from .models import (
    ImplementationType,
    PythonImplementation,
    SkillMetadata,
    SkillParameter,
    SkillReturns,
)

logger = logging.getLogger(__name__)


# JSON type 映射
_TYPE_MAP = {
    "string": "string",
    "str": "string",
    "integer": "integer",
    "int": "integer",
    "number": "number",
    "float": "number",
    "boolean": "boolean",
    "bool": "boolean",
    "array": "array",
    "list": "array",
    "object": "object",
    "dict": "object",
}


class SkillConverter:
    """Skill 转换器"""

    @staticmethod
    def to_openai_tool(skill: SkillMetadata) -> Dict[str, Any]:
        """
        将 SkillMetadata 转换为 OpenAI Function Calling 工具定义

        Returns:
            OpenAI 格式的工具定义:
            {
                "type": "function",
                "function": {
                    "name": "...",
                    "description": "...",
                    "parameters": { ... }
                }
            }
        """
        # 构建描述：合并 description + when_to_use
        description = skill.description
        if skill.when_to_use:
            description += f"\n\n何时使用: {skill.when_to_use}"

        # 构建参数的 JSON Schema
        properties = {}
        required = []

        for param in skill.parameters:
            json_type = _TYPE_MAP.get(param.type.lower(), "string")
            prop: Dict[str, Any] = {
                "type": json_type,
                "description": param.description,
            }
            if param.enum:
                prop["enum"] = param.enum
            if param.default is not None:
                prop["default"] = param.default
            properties[param.name] = prop

            if param.required:
                required.append(param.name)

        # 工具名称：将连字符转为下划线（OpenAI 要求）
        tool_name = skill.name.replace("-", "_")

        return {
            "type": "function",
            "function": {
                "name": tool_name,
                "description": description,
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": required,
                },
            },
        }

    @staticmethod
    def to_openai_tools(skills: List[SkillMetadata]) -> List[Dict[str, Any]]:
        """批量转换 SkillMetadata 为 OpenAI 工具定义列表"""
        tools = []
        for skill in skills:
            if skill.enabled and skill.fc_enabled and skill.parameters:
                tools.append(SkillConverter.to_openai_tool(skill))
        return tools

    @staticmethod
    def to_tool_metadata(skill: SkillMetadata) -> "ToolMetadata":
        """
        将 SkillMetadata 转换为 ToolMetadata（兼容现有 ToolRegistry）

        延迟导入避免循环依赖
        """
        from core.tools.config import ToolMetadata, ToolParameter

        parameters = [
            ToolParameter(
                name=p.name,
                type=p.type,
                description=p.description,
                required=p.required,
                default=p.default,
                enum=p.enum,
            )
            for p in skill.parameters
        ]

        tool_id = skill.name.replace("-", "_")

        return ToolMetadata(
            id=tool_id,
            name=skill.description[:50] if len(skill.description) > 50 else skill.description,
            description=skill.description,
            category=skill.category,
            parameters=parameters,
            data_source=skill.skill_type,
            is_online=True,
            timeout=30,
            icon=skill.icon,
            color=skill.color,
        )

    @staticmethod
    def from_tool_metadata(
        tool_metadata: "ToolMetadata",
        tool_id: Optional[str] = None,
    ) -> SkillMetadata:
        """
        从现有 ToolMetadata 转换为 SkillMetadata

        用于将现有内置工具升级为 Skill
        """
        from core.tools.config import ToolMetadata as TM

        parameters = [
            SkillParameter(
                name=p.name,
                type=p.type,
                description=p.description,
                required=p.required,
                default=p.default,
                enum=p.enum,
            )
            for p in tool_metadata.parameters
        ]

        actual_id = tool_id or tool_metadata.id
        skill_name = actual_id.replace("_", "-")

        return SkillMetadata(
            name=skill_name,
            description=tool_metadata.description,
            category=tool_metadata.category,
            parameters=parameters,
            icon=tool_metadata.icon,
            color=tool_metadata.color,
            implementation=PythonImplementation(
                type=ImplementationType.PYTHON,
                module="",  # 内置工具不需要指定模块
                function=actual_id,
            ),
            is_builtin=True,
            fc_enabled=True,
            enabled=True,
        )

