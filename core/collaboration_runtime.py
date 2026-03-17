"""
协作运行时模型

统一描述 Assistant、Workflow、Agent 之间的内部调用请求与结果，
为后续跨模块协作提供最小一致的运行时契约。
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


def utc_now() -> datetime:
    """返回 UTC 时间，统一内部运行时时间基准。"""
    return datetime.now(timezone.utc)


class CollaborationRuntimeModel(BaseModel):
    """兼容 Pydantic v1/v2 的基础序列化能力。"""

    def to_python_dict(self) -> Dict[str, Any]:
        if hasattr(self, "model_dump"):
            return self.model_dump(mode="python")
        return self.dict()


class InvocationSourceType(str, Enum):
    """内部调用来源类型。"""

    EXTERNAL_USER = "external_user"
    ASSISTANT = "assistant"
    WORKFLOW = "workflow"
    AGENT = "agent"
    SYSTEM = "system"


class InvocationTargetType(str, Enum):
    """内部调用目标类型。"""

    AGENT = "agent"
    WORKFLOW = "workflow"
    TOOL = "tool"


class InvocationStatus(str, Enum):
    """内部调用执行状态。"""

    SUCCEEDED = "succeeded"
    FAILED = "failed"


class InvocationProvenance(CollaborationRuntimeModel):
    """调用来源上下文。"""

    source_type: InvocationSourceType
    source_id: Optional[str] = None
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    thread_id: Optional[str] = None
    workflow_id: Optional[str] = None
    step_id: Optional[str] = None
    trigger: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class InvocationPolicy(CollaborationRuntimeModel):
    """执行策略。"""

    idempotency_key: str
    timeout_seconds: int = 180
    lane: str = "default"
    allow_partial: bool = False
    visible_to_caller: bool = True


class InvocationRequest(CollaborationRuntimeModel):
    """统一的内部调用请求。"""

    invocation_id: str
    target_type: InvocationTargetType
    target_id: str
    action: str = "execute"
    payload: Dict[str, Any] = Field(default_factory=dict)
    provenance: InvocationProvenance
    policy: InvocationPolicy
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utc_now)


class InvocationArtifactRef(CollaborationRuntimeModel):
    """调用产物引用。"""

    ref_type: str
    artifact_key: str
    title: str
    summary: str = ""
    source_collection: str = ""
    symbol: Optional[str] = None
    output_field: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

    def to_report_ref(self, status: Optional[str] = None) -> Dict[str, Any]:
        return {
            "ref_type": self.ref_type,
            "report_key": self.artifact_key,
            "source_collection": self.source_collection,
            "title": self.title,
            "symbol": self.symbol,
            "summary": self.summary,
            "status": status,
            "metadata": self.metadata,
            "created_at": utc_now(),
        }


class InvocationResult(CollaborationRuntimeModel):
    """统一的内部调用结果。"""

    invocation_id: str
    target_type: InvocationTargetType
    target_id: str
    status: InvocationStatus
    started_at: datetime
    completed_at: datetime = Field(default_factory=utc_now)
    output_text: str = ""
    structured_output: Dict[str, Any] = Field(default_factory=dict)
    output_field: Optional[str] = None
    artifacts: List[InvocationArtifactRef] = Field(default_factory=list)
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @property
    def succeeded(self) -> bool:
        return self.status == InvocationStatus.SUCCEEDED
