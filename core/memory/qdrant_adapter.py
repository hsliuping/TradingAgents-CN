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
                from qdrant_client.models import Distance, VectorParams, PointStruct, PointIdsList

                self.QdrantClient = QdrantClient
                self.Distance = Distance
                self.VectorParams = VectorParams
                self.PointStruct = PointStruct
                self.PointIdsList = PointIdsList

                # 确定数据目录
                data_dir = os.getenv("QDRANT_DATA_DIR", "./data/qdrant")
                Path(data_dir).mkdir(parents=True, exist_ok=True)

                # 创建本地客户端
                self._client = QdrantClient(path=data_dir)
                logger.info(f"✅ Qdrant 客户端初始化成功 (本地模式: {data_dir})")

                # 🔧 自动修复 meta.json：防止因并发写入或异常导致 collection 注册丢失
                self._repair_meta_json(data_dir)

                QdrantAdapter._initialized = True

            except ImportError:
                logger.error("❌ Qdrant 未安装，请运行: pip install qdrant-client")
                raise
            except Exception as e:
                logger.error(f"❌ Qdrant 初始化失败: {e}")
                raise

    def get_or_create_collection(self, collection_name: str, vector_size: int = 1024):
        """
        获取或创建集合

        Args:
            collection_name: 集合名称
            vector_size: 向量维度（默认 1024，兼容更多 embedding 模型）

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

    def list_collections(self) -> List[Dict[str, Any]]:
        """列出所有 collection 及其信息（复用现有客户端，避免文件锁冲突）

        Returns:
            [{name, point_count, dimensions}, ...]
        """
        result = []
        try:
            for col in self._client.get_collections().collections:
                try:
                    info = self._client.get_collection(col.name)
                    result.append({
                        "name": col.name,
                        "point_count": info.points_count or 0,
                        "dimensions": info.config.params.vectors.size if info.config.params.vectors else 0,
                    })
                except Exception as e:
                    logger.warning(f"⚠️ Qdrant 读取 collection {col.name} 信息失败: {e}")
                    result.append({"name": col.name, "point_count": 0, "dimensions": 0})
        except Exception as e:
            logger.error(f"❌ Qdrant 列出 collection 失败: {e}")
        return result

    def get_raw_client(self):
        """获取底层 QdrantClient 实例（用于迁移等需要直接操作客户端的场景）"""
        return self._client

    def _repair_meta_json(self, data_dir: str):
        """自动修复 meta.json：将磁盘上存在但 meta.json 未注册的 collection 补回
        
        防止因并发写入、进程异常退出或 Qdrant 版本升级导致 collection 注册信息丢失。
        """
        import json, sqlite3, pickle

        meta_path = os.path.join(data_dir, "meta.json")
        collection_dir = os.path.join(data_dir, "collection")

        if not os.path.exists(meta_path) or not os.path.exists(collection_dir):
            return

        try:
            # 读取当前 meta.json
            with open(meta_path, "r") as f:
                meta = json.load(f)

            registered = set(meta.get("collections", {}).keys())

            # 扫描磁盘上实际存在的 collection
            on_disk = set()
            for name in os.listdir(collection_dir):
                storage = os.path.join(collection_dir, name, "storage.sqlite")
                if os.path.exists(storage):
                    on_disk.add(name)

            # 找出孤儿 collection（磁盘存在但未注册）
            orphans = on_disk - registered
            if not orphans:
                return

            logger.warning(
                f"🔧 [Qdrant] 发现 {len(orphans)} 个孤儿 collection（磁盘存在但 meta.json 未注册），自动修复中..."
            )

            for name in sorted(orphans):
                storage = os.path.join(collection_dir, name, "storage.sqlite")
                dims = 1024  # 默认维度
                try:
                    conn = sqlite3.connect(storage)
                    cur = conn.cursor()
                    cur.execute("SELECT COUNT(*) FROM points")
                    cnt = cur.fetchone()[0]
                    if cnt > 0:
                        cur.execute("SELECT point FROM points LIMIT 1")
                        row = cur.fetchone()
                        if row and row[0]:
                            point = pickle.loads(row[0])
                            dims = len(point.vector)
                    conn.close()
                except Exception:
                    pass

                meta["collections"][name] = {
                    "vectors": {
                        "size": dims, "distance": "Cosine",
                        "hnsw_config": None, "quantization_config": None,
                        "on_disk": None, "datatype": None, "multivector_config": None
                    },
                    "shard_number": None, "sharding_method": None,
                    "replication_factor": None, "write_consistency_factor": None,
                    "on_disk_payload": None, "hnsw_config": None,
                    "wal_config": None, "optimizers_config": None,
                    "quantization_config": None, "sparse_vectors": None,
                    "strict_mode_config": None, "metadata": None
                }
                logger.info(f"  ✅ 已修复: {name} ({dims}d)")

            # 写回 meta.json
            with open(meta_path, "w") as f:
                json.dump(meta, f, indent=2)
            logger.info(f"🔧 [Qdrant] meta.json 修复完成，恢复了 {len(orphans)} 个 collection")

        except Exception as e:
            logger.warning(f"⚠️ [Qdrant] meta.json 修复检查失败（忽略，不影响启动）: {e}")


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
                logger.info(f"🗑️ 已删除旧集合: {collection_name} (维度: {existing_vector_size} -> {vector_size})")
                collection_exists = False
            except Exception as e:
                # 🔥 改进：即使删除失败，也尝试继续创建（可能会覆盖）
                logger.warning(f"⚠️ 删除旧集合失败: {e}，将尝试直接创建新集合（可能会失败）")
                # 不 raise，继续尝试创建

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

    def delete_ids(self, ids: List[str]) -> bool:
        """按文档 ID 删除点。"""
        if not ids:
            return True
        try:
            logger.debug(f"🔒 [Qdrant] 准备按 ID 删除文档 (collection={self.collection_name}, count={len(ids)})")
            self.client.delete(
                collection_name=self.collection_name,
                points_selector=self.adapter.PointIdsList(points=ids),
            )
            logger.debug(f"✅ [Qdrant] 按 ID 删除文档成功 (collection={self.collection_name}, count={len(ids)})")
            return True
        except Exception as e:
            logger.error(f"❌ [Qdrant] 按 ID 删除文档失败: {e}")
            return False

    def delete(self, ids: List[str]) -> bool:
        """delete_ids 的别名（兼容 ChromaDB 风格的 delete 调用）。"""
        return self.delete_ids(ids)

    def get(self, ids: List[str]) -> Dict[str, Any]:
        """按 ID 批量检索点（ChromaDB 风格），用于读取签名 point 等元信息。

        返回格式与 query() 一致：
            {
                "documents": [...],
                "metadatas": [...],
                "ids": [...],
            }
        不存在的 ID 会被跳过，返回结果只包含实际命中的点。
        """
        if not ids:
            return {"documents": [], "metadatas": [], "ids": []}
        try:
            # Qdrant 本地模式中 point ID 是 UUID 对象，需要转换字符串
            import uuid as uuid_module
            qdrant_ids = []
            for id_str in ids:
                try:
                    qdrant_ids.append(uuid_module.UUID(id_str))
                except (ValueError, AttributeError):
                    qdrant_ids.append(id_str)

            retrieved = self.client.retrieve(
                collection_name=self.collection_name,
                ids=qdrant_ids,
                with_payload=True,
                with_vectors=False,
            )
            documents = []
            metadatas = []
            result_ids = []
            for point in retrieved:
                payload = point.payload or {}
                # document 存在 payload["document"]，与 add() 一致
                document = payload.get("document", "")
                metadata = {k: v for k, v in payload.items() if k != "document"}
                documents.append(document)
                metadatas.append(metadata)
                result_ids.append(point.id)
            return {
                "documents": documents,
                "metadatas": metadatas,
                "ids": result_ids,
            }
        except Exception as e:
            logger.error(f"❌ [Qdrant] get 按 ID 检索失败 (collection={self.collection_name}): {e}")
            return {"documents": [], "metadatas": [], "ids": []}

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

            # 执行搜索（使用 query_points 方法，search 方法在 v1.16.0 中已被移除）
            search_results = self.client.query_points(
                collection_name=self.collection_name,
                query=query_vector,
                limit=n_results,
                query_filter=query_filter
            )

            logger.debug(f"✅ [Qdrant] 查询成功 (collection={self.collection_name}, results={len(search_results.points)})")

            # 转换为 ChromaDB 格式
            documents = []
            metadatas = []
            distances = []

            for result in search_results.points:
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

