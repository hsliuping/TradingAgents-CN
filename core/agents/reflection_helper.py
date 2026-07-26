"""
反射节点统一 helper。

所有反思节点遵循同一模式：
1. 构建反思 prompt
2. 调 LLM 提炼结构化 JSON
3. 写入 mem0（infer=False，memory_kind=xxx_lesson）
4. 失败时 fallback 到原文写入（即当前行为），不阻塞主流程

三个场景共用此 helper：
- 项2：复盘反思（trade_lesson）
- 项3：研究员报告反思（analysis_lesson）
- 项8：辩论反思（debate_lesson）
"""

import asyncio
import json
import logging
import re
import threading
from typing import Any, Dict, Optional

from core.memory.models import MemoryScope
from core.memory.service import get_memory_service

logger = logging.getLogger(__name__)

# 反思 LLM 调用超时（秒），超时即降级到原文写入
_REFLECTION_LLM_TIMEOUT = 30


def _resolve_reflection_llm_client(db) -> Optional[Any]:
    """从系统配置解析反思用 LLM 客户端。

    不再硬编码 provider，而是按系统设置中的模型选择顺序
    （quick_analysis_model → deep_analysis_model → 第一个启用的配置）
    解析完整 LLMConfig 并构建 UnifiedLLMClient。反思是轻量提炼任务，
    优先用 quick_analysis 模型以控制成本。

    db 类型兼容：
    - 同步 PyMongo Database → 直接查询
    - Motor AsyncIOMotorDatabase / 代理对象 → 自动回退到同步连接
      （Motor 的 find_one 是 async 方法，同步调用只返回 coroutine 不会真正执行查询）

    若数据库不可用或无可用配置，返回 None；调用方应据此跳过反思提炼，
    降级到原文写入（infer=False），而不是用硬编码 provider 兜底——
    如果系统未配置该 provider，兜底客户端同样无法工作。
    """
    try:
        from app.services.intelligent_assistant_service import (
            get_system_llm_config_from_config_doc,
        )
        # 复用 mem0 配置层的 db 类型检测：Motor async client 会自动回退到同步连接
        from core.memory.config import _read_active_system_config

        config_doc = _read_active_system_config(db)
        if not config_doc:
            logger.warning("[Reflection] 系统配置不存在或读取失败，反思 LLM 不可用")
            return None

        llm_config = get_system_llm_config_from_config_doc(config_doc)
        if llm_config is None:
            logger.warning("[Reflection] 系统配置中无可用 LLM 配置，反思 LLM 不可用")
            return None

        from core.llm import UnifiedLLMClient

        logger.info(
            "[Reflection] 从系统配置解析反思 LLM: provider=%s model=%s",
            llm_config.provider,
            llm_config.model,
        )
        return UnifiedLLMClient.from_config(llm_config)
    except Exception as e:
        logger.warning("[Reflection] 从系统配置解析 LLM 失败: %s", e)
        return None


def run_reflection_sync(**kwargs) -> bool:
    """run_reflection 的同步包装器，供 sync 上下文（如 ResearcherAgent.execute）调用。

    自动处理两种场景：
    1. 当前线程没有运行中的事件循环 → 直接 asyncio.run()
    2. 当前线程有运行中的事件循环（如被 LangGraph 在 async 上下文中调用 sync 节点）
       → 在新线程中创建独立事件循环运行

    所有异常都被捕获并降级返回 False，确保不阻塞主流程。
    """
    try:
        try:
            asyncio.get_running_loop()
            running_loop = True
        except RuntimeError:
            running_loop = False

        if not running_loop:
            # 没有运行中的事件循环，直接用 asyncio.run
            return asyncio.run(run_reflection(**kwargs))

        # 有运行中的事件循环，在新线程中运行
        result: Dict[str, Any] = {"success": False, "error": None}

        def _run_in_thread():
            try:
                result["success"] = asyncio.run(run_reflection(**kwargs))
            except Exception as e:
                result["error"] = e

        t = threading.Thread(target=_run_in_thread, daemon=True)
        t.start()
        t.join(timeout=_REFLECTION_LLM_TIMEOUT + 10)
        if t.is_alive():
            logger.warning("[Reflection] sync 包装器线程超时，降级返回 False")
            return False
        if result["error"]:
            logger.warning("[Reflection] sync 包装器线程异常: %s", result["error"])
            return False
        return result["success"]
    except Exception as e:
        logger.warning("[Reflection] run_reflection_sync 异常: %s", e)
        return False


async def run_reflection(
    *,
    db: Any,
    user_id: str,
    agent_id: str,
    scope: MemoryScope,
    memory_kind: str,
    system_prompt: str,
    user_prompt: str,
    fallback_content: str,
    fallback_metadata: Dict[str, Any],
    llm_client: Any = None,
) -> bool:
    """执行反思提炼节点，失败时降级。

    流程：
    1. 调 LLM 提炼结构化 JSON（超时 30s）
    2. 成功 → 写入 mem0（infer=False，memory_kind=xxx_lesson，reflection_success=True）
    3. 失败 → 降级写入 fallback_content 原文（memory_kind=xxx_lesson，reflection_success=False）
    4. mem0 不可用 → 跳过，返回 False

    Args:
        db: MongoDB 数据库句柄（用于获取 MemoryService）
        user_id: 用户 ID
        agent_id: Agent ID（用于 mem0 元数据）
        scope: MemoryScope 枚举值
        memory_kind: 教训类型（trade_lesson / analysis_lesson / debate_lesson）
        system_prompt: 反思 system prompt
        user_prompt: 反思 user prompt
        fallback_content: 降级时写入的原文
        fallback_metadata: 降级时的元数据（反思成功时也会用这些元数据作为基础）
        llm_client: 可选的 UnifiedLLMClient 实例，若不传则用默认 provider 创建

    Returns:
        True 表示反思成功写入结构化教训；False 表示降级到原文写入或彻底失败。
    """
    svc = get_memory_service(db)
    if not svc.available:
        logger.info("[Reflection] mem0 不可用，跳过反思节点（agent=%s scope=%s）", agent_id, scope)
        return False

    # 1. 调 LLM 提炼
    lessons_json: Optional[str] = None
    try:
        if llm_client is None:
            # 从系统配置解析 LLM，不再硬编码 provider
            llm_client = _resolve_reflection_llm_client(db)

        if llm_client is None:
            # 系统配置不可用 → 直接走降级原文写入（不调 LLM 提炼）
            # 不再使用 deepseek 等硬编码 provider 兜底：若系统未配置该 provider，
            # 兜底客户端同样无法工作，反而掩盖配置问题。
            logger.warning(
                "[Reflection] 系统配置未解析到可用 LLM，跳过反思提炼，降级写入原文（agent=%s scope=%s）",
                agent_id, scope,
            )
        else:
            from core.llm.models import Message, MessageRole
            messages = [
                Message(role=MessageRole.SYSTEM, content=system_prompt),
                Message(role=MessageRole.USER, content=user_prompt),
            ]
            resp = await asyncio.wait_for(
                llm_client.achat(messages),
                timeout=_REFLECTION_LLM_TIMEOUT,
            )
            raw_content = resp.content or "" if hasattr(resp, "content") else str(resp)
            lessons_json = _extract_json(raw_content)
            if not lessons_json:
                logger.warning(
                    "[Reflection] LLM 未返回有效 JSON（agent=%s），降级到原文写入。原始输出前200字: %s",
                    agent_id,
                    raw_content[:200],
                )
    except asyncio.TimeoutError:
        logger.warning("[Reflection] LLM 调用超时（%ds，agent=%s），降级到原文写入", _REFLECTION_LLM_TIMEOUT, agent_id)
    except Exception as e:
        logger.warning("[Reflection] LLM 调用失败（agent=%s）: %s，降级到原文写入", agent_id, e)

    # 2. 写入 mem0
    metadata = dict(fallback_metadata)
    metadata["memory_kind"] = memory_kind
    metadata["source"] = "reflection"

    try:
        if lessons_json:
            # 反思成功：写入结构化教训
            content = lessons_json
            metadata["reflection_success"] = True
        else:
            # 降级：写入原文
            content = fallback_content
            metadata["reflection_success"] = False

        result = await svc.store(
            [{"role": "assistant", "content": content}],
            user_id=user_id,
            agent_id=agent_id,
            scope=scope,
            metadata=metadata,
            infer=False,  # 已用 LLM 提炼，不再触发 mem0 二次提取
        )
        if result.success:
            if lessons_json:
                logger.info(
                    "[Reflection] 反思成功写入（agent=%s scope=%s kind=%s）",
                    agent_id, scope, memory_kind,
                )
            else:
                logger.info(
                    "[Reflection] 降级写入原文（agent=%s scope=%s kind=%s）",
                    agent_id, scope, memory_kind,
                )
            return bool(lessons_json)
        else:
            logger.warning("[Reflection] mem0 写入失败: %s", result.error)
            return False
    except Exception as e:
        logger.warning("[Reflection] 写入 mem0 异常（agent=%s）: %s", agent_id, e)
        return False


def _extract_json(text: str) -> Optional[str]:
    """从 LLM 输出中提取 JSON 对象字符串。

    尝试两种方式：
    1. 优先提取 ```json ... ``` 代码块
    2. 回退到找第一个 { ... } 对

    Args:
        text: LLM 输出文本

    Returns:
        合法的 JSON 字符串，或 None（如果无法提取）
    """
    if not text or not text.strip():
        return None

    # 方式1：提取 ```json ... ``` 代码块
    m = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    candidate = m.group(1).strip() if m else text.strip()

    # 方式2：找第一个 { ... } 对
    start = candidate.find("{")
    end = candidate.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None

    json_str = candidate[start:end + 1]

    # 验证是合法 JSON
    try:
        json.loads(json_str)
        return json_str
    except json.JSONDecodeError:
        return None


# ================================================================
#  反思教训召回（闭环 L2/L3）
#
# 写入闭环已在 run_reflection 中完成（写入 mem0）。
# 召回闭环在此处实现：从 mem0 召回 memory_kind 含 _lesson 的结构化教训，
# 注入到研究员/复盘/辩论节点的 prompt 中，让历史经验真正影响输出。
# ================================================================


def recall_lessons_sync(
    *,
    db: Any,
    user_id: str,
    query: str,
    agent_id: str = "",
    limit: int = 3,
    max_chars: int = 1500,
) -> str:
    """从 mem0 召回反思教训（sync 包装器，供 LangGraph 节点调用）。

    优先返回 memory_kind 含 _lesson 的结构化教训。
    失败时返回空字符串，不阻塞主流程。

    Args:
        db: MongoDB 数据库句柄
        user_id: 用户 ID
        query: 查询文本（通常是股票代码 + 关键信息）
        agent_id: 限定 Agent
        limit: 最大返回条数
        max_chars: 最大返回字符数

    Returns:
        格式化的教训文本，或空字符串
    """
    try:
        try:
            asyncio.get_running_loop()
            running_loop = True
        except RuntimeError:
            running_loop = False

        if not running_loop:
            return asyncio.run(_recall_lessons_async(
                db=db, user_id=user_id, query=query,
                agent_id=agent_id, limit=limit, max_chars=max_chars,
            ))

        # 有运行中的事件循环，在新线程中运行
        result_holder: Dict[str, Any] = {"text": ""}

        def _run_in_thread() -> None:
            try:
                result_holder["text"] = asyncio.run(_recall_lessons_async(
                    db=db, user_id=user_id, query=query,
                    agent_id=agent_id, limit=limit, max_chars=max_chars,
                ))
            except Exception as exc:
                logger.warning("[Recall] sync 包装器线程异常: %s", exc)

        t = threading.Thread(target=_run_in_thread, daemon=True)
        t.start()
        t.join(timeout=15)
        return result_holder.get("text", "")
    except Exception as exc:
        logger.warning("[Recall] recall_lessons_sync 异常: %s", exc)
        return ""


async def _recall_lessons_async(
    *,
    db: Any,
    user_id: str,
    query: str,
    agent_id: str = "",
    limit: int = 3,
    max_chars: int = 1500,
) -> str:
    """从 mem0 召回反思教训（async 实现）。"""
    try:
        svc = get_memory_service(db)
        if not svc.available:
            return ""

        # 查询所有可能含教训的 scope
        items = await svc.recall(
            query=query,
            user_id=user_id,
            agent_id=agent_id,
            scopes=[
                MemoryScope.ANALYSIS_INSIGHT.value,
                MemoryScope.TRADE_PATTERN.value,
                MemoryScope.AGENT_EXPERIENCE.value,
            ],
            limit=max(limit * 3, 9),  # 扩大候选集，客户端过滤教训
        )
        if not items:
            return ""

        # 客户端过滤：只保留 memory_kind 含 _lesson 的教训
        lessons = []
        for item in items:
            meta = getattr(item, "metadata", None) or {}
            kind = meta.get("memory_kind", "")
            if "_lesson" in kind:
                lessons.append(item)

        if not lessons:
            return ""

        # 限制条数和字符数
        lines = []
        total = 0
        for item in lessons[:limit]:
            content = getattr(item, "content", "") or ""
            kind = (getattr(item, "metadata", None) or {}).get("memory_kind", "")
            scope = getattr(item, "scope", "") or ""
            # 标注教训类型
            kind_label = {
                "analysis_lesson": "分析教训",
                "trade_lesson": "交易教训",
                "debate_lesson": "辩论教训",
            }.get(kind, "历史教训")
            line = f"[{kind_label}] {content}"
            if total + len(line) > max_chars:
                break
            lines.append(line)
            total += len(line)

        if not lines:
            return ""

        return "【历史教训】（来自反思节点，优先参考）\n" + "\n".join(lines) + "\n"
    except Exception as exc:
        logger.warning("[Recall] _recall_lessons_async 异常: %s", exc)
        return ""
