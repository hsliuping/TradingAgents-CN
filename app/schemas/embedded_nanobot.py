from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator


class EmbeddedNanobotThreadContext(BaseModel):
    spec_id: str | None = None
    spec_name: str | None = None
    workshop_session_id: str | None = None
    version_id: str | None = None
    version_status: str | None = None
    workflow_id: str | None = None
    node_id: str | None = None
    preference_id: str | None = None
    debug_template_id: str | None = None
    has_blocking_gaps: bool | None = None
    evaluation_status: str | None = None
    intent: dict[str, Any] | None = None
    symbol: str | None = None
    stock_symbol: str | None = None
    object_type: str | None = None
    object_key: str | None = None


class EmbeddedNanobotChatRequest(BaseModel):
    message: str = Field(..., min_length=1, description="用户输入消息")
    display_message: str | None = Field(default=None, description="前端展示用的原始用户输入")
    session_key: str | None = Field(default=None, description="会话标识，未传则按用户维度默认生成")
    model: str | None = Field(default=None, description="优先使用的模型名称")
    channel: str = Field(default="api", description="消息来源渠道")
    chat_id: str | None = Field(default=None, description="聊天标识")
    media: list[str] = Field(default_factory=list, description="附带媒体资源")
    skill_names: list[str] = Field(default_factory=list, description="显式启用的技能名称")
    thread_context: EmbeddedNanobotThreadContext | None = Field(default=None, description="当前前端工作台上下文")


class EmbeddedNanobotChatResponse(BaseModel):
    content: str
    session_key: str
    thread_id: str | None = None
    stop_reason: str | None = None
    tools_used: list[str] = Field(default_factory=list)
    usage: dict[str, int] = Field(default_factory=dict)
    tool_events: list[dict[str, Any]] = Field(default_factory=list)
    thread_context: dict[str, Any] | None = Field(default=None, description="本轮对话后持久化的线程上下文")


class EmbeddedNanobotThreadItem(BaseModel):
    thread_id: str
    title: str
    session_key: str
    channel: str = "embedded"
    archived: bool = False
    message_count: int = 0
    last_user_message: str = ""
    summary: str = ""
    created_at: str | None = None
    updated_at: str | None = None
    thread_context: EmbeddedNanobotThreadContext | None = None

    @field_validator("created_at", "updated_at", mode="before")
    @classmethod
    def _coerce_datetime_fields(cls, value: Any) -> Any:
        if isinstance(value, datetime):
            return value.isoformat()
        return value


class EmbeddedNanobotThreadListResponse(BaseModel):
    items: list[EmbeddedNanobotThreadItem] = Field(default_factory=list)
    total: int = 0


class EmbeddedNanobotMessageItem(BaseModel):
    message_id: str = ""
    role: str
    content: str
    tools_used: list[str] = Field(default_factory=list)
    stop_reason: str | None = None
    usage: dict[str, int] = Field(default_factory=dict)
    tool_events: list[dict[str, Any]] = Field(default_factory=list)
    created_at: str | None = None

    @field_validator("created_at", mode="before")
    @classmethod
    def _coerce_created_at(cls, value: Any) -> Any:
        if isinstance(value, datetime):
            return value.isoformat()
        return value


class EmbeddedNanobotThreadMessagesResponse(BaseModel):
    thread: EmbeddedNanobotThreadItem | None = None
    messages: list[EmbeddedNanobotMessageItem] = Field(default_factory=list)


class EmbeddedNanobotThreadArchiveResponse(BaseModel):
    archived: bool
    thread_id: str
    deleted_messages: int = 0


class EmbeddedNanobotThreadRestoreResponse(BaseModel):
    restored: bool
    thread_id: str
    archived: bool = False


class EmbeddedNanobotThreadContextUpdateRequest(BaseModel):
    session_key: str | None = None
    channel: str = Field(default="embedded")
    thread_context: EmbeddedNanobotThreadContext = Field(default_factory=EmbeddedNanobotThreadContext)
