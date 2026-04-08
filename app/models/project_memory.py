"""L4 项目长期记忆的数据模型。"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


DEFAULT_PROJECT_MEMORY_PROJECT_ID = "tradingagents-cn"


class ProjectMemoryCategory(str, Enum):
    PROJECT_RULE = "project_rule"
    GOVERNANCE_CONSTRAINT = "governance_constraint"
    ANALYSIS_OUTPUT_CONSTRAINT = "analysis_output_constraint"
    RESEARCH_TEMPLATE = "research_template"


class ProjectMemoryItem(BaseModel):
    memory_id: str
    project_id: str = DEFAULT_PROJECT_MEMORY_PROJECT_ID
    memory_key: str
    title: str
    content: str
    category: str
    priority: int = 100
    active: bool = True
    tags: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    updated_by: str = ""


class ProjectMemoryUpsertRequest(BaseModel):
    memory_key: str = Field(..., min_length=1, max_length=100)
    title: str = Field(..., min_length=1, max_length=120)
    content: str = Field(..., min_length=1, max_length=4000)
    category: ProjectMemoryCategory
    project_id: str = Field(default=DEFAULT_PROJECT_MEMORY_PROJECT_ID, min_length=1, max_length=80)
    priority: int = Field(default=100, ge=1, le=999)
    active: bool = True
    tags: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)