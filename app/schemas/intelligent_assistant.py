"""
智能助手 API 请求/响应模型
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    """智能助手对话请求"""
    message: str = Field(..., description="用户输入的问题")
    conversation_id: Optional[str] = Field(None, description="会话 ID，预留用于多轮对话")
    model: Optional[str] = Field(None, description="智能助手统一使用的推理模型")
    model_config_id: Optional[str] = Field(None, description="智能助手统一使用的模型配置 ID，优先于 model")
    quick_model: Optional[str] = Field(None, description="兼容旧版：快速对话模式使用的模型")
    deep_model: Optional[str] = Field(None, description="兼容旧版：深度分析模式使用的模型")
    quick_model_config_id: Optional[str] = Field(None, description="兼容旧版：快速对话模式模型配置 ID")
    deep_model_config_id: Optional[str] = Field(None, description="兼容旧版：深度分析模式模型配置 ID")
    # 使用问答机器人字段（v3.0 新增）
    assistant_role: str = Field("general", description="助手角色：general=通用分析助理（默认）/ usage_helper=使用问答机器人")
    user_context: Optional[Dict[str, Any]] = Field(None, description="前端上下文（当前路由/模式标记等），仅 usage_helper 模式使用")


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
    """主题摘要"""
    abstract: str = Field("", description="摘要文本")
    confirmed_facts: List[str] = Field(default_factory=list, description="已确认事实")
    open_questions: List[str] = Field(default_factory=list, description="待解决问题")
    next_actions: List[str] = Field(default_factory=list, description="建议下一步")
    focus_score: float = Field(0.0, description="聚焦度评分")


class AssistantThreadReportRef(BaseModel):
    """主题关联报告引用"""
    ref_type: str = Field(..., description="引用类型，如 stock_report / position_report / position_task")
    report_key: str = Field(..., description="报告唯一键")
    source_collection: str = Field("", description="来源集合")
    title: str = Field(..., description="报告标题")
    symbol: Optional[str] = Field(None, description="关联股票代码")
    summary: str = Field("", description="报告摘要")
    status: Optional[str] = Field(None, description="报告状态")
    task_id: Optional[str] = Field(None, description="分析任务 ID")
    analysis_id: Optional[str] = Field(None, description="持仓分析 ID")
    created_at: Optional[str] = Field(None, description="报告创建时间")
    linked_at: Optional[str] = Field(None, description="挂载到主题的时间")


class AssistantThreadItem(BaseModel):
    """助手主题会话"""
    thread_id: str = Field(..., description="主题会话 ID")
    title: str = Field(..., description="主题标题")
    parent_thread_id: Optional[str] = Field(None, description="父主题 ID")
    topic_type: str = Field("general", description="主题类型")
    pinned: bool = Field(False, description="是否置顶")
    archived: bool = Field(False, description="是否归档")
    message_count: int = Field(0, description="消息数量")
    last_user_message: str = Field("", description="最近一条用户消息")
    updated_at: Optional[str] = Field(None, description="更新时间")
    report_refs: List[AssistantThreadReportRef] = Field(default_factory=list, description="关联报告引用")
    current_summary: Optional[AssistantThreadSummary] = Field(None, description="当前摘要")


class AssistantThreadListResponse(BaseModel):
    """主题会话列表响应"""
    items: List[AssistantThreadItem] = Field(default_factory=list, description="主题会话列表")
    total: int = Field(0, description="总数")


class CreateAssistantThreadRequest(BaseModel):
    """创建主题会话请求"""
    title: Optional[str] = Field(None, description="主题标题")
    parent_thread_id: Optional[str] = Field(None, description="父主题 ID")


class AssistantThreadMessagesResponse(ConversationResponse):
    """主题消息列表响应"""
    thread: Optional[AssistantThreadItem] = Field(None, description="主题信息")


class ThreadSummarizeResponse(BaseModel):
    """主题总结响应"""
    conversation_id: str = Field(..., description="主题会话 ID")
    summary: AssistantThreadSummary = Field(..., description="最新摘要")


class ThreadDeleteResponse(BaseModel):
    """主题删除响应"""
    success: bool = Field(True, description="是否删除成功")
    deleted_thread_ids: List[str] = Field(default_factory=list, description="被删除的主题 ID 列表")


class AssistantThreadReportDetail(BaseModel):
    """主题关联报告详情"""
    ref_type: str = Field(..., description="引用类型")
    report_key: str = Field(..., description="报告唯一键")
    title: str = Field(..., description="报告标题")
    symbol: Optional[str] = Field(None, description="股票代码")
    status: Optional[str] = Field(None, description="状态")
    task_id: Optional[str] = Field(None, description="任务 ID")
    analysis_id: Optional[str] = Field(None, description="分析 ID")
    created_at: Optional[str] = Field(None, description="报告创建时间")
    linked_at: Optional[str] = Field(None, description="挂载时间")
    content: str = Field("", description="详情正文")
    content_format: str = Field("markdown", description="正文格式")


class AssistantThreadReportDetailResponse(BaseModel):
    """主题关联报告详情响应"""
    detail: AssistantThreadReportDetail = Field(..., description="报告详情")


class AssistantThreadReportSearchResponse(BaseModel):
    """主题可关联报告搜索响应"""
    items: List[AssistantThreadReportRef] = Field(default_factory=list, description="可关联报告列表")
    total: int = Field(0, description="结果数量")


class AssistantThreadAttachReportRequest(BaseModel):
    """主题手动关联旧报告请求"""
    ref_type: str = Field(..., description="引用类型")
    report_key: str = Field(..., description="报告唯一键")


class AssistantThreadAttachReportResponse(BaseModel):
    """主题手动关联旧报告响应"""
    success: bool = Field(True, description="是否关联成功")
    attached_ref: AssistantThreadReportRef = Field(..., description="已关联的报告引用")
