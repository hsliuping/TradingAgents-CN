"""
Gateway 统一消息模型

定义 IM 平台与系统之间的标准消息格式，
所有适配器将平台消息转换为 GatewayMessage，将系统回复转换为 GatewayResponse。
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ChannelType(str, Enum):
    """支持的 IM 平台类型"""
    FEISHU = "feishu"
    QQ = "qq"
    DINGTALK = "dingtalk"
    WECHAT_WORK = "wechat_work"


class MessageType(str, Enum):
    """消息内容类型"""
    TEXT = "text"
    IMAGE = "image"
    FILE = "file"
    COMMAND = "command"       # 斜杠命令，如 /bind, /help


class ResponseType(str, Enum):
    """回复内容类型"""
    TEXT = "text"
    MARKDOWN = "markdown"
    CARD = "card"             # 飞书/钉钉交互卡片


class GatewayMessage(BaseModel):
    """
    统一入站消息 — 适配器将平台原始 Webhook 解析为此格式

    所有字段使用平台无关的通用命名。
    """
    channel_type: ChannelType
    channel_id: str = Field(..., description="平台侧会话 ID（群聊 ID / 私聊 ID）")
    user_identity: str = Field(..., description="平台侧用户标识（open_id / QQ 号）")
    message_type: MessageType = MessageType.TEXT
    content: str = Field(..., description="消息正文（纯文本或已提取的文字）")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    # 平台特有的额外数据，适配器自行填充
    metadata: Dict[str, Any] = Field(default_factory=dict)
    # 如果是群聊 @Bot 场景，记录是否 at 了机器人
    is_mention_bot: bool = False

    class Config:
        use_enum_values = True


class GatewayResponse(BaseModel):
    """
    统一出站回复 — Gateway 路由将助理结果转换为此格式，适配器再转为平台 API 调用
    """
    channel_type: str
    channel_id: str
    response_type: ResponseType = ResponseType.TEXT
    content: str = Field(default="", description="文本/Markdown 内容")
    card_template: Optional[Dict[str, Any]] = None
    attachments: List[Dict[str, Any]] = Field(default_factory=list)
    # 透传元数据（如 QQ 的 msg_id 用于被动回复）
    metadata: Dict[str, Any] = Field(default_factory=dict)

    class Config:
        use_enum_values = True


class UserMapping(BaseModel):
    """IM 用户 ↔ 系统用户绑定记录"""
    user_id: str = Field(..., description="系统 user_id（MongoDB ObjectId 字符串）")
    platform: str = Field(..., description="平台标识，如 feishu / qq")
    platform_identity: str = Field(..., description="平台侧唯一标识")
    display_name: Optional[str] = None
    bound_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    is_active: bool = True

