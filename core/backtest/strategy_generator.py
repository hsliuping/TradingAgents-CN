"""
LLM 策略 DSL 生成
用户确认参数后，生成结构化 JSON 策略
支持 L2 语义校验、L3 执行校验与自修正循环
"""
import json
import logging
import re
from typing import Any, Dict, Optional

from core.llm import UnifiedLLMClient
from core.llm.models import Message, MessageRole

logger = logging.getLogger(__name__)

RETRY_MAX = 2  # 最多重试 2 次，共 3 次尝试

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
    "market": "CN",
    "data_source": "tushare"
  }
}

【规则】
- universe.type 只支持 "static"，symbols 为 6 位股票代码列表
- entry_rules: calendar_month（买入月份）
- exit_rules 支持两种（可同时存在，先触发者生效）:
  - holding_days: 持仓 N 个交易日后卖出
  - calendar_month: 进入指定月份时卖出（如 {"type":"calendar_month","months":[2]} 表示进入2月即卖）
- 春节策略语义：用户说「春节前买、过完春节卖」时：
  - 买入月约 1 月（春节多在1月下旬~2月中旬）
  - 过完春节≈节后2~4周内卖，持仓约 20~35 个交易日，NOT 60 天
  - 或使用 exit calendar_month months=[2]，即 1月买、2月卖
- config.data_source: 数据源，可选 tushare/akshare/baostock
- 必须输出纯 JSON，不要 markdown 代码块包裹
"""


RETRY_USER_TEMPLATE = """上次生成的策略 DSL 存在以下问题，请修正后重新输出纯 JSON：

【上次输出】
{dsl}

【错误】
{errors}

请根据上述错误修正，输出修正后的完整 JSON，不要 markdown 代码块。"""


def _parse_llm_json(raw: str) -> Dict[str, Any]:
    """解析 LLM 输出的 JSON"""
    raw = (raw or "").strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
    return json.loads(raw)


async def generate_strategy_dsl(
    user_description: str,
    llm_client: Optional[UnifiedLLMClient] = None,
    validate_on_generate: bool = True,
    run_execution_check: bool = True,
) -> Dict[str, Any]:
    """
    生成策略 DSL，支持评估与自修正
    Args:
        user_description: 用户描述（可包含确认的参数）
        llm_client: 可选 LLM 客户端
        validate_on_generate: 是否进行 L2/L3 校验
        run_execution_check: 是否进行 L3 执行校验（需 validate_on_generate=True）
    Returns:
        策略 DSL 字典，若解析失败则抛出
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

    from .dsl_evaluator import evaluate_dsl_full

    messages = [
        Message(role=MessageRole.SYSTEM, content=GENERATE_SYSTEM),
        Message(role=MessageRole.USER, content=user_description),
    ]

    last_error: Optional[str] = None
    for attempt in range(RETRY_MAX + 1):
        response = await client.achat(messages)
        raw = (response.content or "").strip()
        try:
            dsl = _parse_llm_json(raw)
        except json.JSONDecodeError as e:
            logger.warning("DSL 解析失败 (attempt %d): %s", attempt + 1, e)
            last_error = f"生成的策略格式有误: {e}"
            if attempt < RETRY_MAX:
                messages.append(
                    Message(role=MessageRole.ASSISTANT, content=raw)
                )
                messages.append(
                    Message(
                        role=MessageRole.USER,
                        content=RETRY_USER_TEMPLATE.format(
                            dsl=raw[:800] + ("..." if len(raw) > 800 else ""),
                            errors=last_error,
                        ),
                    )
                )
                continue
            raise ValueError(last_error)

        if not validate_on_generate:
            return dsl

        passed, errors = await evaluate_dsl_full(
            dsl, run_execution_check=run_execution_check
        )
        if passed:
            return dsl

        last_error = "; ".join(errors)
        logger.warning("DSL 评估未通过 (attempt %d): %s", attempt + 1, last_error)
        if attempt < RETRY_MAX:
            messages.append(Message(role=MessageRole.ASSISTANT, content=raw))
            messages.append(
                Message(
                    role=MessageRole.USER,
                    content=RETRY_USER_TEMPLATE.format(
                        dsl=json.dumps(dsl, ensure_ascii=False, indent=2)[:800]
                        + ("..." if len(json.dumps(dsl)) > 800 else ""),
                        errors=last_error,
                    ),
                )
            )
            continue
        raise ValueError(f"策略校验未通过（已重试{RETRY_MAX}次）: {last_error}")

    raise ValueError(last_error or "生成失败")
