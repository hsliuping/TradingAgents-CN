"""
MongoDB 向量数据库适配器（客户端 cosine 相似度）

特性：
- 向量数据存储在 MongoDB 中（与业务数据统一）
- 相似度计算在 Python 端完成（numpy cosine），不依赖 MongoDB $vectorSearch
- 无文件锁冲突，支持多进程并发访问
- 与 QdrantAdapter 接口完全一致，调用方无需修改
- 适用于中小规模向量集合（< 10K 条），大数据量建议用 Qdrant 服务器模式
"""

import logging
import os
import time
from typing import List, Dict, Any, Optional

import numpy as np
from pymongo import UpdateOne

logger = logging.getLogger(__name__)


def _translate_where_to_mongo(where: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """将 ChromaDB 风格的 where 条件转换为 MongoDB 查询过滤器。

    支持的格式：
    - {"key": "value"} → {"key": "value"}
    - {"$and": [{"k1": "v1"}, {"k2": "v2"}]} → {"$and": [{"k1": "v1"}, {"k2": "v2"}]}
    - {"key": {"$ne": "value"}} → {"key": {"$ne": "value"}}（直通）
    """
    if not where:
        return {}
    result = {}
    for key, value in where.items():
        if key == "$and":
            result["$and"] = [_translate_where_to_mongo(c) for c in value]
        elif key == "$or":
            result["$or"] = [_translate_where_to_mongo(c) for c in value]
        else:
            result[key] = value
    return result


class MongoDBVectorAdapter:
    """MongoDB 向量数据库适配器（单例）

    使用现有 MongoDB 连接，将向量数据存储为文档数组字段。
    相似度搜索在 Python 端用 numpy 完成。
    """

    _instance = None
    _initialized = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not self._initialized:
            try:
                from app.core.database import get_mongo_db_sync

                self._db = get_mongo_db_sync()
                logger.info("✅ MongoDB 向量适配器初始化成功 (客户端 cosine 模式)")
                MongoDBVectorAdapter._initialized = True
            except Exception as e:
                logger.error(f"❌ MongoDB 向量适配器初始化失败: {e}")
                raise

    def get_or_create_collection(self, collection_name: str, vector_size: int = 1024):
        """获取或创建集合"""
        return MongoDBVectorCollection(self._db, collection_name, vector_size)

    def delete_collection(self, collection_name: str) -> bool:
        """删除集合"""
        try:
            self._db.drop_collection(collection_name)
            logger.info(f"✅ MongoDB 集合已删除: {collection_name}")
            return True
        except Exception as e:
            logger.error(f"❌ 删除 MongoDB 集合失败: {e}")
            return False

    def list_collections(self) -> List[Dict[str, Any]]:
        """列出所有向量集合及其信息"""
        result = []
        try:
            for name in self._db.list_collection_names():
                if name.startswith("system."):
                    continue
                try:
                    count = self._db[name].count_documents({})
                    result.append({
                        "name": name,
                        "point_count": count,
                        "dimensions": 0,  # 不缓存维度，按需读取
                    })
                except Exception:
                    result.append({"name": name, "point_count": 0, "dimensions": 0})
        except Exception as e:
            logger.error(f"❌ MongoDB 列出集合失败: {e}")
        return result

    def get_backend_name(self) -> str:
        return "mongodb"


class MongoDBVectorCollection:
    """MongoDB 集合包装类，实现与 QdrantCollection 相同的接口。

    文档结构（扁平，与 Qdrant payload 一致）：
    {
        "_id": "uuid-string",
        "embedding": [0.1, 0.2, ...],   # 向量数组
        "document": "文本内容",
        "title": "...",
        "manual_type": "...",
        ...其他 metadata 字段
    }
    """

    def __init__(self, db, collection_name: str, vector_size: int):
        self._db = db
        self._collection_name = collection_name
        self._vector_size = vector_size
        self._collection = db[collection_name]

        # 确保集合存在（MongoDB 在首次写入时自动创建，这里只创建索引）
        self._ensure_indexes()

    def _ensure_indexes(self):
        """创建必要的索引（幂等操作）"""
        try:
            # 在 document 字段上创建文本索引（可选，用于未来扩展）
            # 在 _id 上 MongoDB 已自动有索引
            pass  # MongoDB 自动管理 _id 索引
        except Exception as e:
            logger.debug(f"[MongoDB Vector] 索引创建跳过: {e}")

    def add(
        self,
        documents: List[str],
        embeddings: List[List[float]],
        metadatas: List[Dict[str, Any]],
        ids: List[str],
    ) -> bool:
        """添加文档（upsert 语义，幂等）"""
        try:
            operations = []
            for doc_id, embedding, metadata, document in zip(ids, embeddings, metadatas, documents):
                # 构建文档：embedding + document + metadata（扁平结构）
                doc = {
                    "embedding": embedding,
                    "document": document,
                }
                # 将 metadata 的字段平铺到文档顶层
                for k, v in metadata.items():
                    doc[k] = v

                operations.append(
                    UpdateOne(
                        {"_id": doc_id},
                        {"$set": doc},
                        upsert=True,
                    )
                )

            if operations:
                result = self._collection.bulk_write(operations, ordered=False)
                logger.debug(
                    f"✅ [MongoDB] 文档添加成功 "
                    f"(collection={self._collection_name}, "
                    f"upserted={result.upserted_count}, modified={result.modified_count})"
                )
            return True

        except Exception as e:
            logger.error(f"❌ [MongoDB] 添加文档失败: {e}")
            return False

    def delete_ids(self, ids: List[str]) -> bool:
        """按 ID 删除文档"""
        if not ids:
            return True
        try:
            result = self._collection.delete_many({"_id": {"$in": ids}})
            logger.debug(
                f"✅ [MongoDB] 删除文档成功 "
                f"(collection={self._collection_name}, deleted={result.deleted_count})"
            )
            return True
        except Exception as e:
            logger.error(f"❌ [MongoDB] 删除文档失败: {e}")
            return False

    def delete(self, ids: List[str]) -> bool:
        """delete_ids 的别名（兼容 ChromaDB 风格）"""
        return self.delete_ids(ids)

    def get(self, ids: List[str]) -> Dict[str, Any]:
        """按 ID 批量检索文档

        返回格式：
            {"documents": [...], "metadatas": [...], "ids": [...]}
        """
        if not ids:
            return {"documents": [], "metadatas": [], "ids": []}
        try:
            cursor = self._collection.find(
                {"_id": {"$in": ids}},
                {"embedding": 0},  # 不返回 embedding（与 Qdrant get 一致）
            )
            documents = []
            metadatas = []
            result_ids = []
            for doc in cursor:
                document = doc.pop("document", "")
                doc_id = doc.pop("_id", "")
                # 剩余字段作为 metadata
                metadata = {k: v for k, v in doc.items() if k not in ("document", "_id", "embedding")}
                documents.append(document)
                metadatas.append(metadata)
                result_ids.append(doc_id)
            return {
                "documents": documents,
                "metadatas": metadatas,
                "ids": result_ids,
            }
        except Exception as e:
            logger.error(f"❌ [MongoDB] get 检索失败: {e}")
            return {"documents": [], "metadatas": [], "ids": []}

    def query(
        self,
        query_embeddings: List[List[float]],
        n_results: int = 5,
        where: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """向量相似度搜索（客户端 cosine）

        流程：
        1. 从 MongoDB 读取所有文档（含 embedding），可选 where 过滤
        2. 在 Python 端用 numpy 计算 cosine 相似度
        3. 返回 top-k 结果

        返回格式与 QdrantCollection.query 一致：
            {"documents": [[...]], "metadatas": [[...]], "distances": [[...]]}
        """
        try:
            if not query_embeddings:
                return {"documents": [[]], "metadatas": [[]], "distances": [[]]}

            query_vector = np.array(query_embeddings[0], dtype=np.float32)

            # 构建 MongoDB 查询过滤器
            mongo_filter = _translate_where_to_mongo(where)

            # 从 MongoDB 读取所有文档，排除 embedding 节省带宽但在 Python 端仍需 embedding
            # 注意：必须返回所有字段（包括 metadata 如 title/provider/...），
            # 否则 search 结果中 metadata 会丢失导致过滤失效
            cursor = self._collection.find(mongo_filter)

            docs = list(cursor)
            if not docs:
                return {"documents": [[]], "metadatas": [[]], "distances": [[]]}

            # 构建向量矩阵
            vectors = []
            valid_docs = []
            for doc in docs:
                emb = doc.get("embedding")
                if emb is None or len(emb) == 0:
                    continue
                # 跳过零向量（签名 point）
                if all(v == 0.0 for v in emb):
                    continue
                vectors.append(emb)
                valid_docs.append(doc)

            if not valid_docs:
                return {"documents": [[]], "metadatas": [[]], "distances": [[]]}

            matrix = np.array(vectors, dtype=np.float32)

            # 计算 cosine 相似度
            # cosine = dot(a, b) / (||a|| * ||b||)
            query_norm = np.linalg.norm(query_vector)
            if query_norm == 0:
                return {"documents": [[]], "metadatas": [[]], "distances": [[]]}

            matrix_norms = np.linalg.norm(matrix, axis=1)
            # 避免除零
            valid_norms = matrix_norms > 0
            if not np.any(valid_norms):
                return {"documents": [[]], "metadatas": [[]], "distances": [[]]}

            # 只计算有效向量的相似度
            valid_matrix = matrix[valid_norms]
            valid_docs_filtered = [d for d, v in zip(valid_docs, valid_norms) if v]
            valid_norms_filtered = matrix_norms[valid_norms]

            similarities = np.dot(valid_matrix, query_vector) / (valid_norms_filtered * query_norm)

            # 按相似度降序排列，取 top-k
            top_k = min(n_results, len(similarities))
            top_indices = np.argsort(similarities)[::-1][:top_k]

            documents = []
            metadatas = []
            distances = []

            for idx in top_indices:
                doc = valid_docs_filtered[idx]
                document = doc.get("document", "")

                # 重新读取完整 metadata（query 时只取了部分字段）
                # 为避免二次查询，这里从已有数据构建
                metadata = {k: v for k, v in doc.items() if k not in ("_id", "embedding", "document")}
                # _id 作为 doc_id
                metadata.setdefault("doc_id", str(doc.get("_id", "")))

                documents.append(document)
                metadatas.append(metadata)
                # distance = 1 - similarity（与 Qdrant COSINE 一致）
                distances.append(float(1.0 - similarities[idx]))

            return {
                "documents": [documents],
                "metadatas": [metadatas],
                "distances": [distances],
            }

        except Exception as e:
            logger.error(f"❌ [MongoDB] 查询失败: {e}")
            return {"documents": [[]], "metadatas": [[]], "distances": [[]]}

    def count(self) -> int:
        """获取文档数量"""
        try:
            return self._collection.count_documents({})
        except Exception as e:
            logger.error(f"❌ [MongoDB] 获取文档数量失败: {e}")
            return 0

    def delete_collection(self) -> bool:
        """删除集合"""
        try:
            self._db.drop_collection(self._collection_name)
            logger.info(f"✅ [MongoDB] 集合已删除: {self._collection_name}")
            return True
        except Exception as e:
            logger.error(f"❌ [MongoDB] 删除集合失败: {e}")
            return False

    def get_backend_name(self) -> str:
        return "mongodb"
