"""
邮件通知相关数据模型
"""

from enum import Enum
from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field

from app.utils.timezone import now_tz


class EmailStatus(str, Enum):
    """邮件发送状态"""
    PENDING = "pending"      # 待发送
    SENDING = "sending"      # 发送中
    SENT = "sent"           # 已发送
    FAILED = "failed"       # 发送失败
    CANCELLED = "cancelled" # 已取消


class EmailType(str, Enum):
    """邮件类型"""
    SINGLE_ANALYSIS = "single_analysis"      # 单股分析结果
    BATCH_ANALYSIS = "batch_analysis"        # 批量分析汇总
    SCHEDULED_ANALYSIS = "scheduled_analysis" # 定时分析报告
    IMPORTANT_SIGNAL = "important_signal"    # 重要信号预警
    SYSTEM_NOTIFICATION = "system_notification" # 系统通知
    TEST_EMAIL = "test_email"                # 测试邮件


class EmailNotificationSettings(BaseModel):
    """邮件通知设置"""
    enabled: bool = False                    # 总开关
    email_address: Optional[str] = None      # 接收邮箱（可与注册邮箱不同）
    
    # 通知类型开关
    single_analysis: bool = True             # 单股分析结果
    batch_analysis: bool = True              # 批量分析汇总
    scheduled_analysis: bool = True          # 定时分析报告
    important_signals: bool = True           # 重要信号预警
    system_notifications: bool = False       # 系统通知
    
    # 发送时间偏好
    quiet_hours_enabled: bool = False        # 是否启用免打扰时段
    quiet_hours_start: str = "22:00"         # 免打扰开始时间
    quiet_hours_end: str = "08:00"           # 免打扰结束时间
    
    # 邮件格式偏好
    format: str = "html"                     # html / text
    include_charts: bool = False             # 是否包含图表（暂不支持）
    language: str = "zh"                     # 邮件语言


class EmailRecord(BaseModel):
    """邮件发送记录"""
    id: Optional[str] = Field(default=None, alias="_id")
    
    # 基本信息
    user_id: str
    to_email: str
    subject: str
    template_name: str
    
    # 邮件类型
    email_type: EmailType
    
    # 关联数据
    reference_id: Optional[str] = None   # 关联的分析报告ID等
    reference_type: Optional[str] = None # analysis_report/scheduled_task等
    
    # 发送状态
    status: EmailStatus = EmailStatus.PENDING
    retry_count: int = 0
    max_retries: int = 3
    
    # 时间戳
    created_at: datetime = Field(default_factory=now_tz)
    sent_at: Optional[datetime] = None
    
    # 错误信息
    error_message: Optional[str] = None
    
    # 元数据
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    class Config:
        populate_by_name = True


class EmailRecordCreate(BaseModel):
    """创建邮件记录请求"""
    user_id: str
    to_email: str
    subject: str
    template_name: str
    email_type: EmailType
    reference_id: Optional[str] = None
    reference_type: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class EmailSettingsUpdate(BaseModel):
    """更新邮件设置请求"""
    enabled: Optional[bool] = None
    email_address: Optional[str] = None
    single_analysis: Optional[bool] = None
    batch_analysis: Optional[bool] = None
    scheduled_analysis: Optional[bool] = None
    important_signals: Optional[bool] = None
    system_notifications: Optional[bool] = None
    quiet_hours_enabled: Optional[bool] = None
    quiet_hours_start: Optional[str] = None
    quiet_hours_end: Optional[str] = None
    format: Optional[str] = None
    language: Optional[str] = None


class SMTPConfig(BaseModel):
    """SMTP配置"""
    host: str
    port: int = 587
    username: str
    password: str
    from_email: str
    from_name: str = "TradingAgents-CN"
    use_tls: bool = True
    use_ssl: bool = False

