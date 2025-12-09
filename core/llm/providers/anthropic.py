"""
Anthropic Claude 适配器

处理 Anthropic Claude 特有的 API 格式和工具调用方式
"""

import json
from typing import Any, AsyncIterator, Dict, List, Optional

from ..models import (
    LLMConfig,
    LLMProvider,
    LLMResponse,
    Message,
    MessageRole,
    ToolCall,
)
from .base import BaseAdapter


class AnthropicAdapter(BaseAdapter):
    """Anthropic Claude 适配器"""
    
    SUPPORTED_PROVIDERS = [LLMProvider.ANTHROPIC]
    
    def __init__(self, config: LLMConfig):
        super().__init__(config)
        self._sync_client = None
        self._async_client = None
    
    def initialize(self) -> None:
        """初始化 Anthropic 客户端"""
        try:
            from anthropic import Anthropic, AsyncAnthropic
        except ImportError:
            raise ImportError(
                "请安装 anthropic 包: pip install anthropic"
            )
        
        self._sync_client = Anthropic(api_key=self.config.api_key)
        self._async_client = AsyncAnthropic(api_key=self.config.api_key)
    
    def _convert_messages(self, messages: List[Message]) -> tuple[List[Dict[str, Any]], Optional[str]]:
        """
        转换消息格式为 Anthropic 格式
        
        Returns:
            (messages, system_prompt): Anthropic 格式的消息和系统提示词
        """
        result = []
        system_prompt = None
        
        for msg in messages:
            # 系统消息单独处理
            if msg.role == MessageRole.SYSTEM:
                system_prompt = msg.content
                continue
            
            # 工具结果消息
            if msg.role == MessageRole.TOOL:
                result.append({
                    "role": "user",
                    "content": [{
                        "type": "tool_result",
                        "tool_use_id": msg.tool_call_id,
                        "content": msg.content or ""
                    }]
                })
                continue
            
            # 普通消息
            role = "user" if msg.role == MessageRole.USER else "assistant"
            
            # 处理带工具调用的助手消息
            if msg.tool_calls:
                content = []
                if msg.content:
                    content.append({"type": "text", "text": msg.content})
                for tc in msg.tool_calls:
                    content.append({
                        "type": "tool_use",
                        "id": tc.id,
                        "name": tc.name,
                        "input": tc.arguments
                    })
                result.append({"role": role, "content": content})
            else:
                result.append({"role": role, "content": msg.content or ""})
        
        return result, system_prompt
    
    def convert_tools_to_provider_format(
        self, 
        tools: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """转换工具格式为 Anthropic 格式"""
        anthropic_tools = []
        
        for tool in tools:
            if tool.get("type") == "function":
                func = tool.get("function", {})
                anthropic_tools.append({
                    "name": func.get("name"),
                    "description": func.get("description", ""),
                    "input_schema": func.get("parameters", {"type": "object", "properties": {}})
                })
        
        return anthropic_tools
    
    def _build_request_kwargs(
        self,
        messages: List[Message],
        tools: Optional[List[Dict[str, Any]]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """构建请求参数"""
        converted_messages, system_prompt = self._convert_messages(messages)
        
        request_kwargs = {
            "model": self.config.model,
            "messages": converted_messages,
            "max_tokens": self.config.max_tokens or 4096,
        }
        
        if system_prompt:
            request_kwargs["system"] = system_prompt
        
        if "temperature" in kwargs or self.config.temperature:
            request_kwargs["temperature"] = kwargs.get("temperature", self.config.temperature)
        
        if tools:
            request_kwargs["tools"] = self.convert_tools_to_provider_format(tools)
        
        return request_kwargs
    
    def chat(
        self,
        messages: List[Message],
        tools: Optional[List[Dict[str, Any]]] = None,
        **kwargs
    ) -> LLMResponse:
        """同步聊天"""
        if not self._sync_client:
            self.initialize()

        request_kwargs = self._build_request_kwargs(messages, tools, **kwargs)
        response = self._sync_client.messages.create(**request_kwargs)

        return self._parse_response(response)

    async def achat(
        self,
        messages: List[Message],
        tools: Optional[List[Dict[str, Any]]] = None,
        **kwargs
    ) -> LLMResponse:
        """异步聊天"""
        if not self._async_client:
            self.initialize()

        request_kwargs = self._build_request_kwargs(messages, tools, **kwargs)
        response = await self._async_client.messages.create(**request_kwargs)

        return self._parse_response(response)

    async def astream(
        self,
        messages: List[Message],
        tools: Optional[List[Dict[str, Any]]] = None,
        **kwargs
    ) -> AsyncIterator[str]:
        """异步流式输出"""
        if not self._async_client:
            self.initialize()

        request_kwargs = self._build_request_kwargs(messages, tools, **kwargs)

        async with self._async_client.messages.stream(**request_kwargs) as stream:
            async for text in stream.text_stream:
                yield text

    def _parse_response(self, response) -> LLMResponse:
        """解析 Anthropic 响应"""
        content = None
        tool_calls = []

        for block in response.content:
            if block.type == "text":
                content = block.text
            elif block.type == "tool_use":
                tool_calls.append(ToolCall(
                    id=block.id,
                    name=block.name,
                    arguments=block.input if isinstance(block.input, dict) else {}
                ))

        # 计算 token 使用量
        usage = None
        if hasattr(response, 'usage') and response.usage:
            usage = {
                "prompt_tokens": response.usage.input_tokens,
                "completion_tokens": response.usage.output_tokens,
                "total_tokens": response.usage.input_tokens + response.usage.output_tokens,
            }

        return LLMResponse(
            content=content,
            tool_calls=tool_calls,
            finish_reason=response.stop_reason,
            model=response.model,
            provider=LLMProvider.ANTHROPIC,
            usage=usage
        )

