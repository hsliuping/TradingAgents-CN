"""
智能筛选 API 响应模型

请求模型复用 app.schemas.intelligent_assistant.ChatRequest
"""

from typing import List, Optional
from pydantic import BaseModel, Field


class StockRecommendation(BaseModel):
    """单只推荐股票"""
    code: str = Field(..., description="股票代码")
    name: str = Field("", description="股票名称")
    industry: str = Field("", description="所属行业")
    price: Optional[float] = Field(None, description="当前价格")
    pe: Optional[float] = Field(None, description="市盈率")
    pb: Optional[float] = Field(None, description="市净率")
    roe: Optional[float] = Field(None, description="净资产收益率(%)")
    dividend_yield: Optional[float] = Field(None, description="股息率(%)")
    debt_to_assets: Optional[float] = Field(None, description="资产负债率(%)")
    current_ratio: Optional[float] = Field(None, description="流动比率")
    report_period: Optional[str] = Field(None, description="财报期")
    pct_change: Optional[float] = Field(None, description="涨跌幅(%)")
    reason: str = Field("", description="推荐理由")


class ScreeningChatResponse(BaseModel):
    """智能筛选对话响应"""
    reply: str = Field(..., description="助手回复内容（Markdown）")
    tools_used: List[str] = Field(default_factory=list, description="使用的工具列表")
    stocks: List[StockRecommendation] = Field(default_factory=list, description="推荐的股票列表")
    phase: str = Field("result", description="当前阶段: confirmation=需求确认, planning=执行规划, result=筛选结果")
    is_fallback: bool = Field(False, description="是否为降级候选结果（LLM超时后由数据库粗筛兜底）")


class ScreeningMessageItem(BaseModel):
    """筛选对话消息项"""
    role: str = Field(..., description="user 或 assistant")
    content: str = Field(..., description="消息内容")
    tools_used: Optional[List[str]] = Field(None, description="工具列表")
    stocks: Optional[List[StockRecommendation]] = Field(None, description="推荐股票")
    phase: Optional[str] = Field(None, description="阶段标记: confirmation / planning / result")
    is_fallback: Optional[bool] = Field(None, description="是否为降级候选结果")


class ScreeningConversationResponse(BaseModel):
    """筛选对话历史响应"""
    messages: List[ScreeningMessageItem] = Field(default_factory=list)

