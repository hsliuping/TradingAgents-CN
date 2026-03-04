"""
Gateway 适配器抽象基类

所有 IM 平台适配器必须继承 BaseGatewayAdapter 并实现以下方法：
- verify_request()   验证 Webhook 签名/Challenge
- parse_message()    将原始请求解析为 GatewayMessage
- send_response()    将 GatewayResponse 推送到平台
- format_report()    将分析报告格式化为平台最佳展示形式
"""

import abc
import logging
from typing import Any, Dict, Optional, Tuple

from core.gateway.models import (
    ChannelType,
    GatewayMessage,
    GatewayResponse,
    ResponseType,
)

logger = logging.getLogger(__name__)


class BaseGatewayAdapter(abc.ABC):
    """IM 平台适配器抽象基类"""

    channel_type: ChannelType  # 子类必须声明

    def __init__(self, config: Dict[str, Any]):
        """
        Args:
            config: 平台配置（app_id, app_secret, webhook_token 等），
                    从 system_configs 集合读取
        """
        self.config = config

    # ------------------------------------------------------------------ #
    # 必须实现的抽象方法
    # ------------------------------------------------------------------ #

    @abc.abstractmethod
    async def verify_request(
        self, headers: Dict[str, str], body: bytes
    ) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """
        验证平台 Webhook 请求的合法性。

        Returns:
            (is_valid, challenge_response)
            - is_valid: 签名是否合法
            - challenge_response: 如果是平台验证请求（如飞书 Challenge），
              返回需要直接回给平台的 JSON；普通消息时为 None
        """
        ...

    @abc.abstractmethod
    async def parse_message(
        self, headers: Dict[str, str], body: bytes
    ) -> Optional[GatewayMessage]:
        """
        将原始 Webhook body 解析为统一 GatewayMessage。

        某些事件（如用户进群、消息撤回）不需要处理，返回 None 跳过。
        """
        ...

    @abc.abstractmethod
    async def send_response(self, response: GatewayResponse) -> bool:
        """
        将 GatewayResponse 推送到 IM 平台。

        Returns:
            是否发送成功
        """
        ...

    # ------------------------------------------------------------------ #
    # 可选覆写的方法（提供合理默认实现）
    # ------------------------------------------------------------------ #

    def format_report_as_response(
        self, report_text: str, channel_id: str
    ) -> GatewayResponse:
        """
        将分析报告文本转换为平台适配的 GatewayResponse。
        默认返回 Markdown，子类可覆写为卡片消息。
        """
        return GatewayResponse(
            channel_type=self.channel_type.value,
            channel_id=channel_id,
            response_type=ResponseType.MARKDOWN,
            content=report_text,
        )

    def truncate_for_platform(self, text: str, max_length: int = 4000) -> str:
        """截断过长文本，适配平台消息长度限制"""
        if len(text) <= max_length:
            return text
        return text[: max_length - 20] + "\n\n…（内容过长已截断）"

