"""
TradingAutoModel - 基于 LazyLLM AutoModel 的封装

不传参数时自动从环境变量读取配置
"""

import os
import sys
from typing import Any, Dict, List, Optional, Union

try:
    from .config import (
        trading_config, 
        get_trading_namespace, 
        LAZYLLM_AVAILABLE,
        TradingConfig
    )
except ImportError:
    from config import (
        trading_config, 
        get_trading_namespace, 
        LAZYLLM_AVAILABLE,
        TradingConfig
    )


class TradingAutoModel:
    """
    TradingAgents 专用的 AutoModel
    
    特点:
    1. 使用 TRADING_ 前缀的环境变量
    2. 不传参数时自动检测可用配置
    3. 支持与 LazyLLM AutoModel 相同的参数
    
    使用示例:
        # 自动从环境变量读取配置
        model = TradingAutoModel()
        response = model("分析一下贵州茅台的股票走势")
        
        # 显式指定模型
        model = TradingAutoModel(model="qwen-max", source="qwen")
        
        # 指定 API Key
        model = TradingAutoModel(api_key="sk-xxx")
    
    环境变量:
        - TRADING_QWEN_API_KEY: 阿里云 DashScope API Key
        - TRADING_DEFAULT_MODEL: 默认模型名称
        - TRADING_DEFAULT_SOURCE: 默认模型来源
    """
    
    def __init__(
        self,
        model: Optional[str] = None,
        source: Optional[str] = None,
        api_key: Optional[str] = None,
        stream: bool = True,
        return_trace: bool = False,
        **kwargs
    ):
        """
        初始化 TradingAutoModel
        
        Args:
            model: 模型名称，如 "qwen-plus", "deepseek-chat"
            source: 模型来源，如 "qwen", "deepseek", "openai"
            api_key: API Key，如果不提供则从环境变量读取
            stream: 是否流式输出
            return_trace: 是否返回追踪信息
            **kwargs: 其他传递给 LazyLLM 的参数
        """
        if not LAZYLLM_AVAILABLE:
            raise ImportError(
                "LazyLLM 未安装。请安装: pip install lazyllm 或从源码安装。"
            )
        
        import lazyllm
        
        # 解析参数
        self._source = source or trading_config.default_source
        self._model = model or trading_config.default_model
        self._api_key = api_key or trading_config.get_api_key(self._source)
        self._stream = stream
        self._return_trace = return_trace
        self._kwargs = kwargs
        
        # 验证配置
        if not self._api_key:
            env_var = TradingConfig.API_KEY_ENVS.get(self._source, f'TRADING_{self._source.upper()}_API_KEY')
            raise ValueError(
                f"未找到 {self._source} 的 API Key。\n"
                f"请设置环境变量 {env_var} 或在初始化时传入 api_key 参数。"
            )
        
        # 创建底层模型
        self._llm = self._create_model()
    
    def _create_model(self):
        """创建底层 LazyLLM 模型"""
        import lazyllm
        from lazyllm.configs import Config
        
        # 在 Trading namespace 中创建模型
        # 这样可以使用 TRADING_ 前缀的环境变量
        ns = get_trading_namespace()
        
        with ns:
            # 设置 API Key 到 LazyLLM 配置
            # 注意：这里需要动态设置，因为 LazyLLM 使用配置系统
            api_key_config_name = f'{self._source}_api_key'
            
            # 创建 OnlineChatModule
            # 不使用 AutoModel，因为我们已经明确知道是在线模型
            try:
                model = lazyllm.OnlineChatModule(
                    model=self._model,
                    source=self._source,
                    api_key=self._api_key,
                    stream=self._stream,
                    return_trace=self._return_trace,
                    **self._kwargs
                )
                return model
            except Exception as e:
                # 如果失败，尝试使用 AutoModel
                try:
                    return lazyllm.AutoModel(
                        model=self._model,
                        source=self._source,
                        **self._kwargs
                    )
                except Exception as e2:
                    raise RuntimeError(
                        f"创建模型失败: {e}\n"
                        f"AutoModel 也失败: {e2}"
                    ) from e
    
    def __call__(
        self,
        query: str,
        *,
        history: Optional[List[List[str]]] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        **kwargs
    ) -> str:
        """
        调用模型进行推理
        
        Args:
            query: 用户输入
            history: 对话历史，格式 [[user1, assistant1], [user2, assistant2], ...]
            tools: 工具定义（如果模型支持 function calling）
            **kwargs: 其他参数
        
        Returns:
            模型输出文本
        """
        call_kwargs = {}
        if history:
            call_kwargs['llm_chat_history'] = history
        if tools:
            call_kwargs['tools'] = tools
        call_kwargs.update(kwargs)
        
        result = self._llm(query, **call_kwargs)
        
        # 处理返回值
        if isinstance(result, str):
            return result
        elif hasattr(result, 'content'):
            return result.content
        elif isinstance(result, dict):
            return result.get('content', str(result))
        else:
            return str(result)
    
    def invoke(self, query: str, **kwargs) -> str:
        """LangChain 兼容的调用方法"""
        return self(query, **kwargs)
    
    @property
    def model_name(self) -> str:
        """获取模型名称"""
        return self._model
    
    @property
    def source(self) -> str:
        """获取模型来源"""
        return self._source
    
    def get_info(self) -> dict:
        """获取模型信息"""
        return {
            'model': self._model,
            'source': self._source,
            'stream': self._stream,
            'api_key_set': bool(self._api_key),
        }
    
    def __repr__(self) -> str:
        return f"TradingAutoModel(model='{self._model}', source='{self._source}')"


def create_trading_automodel(
    model: Optional[str] = None,
    source: Optional[str] = None,
    api_key: Optional[str] = None,
    **kwargs
) -> TradingAutoModel:
    """
    创建 TradingAutoModel 的便捷函数
    
    Args:
        model: 模型名称
        source: 模型来源
        api_key: API Key
        **kwargs: 其他参数
    
    Returns:
        TradingAutoModel 实例
    """
    return TradingAutoModel(
        model=model,
        source=source,
        api_key=api_key,
        **kwargs
    )
