"""
Text Embedding 管理器 v2.0

支持多种 Embedding 提供商：
- DashScope (阿里云通义千问)
- OpenAI
- DeepSeek
- Google
- Qianfan (百度千帆)
- Ollama (本地模型)
- LocalAI (本地模型)

特性：
- 自动降级（主服务失败时切换到备用服务）
- 从数据库配置读取 API Key
- 支持长文本智能截断
- 统一的接口
- 支持本地模型（无需 API Key）
"""

import os
import logging
from typing import List, Optional, Tuple, Dict, Any

logger = logging.getLogger(__name__)


class EmbeddingManager:
    """
    Text Embedding 管理器
    
    负责调用各种 Embedding API 将文本转换为向量
    """
    
    def __init__(self, db=None):
        """
        初始化 Embedding 管理器
        
        Args:
            db: MongoDB 数据库连接（用于读取配置）
        """
        self.db = db
        self._providers = []
        self._primary_provider = None
        self._fallback_providers = []
        
        # 初始化提供商
        self._init_providers()
    
    def _init_providers(self):
        """从数据库或环境变量初始化 Embedding 提供商"""
        # 🔥 优先从数据库读取配置
        if self.db is not None:
            try:
                self._init_from_database()
                if self._providers:
                    logger.info(f"✅ 从数据库加载了 {len(self._providers)} 个 Embedding 提供商")
                    return
            except Exception as e:
                logger.warning(f"⚠️ 从数据库加载 Embedding 配置失败: {e}")
        
        # 降级：从环境变量初始化
        self._init_from_env()
    
    def _init_from_database(self):
        """从数据库读取 Embedding 配置"""
        if self.db is None:
            return
        
        try:
            # 🔥 检查是否是异步数据库（AsyncIOMotorDatabase）
            # 如果是异步数据库，需要使用同步方式查询（通过 get_mongo_db_sync）
            from motor.motor_asyncio import AsyncIOMotorDatabase
            from pymongo.database import Database
            
            if isinstance(self.db, AsyncIOMotorDatabase):
                # 异步数据库：使用同步客户端查询
                from app.core.database import get_mongo_db_sync
                sync_db = get_mongo_db_sync()
                providers_collection = sync_db.llm_providers
                system_configs_collection = sync_db.system_configs
            else:
                # 同步数据库：直接使用
                providers_collection = self.db.llm_providers
                system_configs_collection = self.db.system_configs
            
            # 🔥 新增：优先从系统配置读取默认 Embedding 模型
            default_embedding_model = None
            try:
                system_config = system_configs_collection.find_one(
                    {"is_active": True},
                    sort=[("version", -1)]
                )
                if system_config and system_config.get("system_settings"):
                    default_embedding_model = system_config["system_settings"].get("default_embedding_model")
                    if default_embedding_model:
                        logger.info(f"📋 从系统配置读取默认 Embedding 模型: {default_embedding_model}")
            except Exception as e:
                logger.debug(f"⚠️ 读取系统配置失败: {e}")
            
            # 查询支持 embedding 的厂商
            # 🔥 修复：使用 supported_features 数组检查是否包含 "embedding"
            # 🔥 修复：字段名是 is_active 而不是 enabled
            cursor = providers_collection.find({
                "supported_features": {"$in": ["embedding"]},  # 检查 supported_features 数组是否包含 "embedding"
                "is_active": True
            }).sort("priority", 1)  # 按优先级排序
            
            # 🔥 修复：将游标转换为列表（支持同步和异步游标）
            if isinstance(self.db, AsyncIOMotorDatabase):
                # 异步游标：需要同步执行（这里使用同步客户端，所以已经是同步游标）
                provider_docs = list(cursor)
            else:
                # 同步游标：直接转换为列表
                provider_docs = list(cursor)
            
            # 🔥 如果配置了默认 Embedding 模型，解析并优先使用
            preferred_provider_name = None
            preferred_model = None
            if default_embedding_model and ":" in default_embedding_model:
                parts = default_embedding_model.split(":", 1)
                preferred_provider_name = parts[0].lower()
                preferred_model = parts[1]
                logger.info(f"🎯 优先使用系统配置的 Embedding 模型: {preferred_provider_name}:{preferred_model}")
            
            for provider_doc in provider_docs:
                provider_name = provider_doc.get("name", "").lower()
                api_key = provider_doc.get("api_key", "")
                base_url = provider_doc.get("default_base_url") or provider_doc.get("base_url", "")
                embedding_model = provider_doc.get("embedding_model", "")
                
                if not api_key:
                    logger.debug(f"⚠️ {provider_name} 未配置 API Key，跳过")
                    continue
                
                # 🔥 如果系统配置了该厂商的模型，优先使用系统配置
                if preferred_provider_name == provider_name and preferred_model:
                    embedding_model = preferred_model
                    logger.info(f"✅ 使用系统配置的 Embedding 模型: {provider_name}:{embedding_model}")
                # 🔥 如果没有配置 embedding_model，使用默认模型
                elif not embedding_model:
                    # 根据提供商设置默认模型
                    default_models = {
                        "dashscope": "text-embedding-v3",
                        "openai": "text-embedding-3-small",
                        "deepseek": "text-embedding-v3",
                    }
                    embedding_model = default_models.get(provider_name, "text-embedding-3-small")
                    logger.debug(f"📝 {provider_name} 未配置 embedding_model，使用默认模型: {embedding_model}")
                
                provider_info = {
                    "name": provider_name,
                    "api_key": api_key,
                    "base_url": base_url,
                    "model": embedding_model,
                    "display_name": provider_doc.get("display_name", provider_name)
                }
                
                # 🔥 如果这是系统配置的优先提供商，将其放在最前面
                if preferred_provider_name == provider_name:
                    self._providers.insert(0, provider_info)
                else:
                    self._providers.append(provider_info)
                logger.debug(f"📋 加载 Embedding 提供商: {provider_info['display_name']} (模型: {embedding_model})")
            
            # 设置主提供商和备用提供商
            if self._providers:
                self._primary_provider = self._providers[0]
                self._fallback_providers = self._providers[1:]
                logger.info(f"🎯 主 Embedding 提供商: {self._primary_provider['display_name']} (模型: {self._primary_provider['model']})")
                if self._fallback_providers:
                    logger.info(f"💡 备用提供商: {[p['display_name'] for p in self._fallback_providers]}")
        
        except Exception as e:
            logger.error(f"❌ 从数据库初始化 Embedding 提供商失败: {e}")
            raise
    
    def _init_from_env(self):
        """从环境变量初始化 Embedding 提供商"""
        logger.info("📋 从环境变量初始化 Embedding 提供商")
        
        # 按优先级尝试各个提供商
        providers_config = [
            {
                "name": "dashscope",
                "env_key": "DASHSCOPE_API_KEY",
                "model": "text-embedding-v3",
                "base_url": "https://dashscope.aliyuncs.com/api/v1",
                "display_name": "阿里云通义千问"
            },
            {
                "name": "openai",
                "env_key": "OPENAI_API_KEY",
                "model": "text-embedding-3-small",
                "base_url": "https://api.openai.com/v1",
                "display_name": "OpenAI"
            },
            {
                "name": "deepseek",
                "env_key": "DEEPSEEK_API_KEY",
                "model": "text-embedding-v3",
                "base_url": "https://api.deepseek.com",
                "display_name": "DeepSeek"
            },
            {
                "name": "ollama",
                "env_key": None,  # 本地模型不需要 API Key
                "model": "nomic-embed-text",  # Ollama 默认 Embedding 模型
                "base_url": "http://localhost:11434/v1",
                "display_name": "Ollama (本地)"
            },
            {
                "name": "localai",
                "env_key": None,  # 本地模型不需要 API Key
                "model": "text-embedding-ada-002",  # LocalAI 默认 Embedding 模型
                "base_url": "http://localhost:8080/v1",
                "display_name": "LocalAI (本地)"
            },
        ]
        
        for config in providers_config:
            # 🔥 本地模型（Ollama、LocalAI）不需要 API Key，直接添加
            if config["env_key"] is None:
                provider_info = {
                    "name": config["name"],
                    "api_key": "ollama",  # 本地模型使用占位符
                    "base_url": config["base_url"],
                    "model": config["model"],
                    "display_name": config["display_name"]
                }
                self._providers.append(provider_info)
                logger.debug(f"📋 加载 Embedding 提供商: {config['display_name']} (本地模型)")
            else:
                # 云端模型需要 API Key
                api_key = os.getenv(config["env_key"])
                if api_key:
                    provider_info = {
                        "name": config["name"],
                        "api_key": api_key,
                        "base_url": config["base_url"],
                        "model": config["model"],
                        "display_name": config["display_name"]
                    }
                    self._providers.append(provider_info)
                    logger.debug(f"📋 加载 Embedding 提供商: {config['display_name']}")
        
        # 设置主提供商和备用提供商
        if self._providers:
            self._primary_provider = self._providers[0]
            self._fallback_providers = self._providers[1:]
            logger.info(f"🎯 主 Embedding 提供商: {self._primary_provider['display_name']}")
        else:
            logger.warning("⚠️ 未找到可用的 Embedding 提供商，记忆功能将被禁用")

    def get_config(self) -> Dict[str, Any]:
        """
        获取当前的 Embedding 配置信息
        
        Returns:
            包含主提供商和备用提供商配置的字典
        """
        config = {
            "primary_provider": None,
            "fallback_providers": [],
            "total_providers": len(self._providers),
            "has_provider": bool(self._primary_provider)
        }
        
        if self._primary_provider:
            config["primary_provider"] = {
                "name": self._primary_provider.get("name"),
                "display_name": self._primary_provider.get("display_name"),
                "model": self._primary_provider.get("model"),
                "base_url": self._primary_provider.get("base_url"),
                # 不返回 API Key（安全考虑）
            }
        
        if self._fallback_providers:
            config["fallback_providers"] = [
                {
                    "name": p.get("name"),
                    "display_name": p.get("display_name"),
                    "model": p.get("model"),
                    "base_url": p.get("base_url"),
                }
                for p in self._fallback_providers
            ]
        
        return config
    
    def get_embedding(self, text: str, max_length: int = 50000) -> Tuple[Optional[List[float]], str]:
        """
        获取文本的 Embedding 向量

        Args:
            text: 输入文本
            max_length: 最大文本长度（超过则截断）

        Returns:
            (embedding向量, 提供商名称) 或 (None, 错误信息)
        """
        if not text or not isinstance(text, str):
            logger.warning("⚠️ 输入文本为空或无效")
            return None, "invalid_input"

        # 检查文本长度
        if len(text) > max_length:
            logger.warning(f"⚠️ 文本过长 ({len(text):,} > {max_length:,})，进行截断")
            text = self._smart_truncate(text, max_length)

        # 如果没有可用的提供商
        if not self._primary_provider:
            logger.warning("⚠️ 没有可用的 Embedding 提供商")
            return None, "no_provider"

        # 尝试主提供商
        embedding = self._call_provider(self._primary_provider, text)
        if embedding:
            return embedding, self._primary_provider['display_name']

        # 尝试备用提供商
        for provider in self._fallback_providers:
            logger.info(f"💡 尝试备用提供商: {provider['display_name']}")
            embedding = self._call_provider(provider, text)
            if embedding:
                return embedding, provider['display_name']

        # 所有提供商都失败
        logger.error("❌ 所有 Embedding 提供商都失败")
        return None, "all_failed"

    def _call_provider(self, provider: Dict[str, Any], text: str) -> Optional[List[float]]:
        """
        调用指定的 Embedding 提供商

        Args:
            provider: 提供商配置
            text: 输入文本

        Returns:
            embedding 向量或 None
        """
        provider_name = provider['name']

        try:
            if provider_name == "dashscope":
                return self._call_dashscope(provider, text)
            elif provider_name in ["openai", "deepseek", "ollama", "localai"]:
                # 🔥 本地模型（Ollama、LocalAI）也使用 OpenAI 兼容的 API
                return self._call_openai_compatible(provider, text)
            elif provider_name == "google":
                return self._call_google(provider, text)
            elif provider_name == "qianfan":
                return self._call_qianfan(provider, text)
            else:
                logger.warning(f"⚠️ 未知的提供商: {provider_name}")
                return None
        except Exception as e:
            logger.error(f"❌ {provider['display_name']} Embedding 调用失败: {e}")
            return None

    def _call_dashscope(self, provider: Dict[str, Any], text: str) -> Optional[List[float]]:
        """调用 DashScope Embedding API"""
        try:
            import dashscope
            from dashscope import TextEmbedding

            # 🔥 DashScope API 限制：输入文本长度必须在 [1, 8192] Token 之间
            # 注意：这是 Token 限制，不是字符限制
            # 对于中文：1 Token ≈ 1-2 字符
            # 对于英文：1 Token ≈ 0.75 词 ≈ 3-4 字符
            # 8192 Token ≈ 8000-10000 字符（混合文本的保守估计）
            # 为了安全，我们使用 8000 字符作为限制（留一些余量）
            DASHSCOPE_MAX_CHARS = 8000  # 保守估计，确保不超过 8192 Token
            if len(text) > DASHSCOPE_MAX_CHARS:
                logger.warning(f"⚠️ DashScope 文本过长 ({len(text):,} 字符 > {DASHSCOPE_MAX_CHARS:,} 字符限制)，进行截断")
                logger.info(f"   📝 注意：DashScope Embedding API 限制为 8192 Token，当前使用字符数限制 {DASHSCOPE_MAX_CHARS} 作为保守估计")
                text = self._smart_truncate(text, DASHSCOPE_MAX_CHARS)
                logger.info(f"📝 DashScope 截断后长度: {len(text):,} 字符")

            dashscope.api_key = provider['api_key']

            response = TextEmbedding.call(
                model=provider['model'],
                input=text
            )

            if response.status_code == 200:
                embedding = response.output['embeddings'][0]['embedding']
                logger.debug(f"✅ DashScope Embedding 成功，维度: {len(embedding)}")
                return embedding
            else:
                logger.error(f"❌ DashScope API 错误: {response.code} - {response.message}")
                return None
        except ImportError:
            logger.error("❌ DashScope 包未安装，请运行: pip install dashscope")
            return None
        except Exception as e:
            logger.error(f"❌ DashScope Embedding 异常: {e}")
            return None

    def _call_openai_compatible(self, provider: Dict[str, Any], text: str) -> Optional[List[float]]:
        """调用 OpenAI 兼容的 Embedding API（OpenAI, DeepSeek, Ollama, LocalAI 等）"""
        try:
            from openai import OpenAI

            # 🔥 OpenAI/DeepSeek API 限制：输入文本长度通常在 8192 tokens 左右
            # 为了安全，我们限制字符长度为 8000（留一些余量）
            OPENAI_MAX_LENGTH = 8000
            if len(text) > OPENAI_MAX_LENGTH:
                logger.warning(f"⚠️ {provider['display_name']} 文本过长 ({len(text):,} > {OPENAI_MAX_LENGTH:,})，进行截断")
                text = self._smart_truncate(text, OPENAI_MAX_LENGTH)
                logger.info(f"📝 {provider['display_name']} 截断后长度: {len(text):,}")

            # 🔥 本地模型（Ollama、LocalAI）通常不需要 API Key，使用 "ollama" 或空字符串
            api_key = provider.get('api_key') or "ollama"
            
            client = OpenAI(
                api_key=api_key,  # 本地模型可以使用任意值或 "ollama"
                base_url=provider['base_url']
            )

            response = client.embeddings.create(
                model=provider['model'],
                input=text
            )

            embedding = response.data[0].embedding
            logger.debug(f"✅ {provider['display_name']} Embedding 成功，维度: {len(embedding)}")
            return embedding
        except ImportError:
            logger.error("❌ OpenAI 包未安装，请运行: pip install openai")
            return None
        except Exception as e:
            logger.error(f"❌ {provider['display_name']} Embedding 异常: {e}")
            return None

    def _call_google(self, provider: Dict[str, Any], text: str) -> Optional[List[float]]:
        """调用 Google Embedding API"""
        # TODO: 实现 Google Embedding API 调用
        logger.warning("⚠️ Google Embedding 暂未实现")
        return None

    def _call_qianfan(self, provider: Dict[str, Any], text: str) -> Optional[List[float]]:
        """调用 Qianfan Embedding API"""
        # TODO: 实现 Qianfan Embedding API 调用
        logger.warning("⚠️ Qianfan Embedding 暂未实现")
        return None

    def _smart_truncate(self, text: str, max_length: int) -> str:
        """智能截断文本，保持语义完整性"""
        if len(text) <= max_length:
            return text

        # 尝试在句子边界截断
        sentences = text.split('。')
        if len(sentences) > 1:
            truncated = ""
            for sentence in sentences:
                if len(truncated + sentence + '。') <= max_length - 50:
                    truncated += sentence + '。'
                else:
                    break
            if len(truncated) > max_length // 2:
                logger.debug(f"📝 在句子边界截断，保留 {len(truncated)}/{len(text)} 字符")
                return truncated

        # 简单截断
        truncated = text[:max_length]
        logger.debug(f"📝 简单截断，保留 {len(truncated)}/{len(text)} 字符")
        return truncated

