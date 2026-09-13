"""智能助手质量架构（A11）—— 数据契约。

核心概念见设计文档 §3.2：
- Evidence：一条回复生成所依据的原文（证据集一等公民）
- ReplyCandidate：策略产出的候选回复，携带证据 + 路径类型契约
- GateResult：质量关卡的裁决

路径类型契约（治 B 类"裸透传"的根本手段）：
- answer：面向用户问题的回答，契约上必须经 LLM 处理（llm_processed=True），
  并过全套 A 类溯源检查；
- passthrough_allowed：登记过的系统直出（HITL 回执/数据同步提示/降级回退等），
  route_id 必须在 REGISTERED_PASSTHROUGH 白名单内。
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

# 路径类型
ROUTE_TYPE_ANSWER = "answer"
ROUTE_TYPE_PASSTHROUGH = "passthrough_allowed"

# 证据来源类型
EVIDENCE_TOOL = "tool"
EVIDENCE_SEARCH = "search"
EVIDENCE_USER_MESSAGE = "user_message"
EVIDENCE_HISTORY_TOOL = "history_tool"
EVIDENCE_MEMORY = "memory"

# 可作为"数据源引用"展示给前端的证据类型
_PRESENTABLE_SOURCE_TYPES = frozenset({EVIDENCE_TOOL, EVIDENCE_SEARCH})

# 登记过的系统直出路径白名单（新增需评审，见设计文档 §3.3 / 风险表）
REGISTERED_PASSTHROUGH = frozenset(
    {
        "hitl",               # HITL 确认/拒绝操作回执
        "unsupported_asset",  # 不支持品种的系统提示
        "data_precheck",      # 数据同步引导提示
        "llm_unavailable",    # LLM 客户端不可用提示
        "timeout",            # 超时提示
        "error",              # 异常兜底提示
        "fallback_evidence",  # 关卡降级：局限说明 + 证据原文
    }
)


@dataclass
class Evidence:
    """一条证据原文。

    Attributes:
        source_type: EVIDENCE_* 常量
        source_id:   工具名 / "searxng" / "mem0" 等
        content:     原文（数字溯源可信候选集的来源）
        locator:     可选的数据源定位（报告ID/文件路径等），供前端回链
    """

    source_type: str
    source_id: str
    content: str
    locator: Optional[str] = None


@dataclass
class ReplyCandidate:
    """策略产出的候选回复。

    优先使用工厂方法构造：
    - ReplyCandidate.answer(..., llm_processed=True)：answer 型，llm_processed
      为必传关键字参数，强制调用方显式声明确实经过 LLM；
    - ReplyCandidate.passthrough(...)：登记白名单内的系统直出。
    """

    reply: str
    route_id: str
    route_type: str
    tools_used: List[str] = field(default_factory=list)
    evidence: List[Evidence] = field(default_factory=list)
    llm_processed: bool = False
    meta: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def answer(
        cls,
        reply: str,
        route_id: str,
        *,
        llm_processed: bool,
        tools_used: Optional[List[str]] = None,
        evidence: Optional[List[Evidence]] = None,
        meta: Optional[Dict[str, Any]] = None,
    ) -> "ReplyCandidate":
        """构造 answer 型候选。llm_processed 必传——禁止默认当作"已过 LLM"。"""
        return cls(
            reply=reply,
            route_id=route_id,
            route_type=ROUTE_TYPE_ANSWER,
            tools_used=list(tools_used or []),
            evidence=list(evidence or []),
            llm_processed=bool(llm_processed),
            meta=dict(meta or {}),
        )

    @classmethod
    def passthrough(
        cls,
        reply: str,
        route_id: str,
        *,
        tools_used: Optional[List[str]] = None,
        evidence: Optional[List[Evidence]] = None,
        meta: Optional[Dict[str, Any]] = None,
    ) -> "ReplyCandidate":
        """构造 passthrough_allowed 型候选（route_id 由 gate 校验白名单）。"""
        return cls(
            reply=reply,
            route_id=route_id,
            route_type=ROUTE_TYPE_PASSTHROUGH,
            tools_used=list(tools_used or []),
            evidence=list(evidence or []),
            llm_processed=False,
            meta=dict(meta or {}),
        )


@dataclass
class CheckFailure:
    """单条质量检查失败。"""

    check: str
    reason: str


@dataclass
class GateResult:
    """质量关卡裁决。"""

    passed: bool
    failures: List[CheckFailure] = field(default_factory=list)

    @property
    def failed_checks(self) -> List[str]:
        return [f.check for f in self.failures]


def extract_data_refs(evidence: Optional[List[Evidence]]) -> List[Dict[str, Any]]:
    """从证据集提取前端可展示的数据引用（data_refs 真实现）。

    仅 tool/search 类证据生成引用；按 (类型,来源,定位) 去重。
    user_message/history/memory 不作为"外部数据源链接"展示。
    """
    refs: List[Dict[str, Any]] = []
    seen = set()
    for ev in evidence or []:
        if ev.source_type not in _PRESENTABLE_SOURCE_TYPES:
            continue
        key = (ev.source_type, ev.source_id, ev.locator)
        if key in seen:
            continue
        seen.add(key)
        refs.append(
            {
                "source_type": ev.source_type,
                "source_id": ev.source_id,
                "locator": ev.locator,
            }
        )
    return refs
