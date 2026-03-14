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
from typing import Any, Dict, List, Optional

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
    _get_system_prompt,
    _get_latest_trade_date,
    get_assistant_conversation,
    IntelligentAssistantService,
)

logger = logging.getLogger(__name__)


# ============================================================
# 不支持品种检测
# ============================================================

# ETF / 基金关键词（已支持 ETF 分析，不再阻止）
# 注意：ETF 分析已支持，仅保留用于可能的差异化提示
_ETF_FUND_KEYWORDS = []  # 清空，不再阻止 ETF 相关提问

# 港股关键词
_HK_STOCK_KEYWORDS = [
    "港股", "恒生", "恒指", "H股", "h股", "港交所", "港币",
    "腾讯控股", "美团", "小米集团", "阿里巴巴-SW", "京东集团-SW",
]

# 美股关键词
_US_STOCK_KEYWORDS = [
    "美股", "纳斯达克", "标普", "道琼斯", "NYSE", "NASDAQ",
    "苹果公司", "特斯拉", "英伟达", "谷歌", "亚马逊", "微软",
    "中概股",
]

# 港股/美股代码模式
_HK_CODE_PATTERN = re.compile(r'\b\d{5}\.HK\b', re.IGNORECASE)
_US_CODE_PATTERN = re.compile(r'\b[A-Z]{1,5}\b')  # 简单匹配，需配合关键词
_US_TICKER_PATTERN = re.compile(r'(?<![A-Za-z])(AAPL|TSLA|NVDA|GOOGL|GOOG|AMZN|MSFT|META|NFLX|AMD|BABA|JD|PDD|NIO|XPEV|LI)(?![A-Za-z])', re.IGNORECASE)


def _check_unsupported_asset(question: str) -> Optional[str]:
    """
    检测用户问题是否涉及不支持的品种类型。

    Returns:
        如果检测到不支持的品种，返回提示信息；否则返回 None。
    """
    q = question.strip()

    # 检测 ETF / 基金（已支持，不再阻止）
    # for kw in _ETF_FUND_KEYWORDS:
    #     if kw in q:
    #         return "暂不支持..."  # 已移除

    # 检测港股
    for kw in _HK_STOCK_KEYWORDS:
        if kw in q:
            return (
                "🚫 **暂不支持港股分析**\n\n"
                "当前系统专注于 **A股市场**（沪深两市），港股分析功能尚在开发中。\n\n"
                "您可以尝试：\n"
                "- 分析 A 股个股（如「帮我分析比亚迪」）\n"
                "- 分析行业板块（如「新能源汽车板块怎么样」）"
            )

    # 检测美股
    for kw in _US_STOCK_KEYWORDS:
        if kw in q:
            return (
                "🚫 **暂不支持美股分析**\n\n"
                "当前系统专注于 **A股市场**（沪深两市），美股分析功能尚在开发中。\n\n"
                "您可以尝试：\n"
                "- 分析 A 股个股（如「帮我分析宁德时代」）\n"
                "- 分析行业板块（如「半导体板块最近走势如何」）"
            )

    # 检测美股代码
    if _US_TICKER_PATTERN.search(q):
        return (
            "🚫 **暂不支持美股分析**\n\n"
            "检测到您输入了美股代码。当前系统专注于 **A股市场**（沪深两市）。\n\n"
            "您可以尝试输入 A 股代码（如 600519、000858）或股票名称进行分析。"
        )

    # 检测港股代码
    if _HK_CODE_PATTERN.search(q):
        return (
            "🚫 **暂不支持港股分析**\n\n"
            "检测到您输入了港股代码。当前系统专注于 **A股市场**（沪深两市）。\n\n"
            "您可以尝试输入 A 股代码（如 600519、000858）或股票名称进行分析。"
        )

    return None

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

    def __init__(self, db):
        self._db = db
        self._llm_client: Optional[UnifiedLLMClient] = None
        self._tool_functions: Optional[Dict[str, Any]] = None
        self._openai_tools: Optional[List[Dict[str, Any]]] = None

    async def _ensure_client(self) -> bool:
        """确保 LLM 客户端和工具已加载"""
        if self._llm_client is not None:
            return True

        llm_config = await _get_assistant_llm_config(self._db)
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
                source=PlanSource.SEED,
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
        react_service = IntelligentAssistantService(self._db)
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

