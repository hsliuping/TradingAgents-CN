"""
工具调用标准化器

处理不同 LLM 提供商之间工具调用格式的差异
"""

import json
from typing import Any, Callable, Dict, List, Optional

from .models import LLMProvider, ToolCall, ToolResult


class ToolCallNormalizer:
    """
    工具调用标准化器
    
    统一处理:
    1. 工具定义格式转换
    2. 工具调用结果转换
    3. 工具执行和结果包装
    """
    
    @staticmethod
    def normalize_tool_definition(
        func: Callable,
        name: Optional[str] = None,
        description: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        从函数创建标准化的工具定义
        
        Args:
            func: 工具函数
            name: 工具名称 (默认使用函数名)
            description: 工具描述 (默认使用函数文档字符串)
            
        Returns:
            OpenAI 格式的工具定义
        """
        import inspect
        
        tool_name = name or func.__name__
        tool_desc = description or func.__doc__ or ""
        
        # 从类型注解推断参数
        sig = inspect.signature(func)
        hints = func.__annotations__ if hasattr(func, '__annotations__') else {}
        
        properties = {}
        required = []
        
        for param_name, param in sig.parameters.items():
            if param_name in ('self', 'cls'):
                continue
            
            param_type = hints.get(param_name, str)
            json_type = ToolCallNormalizer._python_type_to_json(param_type)
            
            properties[param_name] = {
                "type": json_type,
                "description": f"参数 {param_name}"
            }
            
            if param.default == inspect.Parameter.empty:
                required.append(param_name)
        
        return {
            "type": "function",
            "function": {
                "name": tool_name,
                "description": tool_desc.strip(),
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": required
                }
            }
        }
    
    @staticmethod
    def _python_type_to_json(python_type) -> str:
        """Python 类型转 JSON Schema 类型"""
        type_map = {
            str: "string",
            int: "integer",
            float: "number",
            bool: "boolean",
            list: "array",
            dict: "object",
        }
        return type_map.get(python_type, "string")
    
    @staticmethod
    def execute_tool_call(
        tool_call: ToolCall,
        tools: Dict[str, Callable],
        **context
    ) -> ToolResult:
        """
        执行工具调用
        
        Args:
            tool_call: 工具调用对象
            tools: 可用工具字典 {name: callable}
            **context: 传递给工具的上下文参数
            
        Returns:
            工具执行结果
        """
        if tool_call.name not in tools:
            return ToolResult(
                tool_call_id=tool_call.id,
                name=tool_call.name,
                content=f"错误: 未找到工具 '{tool_call.name}'",
                is_error=True
            )
        
        try:
            func = tools[tool_call.name]
            # 合并参数
            kwargs = {**tool_call.arguments, **context}
            result = func(**kwargs)
            
            # 确保结果是字符串
            if not isinstance(result, str):
                result = json.dumps(result, ensure_ascii=False, default=str)
            
            return ToolResult(
                tool_call_id=tool_call.id,
                name=tool_call.name,
                content=result,
                is_error=False
            )
        except Exception as e:
            return ToolResult(
                tool_call_id=tool_call.id,
                name=tool_call.name,
                content=f"工具执行错误: {str(e)}",
                is_error=True
            )
    
    @staticmethod
    def tool_result_to_message(
        result: ToolResult,
        provider: LLMProvider
    ) -> Dict[str, Any]:
        """
        将工具结果转换为消息格式
        
        Args:
            result: 工具执行结果
            provider: LLM 提供商
            
        Returns:
            提供商特定的消息格式
        """
        if provider == LLMProvider.GOOGLE:
            return {
                "role": "user",
                "parts": [{
                    "function_response": {
                        "name": result.name,
                        "response": {"result": result.content}
                    }
                }]
            }
        else:
            # OpenAI 兼容格式
            return {
                "role": "tool",
                "tool_call_id": result.tool_call_id,
                "name": result.name,
                "content": result.content
            }

