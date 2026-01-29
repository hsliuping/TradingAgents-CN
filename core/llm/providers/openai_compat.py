"""
OpenAI 兼容 API 适配器

支持所有兼容 OpenAI API 格式的提供商:
- OpenAI
- DeepSeek
- 通义千问 (DashScope)
- 智谱AI
- 硅基流动
- Ollama
- OpenRouter
"""

import json
import logging
from typing import Any, AsyncIterator, Dict, List, Optional

from openai import AsyncOpenAI, OpenAI

from ..models import (
    LLMConfig,
    LLMProvider,
    LLMResponse,
    Message,
    MessageRole,
    ToolCall,
)
from .base import BaseAdapter

logger = logging.getLogger(__name__)


class OpenAICompatAdapter(BaseAdapter):
    """OpenAI 兼容 API 适配器"""
    
    # 支持的提供商列表
    SUPPORTED_PROVIDERS = [
        LLMProvider.OPENAI,
        LLMProvider.DEEPSEEK,
        LLMProvider.DASHSCOPE,
        LLMProvider.ZHIPU,
        LLMProvider.SILICONFLOW,
        LLMProvider.OLLAMA,
        LLMProvider.OPENROUTER,
    ]
    
    def __init__(self, config: LLMConfig):
        super().__init__(config)
        self._sync_client: Optional[OpenAI] = None
        self._async_client: Optional[AsyncOpenAI] = None
    
    def initialize(self) -> None:
        """初始化 OpenAI 客户端"""
        # 🔥 检查 API key 是否存在
        api_key = self.config.api_key
        
        # 🔥 本地模型（Ollama）不需要 API Key，使用占位符
        if not api_key and self.config.provider == LLMProvider.OLLAMA:
            api_key = "ollama"  # 本地模型使用占位符，实际不会验证
        
        if not api_key:
            # 根据 provider 确定应该使用的环境变量名
            provider_env_map = {
                LLMProvider.OPENAI: "OPENAI_API_KEY",
                LLMProvider.DEEPSEEK: "DEEPSEEK_API_KEY",
                LLMProvider.DASHSCOPE: "DASHSCOPE_API_KEY",
                LLMProvider.ZHIPU: "ZHIPU_API_KEY",
                LLMProvider.SILICONFLOW: "SILICONFLOW_API_KEY",
                LLMProvider.OLLAMA: "OLLAMA_API_KEY",
                LLMProvider.OPENROUTER: "OPENROUTER_API_KEY",
            }
            expected_env_key = provider_env_map.get(self.config.provider, "API_KEY")
            raise ValueError(
                f"The api_key client option must be set either by passing api_key to the client "
                f"or by setting the {expected_env_key} environment variable. "
                f"Provider: {self.config.provider.value}, Model: {self.config.model}"
            )
        
        client_kwargs = {
            "api_key": api_key,
            "timeout": self.config.timeout,
        }
        
        if self.config.base_url:
            client_kwargs["base_url"] = self.config.base_url
        
        self._sync_client = OpenAI(**client_kwargs)
        self._async_client = AsyncOpenAI(**client_kwargs)
    
    def _convert_messages(self, messages: List[Message]) -> List[Dict[str, Any]]:
        """转换消息格式为 OpenAI 格式"""
        result = []
        for msg in messages:
            converted = {"role": msg.role, "content": msg.content or ""}
            
            if msg.name:
                converted["name"] = msg.name
            
            if msg.tool_calls:
                converted["tool_calls"] = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.name,
                            "arguments": json.dumps(tc.arguments, ensure_ascii=False)
                        }
                    }
                    for tc in msg.tool_calls
                ]
            
            if msg.tool_call_id:
                converted["tool_call_id"] = msg.tool_call_id
            
            result.append(converted)
        
        return result
    
    def _build_request_kwargs(
        self,
        messages: List[Message],
        tools: Optional[List[Dict[str, Any]]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """构建请求参数"""
        request_kwargs = {
            "model": self.config.model,
            "messages": self._convert_messages(messages),
            "temperature": kwargs.get("temperature", self.config.temperature),
        }
        
        if self.config.max_tokens:
            request_kwargs["max_tokens"] = self.config.max_tokens
        
        if tools:
            request_kwargs["tools"] = self.convert_tools_to_provider_format(tools)
            if self.config.tool_choice:
                request_kwargs["tool_choice"] = self.config.tool_choice
        
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
        response = self._sync_client.chat.completions.create(**request_kwargs)
        
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
        response = await self._async_client.chat.completions.create(**request_kwargs)
        
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
        request_kwargs["stream"] = True
        
        async for chunk in await self._async_client.chat.completions.create(**request_kwargs):
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
    
    def _parse_response(self, response) -> LLMResponse:
        """解析响应"""
        # 🔥 检查 choices 字段是否存在且不为空
        if not hasattr(response, 'choices') or response.choices is None:
            error_msg = f"LLM API 返回的响应中 choices 字段为 null。响应类型: {type(response).__name__}"
            if hasattr(response, 'model'):
                error_msg += f", 模型: {response.model}"
            if hasattr(response, 'id'):
                error_msg += f", 响应ID: {response.id}"
            logger.error(error_msg)
            raise ValueError(error_msg)
        
        if not response.choices or len(response.choices) == 0:
            error_msg = f"LLM API 返回的响应中 choices 字段为空列表。响应类型: {type(response).__name__}"
            if hasattr(response, 'model'):
                error_msg += f", 模型: {response.model}"
            if hasattr(response, 'id'):
                error_msg += f", 响应ID: {response.id}"
            logger.error(error_msg)
            raise ValueError(error_msg)
        
        choice = response.choices[0]
        
        # 🔥 检查 choice 是否有 message 属性
        if not hasattr(choice, 'message') or choice.message is None:
            error_msg = f"LLM API 返回的 choice 中 message 字段为 null。响应类型: {type(response).__name__}"
            if hasattr(response, 'model'):
                error_msg += f", 模型: {response.model}"
            logger.error(error_msg)
            raise ValueError(error_msg)
        
        message = choice.message

        tool_calls = []
        if hasattr(message, 'tool_calls') and message.tool_calls:
            for tc in message.tool_calls:
                # 🔥 修复：处理不同类型的 tool_call 对象
                if isinstance(tc, dict):
                    # 已经是字典，直接使用
                    tool_calls.append(ToolCall.from_openai_format(tc))
                elif isinstance(tc, str):
                    # 字符串类型，跳过（不应该出现，但做容错处理）
                    continue
                elif hasattr(tc, 'model_dump'):
                    # Pydantic 模型，调用 model_dump()
                    tool_calls.append(ToolCall.from_openai_format(tc.model_dump()))
                else:
                    # 其他类型，尝试转换为字典
                    try:
                        tool_calls.append(ToolCall.from_openai_format(dict(tc)))
                    except Exception:
                        # 转换失败，跳过
                        continue

        return LLMResponse(
            content=message.content if hasattr(message, 'content') else None,
            tool_calls=tool_calls,
            finish_reason=choice.finish_reason if hasattr(choice, 'finish_reason') else None,
            model=response.model if hasattr(response, 'model') else None,
            provider=self.config.provider,
            usage={
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
            } if hasattr(response, 'usage') and response.usage else None
        )

