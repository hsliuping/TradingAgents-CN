"""
TradingAgents LazyLLM 配置模块

创建 Trading namespace，使用 TRADING_ 前缀的环境变量
"""

import os
import sys
from typing import Optional


# 添加 LazyLLM 到 path（如果是本地开发）
LAZYLLM_PATH = os.path.join(os.path.dirname(__file__), '..', '..', '..', '..', '..', 'LazyLLM')
if os.path.exists(LAZYLLM_PATH):
    sys.path.insert(0, os.path.abspath(LAZYLLM_PATH))

try:
    import lazyllm
    from lazyllm.configs import Config, Namespace
    LAZYLLM_AVAILABLE = True
except ImportError:
    LAZYLLM_AVAILABLE = False
    Config = None
    Namespace = None


class TradingNamespace:
    """
    Trading namespace 封装
    使用 TRADING_ 前缀的环境变量
    """
    
    def __init__(self):
        if not LAZYLLM_AVAILABLE:
            raise ImportError(
                "LazyLLM 未安装。请安装: pip install lazyllm 或从源码安装。"
            )
        self._namespace = Namespace('TRADING')
        self._config = None
    
    def __enter__(self):
        """进入 Trading namespace 上下文"""
        self._namespace.__enter__()
        return self
    
    def __exit__(self, exc_type, exc, tb):
        """退出 Trading namespace 上下文"""
        return self._namespace.__exit__(exc_type, exc, tb)
    
    @property
    def config(self):
        """获取 Trading 配置"""
        if self._config is None:
            self._config = Config('TRADING')
        return self._config
    
    def OnlineChatModule(self, *args, **kwargs):
        """在 Trading namespace 中创建 OnlineChatModule"""
        with self:
            return lazyllm.OnlineChatModule(*args, **kwargs)
    
    def AutoModel(self, *args, **kwargs):
        """在 Trading namespace 中创建 AutoModel"""
        with self:
            return lazyllm.AutoModel(*args, **kwargs)


# 全局 Trading namespace 实例
_trading_namespace: Optional[TradingNamespace] = None


def get_trading_namespace() -> TradingNamespace:
    """获取全局 Trading namespace 实例"""
    global _trading_namespace
    if _trading_namespace is None:
        _trading_namespace = TradingNamespace()
    return _trading_namespace


class TradingConfig:
    """
    TradingAgents 配置管理器
    
    支持的环境变量 (TRADING_ 前缀):
    - TRADING_QWEN_API_KEY: 阿里云 DashScope API Key
    - TRADING_DEEPSEEK_API_KEY: DeepSeek API Key
    - TRADING_ZHIPU_API_KEY: 智谱 API Key
    - TRADING_DEFAULT_SOURCE: 默认模型来源 (qwen, deepseek, zhipu, openai)
    - TRADING_DEFAULT_MODEL: 默认模型名称
    - TRADING_TEMPERATURE: 默认温度参数
    - TRADING_MAX_TOKENS: 默认最大 token 数
    """
    
    # 支持的模型供应商
    SUPPORTED_SOURCES = ['qwen', 'deepseek', 'zhipu', 'openai', 'kimi', 'doubao']
    
    # 默认模型映射
    DEFAULT_MODELS = {
        'qwen': 'qwen-plus',
        'deepseek': 'deepseek-chat',
        'zhipu': 'glm-4',
        'openai': 'gpt-3.5-turbo',
        'kimi': 'moonshot-v1-8k',
        'doubao': 'doubao-pro-32k',
    }
    
    # API Key 环境变量映射
    API_KEY_ENVS = {
        'qwen': 'TRADING_QWEN_API_KEY',
        'deepseek': 'TRADING_DEEPSEEK_API_KEY',
        'zhipu': 'TRADING_ZHIPU_API_KEY',
        'openai': 'TRADING_OPENAI_API_KEY',
        'kimi': 'TRADING_KIMI_API_KEY',
        'doubao': 'TRADING_DOUBAO_API_KEY',
    }
    
    # 备用环境变量（兼容原有配置）
    FALLBACK_API_KEY_ENVS = {
        'qwen': 'DASHSCOPE_API_KEY',
        'deepseek': 'DEEPSEEK_API_KEY',
        'zhipu': 'ZHIPU_API_KEY',
        'openai': 'OPENAI_API_KEY',
    }
    
    def __init__(self):
        self._lazyllm_config = None
    
    @property
    def lazyllm_config(self):
        """获取 LazyLLM 配置对象"""
        if self._lazyllm_config is None and LAZYLLM_AVAILABLE:
            self._lazyllm_config = Config('TRADING')
        return self._lazyllm_config
    
    def get_api_key(self, source: str) -> Optional[str]:
        """
        获取指定来源的 API Key
        
        优先级:
        1. TRADING_{SOURCE}_API_KEY
        2. 备用环境变量 (如 DASHSCOPE_API_KEY)
        """
        source = source.lower()
        
        # 尝试 TRADING_ 前缀的环境变量
        env_name = self.API_KEY_ENVS.get(source)
        if env_name:
            api_key = os.getenv(env_name)
            if api_key and self._is_valid_api_key(api_key):
                return api_key
        
        # 尝试备用环境变量
        fallback_env = self.FALLBACK_API_KEY_ENVS.get(source)
        if fallback_env:
            api_key = os.getenv(fallback_env)
            if api_key and self._is_valid_api_key(api_key):
                return api_key
        
        return None
    
    def _is_valid_api_key(self, key: str) -> bool:
        """验证 API Key 是否有效（排除占位符）"""
        if not key or len(key) <= 10:
            return False
        if key.startswith('your_') or key.startswith('your-'):
            return False
        if key.endswith('_here') or key.endswith('-here'):
            return False
        if '...' in key:
            return False
        return True
    
    @property
    def default_source(self) -> str:
        """获取默认模型来源"""
        source = os.getenv('TRADING_DEFAULT_SOURCE', '').lower()
        if source in self.SUPPORTED_SOURCES:
            return source
        
        # 自动检测可用的来源
        for src in self.SUPPORTED_SOURCES:
            if self.get_api_key(src):
                return src
        
        return 'qwen'  # 默认使用 qwen
    
    @property
    def default_model(self) -> str:
        """获取默认模型名称"""
        model = os.getenv('TRADING_DEFAULT_MODEL', '')
        if model:
            return model
        return self.DEFAULT_MODELS.get(self.default_source, 'qwen-plus')
    
    @property
    def temperature(self) -> float:
        """获取默认温度参数"""
        try:
            return float(os.getenv('TRADING_TEMPERATURE', '0.1'))
        except ValueError:
            return 0.1
    
    @property
    def max_tokens(self) -> Optional[int]:
        """获取默认最大 token 数"""
        max_tokens = os.getenv('TRADING_MAX_TOKENS', '')
        if max_tokens:
            try:
                return int(max_tokens)
            except ValueError:
                pass
        return None
    
    def get_config_summary(self) -> dict:
        """获取当前配置摘要"""
        return {
            'default_source': self.default_source,
            'default_model': self.default_model,
            'temperature': self.temperature,
            'max_tokens': self.max_tokens,
            'available_sources': [s for s in self.SUPPORTED_SOURCES if self.get_api_key(s)],
            'lazyllm_available': LAZYLLM_AVAILABLE,
        }


# 全局配置实例
trading_config = TradingConfig()


def setup_lazyllm_trading_config():
    """
    设置 LazyLLM 的 Trading namespace 配置
    
    将 TRADING_ 前缀的环境变量注册到 LazyLLM 配置系统
    """
    if not LAZYLLM_AVAILABLE:
        return False
    
    try:
        # 获取 Trading 配置
        config = Config('TRADING')
        
        # 注册支持的配置项
        for source in TradingConfig.SUPPORTED_SOURCES:
            key_name = f'{source}_api_key'
            if key_name.lower() not in config.get_all_configs():
                config.add(key_name, str, '', f'{source.upper()}_API_KEY',
                          description=f'The API key for {source}')
            
            model_name = f'{source}_model_name'
            if model_name.lower() not in config.get_all_configs():
                config.add(model_name, str, TradingConfig.DEFAULT_MODELS.get(source, ''),
                          f'{source.upper()}_MODEL_NAME',
                          description=f'The default model name for {source}')
        
        # 注册默认配置
        if 'default_source' not in config.get_all_configs():
            config.add('default_source', str, 'qwen', 'DEFAULT_SOURCE',
                      description='The default model source')
        
        if 'default_model' not in config.get_all_configs():
            config.add('default_model', str, 'qwen-plus', 'DEFAULT_MODEL',
                      description='The default model name')
        
        return True
    except Exception as e:
        print(f"Warning: Failed to setup LazyLLM trading config: {e}")
        return False


# 初始化时设置配置
if LAZYLLM_AVAILABLE:
    setup_lazyllm_trading_config()
