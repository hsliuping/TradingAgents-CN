"""
TradingLLMAdapter - 将 LazyLLM 适配为 LangChain ChatOpenAI 接口

保持与 TradingAgents 现有 LLM 接口的兼容性
"""

import os
import time
from typing import Any, ClassVar, Dict, List, Optional, Union

from langchain_core.messages import BaseMessage, AIMessage, HumanMessage, SystemMessage
from langchain_core.outputs import ChatResult, ChatGeneration
from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_openai import ChatOpenAI

try:
    from .config import trading_config, LAZYLLM_AVAILABLE, TradingConfig
except ImportError:
    from config import trading_config, LAZYLLM_AVAILABLE, TradingConfig

# 导入日志模块
try:
    from tradingagents.utils.logging_manager import get_logger
    logger = get_logger('agents')
except ImportError:
    import logging
    logger = logging.getLogger(__name__)


# 模型来源到 base_url 的映射（类外部定义）
_SOURCE_BASE_URLS: Dict[str, str] = {
    'qwen': 'https://dashscope.aliyuncs.com/compatible-mode/v1',
    'deepseek': 'https://api.deepseek.com',
    'zhipu': 'https://open.bigmodel.cn/api/paas/v4',
    'openai': 'https://api.openai.com/v1',
    'kimi': 'https://api.moonshot.cn/v1',
    'doubao': 'https://ark.cn-beijing.volces.com/api/v3',
}


class TradingLLMAdapter(ChatOpenAI):
    """
    TradingAgents LazyLLM 适配器
    
    将 LazyLLM 的模型适配为 LangChain ChatOpenAI 接口，
    保持与 TradingAgents 现有代码的兼容性。
    
    特点:
    1. 使用 TRADING_ 前缀的环境变量
    2. 不传参数时自动从环境变量读取配置
    3. 完全兼容 LangChain ChatOpenAI 接口
    
    使用示例:
        # 自动配置
        llm = TradingLLMAdapter()
        response = llm.invoke("你好")
        
        # 显式指定参数
        llm = TradingLLMAdapter(
            source="qwen",
            model="qwen-max",
            temperature=0.7
        )
    """
    
    # 使用 ClassVar 注解类变量
    SOURCE_BASE_URLS: ClassVar[Dict[str, str]] = _SOURCE_BASE_URLS
    
    def __init__(
        self,
        source: Optional[str] = None,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        temperature: float = None,
        max_tokens: Optional[int] = None,
        **kwargs
    ):
        """
        初始化 TradingLLMAdapter
        
        Args:
            source: 模型来源 (qwen, deepseek, zhipu, openai, kimi, doubao)
            model: 模型名称
            api_key: API Key，如果不提供则从环境变量读取
            base_url: API 基础 URL，如果不提供则根据 source 自动设置
            temperature: 温度参数
            max_tokens: 最大 token 数
            **kwargs: 其他传递给 ChatOpenAI 的参数
        """
        # 解析来源（先保存到临时变量）
        _resolved_source = source or trading_config.default_source
        
        # 解析模型名称
        resolved_model = model or trading_config.default_model
        
        # 解析 API Key
        resolved_api_key = api_key or trading_config.get_api_key(_resolved_source)
        
        # 解析 base_url
        resolved_base_url = base_url or _SOURCE_BASE_URLS.get(_resolved_source)
        
        # 解析温度
        resolved_temperature = temperature if temperature is not None else trading_config.temperature
        
        # 解析 max_tokens
        resolved_max_tokens = max_tokens or trading_config.max_tokens
        
        # 记录初始化信息
        logger.info(f"🔍 [TradingLLMAdapter] 初始化")
        logger.info(f"   来源: {_resolved_source}")
        logger.info(f"   模型: {resolved_model}")
        logger.info(f"   Base URL: {resolved_base_url}")
        logger.info(f"   API Key: {'已设置' if resolved_api_key else '未设置'}")
        
        # 验证 API Key
        if not resolved_api_key:
            env_var = TradingConfig.API_KEY_ENVS.get(_resolved_source, f'TRADING_{_resolved_source.upper()}_API_KEY')
            raise ValueError(
                f"未找到 {_resolved_source} 的 API Key。\n"
                f"请设置环境变量 {env_var} 或在初始化时传入 api_key 参数。"
            )
        
        # 构建 ChatOpenAI 参数
        openai_kwargs = {
            "model": resolved_model,
            "temperature": resolved_temperature,
            **kwargs
        }
        
        if resolved_max_tokens:
            openai_kwargs["max_tokens"] = resolved_max_tokens
        
        # 根据 LangChain 版本使用不同的参数名
        try:
            openai_kwargs["api_key"] = resolved_api_key
            openai_kwargs["base_url"] = resolved_base_url
        except Exception:
            openai_kwargs["openai_api_key"] = resolved_api_key
            openai_kwargs["openai_api_base"] = resolved_base_url
        
        # 调用父类初始化
        super().__init__(**openai_kwargs)
        
        # 使用 object.__setattr__ 设置私有属性，避免 Pydantic 验证
        object.__setattr__(self, '_trading_source', _resolved_source)
        
        logger.info(f"✅ TradingLLMAdapter 初始化成功")
    
    @property
    def source(self) -> str:
        """获取模型来源"""
        return getattr(self, '_trading_source', 'unknown')
    
    def _generate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> ChatResult:
        """
        生成聊天响应，并记录 token 使用量
        """
        start_time = time.time()
        
        # 调用父类生成方法
        result = super()._generate(messages, stop, run_manager, **kwargs)
        
        # 记录使用情况
        elapsed = time.time() - start_time
        try:
            if hasattr(result, 'llm_output') and result.llm_output:
                usage = result.llm_output.get('token_usage', {})
                logger.info(
                    f"📊 Token使用 - Source: {self.source}, Model: {self.model_name}, "
                    f"提示: {usage.get('prompt_tokens', 'N/A')}, "
                    f"补全: {usage.get('completion_tokens', 'N/A')}, "
                    f"用时: {elapsed:.2f}s"
                )
        except Exception as e:
            logger.warning(f"⚠️ Token 统计记录失败: {e}")
        
        return result


def create_trading_llm(
    source: Optional[str] = None,
    model: Optional[str] = None,
    api_key: Optional[str] = None,
    temperature: float = None,
    max_tokens: Optional[int] = None,
    **kwargs
) -> TradingLLMAdapter:
    """
    创建 TradingLLMAdapter 的便捷函数
    
    Args:
        source: 模型来源
        model: 模型名称
        api_key: API Key
        temperature: 温度参数
        max_tokens: 最大 token 数
        **kwargs: 其他参数
    
    Returns:
        TradingLLMAdapter 实例
    
    示例:
        # 使用默认配置（从环境变量读取）
        llm = create_trading_llm()
        
        # 指定模型
        llm = create_trading_llm(source="qwen", model="qwen-max")
        
        # 指定 API Key
        llm = create_trading_llm(api_key="sk-xxx")
    """
    return TradingLLMAdapter(
        source=source,
        model=model,
        api_key=api_key,
        temperature=temperature,
        max_tokens=max_tokens,
        **kwargs
    )


# 为了向后兼容，提供与现有适配器相似的工厂函数
def create_lazyllm_openai_compatible_llm(
    provider: str = None,
    model: str = None,
    api_key: Optional[str] = None,
    temperature: float = 0.1,
    max_tokens: Optional[int] = None,
    **kwargs
) -> TradingLLMAdapter:
    """
    创建 LazyLLM OpenAI 兼容 LLM 实例的工厂函数
    
    这是一个向后兼容的函数，映射到 TradingLLMAdapter
    
    Args:
        provider: 提供商名称 (qwen, deepseek, zhipu, openai)
        model: 模型名称
        api_key: API Key
        temperature: 温度参数
        max_tokens: 最大 token 数
        **kwargs: 其他参数
    
    Returns:
        TradingLLMAdapter 实例
    """
    return create_trading_llm(
        source=provider,
        model=model,
        api_key=api_key,
        temperature=temperature,
        max_tokens=max_tokens,
        **kwargs
    )
