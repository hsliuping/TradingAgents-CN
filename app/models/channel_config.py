"""
渠道推送配置数据模型

支持渠道类型:
- feishu     飞书自定义机器人 Webhook
- dingtalk   钉钉自定义机器人 Webhook
- wechatwork 企业微信自定义机器人 Webhook
- email      邮件（复用现有 SMTP 配置）
"""
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field


class ChannelType(str, Enum):
    """渠道类型"""
    FEISHU = "feishu"
    DINGTALK = "dingtalk"
    WECHATWORK = "wechatwork"
    EMAIL = "email"


# 支持的事件类型
EVENT_TYPES = [
    "analysis_complete",   # 分析完成
    "alert",               # 预警
    "skill_gap",           # 工具缺口感知
    "system",              # 系统通知
]

CHANNEL_TYPE_NAMES = {
    ChannelType.FEISHU: "飞书",
    ChannelType.DINGTALK: "钉钉",
    ChannelType.WECHATWORK: "企业微信",
    ChannelType.EMAIL: "邮件",
}


class ChannelConfig(BaseModel):
    """渠道配置"""
    channel_id: str
    type: ChannelType
    name: str
    enabled: bool = True
    webhook_url: Optional[str] = None      # Webhook 渠道
    email_address: Optional[str] = None   # 邮件渠道
    events: List[str] = Field(default_factory=lambda: ["analysis_complete", "alert"])
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class ChannelConfigCreate(BaseModel):
    """创建渠道配置请求"""
    type: ChannelType
    name: str = Field(..., min_length=1, max_length=50)
    enabled: bool = True
    webhook_url: Optional[str] = None
    email_address: Optional[str] = None
    events: List[str] = Field(default_factory=lambda: ["analysis_complete", "alert"])


class ChannelConfigUpdate(BaseModel):
    """更新渠道配置请求"""
    name: Optional[str] = None
    enabled: Optional[bool] = None
    webhook_url: Optional[str] = None
    email_address: Optional[str] = None
    events: Optional[List[str]] = None


class TestSendRequest(BaseModel):
    """测试推送请求"""
    title: str = "TradingAgents-CN 测试通知"
    content: str = "这是一条测试消息，如果您收到此消息，说明渠道配置正确。"

