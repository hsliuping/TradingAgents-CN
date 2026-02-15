"""
LLM 策略生成
用户确认参数后，生成 Backtrader Python 代码 + config
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

GENERATE_SYSTEM = """你是一个策略代码生成器。根据用户的策略描述，生成 **Backtrader** Python 策略代码和配置。

【输出格式】必须输出纯 JSON，格式如下：
{
  "code": "完整的 Python 代码字符串",
  "config": {
    "start_year": 2016,
    "end_year": 2025,
    "initial_capital": 1000000,
    "max_positions": 10,
    "benchmark": "000300",
    "market": "CN",
    "data_source": "tushare",
    "universe": {"type": "static", "symbols": ["600519", "000858", "000568", "002304", "000596", "603288", "000651", "000333", "600887", "601888"]}
  }
}

【重要：避免生存者偏差】
⚠️ 用现在的龙头股回测过去10-20年会导致严重的生存者偏差！

**推荐做法（优先级从高到低）**：

1. **🆕 使用行业分类 + 历史市值**：universe.type = "industry"
   - 系统会自动获取回测开始日期时该行业市值最大的股票
   - 例如回测2010-2020年白酒策略，会用2010年时的白酒龙头（而非现在的）
   - 示例：{"type": "industry", "industry": "白酒", "max_symbols": 10}

2. **使用行业指数**：universe.type = "index"
   - 使用指数历史成分股（如成分股数据有限制，可能获取不到很早的数据）
   - 示例：{"type": "index", "index_code": "000932.SH"}

3. **缩短回测周期**：静态股票池回测不超过5年（如2020-2025）

【行业分类】（推荐 universe.type="industry"）⭐ 最佳选择
支持的行业名称：
- 消费类：白酒、食品、家电、消费（综合）
- 金融类：银行、保险、券商、金融（综合）
- 科技类：半导体、软件、通信、科技（综合）
- 新能源：光伏、锂电、新能源、新能源车
- 医药类：医药
- 其他：房地产、建材、钢铁、化工

示例配置：
```json
"universe": {"type": "industry", "industry": "白酒", "max_symbols": 10}
```

【行业指数代码】（备选 universe.type="index"）
- 消费类：000932.SH（中证消费）、399997.SZ（中证白酒）
- 金融类：399986.SZ（中证银行）、000914.SH（300金融）
- 科技类：399006.SZ（创业板指）、000993.SH（全指信息）

【静态股票池】（仅用于近3-5年回测，不推荐长期回测）
消费类：600519、000858、000568、603288、000651、000333、600887

【Backtrader 使用说明】
- 必须定义类名：`GeneratedStrategy`，继承 `bt.Strategy`
- `self.datas` 为数据列表，`self.datas[i]._name` 为股票代码
- 买入：`self.buy(data=..., size=数量)` 或 `self.buy(data=...)`（不指定 size 时全仓）
- 卖出：`self.sell(data=...)` 或 `self.close(data=...)`
- 持仓：`self.getposition(data).size`
- 在 `next()` 中实现每日逻辑
- **K线索引**：`data.close[0]` 当前 bar，`data.close[-1]` 上一 bar；历史 N 根最低价用 `min(data.low[-i] for i in range(1, N+1))`，且需先判断 `len(self) >= N`
- **日期**：用 `data.datetime.date(0)` 获取当前 bar 日期
- **突破策略关键**：唐奇安/通道突破必须用**前一根**的通道值！`Highest(high, 20)[0]` 含当日 high，导致 `close > entry_high` 几乎不可能（close≤high）。正确：`entry_high = highest_ind[-1]`（上一根的 20 日最高），且 `next()` 开头加 `if len(self) < period+1: return` 跳过预热

【仓位计算易错点】
- 若自定义 size：`size` 必须是**股数**（≥100 且为 100 的整数倍）
- 错误示例：`units_to_buy = min(unit_count, cash//(price*100)*100)` 若 unit_count 是「手数」会得到 <100 股，导致 `if size>=100` 永远不成立
- 正确：手数转股数 `shares = unit_count * 100`，再 `size = min(shares, cash//price//100*100)` 且 `size >= 100`

【中国 A 股规则】
- 最小交易单位 100 股（1手），回测引擎自动按 100 股取整
- 未指定仓位时默认全仓（使用全部可用资金买入）

【策略逻辑注意事项】
- 在 `__init__` 中初始化所有用到的状态变量（如 `_last_sell_date`、`_checked_year`），避免 `hasattr` 导致首次执行被跳过
- 循环逻辑（如每年春节）：确保回测区间内每一年都能触发，检查数据起始年（如 600519 从 2001 年有数据）和策略条件覆盖全区间
- 卖出条件要明确：有持仓且满足卖出时机时立即 `self.close(data)` 或 `self.sell(data)`

【规则】
- universe.type 支持 "static"（symbols 为 6 位股票代码列表）或 "index"（index_code 如 "000300"，由主平台解析）
- config.data_source: 数据源，可选 tushare/akshare/baostock
- code 中只 import backtrader（as bt）；datetime、date、timedelta 已注入，可直接使用（如 datetime(2024,1,1)、date(2024,1,1)、timedelta(days=30)），无需 import
- 必须输出纯 JSON，code 为字符串（内部换行用 \\n），不要 markdown 代码块包裹
"""


RETRY_USER_TEMPLATE = """上次生成的策略存在以下问题，请修正后重新输出纯 JSON：

【上次输出】
{output}

【错误】
{errors}

请根据上述错误修正，输出修正后的完整 JSON（含 code 和 config），不要 markdown 代码块。"""


def _parse_llm_json(raw: str) -> Dict[str, Any]:
    """解析 LLM 输出的 JSON（含 code 和 config）"""
    raw = (raw or "").strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
    data = json.loads(raw)
    if "code" not in data or "config" not in data:
        raise ValueError("输出必须包含 code 和 config 字段")
    return data


async def generate_strategy_dsl(
    user_description: str,
    llm_client: Optional[UnifiedLLMClient] = None,
    validate_on_generate: bool = True,
    run_execution_check: bool = True,
) -> Dict[str, Any]:
    """
    生成策略（Python 代码 + config），支持评估与自修正
    Args:
        user_description: 用户描述（可包含确认的参数）
        llm_client: 可选 LLM 客户端
        validate_on_generate: 是否进行 L2/L3 校验
        run_execution_check: 是否进行 L3 执行校验（需 validate_on_generate=True）
    Returns:
        {"code": str, "config": dict}，若解析失败则抛出
    """
    client = llm_client
    if not client:
        from app.services.intelligent_assistant_service import get_coding_llm_config

        cfg = await get_coding_llm_config()
        if not cfg:
            raise ValueError("未配置 LLM，无法生成策略")
        client = UnifiedLLMClient.from_config(cfg)

    from .dsl_evaluator import evaluate_strategy_python_full

    messages = [
        Message(role=MessageRole.SYSTEM, content=GENERATE_SYSTEM),
        Message(role=MessageRole.USER, content=user_description),
    ]

    last_error: Optional[str] = None
    for attempt in range(RETRY_MAX + 1):
        response = await client.achat(messages)
        raw = (response.content or "").strip()
        try:
            result = _parse_llm_json(raw)
        except (json.JSONDecodeError, ValueError) as e:
            logger.warning("策略解析失败 (attempt %d): %s", attempt + 1, e)
            last_error = f"生成的策略格式有误: {e}"
            if attempt < RETRY_MAX:
                messages.append(Message(role=MessageRole.ASSISTANT, content=raw))
                messages.append(
                    Message(
                        role=MessageRole.USER,
                        content=RETRY_USER_TEMPLATE.format(
                            output=raw[:800] + ("..." if len(raw) > 800 else ""),
                            errors=last_error,
                        ),
                    )
                )
                continue
            raise ValueError(last_error)

        if not validate_on_generate:
            return result

        passed, errors = await evaluate_strategy_python_full(
            result["code"], result["config"], run_execution_check=run_execution_check
        )
        if passed:
            return result

        last_error = "; ".join(errors)
        logger.warning("策略评估未通过 (attempt %d): %s", attempt + 1, last_error)
        if attempt < RETRY_MAX:
            messages.append(Message(role=MessageRole.ASSISTANT, content=raw))
            messages.append(
                Message(
                    role=MessageRole.USER,
                    content=RETRY_USER_TEMPLATE.format(
                        output=json.dumps(result, ensure_ascii=False)[:800]
                        + ("..." if len(json.dumps(result)) > 800 else ""),
                        errors=last_error,
                    ),
                )
            )
            continue
        raise ValueError(f"策略校验未通过（已重试{RETRY_MAX}次）: {last_error}")

    raise ValueError(last_error or "生成失败")
