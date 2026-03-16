"""
Agent 成长相关数据模型
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from bson import ObjectId
from pydantic import BaseModel, ConfigDict, Field

from .user import PyObjectId
from app.utils.timezone import now_tz


class GrowthMemoryScope(str, Enum):
    """长期成长记忆的边界分类"""
    TASK_TEMP = "task_temp"
    OBJECT_TRACKING = "object_tracking"
    USER_PREFERENCE = "user_preference"
    RESEARCH_ASSET = "research_asset"
    PATTERN = "pattern"


class GrowthMemoryStatus(str, Enum):
    """记忆条目状态"""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"


class GrowthReviewLevel(str, Enum):
    """审核等级"""
    AUTO_PENDING = "auto_pending"
    MANUAL_REQUIRED = "manual_required"


class GrowthSuggestionStatus(str, Enum):
    """建议状态"""
    PENDING = "pending"
    ACCEPTED = "accepted"
    DISMISSED = "dismissed"
    EXPIRED = "expired"


class GrowthSuggestionType(str, Enum):
    """成长建议类型"""
    MEMORY_PROMOTION = "memory_promotion"
    RESEARCH_ASSET_PROMOTION = "research_asset_promotion"
    WORKFLOW_OPTIMIZATION = "workflow_optimization"
    WATCH_RULE_SUGGESTION = "watch_rule_suggestion"


class GrowthEvidenceRef(BaseModel):
    """成长证据引用"""
    type: str
    id: str
    label: Optional[str] = None


class AgentGrowthMemoryItem(BaseModel):
    """成长记忆条目"""
    id: Optional[PyObjectId] = Field(default_factory=PyObjectId, alias="_id")
    memory_id: str
    user_id: str
    scope: GrowthMemoryScope
    status: GrowthMemoryStatus = GrowthMemoryStatus.PENDING
    review_level: GrowthReviewLevel = GrowthReviewLevel.MANUAL_REQUIRED

    source_type: str
    source_id: str
    task_type: Optional[str] = None
    workflow_id: Optional[str] = None

    object_type: Optional[str] = None
    object_key: Optional[str] = None

    title: str
    summary: str = ""
    content: str
    structured_payload: Dict[str, Any] = Field(default_factory=dict)
    confidence: float = 0.0
    evidence_refs: List[GrowthEvidenceRef] = Field(default_factory=list)

    confirmed_by: Optional[str] = None
    confirmed_at: Optional[datetime] = None
    rejected_by: Optional[str] = None
    rejected_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None

    created_at: datetime = Field(default_factory=now_tz)
    updated_at: datetime = Field(default_factory=now_tz)

    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        json_encoders={ObjectId: str, datetime: lambda dt: dt.isoformat() if dt else None},
    )


class AgentGrowthSuggestion(BaseModel):
    """成长建议条目"""
    id: Optional[PyObjectId] = Field(default_factory=PyObjectId, alias="_id")
    suggestion_id: str
    user_id: str
    suggestion_type: GrowthSuggestionType
    status: GrowthSuggestionStatus = GrowthSuggestionStatus.PENDING

    source_type: str
    source_id: str
    task_type: Optional[str] = None
    workflow_id: Optional[str] = None
    object_type: Optional[str] = None
    object_key: Optional[str] = None

    title: str
    summary: str
    suggested_action: Dict[str, Any] = Field(default_factory=dict)
    confidence: float = 0.0
    source_refs: List[GrowthEvidenceRef] = Field(default_factory=list)

    accepted_by: Optional[str] = None
    accepted_at: Optional[datetime] = None
    dismissed_by: Optional[str] = None
    dismissed_at: Optional[datetime] = None

    created_at: datetime = Field(default_factory=now_tz)
    updated_at: datetime = Field(default_factory=now_tz)

    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        json_encoders={ObjectId: str, datetime: lambda dt: dt.isoformat() if dt else None},
    )


class TaskGrowthContext(BaseModel):
    """任务级成长提取摘要"""
    memory_items_count: int = 0
    suggestions_count: int = 0
    memory_item_ids: List[str] = Field(default_factory=list)
    suggestion_ids: List[str] = Field(default_factory=list)
    extracted_at: datetime = Field(default_factory=now_tz)
    source_type: str = "unified_analysis_task"
    source_id: Optional[str] = None

    model_config = ConfigDict(
        json_encoders={datetime: lambda dt: dt.isoformat() if dt else None},
    )