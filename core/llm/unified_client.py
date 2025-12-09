"""
统一 LLM 客户端

提供统一的接口调用各种 LLM 提供商
"""

from typing import Any, AsyncIterator, Callable, Dict, List, Optional

from .models import LLMConfig, LLMProvider, LLMResponse, Message, ToolCall, ToolResult
from .providers.base import BaseAdapter
from .providers.openai_compat import OpenAICompatAdapter
from .providers.google import GoogleAdapter
from .providers.anthropic import AnthropicAdapter
from .tool_normalizer import ToolCallNormalizer


class UnifiedLLMClient:
    """
    统一 LLM 客户端
    
    自动选择合适的适配器，提供统一的调用接口
    
    用法:
        client = UnifiedLLMClient.from_config(config)
        response = client.chat(messages)
        
        # 或使用便捷方法
        client = UnifiedLLMClient.from_provider("deepseek")
    """
    
    # 提供商到适配器的映射
    ADAPTER_MAP = {
        LLMProvider.OPENAI: OpenAICompatAdapter,
        LLMProvider.DEEPSEEK: OpenAICompatAdapter,
        LLMProvider.DASHSCOPE: OpenAICompatAdapter,
        LLMProvider.ZHIPU: OpenAICompatAdapter,
        LLMProvider.SILICONFLOW: OpenAICompatAdapter,
        LLMProvider.OLLAMA: OpenAICompatAdapter,
        LLMProvider.OPENROUTER: OpenAICompatAdapter,
        LLMProvider.GOOGLE: GoogleAdapter,
        LLMProvider.ANTHROPIC: AnthropicAdapter,
    }
    
    def __init__(self, adapter: BaseAdapter):
        self._adapter = adapter
        self._tools: Dict[str, Callable] = {}
    
    @classmethod
    def from_config(cls, config: LLMConfig) -> "UnifiedLLMClient":
        """从配置创建客户端"""
        adapter_class = cls.ADAPTER_MAP.get(config.provider)
        if not adapter_class:
            raise ValueError(f"不支持的提供商: {config.provider}")
        
        adapter = adapter_class(config)
        adapter.initialize()
        return cls(adapter)
    
    @classmethod
    def from_provider(
        cls,
        provider: str,
        model: Optional[str] = None,
        **kwargs
    ) -> "UnifiedLLMClient":
        """
        从提供商名称创建客户端 (自动从环境变量读取配置)
        
        Args:
            provider: 提供商名称 (deepseek, dashscope, google, etc.)
            model: 模型名称 (可选，使用默认值)
            **kwargs: 其他配置参数
        """
        provider_enum = LLMProvider(provider.lower())
        config = LLMConfig.from_env(provider_enum)
        
        if model:
            config.model = model
        
        for key, value in kwargs.items():
            if hasattr(config, key):
                setattr(config, key, value)
        
        return cls.from_config(config)
    
    def register_tool(
        self,
        func: Callable,
        name: Optional[str] = None,
        description: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        注册工具函数
        
        Args:
            func: 工具函数
            name: 工具名称
            description: 工具描述
            
        Returns:
            工具定义 (可用于 chat 调用)
        """
        tool_def = ToolCallNormalizer.normalize_tool_definition(func, name, description)
        tool_name = tool_def["function"]["name"]
        self._tools[tool_name] = func
        return tool_def
    
    def chat(
        self,
        messages: List[Message],
        tools: Optional[List[Dict[str, Any]]] = None,
        auto_execute_tools: bool = False,
        max_tool_rounds: int = 5,
        **kwargs
    ) -> LLMResponse:
        """
        同步聊天
        
        Args:
            messages: 消息列表
            tools: 工具定义列表
            auto_execute_tools: 是否自动执行工具调用
            max_tool_rounds: 最大工具调用轮次
            **kwargs: 其他参数
        """
        response = self._adapter.chat(messages, tools, **kwargs)
        
        if auto_execute_tools and response.has_tool_calls:
            return self._execute_tool_loop(
                messages, tools, response, max_tool_rounds, **kwargs
            )
        
        return response
    
    async def achat(
        self,
        messages: List[Message],
        tools: Optional[List[Dict[str, Any]]] = None,
        auto_execute_tools: bool = False,
        max_tool_rounds: int = 5,
        **kwargs
    ) -> LLMResponse:
        """异步聊天"""
        response = await self._adapter.achat(messages, tools, **kwargs)
        
        if auto_execute_tools and response.has_tool_calls:
            return await self._aexecute_tool_loop(
                messages, tools, response, max_tool_rounds, **kwargs
            )
        
        return response
    
    async def astream(
        self,
        messages: List[Message],
        tools: Optional[List[Dict[str, Any]]] = None,
        **kwargs
    ) -> AsyncIterator[str]:
        """异步流式输出"""
        async for chunk in self._adapter.astream(messages, tools, **kwargs):
            yield chunk
    
    def _execute_tool_loop(
        self,
        messages: List[Message],
        tools: List[Dict[str, Any]],
        response: LLMResponse,
        max_rounds: int,
        **kwargs
    ) -> LLMResponse:
        """执行工具调用循环"""
        current_messages = messages.copy()
        current_response = response
        rounds = 0
        
        while current_response.has_tool_calls and rounds < max_rounds:
            # 添加助手消息
            current_messages.append(current_response.to_message())
            
            # 执行所有工具调用
            for tool_call in current_response.tool_calls:
                result = ToolCallNormalizer.execute_tool_call(
                    tool_call, self._tools
                )
                # 添加工具结果消息
                current_messages.append(Message(
                    role="tool",
                    content=result.content,
                    tool_call_id=result.tool_call_id,
                    name=result.name
                ))
            
            # 继续对话
            current_response = self._adapter.chat(current_messages, tools, **kwargs)
            rounds += 1
        
        return current_response
    
    @property
    def provider(self) -> LLMProvider:
        """当前提供商"""
        return self._adapter.config.provider
    
    @property
    def model(self) -> str:
        """当前模型"""
        return self._adapter.config.model

