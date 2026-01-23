"""
Qdrant 向量数据库适配器

特性：
- 完全线程安全（Rust 实现）
- 支持本地模式（无需服务器）
- 自动持久化
- 支持元数据过滤
"""

import logging
import os
from typing import List, Dict, Any, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


class QdrantAdapter:
    """Qdrant 向量数据库适配器"""

    _instance = None
    _initialized = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(QdrantAdapter, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        if not self._initialized:
            try:
                from qdrant_client import QdrantClient
                from qdrant_client.models import Distance, VectorParams, PointStruct

                self.QdrantClient = QdrantClient
                self.Distance = Distance
                self.VectorParams = VectorParams
                self.PointStruct = PointStruct

                # 确定数据目录
                data_dir = os.getenv("QDRANT_DATA_DIR", "./data/qdrant")
                Path(data_dir).mkdir(parents=True, exist_ok=True)

                # 创建本地客户端
                self._client = QdrantClient(path=data_dir)
                logger.info(f"✅ Qdrant 客户端初始化成功 (本地模式: {data_dir})")

                QdrantAdapter._initialized = True

            except ImportError:
                logger.error("❌ Qdrant 未安装，请运行: pip install qdrant-client")
                raise
            except Exception as e:
                logger.error(f"❌ Qdrant 初始化失败: {e}")
                raise

    def get_or_create_collection(self, collection_name: str, vector_size: int = 1536):
        """
        获取或创建集合

        Args:
            collection_name: 集合名称
            vector_size: 向量维度（默认 1536，OpenAI embedding 维度）

        Returns:
            QdrantCollection 实例
        """
        return QdrantCollection(self._client, collection_name, vector_size, self)

    def delete_collection(self, collection_name: str) -> bool:
        """
        删除集合

        Args:
            collection_name: 集合名称

        Returns:
            是否成功
        """
        try:
            self._client.delete_collection(collection_name)
            logger.info(f"✅ Qdrant 集合已删除: {collection_name}")
            return True
        except Exception as e:
            logger.error(f"❌ 删除 Qdrant 集合失败: {e}")
            return False


class QdrantCollection:
    """Qdrant 集合包装类，实现 VectorStoreInterface"""

    def __init__(self, client, collection_name: str, vector_size: int, adapter):
        self.client = client
        self.collection_name = collection_name
        self.vector_size = vector_size
        self.adapter = adapter

        # 检查集合是否存在
        collection_exists = False
        need_recreate = False

        try:
            collection_info = self.client.get_collection(collection_name)
            collection_exists = True

            # 🔥 检查向量维度是否匹配
            existing_vector_size = collection_info.config.params.vectors.size
            if existing_vector_size != vector_size:
                logger.warning(
                    f"⚠️ Qdrant 集合 {collection_name} 的向量维度不匹配！"
                    f"现有: {existing_vector_size}, 需要: {vector_size}"
                )
                logger.info(f"🔄 将删除并重新创建集合...")
                need_recreate = True
            else:
                logger.debug(f"📂 Qdrant 集合已存在: {collection_name} (向量维度: {existing_vector_size})")
        except Exception as e:
            # 集合不存在
            logger.debug(f"📂 Qdrant 集合不存在: {collection_name}，将创建新集合")

        # 如果需要重新创建，先删除旧集合
        if need_recreate:
            try:
                self.client.delete_collection(collection_name)
                logger.info(f"🗑️ 已删除旧集合: {collection_name}")
                collection_exists = False
            except Exception as e:
                logger.error(f"❌ 删除旧集合失败: {e}")
                raise

        # 创建新集合（如果不存在）
        if not collection_exists or need_recreate:
            self.client.create_collection(
                collection_name=collection_name,
                vectors_config=adapter.VectorParams(
                    size=vector_size,
                    distance=adapter.Distance.COSINE
                )
            )
            logger.info(f"✅ Qdrant 集合已创建: {collection_name} (向量维度: {vector_size})")

    def add(
        self,
        documents: List[str],
        embeddings: List[List[float]],
        metadatas: List[Dict[str, Any]],
        ids: List[str]
    ) -> bool:
        """添加文档"""
        try:
            logger.debug(f"🔒 [Qdrant] 准备添加文档 (collection={self.collection_name}, count={len(documents)})")

            # 构建 Qdrant 点
            points = []
            for i, (doc_id, embedding, metadata, document) in enumerate(zip(ids, embeddings, metadatas, documents)):
                # 将文档内容也存入 payload
                payload = metadata.copy()
                payload["document"] = document

                point = self.adapter.PointStruct(
                    id=doc_id,
                    vector=embedding,
                    payload=payload
                )
                points.append(point)

            # 批量上传
            self.client.upsert(
                collection_name=self.collection_name,
                points=points
            )

            logger.debug(f"✅ [Qdrant] 文档添加成功 (collection={self.collection_name}, count={len(documents)})")
            return True

        except Exception as e:
            logger.error(f"❌ [Qdrant] 添加文档失败: {e}")
            return False

    def query(
        self,
        query_embeddings: List[List[float]],
        n_results: int = 5,
        where: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """查询相似文档"""
        try:
            logger.debug(f"🔒 [Qdrant] 准备查询 (collection={self.collection_name}, n_results={n_results})")

            # Qdrant 只支持单个查询向量，取第一个
            query_vector = query_embeddings[0] if query_embeddings else []

            # 构建过滤条件
            from qdrant_client.models import Filter, FieldCondition, MatchValue

            query_filter = None
            if where:
                # 将 ChromaDB 风格的 where 转换为 Qdrant Filter
                conditions = []
                for key, value in where.items():
                    if key == "$and":
                        # 处理 $and 操作符
                        for condition in value:
                            for k, v in condition.items():
                                conditions.append(
                                    FieldCondition(key=k, match=MatchValue(value=v))
                                )
                    else:
                        conditions.append(
                            FieldCondition(key=key, match=MatchValue(value=value))
                        )

                if conditions:
                    query_filter = Filter(must=conditions)

            # 执行搜索
            search_results = self.client.search(
                collection_name=self.collection_name,
                query_vector=query_vector,
                limit=n_results,
                query_filter=query_filter
            )

            logger.debug(f"✅ [Qdrant] 查询成功 (collection={self.collection_name}, results={len(search_results)})")

            # 转换为 ChromaDB 格式
            documents = []
            metadatas = []
            distances = []

            for result in search_results:
                # 提取文档内容
                document = result.payload.get("document", "")
                documents.append(document)

                # 提取元数据（移除 document 字段）
                metadata = {k: v for k, v in result.payload.items() if k != "document"}
                metadatas.append(metadata)

                # Qdrant 返回的是相似度分数（越高越相似），转换为距离（越低越相似）
                # 对于 COSINE 距离：distance = 1 - score
                distance = 1.0 - result.score
                distances.append(distance)

            return {
                'documents': [documents],  # ChromaDB 格式是二维数组
                'metadatas': [metadatas],
                'distances': [distances]
            }

        except Exception as e:
            logger.error(f"❌ [Qdrant] 查询失败: {e}")
            return {'documents': [[]], 'metadatas': [[]], 'distances': [[]]}

    def count(self) -> int:
        """获取文档数量"""
        try:
            logger.debug(f"🔒 [Qdrant] 准备获取文档数量 (collection={self.collection_name})")
            collection_info = self.client.get_collection(self.collection_name)
            count = collection_info.points_count
            logger.debug(f"✅ [Qdrant] 文档数量: {count}")
            return count
        except Exception as e:
            logger.error(f"❌ [Qdrant] 获取文档数量失败: {e}")
            return 0

    def delete_collection(self) -> bool:
        """删除集合"""
        try:
            logger.debug(f"🔒 [Qdrant] 准备删除集合 (collection={self.collection_name})")
            self.client.delete_collection(self.collection_name)
            logger.debug(f"✅ [Qdrant] 集合已删除 (collection={self.collection_name})")
            return True
        except Exception as e:
            logger.error(f"❌ [Qdrant] 删除集合失败: {e}")
            return False

    def get_backend_name(self) -> str:
        """获取后端名称"""
        return "qdrant"

