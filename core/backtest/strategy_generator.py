"""
LLM 策略 DSL 生成
用户确认参数后，生成结构化 JSON 策略
"""
import json
import logging
import re
from typing import Any, Dict, Optional

from core.llm import UnifiedLLMClient
from core.llm.models import Message, MessageRole

logger = logging.getLogger(__name__)

GENERATE_SYSTEM = """你是一个策略 DSL 生成器。根据用户的策略描述，生成符合 Schema 的 JSON。

【Schema】
{
  "name": "策略名称",
  "description": "策略描述",
  "universe": {
    "type": "static",
    "symbols": ["600519", "000858", "601318"]
  },
  "entry_rules": [
    {"type": "calendar_month", "months": [1,2,3,4,5,6,7,8,9,10,11,12]}
  ],
  "exit_rules": [
    {"type": "holding_days", "days": 90}
  ],
  "config": {
    "start_year": 2016,
    "end_year": 2025,
    "initial_capital": 1000000,
    "max_positions": 10,
    "benchmark": "000300",
    "market": "CN"
  }
}

【规则】
- universe.type 只支持 "static"，symbols 为 6 位股票代码列表
- entry_rules: calendar_month（买入月份）, indicator（pe<15 等，可选）
- exit_rules: holding_days（持仓天数）, profit_target（止盈%）, stop_loss（止损%）
- 一期优先实现 calendar_month + holding_days
- 必须输出纯 JSON，不要 markdown 代码块包裹
"""


async def generate_strategy_dsl(
    user_description: str,
    llm_client: Optional[UnifiedLLMClient] = None,
) -> Dict[str, Any]:
    """
    生成策略 DSL
    Args:
        user_description: 用户描述（可包含确认的参数）
        llm_client: 可选 LLM 客户端
    Returns:
        策略 DSL 字典，若解析失败则抛出或返回空
    """
    client = llm_client
    if not client:
        from app.services.intelligent_assistant_service import _get_assistant_llm_config
        from app.core.database import get_mongo_db

        db = get_mongo_db()
        cfg = await _get_assistant_llm_config(db)
        if not cfg:
            raise ValueError("未配置 LLM，无法生成策略")
        client = UnifiedLLMClient.from_config(cfg)

    messages = [
        Message(role=MessageRole.SYSTEM, content=GENERATE_SYSTEM),
        Message(role=MessageRole.USER, content=user_description),
    ]
    response = await client.achat(messages)
    raw = (response.content or "").strip()
    # 去掉可能的 markdown 代码块
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        logger.warning("DSL 解析失败: %s", e)
        raise ValueError(f"生成的策略格式有误: {e}")
