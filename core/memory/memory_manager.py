"""
Memory 管理器 v2.0

支持多种向量数据库后端的记忆系统，用于存储和检索 Agent 的历史经验。

支持的后端：
- MongoDB (默认，与业务数据统一存储，客户端 cosine 相似度)
- Qdrant (可选回退，服务器模式适合大数据量)
- ChromaDB (有线程安全问题，不推荐)

特性：
- 支持多个 Agent 的独立记忆空间
- 基于语义相似度的记忆检索
- 自动管理向量数据库集合
- 与 EmbeddingManager 集成
- 通过环境变量切换后端
"""

import logging
import os
import queue
import asyncio
import threading
from typing import List, Dict, Any, Optional, Tuple

logger = logging.getLogger(__name__)


_MEM0_COMPAT_DEFAULT_USER_ID = "legacy_tradingagents"
_AGENT_ID_ALIAS_MAPPING = {
    "bull_researcher": ["bull_researcher_v2", "bull_researcher"],
    "bull_researcher_v2": ["bull_researcher_v2", "bull_researcher"],
    "bear_researcher": ["bear_researcher_v2", "bear_researcher"],
    "bear_researcher_v2": ["bear_researcher_v2", "bear_researcher"],
    "trader": ["trader_v2", "trader"],
    "trader_v2": ["trader_v2", "trader"],
    "research_manager": ["research_manager_v2", "research_manager"],
    "research_manager_v2": ["research_manager_v2", "research_manager"],
    "risk_manager": ["risk_manager_v2", "risk_manager"],
    "risk_manager_v2": ["risk_manager_v2", "risk_manager"],
}


def _is_truthy(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _run_async_sync(coro):
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)

    result: dict[str, Any] = {}
    error: dict[str, BaseException] = {}
    done = threading.Event()

    def _runner() -> None:
        try:
            result["value"] = asyncio.run(coro)
        except BaseException as exc:  # pragma: no cover - 仅用于跨线程异常传递
            error["value"] = exc
        finally:
            done.set()

    thread = threading.Thread(target=_runner, daemon=True)
    thread.start()
    done.wait()
    if "value" in error:
        raise error["value"]
    return result.get("value")


class Mem0AgentMemory:
    """为 v2 AgentMemory 接口提供 mem0 兼容层。"""

    def __init__(self, agent_id: str):
        self.agent_id = agent_id
        self.agent_ids = list(dict.fromkeys(_AGENT_ID_ALIAS_MAPPING.get(agent_id, [agent_id])))

    def _resolve_user_id(self) -> str:
        return str(os.getenv("MEM0_COMPAT_USER_ID") or _MEM0_COMPAT_DEFAULT_USER_ID).strip() or _MEM0_COMPAT_DEFAULT_USER_ID

    @staticmethod
    def _normalize_store_metadata(metadata: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        merged = dict(metadata or {})
        ticker = str(merged.get("ticker") or merged.get("symbol") or "").strip().upper()
        if ticker:
            merged["ticker"] = ticker
            merged.setdefault("symbol", ticker)
            merged.setdefault("object_type", "stock")
            merged.setdefault("object_key", ticker)
        merged.setdefault("source", "legacy_agent_memory_runtime")
        return merged

    @staticmethod
    def _normalize_recall_filters(filter_metadata: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        if not filter_metadata:
            return None
        merged = dict(filter_metadata)
        ticker = str(merged.get("ticker") or merged.get("symbol") or "").strip().upper()
        if ticker:
            merged["ticker"] = ticker
            merged.setdefault("symbol", ticker)
        return merged

    def add_memory(
        self,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
        memory_id: Optional[str] = None,
    ) -> bool:
        del memory_id
        try:
            from .service import get_memory_service

            svc = get_memory_service()
            result = _run_async_sync(
                svc.store(
                    [{"role": "user", "content": str(content or "")}],
                    user_id=self._resolve_user_id(),
                    agent_id=self.agent_ids[0],
                    session_id=str((metadata or {}).get("ticker") or self.agent_id),
                    scope="agent_experience",
                    metadata=self._normalize_store_metadata(metadata),
                    infer=False,
                )
            )
            if result.success:
                logger.info("✅ mem0 AgentMemory 写入成功 agent_id=%s", self.agent_ids[0])
                return True
            raise RuntimeError(result.error or "mem0 store failed")
        except Exception as exc:
            logger.warning("⚠️ mem0 AgentMemory 写入失败 %s: %s", self.agent_id, exc)
        return False

    def search_memories(
        self,
        query: str,
        n_results: int = 5,
        filter_metadata: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        try:
            from .service import get_memory_service

            svc = get_memory_service()
            memories: List[Dict[str, Any]] = []
            seen_memory_ids = set()
            normalized_filters = self._normalize_recall_filters(filter_metadata)
            for agent_id in self.agent_ids:
                recalled = _run_async_sync(
                    svc.recall(
                        query=str(query or ""),
                        user_id=self._resolve_user_id(),
                        agent_id=agent_id,
                        scopes=["agent_experience"],
                        metadata_filters=normalized_filters,
                        limit=n_results,
                    )
                )
                for item in recalled or []:
                    memory_id = getattr(item, "id", None)
                    if memory_id and memory_id in seen_memory_ids:
                        continue
                    if memory_id:
                        seen_memory_ids.add(memory_id)
                    memories.append({
                        "content": item.metadata.get("legacy_situation") or item.memory,
                        "metadata": item.metadata,
                        "similarity": item.score,
                        "distance": max(0.0, 1.0 - float(item.score or 0.0)),
                    })
                    if len(memories) >= n_results:
                        break
                if len(memories) >= n_results:
                    break
            if memories:
                logger.info("✅ mem0 AgentMemory 命中 agent_id=%s recalled=%d aliases=%s", self.agent_id, len(memories), self.agent_ids)
                return memories
            logger.info("📭 mem0 AgentMemory 未命中 agent_id=%s aliases=%s", self.agent_id, self.agent_ids)
        except Exception as exc:
            logger.warning("⚠️ mem0 AgentMemory 召回失败 %s: %s", self.agent_id, exc)
        return []

    def get_memory_count(self) -> int:
        return 0

    def clear_memories(self):
        return None


class VectorStoreManager:
    """
    向量数据库管理器（单例）

    支持多种后端：
    - mongodb (默认，与业务数据统一存储，客户端 cosine 相似度)
    - qdrant (可选回退，服务器模式适合大数据量)
    - chromadb (有线程安全问题，不推荐)

    通过环境变量 VECTOR_STORE_BACKEND 切换后端
    """

    _instance = None
    _initialized = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(VectorStoreManager, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        if not self._initialized:
            # 读取后端配置（默认使用 mongodb，减少运维组件）
            backend = os.getenv("VECTOR_STORE_BACKEND", "mongodb").lower()
            self.backend = backend

            try:
                if backend == "mongodb":
                    from .mongodb_vector_adapter import MongoDBVectorAdapter
                    self._adapter = MongoDBVectorAdapter()
                    logger.info("✅ 向量数据库后端: MongoDB (客户端 cosine，与业务数据统一存储)")
                elif backend == "qdrant":
                    from .qdrant_adapter import QdrantAdapter
                    self._adapter = QdrantAdapter()
                    logger.info("✅ 向量数据库后端: Qdrant (线程安全)")
                elif backend == "chromadb":
                    from .chromadb_adapter import ChromaDBAdapter
                    self._adapter = ChromaDBAdapter()
                    logger.warning("⚠️ 向量数据库后端: ChromaDB (有线程安全问题，不推荐)")
                else:
                    logger.error(f"❌ 不支持的向量数据库后端: {backend}，使用默认 MongoDB")
                    from .mongodb_vector_adapter import MongoDBVectorAdapter
                    self._adapter = MongoDBVectorAdapter()
                    self.backend = "mongodb"

                VectorStoreManager._initialized = True

            except ImportError as e:
                logger.error(f"❌ 向量数据库后端初始化失败: {e}")
                raise

    def get_or_create_collection(self, name: str, vector_size: int = 1024):
        """
        获取或创建集合

        Args:
            name: 集合名称
            vector_size: 向量维度（默认 1024，兼容更多 embedding 模型）

        Returns:
            集合对象（实现 VectorStoreInterface）
        """
        return self._adapter.get_or_create_collection(name, vector_size)

    def delete_collection(self, name: str) -> bool:
        """
        删除集合

        Args:
            name: 集合名称

        Returns:
            是否成功
        """
        return self._adapter.delete_collection(name)


class AgentMemory:
    """
    Agent 记忆管理器

    为单个 Agent 提供记忆存储和检索功能。

    记忆写入（add_memory）为异步非阻塞操作：
    - 调用 add_memory() 会将任务提交到后台队列，立即返回
    - 后台守护线程依次处理队列中的 embedding 生成 + 向量存储
    - 避免分析主流程被 embedding API 调用和磁盘写入阻塞
    """

    # 所有 AgentMemory 实例共享的后台工作线程和队列（节省线程资源）
    _shared_queue: Optional[queue.Queue] = None
    _shared_worker: Optional[threading.Thread] = None
    _shared_lock = threading.Lock()

    def __init__(self, agent_id: str, embedding_manager):
        """
        初始化 Agent 记忆

        Args:
            agent_id: Agent ID（用作向量数据库集合名称）
            embedding_manager: EmbeddingManager 实例
        """
        self.agent_id = agent_id
        self.embedding_manager = embedding_manager

        # 获取或创建向量数据库集合
        self.vector_store_manager = VectorStoreManager()

        # 获取 embedding 维度
        vector_size = 1024  # 🔥 默认维度 1024（兼容更多模型）
        if hasattr(embedding_manager, 'get_embedding_dimension'):
            vector_size = embedding_manager.get_embedding_dimension()

        self.collection = self.vector_store_manager.get_or_create_collection(
            f"memory_{agent_id}",
            vector_size=vector_size
        )

        backend = self.vector_store_manager.backend
        logger.info(f"🧠 初始化 Agent 记忆: {agent_id} (后端: {backend})")

        # 确保共享后台工作线程已启动
        self._ensure_worker_started()

    @classmethod
    def _ensure_worker_started(cls):
        """确保共享后台工作线程已启动（线程安全）"""
        if cls._shared_worker is not None and cls._shared_worker.is_alive():
            return
        with cls._shared_lock:
            if cls._shared_worker is not None and cls._shared_worker.is_alive():
                return
            cls._shared_queue = queue.Queue(maxsize=500)
            cls._shared_worker = threading.Thread(
                target=cls._worker_loop,
                name="memory-save-worker",
                daemon=True,
            )
            cls._shared_worker.start()
            logger.info("🚀 记忆后台保存线程已启动")

    @classmethod
    def _worker_loop(cls):
        """后台线程：持续从队列取任务并执行同步写入"""
        while True:
            try:
                task = cls._shared_queue.get()
                if task is None:
                    # 收到哨兵值，退出
                    logger.info("🛑 记忆后台保存线程收到退出信号")
                    break
                agent_memory, content, metadata, memory_id = task
                agent_memory._do_add_memory(content, metadata, memory_id)
            except Exception as e:
                logger.error(f"❌ 记忆后台保存线程异常: {e}", exc_info=True)
            finally:
                try:
                    cls._shared_queue.task_done()
                except ValueError:
                    pass

    def add_memory(
        self,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
        memory_id: Optional[str] = None
    ) -> bool:
        """
        添加记忆（非阻塞）

        将任务提交到后台队列，立即返回。后台线程负责实际的
        embedding 生成和向量存储操作。

        Args:
            content: 记忆内容（文本）
            metadata: 元数据（如时间、股票代码等）
            memory_id: 记忆ID（可选，默认自动生成）

        Returns:
            是否成功入队（True=已提交，False=队列已满或异常）
        """
        try:
            self._ensure_worker_started()
            self._shared_queue.put_nowait((self, content, metadata, memory_id))
            logger.debug(f"📨 记忆已提交到后台队列: {self.agent_id} (队列长度: {self._shared_queue.qsize()})")
            return True
        except queue.Full:
            logger.warning(f"⚠️ 记忆保存队列已满，跳过: {self.agent_id}")
            return False
        except Exception as e:
            logger.error(f"❌ 提交记忆到队列失败: {e}")
            return False

    def _do_add_memory(
        self,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
        memory_id: Optional[str] = None
    ) -> bool:
        """
        实际执行记忆写入（在后台线程中调用）

        Args:
            content: 记忆内容（文本）
            metadata: 元数据
            memory_id: 记忆ID
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

            # 存储到向量数据库（适配器内部已处理线程安全）
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

            # 🔥 修复 ChromaDB 查询语法问题
            # ChromaDB 的 where 查询语法要求：
            # - 单个条件：{"key": "value"}
            # - 多个条件：{"$and": [{"key1": "value1"}, {"key2": "value2"}]}
            # 不能直接传递包含多个键的字典
            where_clause = None
            if len(filter_metadata) == 1:
                # 单个条件，直接使用
                key, value = next(iter(filter_metadata.items()))
                where_clause = {key: value}
            elif len(filter_metadata) > 1:
                # 多个条件，使用 $and 操作符
                where_clause = {
                    "$and": [{key: value} for key, value in filter_metadata.items()]
                }
            # 如果 filter_metadata 为空，where_clause 为 None，不进行过滤

            # 检查集合是否为空（适配器内部已处理线程安全）
            count = self.collection.count()
            if count == 0:
                logger.debug(f"📭 记忆库为空: {self.agent_id}")
                return []

            # 调整结果数量
            n_results = min(n_results, count)

            # 执行查询
            query_kwargs = {
                "query_embeddings": [query_embedding],
                "n_results": n_results,
            }
            if where_clause is not None:
                query_kwargs["where"] = where_clause

            results = self.collection.query(**query_kwargs)

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
            # 适配器内部已处理线程安全
            count = self.collection.count()
            return count
        except Exception as e:
            logger.error(f"❌ 获取记忆数量失败: {e}")
            return 0

    def clear_memories(self):
        """清空所有记忆"""
        try:
            # 适配器内部已处理线程安全
            # 删除旧集合
            self.vector_store_manager.delete_collection(f"memory_{self.agent_id}")

            # 重新创建集合
            vector_size = 1024  # 🔥 默认维度 1024（兼容更多模型）
            if hasattr(self.embedding_manager, 'get_embedding_dimension'):
                vector_size = self.embedding_manager.get_embedding_dimension()

            self.collection = self.vector_store_manager.get_or_create_collection(
                f"memory_{self.agent_id}",
                vector_size=vector_size
            )
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
        self._agent_memories: Dict[str, Any] = {}
        self._use_mem0_compat = str(os.getenv("MEMORY_USE_MEM0_COMPAT", "true")).strip().lower() in {"1", "true", "yes", "on"}
        # A3: mem0 实例构造非线程安全（并发构造 AsyncMemory 会死锁），
        # get_agent_memory 的 check-then-create 需串行化（并行开局场景两研究员同时取记忆）
        self._memory_lock = threading.Lock()
        logger.info("🧠 记忆管理器初始化完成")
        if not self._use_mem0_compat:
            logger.warning("⚠️ MemoryManager 当前显式使用 legacy-only AgentMemory 路径，建议迁回 mem0 主路径")

    def get_agent_memory(self, agent_id: str) -> Any:
        """
        获取指定 Agent 的记忆实例（线程安全：mem0 构造串行化）

        Args:
            agent_id: Agent ID

        Returns:
            AgentMemory 实例
        """
        with self._memory_lock:
            if agent_id not in self._agent_memories:
                if self._use_mem0_compat:
                    self._agent_memories[agent_id] = Mem0AgentMemory(agent_id)
                else:
                    self._agent_memories[agent_id] = AgentMemory(agent_id, self.embedding_manager)

        return self._agent_memories[agent_id]

    def clear_all_memories(self):
        """清空所有 Agent 的记忆"""
        for agent_id, memory in self._agent_memories.items():
            memory.clear_memories()
        logger.info("🗑️ 清空所有记忆")

