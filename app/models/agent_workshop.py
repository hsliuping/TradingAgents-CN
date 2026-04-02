"""
Agent 工坊相关数据模型
"""

import json
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Union

from bson import ObjectId
from pydantic import AliasChoices, BaseModel, ConfigDict, Field, model_validator

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


class AgentCapabilityRequirement(BaseModel):
    """规格中的能力项定义"""

    capability_key: str = ""
    capability_name: str = ""
    capability_type: str = ""
    description: str = ""
    delivery_requirement: str = ""
    acceptance_criteria: List[str] = Field(default_factory=list)


class AgentSpecIOField(BaseModel):
    """规格中的输入输出字段定义"""

    name: str = ""
    type: str = "string"
    required: bool = False
    description: str = ""


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
    inputs: List[Union[str, AgentSpecIOField]] = Field(default_factory=list)
    outputs: List[Union[str, AgentSpecIOField]] = Field(default_factory=list)
    success_criteria: List[str] = Field(default_factory=list)
    constraints: List[str] = Field(default_factory=list)
    preferred_methods: List[str] = Field(default_factory=list)
    capability_requirements: List[AgentCapabilityRequirement] = Field(default_factory=list)
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

    @model_validator(mode="before")
    @classmethod
    def _compat_io_fields(cls, data: Any) -> Any:
        """兼容旧格式：允许字符串、JSON 字符串和对象数组混用。"""
        if not isinstance(data, dict):
            return data

        for key in ("inputs", "outputs"):
            items = data.get(key)
            if not isinstance(items, list):
                continue

            normalized: List[Any] = []
            for item in items:
                if not isinstance(item, str):
                    normalized.append(item)
                    continue

                text = item.strip()
                if not text:
                    continue

                if text.startswith("{") and text.endswith("}"):
                    try:
                        parsed = json.loads(text)
                    except Exception:
                        normalized.append(text)
                    else:
                        normalized.append(parsed if isinstance(parsed, dict) else text)
                    continue

                normalized.append(text)

            data[key] = normalized

        return data


class SuggestedToolItem(BaseModel):
    """建议补齐的工具/能力条目"""

    tool_id: str = ""
    description: str = ""
    why_needed: str = ""


class AgentWorkshopGapAnalysis(BaseModel):
    """资源缺口分析结果"""

    existing_tools: List[str] = Field(default_factory=list)
    suggested_tools: List[SuggestedToolItem] = Field(default_factory=list)
    suggested_capabilities: List[SuggestedToolItem] = Field(
        default_factory=list,
        validation_alias=AliasChoices("suggested_capabilities", "suggested_skills"),
        serialization_alias="suggested_capabilities",
    )
    manual_dependencies: List[str] = Field(default_factory=list)
    blocking_gaps: List[str] = Field(default_factory=list)
    fallback_strategy: List[str] = Field(default_factory=list)
    build_recommendations: List[str] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def _compat_string_arrays(cls, data: Any) -> Any:
        """兼容旧格式：将纯字符串数组自动转换为 SuggestedToolItem 对象数组"""
        if isinstance(data, dict):
            for key in ("suggested_tools", "suggested_capabilities", "suggested_skills"):
                items = data.get(key)
                if isinstance(items, list):
                    data[key] = [
                        {"tool_id": item, "description": "", "why_needed": ""}
                        if isinstance(item, str)
                        else item
                        for item in items
                    ]
        return data
    notes: List[str] = Field(default_factory=list)
    generated_by: str = ""
    error_message: str = ""
    raw_response: str = ""


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


class AgentExecutionPlanStep(BaseModel):
    """Agent 版本执行验证步骤"""

    step_id: str = ""
    title: str = ""
    objective: str = ""
    suggested_tools: List[str] = Field(default_factory=list)
    expected_evidence: List[str] = Field(default_factory=list)
    failure_signals: List[str] = Field(default_factory=list)


class AgentExecutionValidationPlan(BaseModel):
    """Agent 版本的执行验证计划"""

    mode: str = "tool-driven"
    validation_status: str = "not-run"
    rationale: str = ""
    sample_input: Dict[str, Any] = Field(default_factory=dict)
    execution_steps: List[AgentExecutionPlanStep] = Field(default_factory=list)
    acceptance_checks: List[str] = Field(default_factory=list)
    fallback_rules: List[str] = Field(default_factory=list)


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
    required_capabilities: List[str] = Field(
        default_factory=list,
        validation_alias=AliasChoices("required_capabilities", "required_skills"),
        serialization_alias="required_capabilities",
    )
    output_schema: Dict[str, Any] = Field(default_factory=dict)
    evaluation_policy: Dict[str, Any] = Field(default_factory=dict)
    execution_plan: AgentExecutionValidationPlan = Field(default_factory=AgentExecutionValidationPlan)
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