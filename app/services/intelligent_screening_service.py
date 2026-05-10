"""
智能筛选服务 — LLM 多轮对话选股

复用智能助手的 LLM 配置、工具注册表、超时机制等基础设施，
新增两阶段流程（需求确认 → 执行筛选）和多轮记忆。
"""

import asyncio
import json
import logging
import os
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, Dict, List, Optional

from motor.motor_asyncio import AsyncIOMotorDatabase

# 复用智能助手的基础设施
from app.services.factor_registry_service import build_screening_fields_markdown
from app.services.intelligent_assistant_service import (
    _get_assistant_llm_config,
    _get_latest_trade_date,
    ASSISTANT_TIMEOUT_SECONDS,
)
from core.tools import get_tool_registry, tool_metadata_list_to_openai
from core.tools.context import set_current_user_id
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
SCREENING_TOOL_IDS = {
    "add_stocks_to_favorites",
    "list_watchlist_groups",
    "add_stock_to_watchlist",
}

# 执行阶段工具收敛：优先仅允许批量筛选链路，避免单股重工具放大时延
RESULT_TOOL_ALLOWLIST = {
    "screen_stocks_by_criteria",
    "batch_check_profit_consistency",
    "add_stocks_to_favorites",
    "list_watchlist_groups",
    "add_stock_to_watchlist",
}

# 选股场景独立预算，默认比全局助手更紧，避免长尾请求拖垮体验
SCREENING_MAX_TOOL_ROUNDS = int(os.environ.get("SCREENING_MAX_TOOL_ROUNDS", "3"))
SCREENING_RESULT_TIMEOUT_SECONDS = int(os.environ.get("SCREENING_RESULT_TIMEOUT_SECONDS", "300"))


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
        self._result_openai_tools: Optional[list] = None
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
            if m.fc_enabled and (m.category in SCREENING_TOOL_CATEGORIES or m.id in SCREENING_TOOL_IDS)
        ]
        self._openai_tools = tool_metadata_list_to_openai(screening_metadata)

        self._tool_functions = {}
        for tool in screening_metadata:
            if tool.parameters:
                func = registry.get_function(tool.id)
                if func:
                    self._tool_functions[tool.id] = func

        # 结果执行阶段仅保留批量筛选相关工具，限制工具链复杂度
        self._result_openai_tools = self._filter_result_tools(self._openai_tools)
        if not self._result_openai_tools:
            self._result_openai_tools = self._openai_tools
            logger.warning("[智能筛选] 结果阶段批量工具白名单为空，回退到完整工具集")

        self._llm_client.inject_tools(self._tool_functions)
        logger.info(
            f"[智能筛选] 已加载 {len(self._openai_tools)} 个选股工具，"
            f"结果阶段使用 {len(self._result_openai_tools)} 个执行工具"
        )
        return True

    def _filter_result_tools(self, openai_tools: Optional[list]) -> list:
        """过滤 result 阶段可用工具，优先保留批量筛选链路。"""
        if not openai_tools:
            return []

        filtered = []
        for t in openai_tools:
            fn = t.get("function", {}) if isinstance(t, dict) else {}
            name = fn.get("name")
            if name in RESULT_TOOL_ALLOWLIST:
                filtered.append(t)
        return filtered

    def _infer_request_focus(self, message: str) -> str:
        """从用户请求中提取核心筛选诉求，用于无结果与降级提示。"""
        text = (message or "").strip()
        if not text:
            return "原筛选条件"

        focus_keywords = [
            ("高分红", ["高分红", "分红", "股息", "股息率", "dividend"]),
            ("低估值", ["低估值", "低pe", "低 pb", "低pb", "估值低", "便宜"]),
            ("银行股", ["银行"]),
            ("消费股", ["消费"]),
            ("科技股", ["科技", "芯片", "半导体", "ai"]),
            ("高ROE", ["roe"]),
        ]
        lower_text = text.lower()
        for label, keywords in focus_keywords:
            if any(keyword in text or keyword in lower_text for keyword in keywords):
                return label
        return "原筛选条件"

    def _build_no_match_reply(self, message: str) -> str:
        """未命中条件时返回硬提示，不推荐任何替代股票。"""
        focus = self._infer_request_focus(message)
        return (
            f"未找到符合“{focus}”条件的股票。\n\n"
            "当前没有适合该筛选要求的标的，不推荐其它不符合条件的股票。"
            "如果您仍想继续筛选，请进一步补充阈值、缩小行业范围，或调整筛选条件后重试。"
        )

    def _build_timeout_reply(self, timeout_seconds: int) -> str:
        """执行超时时返回硬提示，不推荐任何替代股票。"""
        return (
            f"抱歉，处理您的选股需求已超时（超过 {timeout_seconds} 秒）。\n\n"
            "本次不会改为推荐其它不符合原筛选条件的股票。"
            "建议您缩小筛选范围、补充更明确的阈值或行业条件，或稍后重试。"
        )

    async def _emit_progress(
        self,
        progress_callback: Optional[Callable[[Dict[str, Any]], Awaitable[None]]],
        event: str,
        **data,
    ) -> None:
        """发送智能筛选进度事件，供 WebSocket 流式展示。"""
        if not progress_callback:
            return

        payload = {
            "event": event,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            **data,
        }
        try:
            await progress_callback(payload)
        except Exception as e:
            logger.debug("[智能筛选] 进度推送失败(忽略): %s", e)

    def _build_conversation_title(self, message: str) -> str:
        text = re.sub(r"\s+", " ", (message or "").strip())
        if not text:
            return "未命名筛选"
        return text[:30]

    def _format_dt(self, value: Any) -> Optional[str]:
        if isinstance(value, datetime):
            return value.isoformat()
        if isinstance(value, str):
            return value
        return None

    async def _ensure_conversation_doc_identity(self, doc: Optional[dict]) -> Optional[dict]:
        if not doc:
            return None

        messages = doc.get("messages") or []
        first_user_message = next(
            (item.get("content", "") for item in messages if item.get("role") == "user"),
            "",
        )
        updates: Dict[str, Any] = {}
        if not doc.get("conversation_id"):
            updates["conversation_id"] = uuid.uuid4().hex
        if not doc.get("title"):
            updates["title"] = self._build_conversation_title(first_user_message)

        if updates:
            await self._db.screening_conversations.update_one({"_id": doc["_id"]}, {"$set": updates})
            doc.update(updates)

        return doc

    async def _get_conversation_doc(self, user_id: str, conversation_id: Optional[str] = None) -> Optional[dict]:
        if conversation_id:
            doc = await self._db.screening_conversations.find_one({
                "user_id": user_id,
                "conversation_id": conversation_id,
            })
            return await self._ensure_conversation_doc_identity(doc)

        doc = await self._db.screening_conversations.find_one(
            {"user_id": user_id},
            sort=[("updated_at", -1), ("created_at", -1)],
        )
        return await self._ensure_conversation_doc_identity(doc)

    async def chat(
        self,
        user_id: str,
        message: str,
        conversation_id: Optional[str] = None,
        progress_callback: Optional[Callable[[Dict[str, Any]], Awaitable[None]]] = None,
    ) -> Dict[str, Any]:
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
                "conversation_id": conversation_id,
                "is_fallback": False,
            }

        set_current_user_id(user_id)

        # 1. 获取历史对话
        resolved_conversation_id, history = await self._get_context_messages(user_id, conversation_id)
        if not resolved_conversation_id:
            resolved_conversation_id = conversation_id or uuid.uuid4().hex

        # 2. 判断当前应进入哪个阶段
        phase = self._determine_phase(history, message)
        logger.info(f"[智能筛选] 用户={user_id} 当前阶段={phase} 消息={message[:50]}")
        await self._emit_progress(
            progress_callback,
            "phase_determined",
            phase=phase,
            message=(
                "正在分析您的筛选需求" if phase == "confirmation"
                else "正在生成筛选执行计划" if phase == "planning"
                else "正在执行批量筛选与验证"
            ),
        )

        # 3. 构建消息列表（包含历史）
        # planning 阶段需要将实际可用的工具清单传入提示词，防止 LLM 幻觉工具名
        tool_summary = self._build_tool_summary(self._result_openai_tools) if phase == "planning" else ""
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
                await self._emit_progress(
                    progress_callback,
                    "status",
                    phase=phase,
                    message="已进入执行阶段，开始调用筛选与自选股工具",
                )
                # 阶段 3：实际调用工具执行筛选
                resp = await self._llm_client.achat(
                    messages,
                    tools=self._result_openai_tools,
                    auto_execute_tools=True,
                    max_tool_rounds=SCREENING_MAX_TOOL_ROUNDS,
                    tools_used=tools_used,
                    progress_callback=progress_callback,
                    log_payloads=True,
                    payload_log_label=f"intelligent_screening:{phase}",
                )
            else:
                await self._emit_progress(
                    progress_callback,
                    "status",
                    phase=phase,
                    message="正在生成阶段性回复",
                )
                # 阶段 1（confirmation）和阶段 2（planning）：均不调用工具
                resp = await self._llm_client.achat(
                    messages,
                    tools=None,
                    log_payloads=True,
                    payload_log_label=f"intelligent_screening:{phase}",
                )
            return resp.content

        try:
            started_at = datetime.now(timezone.utc)
            content = await asyncio.wait_for(
                _do_chat(),
                timeout=SCREENING_RESULT_TIMEOUT_SECONDS if phase == "result" else ASSISTANT_TIMEOUT_SECONDS,
            )
            reply = content or "抱歉，暂时无法生成回答，请稍后再试。"
            elapsed = (datetime.now(timezone.utc) - started_at).total_seconds()
            logger.info(
                f"[智能筛选] 完成 phase={phase} elapsed={elapsed:.2f}s tools_used={len(tools_used)}"
            )
            await self._emit_progress(
                progress_callback,
                "status",
                phase=phase,
                message=f"阶段处理完成，用时 {elapsed:.2f} 秒",
                tools_used=tools_used,
            )
        except asyncio.TimeoutError:
            timeout_seconds = (
                SCREENING_RESULT_TIMEOUT_SECONDS if phase == "result" else ASSISTANT_TIMEOUT_SECONDS
            )
            logger.warning(f"[智能筛选] 请求超时（{timeout_seconds}s，phase={phase}）")
            await self._emit_progress(
                progress_callback,
                "timeout",
                phase=phase,
                message=f"处理超时（{timeout_seconds} 秒）",
            )

            reply = self._build_timeout_reply(timeout_seconds)
            await self._save_message(user_id, resolved_conversation_id, message, reply, tools_used, [], "result")
            return {
                "reply": reply,
                "tools_used": tools_used,
                "stocks": [],
                "phase": "result",
                "conversation_id": resolved_conversation_id,
            }
        except Exception as e:
            logger.exception("[智能筛选] 对话失败")
            await self._emit_progress(
                progress_callback,
                "error",
                phase=phase,
                message=f"处理失败：{str(e)}",
            )
            reply = f"处理您的请求时发生错误：{str(e)}。请稍后重试。"
            await self._save_message(user_id, resolved_conversation_id, message, reply, tools_used, [], "result")
            return {
                "reply": reply,
                "tools_used": tools_used,
                "stocks": [],
                "phase": "result",
                "conversation_id": resolved_conversation_id,
            }

        # 提取股票（仅 result 阶段）
        stocks = self._extract_stocks(reply) if phase == "result" else []

        if phase == "result" and not stocks and "screen_stocks_by_criteria" in tools_used:
            reply = self._build_no_match_reply(message)
            stocks = []
            await self._emit_progress(
                progress_callback,
                "no_match",
                phase="result",
                message="未找到符合原筛选条件的股票",
                stocks=[],
            )
            await self._save_message(user_id, resolved_conversation_id, message, reply, tools_used, stocks, phase)
            return {
                "reply": reply,
                "tools_used": tools_used,
                "stocks": stocks,
                "phase": phase,
                "conversation_id": resolved_conversation_id,
                "is_fallback": False,
            }

        await self._save_message(user_id, resolved_conversation_id, message, reply, tools_used, stocks, phase)
        return {
            "reply": reply,
            "tools_used": tools_used,
            "stocks": stocks,
            "phase": phase,
            "conversation_id": resolved_conversation_id,
            "is_fallback": False,
        }

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

    async def _get_context_messages(self, user_id: str, conversation_id: Optional[str] = None) -> tuple[str, list]:
        """获取最近 N 条对话历史，用于传给 LLM 作为上下文"""
        doc = await self._get_conversation_doc(user_id, conversation_id)
        if not doc or not doc.get("messages"):
            return conversation_id or "", []
        messages = doc["messages"]
        return doc.get("conversation_id", conversation_id or ""), messages[-MAX_CONTEXT_MESSAGES:]

    def _build_tool_summary(self, tools: Optional[list] = None) -> str:
        """将当前注册的工具列表转为文字说明，供 planning 阶段系统提示词使用"""
        target_tools = tools if tools is not None else self._openai_tools
        if not target_tools:
            return "（暂无可用工具）"
        lines = []
        for t in target_tools:
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
            screening_fields_markdown = build_screening_fields_markdown(public_only=True)
            return f"""你是一位专业的 A 股选股专家。用户已确认选股需求，请制定详细的执行计划。

## 可用工具清单（严格限于以下工具，不得使用其他工具名）

{tool_summary}

## `screen_stocks_by_criteria` 支持的筛选字段

{screening_fields_markdown}

支持的操作符：> < >= <= == != between in not_in contains

**注意**：不支持 audit_opinion_type（审计意见类型）、margin_of_safety_score（自定义安全边际评分）等字段。
若用户需求涉及这些条件，请在计划中说明将用现有字段近似替代，或诚实告知此限制。

## 推荐两步法工作流

**第一步（宽口径批量筛选）**：调用 `screen_stocks_by_criteria`，设置 limit=50，按硬性指标（PE/PB/市值/资产负债率/is_st 等）过滤候选池。
**第二步（盈利稳定性验证）**：将候选股票代码列表传给 `batch_check_profit_consistency`，一次查询验证近N年ROE稳定性。**禁止对每只股票单独重复查询财务数据。**

## 字段使用建议

- 优先使用可比较的比率型指标做硬筛选，如 PE、PB、ROE、毛利率、资产负债率、流动比率、股息率
- `revenue_ttm`、`net_profit_ttm`、`n_cashflow_act` 更适合作为质量补充条件，不宜单独作为唯一标准
- 如果用户强调“现金流好”“利润扎实”“财务稳健”，优先考虑 `n_cashflow_act > 0`、`net_profit_ttm > 0`、`debt_to_assets`、`current_ratio`
- 如果用户强调“高分红”“防御型”，优先考虑 `dividend_yield` 并结合 `debt_to_assets`、`n_cashflow_act`
- 如果用户强调“财报最新”“只看最新财报”，可通过 `report_period` 增加约束

## 自选股联动规则

- 若用户明确要求“筛选完成后加入自选股”或“把上次推荐加入自选股”，可在最终推荐确定后调用 `add_stocks_to_favorites`
- 若用户明确要求“加标签/打标签/标记”（如“打上巴菲特标签”），优先调用 `add_stocks_to_favorites` 并传入 `tags`
- 若用户明确要求放入某个分类/分组（如“银行”“待分析”），可调用 `add_stock_to_watchlist`，必要时先用 `list_watchlist_groups` 查看现有分类
- “标签”和“分组”不是同一概念：标签写入自选股的 `tags`，分组写入 watchlist group
- 未明确提出自选股操作时，不要主动添加

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
            "roe": 32.1,
            "roa": 18.6,
            "gross_margin": 51.2,
            "netprofit_margin": 24.8,
            "dividend_yield": 3.1,
            "debt_to_assets": 18.5,
            "assets_to_eqt": 1.42,
            "current_ratio": 4.2,
            "quick_ratio": 3.8,
            "cash_ratio": 1.9,
            "revenue_ttm": 123456789000,
            "net_profit_ttm": 45678900000,
            "n_cashflow_act": 39876500000,
            "report_period": "20250930",
      "pct_change": 2.1,
      "reason": "白马股龙头，业绩稳定增长，估值处于历史中位"
    }}}}
  ]
}}}}
```

## 规则

- 当前日期：{curr_date}
- 默认最多执行 **两轮数据工具调用**：
    - 第 1 轮：`screen_stocks_by_criteria`
    - 第 2 轮：仅当确有必要时才调用 `batch_check_profit_consistency`
- 若步骤 1 已能直接选出最终推荐，则**跳过**步骤 2，直接输出最终结果
- 一旦已有足够数据生成最终推荐，**立即停止继续调用工具**
- 不要为了“凑满信息”反复改阈值、重复筛选或重新扩大范围；当前条件下结果不足时，应直接说明限制
- 每次推荐恰好 5 只股票，不多不少
- 推荐理由要具体，结合数据说话
- 若工具结果中已提供 ROE、股息率、资产负债率、流动比率、财报期，优先一并放入 JSON 字段，便于前端直接展示
- 若工具结果中已提供 ROA、毛利率、净利率、滚动营收、滚动净利润、经营现金流、权益乘数、速动比率、现金比率，也可一并放入 JSON 字段，便于前端直接展示
- 如果用户要求调整（如"换个行业""PE 再低点"），直接重新调用工具调整筛选
- 如果用户明确要求将当前推荐结果加入自选股，可调用 `add_stocks_to_favorites` 一次性添加；若同时要求“打标签/标记”，把标签通过 `tags` 参数一并写入
- 如果用户明确要求将当前推荐结果放入某个分类/分组，可调用 `add_stock_to_watchlist`，分组不存在时允许自动创建，例如“银行”“待分析”
- 若用户同时要求“加入自选 + 打标签 + 放入分组”，应先调用 `add_stocks_to_favorites` 写入 tags，再调用 `add_stock_to_watchlist`
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
        self, user_id: str, conversation_id: str, user_msg: str, assistant_reply: str,
        tools_used: List[str], stocks: list, phase: str, is_fallback: bool = False,
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
            "is_fallback": is_fallback,
            "timestamp": now,
        }
        await self._db.screening_conversations.update_one(
            {"user_id": user_id, "conversation_id": conversation_id},
            {
                "$push": {
                    "messages": {
                        "$each": [user_entry, assistant_entry],
                        "$slice": -SCREENING_CONVERSATION_LIMIT,
                    }
                },
                "$set": {"updated_at": now},
                "$setOnInsert": {
                    "conversation_id": conversation_id,
                    "title": self._build_conversation_title(user_msg),
                    "created_at": now,
                },
            },
            upsert=True,
        )

    async def run_direct_screening(
        self,
        user_id: str,
        criteria: str,
        max_stocks: int = 10,
    ) -> Dict[str, Any]:
        """
        直接执行选股（单轮，不经过确认/规划阶段）。
        供 MCP / API 等外部调用，无需多轮对话。

        Args:
            user_id: 用户 ID（用于 LLM 配额等）
            criteria: 筛选条件（自然语言），如 "PE小于20的科技股"
            max_stocks: 最多返回股票数量，默认 10

        Returns:
            {"reply": str, "stocks": list, "phase": "result"}
        """
        if not await self._ensure_client():
            return {
                "reply": "智能筛选暂时不可用，请检查 LLM 配置。",
                "stocks": [],
                "phase": "result",
            }
        set_current_user_id(user_id)
        curr_date = _get_latest_trade_date()
        direct_hint = (
            f"【直接执行模式】请根据用户消息中的条件直接调用筛选工具执行，"
            f"无需确认与规划。推荐最多 {max_stocks} 只股票，并在回复末尾用 JSON 代码块列出。"
        )
        system_prompt = direct_hint + "\n\n" + self._get_system_prompt("result", "")
        user_message = f"请根据以下条件直接执行筛选并返回股票列表（最多 {max_stocks} 只）及简要理由。\n\n条件：{criteria}"
        messages = [
            Message(role=MessageRole.SYSTEM, content=system_prompt),
            Message(role=MessageRole.USER, content=user_message),
        ]
        tools_used: List[str] = []
        try:
            started_at = datetime.now(timezone.utc)
            resp = await asyncio.wait_for(
                self._llm_client.achat(
                    messages,
                    tools=self._result_openai_tools,
                    auto_execute_tools=True,
                    max_tool_rounds=SCREENING_MAX_TOOL_ROUNDS,
                    tools_used=tools_used,
                ),
                timeout=SCREENING_RESULT_TIMEOUT_SECONDS,
            )
            reply = (resp.content if resp else None) or "未能生成选股结果，请稍后重试。"
            elapsed = (datetime.now(timezone.utc) - started_at).total_seconds()
            logger.info(f"[智能筛选] run_direct_screening 完成 elapsed={elapsed:.2f}s tools_used={len(tools_used)}")
        except asyncio.TimeoutError:
            reply = self._build_timeout_reply(SCREENING_RESULT_TIMEOUT_SECONDS)
        except Exception as e:
            logger.exception("[智能筛选] run_direct_screening 失败")
            reply = f"处理选股请求时发生错误：{str(e)}。请稍后重试。"
        stocks = self._extract_stocks(reply)
        if not stocks and "screen_stocks_by_criteria" in tools_used:
            reply = self._build_no_match_reply(criteria)
            stocks = []

        return {"reply": reply, "stocks": stocks, "phase": "result"}

    async def get_conversation(self, user_id: str, conversation_id: Optional[str] = None) -> tuple[Optional[str], list]:
        """获取完整对话历史"""
        doc = await self._get_conversation_doc(user_id, conversation_id)
        if not doc:
            return conversation_id, []
        return doc.get("conversation_id"), doc.get("messages", [])

    async def list_conversations(self, user_id: str) -> list:
        """获取会话列表摘要"""
        cursor = self._db.screening_conversations.find({"user_id": user_id}).sort([
            ("updated_at", -1),
            ("created_at", -1),
        ])
        docs = await cursor.to_list(length=100)

        items = []
        for raw_doc in docs:
            doc = await self._ensure_conversation_doc_identity(raw_doc)
            messages = doc.get("messages") or []
            preview = ""
            for item in reversed(messages):
                content = str(item.get("content") or "").strip()
                if content:
                    preview = re.sub(r"\s+", " ", content)[:80]
                    break

            items.append({
                "conversation_id": doc.get("conversation_id"),
                "title": doc.get("title") or self._build_conversation_title(preview),
                "preview": preview,
                "message_count": len(messages),
                "created_at": self._format_dt(doc.get("created_at")),
                "updated_at": self._format_dt(doc.get("updated_at")),
            })

        return items

    async def clear_conversation(self, user_id: str, conversation_id: Optional[str] = None) -> None:
        """清空对话历史"""
        if conversation_id:
            await self._db.screening_conversations.delete_one({
                "user_id": user_id,
                "conversation_id": conversation_id,
            })
            return

        doc = await self._get_conversation_doc(user_id, None)
        if not doc:
            return
        await self._db.screening_conversations.delete_one({"_id": doc["_id"]})

