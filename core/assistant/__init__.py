"""智能助手质量架构（A11）。

模块职责：
- models:      证据集 / 回复候选 / 关卡结果数据契约
- defense:     回复质量防线（数字溯源、编造检测），从 service 收编的纯函数
- reply_gate:  契约型唯一质量出口（所有路径的回复都经过这里）

设计文档：docs/05-design/v3.0/assistant-quality-architecture-refactor.md
"""

from .models import (
    ROUTE_TYPE_ANSWER,
    ROUTE_TYPE_PASSTHROUGH,
    REGISTERED_PASSTHROUGH,
    EVIDENCE_TOOL,
    EVIDENCE_SEARCH,
    EVIDENCE_USER_MESSAGE,
    EVIDENCE_HISTORY_TOOL,
    EVIDENCE_MEMORY,
    Evidence,
    ReplyCandidate,
    CheckFailure,
    GateResult,
    extract_data_refs,
)
from .reply_gate import ReplyGate
from .paths import (
    AssistantRequest,
    PathRegistry,
    RegisteredPath,
    PathHandler,
    ROUTE_HITL,
    ROUTE_UNSUPPORTED_ASSET,
    ROUTE_LLM_UNAVAILABLE,
    ROUTE_FAST_SEARCH,
    ROUTE_DATA_PRECHECK,
    ROUTE_MAIN_LLM,
    ROUTE_TIMEOUT,
    ROUTE_ERROR,
    PRIORITY_HITL,
    PRIORITY_UNSUPPORTED_ASSET,
    PRIORITY_LLM_UNAVAILABLE,
    PRIORITY_FAST_SEARCH,
    PRIORITY_DATA_PRECHECK,
    PRIORITY_MAIN_LLM,
)

__all__ = [
    "ROUTE_TYPE_ANSWER",
    "ROUTE_TYPE_PASSTHROUGH",
    "REGISTERED_PASSTHROUGH",
    "EVIDENCE_TOOL",
    "EVIDENCE_SEARCH",
    "EVIDENCE_USER_MESSAGE",
    "EVIDENCE_HISTORY_TOOL",
    "EVIDENCE_MEMORY",
    "Evidence",
    "ReplyCandidate",
    "CheckFailure",
    "GateResult",
    "extract_data_refs",
    "ReplyGate",
    "AssistantRequest",
    "PathRegistry",
    "RegisteredPath",
    "PathHandler",
    "ROUTE_HITL",
    "ROUTE_UNSUPPORTED_ASSET",
    "ROUTE_LLM_UNAVAILABLE",
    "ROUTE_FAST_SEARCH",
    "ROUTE_DATA_PRECHECK",
    "ROUTE_MAIN_LLM",
    "ROUTE_TIMEOUT",
    "ROUTE_ERROR",
    "PRIORITY_HITL",
    "PRIORITY_UNSUPPORTED_ASSET",
    "PRIORITY_LLM_UNAVAILABLE",
    "PRIORITY_FAST_SEARCH",
    "PRIORITY_DATA_PRECHECK",
    "PRIORITY_MAIN_LLM",
]
