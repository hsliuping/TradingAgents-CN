"""用户手册向量索引管理器

基于 VectorStoreManager + EmbeddingManager 实现用户手册的语义检索。
解决使用问答机器人"用户问自然语言、手册标题匹配不到"的问题。

特性：
- 复用现有 Qdrant 基础设施（与 FinancialKnowledgeManager 同构）
- 按 Markdown 标题切片（一/二/三级标题 + 正文）
- 启动时自动检测手册 mtime 变化，按需重建索引
- 京东云模式下自动索引 jdyun-user-manual-v3.0.md
- 优雅降级：向量库/embedding 不可用时返回空结果，不阻塞启动
"""

import hashlib
import logging
import os
import re
import time
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# 用户手册专用向量集合名（与金融知识库隔离）
USER_MANUAL_COLLECTION_NAME = "user_manual_v3"

# 切片与检索参数
DEFAULT_TOP_K = 5
DEFAULT_MAX_CHARS = 4000
MAX_SECTION_CHARS = 2000  # 单个切片最大字符数，超出则截断
MIN_SECTION_CHARS = 50  # 小于该长度的切片合并到上层标题


class ManualSection:
    """手册切片数据结构"""

    def __init__(
        self,
        section_id: str,
        title: str,
        content: str,
        level: int,
        manual_type: str,  # "standard" | "jdyun"
        manual_file: str,
        parent_title: str = "",
    ):
        self.section_id = section_id
        self.title = title
        self.content = content
        self.level = level
        self.manual_type = manual_type
        self.manual_file = manual_file
        self.parent_title = parent_title

    def to_dict(self) -> Dict[str, Any]:
        return {
            "section_id": self.section_id,
            "title": self.title,
            "content": self.content,
            "level": self.level,
            "manual_type": self.manual_type,
            "manual_file": self.manual_file,
            "parent_title": self.parent_title,
        }


class ManualSearchResult:
    """检索结果"""

    def __init__(
        self,
        section_id: str,
        title: str,
        content: str,
        manual_type: str,
        similarity: float,
        parent_title: str = "",
    ):
        self.section_id = section_id
        self.title = title
        self.content = content
        self.manual_type = manual_type
        self.similarity = similarity
        self.parent_title = parent_title

    def to_dict(self) -> Dict[str, Any]:
        return {
            "section_id": self.section_id,
            "title": self.title,
            "content": self.content,
            "manual_type": self.manual_type,
            "similarity": round(self.similarity, 4),
            "parent_title": self.parent_title,
        }


def _is_jdyun_mode() -> bool:
    """判断是否为京东云模式"""
    return os.environ.get("JDYUN_MODE", "false").lower() == "true"


def _resolve_manual_files() -> List[Tuple[str, str]]:
    """返回 [(手册路径, 手册类型), ...]，按优先级排序。

    京东云模式：jdyun 优先；标准模式：standard 优先。
    两种模式都同时索引两份手册（如果存在），让 LLM 能跨版本回答。

    搜索路径（按优先级）：
    1. 项目根目录 docs/02-user-guide/（开发环境）
    2. /app/docs/02-user-guide/（Docker 容器，挂载或 docker cp）
    3. /app/runtime/docs/02-user-guide/（Docker 容器持久化 volume）
    4. 当前工作目录 docs/02-user-guide/
    """
    # 候选搜索目录
    candidate_dirs = []

    # 1. 基于 __file__ 推导项目根目录（开发环境）
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.abspath(os.path.join(current_dir, "..", ".."))
    candidate_dirs.append(os.path.join(project_root, "docs", "02-user-guide"))

    # 2. Docker 容器内常见路径
    candidate_dirs.append("/app/docs/02-user-guide")
    candidate_dirs.append("/app/runtime/docs/02-user-guide")

    # 3. 当前工作目录相对路径
    candidate_dirs.append(os.path.join(os.getcwd(), "docs", "02-user-guide"))

    # 🔥 兼容旧版平铺 docs 结构（历史便携包/安装包：user-manual-v3.0.md 直接位于 docs/ 根下）
    candidate_dirs.append(os.path.join(project_root, "docs"))
    candidate_dirs.append("/app/docs")

    # 找到第一个存在且包含手册文件的目录（避免选中空目录）
    user_guide_dir = None
    for d in candidate_dirs:
        if os.path.isdir(d) and (
            os.path.exists(os.path.join(d, "user-manual-v3.0.md"))
            or os.path.exists(os.path.join(d, "jdyun-user-manual-v3.0.md"))
        ):
            user_guide_dir = d
            break

    if not user_guide_dir:
        logger.warning(
            f"⚠️ [UserManualManager] 未找到用户手册目录，已尝试: {candidate_dirs}"
        )
        return []

    standard_path = os.path.join(user_guide_dir, "user-manual-v3.0.md")
    jdyun_path = os.path.join(user_guide_dir, "jdyun-user-manual-v3.0.md")

    manuals: List[Tuple[str, str]] = []
    if _is_jdyun_mode():
        if os.path.exists(jdyun_path):
            manuals.append((jdyun_path, "jdyun"))
        if os.path.exists(standard_path):
            manuals.append((standard_path, "standard"))
    else:
        if os.path.exists(standard_path):
            manuals.append((standard_path, "standard"))
        if os.path.exists(jdyun_path):
            manuals.append((jdyun_path, "jdyun"))
    return manuals


def _split_markdown_sections(content: str, manual_type: str, manual_file: str) -> List[ManualSection]:
    """按 Markdown 标题切片。

    切片策略：
    - 按 1-4 级标题切分
    - 每个切片的 body 包含标题下到「下一个同级或更高级标题」之间的所有内容
      （即 H3 切片会包含其下所有 H4 子标题的内容，不会被切空）
    - 过滤过短切片（< MIN_SECTION_CHARS），通常是占位或目录项
    - 过长切片截断（> MAX_SECTION_CHARS），避免 embedding 超长
    """
    sections: List[ManualSection] = []

    # 1. 用 finditer 找到所有标题位置（而非 re.split，避免子标题被切走导致父标题 body 为空）
    heading_pattern = re.compile(r'^(#{1,4})\s+([^\n]+)$', re.MULTILINE)
    headings: List[Tuple[int, int, int, str]] = []  # [(start, end, level, title), ...]
    for m in heading_pattern.finditer(content):
        level = len(m.group(1))
        title = m.group(2).strip()
        headings.append((m.start(), m.end(), level, title))

    title_chain: List[Tuple[int, str]] = []  # [(level, title), ...]

    for i, (start, end, level, title) in enumerate(headings):
        # 维护标题链，找到父标题
        while title_chain and title_chain[-1][0] >= level:
            title_chain.pop()
        parent_title = title_chain[-1][1] if title_chain else ""
        title_chain.append((level, title))

        # 找下一个同级或更高级标题的位置（body 边界）
        body_end = len(content)
        for j in range(i + 1, len(headings)):
            next_start, _, next_level, _ = headings[j]
            if next_level <= level:
                body_end = next_start
                break

        # 提取 body（标题行之后到 body_end）
        body = content[end:body_end].strip()

        # 过滤过短切片（通常是占位或目录项）
        if len(body) < MIN_SECTION_CHARS:
            continue

        # 截断过长切片
        if len(body) > MAX_SECTION_CHARS:
            body = body[:MAX_SECTION_CHARS] + "\n\n...(内容已截断)"

        # 生成确定性 ID（用于幂等 upsert）
        section_id_str = f"{manual_type}:{title}:{parent_title}"

        sections.append(ManualSection(
            section_id=section_id_str,  # 保留原始字符串作为 doc_id，便于去重
            title=title,
            content=body,
            level=level,
            manual_type=manual_type,
            manual_file=manual_file,
            parent_title=parent_title,
        ))

    return sections


class UserManualManager:
    """用户手册向量索引管理器（单例）"""

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
        self._last_indexed_signature: Optional[str] = None  # 用于外部查询上次索引签名
        self._init_backend()
        UserManualManager._initialized = True

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
                USER_MANUAL_COLLECTION_NAME, vector_size=vector_size
            )
            self._available = True
            logger.info(
                f"✅ [UserManualManager] 初始化成功 "
                f"(集合: {USER_MANUAL_COLLECTION_NAME}, 维度: {vector_size})"
            )
        except Exception as e:
            logger.warning(f"⚠️ [UserManualManager] 初始化失败，用户手册向量检索将不可用: {e}")
            self._available = False

    @property
    def available(self) -> bool:
        return self._available

    def reinit(self) -> bool:
        """重新初始化向量后端（embedding + 向量集合）。

        适用场景：启动时 Embedding API Key 未配置/错误导致初始化失败
        （available=False），用户在管理界面配置好 Key 后调用此方法即可
        恢复向量检索，无需重启后端。EmbeddingManager 每次重建都会重新
        从数据库/环境变量读取最新配置。
        """
        try:
            self._embedding_manager = None
            self._collection = None
            self._init_backend()
            if self._available:
                logger.info("✅ [UserManualManager] 重新初始化成功，向量检索已恢复")
                return True
            logger.warning("⚠️ [UserManualManager] 重新初始化后仍不可用")
            return False
        except Exception as e:
            logger.error(f"❌ [UserManualManager] 重新初始化失败: {e}", exc_info=True)
            self._available = False
            return False

    # ----------------------------------------------------------
    # 索引构建
    # ----------------------------------------------------------

    def _compute_manuals_signature(self, manuals: List[Tuple[str, str]]) -> str:
        """计算手册文件签名（基于文件内容 hash），用于变化检测。

        签名只取决于文件名 + 文件内容，不依赖路径和 mtime，
        确保不同部署环境（开发/Docker/京东云）产生相同签名，
        让预生成的种子索引数据能跨环境复用。
        """
        sig_parts = []
        for path, manual_type in manuals:
            try:
                with open(path, "rb") as f:
                    content_hash = hashlib.md5(f.read()).hexdigest()
                sig_parts.append(f"{manual_type}:{os.path.basename(path)}:{content_hash}")
            except OSError:
                sig_parts.append(f"{manual_type}:{os.path.basename(path)}:missing")
        # sorted 确保不同手册顺序产生相同签名
        return hashlib.md5("|".join(sorted(sig_parts)).encode("utf-8")).hexdigest()

    def _get_indexed_signature_from_meta(self) -> Optional[str]:
        """从 Qdrant collection 的元数据中读取上次索引签名。

        我们用一个固定 point_id 存储"索引元信息"，避免遍历整个集合。
        """
        if not self._available:
            return None
        try:
            # 尝试读取签名 point
            sig_point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, "user_manual_index_signature"))
            results = self._collection.get(ids=[sig_point_id])
            if results and results.get("metadatas"):
                meta = results["metadatas"][0]
                if meta:
                    return meta.get("manuals_signature")
        except Exception as e:
            logger.debug(f"[UserManualManager] 读取索引签名失败: {e}")
        return None

    def _save_indexed_signature(self, signature: str) -> None:
        """把当前索引签名写入 collection 元数据"""
        if not self._available:
            return
        try:
            sig_point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, "user_manual_index_signature"))
            # Qdrant 要求 embedding 非空，用全零向量占位（这个 point 不参与语义检索）
            # 但 langchain 的 Qdrant wrapper 要求 embeddings，所以改用一个空字符串 embedding
            # 这里改用 metadata-only 方式：先删除再添加
            try:
                self._collection.delete(ids=[sig_point_id])
            except Exception:
                pass
            # 用一个确定性 embedding（向量维度内）让签名 point 能存进去
            # 实际上我们用 retrieve 时按 ID 取，不会用这个 embedding 做相似度查询
            dim = self._embedding_manager.get_embedding_dimension()
            placeholder_embedding = [0.0] * dim
            self._collection.add(
                documents=["__INDEX_SIGNATURE__"],
                embeddings=[placeholder_embedding],
                metadatas=[{
                    "doc_id": "__INDEX_SIGNATURE__",
                    "title": "__INDEX_SIGNATURE__",
                    "manual_type": "meta",
                    "manuals_signature": signature,
                    "indexed_at": datetime.now().isoformat(),
                }],
                ids=[sig_point_id],
            )
        except Exception as e:
            logger.warning(f"⚠️ [UserManualManager] 保存索引签名失败: {e}")

    def _clear_all_sections(self) -> bool:
        """清空所有手册切片（保留签名 point）"""
        if not self._available:
            return False
        try:
            from core.memory.memory_manager import VectorStoreManager

            vs_manager = VectorStoreManager()
            vs_manager.delete_collection(USER_MANUAL_COLLECTION_NAME)

            vector_size = self._embedding_manager.get_embedding_dimension()
            self._collection = vs_manager.get_or_create_collection(
                USER_MANUAL_COLLECTION_NAME, vector_size=vector_size
            )
            logger.info("🗑️ [UserManualManager] 已清空手册索引集合")
            return True
        except Exception as e:
            logger.error(f"❌ [UserManualManager] 清空集合失败: {e}")
            return False

    def _index_section(self, section: ManualSection) -> bool:
        """把单个手册切片写入向量库"""
        if not self._available:
            return False
        try:
            # 拼接 embedding 文本：标题 + 父标题 + 正文（提升检索时的语义信号）
            embed_text = section.title
            if section.parent_title:
                embed_text = f"{section.parent_title} > {section.title}\n\n{section.content}"
            else:
                embed_text = f"{section.title}\n\n{section.content}"

            embedding, provider = self._embedding_manager.get_embedding(embed_text)
            if embedding is None:
                logger.warning(f"⚠️ [UserManualManager] 无法获取 embedding: {section.title}")
                return False

            metadata = {
                "doc_id": section.section_id,
                "title": section.title,
                "parent_title": section.parent_title,
                "manual_type": section.manual_type,
                "manual_file": os.path.basename(section.manual_file),
                "level": section.level,
                "provider": provider,
                "indexed_at": datetime.now().isoformat(),
            }

            point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, section.section_id))
            self._collection.add(
                documents=[section.content],
                embeddings=[embedding],
                metadatas=[metadata],
                ids=[point_id],
            )
            return True
        except Exception as e:
            logger.error(f"❌ [UserManualManager] 索引切片失败 ({section.title}): {e}")
            return False

    def ensure_indexed(self, force: bool = False) -> Dict[str, Any]:
        """确保手册已索引。若手册文件变化或集合为空则重建。

        Args:
            force: 强制重建（忽略签名比对）

        Returns:
            {
                "rebuilt": bool,         # 是否重建了索引
                "skipped": bool,          # 是否跳过（签名一致）
                "manuals_count": int,     # 索引的手册数量
                "sections_count": int,    # 索引的切片数量
                "signature": str,         # 当前签名
                "error": str,             # 错误信息（如果有）
            }
        """
        result = {
            "rebuilt": False,
            "skipped": False,
            "manuals_count": 0,
            "sections_count": 0,
            "signature": "",
            "error": "",
        }

        if not self._available:
            result["error"] = "向量库/embedding 不可用"
            return result

        manuals = _resolve_manual_files()
        if not manuals:
            result["error"] = "未找到用户手册文件"
            return result

        current_signature = self._compute_manuals_signature(manuals)
        result["signature"] = current_signature
        result["manuals_count"] = len(manuals)

        # 签名比对（非 force 模式下）
        if not force:
            indexed_signature = self._get_indexed_signature_from_meta()
            current_count = self.get_count()
            if indexed_signature == current_signature and current_count > 1:
                logger.info(
                    f"📋 [UserManualManager] 手册未变化，跳过重建 "
                    f"(签名一致，已索引 {current_count} 个切片)"
                )
                result["skipped"] = True
                result["sections_count"] = current_count
                self._last_indexed_signature = current_signature
                return result

        # 重建索引
        logger.info(f"🔨 [UserManualManager] 开始重建手册索引 (force={force})")
        start_time = time.time()

        # 清空旧索引
        if not self._clear_all_sections():
            result["error"] = "清空旧索引失败"
            return result

        all_sections: List[ManualSection] = []
        for path, manual_type in manuals:
            try:
                with open(path, encoding="utf-8") as f:
                    content = f.read()
                sections = _split_markdown_sections(content, manual_type, path)
                all_sections.extend(sections)
                logger.info(f"📖 [UserManualManager] {manual_type} 手册切片完成: {len(sections)} 个 ({os.path.basename(path)})")
            except Exception as e:
                logger.warning(f"⚠️ [UserManualManager] 读取手册失败 {path}: {e}")

        if not all_sections:
            result["error"] = "切片为空"
            return result

        # 批量索引
        success_count = 0
        for section in all_sections:
            if self._index_section(section):
                success_count += 1

        # 保存签名
        self._save_indexed_signature(current_signature)
        self._last_indexed_signature = current_signature

        elapsed = time.time() - start_time
        logger.info(
            f"✅ [UserManualManager] 索引重建完成: "
            f"{success_count}/{len(all_sections)} 切片, "
            f"耗时 {elapsed:.1f}s, 签名={current_signature[:8]}..."
        )

        result["rebuilt"] = True
        result["sections_count"] = success_count
        return result

    # ----------------------------------------------------------
    # 语义检索
    # ----------------------------------------------------------

    def search(
        self,
        query: str,
        top_k: int = DEFAULT_TOP_K,
        manual_type: Optional[str] = None,
    ) -> List[ManualSearchResult]:
        """语义检索用户手册

        Args:
            query: 用户自然语言问题
            top_k: 返回结果数量
            manual_type: 可选筛选（"standard" | "jdyun"）

        Returns:
            按相似度降序的检索结果列表
        """
        if not self._available:
            return []

        try:
            query_embedding, provider = self._embedding_manager.get_embedding(query)
            if query_embedding is None:
                logger.warning("⚠️ [UserManualManager] 无法获取查询 embedding")
                return []

            count = self._collection.count()
            if count == 0:
                logger.debug("📭 [UserManualManager] 手册索引为空")
                return []

            top_k = min(top_k, count)

            # 构建过滤条件（排除签名 point）
            where_clause = {"title": {"$ne": "__INDEX_SIGNATURE__"}}
            if manual_type:
                where_clause = {
                    "$and": [
                        {"title": {"$ne": "__INDEX_SIGNATURE__"}},
                        {"manual_type": manual_type},
                    ]
                }

            results = self._collection.query(
                query_embeddings=[query_embedding],
                n_results=top_k,
                where=where_clause,
            )

            search_results: List[ManualSearchResult] = []
            if results and "documents" in results and results["documents"]:
                documents = results["documents"][0]
                metadatas = results.get("metadatas", [[]])[0]
                distances = results.get("distances", [[]])[0]

                for i, doc_text in enumerate(documents):
                    meta = metadatas[i] if i < len(metadatas) else {}
                    dist = distances[i] if i < len(distances) else 1.0
                    similarity = 1.0 - dist

                    # 过滤签名 point（双保险）
                    if meta.get("title") == "__INDEX_SIGNATURE__":
                        continue

                    search_results.append(ManualSearchResult(
                        section_id=meta.get("doc_id", ""),
                        title=meta.get("title", ""),
                        content=doc_text,
                        manual_type=meta.get("manual_type", ""),
                        similarity=similarity,
                        parent_title=meta.get("parent_title", ""),
                    ))

            logger.debug(
                f"🔍 [UserManualManager] 检索完成: "
                f"query='{query[:30]}...', results={len(search_results)}, "
                f"top_sim={search_results[0].similarity:.3f}" if search_results else
                f"🔍 [UserManualManager] 检索完成: query='{query[:30]}...', results=0"
            )
            return search_results

        except Exception as e:
            logger.error(f"❌ [UserManualManager] 检索失败: {e}")
            return []

    def get_count(self) -> int:
        """获取已索引的切片数量"""
        if not self._available:
            return 0
        try:
            return self._collection.count()
        except Exception as e:
            logger.error(f"❌ [UserManualManager] 获取数量失败: {e}")
            return 0

    def get_status(self) -> Dict[str, Any]:
        """获取索引状态（供健康检查使用）"""
        return {
            "available": self._available,
            "collection": USER_MANUAL_COLLECTION_NAME,
            "sections_count": self.get_count(),
            "last_indexed_signature": self._last_indexed_signature,
        }
