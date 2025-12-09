# tradingagents/agents/utils/embedding_provider.py
"""
Embedding 服务提供者

从数据库配置中获取支持 embedding 的厂商列表，并按优先级尝试使用可用的服务。

支持的厂商（通过 supported_features 包含 "embedding" 判断）：
- openai: text-embedding-3-small
- google: text-embedding-004
- dashscope: text-embedding-v3
- siliconflow: BAAI/bge-large-zh-v1.5
"""

import os
import logging
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass

logger = logging.getLogger("agents.utils.embedding")


@dataclass
class EmbeddingProviderConfig:
    """Embedding 提供者配置"""
    name: str
    display_name: str
    api_key: str
    base_url: str
    model: str
    is_active: bool
    priority: int = 0  # 优先级，数字越小优先级越高


# 默认的 embedding 模型映射
DEFAULT_EMBEDDING_MODELS = {
    "openai": "text-embedding-3-small",
    "google": "text-embedding-004",
    "dashscope": "text-embedding-v3",
    "siliconflow": "BAAI/bge-large-zh-v1.5",
    "alibaba": "text-embedding-v3",  # 阿里百练别名
}

# 提供者优先级（数字越小优先级越高）
PROVIDER_PRIORITY = {
    "dashscope": 1,      # 阿里百练优先（国内访问快）
    "siliconflow": 2,    # 硅基流动次之
    "google": 3,         # Google
    "openai": 4,         # OpenAI（可能需要翻墙）
}


class EmbeddingProviderManager:
    """
    Embedding 提供者管理器
    
    负责从数据库获取支持 embedding 的厂商配置，并提供按优先级尝试的能力
    """
    
    _instance = None
    _providers_cache: Optional[List[EmbeddingProviderConfig]] = None
    _cache_timestamp: float = 0
    _cache_ttl: float = 300  # 缓存 5 分钟
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        self._initialized = getattr(self, '_initialized', False)
        if not self._initialized:
            self._initialized = True
            logger.info("🔧 [EmbeddingProviderManager] 初始化完成")
    
    def get_available_providers(self, force_refresh: bool = False) -> List[EmbeddingProviderConfig]:
        """
        获取可用的 embedding 提供者列表（按优先级排序）
        
        Args:
            force_refresh: 是否强制刷新缓存
            
        Returns:
            按优先级排序的提供者配置列表
        """
        import time
        current_time = time.time()
        
        # 检查缓存是否有效
        if (not force_refresh and 
            self._providers_cache is not None and 
            current_time - self._cache_timestamp < self._cache_ttl):
            return self._providers_cache
        
        # 从数据库获取配置
        providers = self._fetch_providers_from_db()
        
        # 更新缓存
        self._providers_cache = providers
        self._cache_timestamp = current_time
        
        return providers
    
    def _fetch_providers_from_db(self) -> List[EmbeddingProviderConfig]:
        """从数据库获取支持 embedding 的提供者"""
        providers = []
        
        try:
            # 尝试从 MongoDB 获取
            from pymongo import MongoClient
            
            # 获取 MongoDB 连接字符串
            mongo_uri = os.getenv('MONGODB_CONNECTION_STRING', 'mongodb://localhost:27017')
            db_name = os.getenv('MONGODB_DATABASE_NAME', 'tradingagents')
            
            client = MongoClient(mongo_uri, serverSelectionTimeoutMS=5000)
            db = client[db_name]
            
            # 查询支持 embedding 的活跃厂商
            cursor = db.llm_providers.find({
                "is_active": True,
                "supported_features": "embedding"
            })
            
            for doc in cursor:
                # 检查是否有有效的 API Key
                api_key = doc.get('api_key')
                if not api_key or api_key.startswith('your_') or api_key == 'placeholder':
                    # 尝试从环境变量获取
                    api_key = self._get_env_api_key(doc.get('name', ''))
                
                if not api_key:
                    logger.debug(f"⚠️ 厂商 {doc.get('name')} 没有有效的 API Key，跳过")
                    continue
                
                name = doc.get('name', '')
                config = EmbeddingProviderConfig(
                    name=name,
                    display_name=doc.get('display_name', name),
                    api_key=api_key,
                    base_url=doc.get('default_base_url', ''),
                    model=DEFAULT_EMBEDDING_MODELS.get(name, 'text-embedding-3-small'),
                    is_active=True,
                    priority=PROVIDER_PRIORITY.get(name, 99)
                )
                providers.append(config)
            
            client.close()
            
        except Exception as e:
            logger.warning(f"⚠️ 从数据库获取 embedding 提供者失败: {e}")
        
        # 如果数据库没有配置，尝试从环境变量获取
        if not providers:
            providers = self._get_providers_from_env()
        
        # 按优先级排序
        providers.sort(key=lambda x: x.priority)

        logger.info(f"📋 [EmbeddingProviderManager] 可用的 embedding 提供者: {[p.name for p in providers]}")
        return providers

    def _get_providers_from_env(self) -> List[EmbeddingProviderConfig]:
        """从环境变量获取 embedding 提供者配置"""
        providers = []

        # 检查各个厂商的环境变量
        env_mappings = [
            ("dashscope", "DASHSCOPE_API_KEY", "https://dashscope.aliyuncs.com/compatible-mode/v1"),
            ("openai", "OPENAI_API_KEY", "https://api.openai.com/v1"),
            ("google", "GOOGLE_API_KEY", "https://generativelanguage.googleapis.com/v1beta"),
            ("siliconflow", "SILICONFLOW_API_KEY", "https://api.siliconflow.cn/v1"),
        ]

        for name, env_var, base_url in env_mappings:
            api_key = os.getenv(env_var)
            if api_key and not api_key.startswith('your_'):
                providers.append(EmbeddingProviderConfig(
                    name=name,
                    display_name=name.title(),
                    api_key=api_key,
                    base_url=base_url,
                    model=DEFAULT_EMBEDDING_MODELS.get(name, 'text-embedding-3-small'),
                    is_active=True,
                    priority=PROVIDER_PRIORITY.get(name, 99)
                ))
                logger.debug(f"✅ 从环境变量获取到 {name} 的 API Key")

        return providers

    def _get_env_api_key(self, provider_name: str) -> Optional[str]:
        """根据厂商名称获取环境变量中的 API Key"""
        env_var_mapping = {
            "openai": "OPENAI_API_KEY",
            "google": "GOOGLE_API_KEY",
            "dashscope": "DASHSCOPE_API_KEY",
            "alibaba": "DASHSCOPE_API_KEY",
            "siliconflow": "SILICONFLOW_API_KEY",
            "qianfan": "QIANFAN_API_KEY",
        }

        env_var = env_var_mapping.get(provider_name.lower())
        if env_var:
            key = os.getenv(env_var)
            if key and not key.startswith('your_'):
                return key
        return None

    def get_embedding(self, text: str, preferred_provider: Optional[str] = None) -> Tuple[Optional[List[float]], str]:
        """
        获取文本的 embedding 向量

        按优先级尝试各个提供者，直到成功或全部失败

        Args:
            text: 要获取 embedding 的文本
            preferred_provider: 首选的提供者名称（可选）

        Returns:
            (embedding_vector, provider_name) 或 (None, error_message)
        """
        providers = self.get_available_providers()

        if not providers:
            logger.warning("⚠️ 没有可用的 embedding 提供者")
            return None, "no_provider_available"

        # 如果指定了首选提供者，将其放到最前面
        if preferred_provider:
            providers = sorted(providers,
                             key=lambda x: (0 if x.name == preferred_provider else 1, x.priority))

        # 按优先级尝试各个提供者
        for provider in providers:
            try:
                embedding = self._call_provider(provider, text)
                if embedding:
                    logger.info(f"✅ 使用 {provider.display_name} 获取 embedding 成功")
                    return embedding, provider.name
            except Exception as e:
                logger.warning(f"⚠️ {provider.display_name} 获取 embedding 失败: {e}")
                continue

        return None, "all_providers_failed"

    def _call_provider(self, provider: EmbeddingProviderConfig, text: str) -> Optional[List[float]]:
        """调用指定提供者获取 embedding"""

        if provider.name in ("dashscope", "alibaba"):
            return self._call_dashscope(provider, text)
        elif provider.name == "openai":
            return self._call_openai(provider, text)
        elif provider.name == "google":
            return self._call_google(provider, text)
        elif provider.name == "siliconflow":
            return self._call_siliconflow(provider, text)
        else:
            # 默认尝试 OpenAI 兼容接口
            return self._call_openai_compatible(provider, text)

    def _call_dashscope(self, provider: EmbeddingProviderConfig, text: str) -> Optional[List[float]]:
        """调用阿里百练 embedding API"""
        try:
            import dashscope
            from dashscope import TextEmbedding

            dashscope.api_key = provider.api_key

            response = TextEmbedding.call(
                model=provider.model,
                input=text
            )

            if response.status_code == 200:
                return response.output['embeddings'][0]['embedding']
            else:
                logger.warning(f"DashScope API 错误: {response.code} - {response.message}")
                return None

        except Exception as e:
            logger.warning(f"DashScope 调用失败: {e}")
            raise

    def _call_openai(self, provider: EmbeddingProviderConfig, text: str) -> Optional[List[float]]:
        """调用 OpenAI embedding API"""
        return self._call_openai_compatible(provider, text)

    def _call_openai_compatible(self, provider: EmbeddingProviderConfig, text: str) -> Optional[List[float]]:
        """调用 OpenAI 兼容的 embedding API"""
        try:
            from openai import OpenAI

            client = OpenAI(
                api_key=provider.api_key,
                base_url=provider.base_url,
                timeout=30.0
            )

            response = client.embeddings.create(
                model=provider.model,
                input=text
            )

            return response.data[0].embedding

        except Exception as e:
            logger.warning(f"OpenAI 兼容 API 调用失败: {e}")
            raise

    def _call_google(self, provider: EmbeddingProviderConfig, text: str) -> Optional[List[float]]:
        """调用 Google embedding API"""
        try:
            import google.generativeai as genai

            genai.configure(api_key=provider.api_key)

            result = genai.embed_content(
                model=f"models/{provider.model}",
                content=text
            )

            return result['embedding']

        except Exception as e:
            logger.warning(f"Google API 调用失败: {e}")
            raise

    def _call_siliconflow(self, provider: EmbeddingProviderConfig, text: str) -> Optional[List[float]]:
        """调用硅基流动 embedding API (OpenAI 兼容)"""
        return self._call_openai_compatible(provider, text)


# 全局单例
_embedding_manager: Optional[EmbeddingProviderManager] = None


def get_embedding_manager() -> EmbeddingProviderManager:
    """获取 Embedding 管理器单例"""
    global _embedding_manager
    if _embedding_manager is None:
        _embedding_manager = EmbeddingProviderManager()
    return _embedding_manager


def get_embedding_with_fallback(text: str, preferred_provider: Optional[str] = None) -> Tuple[Optional[List[float]], str]:
    """
    获取文本的 embedding（带自动降级）

    便捷函数，自动处理降级逻辑

    Args:
        text: 要获取 embedding 的文本
        preferred_provider: 首选的提供者名称

    Returns:
        (embedding_vector, provider_name) 或 (None, error_message)
    """
    manager = get_embedding_manager()
    return manager.get_embedding(text, preferred_provider)

