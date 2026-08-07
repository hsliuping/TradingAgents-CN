"""
mem0 自定义 MongoDB 向量存储（客户端 cosine 相似度）

替代 mem0 官方的 mem0.vector_stores.mongodb.MongoDB（依赖 Atlas $vectorSearch）。
使用 MongoDB Community Edition 存储向量，Python 端用 numpy 计算 cosine 相似度。

注册方式：在 mem0 初始化前，将 VectorStoreFactory.provider_to_class["mongodb"]
指向本模块的 MongoDBClientCosine 类。

文档结构（与官方 mem0 MongoDB 一致，保证未来可切回 Atlas）：
{
    "_id": "uuid-string",
    "embedding": [0.1, 0.2, ...],
    "payload": {
        "data": "原始文本",
        "memory": "提取后记忆",
        "user_id": "...",
        "agent_id": "...",
        "scope": "...",
        ...其他 metadata
    }
}
"""

import logging
import uuid
from typing import Any, Dict, List, Optional

import numpy as np
from pydantic import BaseModel
from pymongo import MongoClient, UpdateOne

logger = logging.getLogger(__name__)


class OutputData(BaseModel):
    """与 mem0 官方 OutputData 完全一致的数据模型"""
    id: Optional[str] = None
    score: Optional[float] = None
    payload: Optional[dict] = None


class MongoDBClientCosine:
    """
    mem0 VectorStoreBase 兼容的 MongoDB 向量存储（客户端 cosine）。

    构造函数签名与 mem0 官方 MongoDB 类一致，便于无缝替换：
        MongoDBClientCosine(db_name, collection_name, embedding_model_dims, mongo_uri)
    """

    VECTOR_TYPE = "vector"
    SIMILARITY_METRIC = "cosine"

    def __init__(
        self,
        db_name: str,
        collection_name: str,
        embedding_model_dims: int,
        mongo_uri: str,
    ):
        self.collection_name = collection_name
        self.embedding_model_dims = embedding_model_dims
        self.db_name = db_name
        self.mongo_uri = mongo_uri

        self.client = MongoClient(mongo_uri)
        self.db = self.client[db_name]
        self.collection = self._get_or_create_collection()

    def _get_or_create_collection(self):
        """获取或创建 collection（幂等，不依赖 Atlas Search Index）"""
        database = self.client[self.db_name]
        collection_names = database.list_collection_names(authorizedCollections=True)
        if self.collection_name not in collection_names:
            logger.info(
                "[mem0-mongodb] Collection '%s' 不存在，自动创建",
                self.collection_name,
            )
            collection = database[self.collection_name]
            # 插入并删除占位文档以创建 collection
            collection.insert_one({"_id": "placeholder", "placeholder": True})
            collection.delete_one({"_id": "placeholder"})
        else:
            collection = database[self.collection_name]

        # 创建常用字段索引（加速 metadata 过滤）
        try:
            collection.create_index("payload.user_id")
            collection.create_index("payload.agent_id")
            collection.create_index("payload.scope")
            collection.create_index("payload.run_id")
        except Exception as e:
            logger.debug("[mem0-mongodb] 创建索引跳过: %s", e)

        return collection

    # ------------------------------------------------------------------
    # VectorStoreBase 接口实现
    # ------------------------------------------------------------------

    def create_col(self, name=None, vector_size=None, distance=None):
        """创建 collection（mem0 调用，但我们在 __init__ 已创建）"""
        # 如果 name 与当前不同，切换 collection
        if name and name != self.collection_name:
            self.collection_name = name
            self.collection = self._get_or_create_collection()
        return self.collection

    def insert(
        self,
        vectors: List[List[float]],
        payloads: Optional[List[Dict]] = None,
        ids: Optional[List[str]] = None,
    ) -> None:
        """插入向量（upsert 语义）"""
        operations = []
        for vector, payload, _id in zip(
            vectors,
            payloads or [{}] * len(vectors),
            ids or [None] * len(vectors),
        ):
            doc_id = _id or str(uuid.uuid4())
            operations.append(
                UpdateOne(
                    {"_id": doc_id},
                    {
                        "$set": {
                            "embedding": vector,
                            "payload": payload or {},
                        }
                    },
                    upsert=True,
                )
            )

        if operations:
            try:
                self.collection.bulk_write(operations, ordered=False)
                logger.debug(
                    "[mem0-mongodb] 插入 %d 条 (collection=%s)",
                    len(operations),
                    self.collection_name,
                )
            except Exception as e:
                logger.error("[mem0-mongodb] 插入失败: %s", e)

    def search(
        self,
        query: str,
        vectors: List[float],
        top_k: int = 5,
        filters: Optional[Dict] = None,
    ) -> List[OutputData]:
        """向量相似度搜索（客户端 cosine）

        返回 List[OutputData]，score 为相似度（越大越相似，范围 [0, 1]）。
        """
        try:
            if not vectors:
                return []

            query_vector = np.array(vectors, dtype=np.float32)
            query_norm = np.linalg.norm(query_vector)
            if query_norm == 0:
                return []

            # 构建 MongoDB 查询过滤器（基于 payload 子文档）
            mongo_filter = self._build_mongo_filter(filters)

            # 读取所有文档（含 embedding）
            cursor = self.collection.find(
                mongo_filter,
                {"_id": 1, "embedding": 1, "payload": 1},
            )

            docs = list(cursor)
            if not docs:
                return []

            # 构建向量矩阵，计算 cosine 相似度
            valid_docs = []
            vectors_list = []
            for doc in docs:
                emb = doc.get("embedding")
                if not emb or not isinstance(emb, list):
                    continue
                # 跳过零向量（签名 point 等）
                if all(v == 0.0 for v in emb):
                    continue
                vectors_list.append(emb)
                valid_docs.append(doc)

            if not valid_docs:
                return []

            matrix = np.array(vectors_list, dtype=np.float32)
            matrix_norms = np.linalg.norm(matrix, axis=1)

            # 过滤零范数行
            valid_mask = matrix_norms > 0
            if not np.any(valid_mask):
                return []

            valid_matrix = matrix[valid_mask]
            valid_docs_filtered = [d for d, v in zip(valid_docs, valid_mask) if v]
            valid_norms = matrix_norms[valid_mask]

            similarities = np.dot(valid_matrix, query_vector) / (valid_norms * query_norm)

            # top-k
            top_k = min(top_k, len(similarities))
            top_indices = np.argsort(similarities)[::-1][:top_k]

            results = []
            for idx in top_indices:
                doc = valid_docs_filtered[idx]
                results.append(
                    OutputData(
                        id=str(doc["_id"]),
                        score=float(similarities[idx]),
                        payload=doc.get("payload"),
                    )
                )

            logger.debug(
                "[mem0-mongodb] 搜索完成 query='%s...' found=%d",
                str(query)[:30],
                len(results),
            )
            return results

        except Exception as e:
            logger.error("[mem0-mongodb] 搜索失败 query=%s: %s", query, e)
            return []

    def delete(self, vector_id: str) -> None:
        """按 ID 删除"""
        try:
            result = self.collection.delete_one({"_id": vector_id})
            if result.deleted_count > 0:
                logger.debug("[mem0-mongodb] 删除成功 id=%s", vector_id)
            else:
                logger.warning("[mem0-mongodb] 未找到要删除的 id=%s", vector_id)
        except Exception as e:
            logger.error("[mem0-mongodb] 删除失败: %s", e)

    def update(
        self,
        vector_id: str,
        vector: Optional[List[float]] = None,
        payload: Optional[Dict] = None,
    ) -> None:
        """更新向量和 payload"""
        update_fields = {}
        if vector is not None:
            update_fields["embedding"] = vector
        if payload is not None:
            update_fields["payload"] = payload

        if update_fields:
            try:
                result = self.collection.update_one(
                    {"_id": vector_id}, {"$set": update_fields}
                )
                if result.matched_count > 0:
                    logger.debug("[mem0-mongodb] 更新成功 id=%s", vector_id)
                else:
                    logger.warning("[mem0-mongodb] 未找到要更新的 id=%s", vector_id)
            except Exception as e:
                logger.error("[mem0-mongodb] 更新失败: %s", e)

    def get(self, vector_id: str) -> Optional[OutputData]:
        """按 ID 检索"""
        try:
            doc = self.collection.find_one({"_id": vector_id})
            if doc:
                return OutputData(
                    id=str(doc["_id"]),
                    score=None,
                    payload=doc.get("payload"),
                )
            return None
        except Exception as e:
            logger.error("[mem0-mongodb] get 失败: %s", e)
            return None

    def list_cols(self) -> List[str]:
        """列出所有 collection"""
        try:
            return self.db.list_collection_names(authorizedCollections=True)
        except Exception as e:
            logger.error("[mem0-mongodb] list_cols 失败: %s", e)
            return []

    def delete_col(self) -> None:
        """删除 collection"""
        try:
            self.collection.drop()
            logger.info("[mem0-mongodb] 删除 collection '%s'", self.collection_name)
        except Exception as e:
            logger.error("[mem0-mongodb] delete_col 失败: %s", e)

    def col_info(self) -> Dict[str, Any]:
        """获取 collection 信息"""
        try:
            stats = self.db.command("collstats", self.collection_name)
            return {
                "name": self.collection_name,
                "count": stats.get("count", 0),
                "size": stats.get("size", 0),
            }
        except Exception as e:
            logger.error("[mem0-mongodb] col_info 失败: %s", e)
            return {}

    def list(self, filters: Optional[Dict] = None, top_k: int = 100) -> List[OutputData]:
        """列出向量（可选过滤）"""
        try:
            mongo_filter = self._build_mongo_filter(filters)
            cursor = self.collection.find(mongo_filter).limit(top_k)
            results = [
                OutputData(id=str(doc["_id"]), score=None, payload=doc.get("payload"))
                for doc in cursor
            ]
            return [results]
        except Exception as e:
            logger.error("[mem0-mongodb] list 失败: %s", e)
            return [[]]

    def reset(self) -> None:
        """重置 collection（删除并重建）"""
        logger.warning("[mem0-mongodb] 重置 collection '%s'", self.collection_name)
        self.delete_col()
        self.collection = self._get_or_create_collection()

    def __del__(self):
        try:
            if hasattr(self, "client"):
                self.client.close()
        except Exception:
            pass

    # ------------------------------------------------------------------
    # 内部工具
    # ------------------------------------------------------------------

    @staticmethod
    def _validate_filter_value(key: str, value: Any) -> None:
        """防止 MongoDB 注入"""
        if isinstance(value, dict):
            raise ValueError(
                f"Filter value for {key!r} must be a scalar, not a dict."
            )
        if isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    raise ValueError(
                        f"Filter list for {key!r} contains a dict."
                    )

    def _build_mongo_filter(self, filters: Optional[Dict]) -> Dict[str, Any]:
        """将 mem0 风格的 filters 转换为 MongoDB 查询。

        mem0 filters 是扁平的 key-value dict，存储在 payload 子文档中，
        所以过滤条件需要加 payload. 前缀。
        """
        if not filters:
            return {}

        for key, value in filters.items():
            self._validate_filter_value(key, value)

        conditions = []
        for key, value in filters.items():
            conditions.append({f"payload.{key}": value})

        if len(conditions) == 1:
            return conditions[0]
        return {"$and": conditions}


def register_mem0_mongodb_provider():
    """将自定义 MongoDB 客户端 cosine 向量存储注册到 mem0 的 VectorStoreFactory。

    在 mem0 初始化前调用（如 service.py 的 _ensure_init 中）。
    替换官方 MongoDB provider（依赖 Atlas $vectorSearch）为客户端 cosine 版本。
    """
    try:
        from mem0.utils.factory import VectorStoreFactory

        provider_path = "core.memory.mem0_mongodb_store.MongoDBClientCosine"
        VectorStoreFactory.provider_to_class["mongodb"] = provider_path
        logger.info(
            "✅ [mem0-mongodb] 已注册自定义 MongoDB 向量存储 provider (客户端 cosine)"
        )
    except Exception as e:
        logger.error("❌ [mem0-mongodb] 注册 provider 失败: %s", e)
        raise
