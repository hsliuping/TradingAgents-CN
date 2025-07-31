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
    def __init__(self, name, config):
        self.config = config
        self.llm_provider = config.get("llm_provider", "openai").lower()

        # 根据LLM提供商选择嵌入模型和客户端
        if self.llm_provider == "dashscope" or self.llm_provider == "alibaba":
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
            if dashscope_key:
                try:
                    # 尝试初始化DashScope
                    import dashscope
                    from dashscope import TextEmbedding

                    self.embedding = "text-embedding-v3"
                    self.client = None
                    dashscope.api_key = dashscope_key
                    logger.info(f"💡 Google AI使用阿里百炼嵌入服务")
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

    def get_embedding(self, text):
        """Get embedding for a text using the configured provider"""

        # 检查记忆功能是否被禁用
        if self.client == "DISABLED":
            # 内存功能已禁用，返回空向量
            logger.debug(f"⚠️ 记忆功能已禁用，返回空向量")
            return [0.0] * 1024  # 返回1024维的零向量

        if (self.llm_provider == "dashscope" or
            self.llm_provider == "alibaba" or
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
                    logger.error(f"❌ DashScope API错误: {response.code} - {response.message}")
                    logger.warning(f"⚠️ 记忆功能降级，返回空向量")
                    return [0.0] * 1024  # 返回空向量而不是抛出异常

            except ImportError as e:
                # dashscope包未安装
                logger.error(f"❌ DashScope包未安装: {str(e)}")
                logger.warning(f"⚠️ 记忆功能降级，返回空向量")
                return [0.0] * 1024

            except AttributeError as e:
                # API调用方法不存在或参数错误
                logger.error(f"❌ DashScope API调用错误: {str(e)}")
                logger.warning(f"⚠️ 记忆功能降级，返回空向量")
                return [0.0] * 1024

            except ConnectionError as e:
                # 网络连接错误
                logger.error(f"❌ DashScope网络连接错误: {str(e)}")
                logger.warning(f"⚠️ 记忆功能降级，返回空向量")
                return [0.0] * 1024

            except TimeoutError as e:
                # 请求超时
                logger.error(f"❌ DashScope请求超时: {str(e)}")
                logger.warning(f"⚠️ 记忆功能降级，返回空向量")
                return [0.0] * 1024

            except KeyError as e:
                # 响应格式错误
                logger.error(f"❌ DashScope响应格式错误: {str(e)}")
                logger.warning(f"⚠️ 记忆功能降级，返回空向量")
                return [0.0] * 1024

            except Exception as e:
                # 其他所有异常
                logger.error(f"❌ DashScope embedding未知异常: {str(e)}")
                logger.warning(f"⚠️ 记忆功能降级，返回空向量")
                return [0.0] * 1024  # 返回空向量而不是抛出异常
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
                logger.debug(f"✅ OpenAI embedding成功，维度: {len(embedding)}")
                return embedding

            except AttributeError as e:
                # API调用方法不存在
                logger.error(f"❌ OpenAI API调用错误: {str(e)}")
                logger.warning(f"⚠️ 记忆功能降级，返回空向量")
                return [0.0] * 1024

            except ConnectionError as e:
                # 网络连接错误
                logger.error(f"❌ OpenAI网络连接错误: {str(e)}")
                logger.warning(f"⚠️ 记忆功能降级，返回空向量")
                return [0.0] * 1024

            except TimeoutError as e:
                # 请求超时
                logger.error(f"❌ OpenAI请求超时: {str(e)}")
                logger.warning(f"⚠️ 记忆功能降级，返回空向量")
                return [0.0] * 1024

            except KeyError as e:
                # 响应格式错误
                logger.error(f"❌ OpenAI响应格式错误: {str(e)}")
                logger.warning(f"⚠️ 记忆功能降级，返回空向量")
                return [0.0] * 1024

            except Exception as e:
                # 其他所有异常
                logger.error(f"❌ OpenAI embedding未知异常: {str(e)}")
                logger.warning(f"⚠️ 记忆功能降级，返回空向量")
                return [0.0] * 1024

            response = self.client.embeddings.create(
                model=self.embedding, input=text
            )
            return response.data[0].embedding

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
