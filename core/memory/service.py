"""
MemoryService — mem0 统一记忆适配层

所有子系统（智能助手、Skill 生成、工作流 Agent、成长系统）通过本服务
存储和召回记忆，不直接调用 mem0 SDK。

特性：
- 异步优先（AsyncMemory）
- 降级容错：mem0 不可用时返回空结果，不阻塞主流程
- 通过 metadata.scope 实现记忆分类过滤
- 单例 + 延迟初始化
- MEM0_ENABLED 环境变量总开关
"""

import asyncio
import inspect
import logging
import os
from typing import Any, Dict, List, Optional

from .models import MemoryItem, MemoryScope, StoreResult

logger = logging.getLogger(__name__)

_instance: Optional["MemoryService"] = None

_STORE_MAX_CONTENT_CHARS = 3000


def _is_mem0_enabled() -> bool:
    val = (os.environ.get("MEM0_ENABLED") or "true").strip().lower()
    return val in ("true", "1", "yes", "on")


def get_memory_service(db=None) -> "MemoryService":
    """获取全局 MemoryService 单例（延迟初始化）"""
    global _instance
    if _instance is None:
        _instance = MemoryService(db=db)
    elif db is not None and _instance._db is None:
        _instance._db = db
    return _instance


class MemoryService:
    """统一记忆服务 — mem0 适配层"""

    def __init__(self, db=None):
        self._db = db
        self._mem: Any = None
        self._init_error: str = ""
        self._init_lock = asyncio.Lock()

    @property
    def available(self) -> bool:
        return self._mem is not None

    async def _ensure_init(self) -> bool:
        """延迟初始化 mem0 AsyncMemory 实例（asyncio.Lock 保证并发安全）"""
        if self._mem is not None:
            return True
        if self._init_error:
            return False

        if not _is_mem0_enabled():
            self._init_error = "MEM0_ENABLED=false，记忆层已禁用"
            return False

        async with self._init_lock:
            if self._mem is not None:
                return True
            if self._init_error:
                return False

            try:
                from mem0 import AsyncMemory
                from .config import build_mem0_config

                config = build_mem0_config(self._db)
                if not config.get("llm", {}).get("config", {}).get("api_key"):
                    self._init_error = "缺少 LLM API Key，mem0 记忆层不可用"
                    logger.warning("[MemoryService] %s", self._init_error)
                    return False

                env_backup = {
                    "OPENAI_API_KEY": os.environ.get("OPENAI_API_KEY"),
                    "OPENAI_BASE_URL": os.environ.get("OPENAI_BASE_URL"),
                    "OPENAI_API_BASE": os.environ.get("OPENAI_API_BASE"),
                    "OPENROUTER_API_KEY": os.environ.get("OPENROUTER_API_KEY"),
                }

                llm_cfg = config.get("llm", {}).get("config", {})
                embedder_cfg = config.get("embedder", {}).get("config", {})
                selected_api_key = llm_cfg.get("api_key") or embedder_cfg.get("api_key") or ""
                selected_base_url = llm_cfg.get("openai_base_url") or embedder_cfg.get("openai_base_url") or ""

                if selected_api_key:
                    os.environ["OPENAI_API_KEY"] = selected_api_key
                if selected_base_url:
                    os.environ["OPENAI_BASE_URL"] = selected_base_url
                    os.environ["OPENAI_API_BASE"] = selected_base_url

                if selected_base_url and "openrouter.ai" not in selected_base_url.lower():
                    os.environ.pop("OPENROUTER_API_KEY", None)

                try:
                    mem_client = AsyncMemory.from_config(config)
                    if inspect.isawaitable(mem_client):
                        mem_client = await mem_client
                finally:
                    for key, value in env_backup.items():
                        if value is None:
                            os.environ.pop(key, None)
                        else:
                            os.environ[key] = value

                self._mem = mem_client
                logger.info("[MemoryService] mem0 AsyncMemory 初始化成功")
                return True
            except Exception as e:
                self._init_error = str(e)
                logger.warning("[MemoryService] mem0 初始化失败（已降级）: %s", e)
                return False

    # ------------------------------------------------------------------
    #  写入
    # ------------------------------------------------------------------

    async def store(
        self,
        messages: List[Dict[str, str]],
        *,
        user_id: str = "",
        agent_id: str = "",
        session_id: str = "",
        scope: str = MemoryScope.CONVERSATION,
        metadata: Optional[Dict[str, Any]] = None,
        infer: bool = True,
    ) -> StoreResult:
        """
        存储记忆 — mem0 自动调用 LLM 提取事实并向量化。

        Args:
            messages: OpenAI 格式消息列表 [{"role": "user", "content": "..."}]
            user_id: 用户 ID（跨会话持久）
            agent_id: agent 类型标识（如 "assistant", "skill_generator"）
            session_id: 会话 / run ID
            scope: 记忆分类（见 MemoryScope）
            metadata: 附加元数据（symbol, task_id 等）
        """
        if not await self._ensure_init():
            logger.info(
                "[MemoryService] store SKIP — user=%s agent=%s scope=%s error=%s",
                user_id, agent_id, scope, self._init_error or "mem0 不可用",
            )
            return StoreResult(success=False, error=self._init_error or "mem0 不可用")

        truncated = _truncate_messages(messages)

        merged_meta = {"scope": scope}
        if metadata:
            merged_meta.update(metadata)

        kwargs: Dict[str, Any] = {"metadata": merged_meta}
        if user_id:
            kwargs["user_id"] = user_id
        if agent_id:
            kwargs["agent_id"] = agent_id
        if session_id:
            kwargs["run_id"] = session_id
        kwargs["infer"] = infer

        try:
            result = await self._mem.add(truncated, **kwargs)
            ids = []
            count = 0
            if isinstance(result, dict):
                results_list = result.get("results") or result.get("memories") or []
                if isinstance(results_list, list):
                    for item in results_list:
                        if isinstance(item, dict) and item.get("id"):
                            ids.append(item["id"])
                            count += 1
            elif isinstance(result, list):
                for item in result:
                    if isinstance(item, dict) and item.get("id"):
                        ids.append(item["id"])
                        count += 1

            logger.debug(
                "[MemoryService] store OK — scope=%s user=%s agent=%s facts=%d",
                scope, user_id, agent_id, count,
            )
            logger.info(
                "[MemoryService] store RESULT — user=%s agent=%s scope=%s facts=%d ids=%d",
                user_id, agent_id, scope, count, len(ids),
            )
            return StoreResult(memory_ids=ids, facts_extracted=count)
        except Exception as e:
            logger.warning("[MemoryService] store 失败（已忽略）: %s", e)
            return StoreResult(success=False, error=str(e))

    # ------------------------------------------------------------------
    #  召回
    # ------------------------------------------------------------------

    async def recall(
        self,
        query: str,
        *,
        user_id: str = "",
        agent_id: str = "",
        scopes: Optional[List[str]] = None,
        limit: int = 5,
    ) -> List[MemoryItem]:
        """
        语义召回相关记忆。

        Args:
            query: 查询文本
            user_id: 限定用户
            agent_id: 限定 agent
            scopes: 限定 scope 列表（None = 不限）
            limit: 最大返回条数
        """
        if not await self._ensure_init():
            return []

        kwargs: Dict[str, Any] = {"limit": limit}
        if user_id:
            kwargs["user_id"] = user_id
        if agent_id:
            kwargs["agent_id"] = agent_id

        scope_filter = _build_mem0_scope_filter(scopes)
        if scope_filter:
            kwargs["filters"] = scope_filter
        elif _normalize_scopes(scopes):
            # mem0 qdrant backend only supports scalar MatchValue filters, not Mongo-style $in.
            # For multiple scopes, fetch a larger candidate set and filter client-side.
            kwargs["limit"] = max(limit * 5, 20)

        try:
            results = await self._mem.search(query, **kwargs)
            items = []
            raw_list = results.get("results", []) if isinstance(results, dict) else results
            for raw in raw_list:
                if isinstance(raw, dict):
                    items.append(MemoryItem.from_mem0(raw))
            items = _filter_items_by_scopes(items, scopes)
            return items[:limit]
        except Exception as e:
            logger.warning("[MemoryService] recall 失败（已降级）: %s", e)
            return []

    async def recall_formatted(
        self,
        query: str,
        *,
        user_id: str = "",
        agent_id: str = "",
        scopes: Optional[List[str]] = None,
        limit: int = 5,
        max_chars: int = 1500,
    ) -> str:
        """
        召回并格式化为可直接注入 LLM prompt 的文本。

        返回空字符串表示无可用记忆（调用方无需额外判断）。
        """
        items = await self.recall(
            query, user_id=user_id, agent_id=agent_id, scopes=scopes, limit=limit,
        )
        if not items:
            return ""

        lines: List[str] = []
        total = 0
        for item in items:
            scope_label = _SCOPE_LABEL.get(item.scope, item.scope)
            line = f"- [{scope_label}] {item.memory}"
            if total + len(line) > max_chars:
                break
            lines.append(line)
            total += len(line)

        if not lines:
            return ""
        return "【历史记忆】\n" + "\n".join(lines) + "\n"

    # ------------------------------------------------------------------
    #  辅助
    # ------------------------------------------------------------------

    async def get_user_summary(
        self,
        user_id: str,
        scopes: Optional[List[str]] = None,
    ) -> str:
        """获取用户所有记忆的摘要文本（用于画像增强）"""
        if not await self._ensure_init():
            return ""

        kwargs: Dict[str, Any] = {"user_id": user_id, "limit": 50}
        scope_filter = _build_mem0_scope_filter(scopes)
        if scope_filter:
            kwargs["filters"] = scope_filter

        try:
            results = await self._mem.get_all(**kwargs)
            raw_list = results.get("results", []) if isinstance(results, dict) else results
            items = [
                MemoryItem.from_mem0(r)
                for r in raw_list
                if isinstance(r, dict)
            ]
            items = _filter_items_by_scopes(items, scopes)
            facts = [item.memory for item in items if item.memory]
            if not facts:
                return ""
            summary_lines = [f"- {f}" for f in facts[:30]]
            return "【用户记忆摘要】\n" + "\n".join(summary_lines) + "\n"
        except Exception as e:
            logger.warning("[MemoryService] get_user_summary 失败: %s", e)
            return ""

    async def get_all(
        self,
        *,
        user_id: str = "",
        scopes: Optional[List[str]] = None,
        limit: int = 50,
        page: int = 1,
    ) -> Dict[str, Any]:
        """
        获取用户的所有记忆（分页）。

        Returns:
            {"items": [MemoryItem, ...], "total": int}
        """
        if not await self._ensure_init():
            logger.info(
                "[MemoryService] get_all SKIP — user=%s scopes=%s error=%s",
                user_id, scopes, self._init_error or "mem0 不可用",
            )
            return {"items": [], "total": 0}

        kwargs: Dict[str, Any] = {"limit": 200}
        if user_id:
            kwargs["user_id"] = user_id
        scope_filter = _build_mem0_scope_filter(scopes)
        if scope_filter:
            kwargs["filters"] = scope_filter

        try:
            results = await self._mem.get_all(**kwargs)
            raw_list = results.get("results", []) if isinstance(results, dict) else results
            all_items = [
                MemoryItem.from_mem0(raw)
                for raw in raw_list
                if isinstance(raw, dict)
            ]
            all_items = _filter_items_by_scopes(all_items, scopes)
            total = len(all_items)
            start = (page - 1) * limit
            end = start + limit
            logger.info(
                "[MemoryService] get_all RESULT — user=%s scopes=%s total=%d page=%d limit=%d",
                user_id, scopes, total, page, limit,
            )
            return {"items": all_items[start:end], "total": total}
        except Exception as e:
            logger.warning("[MemoryService] get_all 失败: %s", e)
            return {"items": [], "total": 0}

    async def delete_memory(self, memory_id: str) -> bool:
        """删除单条记忆"""
        if not await self._ensure_init():
            return False
        try:
            await self._mem.delete(memory_id)
            logger.info("[MemoryService] 已删除记忆: %s", memory_id)
            return True
        except Exception as e:
            logger.warning("[MemoryService] delete 失败: %s", e)
            return False

    async def delete_all_user_memories(self, user_id: str) -> int:
        """清除用户的全部记忆，返回删除数量"""
        if not await self._ensure_init():
            return 0
        try:
            results = await self._mem.get_all(user_id=user_id, limit=500)
            raw_list = results.get("results", []) if isinstance(results, dict) else results
            count = 0
            for raw in raw_list:
                if isinstance(raw, dict) and raw.get("id"):
                    try:
                        await self._mem.delete(raw["id"])
                        count += 1
                    except Exception:
                        pass
            logger.info("[MemoryService] 已清除用户 %s 的 %d 条记忆", user_id, count)
            return count
        except Exception as e:
            logger.warning("[MemoryService] delete_all 失败: %s", e)
            return 0

    async def health_check(self) -> Dict[str, Any]:
        """连通性检查"""
        if not await self._ensure_init():
            return {"ok": False, "error": self._init_error}
        try:
            await self._mem.get_all(user_id="__health_check__", limit=1)
            return {"ok": True, "mem0_version": _get_mem0_version()}
        except Exception as e:
            return {"ok": False, "error": str(e)}


# ------------------------------------------------------------------
#  内部工具函数
# ------------------------------------------------------------------

_SCOPE_LABEL = {
    MemoryScope.CONVERSATION: "对话",
    MemoryScope.USER_PREFERENCE: "偏好",
    MemoryScope.ANALYSIS_INSIGHT: "分析",
    MemoryScope.SKILL_LESSON: "教训",
    MemoryScope.AGENT_EXPERIENCE: "经验",
    MemoryScope.TRADE_PATTERN: "交易",
}


def _normalize_scopes(scopes: Optional[List[str]]) -> List[str]:
    if not scopes:
        return []
    normalized: List[str] = []
    for scope in scopes:
        value = str(scope or "").strip()
        if value:
            normalized.append(value)
    return normalized


def _build_mem0_scope_filter(scopes: Optional[List[str]]) -> Optional[Dict[str, str]]:
    normalized = _normalize_scopes(scopes)
    if len(normalized) == 1:
        return {"scope": normalized[0]}
    return None


def _filter_items_by_scopes(items: List[MemoryItem], scopes: Optional[List[str]]) -> List[MemoryItem]:
    normalized = set(_normalize_scopes(scopes))
    if not normalized:
        return items
    return [item for item in items if (item.scope or "") in normalized]


def _truncate_messages(
    messages: List[Dict[str, str]],
    max_chars: int = _STORE_MAX_CONTENT_CHARS,
) -> List[Dict[str, str]]:
    """截断过长的消息内容，避免事实提取阶段浪费 LLM token"""
    result = []
    for msg in messages:
        content = msg.get("content", "")
        if len(content) > max_chars:
            content = content[:max_chars] + "...(已截断)"
        result.append({**msg, "content": content})
    return result


def _get_mem0_version() -> str:
    try:
        import mem0
        return getattr(mem0, "__version__", "unknown")
    except Exception:
        return "unknown"
