"""
定时分析任务配置数据模型
"""

from datetime import datetime, time
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from app.utils.timezone import now_tz


class ScheduledAnalysisTimeSlot(BaseModel):
    """定时分析时间段配置"""
    name: str = Field(..., description="时段名称，如：开盘前、午盘、收盘后")
    cron_expression: str = Field(..., description="CRON表达式")
    enabled: bool = Field(default=True, description="是否启用")
    
    # 该时段要分析的分组ID列表
    group_ids: List[str] = Field(default_factory=list, description="要分析的分组ID列表")
    
    # 该时段的分析参数（可选，如果不设置则使用分组的参数）
    analysis_depth: Optional[int] = Field(None, ge=1, le=5, description="分析深度（1-5级）")
    quick_analysis_model: Optional[str] = Field(None, description="快速分析模型")
    deep_analysis_model: Optional[str] = Field(None, description="深度分析模型")
    prompt_template_id: Optional[str] = Field(None, description="提示词模板ID")
    
    class Config:
        json_schema_extra = {
            "example": {
                "name": "开盘前分析",
                "cron_expression": "0 9 * * 1-5",
                "enabled": True,
                "group_ids": ["group_123", "group_456"],
                "analysis_depth": 3
            }
        }


class ScheduledAnalysisConfig(BaseModel):
    """定时分析配置"""
    id: str = Field(..., description="配置ID")
    user_id: str = Field(..., description="用户ID")
    name: str = Field(..., description="配置名称")
    description: str = Field(default="", description="配置描述")
    
    # 是否启用
    enabled: bool = Field(default=True, description="是否启用")
    
    # 时间段配置列表
    time_slots: List[ScheduledAnalysisTimeSlot] = Field(default_factory=list, description="时间段配置列表")
    
    # 全局默认参数（当时段和分组都没有设置时使用）
    default_group_ids: List[str] = Field(default_factory=list, description="默认分析分组ID列表")
    default_analysis_depth: int = Field(default=3, ge=1, le=5, description="默认分析深度")
    default_quick_analysis_model: str = Field(default="qwen-plus", description="默认快速分析模型")
    default_deep_analysis_model: str = Field(default="qwen-max", description="默认深度分析模型")
    default_prompt_template_id: Optional[str] = Field(None, description="默认提示词模板ID")
    
    # 通知设置
    notify_on_complete: bool = Field(default=True, description="完成时通知")
    notify_on_error: bool = Field(default=True, description="出错时通知")
    send_email: bool = Field(default=False, description="发送邮件通知")
    
    # 时间戳
    created_at: datetime = Field(default_factory=now_tz, description="创建时间")
    updated_at: datetime = Field(default_factory=now_tz, description="更新时间")
    last_run_at: Optional[datetime] = Field(None, description="最后运行时间")
    
    class Config:
        json_schema_extra = {
            "example": {
                "id": "config_123",
                "user_id": "user_456",
                "name": "我的定时分析",
                "description": "每日三次定时分析",
                "enabled": True,
                "time_slots": [
                    {
                        "name": "开盘前",
                        "cron_expression": "0 9 * * 1-5",
                        "enabled": True,
                        "group_ids": ["group_tech"],
                        "analysis_depth": 3
                    },
                    {
                        "name": "午盘",
                        "cron_expression": "30 11 * * 1-5",
                        "enabled": True,
                        "group_ids": ["group_finance"],
                        "analysis_depth": 2
                    },
                    {
                        "name": "收盘后",
                        "cron_expression": "30 15 * * 1-5",
                        "enabled": True,
                        "group_ids": ["group_tech", "group_finance"],
                        "analysis_depth": 4
                    }
                ],
                "default_analysis_depth": 3,
                "notify_on_complete": True,
                "send_email": False
            }
        }


class ScheduledAnalysisConfigCreate(BaseModel):
    """创建定时分析配置请求"""
    name: str = Field(..., min_length=1, max_length=50, description="配置名称")
    description: str = Field(default="", max_length=200, description="配置描述")
    enabled: bool = Field(default=True, description="是否启用")
    time_slots: List[ScheduledAnalysisTimeSlot] = Field(default_factory=list, description="时间段配置列表")
    default_group_ids: List[str] = Field(default_factory=list, description="默认分析分组ID列表")
    default_analysis_depth: int = Field(default=3, ge=1, le=5, description="默认分析深度")
    default_quick_analysis_model: str = Field(default="qwen-plus", description="默认快速分析模型")
    default_deep_analysis_model: str = Field(default="qwen-max", description="默认深度分析模型")
    default_prompt_template_id: Optional[str] = Field(None, description="默认提示词模板ID")
    notify_on_complete: bool = Field(default=True, description="完成时通知")
    notify_on_error: bool = Field(default=True, description="出错时通知")
    send_email: bool = Field(default=False, description="发送邮件通知")


class ScheduledAnalysisConfigUpdate(BaseModel):
    """更新定时分析配置请求"""
    name: Optional[str] = Field(None, min_length=1, max_length=50, description="配置名称")
    description: Optional[str] = Field(None, max_length=200, description="配置描述")
    enabled: Optional[bool] = Field(None, description="是否启用")
    time_slots: Optional[List[ScheduledAnalysisTimeSlot]] = Field(None, description="时间段配置列表")
    default_group_ids: Optional[List[str]] = Field(None, description="默认分析分组ID列表")
    default_analysis_depth: Optional[int] = Field(None, ge=1, le=5, description="默认分析深度")
    default_quick_analysis_model: Optional[str] = Field(None, description="默认快速分析模型")
    default_deep_analysis_model: Optional[str] = Field(None, description="默认深度分析模型")
    default_prompt_template_id: Optional[str] = Field(None, description="默认提示词模板ID")
    notify_on_complete: Optional[bool] = Field(None, description="完成时通知")
    notify_on_error: Optional[bool] = Field(None, description="出错时通知")
    send_email: Optional[bool] = Field(None, description="发送邮件通知")


class ScheduledAnalysisHistory(BaseModel):
    """定时分析历史记录"""
    id: str = Field(..., description="记录ID")
    config_id: str = Field(..., description="配置ID")
    config_name: str = Field(..., description="配置名称")
    time_slot_name: str = Field(..., description="时间段名称")
    created_at: datetime = Field(default_factory=now_tz, description="执行时间")
    status: str = Field(..., description="状态: success/failed/partial")
    total_count: int = Field(0, description="总任务数")
    success_count: int = Field(0, description="成功数")
    failed_count: int = Field(0, description="失败数")
    
    # 关联的任务ID
    task_ids: List[str] = Field(default_factory=list, description="关联的分析任务ID列表")
    
    # 结果摘要 (可选)
    result_summary: Optional[Dict[str, int]] = Field(None, description="结果摘要(买入/持有/卖出数量)")


