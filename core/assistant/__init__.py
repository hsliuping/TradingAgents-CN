"""智能助手质量架构（A11）。

模块职责：
- models:      证据集 / 回复候选 / 关卡结果数据契约
- defense:     回复质量防线（数字溯源、编造检测），从 service 收编的纯函数
- reply_gate:  契约型唯一质量出口（所有路径的回复都经过这里）
- paths:       路径注册表（显式优先级）与请求上下文
- lexicon:     词典事实源（股票名目录 / 品种闸门），阶段 4
- metrics:     质量埋点落库（S9），阶段 4

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
from .reply_gate import build_fallback_candidate
from .lexicon import (
    A_SHARE_CODE_RE,
    StockDirectory,
    detect_unsupported_asset,
    extract_a_share_code,
    stock_directory,
)
from .metrics import AssistantQualityMetrics, quality_metrics
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
    "build_fallback_candidate",
    "A_SHARE_CODE_RE",
    "StockDirectory",
    "detect_unsupported_asset",
    "extract_a_share_code",
    "stock_directory",
    "AssistantQualityMetrics",
    "quality_metrics",
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
