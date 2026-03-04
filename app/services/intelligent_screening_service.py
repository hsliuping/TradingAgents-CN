"""
智能筛选服务 — LLM 多轮对话选股

复用智能助手的 LLM 配置、工具注册表、超时机制等基础设施，
新增两阶段流程（需求确认 → 执行筛选）和多轮记忆。
"""

import asyncio
import json
import logging
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from motor.motor_asyncio import AsyncIOMotorDatabase

# 复用智能助手的基础设施
from app.services.intelligent_assistant_service import (
    _get_assistant_llm_config,
    _get_latest_trade_date,
    ASSISTANT_TIMEOUT_SECONDS,
)
from core.tools import get_tool_registry, tool_metadata_list_to_openai
from core.llm import UnifiedLLMClient
from core.llm.models import Message, MessageRole

logger = logging.getLogger(__name__)

# 会话历史最大条数（每用户）
SCREENING_CONVERSATION_LIMIT = 50
# 每次请求最多传给 LLM 的历史消息条数
MAX_CONTEXT_MESSAGES = 20
# 选股相关的工具类别
# "screening" 类别包含 screen_stocks_by_criteria 批量筛选工具（核心）
SCREENING_TOOL_CATEGORIES = ["screening", "market", "fundamentals", "news", "china", "technical"]


class IntelligentScreeningService:
    """
    智能筛选服务 — LLM 多轮对话选股

    复用智能助手的 LLM 配置、工具注册表、超时机制等基础设施，
    新增两阶段流程（需求确认 → 执行筛选）和多轮记忆。
    """

    def __init__(self, db: AsyncIOMotorDatabase):
        self._db = db
        self._llm_client: Optional[UnifiedLLMClient] = None
        self._openai_tools: Optional[list] = None
        self._tool_functions: Optional[dict] = None

    async def _ensure_client(self) -> bool:
        """懒加载 LLM 客户端和工具（只加载选股相关的 5 类工具）"""
        if self._llm_client is not None:
            return True

        llm_config = await _get_assistant_llm_config(self._db)
        if not llm_config:
            return False

        try:
            self._llm_client = UnifiedLLMClient.from_config(llm_config)
        except Exception as e:
            logger.error(f"[智能筛选] 创建 LLM 客户端失败: {e}", exc_info=True)
            return False

        # 只加载选股相关的工具
        registry = get_tool_registry()
        all_metadata = registry.list_all()
        screening_metadata = [
            m for m in all_metadata
            if m.fc_enabled and m.category in SCREENING_TOOL_CATEGORIES
        ]
        self._openai_tools = tool_metadata_list_to_openai(screening_metadata)

        self._tool_functions = {}
        for tool in screening_metadata:
            if tool.parameters:
                func = registry.get_function(tool.id)
                if func:
                    self._tool_functions[tool.id] = func

        self._llm_client.inject_tools(self._tool_functions)
        logger.info(f"[智能筛选] 已加载 {len(self._openai_tools)} 个选股工具")
        return True

    async def chat(self, user_id: str, message: str) -> Dict[str, Any]:
        """
        核心方法：处理用户的选股请求（三阶段流程）

        阶段 1 — 需求确认（confirmation）：LLM 分析需求，返回理解 + 改进建议，不调用工具
        阶段 2 — 执行规划（planning）：LLM 说明具体调用哪些工具、用什么参数，不实际执行
        阶段 3 — 执行筛选（result）：LLM 调用工具，返回 5 只股票
        """
        if not await self._ensure_client():
            return {
                "reply": "智能筛选暂时不可用，请检查 LLM 配置是否已在「设置」中正确配置。",
                "tools_used": [],
                "stocks": [],
                "phase": "result",
            }

        # 1. 获取历史对话
        history = await self._get_context_messages(user_id)

        # 2. 判断当前应进入哪个阶段
        phase = self._determine_phase(history, message)
        logger.info(f"[智能筛选] 用户={user_id} 当前阶段={phase} 消息={message[:50]}")

        # 3. 构建消息列表（包含历史）
        # planning 阶段需要将实际可用的工具清单传入提示词，防止 LLM 幻觉工具名
        tool_summary = self._build_tool_summary() if phase == "planning" else ""
        system_prompt = self._get_system_prompt(phase, tool_summary)
        messages = [Message(role=MessageRole.SYSTEM, content=system_prompt)]
        for h in history:
            role = MessageRole.USER if h["role"] == "user" else MessageRole.ASSISTANT
            messages.append(Message(role=role, content=h["content"]))
        messages.append(Message(role=MessageRole.USER, content=message))

        tools_used: List[str] = []

        async def _do_chat():
            nonlocal tools_used
            if phase == "result":
                # 阶段 3：实际调用工具执行筛选
                resp = await self._llm_client.achat(
                    messages,
                    tools=self._openai_tools,
                    auto_execute_tools=True,
                    max_tool_rounds=8,
                    tools_used=tools_used,
                )
            else:
                # 阶段 1（confirmation）和阶段 2（planning）：均不调用工具
                resp = await self._llm_client.achat(messages, tools=None)
            return resp.content

        try:
            content = await asyncio.wait_for(
                _do_chat(),
                timeout=ASSISTANT_TIMEOUT_SECONDS,
            )
            reply = content or "抱歉，暂时无法生成回答，请稍后再试。"
        except asyncio.TimeoutError:
            logger.warning(f"[智能筛选] 请求超时（{ASSISTANT_TIMEOUT_SECONDS}s）")
            reply = (
                f"抱歉，处理您的选股需求用时过长（已超过 {ASSISTANT_TIMEOUT_SECONDS} 秒）。\n\n"
                "建议您：\n• 缩小筛选范围，如指定行业\n• 稍后重试"
            )
            await self._save_message(user_id, message, reply, tools_used, [], "result")
            return {"reply": reply, "tools_used": tools_used, "stocks": [], "phase": "result"}
        except Exception as e:
            logger.exception("[智能筛选] 对话失败")
            reply = f"处理您的请求时发生错误：{str(e)}。请稍后重试。"
            await self._save_message(user_id, message, reply, tools_used, [], "result")
            return {"reply": reply, "tools_used": tools_used, "stocks": [], "phase": "result"}

        # 提取股票（仅 result 阶段）
        stocks = self._extract_stocks(reply) if phase == "result" else []

        await self._save_message(user_id, message, reply, tools_used, stocks, phase)
        return {"reply": reply, "tools_used": tools_used, "stocks": stocks, "phase": phase}

    def _determine_phase(self, history: list, message: str) -> str:
        """
        判断当前消息应进入哪个阶段

        返回 'confirmation' → 阶段 1：LLM 分析需求，不调用工具
        返回 'planning'     → 阶段 2：LLM 解释执行计划，不调用工具
        返回 'result'       → 阶段 3：LLM 调用工具，返回股票列表
        """
        # 无历史 → 新需求 → 确认阶段
        if not history:
            return "confirmation"

        # 找到最近一条 assistant 消息
        last_assistant = None
        for msg in reversed(history):
            if msg.get("role") == "assistant":
                last_assistant = msg
                break

        if not last_assistant:
            return "confirmation"

        last_phase = last_assistant.get("phase", "")

        if last_phase == "confirmation":
            # 用户回应了确认消息 → 进入规划阶段
            return "planning"

        if last_phase == "planning":
            # 用户回应了规划消息
            # 检查是否要重新描述需求
            adjust_keywords = ["重新", "修改", "调整需求", "换个", "不对", "重新描述", "重新考虑"]
            for kw in adjust_keywords:
                if kw in message:
                    return "confirmation"
            # 否则批准计划，进入执行阶段
            return "result"

        # last_phase == "result" → 在结果基础上调整 → 直接再次执行
        return "result"

    async def _get_context_messages(self, user_id: str) -> list:
        """获取最近 N 条对话历史，用于传给 LLM 作为上下文"""
        doc = await self._db.screening_conversations.find_one({"user_id": user_id})
        if not doc or not doc.get("messages"):
            return []
        messages = doc["messages"]
        return messages[-MAX_CONTEXT_MESSAGES:]

    def _build_tool_summary(self) -> str:
        """将当前注册的工具列表转为文字说明，供 planning 阶段系统提示词使用"""
        if not self._openai_tools:
            return "（暂无可用工具）"
        lines = []
        for t in self._openai_tools:
            fn = t.get("function", {})
            name = fn.get("name", "")
            desc = fn.get("description", "")
            params = fn.get("parameters", {}).get("properties", {})
            param_names = ", ".join(params.keys()) if params else "无参数"
            lines.append(f"- `{name}`：{desc}\n  参数：{param_names}")
        return "\n".join(lines)

    def _get_system_prompt(self, phase: str, tool_summary: str = "") -> str:
        """构建选股专家的系统提示词（根据阶段定制）"""
        curr_date = _get_latest_trade_date()

        if phase == "confirmation":
            return f"""你是一位专业的 A 股选股专家。用户刚提出了新的选股需求。

## 你的任务：需求分析与确认

**不要调用任何工具，不要推荐股票。** 请按以下步骤回复：

1. **分析理解**：提炼用户需求的核心条件（行业、估值、风格、时间维度等）
2. **展示理解**：用清晰的列表形式告诉用户"我理解您的需求是..."
3. **改进建议**：基于专业判断，提出 2-3 条可选的改进建议（增加筛选维度、调整阈值、补充考量因素等）
4. **等待确认**：明确询问用户是"按原需求筛选"还是"采纳建议后再筛选"

回复格式：
```
## 📋 需求分析

我理解您的选股需求如下：
- **行业范围**：xxx
- **核心条件**：xxx
- **筛选风格**：xxx

## 💡 改进建议

基于专业分析，我建议您可以考虑：
1. xxx（原因）
2. xxx（原因）

## ⏳ 请确认

请选择：
- **按原需求筛选** — 直接按您的条件执行
- **采纳建议后筛选** — 添加以上改进条件后再执行
```

当前日期：{curr_date}
只分析需求，不推荐股票，不调用工具。
"""

        if phase == "planning":
            return f"""你是一位专业的 A 股选股专家。用户已确认选股需求，请制定详细的执行计划。

## 可用工具清单（严格限于以下工具，不得使用其他工具名）

{tool_summary}

## `screen_stocks_by_criteria` 支持的筛选字段

- pe / pe_ttm     市盈率（TTM）
- pb / pb_mrq     市净率
- roe             净资产收益率（%）
- total_mv        总市值（亿元）
- circ_mv         流通市值（亿元）
- turnover_rate   换手率（%）
- volume_ratio    量比
- pct_chg         当日涨跌幅（%）
- amount          成交额（万元）
- close           收盘价（元）
- industry        行业名称（使用 == 或 in 操作符）
- keyword         股票代码或名称模糊搜索
- debt_to_assets       资产负债率（%）
- current_ratio        流动比率（> 1 表示流动性良好）
- dividend_yield       股息率（%）
- net_working_capital  净营运资本（亿元，> 0 表示流动资产超过流动负债）
- is_st                是否ST股（True/False，使用 == 操作符，例如 {{"field":"is_st","operator":"==","value":false}}）

支持的操作符：> < >= <= == != between in not_in contains

**注意**：不支持 audit_opinion_type（审计意见类型）、margin_of_safety_score（自定义安全边际评分）等字段。
若用户需求涉及这些条件，请在计划中说明将用现有字段近似替代，或诚实告知此限制。

## 推荐两步法工作流

**第一步（宽口径批量筛选）**：调用 `screen_stocks_by_criteria`，设置 limit=50，按硬性指标（PE/PB/市值/资产负债率/is_st 等）过滤候选池。
**第二步（盈利稳定性验证）**：将候选股票代码列表传给 `batch_check_profit_consistency`，一次查询验证近N年ROE稳定性。**禁止对每只股票单独重复查询财务数据。**

## 你的任务：执行计划说明

**不要调用任何工具，不要推荐股票。** 请详细说明你打算如何执行此次筛选：

1. **筛选策略**：总结最终采用的筛选条件，注明哪些需求能被现有字段支持，哪些无法精确筛选
2. **工具调用计划**：**仅使用上方可用工具清单中的工具**，列出工具名和具体参数
   - 步骤1：`screen_stocks_by_criteria` 的 conditions JSON 数组（每个条件的 field/operator/value），limit 建议 30-50
   - 步骤2（如需验证盈利稳定性）：`batch_check_profit_consistency`，传入步骤1的候选股代码列表
3. **数据处理**：说明如何从工具返回结果中选出最终 5 只股票（排序依据、优先级等）
4. **限制说明**：诚实告知用户哪些条件无法精确筛选（如审计意见类型、自定义安全边际评分）
5. **请求批准**：询问用户是否同意该方案

回复格式：
```
## 🔧 执行计划

### 筛选条件（最终版）
- PE < xxx（现有字段支持）
- 市值 > 50亿（现有字段支持）
- 资产负债率 ≤ 60%（debt_to_assets 字段支持）
- 非ST股（is_st 字段支持）
- 近3年ROE稳定（batch_check_profit_consistency 工具支持）

### 工具调用
**步骤 1**：调用 `screen_stocks_by_criteria`
- conditions: [{{{{"field": "pe", "operator": "<", "value": 15}}}}, {{{{"field": "total_mv", "operator": ">", "value": 50}}}}, {{{{"field": "is_st", "operator": "==", "value": false}}}}]
- limit: 50
- order_by_field: "pb"
- order_direction: "asc"

**步骤 2**：调用 `batch_check_profit_consistency`（对步骤1的候选股批量验证盈利稳定性）
- stock_codes_json: 步骤1返回的全部股票代码列表
- years: 3
- threshold_cv: 0.3

### 数据处理
- 从步骤2结果中筛选"盈利稳定"的股票，按 PB 升序取前 5 只
- 确保行业不重叠

## ✅ 请确认

以上是我的执行方案，请选择：
- **执行筛选方案** — 按此方案立即执行
- **重新描述需求** — 重新调整筛选条件
```

当前日期：{curr_date}
只说明计划，不调用工具，不推荐股票。**严禁使用工具清单以外的工具名。**
"""

        # phase == "result"
        return f"""你是一位专业的 A 股选股专家。用户已批准执行计划，请立即执行筛选并推荐股票。

## 你的任务：执行筛选

1. **调用工具**：按之前计划的参数调用 `screen_stocks_by_criteria` 等工具获取数据
2. **精选推荐**：每次严格推荐 **5 只** 最符合条件的股票
3. **结构化输出**：在回答最后包含以下 JSON 代码块

```json
{{{{
  "stocks": [
    {{{{
      "code": "600519",
      "name": "贵州茅台",
      "industry": "白酒",
      "price": 1680.00,
      "pe": 25.3,
      "pb": 8.5,
      "pct_change": 2.1,
      "reason": "白马股龙头，业绩稳定增长，估值处于历史中位"
    }}}}
  ]
}}}}
```

## 规则

- 当前日期：{curr_date}
- 每次推荐恰好 5 只股票，不多不少
- 推荐理由要具体，结合数据说话
- 如果用户要求调整（如"换个行业""PE 再低点"），直接重新调用工具调整筛选
- 不给出具体的买入/卖出建议，只做选股推荐和分析
- 只推荐 A 股（沪深两市）
"""

    def _extract_stocks(self, reply: str) -> list:
        """从 LLM 回复中提取结构化股票列表"""
        pattern = r'```json\s*(\{[\s\S]*?\})\s*```'
        match = re.search(pattern, reply)
        if match:
            try:
                data = json.loads(match.group(1))
                return data.get("stocks", [])
            except json.JSONDecodeError:
                pass
        return []

    async def _save_message(
        self, user_id: str, user_msg: str, assistant_reply: str,
        tools_used: List[str], stocks: list, phase: str,
    ) -> None:
        """持久化对话消息到 screening_conversations"""
        now = datetime.now(timezone.utc)
        user_entry = {"role": "user", "content": user_msg, "timestamp": now}
        assistant_entry = {
            "role": "assistant",
            "content": assistant_reply,
            "tools_used": tools_used,
            "stocks": stocks,
            "phase": phase,
            "timestamp": now,
        }
        await self._db.screening_conversations.update_one(
            {"user_id": user_id},
            {
                "$push": {
                    "messages": {
                        "$each": [user_entry, assistant_entry],
                        "$slice": -SCREENING_CONVERSATION_LIMIT,
                    }
                },
                "$set": {"updated_at": now},
                "$setOnInsert": {"created_at": now},
            },
            upsert=True,
        )

    async def get_conversation(self, user_id: str) -> list:
        """获取完整对话历史"""
        doc = await self._db.screening_conversations.find_one({"user_id": user_id})
        if not doc:
            return []
        return doc.get("messages", [])

    async def clear_conversation(self, user_id: str) -> None:
        """清空对话历史"""
        await self._db.screening_conversations.delete_one({"user_id": user_id})

