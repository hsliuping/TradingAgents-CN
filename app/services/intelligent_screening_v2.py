"""
智能筛选服务 V2 - 基于意图理解的选股对话系统

架构设计：
- 意图优先：所有决策基于LLM意图理解，无硬编码关键词
- 状态机驱动：清晰的对话状态管理
- 端到端LLM协调：LLM协调整个流程
"""

import asyncio
import json
import logging
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, Dict, List, Optional
from dataclasses import dataclass, asdict
from enum import Enum

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.services.factor_registry_service import build_screening_fields_markdown
from app.services.screening_metric_display import resolve_metric_value, select_metric_display_spec
from app.services.intelligent_assistant_service import (
    _get_assistant_llm_config,
    _get_latest_trade_date,
    ASSISTANT_TIMEOUT_SECONDS,
)
from core.tools import get_tool_registry, tool_metadata_list_to_openai
from core.tools.context import set_current_user_id
from core.tools.implementations.market.stock_screening_tool import _execute_screening_query, _format_screening_output
from core.llm import UnifiedLLMClient
from core.llm.models import Message, MessageRole

logger = logging.getLogger(__name__)

# 选股场景独立预算
SCREENING_MAX_TOOL_ROUNDS = 3
SCREENING_RESULT_TIMEOUT_SECONDS = 300
MAX_CONTEXT_MESSAGES = 20
SCREENING_CONVERSATION_LIMIT = 50


async def _recall_user_plans_memory(db, user_id: str, query: str) -> str:
    """召回该用户的交易计划纪律 / 偏好（user_preference）记忆，注入到选股 prompt。

    参考：docs/05-design/v3.0/unified-memory-layer-mem0.md §15.5 P0-2
    """
    if not user_id:
        return ""
    try:
        from core.memory.service import get_memory_service
        svc = get_memory_service(db)
        return await svc.recall_formatted(
            query=query or "选股偏好",
            user_id=user_id,
            scopes=["user_preference", "trade_pattern"],
            limit=8,
            max_chars=900,
        )
    except Exception as e:
        logger.debug(f"[智能筛选V2][mem0] 记忆召回失败（已忽略）: {e}")
        return ""


def _build_plan_directive(memory_block: str) -> str:
    """构造『多交易计划处理规则』指引片段；memory_block 为空时返回空串。"""
    if not memory_block:
        return ""
    return (
        f"\n{memory_block}\n"
        "【多交易计划处理规则】如果【历史记忆】中出现多个『用户当前交易计划：xxx（v数字）』条目"
        "（例如『中长期价值』『短期波段』『机动备用』），说明用户同时维护多套并存策略。本次选股请按以下规则：\n"
        "1) 优先看用户本轮消息是否明确指定（如『按中长期计划选股』『短线机会』），如有则用对应计划纪律。\n"
        "2) 如未明确指定，但需求强相关（『长期持有』倾向中长期；『短线追涨』倾向短期），按相关性选择并在回复中说明『按您的xxx计划』。\n"
        "3) 风格不明显时，先反问用户『您想按哪个计划来选股？(中长期/短期/机动)』，再继续；不要默认按第一个或混用多个计划纪律。\n"
        "4) 严禁把不同计划的止损/仓位/选股口径混在一起。\n"
    )


class DialogState(Enum):
    """对话状态枚举"""
    IDLE = "idle"
    CONFIRMING = "confirming"
    PLANNING = "planning"
    EXECUTING = "executing"
    DONE = "done"


class IntentType(Enum):
    """意图类型枚举"""
    NEW_REQUEST = "new_request"
    ADJUST = "adjust"
    APPROVE = "approve"
    FOLLOW_UP = "follow_up"
    SINGLE_STOCK = "single_stock"


@dataclass
class IntentResult:
    """意图分类结果"""
    intent: IntentType
    slots: Dict[str, Any]
    confidence: float
    clarification_needed: bool
    clarification_question: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "intent": self.intent.value,
            "slots": self.slots,
            "confidence": self.confidence,
            "clarification_needed": self.clarification_needed,
            "clarification_question": self.clarification_question
        }


@dataclass
class ScreeningChatResponse:
    """智能筛选对话响应"""
    reply: str
    tools_used: List[str]
    stocks: List[dict]
    phase: str
    conversation_id: Optional[str] = None
    is_fallback: bool = False


class IntentClassifier:
    """纯LLM驱动的意图分类器"""

    def __init__(self, llm_client: UnifiedLLMClient):
        self.llm_client = llm_client

    async def classify(self, message: str, history: List[dict]) -> IntentResult:
        """
        分类用户意图并填充槽位

        Args:
            message: 用户最新消息
            history: 对话历史

        Returns:
            IntentResult: 意图分类结果
        """
        history_summary = self._build_history_summary(history)

        system_prompt = """你是一个专业的对话意图分类器。请分析用户最新消息，并结合对话历史，判断用户意图。

返回严格的JSON格式，不要包含其他文字：
{
    "intent": "new_request" | "adjust" | "approve" | "follow_up" | "single_stock",
    "slots": {
        "target_metric": "roe" | "pe" | "pb" | "margin" | "debt" | "cashflow" | "other" | null,
        "adjust_direction": "loosen" | "tighten" | null,
        "target_value": "10%" | "20" | "30%" | null,
        "stock_code": "002582" | "600519" | null,
        "stock_name": "好想你" | "贵州茅台" | null,
        "action": "add_favorite" | "analyze" | null
    },
    "confidence": 0.95,
    "clarification_needed": false,
    "clarification_question": null
}

意图定义：
- new_request: 用户提出了全新的选股需求
- adjust: 用户希望调整之前的筛选条件（放宽、收紧、修改等）
- approve: 用户明确批准某个方案（"执行"、"按此方案"、"好的"、"可以"、"确认"、"是的"、"没问题"等）
- follow_up: 用户基于当前结果追问（"这几只怎么样"、"加入自选"、"分析一下"等）
- single_stock: 用户询问单只股票的情况

槽位填充说明：
- target_metric: 当intent=adjust时，指出用户想调整哪个指标
- adjust_direction: 当intent=adjust时，指出是放宽(loosen)还是收紧(tighten)
- target_value: 用户明确提到的具体参数值
- stock_code/stock_name: 当intent=single_stock或follow_up涉及单只股票时提取
- action: 用户想执行的操作

澄清机制：
- 仅当意图非常模糊、完全无法判断用户想做什么时，才设置clarification_needed=true
- **用户回复"确认""是的""好的""可以"等批准性词语时，intent=approve，clarification_needed=false**
- 不要因为"缺少关键参数"而触发澄清，参数缺失可在后续阶段补充

示例：
- 用户说"帮我选低估值银行股" → intent=new_request
- 用户说"先放宽ROE吧" → intent=adjust, target_metric=roe, adjust_direction=loosen
- 用户说"把PE改成<20" → intent=adjust, target_metric=pe, adjust_direction=loosen, target_value="20"
- 用户说"执行筛选方案" → intent=approve
- 用户说"把这几只加入自选" → intent=follow_up, action=add_favorite
- 用户说"贵州茅台怎么样" → intent=single_stock, stock_name="贵州茅台"
"""

        messages = [
            Message(role=MessageRole.SYSTEM, content=system_prompt),
            Message(
                role=MessageRole.USER,
                content=f"对话历史：\n{history_summary}\n\n用户最新消息：{message}"
            )
        ]

        try:
            resp = await self.llm_client.achat(
                messages,
                tools=None,
                log_payloads=True,
                payload_log_label="intent_classification_v2"
            )
            content = resp.content if resp else ""
            result = self._parse_intent_result(content)
            return result
        except Exception as e:
            logger.warning(f"[意图分类] LLM调用失败: {e}")
            # 失败时返回默认意图
            return IntentResult(
                intent=IntentType.FOLLOW_UP,
                slots={},
                confidence=0.5,
                clarification_needed=False
            )

    def _build_history_summary(self, history: List[dict]) -> str:
        """构建历史摘要"""
        if not history:
            return "无对话历史"

        recent = history[-6:]  # 最近6条足够理解上下文
        summary = []
        for h in recent:
            role = "用户" if h["role"] == "user" else "助手"
            content = h["content"][:300] + "..." if len(h["content"]) > 300 else h["content"]
            phase = h.get("phase", "")
            phase_tag = f" [{phase}]" if phase else ""
            summary.append(f"{role}{phase_tag}: {content}")

        return "\n".join(summary)

    def _parse_intent_result(self, content: str) -> IntentResult:
        """解析LLM返回的意图结果"""
        # 提取JSON
        json_match = re.search(r'\{[\s\S]*\}', content)
        if not json_match:
            return IntentResult(
                intent=IntentType.FOLLOW_UP,
                slots={},
                confidence=0.5,
                clarification_needed=False
            )

        try:
            data = json.loads(json_match.group(0))
            intent_str = data.get("intent", "follow_up")
            intent = IntentType(intent_str) if intent_str in [t.value for t in IntentType] else IntentType.FOLLOW_UP

            return IntentResult(
                intent=intent,
                slots=data.get("slots", {}),
                confidence=float(data.get("confidence", 0.5)),
                clarification_needed=bool(data.get("clarification_needed", False)),
                clarification_question=data.get("clarification_question")
            )
        except Exception as e:
            logger.warning(f"[意图分类] JSON解析失败: {e}")
            return IntentResult(
                intent=IntentType.FOLLOW_UP,
                slots={},
                confidence=0.5,
                clarification_needed=False
            )


class StateMachine:
    """对话状态机"""

    def __init__(self):
        pass

    def determine_state(self, history: List[dict], intent: IntentResult) -> DialogState:
        """
        根据历史和意图确定当前状态

        Args:
            history: 对话历史
            intent: 意图分类结果

        Returns:
            DialogState: 当前应该进入的状态
        """
        if not history:
            return DialogState.CONFIRMING

        last_assistant = self._find_last_assistant(history)
        if not last_assistant:
            return DialogState.CONFIRMING

        last_phase = last_assistant.get("phase", "")

        # 根据最后阶段和意图来决定
        if last_phase == "confirmation":
            return DialogState.PLANNING

        if last_phase == "planning":
            if intent.intent == IntentType.ADJUST:
                return DialogState.CONFIRMING
            return DialogState.EXECUTING

        # last_phase == "result" (即 DONE)
        if intent.intent == IntentType.NEW_REQUEST:
            return DialogState.CONFIRMING

        # 其他情况都在 EXECUTING/DONE 状态处理
        return DialogState.EXECUTING

    def _find_last_assistant(self, history: List[dict]) -> Optional[dict]:
        """找到最后一条assistant消息"""
        for msg in reversed(history):
            if msg.get("role") == "assistant":
                return msg
        return None


class IntelligentScreeningServiceV2:
    """
    智能筛选服务 V2 - 基于意图理解的选股对话系统
    """

    def __init__(self, db: AsyncIOMotorDatabase):
        self._db = db
        self._llm_client: Optional[UnifiedLLMClient] = None
        self._openai_tools: Optional[list] = None
        self._result_openai_tools: Optional[list] = None
        self._tool_functions: Optional[dict] = None
        self._intent_classifier: Optional[IntentClassifier] = None
        self._state_machine = StateMachine()

    async def _ensure_client(self) -> bool:
        """懒加载 LLM 客户端和工具"""
        if self._llm_client is not None:
            return True

        llm_config = await _get_assistant_llm_config(self._db)
        if not llm_config:
            return False

        try:
            self._llm_client = UnifiedLLMClient.from_config(llm_config)
            self._intent_classifier = IntentClassifier(self._llm_client)
        except Exception as e:
            logger.error(f"[智能筛选V2] 创建 LLM 客户端失败: {e}", exc_info=True)
            return False

        # 加载选股相关工具
        registry = get_tool_registry()
        all_metadata = registry.list_all()
        screening_metadata = [
            m for m in all_metadata
            if m.fc_enabled and (
                m.category in ["screening", "market", "fundamentals", "news", "china", "technical"]
                or m.id in ["add_stocks_to_favorites", "list_watchlist_groups", "add_stock_to_watchlist"]
            )
        ]
        self._openai_tools = tool_metadata_list_to_openai(screening_metadata)

        self._tool_functions = {}
        for tool in screening_metadata:
            func = registry.get_function(tool.id)
            if func:
                self._tool_functions[tool.id] = func

        # 结果执行阶段仅保留批量筛选相关工具
        self._result_openai_tools = self._filter_result_tools(self._openai_tools)
        if not self._result_openai_tools:
            self._result_openai_tools = self._openai_tools

        self._llm_client.inject_tools(self._tool_functions)
        logger.info(f"[智能筛选V2] 已加载 {len(self._openai_tools)} 个选股工具")
        return True

    def _filter_result_tools(self, openai_tools: Optional[list]) -> list:
        """过滤result阶段可用工具"""
        if not openai_tools:
            return []

        allowlist = {"screen_stocks_by_criteria", "batch_check_profit_consistency",
                     "add_stocks_to_favorites", "list_watchlist_groups", "add_stock_to_watchlist"}
        filtered = []
        for t in openai_tools:
            fn = t.get("function", {}) if isinstance(t, dict) else {}
            name = fn.get("name")
            if name in allowlist:
                filtered.append(t)
        return filtered

    async def chat(
        self,
        user_id: str,
        message: str,
        conversation_id: Optional[str] = None,
        progress_callback: Optional[Callable[[Dict[str, Any]], Awaitable[None]]] = None,
    ) -> Dict[str, Any]:
        """
        核心对话入口
        """
        # 1. 获取历史对话
        resolved_conversation_id, history = await self._get_context_messages(user_id, conversation_id)
        if not resolved_conversation_id:
            resolved_conversation_id = conversation_id or uuid.uuid4().hex

        # 2. 确保LLM客户端就绪
        if not await self._ensure_client():
            return self._error_response("智能筛选暂时不可用，请检查 LLM 配置", resolved_conversation_id)

        set_current_user_id(user_id)

        # 3. 意图分类
        intent = await self._intent_classifier.classify(message, history)
        logger.info(f"[智能筛选V2] 用户={user_id} 意图={intent.intent.value} 置信度={intent.confidence:.2f}")

        # 4. 状态机判断（先判断状态，再决定是否需要澄清）
        state = self._state_machine.determine_state(history, intent)
        logger.info(f"[智能筛选V2] 当前状态={state.value}")

        # 5. 仅在确认阶段才允许澄清；用户正在回复确认问题时，不应再追问
        if state == DialogState.CONFIRMING and intent.clarification_needed and intent.clarification_question:
            response = {
                "reply": intent.clarification_question,
                "tools_used": [],
                "stocks": [],
                "phase": "confirming",
                "conversation_id": resolved_conversation_id,
                "is_fallback": False
            }
            await self._save_message(user_id, resolved_conversation_id, message, response["reply"], [], [], "confirming")
            return response

        # 6. 路由到对应处理器
        response: Optional[Dict[str, Any]] = None

        if state == DialogState.CONFIRMING:
            response = await self._handle_confirming(user_id, message, history, intent, resolved_conversation_id, progress_callback)
        elif state == DialogState.PLANNING:
            response = await self._handle_planning(user_id, message, history, intent, resolved_conversation_id, progress_callback)
        elif state in [DialogState.EXECUTING, DialogState.DONE]:
            response = await self._handle_executing(user_id, message, history, intent, resolved_conversation_id, progress_callback)

        if response is None:
            response = self._error_response("处理失败，请稍后重试", resolved_conversation_id)

        return response

    async def _handle_confirming(
        self,
        user_id: str,
        message: str,
        history: List[dict],
        intent: IntentResult,
        conversation_id: str,
        progress_callback: Optional[Callable[[Dict[str, Any]], Awaitable[None]]]
    ) -> Dict[str, Any]:
        """处理确认阶段"""
        await self._emit_progress(progress_callback, "phase_determined", phase="confirmation", message="正在分析您的筛选需求")

        # 召回用户交易计划/偏好记忆，注入到 prompt（多计划场景）
        memory_block = await _recall_user_plans_memory(self._db, user_id, message)
        plan_directive = _build_plan_directive(memory_block)

        system_prompt = self._get_confirmation_prompt() + plan_directive
        messages = [Message(role=MessageRole.SYSTEM, content=system_prompt)]
        for h in history[-MAX_CONTEXT_MESSAGES:]:
            role = MessageRole.USER if h["role"] == "user" else MessageRole.ASSISTANT
            messages.append(Message(role=role, content=h["content"]))
        messages.append(Message(role=MessageRole.USER, content=message))

        try:
            resp = await asyncio.wait_for(
                self._llm_client.achat(messages, tools=None, log_payloads=True, payload_log_label="screening_confirmation"),
                timeout=ASSISTANT_TIMEOUT_SECONDS
            )
            reply = resp.content if resp else "抱歉，处理失败"

            await self._save_message(user_id, conversation_id, message, reply, [], [], "confirmation")

            return {
                "reply": reply,
                "tools_used": [],
                "stocks": [],
                "phase": "confirmation",
                "conversation_id": conversation_id,
                "is_fallback": False
            }
        except asyncio.TimeoutError:
            return self._error_response("处理超时，请稍后重试", conversation_id)
        except Exception as e:
            logger.exception("[确认阶段] 处理失败")
            return self._error_response(f"处理失败: {str(e)}", conversation_id)

    async def _handle_planning(
        self,
        user_id: str,
        message: str,
        history: List[dict],
        intent: IntentResult,
        conversation_id: str,
        progress_callback: Optional[Callable[[Dict[str, Any]], Awaitable[None]]]
    ) -> Dict[str, Any]:
        """处理规划阶段"""
        await self._emit_progress(progress_callback, "phase_determined", phase="planning", message="正在生成筛选执行计划")

        tool_summary = self._build_tool_summary(self._result_openai_tools)
        # 召回交易计划/偏好记忆
        memory_block = await _recall_user_plans_memory(self._db, user_id, message)
        plan_directive = _build_plan_directive(memory_block)
        system_prompt = self._get_planning_prompt(tool_summary) + plan_directive

        messages = [Message(role=MessageRole.SYSTEM, content=system_prompt)]
        for h in history[-MAX_CONTEXT_MESSAGES:]:
            role = MessageRole.USER if h["role"] == "user" else MessageRole.ASSISTANT
            messages.append(Message(role=role, content=h["content"]))
        messages.append(Message(role=MessageRole.USER, content=message))

        try:
            resp = await asyncio.wait_for(
                self._llm_client.achat(messages, tools=None, log_payloads=True, payload_log_label="screening_planning"),
                timeout=ASSISTANT_TIMEOUT_SECONDS
            )
            reply = resp.content if resp else "抱歉，处理失败"

            await self._save_message(user_id, conversation_id, message, reply, [], [], "planning")

            return {
                "reply": reply,
                "tools_used": [],
                "stocks": [],
                "phase": "planning",
                "conversation_id": conversation_id,
                "is_fallback": False
            }
        except asyncio.TimeoutError:
            return self._error_response("处理超时，请稍后重试", conversation_id)
        except Exception as e:
            logger.exception("[规划阶段] 处理失败")
            return self._error_response(f"处理失败: {str(e)}", conversation_id)

    async def _handle_executing(
        self,
        user_id: str,
        message: str,
        history: List[dict],
        intent: IntentResult,
        conversation_id: str,
        progress_callback: Optional[Callable[[Dict[str, Any]], Awaitable[None]]]
    ) -> Dict[str, Any]:
        """处理执行阶段"""
        await self._emit_progress(progress_callback, "phase_determined", phase="result", message="正在执行批量筛选与验证")

        # 先检查是否有已批准的计划可以直接执行
        locked_plan = self._extract_locked_execution_plan(history) if intent.intent == IntentType.APPROVE else None

        # 召回交易计划/偏好记忆
        memory_block = await _recall_user_plans_memory(self._db, user_id, message)
        plan_directive = _build_plan_directive(memory_block)
        system_prompt = self._get_execution_prompt(intent, history) + plan_directive
        messages = [Message(role=MessageRole.SYSTEM, content=system_prompt)]
        for h in history[-MAX_CONTEXT_MESSAGES:]:
            role = MessageRole.USER if h["role"] == "user" else MessageRole.ASSISTANT
            messages.append(Message(role=role, content=h["content"]))
        messages.append(Message(role=MessageRole.USER, content=message))

        tools_used: List[str] = []
        structured_stocks: List[dict] = []

        async def _do_execute():
            nonlocal tools_used, structured_stocks

            if locked_plan:
                logger.info("[智能筛选V2] 使用已批准计划直接执行")
                reply, locked_tools, locked_stocks = await self._run_locked_result_execution(
                    message, locked_plan, progress_callback
                )
                tools_used.extend(locked_tools)
                structured_stocks = locked_stocks
                return reply

            # 普通执行流程
            resp = await self._llm_client.achat(
                messages,
                tools=self._result_openai_tools,
                auto_execute_tools=True,
                max_tool_rounds=SCREENING_MAX_TOOL_ROUNDS,
                tools_used=tools_used,
                progress_callback=progress_callback,
                log_payloads=True,
                payload_log_label="screening_execution"
            )
            return resp.content if resp else ""

        try:
            started_at = datetime.now(timezone.utc)
            reply = await asyncio.wait_for(_do_execute(), timeout=SCREENING_RESULT_TIMEOUT_SECONDS)
            elapsed = (datetime.now(timezone.utc) - started_at).total_seconds()
            logger.info(f"[智能筛选V2] 执行完成 耗时={elapsed:.2f}s 工具={tools_used}")

            await self._emit_progress(progress_callback, "status", phase="result",
                                     message=f"阶段处理完成，用时 {elapsed:.2f} 秒", tools_used=tools_used)

            # 提取股票
            if not structured_stocks:
                structured_stocks = self._extract_stocks(reply)

            # 清理reply中的JSON代码块（股票数据已通过stocks字段返回）
            reply = re.sub(r'```json\s*\{[\s\S]*?\}\s*```', '', reply)
            reply = re.sub(r'```\s*\{[\s\S]*?\}\s*```', '', reply)
            reply = reply.strip()

            # 如果没有找到股票且用了筛选工具，返回明确的无结果提示
            if not structured_stocks and "screen_stocks_by_criteria" in tools_used:
                reply = self._build_no_match_reply(message)
                structured_stocks = []

            await self._save_message(user_id, conversation_id, message, reply, tools_used, structured_stocks, "result")

            return {
                "reply": reply,
                "tools_used": tools_used,
                "stocks": structured_stocks,
                "phase": "result",
                "conversation_id": conversation_id,
                "is_fallback": False
            }
        except asyncio.TimeoutError:
            reply = self._build_timeout_reply(SCREENING_RESULT_TIMEOUT_SECONDS)
            await self._save_message(user_id, conversation_id, message, reply, [], [], "result")
            return {
                "reply": reply,
                "tools_used": [],
                "stocks": [],
                "phase": "result",
                "conversation_id": conversation_id,
                "is_fallback": False
            }
        except Exception as e:
            logger.exception("[执行阶段] 处理失败")
            reply = f"处理您的请求时发生错误: {str(e)}。请稍后重试。"
            await self._save_message(user_id, conversation_id, message, reply, [], [], "result")
            return {
                "reply": reply,
                "tools_used": [],
                "stocks": [],
                "phase": "result",
                "conversation_id": conversation_id,
                "is_fallback": False
            }

    def _get_confirmation_prompt(self) -> str:
        """获取确认阶段提示词"""
        curr_date = _get_latest_trade_date()
        return f"""你是一位专业的 A 股选股专家。用户提出了选股或行业研究需求。

## 你的任务：需求分析与确认

**不要调用任何工具，不要推荐股票。** 请按以下步骤回复：

1. **分析理解**：提炼用户需求的核心条件（行业、估值、风格、时间维度等）
2. **展示理解**：用清晰的列表形式告诉用户"我理解您的需求是..."
3. **改进建议**：基于专业判断，提出 2-3 条可选的改进建议
4. **等待确认**：明确询问用户是"按原需求筛选"还是"采纳建议后再筛选"

## 重要规则

- **行业/板块类问题**：如"养猪行业龙头有哪些"，应理解为"筛选该行业内按市值/营收排序的头部公司"，转化为筛选条件（行业=xxx + 按市值降序 + 取前N只），**不要追问具体股票名称**
- **用户回复"确认""好的""是的""可以"等**：表示批准当前方案，不要再追问
- 如果用户使用"低估值"这类模糊描述，但没有明确口径，请指出歧义并建议默认值
- PE 相关口径区分 PE / PE(TTM)
- PB 相关口径区分 PB / PB(MRQ)

当前日期：{curr_date}
只分析需求，不推荐股票，不调用工具。
"""

    def _get_planning_prompt(self, tool_summary: str) -> str:
        """获取规划阶段提示词"""
        curr_date = _get_latest_trade_date()
        screening_fields = build_screening_fields_markdown(public_only=True)
        return f"""你是一位专业的 A 股选股专家。用户已确认选股需求，请制定详细的执行计划。

## 可用工具清单

{tool_summary}

## `screen_stocks_by_criteria` 支持的筛选字段

{screening_fields}

支持的操作符：> < >= <= == != between in not_in contains

## 你的任务：执行计划说明

**不要调用任何工具，不要推荐股票。** 请详细说明你打算如何执行此次筛选：

1. **筛选策略**：总结最终采用的筛选条件
2. **工具调用计划**：列出工具名和具体参数（JSON格式的conditions）
3. **数据处理**：说明如何从工具返回结果中选出最终 5 只股票
4. **请求批准**：询问用户是否同意该方案

回复格式中请明确包含：
- `conditions`: [...] （筛选条件的JSON数组）
- `limit`: 50 （候选数量）
- `order_by_field`: "total_mv" （排序字段）
- `order_direction`: "desc" （排序方向）

当前日期：{curr_date}
只说明计划，不调用工具，不推荐股票。
"""

    def _get_execution_prompt(self, intent: IntentResult, history: List[dict]) -> str:
        """获取执行阶段提示词"""
        curr_date = _get_latest_trade_date()

        intent_hint = ""
        if intent.intent == IntentType.ADJUST:
            target = intent.slots.get("target_metric", "未知指标")
            direction = intent.slots.get("adjust_direction", "")
            params = intent.slots.get("target_value", "")
            intent_hint = f"""
## 当前用户意图分析（重要）

用户希望**调整筛选条件**：
- 调整目标：{target}
- 调整方向：{'放宽条件' if direction == 'loosen' else '收紧条件' if direction == 'tighten' else ''}
- 明确参数：{params or '用户未明确给出具体数值，请根据对话历史中的建议推断'}

请仔细阅读对话历史，找到之前的筛选条件，然后按用户意图调整后重新筛选。
特别注意：如果历史中助手给出了具体的调整建议表格（如"放宽 ROE > 15% → ROE > 10%"），请优先采用那个建议值。
"""
        elif intent.intent == IntentType.APPROVE:
            intent_hint = """
## 当前用户意图分析（重要）

用户已**批准执行计划**，请按之前规划的参数立即执行筛选。
"""
        elif intent.intent == IntentType.FOLLOW_UP:
            action = intent.slots.get("action", "")
            if action == "add_favorite":
                intent_hint = """
## 当前用户意图分析（重要）

用户希望**将筛选结果加入关注列表**。请：
1. 调用 `add_stocks_to_favorites` 工具，将之前筛选出的股票批量添加到用户的关注列表
2. 参数 `stocks_json` 是一个 JSON 数组，格式如 `[{"code":"002714","name":"牧原股份","market":"A股"}]`
3. 可通过 `tags` 参数给这批股票打标签（如用户指定了分组名，可作为标签）
4. 告诉用户操作结果

**不要说"无法获取分组信息"或让用户手动操作，必须调用工具完成。**
"""
            else:
                intent_hint = """
## 当前用户意图分析（重要）

用户在**追问当前结果**。请根据用户的问题，调用合适的工具回答。
"""

        return f"""你是一位专业的 A 股选股专家。
{intent_hint}

## 你的任务

### 筛选任务
1. **调用工具**：按计划调用 `screen_stocks_by_criteria` 等工具获取数据
2. **精选推荐**：每次严格推荐 **5 只** 最符合条件的股票（如果筛选结果不足5只，就推荐实际找到的数量）
3. **结构化输出**：在回答最后包含以下 JSON 代码块

```json
{{
    "stocks": [
        {{
            "code": "002582",
            "name": "好想你",
            "industry": "食品",
            "price": 12.34,
            "pe": 2.78,
            "pe_display_label": "PE(TTM)",
            "pb": 1.05,
            "pb_display_label": "PB(MRQ)",
            "roe": 24.4,
            "dividend_yield": 8.11,
            "debt_to_assets": 32.0,
            "reason": "推荐理由..."
        }}
    ]
}}
```

### 关注列表操作
- 用户说"加入自选""加入关注"时，调用 `add_stocks_to_favorites` 批量添加到关注列表
- 参数 `stocks_json` 格式：`[{{"code":"002714","name":"牧原股份","market":"A股"}}]`
- 可通过 `tags` 参数给这批股票打标签
- **不要让用户手动操作，必须通过工具完成**

当前日期：{curr_date}
- 最多执行 {SCREENING_MAX_TOOL_ROUNDS} 轮工具调用
- 如果工具结果中没有足够数据，就直接说明，不要编造
- 不要给出具体的买入/卖出建议，只做选股推荐和分析
- 只推荐 A 股（沪深两市）
"""

    def _build_tool_summary(self, tools: Optional[list] = None) -> str:
        """构建工具摘要"""
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
            lines.append(f"- `{name}`: {desc}\n  参数: {param_names}")
        return "\n".join(lines)

    def _extract_locked_execution_plan(self, history: List[dict]) -> Optional[dict]:
        """从历史中提取已批准的执行计划"""
        latest_planning = None
        for item in reversed(history):
            if item.get("role") == "assistant" and item.get("phase") == "planning":
                latest_planning = item
                break

        if not latest_planning:
            return None

        content = str(latest_planning.get("content", ""))
        conditions_match = re.search(r'`?conditions`?\s*[:：]\s*`(\[[\s\S]*?\])`', content)
        limit_match = re.search(r'`?limit`?\s*[:：]\s*(\d+)', content)
        order_by_match = re.search(r'`?order_by_field`?\s*[:：]\s*"([^"]+)"', content)
        order_direction_match = re.search(r'`?order_direction`?\s*[:：]\s*"([^"]+)"', content)

        if not conditions_match:
            return None

        try:
            raw_conditions = json.loads(conditions_match.group(1))
        except json.JSONDecodeError:
            return None

        if not isinstance(raw_conditions, list) or not raw_conditions:
            return None

        return {
            "planning_content": content,
            "screen": {
                "conditions_json": json.dumps(raw_conditions, ensure_ascii=False),
                "limit": int(limit_match.group(1)) if limit_match else 50,
                "order_by_field": order_by_match.group(1) if order_by_match else "total_mv",
                "order_direction": order_direction_match.group(1) if order_direction_match else "desc",
            }
        }

    async def _run_locked_result_execution(
        self,
        message: str,
        locked_plan: dict,
        progress_callback: Optional[Callable[[Dict[str, Any]], Awaitable[None]]]
    ) -> tuple[str, List[str], List[dict]]:
        """按已批准计划直接执行"""
        tools_used: List[str] = []

        screen_args = locked_plan["screen"]
        raw_conditions = json.loads(screen_args.get("conditions_json", "[]"))

        await self._emit_progress(
            progress_callback, "status", phase="result", message="按已批准的执行计划直接运行批量筛选"
        )

        screen_items, total_candidates = await _execute_screening_query(
            raw_conditions,
            int(screen_args.get("limit", 50)),
            screen_args.get("order_by_field", "total_mv"),
            screen_args.get("order_direction", "desc"),
        )
        tools_used.append("screen_stocks_by_criteria")

        stocks = self._build_structured_stocks(screen_items, raw_conditions, screen_args.get("order_by_field", "total_mv"), "")
        reply = self._build_locked_result_reply(total_candidates, stocks, "")

        return reply, tools_used, stocks

    def _build_structured_stocks(self, items: list, raw_conditions: list, order_by_field: str, batch_output: str) -> List[dict]:
        """构建结构化股票列表"""
        if not items:
            return []

        stocks: List[dict] = []
        for item in items[:5]:
            code = str(item.get("code") or item.get("symbol", "")).strip()
            if not code:
                continue

            pe_display_field, pe_display_label = select_metric_display_spec(raw_conditions, order_by_field, "pe")
            pb_display_field, pb_display_label = select_metric_display_spec(raw_conditions, order_by_field, "pb")

            stocks.append({
                "code": code,
                "name": str(item.get("name", "")),
                "industry": str(item.get("industry", "")),
                "price": item.get("close"),
                "pe": resolve_metric_value(item, pe_display_field, "pe"),
                "pe_display_label": pe_display_label,
                "pb": resolve_metric_value(item, pb_display_field, "pb"),
                "pb_display_label": pb_display_label,
                "roe": item.get("roe"),
                "roa": item.get("roa"),
                "gross_margin": item.get("gross_margin"),
                "netprofit_margin": item.get("netprofit_margin"),
                "dividend_yield": item.get("dividend_yield"),
                "debt_to_assets": item.get("debt_to_assets"),
                "assets_to_eqt": item.get("assets_to_eqt"),
                "current_ratio": item.get("current_ratio"),
                "quick_ratio": item.get("quick_ratio"),
                "cash_ratio": item.get("cash_ratio"),
                "revenue_ttm": item.get("revenue_ttm"),
                "netprofit_ttm": item.get("net_profit_ttm"),
                "n_cashflow_act": item.get("n_cashflow_act"),
                "report_period": item.get("report_period"),
                "pct_change": item.get("pct_change"),
                "reason": "符合筛选条件"
            })
        return stocks

    def _build_locked_result_reply(self, total_candidates: int, stocks: List[dict], batch_output: str) -> str:
        """构建结果回复"""
        lines = ["已按批准的筛选方案执行完成。"]
        if total_candidates:
            lines.append(f"共筛出 {total_candidates} 只候选。")

        if not stocks:
            lines.append("当前未找到符合条件的股票。")
        else:
            lines.append(f"以下是最符合条件的 {len(stocks)} 只候选：")
            for i, stock in enumerate(stocks, 1):
                metrics = []
                if stock.get("price"):
                    metrics.append(f"价格={stock['price']:.2f}")
                if stock.get("pe"):
                    metrics.append(f"{stock.get('pe_display_label', 'PE')}={stock['pe']:.2f}")
                if stock.get("pb"):
                    metrics.append(f"{stock.get('pb_display_label', 'PB')}={stock['pb']:.2f}")
                if stock.get("roe"):
                    metrics.append(f"ROE={stock['roe']:.2f}%")

                lines.append(f"{i}. {stock.get('code')} {stock.get('name')} ({stock.get('industry', '未知')})")
                if metrics:
                    lines.append(f"   - {'; '.join(metrics)}")

        return "\n".join(lines)

    def _extract_stocks(self, reply: str) -> List[dict]:
        """从LLM回复中提取股票"""
        pattern = r'```json\s*(\{[\s\S]*?\})\s*```'
        match = re.search(pattern, reply)
        if match:
            try:
                data = json.loads(match.group(1))
                return data.get("stocks", [])
            except json.JSONDecodeError:
                pass
        return []

    def _build_no_match_reply(self, message: str) -> str:
        """构建无匹配结果的回复"""
        return f"未找到符合当前筛选条件的股票。\n\n当前没有适合该筛选要求的标的。如果您仍想继续筛选，请考虑调整条件。"

    def _build_timeout_reply(self, timeout_seconds: int) -> str:
        """构建超时回复"""
        return f"抱歉，处理您的选股请求已超时（超过 {timeout_seconds} 秒）。\n\n请您缩小筛选范围、补充更明确的条件，或稍后重试。"

    def _error_response(self, message: str, conversation_id: str) -> Dict[str, Any]:
        """构建错误响应"""
        return {
            "reply": message,
            "tools_used": [],
            "stocks": [],
            "phase": "result",
            "conversation_id": conversation_id,
            "is_fallback": False
        }

    async def _emit_progress(
        self,
        progress_callback: Optional[Callable[[Dict[str, Any]], Awaitable[None]]],
        event: str,
        **data
    ) -> None:
        """发送进度事件"""
        if not progress_callback:
            return

        payload = {
            "event": event,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            **data
        }
        try:
            await progress_callback(payload)
        except Exception as e:
            logger.debug("[智能筛选V2] 进度推送失败: %s", e)

    async def _save_message(
        self,
        user_id: str,
        conversation_id: str,
        user_msg: str,
        assistant_reply: str,
        tools_used: List[str],
        stocks: List[dict],
        phase: str,
        is_fallback: bool = False
    ) -> None:
        """保存消息到数据库"""
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

    def _build_conversation_title(self, message: str) -> str:
        """构建会话标题"""
        text = re.sub(r"\s+", " ", (message or "").strip())
        if not text:
            return "未命名筛选"
        return text[:30]

    async def _get_context_messages(self, user_id: str, conversation_id: Optional[str] = None) -> tuple[str, List[dict]]:
        """获取历史对话消息"""
        doc = await self._get_conversation_doc(user_id, conversation_id)
        if not doc or not doc.get("messages"):
            return conversation_id or "", []
        messages = doc["messages"]
        return doc.get("conversation_id", conversation_id or ""), messages[-MAX_CONTEXT_MESSAGES:]

    async def _get_conversation_doc(self, user_id: str, conversation_id: Optional[str] = None) -> Optional[dict]:
        """获取会话文档"""
        if conversation_id:
            doc = await self._db.screening_conversations.find_one({
                "user_id": user_id,
                "conversation_id": conversation_id,
            })
            return doc

        doc = await self._db.screening_conversations.find_one(
            {"user_id": user_id},
            sort=[("updated_at", -1), ("created_at", -1)],
        )
        return doc

    async def get_conversation(self, user_id: str, conversation_id: Optional[str] = None) -> tuple[Optional[str], List[dict]]:
        """获取完整对话历史"""
        doc = await self._get_conversation_doc(user_id, conversation_id)
        if not doc:
            return conversation_id, []
        return doc.get("conversation_id"), doc.get("messages", [])

    async def list_conversations(self, user_id: str) -> List[dict]:
        """获取会话列表"""
        cursor = self._db.screening_conversations.find({"user_id": user_id}).sort([
            ("updated_at", -1),
            ("created_at", -1),
        ])
        docs = await cursor.to_list(length=100)

        items = []
        for doc in docs:
            messages = doc.get("messages", [])
            preview = ""
            for item in reversed(messages):
                content = str(item.get("content", "")).strip()
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
        """清空会话"""
        if conversation_id:
            await self._db.screening_conversations.delete_one({
                "user_id": user_id,
                "conversation_id": conversation_id,
            })
            return

        doc = await self._get_conversation_doc(user_id, None)
        if doc:
            await self._db.screening_conversations.delete_one({"_id": doc["_id"]})

    def _format_dt(self, value: Any) -> Optional[str]:
        """格式化日期"""
        if isinstance(value, datetime):
            return value.isoformat()
        if isinstance(value, str):
            return value
        return None
