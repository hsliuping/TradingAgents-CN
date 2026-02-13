"""
智能助手 API 请求/响应模型
"""

from typing import List, Optional
from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    """智能助手对话请求"""
    message: str = Field(..., description="用户输入的问题")
    conversation_id: Optional[str] = Field(None, description="会话 ID，预留用于多轮对话")


class ChatResponse(BaseModel):
    """智能助手对话响应"""
    reply: str = Field(..., description="助手回复内容")
    tools_used: List[str] = Field(default_factory=list, description="本次回复使用的工具列表")
    data_refs: Optional[List] = Field(None, description="引用的数据，预留")
