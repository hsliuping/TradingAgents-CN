"""智能助手质量架构（A11）—— 路径注册表（设计文档 §3.5）。

把"按代码书写顺序 if/return"的隐式路由（S5）变为：
- 显式 priority（数字越小越优先）；
- 每条路径声明 route_id / route_type（answer 必经 LLM 与 gate）；
- 注册后才可能触达用户——架构上不存在绕过 ReplyGate 的旁路（S1）。

新增路径的成本从"随便 return"变为：实现 handler + register + 声明类型。
本模块不依赖 service（避免循环 import）；策略 handler 由 service 装配，
第一个返回 ReplyCandidate 的路径胜出，main 路径必须兜底（不得返回 None）。
"""

from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Dict, List, Optional

from .models import ROUTE_TYPE_ANSWER, ReplyCandidate

# ─────────────────────────── 路径 ID 与显式优先级 ───────────────────────────

ROUTE_HITL = "hitl"
ROUTE_UNSUPPORTED_ASSET = "unsupported_asset"
ROUTE_LLM_UNAVAILABLE = "llm_unavailable"
ROUTE_FAST_SEARCH = "fast_search"
ROUTE_DATA_PRECHECK = "data_precheck"
ROUTE_MAIN_LLM = "main_llm"
# 降级/异常路径（不由注册表直接产出，供适配器统一构造）
ROUTE_TIMEOUT = "timeout"
ROUTE_ERROR = "error"

# 数字越小越优先。顺序沿用重构前 chat() 的实际 precedence（快路径在预检查之前：
# "最新/近期"问题即使数据未同步也先走互联网搜索总结），重构不改变路由行为。
PRIORITY_HITL = 10
PRIORITY_UNSUPPORTED_ASSET = 20
PRIORITY_LLM_UNAVAILABLE = 30
PRIORITY_FAST_SEARCH = 40
PRIORITY_DATA_PRECHECK = 50
PRIORITY_MAIN_LLM = 100

# 异步策略处理器：命中返回 ReplyCandidate，不命中返回 None；main 不允许返回 None
PathHandler = Callable[["AssistantRequest"], Awaitable[Optional[ReplyCandidate]]]


@dataclass
class AssistantRequest:
    """单次对话的上下文袋（JSON / SSE 两种模式共用）。

    on_progress：仅流式模式注入，用于把工具执行进度事件（tool_started 等）
    推给 SSE 适配器；非流式为 None。
    tools_used：主路径累积的工具名，适配器异常分支也要能拿到。
    """

    service: Any
    user_message: str
    conversation_id: Optional[str] = None
    assistant_settings: Optional[dict] = None
    is_im: bool = False
    history_messages: Optional[List[Any]] = None
    user_profile: Optional[dict] = None
    current_topic_title: Optional[str] = None
    memory_block: str = ""
    on_progress: Optional[Callable[[Dict[str, Any]], Awaitable[None]]] = None
    tools_used: List[str] = field(default_factory=list)


@dataclass
class RegisteredPath:
    route_id: str
    priority: int
    handler: PathHandler
    route_type: str = ROUTE_TYPE_ANSWER
    description: str = ""


class PathRegistry:
    """显式优先级路径注册表。装配一次、resolve 一次。"""

    def __init__(self) -> None:
        self._paths: List[RegisteredPath] = []

    def register(
        self,
        route_id: str,
        priority: int,
        handler: PathHandler,
        route_type: str = ROUTE_TYPE_ANSWER,
        description: str = "",
    ) -> "PathRegistry":
        if any(p.route_id == route_id for p in self._paths):
            raise ValueError(f"路径 {route_id!r} 重复注册")
        self._paths.append(
            RegisteredPath(
                route_id=route_id,
                priority=priority,
                handler=handler,
                route_type=route_type,
                description=description,
            )
        )
        return self

    def ordered(self) -> List[RegisteredPath]:
        return sorted(self._paths, key=lambda p: (p.priority, p.route_id))

    async def resolve(self, request: AssistantRequest) -> ReplyCandidate:
        """按优先级依次尝试；main 路径必须兜底，否则抛错（属于程序缺陷）。"""
        for path in self.ordered():
            candidate = await path.handler(request)
            if candidate is not None:
                candidate.meta.setdefault("route_priority", path.priority)
                return candidate
        raise RuntimeError("PathRegistry 无任何路径命中（main 路径必须兜底）")
