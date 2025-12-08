"""
Google Generative AI 适配器

处理 Google 特有的 API 格式和工具调用方式
"""

from typing import Any, AsyncIterator, Dict, List, Optional
import google.generativeai as genai
from google.generativeai.types import content_types

from ..models import (
    LLMConfig,
    LLMProvider,
    LLMResponse,
    Message,
    MessageRole,
    ToolCall,
)
from .base import BaseAdapter


class GoogleAdapter(BaseAdapter):
    """Google Generative AI 适配器"""
    
    SUPPORTED_PROVIDERS = [LLMProvider.GOOGLE]
    
    def __init__(self, config: LLMConfig):
        super().__init__(config)
        self._model = None
    
    def initialize(self) -> None:
        """初始化 Google AI 客户端"""
        genai.configure(api_key=self.config.api_key)
        self._model = genai.GenerativeModel(self.config.model)
    
    def _convert_messages(self, messages: List[Message]) -> List[Dict[str, Any]]:
        """转换消息格式为 Google 格式"""
        result = []
        system_instruction = None
        
        for msg in messages:
            if msg.role == MessageRole.SYSTEM:
                system_instruction = msg.content
                continue
            
            role = "user" if msg.role == MessageRole.USER else "model"
            
            parts = []
            if msg.content:
                parts.append({"text": msg.content})
            
            # 处理工具调用结果
            if msg.role == MessageRole.TOOL and msg.tool_call_id:
                parts.append({
                    "function_response": {
                        "name": msg.name or "unknown",
                        "response": {"result": msg.content}
                    }
                })
            
            # 处理工具调用
            if msg.tool_calls:
                for tc in msg.tool_calls:
                    parts.append({
                        "function_call": {
                            "name": tc.name,
                            "args": tc.arguments
                        }
                    })
            
            if parts:
                result.append({"role": role, "parts": parts})
        
        return result, system_instruction
    
    def convert_tools_to_provider_format(
        self, 
        tools: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """转换工具格式为 Google 格式"""
        google_tools = []
        
        for tool in tools:
            if tool.get("type") == "function":
                func = tool.get("function", {})
                google_tools.append({
                    "name": func.get("name"),
                    "description": func.get("description", ""),
                    "parameters": func.get("parameters", {})
                })
        
        return [{"function_declarations": google_tools}] if google_tools else []
    
    def chat(
        self,
        messages: List[Message],
        tools: Optional[List[Dict[str, Any]]] = None,
        **kwargs
    ) -> LLMResponse:
        """同步聊天"""
        if not self._model:
            self.initialize()
        
        contents, system_instruction = self._convert_messages(messages)
        
        generation_config = {
            "temperature": kwargs.get("temperature", self.config.temperature),
        }
        if self.config.max_tokens:
            generation_config["max_output_tokens"] = self.config.max_tokens
        
        # 创建带系统指令的模型实例
        model = self._model
        if system_instruction:
            model = genai.GenerativeModel(
                self.config.model,
                system_instruction=system_instruction
            )
        
        # 准备工具
        google_tools = None
        if tools:
            google_tools = self.convert_tools_to_provider_format(tools)
        
        response = model.generate_content(
            contents,
            generation_config=generation_config,
            tools=google_tools,
        )
        
        return self._parse_response(response)
    
    async def achat(
        self,
        messages: List[Message],
        tools: Optional[List[Dict[str, Any]]] = None,
        **kwargs
    ) -> LLMResponse:
        """异步聊天"""
        if not self._model:
            self.initialize()
        
        contents, system_instruction = self._convert_messages(messages)
        
        generation_config = {
            "temperature": kwargs.get("temperature", self.config.temperature),
        }
        if self.config.max_tokens:
            generation_config["max_output_tokens"] = self.config.max_tokens
        
        model = self._model
        if system_instruction:
            model = genai.GenerativeModel(
                self.config.model,
                system_instruction=system_instruction
            )
        
        google_tools = None
        if tools:
            google_tools = self.convert_tools_to_provider_format(tools)
        
        response = await model.generate_content_async(
            contents,
            generation_config=generation_config,
            tools=google_tools,
        )
        
        return self._parse_response(response)
    
    async def astream(
        self,
        messages: List[Message],
        tools: Optional[List[Dict[str, Any]]] = None,
        **kwargs
    ) -> AsyncIterator[str]:
        """异步流式输出"""
        # Google API 的流式实现
        # 注意: 需要根据实际 API 调整
        response = await self.achat(messages, tools, **kwargs)
        if response.content:
            yield response.content
    
    def _parse_response(self, response) -> LLMResponse:
        """解析 Google 响应"""
        content = None
        tool_calls = []
        
        if response.candidates:
            candidate = response.candidates[0]
            parts = candidate.content.parts
            
            for part in parts:
                if hasattr(part, 'text') and part.text:
                    content = part.text
                elif hasattr(part, 'function_call'):
                    fc = part.function_call
                    tool_calls.append(ToolCall(
                        id=f"call_{hash(fc.name)}",
                        name=fc.name,
                        arguments=dict(fc.args) if fc.args else {}
                    ))
        
        return LLMResponse(
            content=content,
            tool_calls=tool_calls,
            finish_reason=response.candidates[0].finish_reason.name if response.candidates else None,
            model=self.config.model,
            provider=LLMProvider.GOOGLE,
        )

