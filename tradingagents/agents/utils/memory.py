import chromadb
from chromadb.config import Settings
from openai import OpenAI
import dashscope
from dashscope import TextEmbedding
import os
import threading
import hashlib
from typing import Dict, Optional

# 导入统一日志系统
from tradingagents.utils.logging_init import get_logger
logger = get_logger("agents.utils.memory")


class ChromaDBManager:
    """单例ChromaDB管理器，避免并发创建集合的冲突"""

    _instance = None
    _lock = threading.Lock()
    _collections: Dict[str, any] = {}
    _client = None
    _chroma_operation_lock = threading.Lock()  # 🔒 ChromaDB 操作锁（保护 Rust 扩展）

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(ChromaDBManager, cls).__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if not self._initialized:
            try:
                # 使用统一的配置模块
                from .chromadb_config import get_optimal_chromadb_client, is_windows_11
                import platform

                self._client = get_optimal_chromadb_client()

                # 记录初始化信息
                system = platform.system()
                if system == "Windows":
                    if is_windows_11():
                        logger.info(f"📚 [ChromaDB] Windows 11优化配置初始化完成 (构建号: {platform.version()})")
                    else:
                        logger.info(f"📚 [ChromaDB] Windows 10兼容配置初始化完成")
                else:
                    logger.info(f"📚 [ChromaDB] {system}标准配置初始化完成")

                self._initialized = True
            except Exception as e:
                logger.error(f"❌ [ChromaDB] 初始化失败: {e}")
                # 使用最简单的配置作为备用
                try:
                    settings = Settings(
                        allow_reset=True,
                        anonymized_telemetry=False,  # 关键：禁用遥测
                        is_persistent=False
                    )
                    self._client = chromadb.Client(settings)
                    logger.info(f"📚 [ChromaDB] 使用备用配置初始化完成")
                except Exception as backup_error:
                    # 最后的备用方案
                    self._client = chromadb.Client()
                    logger.warning(f"⚠️ [ChromaDB] 使用最简配置初始化: {backup_error}")
                self._initialized = True

    def get_or_create_collection(self, name: str):
        """线程安全地获取或创建集合"""
        with self._lock:
            if name in self._collections:
                logger.info(f"📚 [ChromaDB] 使用缓存集合: {name}")
                return self._collections[name]

            try:
                # 尝试获取现有集合
                collection = self._client.get_collection(name=name)
                logger.info(f"📚 [ChromaDB] 获取现有集合: {name}")
            except Exception:
                try:
                    # 创建新集合
                    collection = self._client.create_collection(name=name)
                    logger.info(f"📚 [ChromaDB] 创建新集合: {name}")
                except Exception as e:
                    # 可能是并发创建，再次尝试获取
                    try:
                        collection = self._client.get_collection(name=name)
                        logger.info(f"📚 [ChromaDB] 并发创建后获取集合: {name}")
                    except Exception as final_error:
                        logger.error(f"❌ [ChromaDB] 集合操作失败: {name}, 错误: {final_error}")
                        raise final_error

            # 缓存集合
            self._collections[name] = collection
            return collection


class FinancialSituationMemory:
    def __init__(self, name, config):
        self.config = config
        self.llm_provider = config.get("llm_provider", "openai").lower()

        # 配置向量缓存的长度限制（向量缓存默认启用长度检查）
        self.max_embedding_length = int(os.getenv('MAX_EMBEDDING_CONTENT_LENGTH', '50000'))  # 默认50K字符
        self.enable_embedding_length_check = os.getenv('ENABLE_EMBEDDING_LENGTH_CHECK', 'true').lower() == 'true'  # 向量缓存默认启用

        # 根据LLM提供商选择嵌入模型和客户端
        # 初始化降级选项标志
        self.fallback_available = False

        # 🔥 优先从数据库配置获取可用的 embedding 服务
        if self._init_from_database_config():
            # 从数据库初始化成功，跳过传统初始化逻辑
            pass
        elif self.llm_provider == "dashscope" or self.llm_provider == "alibaba":
            self.embedding = "text-embedding-v3"
            self.client = None  # DashScope不需要OpenAI客户端

            # 设置DashScope API密钥
            dashscope_key = os.getenv('DASHSCOPE_API_KEY')
            if dashscope_key:
                try:
                    # 尝试导入和初始化DashScope
                    import dashscope
                    from dashscope import TextEmbedding

                    dashscope.api_key = dashscope_key
                    logger.info(f"✅ DashScope API密钥已配置，启用记忆功能")

                    # 可选：测试API连接（简单验证）
                    # 这里不做实际调用，只验证导入和密钥设置

                except ImportError as e:
                    # DashScope包未安装
                    logger.error(f"❌ DashScope包未安装: {e}")
                    self.client = "DISABLED"
                    logger.warning(f"⚠️ 记忆功能已禁用")

                except Exception as e:
                    # 其他初始化错误
                    logger.error(f"❌ DashScope初始化失败: {e}")
                    self.client = "DISABLED"
                    logger.warning(f"⚠️ 记忆功能已禁用")
            else:
                # 没有DashScope密钥，禁用记忆功能
                self.client = "DISABLED"
                logger.warning(f"⚠️ 未找到DASHSCOPE_API_KEY，记忆功能已禁用")
                logger.info(f"💡 系统将继续运行，但不会保存或检索历史记忆")
        elif self.llm_provider == "qianfan":
            # 千帆（文心一言）embedding配置
            # 千帆目前没有独立的embedding API，使用阿里百炼作为降级选项
            dashscope_key = os.getenv('DASHSCOPE_API_KEY')
            if dashscope_key:
                try:
                    # 使用阿里百炼嵌入服务作为千帆的embedding解决方案
                    import dashscope
                    from dashscope import TextEmbedding

                    dashscope.api_key = dashscope_key
                    self.embedding = "text-embedding-v3"
                    self.client = None
                    logger.info(f"💡 千帆使用阿里百炼嵌入服务")
                except ImportError as e:
                    logger.error(f"❌ DashScope包未安装: {e}")
                    self.client = "DISABLED"
                    logger.warning(f"⚠️ 千帆记忆功能已禁用")
                except Exception as e:
                    logger.error(f"❌ 千帆嵌入初始化失败: {e}")
                    self.client = "DISABLED"
                    logger.warning(f"⚠️ 千帆记忆功能已禁用")
            else:
                # 没有DashScope密钥，禁用记忆功能
                self.client = "DISABLED"
                logger.warning(f"⚠️ 千帆未找到DASHSCOPE_API_KEY，记忆功能已禁用")
                logger.info(f"💡 系统将继续运行，但不会保存或检索历史记忆")
        elif self.llm_provider == "deepseek":
            # 检查是否强制使用OpenAI嵌入
            force_openai = os.getenv('FORCE_OPENAI_EMBEDDING', 'false').lower() == 'true'

            if not force_openai:
                # 尝试使用阿里百炼嵌入
                dashscope_key = os.getenv('DASHSCOPE_API_KEY')
                if dashscope_key:
                    try:
                        # 测试阿里百炼是否可用
                        import dashscope
                        from dashscope import TextEmbedding

                        dashscope.api_key = dashscope_key
                        # 验证TextEmbedding可用性（不需要实际调用）
                        self.embedding = "text-embedding-v3"
                        self.client = None
                        logger.info(f"💡 DeepSeek使用阿里百炼嵌入服务")
                    except ImportError as e:
                        logger.error(f"⚠️ DashScope包未安装: {e}")
                        dashscope_key = None  # 强制降级
                    except Exception as e:
                        logger.error(f"⚠️ 阿里百炼嵌入初始化失败: {e}")
                        dashscope_key = None  # 强制降级
            else:
                dashscope_key = None  # 跳过阿里百炼

            if not dashscope_key or force_openai:
                # 降级到OpenAI嵌入
                self.embedding = "text-embedding-3-small"
                openai_key = os.getenv('OPENAI_API_KEY')
                if openai_key:
                    self.client = OpenAI(
                        api_key=openai_key,
                        base_url=config.get("backend_url", "https://api.openai.com/v1")
                    )
                    logger.warning(f"⚠️ DeepSeek回退到OpenAI嵌入服务")
                else:
                    # 最后尝试DeepSeek自己的嵌入
                    deepseek_key = os.getenv('DEEPSEEK_API_KEY')
                    if deepseek_key:
                        try:
                            self.client = OpenAI(
                                api_key=deepseek_key,
                                base_url="https://api.deepseek.com"
                            )
                            logger.info(f"💡 DeepSeek使用自己的嵌入服务")
                        except Exception as e:
                            logger.error(f"❌ DeepSeek嵌入服务不可用: {e}")
                            # 禁用内存功能
                            self.client = "DISABLED"
                            logger.info(f"🚨 内存功能已禁用，系统将继续运行但不保存历史记忆")
                    else:
                        # 禁用内存功能而不是抛出异常
                        self.client = "DISABLED"
                        logger.info(f"🚨 未找到可用的嵌入服务，内存功能已禁用")
        elif self.llm_provider == "google":
            # Google AI使用阿里百炼嵌入（如果可用），否则禁用记忆功能
            dashscope_key = os.getenv('DASHSCOPE_API_KEY')
            openai_key = os.getenv('OPENAI_API_KEY')
            
            if dashscope_key:
                try:
                    # 尝试初始化DashScope
                    import dashscope
                    from dashscope import TextEmbedding

                    self.embedding = "text-embedding-v3"
                    self.client = None
                    dashscope.api_key = dashscope_key
                    
                    # 检查是否有OpenAI密钥作为降级选项
                    if openai_key:
                        logger.info(f"💡 Google AI使用阿里百炼嵌入服务（OpenAI作为降级选项）")
                        self.fallback_available = True
                        self.fallback_client = OpenAI(api_key=openai_key, base_url=config["backend_url"])
                        self.fallback_embedding = "text-embedding-3-small"
                    else:
                        logger.info(f"💡 Google AI使用阿里百炼嵌入服务（无降级选项）")
                        self.fallback_available = False
                        
                except ImportError as e:
                    logger.error(f"❌ DashScope包未安装: {e}")
                    self.client = "DISABLED"
                    logger.warning(f"⚠️ Google AI记忆功能已禁用")
                except Exception as e:
                    logger.error(f"❌ DashScope初始化失败: {e}")
                    self.client = "DISABLED"
                    logger.warning(f"⚠️ Google AI记忆功能已禁用")
            else:
                # 没有DashScope密钥，禁用记忆功能
                self.client = "DISABLED"
                self.fallback_available = False
                logger.warning(f"⚠️ Google AI未找到DASHSCOPE_API_KEY，记忆功能已禁用")
                logger.info(f"💡 系统将继续运行，但不会保存或检索历史记忆")
        elif self.llm_provider == "openrouter":
            # OpenRouter支持：优先使用阿里百炼嵌入，否则禁用记忆功能
            dashscope_key = os.getenv('DASHSCOPE_API_KEY')
            if dashscope_key:
                try:
                    # 尝试使用阿里百炼嵌入
                    import dashscope
                    from dashscope import TextEmbedding

                    self.embedding = "text-embedding-v3"
                    self.client = None
                    dashscope.api_key = dashscope_key
                    logger.info(f"💡 OpenRouter使用阿里百炼嵌入服务")
                except ImportError as e:
                    logger.error(f"❌ DashScope包未安装: {e}")
                    self.client = "DISABLED"
                    logger.warning(f"⚠️ OpenRouter记忆功能已禁用")
                except Exception as e:
                    logger.error(f"❌ DashScope初始化失败: {e}")
                    self.client = "DISABLED"
                    logger.warning(f"⚠️ OpenRouter记忆功能已禁用")
            else:
                # 没有DashScope密钥，禁用记忆功能
                self.client = "DISABLED"
                logger.warning(f"⚠️ OpenRouter未找到DASHSCOPE_API_KEY，记忆功能已禁用")
                logger.info(f"💡 系统将继续运行，但不会保存或检索历史记忆")
        elif config["backend_url"] == "http://localhost:11434/v1":
            self.embedding = "nomic-embed-text"
            self.client = OpenAI(base_url=config["backend_url"])
        else:
            self.embedding = "text-embedding-3-small"
            openai_key = os.getenv('OPENAI_API_KEY')
            if openai_key:
                self.client = OpenAI(
                    api_key=openai_key,
                    base_url=config["backend_url"]
                )
            else:
                self.client = "DISABLED"
                logger.warning(f"⚠️ 未找到OPENAI_API_KEY，记忆功能已禁用")

        # 使用单例ChromaDB管理器
        self.chroma_manager = ChromaDBManager()
        self.situation_collection = self.chroma_manager.get_or_create_collection(name)

    def _smart_text_truncation(self, text, max_length=8192):
        """智能文本截断，保持语义完整性和缓存兼容性"""
        if len(text) <= max_length:
            return text, False  # 返回原文本和是否截断的标志
        
        # 尝试在句子边界截断
        sentences = text.split('。')
        if len(sentences) > 1:
            truncated = ""
            for sentence in sentences:
                if len(truncated + sentence + '。') <= max_length - 50:  # 留50字符余量
                    truncated += sentence + '。'
                else:
                    break
            if len(truncated) > max_length // 2:  # 至少保留一半内容
                logger.info(f"📝 智能截断：在句子边界截断，保留{len(truncated)}/{len(text)}字符")
                return truncated, True
        
        # 尝试在段落边界截断
        paragraphs = text.split('\n')
        if len(paragraphs) > 1:
            truncated = ""
            for paragraph in paragraphs:
                if len(truncated + paragraph + '\n') <= max_length - 50:
                    truncated += paragraph + '\n'
                else:
                    break
            if len(truncated) > max_length // 2:
                logger.info(f"📝 智能截断：在段落边界截断，保留{len(truncated)}/{len(text)}字符")
                return truncated, True
        
        # 最后选择：保留前半部分和后半部分的关键信息
        front_part = text[:max_length//2]
        back_part = text[-(max_length//2-100):]  # 留100字符给连接符
        truncated = front_part + "\n...[内容截断]...\n" + back_part
        logger.warning(f"⚠️ 强制截断：保留首尾关键信息，{len(text)}字符截断为{len(truncated)}字符")
        return truncated, True

    def _init_from_database_config(self) -> bool:
        """
        从数据库配置初始化 embedding 服务

        优先从数据库获取支持 embedding 且已启用的厂商，按优先级选择

        Returns:
            True 如果初始化成功，False 如果需要回退到传统初始化
        """
        try:
            from .embedding_provider import get_embedding_manager, EmbeddingProviderConfig

            manager = get_embedding_manager()
            providers = manager.get_available_providers()

            if not providers:
                logger.debug("📋 数据库中没有可用的 embedding 提供者，使用传统初始化")
                return False

            # 选择优先级最高的提供者
            primary_provider = providers[0]
            logger.info(f"✅ 从数据库获取 embedding 配置: {primary_provider.display_name} ({primary_provider.name})")

            # 配置 embedding 参数
            self.embedding = primary_provider.model
            self.embedding_provider_name = primary_provider.name
            self._embedding_provider_config = primary_provider
            self._embedding_manager = manager

            # 根据提供者类型设置客户端
            if primary_provider.name in ("dashscope", "alibaba"):
                # DashScope 使用自己的 SDK，不需要 OpenAI 客户端
                try:
                    import dashscope
                    dashscope.api_key = primary_provider.api_key
                    self.client = None
                    logger.info(f"✅ 使用 {primary_provider.display_name} embedding 服务（SDK模式）")
                except ImportError:
                    logger.warning("⚠️ DashScope 包未安装，尝试使用 OpenAI 兼容模式")
                    self.client = OpenAI(
                        api_key=primary_provider.api_key,
                        base_url=primary_provider.base_url,
                        timeout=30.0
                    )
            else:
                # 其他提供者使用 OpenAI 兼容客户端
                self.client = OpenAI(
                    api_key=primary_provider.api_key,
                    base_url=primary_provider.base_url,
                    timeout=30.0
                )
                logger.info(f"✅ 使用 {primary_provider.display_name} embedding 服务（OpenAI兼容模式）")

            # 如果有其他提供者，标记降级可用
            if len(providers) > 1:
                self.fallback_available = True
                logger.info(f"💡 降级选项可用: {[p.name for p in providers[1:]]}")

            # 更新 llm_provider 以反映实际使用的提供者
            self.llm_provider = primary_provider.name

            return True

        except ImportError as e:
            logger.debug(f"📋 EmbeddingProviderManager 不可用: {e}，使用传统初始化")
            return False
        except Exception as e:
            logger.warning(f"⚠️ 从数据库初始化 embedding 失败: {e}，使用传统初始化")
            return False

    def get_embedding(self, text):
        """Get embedding for a text using the configured provider"""

        # 检查记忆功能是否被禁用
        if self.client == "DISABLED":
            # 内存功能已禁用，返回空向量
            logger.debug(f"⚠️ 记忆功能已禁用，返回空向量")
            return [0.0] * 1024  # 返回1024维的零向量

        # 验证输入文本
        if not text or not isinstance(text, str):
            logger.warning(f"⚠️ 输入文本为空或无效，返回空向量")
            return [0.0] * 1024

        text_length = len(text)
        if text_length == 0:
            logger.warning(f"⚠️ 输入文本长度为0，返回空向量")
            return [0.0] * 1024
        
        # 检查是否启用长度限制
        if self.enable_embedding_length_check and text_length > self.max_embedding_length:
            logger.warning(f"⚠️ 文本过长({text_length:,}字符 > {self.max_embedding_length:,}字符)，跳过向量化")
            # 存储跳过信息
            self._last_text_info = {
                'original_length': text_length,
                'processed_length': 0,
                'was_truncated': False,
                'was_skipped': True,
                'provider': self.llm_provider,
                'strategy': 'length_limit_skip',
                'max_length': self.max_embedding_length
            }
            return [0.0] * 1024
        
        # 记录文本信息（不进行任何截断）
        if text_length > 8192:
            logger.info(f"📝 处理长文本: {text_length}字符，提供商: {self.llm_provider}")
        
        # 存储文本处理信息
        self._last_text_info = {
            'original_length': text_length,
            'processed_length': text_length,  # 不截断，保持原长度
            'was_truncated': False,  # 永不截断
            'was_skipped': False,
            'provider': self.llm_provider,
            'strategy': 'no_truncation_with_fallback'  # 标记策略
        }

        # 🔥 优先使用数据库配置的 embedding 管理器
        if hasattr(self, '_embedding_manager') and self._embedding_manager is not None:
            try:
                embedding, provider_name = self._embedding_manager.get_embedding(text)
                if embedding:
                    logger.debug(f"✅ 使用 {provider_name} 获取 embedding，维度: {len(embedding)}")
                    return embedding
                else:
                    logger.warning(f"⚠️ EmbeddingManager 获取失败: {provider_name}，返回空向量")
                    return [0.0] * 1024
            except Exception as e:
                logger.warning(f"⚠️ EmbeddingManager 异常: {e}，返回空向量")
                return [0.0] * 1024

        if (self.llm_provider == "dashscope" or
            self.llm_provider == "alibaba" or
            self.llm_provider == "qianfan" or
            (self.llm_provider == "google" and self.client is None) or
            (self.llm_provider == "deepseek" and self.client is None) or
            (self.llm_provider == "openrouter" and self.client is None)):
            # 使用阿里百炼的嵌入模型
            try:
                # 导入DashScope模块
                import dashscope
                from dashscope import TextEmbedding

                # 检查DashScope API密钥是否可用
                if not hasattr(dashscope, 'api_key') or not dashscope.api_key:
                    logger.warning(f"⚠️ DashScope API密钥未设置，记忆功能降级")
                    return [0.0] * 1024  # 返回空向量

                # 尝试调用DashScope API
                response = TextEmbedding.call(
                    model=self.embedding,
                    input=text
                )

                # 检查响应状态
                if response.status_code == 200:
                    # 成功获取embedding
                    embedding = response.output['embeddings'][0]['embedding']
                    logger.debug(f"✅ DashScope embedding成功，维度: {len(embedding)}")
                    return embedding
                else:
                    # API返回错误状态码
                    error_msg = f"{response.code} - {response.message}"
                    
                    # 检查是否为长度限制错误
                    if any(keyword in error_msg.lower() for keyword in ['length', 'token', 'limit', 'exceed']):
                        logger.warning(f"⚠️ DashScope长度限制: {error_msg}")
                        
                        # 检查是否有降级选项
                        if hasattr(self, 'fallback_available') and self.fallback_available:
                            logger.info(f"💡 尝试使用OpenAI降级处理长文本")
                            try:
                                response = self.fallback_client.embeddings.create(
                                    model=self.fallback_embedding,
                                    input=text
                                )
                                embedding = response.data[0].embedding
                                logger.info(f"✅ OpenAI降级成功，维度: {len(embedding)}")
                                return embedding
                            except Exception as fallback_error:
                                logger.error(f"❌ OpenAI降级失败: {str(fallback_error)}")
                                logger.info(f"💡 所有降级选项失败，记忆功能降级")
                                return [0.0] * 1024
                        else:
                            logger.info(f"💡 无可用降级选项，记忆功能降级")
                            return [0.0] * 1024
                    else:
                        logger.error(f"❌ DashScope API错误: {error_msg}")
                        return [0.0] * 1024  # 返回空向量而不是抛出异常

            except Exception as e:
                error_str = str(e).lower()
                
                # 检查是否为长度限制错误
                if any(keyword in error_str for keyword in ['length', 'token', 'limit', 'exceed', 'too long']):
                    logger.warning(f"⚠️ DashScope长度限制异常: {str(e)}")
                    
                    # 检查是否有降级选项
                    if hasattr(self, 'fallback_available') and self.fallback_available:
                        logger.info(f"💡 尝试使用OpenAI降级处理长文本")
                        try:
                            response = self.fallback_client.embeddings.create(
                                model=self.fallback_embedding,
                                input=text
                            )
                            embedding = response.data[0].embedding
                            logger.info(f"✅ OpenAI降级成功，维度: {len(embedding)}")
                            return embedding
                        except Exception as fallback_error:
                            logger.error(f"❌ OpenAI降级失败: {str(fallback_error)}")
                            logger.info(f"💡 所有降级选项失败，记忆功能降级")
                            return [0.0] * 1024
                    else:
                        logger.info(f"💡 无可用降级选项，记忆功能降级")
                        return [0.0] * 1024
                elif 'import' in error_str:
                    logger.error(f"❌ DashScope包未安装: {str(e)}")
                else:
                    # 检查是否为网络错误，尝试使用其他可用服务降级
                    is_network_error = any(keyword in error_str for keyword in [
                        'timeout', 'timed out', 'connection', 'network', 'refused'
                    ])

                    if is_network_error:
                        logger.warning(f"⚠️ DashScope 网络错误: {str(e)}")
                        # 尝试使用配置的其他 embedding 服务降级（排除当前 dashscope）
                        try:
                            from .embedding_provider import get_embedding_manager
                            manager = get_embedding_manager()
                            providers = manager.get_available_providers()
                            # 过滤掉 dashscope，尝试其他服务
                            for provider in providers:
                                if provider.name not in ('dashscope', 'alibaba'):
                                    try:
                                        embedding = manager._call_provider(provider, text)
                                        if embedding:
                                            logger.info(f"✅ 使用 {provider.display_name} 降级成功")
                                            return embedding
                                    except Exception:
                                        continue
                        except Exception as fallback_e:
                            logger.debug(f"⚠️ 降级尝试失败: {fallback_e}")
                    else:
                        logger.error(f"❌ DashScope embedding异常: {str(e)}")

                logger.warning(f"⚠️ 记忆功能降级，返回空向量")
                return [0.0] * 1024
        else:
            # 使用OpenAI兼容的嵌入模型
            if self.client is None:
                logger.warning(f"⚠️ 嵌入客户端未初始化，返回空向量")
                return [0.0] * 1024  # 返回空向量
            elif self.client == "DISABLED":
                # 内存功能已禁用，返回空向量
                logger.debug(f"⚠️ 内存功能已禁用，返回空向量")
                return [0.0] * 1024  # 返回1024维的零向量

            # 尝试调用OpenAI兼容的embedding API
            try:
                response = self.client.embeddings.create(
                    model=self.embedding,
                    input=text
                )
                embedding = response.data[0].embedding
                logger.debug(f"✅ {self.llm_provider} embedding成功，维度: {len(embedding)}")
                return embedding

            except Exception as e:
                error_str = str(e).lower()

                # 检查是否为超时或网络错误，尝试使用阿里百练降级
                is_network_error = any(keyword in error_str for keyword in [
                    'timeout', 'timed out', 'connection', 'network', 'refused'
                ])

                if is_network_error:
                    logger.warning(f"⚠️ {self.llm_provider} embedding 网络错误: {str(e)}")
                    # 尝试使用配置的 embedding 服务降级（按优先级）
                    fallback_result = self._try_embedding_fallback(text)
                    if fallback_result is not None:
                        return fallback_result

                # 检查是否为长度限制错误
                length_error_keywords = [
                    'token', 'length', 'too long', 'exceed', 'maximum', 'limit',
                    'context', 'input too large', 'request too large'
                ]

                is_length_error = any(keyword in error_str for keyword in length_error_keywords)

                if is_length_error:
                    # 长度限制错误：直接降级，不截断重试
                    logger.warning(f"⚠️ {self.llm_provider}长度限制: {str(e)}")
                    logger.info(f"💡 为保证分析准确性，不截断文本，记忆功能降级")
                else:
                    # 其他类型的错误
                    if 'attributeerror' in error_str:
                        logger.error(f"❌ {self.llm_provider} API调用错误: {str(e)}")
                    elif 'connectionerror' in error_str or 'connection' in error_str:
                        logger.error(f"❌ {self.llm_provider}网络连接错误: {str(e)}")
                    elif 'timeout' in error_str:
                        logger.error(f"❌ {self.llm_provider}请求超时: {str(e)}")
                    elif 'keyerror' in error_str:
                        logger.error(f"❌ {self.llm_provider}响应格式错误: {str(e)}")
                    else:
                        logger.error(f"❌ {self.llm_provider} embedding异常: {str(e)}")

                logger.warning(f"⚠️ 记忆功能降级，返回空向量")
                return [0.0] * 1024

    def _try_dashscope_fallback(self, text):
        """
        尝试使用阿里百练（DashScope）作为 embedding 降级选项

        当主要的 embedding 服务（如 OpenAI）不可用时调用此方法

        Args:
            text: 要生成 embedding 的文本

        Returns:
            embedding 向量，或 None（如果降级也失败）
        """
        # 检查是否有 DashScope API 密钥
        dashscope_key = os.getenv('DASHSCOPE_API_KEY')
        if not dashscope_key:
            logger.debug("⚠️ 未配置 DASHSCOPE_API_KEY，无法使用阿里百练降级")
            return None

        try:
            import dashscope
            from dashscope import TextEmbedding

            # 确保 API 密钥已设置
            if not hasattr(dashscope, 'api_key') or not dashscope.api_key:
                dashscope.api_key = dashscope_key

            logger.info("💡 尝试使用阿里百练 embedding 降级...")

            # 调用 DashScope API
            response = TextEmbedding.call(
                model="text-embedding-v3",
                input=text
            )

            if response.status_code == 200:
                embedding = response.output['embeddings'][0]['embedding']
                logger.info(f"✅ 阿里百练降级成功，维度: {len(embedding)}")
                return embedding
            else:
                logger.warning(f"⚠️ 阿里百练降级失败: {response.code} - {response.message}")
                return None

        except ImportError:
            logger.debug("⚠️ DashScope 包未安装，无法使用阿里百练降级")
            return None
        except Exception as e:
            logger.warning(f"⚠️ 阿里百练降级异常: {str(e)}")
            return None

    def _try_embedding_fallback(self, text):
        """
        使用 EmbeddingProviderManager 尝试所有可用的 embedding 服务

        从数据库配置中获取支持 embedding 的厂商，按优先级尝试

        Args:
            text: 要生成 embedding 的文本

        Returns:
            embedding 向量，或 None（如果所有服务都失败）
        """
        try:
            from .embedding_provider import get_embedding_with_fallback

            logger.info("💡 尝试使用可用的 embedding 服务降级...")

            # 排除当前已经失败的提供者
            embedding, provider_name = get_embedding_with_fallback(
                text,
                preferred_provider=None  # 让管理器按优先级选择
            )

            if embedding:
                logger.info(f"✅ 使用 {provider_name} embedding 降级成功，维度: {len(embedding)}")
                return embedding
            else:
                logger.warning(f"⚠️ 所有 embedding 服务都失败: {provider_name}")
                return None

        except ImportError as e:
            logger.debug(f"⚠️ EmbeddingProviderManager 不可用: {e}")
            # 回退到原来的 DashScope 降级
            return self._try_dashscope_fallback(text)
        except Exception as e:
            logger.warning(f"⚠️ embedding 降级异常: {str(e)}")
            return None

    def get_embedding_config_status(self):
        """获取向量缓存配置状态"""
        return {
            'enabled': self.enable_embedding_length_check,
            'max_embedding_length': self.max_embedding_length,
            'max_embedding_length_formatted': f"{self.max_embedding_length:,}字符",
            'provider': self.llm_provider,
            'client_status': 'DISABLED' if self.client == "DISABLED" else 'ENABLED'
        }

    def get_last_text_info(self):
        """获取最后处理的文本信息"""
        return getattr(self, '_last_text_info', None)

    def add_situations(self, situations_and_advice):
        """Add financial situations and their corresponding advice. Parameter is a list of tuples (situation, rec)"""

        situations = []
        advice = []
        ids = []
        embeddings = []

        # 🔒 使用线程锁保护 ChromaDB 操作（Rust 扩展不是线程安全的）
        with ChromaDBManager._chroma_operation_lock:
            offset = self.situation_collection.count()

        for i, (situation, recommendation) in enumerate(situations_and_advice):
            situations.append(situation)
            advice.append(recommendation)
            ids.append(str(offset + i))
            embeddings.append(self.get_embedding(situation))

        # 🔒 使用线程锁保护 ChromaDB 操作（Rust 扩展不是线程安全的）
        with ChromaDBManager._chroma_operation_lock:
            self.situation_collection.add(
                documents=situations,
                metadatas=[{"recommendation": rec} for rec in advice],
                embeddings=embeddings,
                ids=ids,
            )

    def get_memories(self, current_situation, n_matches=1):
        """Find matching recommendations using embeddings with smart truncation handling"""
        
        # 获取当前情况的embedding
        query_embedding = self.get_embedding(current_situation)
        
        # 检查是否为空向量（记忆功能被禁用或出错）
        if all(x == 0.0 for x in query_embedding):
            logger.debug(f"⚠️ 查询embedding为空向量，返回空结果")
            return []

        # 🔒 使用线程锁保护 ChromaDB 操作（Rust 扩展不是线程安全的）
        with ChromaDBManager._chroma_operation_lock:
            # 检查是否有足够的数据进行查询
            collection_count = self.situation_collection.count()
            if collection_count == 0:
                logger.debug(f"📭 记忆库为空，返回空结果")
                return []

            # 调整查询数量，不能超过集合中的文档数量
            actual_n_matches = min(n_matches, collection_count)

        try:
            # 🔒 使用线程锁保护 ChromaDB 操作（Rust 扩展不是线程安全的）
            with ChromaDBManager._chroma_operation_lock:
                # 执行相似度查询
                results = self.situation_collection.query(
                    query_embeddings=[query_embedding],
                    n_results=actual_n_matches
                )
            
            # 处理查询结果
            memories = []
            if results and 'documents' in results and results['documents']:
                documents = results['documents'][0]
                metadatas = results.get('metadatas', [[]])[0]
                distances = results.get('distances', [[]])[0]
                
                for i, doc in enumerate(documents):
                    metadata = metadatas[i] if i < len(metadatas) else {}
                    distance = distances[i] if i < len(distances) else 1.0
                    
                    memory_item = {
                        'situation': doc,
                        'recommendation': metadata.get('recommendation', ''),
                        'similarity': 1.0 - distance,  # 转换为相似度分数
                        'distance': distance
                    }
                    memories.append(memory_item)
                
                # 记录查询信息
                if hasattr(self, '_last_text_info') and self._last_text_info.get('was_truncated'):
                    logger.info(f"🔍 截断文本查询完成，找到{len(memories)}个相关记忆")
                    logger.debug(f"📊 原文长度: {self._last_text_info['original_length']}, "
                               f"处理后长度: {self._last_text_info['processed_length']}")
                else:
                    logger.debug(f"🔍 记忆查询完成，找到{len(memories)}个相关记忆")
            
            return memories
            
        except Exception as e:
            logger.error(f"❌ 记忆查询失败: {str(e)}")
            return []

    def get_cache_info(self):
        """获取缓存相关信息，用于调试和监控"""
        # 🔒 使用线程锁保护 ChromaDB 操作（Rust 扩展不是线程安全的）
        with ChromaDBManager._chroma_operation_lock:
            collection_count = self.situation_collection.count()

        info = {
            'collection_count': collection_count,
            'client_status': 'enabled' if self.client != "DISABLED" else 'disabled',
            'embedding_model': self.embedding,
            'provider': self.llm_provider
        }
        
        # 添加最后一次文本处理信息
        if hasattr(self, '_last_text_info'):
            info['last_text_processing'] = self._last_text_info
            
        return info


if __name__ == "__main__":
    # Example usage
    matcher = FinancialSituationMemory()

    # Example data
    example_data = [
        (
            "High inflation rate with rising interest rates and declining consumer spending",
            "Consider defensive sectors like consumer staples and utilities. Review fixed-income portfolio duration.",
        ),
        (
            "Tech sector showing high volatility with increasing institutional selling pressure",
            "Reduce exposure to high-growth tech stocks. Look for value opportunities in established tech companies with strong cash flows.",
        ),
        (
            "Strong dollar affecting emerging markets with increasing forex volatility",
            "Hedge currency exposure in international positions. Consider reducing allocation to emerging market debt.",
        ),
        (
            "Market showing signs of sector rotation with rising yields",
            "Rebalance portfolio to maintain target allocations. Consider increasing exposure to sectors benefiting from higher rates.",
        ),
    ]

    # Add the example situations and recommendations
    matcher.add_situations(example_data)

    # Example query
    current_situation = """
    Market showing increased volatility in tech sector, with institutional investors 
    reducing positions and rising interest rates affecting growth stock valuations
    """

    try:
        recommendations = matcher.get_memories(current_situation, n_matches=2)

        for i, rec in enumerate(recommendations, 1):
            logger.info(f"\nMatch {i}:")
            logger.info(f"Similarity Score: {rec.get('similarity', 0):.2f}")
            logger.info(f"Matched Situation: {rec.get('situation', '')}")
            logger.info(f"Recommendation: {rec.get('recommendation', '')}")

    except Exception as e:
        logger.error(f"Error during recommendation: {str(e)}")
