"""
金融知识管理器

基于 VectorStoreManager + EmbeddingManager 实现金融领域知识的存储和语义检索。
用于 RAG（Retrieval-Augmented Generation）动态知识注入。

特性：
- 复用现有向量数据库基础设施（Qdrant）
- 支持知识文档的 CRUD 操作
- 语义检索 + 分类筛选
- 优雅降级（向量库不可用时返回空结果，不阻塞分析流程）
- 检索结果格式化为 prompt 注入文本
"""

import hashlib
import logging
import time
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# 知识库向量集合名称
KNOWLEDGE_COLLECTION_NAME = "knowledge_finance"

# 检索默认参数
DEFAULT_TOP_K = 3
DEFAULT_MAX_CHARS = 1500
RETRIEVE_TIMEOUT_SECONDS = 3.0


class KnowledgeDocument:
    """知识文档数据结构"""

    def __init__(
        self,
        id: str,
        category: str,
        title: str,
        content: str,
        tags: Optional[List[str]] = None,
        priority: int = 5,
        created_at: Optional[str] = None,
        updated_at: Optional[str] = None,
    ):
        self.id = id
        self.category = category
        self.title = title
        self.content = content
        self.tags = tags or []
        self.priority = priority
        now = datetime.now().isoformat()
        self.created_at = created_at or now
        self.updated_at = updated_at or now

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "category": self.category,
            "title": self.title,
            "content": self.content,
            "tags": self.tags,
            "priority": self.priority,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "KnowledgeDocument":
        return cls(
            id=data["id"],
            category=data.get("category", ""),
            title=data.get("title", ""),
            content=data.get("content", ""),
            tags=data.get("tags", []),
            priority=data.get("priority", 5),
            created_at=data.get("created_at"),
            updated_at=data.get("updated_at"),
        )


class KnowledgeSnippet:
    """检索结果片段"""

    def __init__(self, doc_id: str, title: str, content: str, category: str,
                 similarity: float, tags: List[str]):
        self.doc_id = doc_id
        self.title = title
        self.content = content
        self.category = category
        self.similarity = similarity
        self.tags = tags

    def to_dict(self) -> Dict[str, Any]:
        return {
            "doc_id": self.doc_id,
            "title": self.title,
            "content": self.content,
            "category": self.category,
            "similarity": round(self.similarity, 4),
            "tags": self.tags,
        }


class FinancialKnowledgeManager:
    """
    金融知识管理器（单例）

    提供知识文档的 CRUD 和语义检索功能。
    底层复用 VectorStoreManager + EmbeddingManager。
    """

    _instance = None
    _initialized = False

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, db=None):
        if self._initialized:
            return
        self._db = db
        self._embedding_manager = None
        self._collection = None
        self._available = False
        self._init_backend()
        FinancialKnowledgeManager._initialized = True

    # ----------------------------------------------------------
    # 初始化
    # ----------------------------------------------------------

    def _init_backend(self):
        """初始化向量数据库和 Embedding 后端"""
        try:
            from core.llm.embedding_manager import EmbeddingManager
            from core.memory.memory_manager import VectorStoreManager

            self._embedding_manager = EmbeddingManager(db=self._db)
            vector_size = self._embedding_manager.get_embedding_dimension()

            vs_manager = VectorStoreManager()
            self._collection = vs_manager.get_or_create_collection(
                KNOWLEDGE_COLLECTION_NAME, vector_size=vector_size
            )
            self._available = True
            logger.info(
                f"✅ [KnowledgeManager] 初始化成功 "
                f"(集合: {KNOWLEDGE_COLLECTION_NAME}, 维度: {vector_size})"
            )
        except Exception as e:
            logger.warning(f"⚠️ [KnowledgeManager] 初始化失败，知识检索将不可用: {e}")
            self._available = False

    @property
    def available(self) -> bool:
        """知识检索是否可用"""
        return self._available

    # ----------------------------------------------------------
    # CRUD 操作
    # ----------------------------------------------------------

    def add_knowledge(self, doc: KnowledgeDocument) -> bool:
        """
        添加知识文档（幂等，相同 id 会覆盖）

        Args:
            doc: 知识文档

        Returns:
            是否成功
        """
        if not self._available:
            logger.warning("⚠️ [KnowledgeManager] 不可用，跳过添加")
            return False

        try:
            embedding, provider = self._embedding_manager.get_embedding(doc.content)
            if embedding is None:
                logger.warning(f"⚠️ [KnowledgeManager] 无法获取 embedding: {doc.id}")
                return False

            metadata = {
                "doc_id": doc.id,
                "category": doc.category,
                "title": doc.title,
                "tags": ",".join(doc.tags),
                "priority": doc.priority,
                "provider": provider,
                "created_at": doc.created_at,
                "updated_at": doc.updated_at,
            }

            # Qdrant 要求 UUID 格式的 ID，用 uuid5 确定性转换（相同 doc.id → 相同 UUID）
            point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, doc.id))

            self._collection.add(
                documents=[doc.content],
                embeddings=[embedding],
                metadatas=[metadata],
                ids=[point_id],
            )
            logger.debug(f"✅ [KnowledgeManager] 知识已添加: {doc.id} ({doc.title})")
            return True

        except Exception as e:
            logger.error(f"❌ [KnowledgeManager] 添加知识失败: {e}")
            return False

    def add_knowledge_batch(self, docs: List[KnowledgeDocument]) -> int:
        """
        批量添加知识文档

        Returns:
            成功添加的数量
        """
        success = 0
        for doc in docs:
            if self.add_knowledge(doc):
                success += 1
        logger.info(f"📚 [KnowledgeManager] 批量添加完成: {success}/{len(docs)}")
        return success

    def get_count(self) -> int:
        """获取知识文档数量"""
        if not self._available:
            return 0
        try:
            return self._collection.count()
        except Exception as e:
            logger.error(f"❌ [KnowledgeManager] 获取数量失败: {e}")
            return 0

    def clear_all(self) -> bool:
        """清空所有知识文档"""
        if not self._available:
            return False
        try:
            from core.memory.memory_manager import VectorStoreManager

            vs_manager = VectorStoreManager()
            vs_manager.delete_collection(KNOWLEDGE_COLLECTION_NAME)

            vector_size = self._embedding_manager.get_embedding_dimension()
            self._collection = vs_manager.get_or_create_collection(
                KNOWLEDGE_COLLECTION_NAME, vector_size=vector_size
            )
            logger.info("🗑️ [KnowledgeManager] 已清空所有知识")
            return True
        except Exception as e:
            logger.error(f"❌ [KnowledgeManager] 清空失败: {e}")
            return False

    # ----------------------------------------------------------
    # 语义检索
    # ----------------------------------------------------------

    def search(
        self,
        query: str,
        top_k: int = DEFAULT_TOP_K,
        category: Optional[str] = None,
    ) -> List[KnowledgeSnippet]:
        """
        语义检索知识文档

        Args:
            query: 查询文本
            top_k: 返回结果数量
            category: 可选分类筛选

        Returns:
            知识片段列表（按相似度降序）
        """
        if not self._available:
            return []

        try:
            start_time = time.time()

            query_embedding, provider = self._embedding_manager.get_embedding(query)
            if query_embedding is None:
                logger.warning("⚠️ [KnowledgeManager] 无法获取查询 embedding")
                return []

            count = self._collection.count()
            if count == 0:
                logger.debug("📭 [KnowledgeManager] 知识库为空")
                return []

            top_k = min(top_k, count)

            # 构建过滤条件
            where_clause = None
            filter_parts = {"provider": provider}
            if category:
                filter_parts["category"] = category

            if len(filter_parts) == 1:
                key, value = next(iter(filter_parts.items()))
                where_clause = {key: value}
            else:
                where_clause = {
                    "$and": [{k: v} for k, v in filter_parts.items()]
                }

            results = self._collection.query(
                query_embeddings=[query_embedding],
                n_results=top_k,
                where=where_clause,
            )

            elapsed = time.time() - start_time

            snippets: List[KnowledgeSnippet] = []
            if results and "documents" in results and results["documents"]:
                documents = results["documents"][0]
                metadatas = results.get("metadatas", [[]])[0]
                distances = results.get("distances", [[]])[0]

                for i, doc_text in enumerate(documents):
                    meta = metadatas[i] if i < len(metadatas) else {}
                    dist = distances[i] if i < len(distances) else 1.0
                    similarity = 1.0 - dist

                    snippets.append(KnowledgeSnippet(
                        doc_id=meta.get("doc_id", ""),
                        title=meta.get("title", ""),
                        content=doc_text,
                        category=meta.get("category", ""),
                        similarity=similarity,
                        tags=meta.get("tags", "").split(",") if meta.get("tags") else [],
                    ))

            # 按 priority 二次排序（相似度相近时优先级高的排前面）
            snippets.sort(key=lambda s: (-s.similarity, -0))

            logger.debug(
                f"🔍 [KnowledgeManager] 检索完成: "
                f"query='{query[:30]}...', results={len(snippets)}, "
                f"elapsed={elapsed:.2f}s"
            )
            return snippets

        except Exception as e:
            logger.error(f"❌ [KnowledgeManager] 检索失败: {e}")
            return []

    # ----------------------------------------------------------
    # Prompt 集成接口
    # ----------------------------------------------------------

    def retrieve_for_prompt(
        self,
        question: str,
        top_k: int = DEFAULT_TOP_K,
        max_chars: int = DEFAULT_MAX_CHARS,
    ) -> str:
        """
        检索知识并格式化为 prompt 注入文本。

        这是与 IntelligentAssistantService / PlannedAnalysisService 的主要集成接口。
        返回空字符串表示无可用知识（降级为静态知识）。

        Args:
            question: 用户问题
            top_k: 检索数量
            max_chars: 最大字符数

        Returns:
            格式化的知识文本（可直接拼入 system prompt），或空字符串
        """
        if not self._available:
            return ""

        try:
            snippets = self.search(question, top_k=top_k)
            if not snippets:
                return ""

            lines = ["【动态知识参考】"]
            total_chars = len(lines[0])

            for s in snippets:
                entry = f"- **{s.title}**: {s.content}"
                if total_chars + len(entry) > max_chars:
                    break
                lines.append(entry)
                total_chars += len(entry)

            if len(lines) <= 1:
                return ""

            result = "\n".join(lines)
            logger.info(
                f"📚 [KnowledgeManager] 注入 {len(lines) - 1} 条知识 "
                f"({total_chars} 字符) for: '{question[:30]}...'"
            )
            return result

        except Exception as e:
            logger.warning(f"⚠️ [KnowledgeManager] retrieve_for_prompt 失败: {e}")
            return ""

    # ----------------------------------------------------------
    # 统计信息
    # ----------------------------------------------------------

    def get_stats(self) -> Dict[str, Any]:
        """获取知识库统计信息"""
        return {
            "available": self._available,
            "collection_name": KNOWLEDGE_COLLECTION_NAME,
            "total_documents": self.get_count(),
            "backend": "qdrant" if self._available else "unavailable",
        }

