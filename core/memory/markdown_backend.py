"""
Markdown 记忆后端 — 零外部依赖的记忆降级方案

当 mem0 初始化失败（缺少 Embedding 配置、Ollama 未运行等）时，
MemoryService 自动降级到本后端，保证记忆功能开箱即用。

设计：
- 存储结构：<项目根>/data/memory/<safe_user_id>/memory.md
- 每条记忆为一个块：
  <!-- memory: {"id":"...","scope":"...","user_id":"...","agent_id":"...","created_at":"...","metadata":{...}} -->
  记忆内容（可多行，保留原样）
- 人类可读可编辑，Git 可版本管理
- 检索：关键词匹配（中文二元组 + 英文单词）+ 近期时间加权，无需 Embedding
- 事实抽取：优先调用系统已配置的 LLM（复用 mem0 的 LLM 配置），失败回退启发式截断
"""

import asyncio
import json
import logging
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from .models import MemoryItem, StoreResult

logger = logging.getLogger(__name__)

# 项目根目录/data/memory（core/memory/markdown_backend.py → 上两级为项目根）
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
MEMORY_ROOT = _PROJECT_ROOT / "data" / "memory"

_BLOCK_HEADER_RE = re.compile(r"^\s*<!--\s*memory:\s*(\{.*?\})\s*-->\s*$", re.MULTILINE)


# ------------------------------------------------------------------
#  工具函数
# ------------------------------------------------------------------

def _safe_user_id(user_id: str) -> str:
    """user_id → 安全目录名（英文/数字/下划线/连字符/点，其余替换为 _）"""
    if not user_id:
        return "default"
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(user_id)).strip("._")
    return safe or "default"


def _user_memory_file(user_id: str) -> Path:
    return MEMORY_ROOT / _safe_user_id(user_id) / "memory.md"


def _parse_blocks(content: str) -> List[Dict[str, Any]]:
    """解析 memory.md 为块列表 [{"header": {...}, "text": str}]"""
    blocks: List[Dict[str, Any]] = []
    matches = list(_BLOCK_HEADER_RE.finditer(content))
    for i, m in enumerate(matches):
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(content)
        text = content[start:end].strip()
        if not text:
            continue
        try:
            header = json.loads(m.group(1))
            if not isinstance(header, dict):
                header = {}
        except json.JSONDecodeError:
            header = {}
        blocks.append({"header": header, "text": text})
    return blocks


def _format_block(header: Dict[str, Any], text: str) -> str:
    header_str = json.dumps(header, ensure_ascii=False, separators=(",", ":"))
    return f"<!-- memory: {header_str} -->\n{text}\n"


def _extract_query_terms(query: str) -> List[str]:
    """中文按字符二元组、英文/数字按单词提取查询词"""
    terms: List[str] = []
    chs = re.findall(r"[\u4e00-\u9fff]", query)
    if len(chs) >= 2:
        terms.extend("".join(chs[i:i + 2]) for i in range(len(chs) - 1))
    elif chs:
        terms.extend(chs)
    terms.extend(w.lower() for w in re.findall(r"[A-Za-z0-9]+", query))
    return terms


def _keyword_score(query: str, text: str) -> float:
    """关键词命中率 0-1"""
    terms = _extract_query_terms(query)
    if not terms:
        return 0.0
    text_lower = text.lower()
    hits = sum(1 for t in terms if t in text_lower)
    return min(hits / len(terms), 1.0)


def _time_boost(created_at: str) -> float:
    """30 天内线性衰减加成 0~0.2，越新加分越高"""
    try:
        dt = datetime.fromisoformat(str(created_at).replace("Z", "+00:00"))
        days = (datetime.now(timezone.utc) - dt).total_seconds() / 86400
        return max(0.2 * (1 - min(days / 30.0, 1.0)), 0.0)
    except Exception:
        return 0.0


def _block_to_item(block: Dict[str, Any], user_id: str, score: float = 0.0) -> MemoryItem:
    header = block["header"] or {}
    meta = header.get("metadata") or {}
    return MemoryItem(
        id=str(header.get("id") or ""),
        memory=str(block.get("text") or ""),
        user_id=str(header.get("user_id") or user_id or ""),
        agent_id=str(header.get("agent_id") or ""),
        scope=str(header.get("scope") or ""),
        score=round(score, 4),
        metadata=meta,
        created_at=str(header.get("created_at") or ""),
        updated_at=str(header.get("created_at") or ""),
        object_type=str(meta.get("object_type") or ""),
        object_key=str(meta.get("object_key") or ""),
        symbol=str(meta.get("symbol") or ""),
        market=str(meta.get("market") or ""),
        memory_kind=str(meta.get("memory_kind") or ""),
    )


def _passes_filters(header: Dict[str, Any], scopes: set, meta_filters: Dict[str, str]) -> bool:
    if scopes and str(header.get("scope") or "") not in scopes:
        return False
    if meta_filters:
        meta = header.get("metadata") or {}
        for key, expected in meta_filters.items():
            if str(meta.get(key) or "").strip() != expected:
                return False
    return True


# ------------------------------------------------------------------
#  MarkdownBackend
# ------------------------------------------------------------------

class MarkdownBackend:
    """Markdown 文件记忆后端（进程内实例，文件级 asyncio.Lock 串行化写操作）"""

    def __init__(self):
        self._write_lock = asyncio.Lock()

    # ---- 文件读写 ----

    async def _read_blocks(self, user_id: str) -> List[Dict[str, Any]]:
        path = _user_memory_file(user_id)

        def _read() -> str:
            if not path.exists():
                return ""
            return path.read_text(encoding="utf-8", errors="replace")

        content = await asyncio.to_thread(_read)
        return _parse_blocks(content)

    async def _write_blocks(self, user_id: str, blocks: List[Dict[str, Any]]) -> None:
        path = _user_memory_file(user_id)

        def _write() -> None:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("\n".join(_format_block(b["header"], b["text"]) for b in blocks), encoding="utf-8")

        await asyncio.to_thread(_write)

    async def _iter_user_dirs(self) -> List[str]:
        def _scan() -> List[str]:
            if not MEMORY_ROOT.exists():
                return []
            return sorted(d.name for d in MEMORY_ROOT.iterdir() if d.is_dir())

        return await asyncio.to_thread(_scan)

    async def _iter_all_blocks(self) -> List[Dict[str, Any]]:
        """扫描所有用户文件（目录名即 safe_user_id）"""
        all_blocks: List[Dict[str, Any]] = []
        for dirname in await self._iter_user_dirs():
            path = MEMORY_ROOT / dirname / "memory.md"

            def _read(p=path) -> str:
                if not p.exists():
                    return ""
                return p.read_text(encoding="utf-8", errors="replace")

            content = await asyncio.to_thread(_read)
            for block in _parse_blocks(content):
                block["_dir"] = dirname
                all_blocks.append(block)
        return all_blocks

    # ---- 公共接口 ----

    async def store(
        self,
        messages: List[Dict[str, str]],
        *,
        user_id: str,
        agent_id: str = "",
        session_id: str = "",
        scope: str = "",
        metadata: Optional[Dict[str, Any]] = None,
        infer: bool = True,
        llm_config: Optional[Dict[str, Any]] = None,
    ) -> StoreResult:
        """写入记忆：LLM 抽取事实（失败回退启发式），追加到 memory.md"""
        if not str(user_id or "").strip():
            return StoreResult(success=False, error="缺少 user_id，Markdown 后端无法写入")
        if not messages:
            return StoreResult(success=False, error="无可存储内容")

        facts = await self._extract_facts(messages, infer=infer, llm_config=llm_config)
        facts = [f.strip() for f in facts if str(f or "").strip()]
        if not facts:
            return StoreResult(success=False, error="未抽取到可记忆内容")

        now_iso = datetime.now(timezone.utc).isoformat()
        new_blocks: List[Dict[str, Any]] = []
        for fact in facts:
            header = {
                "id": uuid.uuid4().hex[:12],
                "scope": str(scope or "conversation"),
                "user_id": str(user_id),
                "agent_id": str(agent_id or ""),
                "session_id": str(session_id or ""),
                "created_at": now_iso,
                "metadata": metadata or {},
            }
            new_blocks.append({"header": header, "text": fact})

        async with self._write_lock:
            blocks = await self._read_blocks(user_id)
            blocks.extend(new_blocks)
            await self._write_blocks(user_id, blocks)

        logger.info(
            "[MarkdownBackend] store OK — user=%s agent=%s scope=%s facts=%d",
            user_id, agent_id, scope, len(new_blocks),
        )
        return StoreResult(
            memory_ids=[b["header"]["id"] for b in new_blocks],
            facts_extracted=len(new_blocks),
        )

    async def recall(
        self,
        query: str,
        *,
        user_id: str = "",
        agent_id: str = "",
        scopes: Optional[List[str]] = None,
        metadata_filters: Optional[Dict[str, Any]] = None,
        limit: int = 5,
    ) -> List[MemoryItem]:
        """关键词召回 + 过滤 + 时间加权评分"""
        norm_scopes = {s for s in (scopes or []) if str(s or "").strip()}
        norm_meta = {str(k).strip(): str(v).strip() for k, v in (metadata_filters or {}).items()
                     if str(k or "").strip() and str(v or "").strip()}

        if user_id:
            blocks = await self._read_blocks(user_id)
        else:
            blocks = await self._iter_all_blocks()

        scored: List[tuple] = []
        for block in blocks:
            header = block.get("header") or {}
            if agent_id and str(header.get("agent_id") or "") != agent_id:
                continue
            if not _passes_filters(header, norm_scopes, norm_meta):
                continue
            score = _keyword_score(query, block.get("text") or "") + _time_boost(header.get("created_at") or "")
            if score <= 0:
                continue
            scored.append((score, block))

        scored.sort(key=lambda x: x[0], reverse=True)
        items: List[MemoryItem] = []
        for score, block in scored[:max(int(limit or 5), 0)]:
            header = block.get("header") or {}
            uid = str(header.get("user_id") or block.get("_dir") or "")
            items.append(_block_to_item(block, uid, score))
        return items

    async def get_all(
        self,
        *,
        user_id: str = "",
        scopes: Optional[List[str]] = None,
        metadata_filters: Optional[Dict[str, Any]] = None,
        limit: int = 50,
        page: int = 1,
    ) -> Dict[str, Any]:
        """获取记忆列表（按创建时间倒序 + 分页）"""
        norm_scopes = {s for s in (scopes or []) if str(s or "").strip()}
        norm_meta = {str(k).strip(): str(v).strip() for k, v in (metadata_filters or {}).items()
                     if str(k or "").strip() and str(v or "").strip()}

        if user_id:
            blocks = await self._read_blocks(user_id)
        else:
            blocks = await self._iter_all_blocks()

        filtered = [
            b for b in blocks
            if _passes_filters(b.get("header") or {}, norm_scopes, norm_meta)
        ]
        filtered.sort(key=lambda b: str((b.get("header") or {}).get("created_at") or ""), reverse=True)

        total = len(filtered)
        try:
            page_i = max(int(page or 1), 1)
            limit_i = max(int(limit or 50), 1)
        except Exception:
            page_i, limit_i = 1, 50
        window = filtered[(page_i - 1) * limit_i: page_i * limit_i]

        items = []
        for b in window:
            header = b.get("header") or {}
            uid = str(header.get("user_id") or b.get("_dir") or user_id or "")
            items.append(_block_to_item(b, uid))
        return {"items": items, "total": total}

    async def get_user_summary(
        self,
        user_id: str,
        scopes: Optional[List[str]] = None,
    ) -> str:
        """用户记忆摘要文本（画像增强用）"""
        norm_scopes = {s for s in (scopes or []) if str(s or "").strip()}
        blocks = await self._read_blocks(user_id)
        facts = [
            b["text"] for b in blocks
            if _passes_filters(b.get("header") or {}, norm_scopes, {}) and b.get("text")
        ]
        if not facts:
            return ""
        return "【用户记忆摘要】\n" + "\n".join(f"- {f}" for f in facts[:30]) + "\n"

    async def delete_memory(self, memory_id: str) -> bool:
        """删除单条记忆（扫描所有用户文件）"""
        if not str(memory_id or "").strip():
            return False
        deleted = False
        async with self._write_lock:
            for dirname in await self._iter_user_dirs():
                blocks = await self._read_blocks(dirname)
                remaining = [b for b in blocks if str((b.get("header") or {}).get("id") or "") != memory_id]
                if len(remaining) != len(blocks):
                    await self._write_blocks(dirname, remaining)
                    deleted = True
        if deleted:
            logger.info("[MarkdownBackend] 已删除记忆: %s", memory_id)
        return deleted

    async def delete_all_user_memories(self, user_id: str) -> int:
        """清除用户全部记忆"""
        async with self._write_lock:
            blocks = await self._read_blocks(user_id)
            count = len(blocks)
            if count:
                await self._write_blocks(user_id, [])
        if count:
            logger.info("[MarkdownBackend] 已清除用户 %s 的 %d 条记忆", user_id, count)
        return count

    async def health_check(self) -> Dict[str, Any]:
        """目录可写即健康"""
        probe = MEMORY_ROOT / ".health_probe"
        try:
            await asyncio.to_thread(MEMORY_ROOT.mkdir, parents=True, exist_ok=True)
            await asyncio.to_thread(probe.write_text, "ok", encoding="utf-8")
            await asyncio.to_thread(probe.unlink)
            return {"ok": True, "backend": "markdown", "root": str(MEMORY_ROOT)}
        except Exception as e:
            return {"ok": False, "backend": "markdown", "error": str(e), "root": str(MEMORY_ROOT)}

    # ---- 事实抽取 ----

    async def _extract_facts(
        self,
        messages: List[Dict[str, str]],
        *,
        infer: bool,
        llm_config: Optional[Dict[str, Any]],
    ) -> List[str]:
        if not infer:
            # 不推理：逐条原文存储（如股票分析对象化记忆）
            return [str(m.get("content") or "").strip() for m in messages if str(m.get("content") or "").strip()]

        if llm_config and isinstance(llm_config, dict):
            cfg = llm_config.get("config") or {}
            if str(cfg.get("api_key") or "").strip():
                try:
                    facts = await self._llm_extract_facts(messages, llm_config)
                    if facts:
                        return facts
                except Exception as e:
                    logger.warning("[MarkdownBackend] LLM 事实抽取失败，回退启发式: %s", e)

        # 启发式回退：最近 user / assistant 各截断 300 字
        facts: List[str] = []
        for msg in reversed(messages):
            role = str(msg.get("role") or "")
            content = str(msg.get("content") or "").strip()
            if not content or role not in ("user", "assistant"):
                continue
            short = content[:300] + ("…" if len(content) > 300 else "")
            facts.append(f"[{role}] {short}")
            if len(facts) >= 2:
                break
        facts.reverse()
        return facts

    async def _llm_extract_facts(
        self,
        messages: List[Dict[str, str]],
        llm_config: Dict[str, Any],
    ) -> List[str]:
        """调用 OpenAI 兼容 LLM 抽取事实（JSON 数组）"""
        import httpx

        cfg = llm_config.get("config") or {}
        api_key = str(cfg.get("api_key") or "").strip()
        model = str(cfg.get("model") or "").strip()
        base_url = str(cfg.get("openai_base_url") or "https://api.openai.com/v1").rstrip("/")
        if not api_key or not model:
            return []

        conversation = "\n".join(
            f"{m.get('role', '?')}: {m.get('content', '')}" for m in messages
        )[:6000]

        prompt = (
            "从以下对话中提取 1-5 条值得长期记住的事实/偏好/结论。"
            '只返回 JSON 字符串数组，格式：["事实1", "事实2"]，不要任何其他文本。\n\n'
            f"对话：\n{conversation}"
        )

        async with httpx.AsyncClient(timeout=45.0) as client:
            resp = await client.post(
                f"{base_url}/chat/completions",
                headers={"Authorization": f"Bearer {api_key}"},
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.1,
                    "max_tokens": 1000,
                },
            )
            resp.raise_for_status()
            data = resp.json()

        content = str(
            (data.get("choices") or [{}])[0].get("message", {}).get("content") or ""
        ).strip()
        if not content:
            return []

        # 解析 JSON 数组（容忍 markdown 代码块包裹）
        cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", content, flags=re.MULTILINE).strip()
        try:
            parsed = json.loads(cleaned)
            if isinstance(parsed, list):
                return [str(x).strip() for x in parsed if str(x or "").strip()]
        except json.JSONDecodeError:
            pass
        # 兜底：按行拆分
        return [
            line.strip("- •* ").strip()
            for line in cleaned.splitlines()
            if line.strip("- •* ").strip()
        ]
