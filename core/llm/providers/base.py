"""
LLM 适配器基类
"""

from abc import ABC, abstractmethod
from typing import Any, AsyncIterator, Dict, List, Optional

from ..models import LLMConfig, LLMResponse, Message, ToolCall


class BaseAdapter(ABC):
    """
    LLM 适配器基类
    
    所有提供商适配器都需要继承此类并实现相应方法
    """
    
    def __init__(self, config: LLMConfig):
        self.config = config
        self._client = None
    
    @abstractmethod
    def initialize(self) -> None:
        """初始化客户端连接"""
        pass
    
    @abstractmethod
    def chat(
        self,
        messages: List[Message],
        tools: Optional[List[Dict[str, Any]]] = None,
        **kwargs
    ) -> LLMResponse:
        """
        同步聊天接口
        
        Args:
            messages: 消息列表
            tools: 可用工具定义列表
            **kwargs: 其他参数
            
        Returns:
            LLMResponse: 统一响应格式
        """
        pass
    
    @abstractmethod
    async def achat(
        self,
        messages: List[Message],
        tools: Optional[List[Dict[str, Any]]] = None,
        **kwargs
    ) -> LLMResponse:
        """
        异步聊天接口
        
        Args:
            messages: 消息列表
            tools: 可用工具定义列表
            **kwargs: 其他参数
            
        Returns:
            LLMResponse: 统一响应格式
        """
        pass
    
    @abstractmethod
    async def astream(
        self,
        messages: List[Message],
        tools: Optional[List[Dict[str, Any]]] = None,
        **kwargs
    ) -> AsyncIterator[str]:
        """
        异步流式输出接口
        
        Args:
            messages: 消息列表
            tools: 可用工具定义列表
            **kwargs: 其他参数
            
        Yields:
            str: 流式输出的文本片段
        """
        pass
    
    def convert_tools_to_provider_format(
        self, 
        tools: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        将统一工具格式转换为提供商特定格式
        
        默认实现返回 OpenAI 格式，子类可覆盖
        
        Args:
            tools: 统一工具定义列表
            
        Returns:
            转换后的工具定义列表
        """
        return tools
    
    def convert_tool_calls_from_response(
        self, 
        raw_tool_calls: Any
    ) -> List[ToolCall]:
        """
        从提供商响应中提取并转换工具调用
        
        Args:
            raw_tool_calls: 原始工具调用数据
            
        Returns:
            标准化的工具调用列表
        """
        return []
    
    def validate_config(self) -> bool:
        """
        验证配置是否有效
        
        Returns:
            bool: 配置是否有效
        """
        if not self.config.api_key:
            return False
        if not self.config.model:
            return False
        return True
    
    @property
    def provider_name(self) -> str:
        """提供商名称"""
        return self.config.provider.value
    
    @property
    def model_name(self) -> str:
        """模型名称"""
        return self.config.model

