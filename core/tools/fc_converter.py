"""
ToolMetadata → OpenAI Function Calling 格式转换器

将 ToolMetadata 转换为 OpenAI 兼容的工具定义，供 LLM Function Calling 使用。
与 SkillConverter 对齐，确保工具描述与 Skill 元数据一致。
"""

import re
from typing import Any, Dict, List

from .config import ToolMetadata, ToolParameter

# JSON Schema 类型映射
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

# OpenAI 工具名合法字符正则：^[a-zA-Z0-9_-]+$
_OPENAI_NAME_PATTERN = re.compile(r"[^a-zA-Z0-9_-]")


def sanitize_function_name(name: str) -> str:
    """将任意字符串清理成符合 OpenAI 工具名规范的字符串

    - 把非法字符（中文、空格、括号、点等）替换为下划线
    - 合并多余的连续下划线
    - 去掉首尾下划线
    - 如果清理后为空，返回 'tool'
    """
    if not name:
        return "tool"
    cleaned = _OPENAI_NAME_PATTERN.sub("_", str(name))
    cleaned = re.sub(r"_+", "_", cleaned).strip("_-")
    return cleaned or "tool"


def tool_metadata_to_openai(tool: ToolMetadata) -> Dict[str, Any]:
    """
    将 ToolMetadata 转换为 OpenAI Function Calling 工具定义格式

    Args:
        tool: 工具元数据

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
    # 构建描述：合并 description + when_to_use（与 SkillConverter 对齐）
    description = tool.description
    if tool.when_to_use:
        description += f"\n\n何时使用: {tool.when_to_use}"
    if tool.when_not_to_use:
        description += f"\n\n不宜使用: {tool.when_not_to_use}"

    # 构建参数的 JSON Schema
    properties: Dict[str, Any] = {}
    required: List[str] = []

    for param in tool.parameters:
        json_type = _TYPE_MAP.get(param.type.lower() if param.type else "string", "string")
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

    return {
        "type": "function",
        "function": {
            "name": sanitize_function_name(tool.id),  # OpenAI 要求 ^[a-zA-Z0-9_-]+$
            "description": description,
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required,
            },
        },
    }


def tool_metadata_list_to_openai(tools: List[ToolMetadata]) -> List[Dict[str, Any]]:
    """
    批量将 ToolMetadata 转换为 OpenAI 工具定义列表

    仅转换 fc_enabled=True 的工具（无参数工具也支持）
    """
    result = []
    for tool in tools:
        if tool.fc_enabled:
            result.append(tool_metadata_to_openai(tool))
    return result
