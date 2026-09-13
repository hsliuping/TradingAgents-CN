"""
规划分析服务 — Plan-then-Execute 模式

编排三级保障流程：
  1. 种子流程匹配 → 2. LLM 自主规划 → 3. ReAct 回退

依赖共享层（来自 intelligent_assistant_service）：
  - _get_assistant_llm_config()
  - _get_system_prompt()
  - _get_latest_trade_date()
"""

import asyncio
import json
import logging
import os
import re
from typing import Any, AsyncGenerator, AsyncIterator, Dict, List, Optional

from core.agents.plan_executor import PlanExecutor
from core.agents.planner import Planner
from core.agents.planner_models import (
    AnalysisPlan,
    PlanSource,
    PlanStep,
    PlannedAnalysisResult,
    StepResult,
    SupplementRequest,
)
from core.llm import UnifiedLLMClient
from core.llm.models import Message, MessageRole
from core.tools import get_tool_registry, tool_metadata_list_to_openai

from app.services.intelligent_assistant_service import (
    _get_assistant_llm_config,
    _build_assistant_model_preferences,
    _build_fallback_memory_facts,
    _get_preferred_assistant_config_id,
    _get_preferred_assistant_model,
    _get_system_prompt,
    _get_latest_trade_date,
    get_assistant_conversation,
    get_or_create_assistant_thread,
    IntelligentAssistantService,
    save_assistant_message,
)

logger = logging.getLogger(__name__)


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


async def _store_planned_analysis_memory(
    db,
    user_id: str,
    conversation_id: str,
    user_message: str,
    reply: str,
    tools_used: List[str],
    source: str,
) -> None:
    """规划分析回复不再写入 mem0 长期记忆，避免自由文本污染。"""
    return


# ============================================================
# 不支持品种检测
# ============================================================
# 词表与检测逻辑已收编至 core.assistant.lexicon（A11 阶段4：词典收敛单处，
# 助手路由与规划分析共用同一套品种闸门），此处仅保留兼容委托。


def _check_unsupported_asset(question: str) -> Optional[str]:
    """检测用户问题是否涉及不支持的品种类型（事实源：core.assistant.lexicon）。

    Returns:
        如果检测到不支持的品种，返回提示信息；否则返回 None。
    """
    from core.assistant.lexicon import detect_unsupported_asset
    return detect_unsupported_asset(question)

# 整体超时
PLANNED_ANALYSIS_TIMEOUT = int(os.environ.get("PLANNED_ANALYSIS_TIMEOUT", "180"))

# 会话上下文最大条数
MAX_CONTEXT_MESSAGES = 5


def _build_synthesize_prompt(
    question: str,
    plan: AnalysisPlan,
    step_results: List[StepResult],
) -> str:
    """构建综合阶段 prompt"""
    results_text = ""
    for sr in step_results:
        status = "✅ 成功" if sr.success else f"❌ 失败: {sr.error}"
        result_preview = str(sr.result)[:2000] if sr.result else "(无数据)"
        results_text += f"\n### 步骤 {sr.step_id}: {sr.intent}\n"
        results_text += f"- 工具: {sr.tool}\n- 状态: {status}\n"
        results_text += f"- 数据:\n```\n{result_preview}\n```\n"

    return f"""基于以下分析数据，回答用户问题。

## 用户问题
{question}

## 分析结果
{results_text}

## 要求（以投资教练的身份回答）
1. 基于工具返回的客观数据进行解读，教用户如何理解这些数据
2. 讲解分析方法和框架，引导用户建立自己的判断，不给"买入/卖出"的直接建议
3. 遇到专业概念时用通俗语言解释
4. 如果某些数据获取失败，说明原因并基于已有数据回答
5. 如果数据严重不足无法回答，在回答末尾添加一行: [NEED_SUPPLEMENT]
6. 使用 Markdown 格式，条理清晰
7. 结尾自然提醒：以上分析仅供学习参考，不构成投资建议

请回答："""


def _build_supplement_prompt(
    question: str,
    current_answer: str,
) -> str:
    """构建补充请求判断 prompt"""
    return f"""你之前基于工具数据回答了用户问题，但标记了数据不足。

## 用户问题
{question}

## 当前回答（不完整）
{current_answer}

## 要求
如果需要补充数据，返回 JSON 格式的补充请求：
```json
{{
  "reason": "需要补充的原因",
  "steps": [
    {{"id": 1, "tool": "工具ID", "args": {{"参数": "值"}}, "intent": "目的", "depends_on": []}}
  ]
}}
```
补充步骤最多 2 个。如果不需要补充直接返回 "none"。"""


class PlannedAnalysisService:
    """
    规划分析服务

    编排完整的 Plan → Execute → Synthesize 流程。
    若规划失败，回退到 ReAct 模式（复用 IntelligentAssistantService）。
    """

    def __init__(self, db, preferred_models: Optional[Dict[str, Any]] = None):
        self._db = db
        self._llm_client: Optional[UnifiedLLMClient] = None
        self._tool_functions: Optional[Dict[str, Any]] = None
        self._openai_tools: Optional[List[Dict[str, Any]]] = None
        self._preferred_model = _get_preferred_assistant_model(preferred_models)
        self._preferred_model_config_id = _get_preferred_assistant_config_id(preferred_models)

    def _get_react_preferred_models(self) -> Dict[str, str]:
        if not self._preferred_model and not self._preferred_model_config_id:
            return {}
        preferred: Dict[str, str] = {}
        if self._preferred_model:
            preferred["model"] = self._preferred_model
        if self._preferred_model_config_id:
            preferred["model_config_id"] = self._preferred_model_config_id
        return preferred

    async def _ensure_client(self) -> bool:
        """确保 LLM 客户端和工具已加载"""
        if self._llm_client is not None:
            return True

        llm_config = await _get_assistant_llm_config(
            self._db,
            preferred_models=self._get_react_preferred_models() or None,
        )
        if not llm_config:
            return False

        try:
            self._llm_client = UnifiedLLMClient.from_config(llm_config)
        except Exception as e:
            logger.error(f"[规划分析] 创建 LLM 客户端失败: {e}", exc_info=True)
            return False

        registry = get_tool_registry()
        all_metadata = registry.list_all()
        self._openai_tools = tool_metadata_list_to_openai(all_metadata)

        self._tool_functions = {}
        for tool in all_metadata:
            if tool.fc_enabled and tool.parameters:
                func = registry.get_function(tool.id)
                if func:
                    self._tool_functions[tool.id] = func

        self._llm_client.inject_tools(self._tool_functions)
        logger.info(f"[规划分析] 已加载 {len(self._openai_tools)} 个工具")
        return True

    # ----------------------------------------------------------
    # 公共接口
    # ----------------------------------------------------------

    async def analyze(
        self,
        question: str,
        user_id: Optional[str] = None,
        conversation_id: Optional[str] = None,
    ) -> PlannedAnalysisResult:
        """
        执行规划分析。

        Args:
            question: 用户问题
            user_id: 用户 ID（用于获取会话历史）
            conversation_id: 会话 ID

        Returns:
            PlannedAnalysisResult
        """
        # === 前置检查：不支持的品种类型 ===
        unsupported_msg = _check_unsupported_asset(question)
        if unsupported_msg:
            logger.info(f"[规划分析] 检测到不支持的品种类型，直接返回提示")
            return PlannedAnalysisResult(
                reply=unsupported_msg,
                source=PlanSource.SEED_FLOW,
            )

        if not await self._ensure_client():
            return PlannedAnalysisResult(
                reply="智能分析暂时不可用，请检查 LLM 配置是否已在「设置」中正确配置。",
                source=PlanSource.REACT_FALLBACK,
            )

        try:
            return await asyncio.wait_for(
                self._do_analyze(question, user_id, conversation_id),
                timeout=PLANNED_ANALYSIS_TIMEOUT,
            )
        except asyncio.TimeoutError:
            logger.warning(f"[规划分析] 整体超时（{PLANNED_ANALYSIS_TIMEOUT}s）")
            return PlannedAnalysisResult(
                reply=f"抱歉，分析用时过长（已超过 {PLANNED_ANALYSIS_TIMEOUT} 秒）。\n\n"
                      "建议您尝试将问题拆分得更具体一些，或稍后重试。",
                source=PlanSource.REACT_FALLBACK,
            )
        except Exception as e:
            logger.exception("[规划分析] 分析失败")
            return PlannedAnalysisResult(
                reply=f"处理您的请求时发生错误：{str(e)}。请检查网络和 LLM 配置后重试。",
                source=PlanSource.REACT_FALLBACK,
            )

    async def analyze_stream(
        self,
        question: str,
        user_id: Optional[str] = None,
        conversation_id: Optional[str] = None,
    ) -> AsyncGenerator[str, None]:
        """流式执行规划分析，输出 SSE 事件。"""
        unsupported_msg = _check_unsupported_asset(question)
        if unsupported_msg:
            yield _sse("token", {"content": unsupported_msg})
            yield _sse(
                "done",
                {
                    "reply": unsupported_msg,
                    "tools_used": [],
                    "source": PlanSource.SEED_FLOW.value,
                    "supplemented": False,
                },
            )
            return

        if not await self._ensure_client():
            message = "智能分析暂时不可用，请检查 LLM 配置是否已在「设置」中正确配置。"
            yield _sse("token", {"content": message})
            yield _sse(
                "done",
                {
                    "reply": message,
                    "tools_used": [],
                    "source": PlanSource.REACT_FALLBACK.value,
                    "supplemented": False,
                },
            )
            return

        tools_used: List[str] = []
        collected_step_results: List[StepResult] = []
        supplemented = False
        plan: Optional[AnalysisPlan] = None

        try:
            context_messages = await self._get_context_messages(user_id, conversation_id)

            curr_date = _get_latest_trade_date()
            trade_date = curr_date

            knowledge_snippets = ""
            try:
                from core.knowledge import FinancialKnowledgeManager
                km = FinancialKnowledgeManager(db=self._db)
                knowledge_snippets = km.retrieve_for_prompt(question)
            except Exception as e:
                logger.debug(f"[规划分析] 知识检索跳过: {e}")

            yield _sse("plan_started", {"message": "正在规划分析步骤"})

            planner = Planner(
                llm_client=self._llm_client,
                curr_date=curr_date,
                trade_date=trade_date,
            )
            plan = await planner.plan(question, context_messages, knowledge_snippets=knowledge_snippets)

            if plan.source == PlanSource.REACT_FALLBACK:
                yield _sse(
                    "mode_switch",
                    {"source": PlanSource.REACT_FALLBACK.value, "message": "规划失败，回退到 ReAct 模式"},
                )
                react_service = IntelligentAssistantService(
                    self._db,
                    preferred_models=self._get_react_preferred_models(),
                )
                async for event_str in react_service.chat_stream(question, conversation_id):
                    yield event_str
                return

            yield _sse(
                "plan_ready",
                {
                    "plan": plan.model_dump(),
                    "source": plan.source.value,
                },
            )

            executor = PlanExecutor()
            step_queue: asyncio.Queue = asyncio.Queue()

            def _on_step_started(step_id: int, tool: str, intent: str):
                step_queue.put_nowait(
                    {
                        "event": "step_started",
                        "step_id": step_id,
                        "tool": tool,
                        "intent": intent,
                    }
                )

            def _on_step_completed(sr: StepResult):
                tools_used.append(sr.tool)
                step_queue.put_nowait(
                    {
                        "event": "step_completed",
                        "step_result": sr.model_dump(),
                    }
                )

            execute_task = asyncio.create_task(
                executor.execute(
                    plan,
                    on_step_started=_on_step_started,
                    on_step_completed=_on_step_completed,
                )
            )

            while not execute_task.done() or not step_queue.empty():
                try:
                    payload = await asyncio.wait_for(step_queue.get(), timeout=0.3)
                    event_name = payload.pop("event", "progress")
                    if event_name == "step_completed":
                        step_result = payload.get("step_result")
                        if step_result:
                            collected_step_results.append(StepResult(**step_result))
                    yield _sse(event_name, payload)
                except asyncio.TimeoutError:
                    continue

            step_results = await execute_task
            collected_step_results = step_results

            yield _sse("synthesis_started", {"message": "正在汇总结论并生成报告"})
            reply_parts: List[str] = []
            async for chunk in self._stream_synthesize_chunks(question, plan, collected_step_results):
                reply_parts.append(chunk)
                yield _sse("token", {"content": chunk})
            reply = "".join(reply_parts)

            if "[NEED_SUPPLEMENT]" in reply:
                reply = reply.replace("[NEED_SUPPLEMENT]", "").strip()
                yield _sse("supplement_started", {"message": "正在补充缺失数据"})
                supplement_result = await self._try_supplement(question, reply, plan, tools_used)
                if supplement_result:
                    for sr in supplement_result:
                        collected_step_results.append(sr)
                        yield _sse("step_completed", {"step_result": sr.model_dump()})

                    yield _sse("synthesis_started", {"message": "补充完成，正在重新整理答案"})
                    reply_parts = []
                    async for chunk in self._stream_synthesize_chunks(question, plan, collected_step_results):
                        reply_parts.append(chunk)
                        yield _sse("token", {"content": chunk})
                    reply = "".join(reply_parts).replace("[NEED_SUPPLEMENT]", "").strip()
                    supplemented = True

            yield _sse(
                "done",
                {
                    "reply": reply,
                    "tools_used": list(set(tools_used)),
                    "step_results": [sr.model_dump() for sr in collected_step_results],
                    "plan": plan.model_dump() if plan else None,
                    "source": plan.source.value if plan else PlanSource.LLM_PLAN.value,
                    "supplemented": supplemented,
                },
            )
        except asyncio.CancelledError:
            yield _sse("error", {"message": "请求已取消"})
            yield _sse("done", {"tools_used": list(set(tools_used)), "error": True})
        except Exception as e:
            logger.exception("[规划分析] 流式分析失败")
            yield _sse("error", {"message": f"处理请求时发生错误：{str(e)}"})
            yield _sse("done", {"tools_used": list(set(tools_used)), "error": True})

    # ----------------------------------------------------------
    # 内部实现
    # ----------------------------------------------------------

    async def _do_analyze(
        self,
        question: str,
        user_id: Optional[str] = None,
        conversation_id: Optional[str] = None,
    ) -> PlannedAnalysisResult:
        """核心分析流程"""
        # 获取会话上下文
        context_messages = await self._get_context_messages(user_id, conversation_id)

        curr_date = _get_latest_trade_date()
        trade_date = curr_date  # 交易日与当前日期一致（_get_latest_trade_date 已处理周末）

        # RAG 动态知识检索（优雅降级：不可用时返回空字符串）
        knowledge_snippets = ""
        try:
            from core.knowledge import FinancialKnowledgeManager
            km = FinancialKnowledgeManager(db=self._db)
            knowledge_snippets = km.retrieve_for_prompt(question)
        except Exception as e:
            logger.debug(f"[规划分析] 知识检索跳过: {e}")

        # === 阶段 1：规划 ===
        planner = Planner(
            llm_client=self._llm_client,
            curr_date=curr_date,
            trade_date=trade_date,
        )
        plan = await planner.plan(question, context_messages, knowledge_snippets=knowledge_snippets)

        # 第三级回退：ReAct
        if plan.source == PlanSource.REACT_FALLBACK:
            return await self._react_fallback(question, conversation_id)

        # === 阶段 2：执行 ===
        tools_used: List[str] = []
        executor = PlanExecutor()
        step_results = await executor.execute(
            plan,
            on_step_started=lambda sid, tool, intent: logger.info(
                f"[规划分析] 步骤 {sid} 开始: {tool} - {intent}"
            ),
            on_step_completed=lambda sr: (
                tools_used.append(sr.tool),
                logger.info(
                    f"[规划分析] 步骤 {sr.step_id} 完成: "
                    f"{'成功' if sr.success else '失败'} ({sr.duration_ms}ms)"
                ),
            ),
        )

        # === 阶段 3：综合 ===
        reply = await self._synthesize(question, plan, step_results)

        # 有限补充机制
        supplemented = False
        if "[NEED_SUPPLEMENT]" in reply:
            reply = reply.replace("[NEED_SUPPLEMENT]", "").strip()
            supplement_result = await self._try_supplement(
                question, reply, plan, tools_used
            )
            if supplement_result:
                step_results.extend(supplement_result)
                reply = await self._synthesize(question, plan, step_results)
                reply = reply.replace("[NEED_SUPPLEMENT]", "").strip()
                supplemented = True

        return PlannedAnalysisResult(
            reply=reply,
            plan=plan,
            tools_used=list(set(tools_used)),
            step_results=step_results,
            source=plan.source,
            supplemented=supplemented,
        )

    async def _synthesize(
        self,
        question: str,
        plan: AnalysisPlan,
        step_results: List[StepResult],
    ) -> str:
        """综合阶段：基于步骤结果生成最终回答"""
        system_prompt = _get_system_prompt()
        synth_prompt = _build_synthesize_prompt(question, plan, step_results)

        messages = [
            Message(role=MessageRole.SYSTEM, content=system_prompt),
            Message(role=MessageRole.USER, content=synth_prompt),
        ]

        try:
            resp = await self._llm_client.achat(messages)
            return resp.content or "抱歉，暂时无法生成综合分析。"
        except Exception as e:
            logger.error(f"[规划分析] 综合阶段失败: {e}")
            # 降级：拼接原始数据
            parts = [f"## {question}\n"]
            for sr in step_results:
                if sr.success and sr.result:
                    parts.append(f"### {sr.intent}\n{str(sr.result)[:1000]}\n")
            parts.append("\n> ⚠️ 综合分析生成失败，以上为原始数据摘要。")
            return "\n".join(parts)

    async def _stream_synthesize_chunks(
        self,
        question: str,
        plan: AnalysisPlan,
        step_results: List[StepResult],
    ) -> AsyncIterator[str]:
        """综合阶段流式输出 token。"""
        system_prompt = _get_system_prompt()
        synth_prompt = _build_synthesize_prompt(question, plan, step_results)

        messages = [
            Message(role=MessageRole.SYSTEM, content=system_prompt),
            Message(role=MessageRole.USER, content=synth_prompt),
        ]

        try:
            has_chunk = False
            async for chunk in self._llm_client.astream(messages):
                if chunk:
                    has_chunk = True
                    yield chunk
            if not has_chunk:
                fallback = await self._synthesize(question, plan, step_results)
                for i in range(0, len(fallback), 120):
                    yield fallback[i:i + 120]
        except Exception as e:
            logger.warning(f"[规划分析] 综合流式输出失败，回退到非流式综合: {e}")
            fallback = await self._synthesize(question, plan, step_results)
            for i in range(0, len(fallback), 120):
                yield fallback[i:i + 120]

    async def _try_supplement(
        self,
        question: str,
        current_answer: str,
        plan: AnalysisPlan,
        tools_used: List[str],
    ) -> Optional[List[StepResult]]:
        """有限补充机制：最多 1 轮，最多 2 个工具调用"""
        prompt = _build_supplement_prompt(question, current_answer)
        messages = [
            Message(role=MessageRole.SYSTEM, content="你是股票分析规划器，只输出 JSON 或 none。"),
            Message(role=MessageRole.USER, content=prompt),
        ]

        try:
            resp = await self._llm_client.achat(messages)
            raw = (resp.content or "").strip()

            if raw.lower() == "none" or not raw:
                return None

            # 解析补充请求
            import re
            json_match = re.search(r"```(?:json)?\s*([\s\S]*?)```", raw)
            text = json_match.group(1).strip() if json_match else raw.strip()
            start = text.find("{")
            end = text.rfind("}")
            if start == -1 or end == -1:
                return None

            data = json.loads(text[start:end + 1])
            raw_steps = data.get("steps", [])[:2]  # 最多 2 个

            # 构建补充步骤并执行
            supplement_steps = []
            max_id = max((s.id for s in plan.steps), default=0)
            for i, s in enumerate(raw_steps):
                supplement_steps.append(PlanStep(
                    id=max_id + i + 1,
                    tool=s.get("tool", ""),
                    args=s.get("args", {}),
                    intent=s.get("intent", "补充数据"),
                    depends_on=[],
                ))

            if not supplement_steps:
                return None

            logger.info(f"[规划分析] 执行补充调用: {len(supplement_steps)} 个步骤")
            supplement_plan = AnalysisPlan(
                question=question,
                steps=supplement_steps,
            )
            executor = PlanExecutor()
            results = await executor.execute(
                supplement_plan,
                on_step_completed=lambda sr: tools_used.append(sr.tool),
            )
            return results

        except Exception as e:
            logger.warning(f"[规划分析] 补充调用失败: {e}")
            return None

    async def _react_fallback(
        self,
        question: str,
        conversation_id: Optional[str] = None,
    ) -> PlannedAnalysisResult:
        """第三级回退：使用现有 ReAct 模式"""
        logger.info("[规划分析] 回退到 ReAct 模式")
        react_service = IntelligentAssistantService(
            self._db,
            preferred_models=self._get_react_preferred_models(),
        )
        result = await react_service.chat(question, conversation_id)
        return PlannedAnalysisResult(
            reply=result.get("reply", ""),
            tools_used=result.get("tools_used", []),
            source=PlanSource.REACT_FALLBACK,
        )

    async def _get_context_messages(
        self,
        user_id: Optional[str] = None,
        conversation_id: Optional[str] = None,
    ) -> Optional[List[Message]]:
        """获取最近的会话历史作为上下文"""
        if not user_id:
            return None

        try:
            raw_messages = await get_assistant_conversation(
                self._db,
                user_id,
                conversation_id,
            )
            if not raw_messages:
                return None

            recent = raw_messages[-MAX_CONTEXT_MESSAGES:]
            messages = []
            for m in recent:
                role = MessageRole.USER if m["role"] == "user" else MessageRole.ASSISTANT
                content = m.get("content", "")
                if content:
                    # 截断过长的历史消息
                    messages.append(Message(
                        role=role,
                        content=content[:500],
                    ))
            return messages if messages else None

        except Exception as e:
            logger.warning(f"[规划分析] 获取会话历史失败: {e}")
            return None


async def stream_planned_analysis_with_assistant(
    db,
    user_message: str,
    user_id: str,
    conversation_id: Optional[str] = None,
    model: Optional[str] = None,
    model_config_id: Optional[str] = None,
    quick_model: Optional[str] = None,
    quick_model_config_id: Optional[str] = None,
    deep_model: Optional[str] = None,
    deep_model_config_id: Optional[str] = None,
) -> AsyncGenerator[str, None]:
    """对外提供带持久化的规划分析流式接口。"""
    service = PlannedAnalysisService(
        db,
        preferred_models=_build_assistant_model_preferences(
            model=model,
            model_config_id=model_config_id,
            quick_model=quick_model,
            quick_model_config_id=quick_model_config_id,
            deep_model=deep_model,
            deep_model_config_id=deep_model_config_id,
        ),
    )

    collected_reply = ""
    collected_tools: List[str] = []
    collected_plan: Optional[Dict[str, Any]] = None
    collected_step_results: List[Dict[str, Any]] = []
    source = PlanSource.LLM_PLAN.value
    supplemented = False

    async for event_str in service.analyze_stream(
        question=user_message.strip(),
        user_id=user_id,
        conversation_id=conversation_id,
    ):
        if event_str.startswith("event: done\n"):
            try:
                data_line = event_str.split("\ndata: ", 1)[1].rstrip("\n")
                data = json.loads(data_line)
                collected_tools = data.get("tools_used", [])
                collected_reply = data.get("reply", collected_reply)
                collected_plan = data.get("plan")
                collected_step_results = data.get("step_results", [])
                source = data.get("source", source)
                supplemented = data.get("supplemented", supplemented)
            except Exception:
                pass
            continue
        if event_str.startswith("event: token\n"):
            try:
                data_line = event_str.split("\ndata: ", 1)[1].rstrip("\n")
                data = json.loads(data_line)
                collected_reply += data.get("content", "")
            except Exception:
                pass
        elif event_str.startswith("event: plan_ready\n"):
            try:
                data_line = event_str.split("\ndata: ", 1)[1].rstrip("\n")
                data = json.loads(data_line)
                collected_plan = data.get("plan")
                source = data.get("source", source)
            except Exception:
                pass
        elif event_str.startswith("event: mode_switch\n"):
            try:
                data_line = event_str.split("\ndata: ", 1)[1].rstrip("\n")
                data = json.loads(data_line)
                source = data.get("source", source)
            except Exception:
                pass
        elif event_str.startswith("event: step_completed\n"):
            try:
                data_line = event_str.split("\ndata: ", 1)[1].rstrip("\n")
                data = json.loads(data_line)
                step_result = data.get("step_result")
                if step_result:
                    collected_step_results.append(step_result)
            except Exception:
                pass
        yield event_str

    if user_id and collected_reply:
        try:
            await save_assistant_message(
                db,
                user_id=user_id,
                user_content=user_message.strip(),
                assistant_content=collected_reply,
                tools_used=collected_tools,
                conversation_id=conversation_id,
            )
        except Exception as e:
            logger.warning("[规划分析·流式] 保存会话失败: %s", e)

        asyncio.create_task(
            _store_planned_analysis_memory(
                db,
                user_id,
                conversation_id or "",
                user_message.strip(),
                collected_reply,
                collected_tools,
                source,
            )
        )

    conv_id = conversation_id
    if user_id:
        thread = await get_or_create_assistant_thread(db, user_id, conversation_id)
        conv_id = thread["thread_id"]

    yield _sse(
        "done",
        {
            "reply": collected_reply,
            "tools_used": collected_tools,
            "conversation_id": conv_id,
            "plan": collected_plan,
            "step_results": collected_step_results,
            "source": source,
            "supplemented": supplemented,
        },
    )

