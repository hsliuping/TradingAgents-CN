"""
mem0 统一记忆层 — 数据模型

定义 MemoryService 对外暴露的数据结构，与 mem0 内部实现解耦。
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class MemoryScope(str, Enum):
    """记忆 scope — 通过 mem0 metadata 实现分类过滤"""

    CONVERSATION = "conversation"
    USER_PREFERENCE = "user_preference"
    ANALYSIS_INSIGHT = "analysis_insight"
    SKILL_LESSON = "skill_lesson"
    AGENT_EXPERIENCE = "agent_experience"
    TRADE_PATTERN = "trade_pattern"


class MemoryItem(BaseModel):
    """mem0 返回的单条记忆（已归一化）"""

    id: str = ""
    memory: str = ""
    user_id: str = ""
    agent_id: str = ""
    scope: str = ""
    score: float = 0.0
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: str = ""
    updated_at: str = ""

    @classmethod
    def from_mem0(cls, raw: dict, default_scope: str = "") -> "MemoryItem":
        """将 mem0 SDK 返回的 dict 归一化为 MemoryItem"""
        meta = raw.get("metadata") or {}
        return cls(
            id=raw.get("id", ""),
            memory=raw.get("memory", ""),
            user_id=raw.get("user_id") or meta.get("user_id", ""),
            agent_id=raw.get("agent_id") or meta.get("agent_id", ""),
            scope=meta.get("scope", default_scope),
            score=raw.get("score", 0.0),
            metadata=meta,
            created_at=raw.get("created_at", ""),
            updated_at=raw.get("updated_at", ""),
        )


class StoreResult(BaseModel):
    """MemoryService.store 的返回值"""

    memory_ids: List[str] = Field(default_factory=list)
    facts_extracted: int = 0
    success: bool = True
    error: str = ""
