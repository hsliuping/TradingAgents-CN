from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class EmbeddedNanobotChatRequest(BaseModel):
    message: str = Field(..., min_length=1, description="用户输入消息")
    session_key: str | None = Field(default=None, description="会话标识，未传则按用户维度默认生成")
    model: str | None = Field(default=None, description="优先使用的模型名称")
    channel: str = Field(default="api", description="消息来源渠道")
    chat_id: str | None = Field(default=None, description="聊天标识")
    media: list[str] = Field(default_factory=list, description="附带媒体资源")
    skill_names: list[str] = Field(default_factory=list, description="显式启用的技能名称")


class EmbeddedNanobotChatResponse(BaseModel):
    content: str
    session_key: str
    stop_reason: str | None = None
    tools_used: list[str] = Field(default_factory=list)
    usage: dict[str, int] = Field(default_factory=dict)
    tool_events: list[dict[str, Any]] = Field(default_factory=list)
