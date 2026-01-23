"""
向量数据库统一接口

支持多种向量数据库后端：
- ChromaDB (默认，但有线程安全问题)
- Qdrant (推荐，线程安全)
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Tuple
import logging

logger = logging.getLogger(__name__)


class VectorStoreInterface(ABC):
    """向量数据库统一接口"""

    @abstractmethod
    def add(
        self,
        documents: List[str],
        embeddings: List[List[float]],
        metadatas: List[Dict[str, Any]],
        ids: List[str]
    ) -> bool:
        """
        添加文档到向量数据库

        Args:
            documents: 文档内容列表
            embeddings: 向量列表
            metadatas: 元数据列表
            ids: 文档 ID 列表

        Returns:
            是否成功
        """
        pass

    @abstractmethod
    def query(
        self,
        query_embeddings: List[List[float]],
        n_results: int = 5,
        where: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        查询相似文档

        Args:
            query_embeddings: 查询向量列表
            n_results: 返回结果数量
            where: 元数据过滤条件

        Returns:
            查询结果字典，格式：
            {
                'documents': [[doc1, doc2, ...]],
                'metadatas': [[meta1, meta2, ...]],
                'distances': [[dist1, dist2, ...]]
            }
        """
        pass

    @abstractmethod
    def count(self) -> int:
        """
        获取文档数量

        Returns:
            文档数量
        """
        pass

    @abstractmethod
    def delete_collection(self) -> bool:
        """
        删除集合

        Returns:
            是否成功
        """
        pass

    @abstractmethod
    def get_backend_name(self) -> str:
        """
        获取后端名称

        Returns:
            后端名称（chromadb, qdrant 等）
        """
        pass

