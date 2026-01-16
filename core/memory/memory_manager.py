"""
Memory 管理器 v2.0

基于 ChromaDB 的向量记忆系统，用于存储和检索 Agent 的历史经验。

特性：
- 支持多个 Agent 的独立记忆空间
- 基于语义相似度的记忆检索
- 自动管理 ChromaDB 集合
- 与 EmbeddingManager 集成
"""

import logging
import threading
from typing import List, Dict, Any, Optional, Tuple
import chromadb
from chromadb.config import Settings

logger = logging.getLogger(__name__)


class ChromaDBManager:
    """
    ChromaDB 单例管理器
    
    线程安全地管理 ChromaDB 客户端和集合
    """
    
    _instance = None
    _lock = threading.Lock()
    _initialized = False
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(ChromaDBManager, cls).__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not self._initialized:
            try:
                # 使用优化的 ChromaDB 配置（内部会尝试多种配置和降级方案）
                from .chromadb_config import get_optimal_chromadb_client
                self._client = get_optimal_chromadb_client()
                logger.info("✅ ChromaDB 客户端初始化成功")
            except ImportError:
                # 降级：使用默认配置
                logger.warning("⚠️ 无法导入 chromadb_config，使用默认配置")
                try:
                    settings = Settings(
                        allow_reset=True,
                        anonymized_telemetry=False,
                        is_persistent=True,
                        persist_directory="./data/chromadb"
                    )
                    self._client = chromadb.Client(settings)
                    logger.info("✅ ChromaDB 客户端初始化成功（默认配置）")
                except Exception as e:
                    logger.error(f"❌ 默认配置也失败: {e}")
                    # 最后的备用方案：内存模式
                    settings = Settings(
                        allow_reset=True,
                        anonymized_telemetry=False,
                        is_persistent=False
                    )
                    self._client = chromadb.Client(settings)
                    logger.warning("⚠️ ChromaDB 使用内存模式（数据不会持久化）")
            except Exception as e:
                error_msg = str(e)
                logger.error(f"❌ ChromaDB 初始化失败: {error_msg}")
                
                # 🔥 如果是 Rust panic 错误，提供更详细的错误信息和建议
                if "PanicException" in error_msg or "panicked" in error_msg:
                    logger.error("=" * 80)
                    logger.error("❌ ChromaDB Rust Panic 错误")
                    logger.error("   这通常是由以下原因之一引起的：")
                    logger.error("   1. ChromaDB 版本不兼容")
                    logger.error("   2. 数据库文件损坏")
                    logger.error("   3. Windows 路径问题")
                    logger.error("")
                    logger.error("   解决方案：")
                    logger.error("   1. 升级 chromadb: pip install --upgrade chromadb")
                    logger.error("   2. 删除数据库目录: rmdir /s data\\chromadb")
                    logger.error("   3. 使用内存模式（当前会自动降级）")
                    logger.error("=" * 80)
                
                # 最后的备用方案：内存模式
                try:
                    settings = Settings(
                        allow_reset=True,
                        anonymized_telemetry=False,
                        is_persistent=False
                    )
                    self._client = chromadb.Client(settings)
                    logger.warning("⚠️ ChromaDB 已降级到内存模式（数据不会持久化）")
                except Exception as final_error:
                    logger.error(f"❌ 内存模式也失败: {final_error}")
                    logger.error("❌ ChromaDB 完全无法初始化，记忆功能将被禁用")
                    raise RuntimeError(f"ChromaDB 初始化完全失败: {final_error}") from final_error
            
            self._collections = {}
            self._initialized = True
            
            # 🔥 记录 ChromaDB 的运行模式
            try:
                # 检查是否是持久化模式
                if hasattr(self._client, '_settings'):
                    settings = self._client._settings
                    if hasattr(settings, 'is_persistent'):
                        if settings.is_persistent:
                            persist_dir = getattr(settings, 'persist_directory', 'unknown')
                            logger.info(f"📚 ChromaDB 运行模式: 持久化模式 (目录: {persist_dir})")
                        else:
                            logger.info(f"📚 ChromaDB 运行模式: 内存模式（数据不会持久化）")
            except Exception:
                pass  # 忽略检查错误
    
    def get_or_create_collection(self, name: str):
        """线程安全地获取或创建集合"""
        with self._lock:
            if name in self._collections:
                logger.debug(f"📚 使用缓存集合: {name}")
                return self._collections[name]
            
            try:
                # 尝试获取现有集合
                collection = self._client.get_collection(name=name)
                logger.info(f"📚 获取现有集合: {name}")
            except Exception:
                try:
                    # 创建新集合
                    collection = self._client.create_collection(name=name)
                    logger.info(f"📚 创建新集合: {name}")
                except Exception as e:
                    # 可能是并发创建，再次尝试获取
                    try:
                        collection = self._client.get_collection(name=name)
                        logger.info(f"📚 并发创建后获取集合: {name}")
                    except Exception as final_error:
                        logger.error(f"❌ 集合操作失败: {name}, 错误: {final_error}")
                        raise final_error
            
            # 缓存集合
            self._collections[name] = collection
            return collection
    
    def delete_collection(self, name: str):
        """删除集合"""
        with self._lock:
            try:
                self._client.delete_collection(name=name)
                if name in self._collections:
                    del self._collections[name]
                logger.info(f"🗑️ 删除集合: {name}")
            except Exception as e:
                logger.error(f"❌ 删除集合失败: {name}, 错误: {e}")


class AgentMemory:
    """
    Agent 记忆管理器
    
    为单个 Agent 提供记忆存储和检索功能
    """
    
    def __init__(self, agent_id: str, embedding_manager):
        """
        初始化 Agent 记忆
        
        Args:
            agent_id: Agent ID（用作 ChromaDB 集合名称）
            embedding_manager: EmbeddingManager 实例
        """
        self.agent_id = agent_id
        self.embedding_manager = embedding_manager
        
        # 获取或创建 ChromaDB 集合
        self.chroma_manager = ChromaDBManager()
        self.collection = self.chroma_manager.get_or_create_collection(f"memory_{agent_id}")
        
        logger.info(f"🧠 初始化 Agent 记忆: {agent_id}")
    
    def add_memory(
        self,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
        memory_id: Optional[str] = None
    ) -> bool:
        """
        添加记忆
        
        Args:
            content: 记忆内容（文本）
            metadata: 元数据（如时间、股票代码等）
            memory_id: 记忆ID（可选，默认自动生成）
        
        Returns:
            是否成功
        """
        try:
            # 获取 embedding
            embedding, provider = self.embedding_manager.get_embedding(content)
            if embedding is None:
                logger.warning(f"⚠️ 无法获取 embedding，跳过记忆存储")
                return False

            # 生成 ID
            if memory_id is None:
                import hashlib
                import time
                memory_id = hashlib.md5(f"{content[:100]}_{time.time()}".encode()).hexdigest()

            # 准备元数据
            if metadata is None:
                metadata = {}
            metadata["agent_id"] = self.agent_id
            metadata["provider"] = provider

            # 存储到 ChromaDB
            self.collection.add(
                documents=[content],
                embeddings=[embedding],
                metadatas=[metadata],
                ids=[memory_id]
            )

            logger.debug(f"✅ 记忆已存储: {self.agent_id}, ID={memory_id[:8]}...")
            return True

        except Exception as e:
            logger.error(f"❌ 存储记忆失败: {e}")
            return False

    def search_memories(
        self,
        query: str,
        n_results: int = 5,
        filter_metadata: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        搜索相似记忆

        Args:
            query: 查询文本
            n_results: 返回结果数量
            filter_metadata: 元数据过滤条件

        Returns:
            记忆列表，每个记忆包含 content, metadata, similarity
        """
        try:
            # 获取查询的 embedding
            query_embedding, provider = self.embedding_manager.get_embedding(query)
            if query_embedding is None:
                logger.warning(f"⚠️ 无法获取查询 embedding")
                return []

            # 检查集合是否为空
            count = self.collection.count()
            if count == 0:
                logger.debug(f"📭 记忆库为空: {self.agent_id}")
                return []

            # 🔥 重要：确保查询时使用与存储时相同的 Embedding 模型
            # 
            # 原因：
            # 1. 不同模型的向量维度可能不同（DashScope 1024维，OpenAI 1536维等）
            # 2. 不同模型的语义空间不同，即使维度相同也不能互相查询
            # 3. 只有使用相同模型生成的向量才能进行准确的相似度计算
            #
            # 方案：在元数据过滤中添加 provider 过滤，只查询使用相同 provider 的记忆
            if filter_metadata is None:
                filter_metadata = {}
            
            # 🔥 添加 provider 过滤，确保只查询使用相同 Embedding 模型的记忆
            # 注意：
            # - 如果集合中有使用不同 provider 的记忆，它们会被过滤掉
            # - 这意味着切换 Embedding 模型后，只能查询到使用新模型存储的记忆
            # - 旧模型的记忆仍然存在，但不会被查询到（除非切换回旧模型）
            filter_metadata["provider"] = provider
            
            logger.debug(f"🔍 查询记忆（使用 {provider} Embedding 模型，只查询相同 provider 的记忆）")

            # 调整结果数量
            n_results = min(n_results, count)

            # 执行查询
            results = self.collection.query(
                query_embeddings=[query_embedding],
                n_results=n_results,
                where=filter_metadata  # 元数据过滤（包含 provider 过滤）
            )

            # 格式化结果
            memories = []
            if results and 'documents' in results and results['documents']:
                documents = results['documents'][0]
                metadatas = results.get('metadatas', [[]])[0]
                distances = results.get('distances', [[]])[0]

                for i, doc in enumerate(documents):
                    metadata = metadatas[i] if i < len(metadatas) else {}
                    distance = distances[i] if i < len(distances) else 1.0

                    memory = {
                        'content': doc,
                        'metadata': metadata,
                        'similarity': 1.0 - distance,  # 转换为相似度
                        'distance': distance
                    }
                    memories.append(memory)

                logger.debug(f"🔍 找到 {len(memories)} 个相似记忆")

            return memories

        except Exception as e:
            logger.error(f"❌ 搜索记忆失败: {e}")
            return []

    def get_memory_count(self) -> int:
        """获取记忆数量"""
        try:
            return self.collection.count()
        except Exception as e:
            logger.error(f"❌ 获取记忆数量失败: {e}")
            return 0

    def clear_memories(self):
        """清空所有记忆"""
        try:
            self.chroma_manager.delete_collection(f"memory_{self.agent_id}")
            self.collection = self.chroma_manager.get_or_create_collection(f"memory_{self.agent_id}")
            logger.info(f"🗑️ 清空记忆: {self.agent_id}")
        except Exception as e:
            logger.error(f"❌ 清空记忆失败: {e}")


class MemoryManager:
    """
    全局记忆管理器

    管理所有 Agent 的记忆实例
    """

    def __init__(self, embedding_manager):
        """
        初始化记忆管理器

        Args:
            embedding_manager: EmbeddingManager 实例
        """
        self.embedding_manager = embedding_manager
        self._agent_memories: Dict[str, AgentMemory] = {}
        logger.info("🧠 记忆管理器初始化完成")

    def get_agent_memory(self, agent_id: str) -> AgentMemory:
        """
        获取指定 Agent 的记忆实例

        Args:
            agent_id: Agent ID

        Returns:
            AgentMemory 实例
        """
        if agent_id not in self._agent_memories:
            self._agent_memories[agent_id] = AgentMemory(agent_id, self.embedding_manager)

        return self._agent_memories[agent_id]

    def clear_all_memories(self):
        """清空所有 Agent 的记忆"""
        for agent_id, memory in self._agent_memories.items():
            memory.clear_memories()
        logger.info("🗑️ 清空所有记忆")

