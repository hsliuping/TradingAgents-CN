import chromadb
from chromadb.config import Settings
from openai import OpenAI
import dashscope
from dashscope import TextEmbedding
import os
import threading
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
                # 自动检测操作系统版本并使用最优配置
                import platform
                system = platform.system()
                
                if system == "Windows":
                    # 使用改进的Windows 11检测
                    from .chromadb_win11_config import is_windows_11
                    if is_windows_11():
                        # Windows 11 或更新版本，使用优化配置
                        from .chromadb_win11_config import get_win11_chromadb_client
                        self._client = get_win11_chromadb_client()
                        logger.info(f"📚 [ChromaDB] Windows 11优化配置初始化完成 (构建号: {platform.version()})")
                    else:
                        # Windows 10 或更老版本，使用兼容配置
                        from .chromadb_win10_config import get_win10_chromadb_client
                        self._client = get_win10_chromadb_client()
                        logger.info(f"📚 [ChromaDB] Windows 10兼容配置初始化完成")
                else:
                    # 非Windows系统，使用标准配置
                    settings = Settings(
                        allow_reset=True,
                        anonymized_telemetry=False,
                        is_persistent=False
                    )
                    self._client = chromadb.Client(settings)
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
    def __init__(self, name, config, memory_provider=None, memory_model=None):
        self.config = config
        self.client = "DISABLED"  # 默认禁用

        # 确定记忆功能使用的提供商和模型
        # 优先使用专门为memory指定的provider和model
        if memory_provider and memory_provider != "与主模型相同":
            provider = memory_provider.lower()
            model = memory_model if memory_model else None
            logger.info(f"🧠 [Memory] 使用独立的矢量模型配置: Provider='{provider}', Model='{model}'")
        else:
            # 如果未指定，则回退到主模型的provider，并发出警告
            provider = config.get("llm_provider", "openai").lower()
            model = None # 让后续逻辑选择默认的embedding model
            logger.warning(f"⚠️ [Memory] 未指定独立的矢量模型，将尝试使用主模型提供商 '{provider}' 的默认嵌入模型。")

        self.llm_provider = provider
        self.embedding_model = model

        # 根据提供商初始化客户端
        provider_key = self.llm_provider.split('-')[0] # 例如 'openrouter-google' -> 'openrouter'

        if provider_key == "dashscope" or provider_key == "alibaba":
            self.embedding_model = self.embedding_model or "text-embedding-v3"
            api_key = os.getenv('DASHSCOPE_API_KEY')
            if api_key:
                try:
                    import dashscope
                    from dashscope import TextEmbedding
                    dashscope.api_key = api_key
                    self.client = None # DashScope 使用模块级调用
                    logger.info(f"✅ [Memory] DashScope (阿里百炼) 嵌入服务已配置 (模型: {self.embedding_model})")
                except ImportError:
                    logger.error("❌ [Memory] DashScope包未安装，记忆功能禁用")
                except Exception as e:
                    logger.error(f"❌ [Memory] DashScope初始化失败: {e}，记忆功能禁用")
            else:
                logger.warning("⚠️ [Memory] 未找到DASHSCOPE_API_KEY，记忆功能禁用")

        elif provider_key == "deepseek":
            self.embedding_model = self.embedding_model or "embedding-2"
            api_key = os.getenv('DEEPSEEK_API_KEY')
            if api_key:
                try:
                    self.client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com/v1")
                    logger.info(f"✅ [Memory] DeepSeek嵌入服务已配置 (模型: {self.embedding_model})")
                except Exception as e:
                    logger.error(f"❌ [Memory] DeepSeek客户端初始化失败: {e}，记忆功能禁用")
            else:
                logger.warning("⚠️ [Memory] 未找到DEEPSEEK_API_KEY，记忆功能禁用")

        elif provider_key == "openai":
            self.embedding_model = self.embedding_model or "text-embedding-3-small"
            api_key = os.getenv('OPENAI_API_KEY')
            base_url = config.get("backend_url", "https://api.openai.com/v1")
            if api_key:
                try:
                    self.client = OpenAI(api_key=api_key, base_url=base_url)
                    logger.info(f"✅ [Memory] OpenAI嵌入服务已配置 (模型: {self.embedding_model})")
                except Exception as e:
                    logger.error(f"❌ [Memory] OpenAI客户端初始化失败: {e}，记忆功能禁用")
            else:
                logger.warning("⚠️ [Memory] 未找到OPENAI_API_KEY，记忆功能禁用")
        
        elif provider_key == "openrouter":
            self.embedding_model = self.embedding_model or "text-embedding-3-small" # 默认值
            api_key = os.getenv('OPENROUTER_API_KEY')
            base_url = "https://openrouter.ai/api/v1"
            if api_key:
                try:
                    self.client = OpenAI(api_key=api_key, base_url=base_url)
                    logger.info(f"✅ [Memory] OpenRouter嵌入服务已配置 (模型: {self.embedding_model})")
                except Exception as e:
                    logger.error(f"❌ [Memory] OpenRouter客户端初始化失败: {e}，记忆功能禁用")
            else:
                logger.warning("⚠️ [Memory] 未找到OPENROUTER_API_KEY，记忆功能禁用")

        elif provider_key == "google":
            api_key = os.getenv('GOOGLE_API_KEY')
            base_url = os.getenv('GOOGLE_BASE_URL') # 从环境变量获取
            if api_key and base_url:
                try:
                    self.client = OpenAI(api_key=api_key, base_url=f"{base_url}/v1/") # 尝试OpenAI API的常见路径
                    self.embedding_model = "text-embedding-004" # 明确设置为text-embedding-004
                    logger.info(f"✅ [Memory] Google嵌入服务已配置 (模型: {self.embedding_model})")
                except Exception as e:
                    logger.error(f"❌ [Memory] Google客户端初始化失败: {e}，记忆功能禁用")
            else:
                logger.warning("⚠️ [Memory] 未找到GOOGLE_API_KEY或GOOGLE_BASE_URL，记忆功能禁用")
        
        elif provider_key == "siliconflow":
            self.embedding_model = self.embedding_model or "BAAI/bge-large-zh-v1.5"
            api_key = os.getenv('SILICONFLOW_API_KEY')
            base_url = "https://api.siliconflow.cn/v1"
            if api_key:
                try:
                    self.client = OpenAI(api_key=api_key, base_url=base_url)
                    logger.info(f"✅ [Memory] SiliconFlow嵌入服务已配置 (模型: {self.embedding_model})")
                except Exception as e:
                    logger.error(f"❌ [Memory] SiliconFlow客户端初始化失败: {e}，记忆功能禁用")
            else:
                logger.warning("⚠️ [Memory] 未找到SILICONFLOW_API_KEY，记忆功能禁用")

        elif config.get("backend_url") == "http://localhost:11434/v1":
            self.embedding_model = self.embedding_model or "nomic-embed-text"
            self.client = OpenAI(base_url=config["backend_url"])
            logger.info(f"✅ [Memory] 本地Ollama嵌入服务已配置 (模型: {self.embedding_model})")
        
        else:
            logger.warning(f"⚠️ [Memory] 未知的记忆提供商 '{self.llm_provider}'，记忆功能已禁用")
            self.client = "DISABLED"

        # 使用单例ChromaDB管理器
        self.chroma_manager = ChromaDBManager()
        self.situation_collection = self.chroma_manager.get_or_create_collection(name)

    def get_embedding(self, text):
        """Get embedding for a text using the configured provider"""

        if self.client == "DISABLED":
            logger.debug("⚠️ 记忆功能已禁用，返回零向量")
            return [0.0] * 1024

        try:
            provider_key = self.llm_provider.split('-')[0]

            if provider_key == "dashscope":
                from dashscope import TextEmbedding
                response = TextEmbedding.call(model=self.embedding_model, input=text)
                if response.status_code == 200:
                    embedding = response.output['embeddings'][0]['embedding']
                    logger.debug(f"✅ DashScope embedding成功，维度: {len(embedding)}")
                    return embedding
                else:
                    logger.error(f"❌ DashScope API错误: {response.code} - {response.message}")
                    logger.warning("⚠️ 记忆功能降级，返回零向量")
                    return [0.0] * 1024

            elif provider_key == "google":
                # 根据gemini-balance的实现，它使用OpenAI客户端进行嵌入，所以这里也使用OpenAI客户端
                if self.client == "DISABLED":
                    logger.error("❌ Google嵌入客户端未初始化，无法调用")
                    return [0.0] * 1024
                
                response = self.client.embeddings.create(model=self.embedding_model, input=text)
                embedding = response.data[0].embedding
                logger.debug(f"✅ Google embedding成功，维度: {len(embedding)}")
                return embedding

            elif self.client: # 适用于OpenAI, DeepSeek, OpenRouter等
                response = self.client.embeddings.create(model=self.embedding_model, input=text)
                embedding = response.data[0].embedding
                logger.debug(f"✅ {self.llm_provider.capitalize()} embedding成功，维度: {len(embedding)}")
                return embedding
            
            else:
                logger.error("❌ 嵌入客户端未正确初始化")
                return [0.0] * 1024

        except Exception as e:
            logger.error(f"❌ {self.llm_provider.capitalize()} embedding未知异常: {str(e)}")
            logger.warning("⚠️ 记忆功能降级，返回零向量")
            return [0.0] * 1024

    def add_situations(self, situations_and_advice):
        """Add financial situations and their corresponding advice. Parameter is a list of tuples (situation, rec)"""

        situations = []
        advice = []
        ids = []
        embeddings = []

        offset = self.situation_collection.count()

        for i, (situation, recommendation) in enumerate(situations_and_advice):
            situations.append(situation)
            advice.append(recommendation)
            ids.append(str(offset + i))
            embeddings.append(self.get_embedding(situation))

        self.situation_collection.add(
            documents=situations,
            metadatas=[{"recommendation": rec} for rec in advice],
            embeddings=embeddings,
            ids=ids,
        )

    def get_memories(self, current_situation, n_matches=1):
        """Find matching recommendations using embeddings"""
        query_embedding = self.get_embedding(current_situation)

        # 检查是否为空向量（记忆功能被禁用）
        if all(x == 0.0 for x in query_embedding):
            logger.debug(f"⚠️ 记忆功能已禁用，返回空记忆列表")
            return []  # 返回空列表而不是查询数据库

        try:
            results = self.situation_collection.query(
                query_embeddings=[query_embedding],
                n_results=n_matches,
                include=["metadatas", "documents", "distances"],
            )

            matched_results = []
            for i in range(len(results["documents"][0])):
                matched_results.append(
                    {
                        "matched_situation": results["documents"][0][i],
                        "recommendation": results["metadatas"][0][i]["recommendation"],
                        "similarity_score": 1 - results["distances"][0][i],
                    }
                )

            return matched_results
        except Exception as e:
            logger.error(f"❌ 记忆查询失败: {e}")
            logger.warning(f"⚠️ 返回空记忆列表")
            return []  # 查询失败时返回空列表


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
            logger.info(f"Similarity Score: {rec['similarity_score']:.2f}")
            logger.info(f"Matched Situation: {rec['matched_situation']}")
            logger.info(f"Recommendation: {rec['recommendation']}")

    except Exception as e:
        logger.error(f"Error during recommendation: {str(e)}")
