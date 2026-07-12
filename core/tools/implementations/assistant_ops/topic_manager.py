"""
智能助手主题管理工具

让 AI 可以直接创建研究主题、创建子主题、查看主题树、删除主题树。
用户身份和当前主题上下文通过 core.tools.context 获取。
"""

import logging
from typing import Annotated, List, Optional

from langchain_core.tools import tool

from core.tools.base import register_tool
from core.tools.context import get_current_assistant_thread_id, get_current_im_channel, require_current_user_id, set_current_assistant_thread_id

logger = logging.getLogger(__name__)


async def _load_threads(db, user_id: str) -> List[dict]:
    cursor = db.assistant_threads.find({
        "user_id": user_id,
        "archived": {"$ne": True},
    }).sort([("pinned", -1), ("updated_at", -1)])
    docs = await cursor.to_list(length=None)
    return [
        doc for doc in docs
        if (doc.get("topic_type") or "") != "im_session" and not _is_gateway_session_thread_id(doc.get("thread_id"))
    ]


def _is_gateway_session_thread_id(thread_id: Optional[str]) -> bool:
    return bool(thread_id and ":" in thread_id)


async def _get_current_im_session(db, user_id: str) -> Optional[dict]:
    im_channel = get_current_im_channel()
    if not im_channel:
        return None

    from core.gateway.session import SessionManager

    session_manager = SessionManager(db)
    return await session_manager.get_or_create(
        user_id,
        im_channel.get("channel_type") or "",
        im_channel.get("channel_id") or "",
    )


async def _bind_current_topic(db, user_id: str, thread_id: Optional[str]) -> None:
    session = await _get_current_im_session(db, user_id)
    if session:
        from core.gateway.session import SessionManager

        session_manager = SessionManager(db)
        await session_manager.set_current_topic_id(session.get("session_key") or "", thread_id)

    set_current_assistant_thread_id(thread_id)


async def _get_bound_current_topic_id(db, user_id: str) -> Optional[str]:
    current_thread_id = (get_current_assistant_thread_id() or "").strip() or None
    if current_thread_id and not _is_gateway_session_thread_id(current_thread_id):
        return current_thread_id

    session = await _get_current_im_session(db, user_id)
    if not session:
        return None

    context = session.get("context") or {}
    return (context.get("current_topic_id") or "").strip() or None


async def _get_bound_current_topic_doc(db, user_id: str) -> Optional[dict]:
    current_topic_id = await _get_bound_current_topic_id(db, user_id)
    if not current_topic_id:
        return None
    return await db.assistant_threads.find_one({
        "user_id": user_id,
        "thread_id": current_topic_id,
        "archived": {"$ne": True},
    })


def _normalize_title(title: str) -> str:
    text = (title or "").strip().lower()
    if not text:
        return ""

    replacements = {
        "新能源汽车": "新能源车",
        "新能源汽車": "新能源车",
        "个股": "公司",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)

    for token in ["（", "）", "(", ")", "-", "_", " ", "　", "/", "\\", "·", "、"]:
        text = text.replace(token, "")

    removable_suffixes = [
        "研究主题",
        "产业链研究",
        "行业研究",
        "板块研究",
        "公司研究",
        "个股研究",
        "深度研究",
        "专题研究",
        "课题研究",
        "产业链",
        "行业",
        "板块",
        "研究",
        "分析",
        "跟踪",
        "专题",
        "主题",
    ]
    changed = True
    while changed and len(text) > 2:
        changed = False
        for suffix in removable_suffixes:
            if text.endswith(suffix) and len(text) > len(suffix) + 1:
                text = text[: -len(suffix)]
                changed = True
                break

    return text


def _titles_match(first: str, second: str) -> bool:
    normalized_first = _normalize_title(first)
    normalized_second = _normalize_title(second)
    if not normalized_first or not normalized_second:
        return False
    return normalized_first == normalized_second


def _find_matching_thread(docs: List[dict], title: str, parent_thread_id: Optional[str] = None) -> Optional[dict]:
    normalized_parent_id = (parent_thread_id or "").strip() or None
    candidates = [doc for doc in docs if (doc.get("parent_thread_id") or None) == normalized_parent_id]
    for doc in candidates:
        if _titles_match(doc.get("title") or "", title):
            return doc
    return None


def _format_thread_tree(docs: List[dict]) -> str:
    by_parent = {}
    by_id = {}
    for doc in docs:
        thread_id = doc.get("thread_id")
        by_id[thread_id] = doc
        by_parent.setdefault(doc.get("parent_thread_id"), []).append(doc)

    def _sort(items: List[dict]) -> List[dict]:
        return sorted(
            items,
            key=lambda item: (
                0 if item.get("pinned") else 1,
                -(item.get("updated_at").timestamp() if item.get("updated_at") else 0),
            ),
        )

    lines: List[str] = []

    def _walk(parent_id: Optional[str], depth: int = 0):
        for item in _sort(by_parent.get(parent_id, [])):
            prefix = "  " * depth + ("- " if depth else "• ")
            label = item.get("title") or "未命名主题"
            count = int(item.get("message_count") or 0)
            lines.append(f"{prefix}{label} [{item.get('thread_id')}]（{count} 条消息）")
            _walk(item.get("thread_id"), depth + 1)

    _walk(None)
    return "\n".join(lines)


async def _resolve_parent_thread_id(db, user_id: str, parent_title: Optional[str]) -> Optional[str]:
    title = (parent_title or "").strip()
    if not title:
        return await _get_bound_current_topic_id(db, user_id)

    all_docs = await _load_threads(db, user_id)
    matched = _find_matching_thread(all_docs, title, parent_thread_id=None)
    if matched:
        return matched.get("thread_id")

    docs = await db.assistant_threads.find({
        "user_id": user_id,
        "title": title,
        "archived": {"$ne": True},
    }).to_list(length=5)

    if not docs:
        raise ValueError(f"未找到标题为「{title}」的主题")
    if len(docs) > 1:
        raise ValueError(f"找到多个同名主题「{title}」，请先让我列出主题树后再指定更精确的父主题")
    return docs[0].get("thread_id")


async def _resolve_target_thread_id(db, user_id: str, title: Optional[str]) -> Optional[str]:
    normalized_title = (title or "").strip()
    if not normalized_title:
        return await _get_bound_current_topic_id(db, user_id)

    all_docs = await _load_threads(db, user_id)
    exact_or_semantic = [doc for doc in all_docs if _titles_match(doc.get("title") or "", normalized_title)]
    if len(exact_or_semantic) == 1:
        return exact_or_semantic[0].get("thread_id")
    if len(exact_or_semantic) > 1:
        raise ValueError(f"找到多个语义相近的主题「{normalized_title}」，请先让我列出主题树后再指定更精确的目标主题")

    docs = await db.assistant_threads.find({
        "user_id": user_id,
        "title": normalized_title,
        "archived": {"$ne": True},
    }).to_list(length=5)

    if not docs:
        raise ValueError(f"未找到标题为「{normalized_title}」的主题")
    if len(docs) > 1:
        raise ValueError(f"找到多个同名主题「{normalized_title}」，请先让我列出主题树后再指定更精确的目标主题")
    return docs[0].get("thread_id")


@tool
@register_tool(
    tool_id="list_assistant_topics",
    name="查看研究主题树",
    description="列出当前用户的研究主题树。返回主题层级缩进、主题ID和各主题消息数量，便于查看研究目录结构。",
    when_to_use="当用户想查看当前研究目录、主题结构、行业与公司子主题层级时使用。",
    category="assistant_ops",
    is_online=True,
    auto_register=True,
    timeout_tier="light",
    data_source_handling="local_only",
    capability_tags=["topic_management", "research_topic", "topic_tree", "list", "query", "assistant_ops", "thread_management", "topic_hierarchy", "topic_structure", "research_directory"],
    tool_role_hint="primary",
    output_shape="text",
    preferred_for=["topic_tree_viewing", "research_structure_browsing", "topic_hierarchy_query", "thread_listing", "research_directory_viewing"],
    returns="返回文本格式的主题树，包含主题层级缩进、主题ID和各主题消息数量。",
)
async def list_assistant_topics() -> str:
    """查看当前用户的研究主题树。"""
    from app.core.database import get_mongo_db

    user_id = require_current_user_id()
    db = get_mongo_db()
    docs = await _load_threads(db, user_id)
    if not docs:
        return "📁 当前还没有研究主题。你可以让我先创建一个行业或公司主题。"
    current_topic = await _get_bound_current_topic_doc(db, user_id)
    current_topic_line = ""
    if current_topic:
        current_topic_line = f"🎯 当前外部会话主题：{current_topic.get('title') or current_topic.get('thread_id')}\n"
    return current_topic_line + "📁 当前研究主题树：\n" + _format_thread_tree(docs)


@tool
@register_tool(
    tool_id="create_assistant_topic",
    name="创建研究主题",
    description="创建新的顶层研究主题，用于行业、策略或独立研究主线。返回创建结果（新建/复用）和主题ID。",
    when_to_use="当用户明确表示要新建研究主题、行业目录、研究主线时使用。",
    category="assistant_ops",
    is_online=True,
    auto_register=True,
    timeout_tier="light",
    data_source_handling="local_only",
    capability_tags=["topic_management", "research_topic", "create", "assistant_ops", "thread_management", "topic_creation", "research_mainline", "new_topic"],
    tool_role_hint="primary",
    output_shape="text",
    preferred_for=["topic_creation", "research_mainline_setup", "new_topic_initialization", "research_directory_creation"],
    returns="返回文本消息，包含创建结果（新建/复用）和主题ID。",
)
async def create_assistant_topic(
    title: Annotated[str, "要创建的主题名称，如 电池行业跟踪 或 券商板块研究"],
) -> str:
    """创建顶层研究主题。"""
    from app.core.database import get_mongo_db
    from app.services.intelligent_assistant_service import create_assistant_thread

    user_id = require_current_user_id()
    db = get_mongo_db()
    current_topic = await _get_bound_current_topic_doc(db, user_id)
    if current_topic and _titles_match(current_topic.get("title") or "", title):
        await _bind_current_topic(db, user_id, current_topic.get("thread_id"))
        return (
            f"ℹ️ 当前就在语义相同的主题「{current_topic.get('title') or title}」下，"
            f"无需重复创建。\n- 主题ID: {current_topic.get('thread_id')}"
        )

    item = await create_assistant_thread(db, user_id, title=title, parent_thread_id=None)
    await _bind_current_topic(db, user_id, item["thread_id"])
    if _titles_match(item.get("title") or "", title):
        return f"✅ 已创建并切换到研究主题「{item['title']}」\n- 主题ID: {item['thread_id']}"
    return f"ℹ️ 已复用并切换到语义相近的现有主题「{item['title']}」\n- 主题ID: {item['thread_id']}"


@tool
@register_tool(
    tool_id="create_assistant_subtopic",
    name="创建研究子主题",
    description="在当前或指定父主题下创建子主题（行业拆公司、公司拆估值等）。返回子主题创建结果、父主题和子主题ID。",
    when_to_use="当用户说‘在这个主题下新增子主题’、‘在某个行业下面加公司’、‘拆一个子问题出来’时使用。",
    category="assistant_ops",
    is_online=True,
    auto_register=True,
    timeout_tier="light",
    data_source_handling="local_only",
    capability_tags=["topic_management", "research_topic", "create", "subtopic", "assistant_ops", "thread_management", "topic_hierarchy", "subtopic_creation", "child_topic"],
    tool_role_hint="primary",
    output_shape="text",
    preferred_for=["subtopic_creation", "topic_branching", "research_subdivision", "child_topic_setup"],
    returns="返回文本消息，包含子主题创建结果、父主题ID和子主题ID。",
)
async def create_assistant_subtopic(
    title: Annotated[str, "子主题名称，如 宁德时代、估值拆解、风险点"],
    parent_title: Annotated[Optional[str], "可选，父主题标题；不填时默认挂到当前正在讨论的主题下"] = None,
) -> str:
    """创建研究子主题。"""
    from app.core.database import get_mongo_db
    from app.services.intelligent_assistant_service import create_assistant_thread

    user_id = require_current_user_id()
    db = get_mongo_db()
    try:
        parent_thread_id = await _resolve_parent_thread_id(db, user_id, parent_title)
    except ValueError as exc:
        return f"❌ {str(exc)}"

    if not parent_thread_id:
        return "❌ 当前没有可用的父主题。请先创建一个研究主题，或明确告诉我要挂到哪个主题下面。"

    all_docs = await _load_threads(db, user_id)
    similar_child = _find_matching_thread(all_docs, title, parent_thread_id=parent_thread_id)
    if similar_child:
        return (
            f"ℹ️ 当前主题下已存在语义相近的子主题「{similar_child.get('title') or title}」，"
            f"无需重复创建。\n- 子主题ID: {similar_child.get('thread_id')}"
        )

    item = await create_assistant_thread(db, user_id, title=title, parent_thread_id=parent_thread_id)
    return (
        f"✅ 已创建子主题「{item['title']}」\n"
        f"- 当前会话仍绑定父主题: {parent_thread_id}\n"
        f"- 父主题ID: {parent_thread_id}\n"
        f"- 子主题ID: {item['thread_id']}"
    )


@tool
@register_tool(
    tool_id="get_current_assistant_topic",
    name="查看当前研究主题",
    description="查看当前外部会话绑定的研究主题。返回主题名称和主题ID，便于确认后续讨论归属的研究主线。",
    when_to_use="当用户问当前在聊哪个主题、这个主题是什么、现在挂在哪个研究目录下时使用。",
    category="assistant_ops",
    is_online=True,
    auto_register=True,
    timeout_tier="light",
    data_source_handling="local_only",
    capability_tags=["topic_management", "research_topic", "query", "current_topic", "assistant_ops", "thread_management", "context_query", "session_context"],
    tool_role_hint="supporting",
    output_shape="text",
    preferred_for=["current_topic_query", "session_context_check", "active_topic_verification"],
    returns="返回文本消息，包含当前主题名称和主题ID。",
)
async def get_current_assistant_topic() -> str:
    """查看当前外部会话绑定的研究主题。"""
    from app.core.database import get_mongo_db

    user_id = require_current_user_id()
    db = get_mongo_db()
    current_topic = await _get_bound_current_topic_doc(db, user_id)
    if not current_topic:
        return "ℹ️ 当前外部会话还没有绑定研究主题。你可以先让我创建一个主题，或者明确说“切换到某个主题”。"
    return (
        f"🎯 当前研究主题：{current_topic.get('title') or current_topic.get('thread_id')}\n"
        f"- 主题ID: {current_topic.get('thread_id')}"
    )


@tool
@register_tool(
    tool_id="switch_assistant_topic",
    name="切换当前研究主题",
    description="将当前会话切换绑定到某个已有研究主题，后续讨论默认指向该主题。返回切换结果和目标主题ID。",
    when_to_use="当用户明确要求切换到某个主题、继续另一个行业或公司主题、或指定当前会话应绑定到某条研究主线时使用。",
    category="assistant_ops",
    is_online=True,
    auto_register=True,
    timeout_tier="light",
    data_source_handling="local_only",
    capability_tags=["topic_management", "research_topic", "switch", "assistant_ops", "thread_management", "topic_switching", "context_binding", "active_topic_change"],
    tool_role_hint="primary",
    output_shape="text",
    preferred_for=["topic_switching", "research_mainline_change", "session_binding_update", "active_topic_selection"],
    returns="返回文本消息，包含切换结果和目标主题ID。",
)
async def switch_assistant_topic(
    title: Annotated[str, "要切换到的主题标题，如 新能源车研究、宁德时代、券商板块研究"],
) -> str:
    """切换当前外部会话绑定的研究主题。"""
    from app.core.database import get_mongo_db

    user_id = require_current_user_id()
    db = get_mongo_db()
    try:
        thread_id = await _resolve_target_thread_id(db, user_id, title)
    except ValueError as exc:
        return f"❌ {str(exc)}"

    if not thread_id:
        return "❌ 没有找到可切换的目标主题。请先创建主题，或提供更精确的主题标题。"

    target = await db.assistant_threads.find_one({
        "user_id": user_id,
        "thread_id": thread_id,
        "archived": {"$ne": True},
    })
    if not target:
        return "❌ 目标主题不存在或已删除。"

    await _bind_current_topic(db, user_id, thread_id)
    return (
        f"✅ 已切换当前研究主题到「{target.get('title') or thread_id}」\n"
        f"- 主题ID: {thread_id}"
    )


@tool
@register_tool(
    tool_id="delete_assistant_topic",
    name="删除研究主题树",
    description="删除研究主题及其全部子主题、消息和摘要（默认当前主题或按标题）。返回删除主题数量和主题ID列表。",
    when_to_use="仅当用户明确要求删除某个研究主题、清理某条研究主线、或删除当前主题及其子主题时使用。涉及破坏性操作，必须在用户明确表达删除意图后调用。",
    category="assistant_ops",
    is_online=True,
    auto_register=True,
    timeout_tier="light",
    data_source_handling="local_only",
    capability_tags=["topic_management", "research_topic", "delete", "assistant_ops", "thread_management", "topic_deletion", "destructive_operation", "topic_tree_removal"],
    tool_role_hint="primary",
    output_shape="text",
    preferred_for=["topic_deletion", "research_cleanup", "topic_tree_removal", "theme_removal"],
    returns="返回文本消息，包含删除结果、删除主题数和删除的主题ID列表。",
)
async def delete_assistant_topic(
    title: Annotated[Optional[str], "可选，要删除的主题标题；不填时默认删除当前主题"] = None,
) -> str:
    """删除研究主题树。"""
    from app.core.database import get_mongo_db
    from app.services.intelligent_assistant_service import ASSISTANT_DEFAULT_THREAD_ID, delete_assistant_thread

    user_id = require_current_user_id()
    db = get_mongo_db()

    try:
        thread_id = await _resolve_target_thread_id(db, user_id, title)
    except ValueError as exc:
        return f"❌ {str(exc)}"

    if not thread_id:
        return "❌ 当前没有可删除的目标主题。请先指定主题标题，或在某个主题下再执行删除。"
    if thread_id == ASSISTANT_DEFAULT_THREAD_ID:
        return "❌ 默认主题不能删除。请切换到其他主题，或删除默认主题下的子主题。"

    target = await db.assistant_threads.find_one({
        "user_id": user_id,
        "thread_id": thread_id,
        "archived": {"$ne": True},
    })
    if not target:
        return "❌ 目标主题不存在或已删除。"

    try:
        deleted_ids = await delete_assistant_thread(db, user_id, thread_id)
    except ValueError as exc:
        return f"❌ {str(exc)}"

    current_topic_id = await _get_bound_current_topic_id(db, user_id)
    if current_topic_id and current_topic_id in deleted_ids:
        fallback_topic_id = (target.get("parent_thread_id") or "").strip() or None
        await _bind_current_topic(db, user_id, fallback_topic_id)

    deleted_count = len(deleted_ids)
    return (
        f"✅ 已删除主题树「{target.get('title') or thread_id}」\n"
        f"- 删除主题数: {deleted_count}\n"
        f"- 删除主题ID: {', '.join(deleted_ids)}"
    )