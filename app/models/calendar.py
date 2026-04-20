from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, ConfigDict


class CalendarEventStatus(str, Enum):
    SCHEDULED = "scheduled"
    UPDATED = "updated"
    CANCELLED = "cancelled"


class CalendarEventRaw(BaseModel):
    source: str
    source_event_id: str
    title: str
    summary: Optional[str] = None
    content: Optional[str] = None
    start_time: datetime
    end_time: Optional[datetime] = None
    timezone: str = "Asia/Shanghai"
    region: Optional[str] = None
    category: str = "其他"
    importance: int = Field(default=3, ge=1, le=5)
    status: CalendarEventStatus = CalendarEventStatus.SCHEDULED
    tags: List[str] = Field(default_factory=list)
    raw_payload: Dict[str, Any] = Field(default_factory=dict)


class CalendarEventInDB(BaseModel):
    event_id: str
    source: str
    source_event_id: str
    title: str
    summary: Optional[str] = None
    content: Optional[str] = None
    start_time: datetime
    end_time: Optional[datetime] = None
    date: str
    timezone: str = "Asia/Shanghai"
    region: Optional[str] = None
    category: str = "其他"
    importance: int = Field(default=3, ge=1, le=5)
    status: CalendarEventStatus = CalendarEventStatus.SCHEDULED
    tags: List[str] = Field(default_factory=list)
    raw_payload: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(populate_by_name=True)


class CalendarEventListResponse(BaseModel):
    total: int
    items: List[CalendarEventInDB]


class CalendarAnalyzeRequest(BaseModel):
    model_name: Optional[str] = None
    force_refresh: bool = False
    language: str = "zh-CN"


class ThemeItem(BaseModel):
    theme: str
    rationale: str
    confidence: float = Field(ge=0.0, le=1.0)


class Tradability(BaseModel):
    score: int = Field(ge=0, le=100)
    reason: str
    time_window: Dict[str, Any] = Field(default_factory=dict)


class ConceptItem(BaseModel):
    concept: str
    why: str
    risk: str


class RelatedStock(BaseModel):
    market: str
    code: str
    name: str
    reason: str
    confidence: float = Field(ge=0.0, le=1.0)


class CalendarAIResult(BaseModel):
    event_summary: str
    themes: List[ThemeItem] = Field(default_factory=list)
    tradability: Tradability
    concepts: List[ConceptItem] = Field(default_factory=list)
    related_stocks: List[RelatedStock] = Field(default_factory=list)
    risks: List[str] = Field(default_factory=list)
    validation_signals: List[str] = Field(default_factory=list)
    unknowns: List[str] = Field(default_factory=list)
    disclaimer: str


class CalendarAnalysisStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class CalendarAnalysisInDB(BaseModel):
    analysis_id: str
    task_id: str
    event_id: str
    status: CalendarAnalysisStatus
    model_provider: Optional[str] = None
    model_name: Optional[str] = None
    prompt_version: str = "v1"
    input_snapshot: Dict[str, Any] = Field(default_factory=dict)
    result: Optional[CalendarAIResult] = None
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime
