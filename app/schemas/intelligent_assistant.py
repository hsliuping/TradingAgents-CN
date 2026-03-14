"""
智能助手 API 请求/响应模型
"""

from typing import Any, Dict, List, Optional
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
    conversation_id: Optional[str] = Field(None, description="实际使用的主题会话 ID")


class PlannedAnalysisResponse(ChatResponse):
    """规划分析响应（扩展自 ChatResponse）"""
    plan: Optional[Dict[str, Any]] = Field(None, description="执行的分析计划")
    step_results: Optional[List[Dict[str, Any]]] = Field(None, description="各步骤执行结果")
    source: str = Field("llm_plan", description="分析来源：seed_flow / llm_plan / react")
    supplemented: bool = Field(False, description="是否进行了补充调用")


class MessageItem(BaseModel):
    """会话消息项"""
    role: str = Field(..., description="user 或 assistant")
    content: str = Field(..., description="消息内容")
    tools_used: Optional[List[str]] = Field(None, description="助手使用的工具列表")


class ConversationResponse(BaseModel):
    """会话历史响应"""
    messages: List[MessageItem] = Field(default_factory=list, description="消息列表")
    conversation_id: Optional[str] = Field(None, description="当前主题会话 ID")


class AssistantThreadSummary(BaseModel):
    """主题摘要（MVP 仅保留摘要文本）"""
    abstract: str = Field("", description="摘要文本")


class AssistantThreadItem(BaseModel):
    """助手主题会话"""
    thread_id: str = Field(..., description="主题会话 ID")
    title: str = Field(..., description="主题标题")
    topic_type: str = Field("general", description="主题类型")
    pinned: bool = Field(False, description="是否置顶")
    archived: bool = Field(False, description="是否归档")
    message_count: int = Field(0, description="消息数量")
    last_user_message: str = Field("", description="最近一条用户消息")
    updated_at: Optional[str] = Field(None, description="更新时间")
    current_summary: Optional[AssistantThreadSummary] = Field(None, description="当前摘要")


class AssistantThreadListResponse(BaseModel):
    """主题会话列表响应"""
    items: List[AssistantThreadItem] = Field(default_factory=list, description="主题会话列表")
    total: int = Field(0, description="总数")


class CreateAssistantThreadRequest(BaseModel):
    """创建主题会话请求"""
    title: Optional[str] = Field(None, description="主题标题")


class AssistantThreadMessagesResponse(ConversationResponse):
    """主题消息列表响应"""
    thread: Optional[AssistantThreadItem] = Field(None, description="主题信息")
