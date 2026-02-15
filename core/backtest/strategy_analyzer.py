"""
LLM 策略可行性分析
用户用自然语言描述策略想法 → AI 分析可行性
"""
import json
import logging
from typing import Any, Dict, Optional

from core.llm import UnifiedLLMClient
from core.llm.models import Message, MessageRole

logger = logging.getLogger(__name__)

ANALYZE_SYSTEM = """你是一位专业的量化回测分析师。用户会描述一个投资策略想法，你需要分析其可行性。

【分析维度】
1. 策略逻辑是否清晰、可回测
2. 数据可得性（A股日线、财务指标等）
3. 风险点（过拟合、幸存者偏差等）
4. 回测可实施性（能否转化为规则化策略）

【输出】
用简洁的中文回答，包含：可行性结论、主要风险、建议的回测参数范围（如回测区间、持仓数量等）。
无需输出 JSON，自然语言即可。"""


async def analyze_strategy_feasibility(
    user_description: str,
    llm_client: Optional[UnifiedLLMClient] = None,
) -> str:
    """
    分析策略可行性
    Args:
        user_description: 用户自然语言描述
        llm_client: LLM 客户端，若不传则从数据库配置创建
    Returns:
        可行性分析文本
    """
    client = llm_client
    if not client:
        from app.services.intelligent_assistant_service import get_coding_llm_config

        cfg = await get_coding_llm_config()
        if not cfg:
            return "当前未配置 LLM，无法进行策略分析。请在系统设置中配置模型。"
        client = UnifiedLLMClient.from_config(cfg)

    messages = [
        Message(role=MessageRole.SYSTEM, content=ANALYZE_SYSTEM),
        Message(role=MessageRole.USER, content=user_description),
    ]
    try:
        response = await client.achat(messages)
        return response.content or ""
    except Exception as e:
        logger.exception("策略分析失败")
        return f"分析出错: {e}"
