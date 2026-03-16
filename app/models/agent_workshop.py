"""
Agent 工坊相关数据模型
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from bson import ObjectId
from pydantic import BaseModel, ConfigDict, Field

from app.models.user import PyObjectId
from app.utils.timezone import now_tz


class AgentSpecStatus(str, Enum):
    """Agent 规格状态"""

    DRAFT = "draft"
    TESTING = "testing"
    ACTIVE = "active"
    ARCHIVED = "archived"


class AgentWorkshopStage(str, Enum):
    """Agent 工坊会话阶段"""

    GATHERING = "gathering"
    PLANNING = "planning"
    GAP_ANALYSIS = "gap-analysis"
    BUILDING = "building"
    EVALUATING = "evaluating"
    COMPLETED = "completed"


class AgentVersionStatus(str, Enum):
    """Agent 版本状态"""

    DRAFT = "draft"
    TESTING = "testing"
    ACTIVE = "active"
    ARCHIVED = "archived"


class AgentWorkshopMessage(BaseModel):
    """Agent 工坊消息"""

    role: str
    content: str
    timestamp: datetime = Field(default_factory=now_tz)

    model_config = ConfigDict(
        json_encoders={datetime: lambda dt: dt.isoformat() if dt else None},
    )


class AgentSpec(BaseModel):
    """Agent 规格定义"""

    id: Optional[PyObjectId] = Field(default_factory=PyObjectId, alias="_id")
    spec_id: str
    name: str
    domain: str = "general"
    target_users: List[str] = Field(default_factory=list)
    primary_goal: str = ""
    responsibilities: List[str] = Field(default_factory=list)
    non_goals: List[str] = Field(default_factory=list)
    inputs: List[str] = Field(default_factory=list)
    outputs: List[str] = Field(default_factory=list)
    success_criteria: List[str] = Field(default_factory=list)
    constraints: List[str] = Field(default_factory=list)
    preferred_methods: List[str] = Field(default_factory=list)
    sample_symbols: List[str] = Field(default_factory=list)
    status: AgentSpecStatus = AgentSpecStatus.DRAFT
    source: str = "agent_workshop"
    owner_user_id: str = ""
    latest_session_id: Optional[str] = None
    current_version_id: Optional[str] = None
    version_count: int = 0
    created_at: datetime = Field(default_factory=now_tz)
    updated_at: datetime = Field(default_factory=now_tz)

    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        json_encoders={ObjectId: str, datetime: lambda dt: dt.isoformat() if dt else None},
    )


class AgentWorkshopGapAnalysis(BaseModel):
    """资源缺口分析结果"""

    reusable_modules: List[str] = Field(default_factory=list)
    existing_tools: List[str] = Field(default_factory=list)
    suggested_tools: List[str] = Field(default_factory=list)
    suggested_skills: List[str] = Field(default_factory=list)
    manual_dependencies: List[str] = Field(default_factory=list)
    blocking_gaps: List[str] = Field(default_factory=list)
    fallback_strategy: List[str] = Field(default_factory=list)
    build_recommendations: List[str] = Field(default_factory=list)
    notes: List[str] = Field(default_factory=list)


class AgentWorkshopSession(BaseModel):
    """Agent 工坊会话"""

    id: Optional[PyObjectId] = Field(default_factory=PyObjectId, alias="_id")
    session_id: str
    spec_id: str
    user_id: str = ""
    stage: AgentWorkshopStage = AgentWorkshopStage.GATHERING
    current_round: int = 1
    messages: List[AgentWorkshopMessage] = Field(default_factory=list)
    current_spec_snapshot: AgentSpec
    pending_questions: List[str] = Field(default_factory=list)
    completeness_score: float = 0.0
    feasibility_status: str = "need-clarification"
    refusal_reason: str = ""
    gap_report: Optional[AgentWorkshopGapAnalysis] = None
    tooling_plan: Optional[Dict[str, Any]] = None
    proposed_version: Optional[Dict[str, Any]] = None
    created_at: datetime = Field(default_factory=now_tz)
    updated_at: datetime = Field(default_factory=now_tz)

    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        json_encoders={ObjectId: str, datetime: lambda dt: dt.isoformat() if dt else None},
    )


class AgentVersion(BaseModel):
    """Agent 版本记录"""

    id: Optional[PyObjectId] = Field(default_factory=PyObjectId, alias="_id")
    version_id: str
    spec_id: str
    version: int
    status: AgentVersionStatus = AgentVersionStatus.DRAFT
    agent_metadata: Dict[str, Any] = Field(default_factory=dict)
    prompt_template_ref: Dict[str, Any] = Field(default_factory=dict)
    required_tools: List[str] = Field(default_factory=list)
    required_skills: List[str] = Field(default_factory=list)
    output_schema: Dict[str, Any] = Field(default_factory=dict)
    evaluation_policy: Dict[str, Any] = Field(default_factory=dict)
    published_from_session_id: Optional[str] = None
    created_at: datetime = Field(default_factory=now_tz)
    updated_at: datetime = Field(default_factory=now_tz)

    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        json_encoders={ObjectId: str, datetime: lambda dt: dt.isoformat() if dt else None},
    )


class AgentBenchmarkCase(BaseModel):
    """基准样本用例"""

    case_id: str
    title: str
    input_payload: Dict[str, Any] = Field(default_factory=dict)
    expected_outputs: List[str] = Field(default_factory=list)
    required_keywords: List[str] = Field(default_factory=list)
    forbidden_keywords: List[str] = Field(default_factory=list)
    expected_methods: List[str] = Field(default_factory=list)


class AgentBenchmarkSampleSet(BaseModel):
    """基准样本集"""

    sample_set_id: str
    spec_id: str
    name: str
    domain: str = "general"
    description: str = ""
    cases: List[AgentBenchmarkCase] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=now_tz)
    updated_at: datetime = Field(default_factory=now_tz)

    model_config = ConfigDict(
        json_encoders={datetime: lambda dt: dt.isoformat() if dt else None},
    )


class AgentEvaluationReport(BaseModel):
    """Agent 评估报告"""

    id: Optional[PyObjectId] = Field(default_factory=PyObjectId, alias="_id")
    evaluation_id: str
    version_id: str
    evaluation_type: str
    sample_set_id: Optional[str] = None
    scores: Dict[str, Any] = Field(default_factory=dict)
    issues: List[str] = Field(default_factory=list)
    recommendations: List[str] = Field(default_factory=list)
    details: Dict[str, Any] = Field(default_factory=dict)
    decision: str = "revise"
    created_at: datetime = Field(default_factory=now_tz)
    updated_at: datetime = Field(default_factory=now_tz)

    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        json_encoders={ObjectId: str, datetime: lambda dt: dt.isoformat() if dt else None},
    )