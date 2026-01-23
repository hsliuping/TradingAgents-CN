"""
ChromaDB 向量数据库适配器

特性：
- 轻量级，易于使用
- 支持本地持久化

⚠️ 警告：
- Rust 扩展在多线程环境下不是线程安全的
- 可能导致 Windows 访问冲突崩溃
- 建议使用 Qdrant 替代
"""

import logging
import threading
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)


class ChromaDBAdapter:
    """ChromaDB 向量数据库适配器"""

    _instance = None
    _lock = threading.Lock()
    _initialized = False
    _chroma_operation_lock = threading.Lock()  # 🔒 ChromaDB 操作锁（保护 Rust 扩展）

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(ChromaDBAdapter, cls).__new__(cls)
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
                import chromadb
                from chromadb.config import Settings

                self._client = chromadb.Client(Settings(
                    anonymized_telemetry=False,
                    allow_reset=True
                ))
                logger.info("✅ ChromaDB 客户端初始化成功（默认配置）")

            ChromaDBAdapter._initialized = True

    def get_or_create_collection(self, collection_name: str, vector_size: int = 1536):
        """
        获取或创建集合

        Args:
            collection_name: 集合名称
            vector_size: 向量维度（ChromaDB 会自动检测，此参数仅用于兼容性）

        Returns:
            ChromaDBCollection 实例
        """
        collection = self._client.get_or_create_collection(name=collection_name)
        return ChromaDBCollection(collection, collection_name)

    def delete_collection(self, collection_name: str) -> bool:
        """
        删除集合

        Args:
            collection_name: 集合名称

        Returns:
            是否成功
        """
        try:
            with ChromaDBAdapter._chroma_operation_lock:
                self._client.delete_collection(name=collection_name)
            logger.info(f"✅ ChromaDB 集合已删除: {collection_name}")
            return True
        except Exception as e:
            logger.error(f"❌ 删除 ChromaDB 集合失败: {e}")
            return False


class ChromaDBCollection:
    """ChromaDB 集合包装类，实现 VectorStoreInterface"""

    def __init__(self, collection, collection_name: str):
        self.collection = collection
        self.collection_name = collection_name

    def add(
        self,
        documents: List[str],
        embeddings: List[List[float]],
        metadatas: List[Dict[str, Any]],
        ids: List[str]
    ) -> bool:
        """添加文档"""
        try:
            logger.debug(f"🔒 [ChromaDB] 准备获取锁 - add (collection={self.collection_name})")
            with ChromaDBAdapter._chroma_operation_lock:
                logger.debug(f"🔓 [ChromaDB] 已获取锁 - add (collection={self.collection_name})")
                self.collection.add(
                    documents=documents,
                    embeddings=embeddings,
                    metadatas=metadatas,
                    ids=ids
                )
                logger.debug(f"✅ [ChromaDB] add 操作完成 (collection={self.collection_name}, count={len(documents)})")
            logger.debug(f"🔓 [ChromaDB] 已释放锁 - add (collection={self.collection_name})")
            return True

        except Exception as e:
            logger.error(f"❌ [ChromaDB] 添加文档失败: {e}")
            return False

    def query(
        self,
        query_embeddings: List[List[float]],
        n_results: int = 5,
        where: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """查询相似文档"""
        try:
            logger.debug(f"🔒 [ChromaDB] 准备获取锁 - query (collection={self.collection_name})")
            with ChromaDBAdapter._chroma_operation_lock:
                logger.debug(f"🔓 [ChromaDB] 已获取锁 - query (collection={self.collection_name})")

                query_kwargs = {
                    "query_embeddings": query_embeddings,
                    "n_results": n_results,
                }
                if where is not None:
                    query_kwargs["where"] = where

                results = self.collection.query(**query_kwargs)
                logger.debug(f"✅ [ChromaDB] query 操作完成 (collection={self.collection_name})")
            logger.debug(f"🔓 [ChromaDB] 已释放锁 - query (collection={self.collection_name})")
            return results

        except Exception as e:
            logger.error(f"❌ [ChromaDB] 查询失败: {e}")
            return {'documents': [[]], 'metadatas': [[]], 'distances': [[]]}

    def count(self) -> int:
        """获取文档数量"""
        try:
            logger.debug(f"🔒 [ChromaDB] 准备获取锁 - count (collection={self.collection_name})")
            with ChromaDBAdapter._chroma_operation_lock:
                logger.debug(f"🔓 [ChromaDB] 已获取锁 - count (collection={self.collection_name})")
                count = self.collection.count()
                logger.debug(f"✅ [ChromaDB] count 操作完成 (collection={self.collection_name}, count={count})")
            logger.debug(f"🔓 [ChromaDB] 已释放锁 - count (collection={self.collection_name})")
            return count
        except Exception as e:
            logger.error(f"❌ [ChromaDB] 获取文档数量失败: {e}")
            return 0

    def delete_collection(self) -> bool:
        """删除集合"""
        try:
            logger.debug(f"🔒 [ChromaDB] 准备获取锁 - delete_collection (collection={self.collection_name})")
            with ChromaDBAdapter._chroma_operation_lock:
                logger.debug(f"🔓 [ChromaDB] 已获取锁 - delete_collection (collection={self.collection_name})")
                # ChromaDB 的 collection 对象没有 delete 方法，需要通过 client 删除
                # 这里只是标记，实际删除由 ChromaDBAdapter.delete_collection 完成
                logger.debug(f"✅ [ChromaDB] delete_collection 操作完成 (collection={self.collection_name})")
            logger.debug(f"🔓 [ChromaDB] 已释放锁 - delete_collection (collection={self.collection_name})")
            return True
        except Exception as e:
            logger.error(f"❌ [ChromaDB] 删除集合失败: {e}")
            return False

    def get_backend_name(self) -> str:
        """获取后端名称"""
        return "chromadb"

