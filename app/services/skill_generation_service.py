"""
Skill 生成服务 — 业务逻辑层

封装 core/tools/external/ 的各模块，处理 MongoDB 持久化和异步编排。
"""

import asyncio
import json
import logging
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from core.llm import Message
from motor.motor_asyncio import AsyncIOMotorDatabase

from core.tools.external import (
    ConversationRound,
    DefaultReconnaissanceController,
    ExpectedOutput,
    ImplementationFactReport,
    IterationController,
    RequirementAnalyzer,
    SkillCreationSession,
    SkillHandoffContext,
    SkillParameter,
    SkillSpec,
    SessionStatus,
    PipelineResult,
)
from core.tools.external.requirement_analyzer import classify_requirement_mode

logger = logging.getLogger("webapi")

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SKILL_CODE_SNAPSHOT_DIR = PROJECT_ROOT / "data" / "code" / "skill"

# MongoDB 集合名
SESSION_COLLECTION = "skill_creation_sessions"
SKILL_COLLECTION = "external_skills"
# 与 iteration_controller.MAX_ITERATIONS 保持一致；如需调整请同步修改
SKILL_PIPELINE_MAX_ITERATIONS = 10
SKILL_GENERATION_AGENTIC_ENABLED = os.getenv("SKILL_GENERATION_AGENTIC_ENABLED", "true").lower() not in {"0", "false", "no", "off"}


class SkillGenerationService:
    """
    Skill 生成服务

    提供需求沟通、代码生成、Skill 管理的完整业务逻辑。
    """

    def __init__(
        self,
        db: AsyncIOMotorDatabase,
        reasoning_llm_client=None,
        coding_llm_client=None,
        quick_llm_client=None,
        provider: str = "deepseek",
        model: Optional[str] = None,
    ):
        """
        Args:
            db: MongoDB 数据库
            reasoning_llm_client: 需求分析用（深度推理大模型），规格生成等重推理环节
            coding_llm_client: 代码生成用（编程大模型），生成代码、Judge 评分
            quick_llm_client: 需求对话用（快速模型），清晰度/边界/多轮回复等低延迟环节
            provider, model: 回退用，当上述客户端均为空时使用
        """
        self._db = db
        self._provider = provider
        self._model = model
        self._analyzer = RequirementAnalyzer(
            llm_client=reasoning_llm_client,
            provider=provider,
            model=model,
            quick_llm_client=quick_llm_client,
        )
        self._reconnaissance = DefaultReconnaissanceController(
            llm_client=coding_llm_client, provider=provider, model=model,
            analyzer=self._analyzer,
        )
        self._controller = IterationController(
            llm_client=coding_llm_client,
            provider=provider,
            model=model,
            max_iterations=SKILL_PIPELINE_MAX_ITERATIONS,
            reconnaissance_controller=self._reconnaissance,
            quick_llm_client=quick_llm_client,
        )

    def _build_session_recommendations(
        self,
        *,
        spec: Optional[SkillSpec] = None,
        session: Optional[SkillCreationSession] = None,
        fact_report: Optional[Any] = None,
    ) -> Dict[str, Any]:
        if spec is not None:
            return self._analyzer.build_recommendations(spec=spec, fact_report=fact_report)
        conversation = ""
        if session is not None:
            conversation = self._analyzer._collect_conversation(session)
        return self._analyzer.build_recommendations(conversation=conversation, fact_report=fact_report)

    @staticmethod
    def _dedupe_text_list(items: Any) -> List[str]:
        result: List[str] = []
        seen: set[str] = set()
        if not isinstance(items, list):
            return result
        for item in items:
            value = str(item or "").strip()
            if not value:
                continue
            key = value.lower()
            if key in seen:
                continue
            seen.add(key)
            result.append(value)
        return result

    async def _search_capability_index(self, spec: SkillSpec) -> list:
        """从能力索引（Qdrant 向量库）中搜索与 spec 语义相关的工具。

        使用 spec 的 display_name + description 构造查询，召回 top_k=12 的相关工具。
        如果能力索引服务不可用，返回空列表（不阻塞流程）。
        """
        try:
            from app.services.capability_index_service import CapabilityIndexService
            # 构造语义查询文本
            query_parts = [
                spec.display_name or "",
                spec.description or "",
                spec.category or "",
            ]
            # 加入参数描述，让搜索更精准
            for param in (spec.parameters or []):
                desc = getattr(param, "description", None) or (param.get("description") if isinstance(param, dict) else None)
                if desc:
                    query_parts.append(desc)
            query = " ".join(p for p in query_parts if p).strip()
            if not query:
                return []

            svc = CapabilityIndexService(self._db)
            hits = await svc.search_capabilities(
                query=query,
                top_k=12,
                bindable_only=True,
                source_types=["builtin_tool", "mcp_tool"],
            )
            logger.info(
                "🧭 能力索引向量搜索: query='%s...' → %d 个命中",
                query[:40],
                len(hits),
            )
            return hits
        except Exception as exc:
            logger.warning("⚠️ 能力索引搜索失败（不阻塞流程）: %s", exc)
            return []

    @staticmethod
    def _infer_skill_role_metadata(spec: SkillSpec, session: SkillCreationSession) -> Dict[str, Any]:
        text = " ".join([
            spec.tool_id or "",
            spec.display_name or "",
            spec.description or "",
            spec.category or "",
            spec.data_source or "",
            " ".join(spec.constraints or []),
            " ".join(spec.expected_output.fields or []),
            spec.expected_output.description or "",
            str((spec.metadata or {}).get("handoff_context_summary") or ""),
            str((spec.metadata or {}).get("generation_context") or ""),
        ]).lower()
        handoff = session.handoff_context
        source = str(getattr(handoff, "source", "") or "") if handoff is not None else ""
        source_capability = str(getattr(handoff, "target_capability", "") or "") if handoff is not None else ""
        if source_capability:
            text += " " + source_capability.lower()

        capability_tags: List[str] = []
        tag_patterns = [
            (r"现金流|cash\s*flow|cashflow|ocf|fcf|cfo|自由现金流", "cashflow_quality"),
            (r"财务健康|偿债|负债|debt|solvency|liquidity|current_ratio|interest_coverage", "financial_health"),
            (r"风险|risk|预警|异常|商誉|应收|goodwill|receivable", "financial_risk"),
            (r"估值|valuation|pe|pb|percentile|分位|dcf|peg", "valuation"),
            (r"趋势|trend|series|历史|多年|time_series", "historical_series"),
            (r"质量|quality|roe|roa|roic|piotroski|altman|beneish", "quality_factor"),
            (r"技术|technical|macd|rsi|kdj|ma20", "technical"),
            (r"新闻|news|舆情|sentiment", "news_sentiment"),
        ]
        for pattern, tag in tag_patterns:
            if re.search(pattern, text):
                capability_tags.append(tag)

        output_fields = [str(item or "").lower() for item in (spec.expected_output.fields or [])]
        output_type = str(spec.expected_output.type or "").lower()
        if output_type in {"dict", "list[dict]", "list"} and output_fields:
            if any(re.search(r"ratio|rate|score|metrics?|指标|比率|分数|flag", field) for field in output_fields):
                output_shape = "structured_metrics"
            else:
                output_shape = "structured_records"
        elif "markdown" in text or "报告" in text or "report" in text:
            output_shape = "report"
        else:
            output_shape = "structured_records" if output_fields else "text"

        preferred_for: List[str] = []
        if "financial_risk" in capability_tags:
            preferred_for.append("financial_risk_signal_detection")
        if "cashflow_quality" in capability_tags:
            preferred_for.append("cashflow_quality_analysis")
        if "financial_health" in capability_tags:
            preferred_for.append("financial_health_analysis")
        if "valuation" in capability_tags:
            preferred_for.append("valuation_analysis")
        if "historical_series" in capability_tags:
            preferred_for.append("historical_trend_analysis")

        if source in {"agent_studio_gap", "agent_workshop_gap"}:
            tool_role_hint = "specialized"
        elif output_shape == "report":
            tool_role_hint = "supporting"
        elif len(preferred_for) == 1:
            tool_role_hint = "specialized"
        elif preferred_for:
            tool_role_hint = "specialized"
        else:
            tool_role_hint = "supporting"

        not_replacement_for: List[str] = []
        if tool_role_hint in {"supporting", "generic", "fallback"}:
            not_replacement_for.extend(preferred_for)
        if output_shape == "report":
            not_replacement_for.extend(["structured_metric_calculation", "primary_capability"])

        return {
            "capability_tags": SkillGenerationService._dedupe_text_list(capability_tags),
            "tool_role_hint": tool_role_hint,
            "output_shape": output_shape,
            "preferred_for": SkillGenerationService._dedupe_text_list(preferred_for),
            "not_replacement_for": SkillGenerationService._dedupe_text_list(not_replacement_for),
        }

    @staticmethod
    def _get_last_generated_code(pipeline_result: Optional[PipelineResult]) -> str:
        if not pipeline_result:
            return ""
        if pipeline_result.final_code:
            return pipeline_result.final_code
        for iteration in reversed(pipeline_result.iterations or []):
            generated = iteration.generated_code
            if generated and generated.code:
                return generated.code
        return ""

    @staticmethod
    def _persist_generated_code_snapshots(
        *,
        session_id: str,
        tool_id: str,
        attempt_number: int,
        pipeline_result: Optional[PipelineResult],
    ) -> List[Path]:
        if not pipeline_result:
            return []

        session_dir = SKILL_CODE_SNAPSHOT_DIR / tool_id / session_id
        attempt_dir = session_dir / f"attempt_{attempt_number:02d}"
        attempt_dir.mkdir(parents=True, exist_ok=True)

        written_files: List[Path] = []

        for iteration in pipeline_result.iterations or []:
            generated = iteration.generated_code
            code = (generated.code if generated and generated.code else "").strip()
            if not code:
                continue

            round_path = attempt_dir / f"round_{iteration.round_number:02d}.py"
            round_path.write_text(code + "\n", encoding="utf-8")
            written_files.append(round_path)

        latest_code = SkillGenerationService._get_last_generated_code(pipeline_result).strip()
        if latest_code:
            attempt_latest_path = attempt_dir / "latest.py"
            attempt_latest_path.write_text(latest_code + "\n", encoding="utf-8")
            written_files.append(attempt_latest_path)

            session_latest_path = session_dir / "latest.py"
            session_latest_path.write_text(latest_code + "\n", encoding="utf-8")
            written_files.append(session_latest_path)

        return written_files

    @staticmethod
    def _summarize_text(
        text: Any,
        *,
        max_chars: int,
        head_chars: Optional[int] = None,
        separator: str = "\n... (中间省略) ...\n",
    ) -> str:
        """长文本摘要默认保留首尾，避免只看到前半段导致误判。"""
        if text is None:
            return ""

        text_str = str(text)
        if len(text_str) <= max_chars:
            return text_str

        if head_chars is None:
            head_chars = max_chars // 2

        head_chars = max(1, min(head_chars, max_chars - len(separator) - 1))
        tail_chars = max_chars - head_chars - len(separator)
        if tail_chars <= 0:
            return text_str[:max_chars]

        return text_str[:head_chars] + separator + text_str[-tail_chars:]

    @staticmethod
    def _format_single_pipeline(
        pipeline_result: PipelineResult,
        label: str = "",
        compact: bool = False,
    ) -> List[str]:
        """
        将单次管线结果格式化为结构化文本行列表。

        Args:
            compact: True 时只保留根因分析和评分，省略 stdout/stderr/feedback
                     等大体积字段，用于压缩历史管线。
        """
        parts: List[str] = []
        if label:
            parts.append(f"\n{'='*20} {label} {'='*20}")
        if pipeline_result.error:
            parts.append(f"最终结论：{pipeline_result.error}")

        for iteration in pipeline_result.iterations or []:
            parts.append(f"\n[第{iteration.round_number}轮 | 决策={iteration.decision or 'UNKNOWN'}]")

            if iteration.validation and iteration.validation.errors:
                parts.append("静态验证问题：")
                parts.extend(f"- {item}" for item in iteration.validation.errors[:3])

            if iteration.sandbox and not iteration.sandbox.success:
                parts.append(f"沙箱执行失败：{iteration.sandbox.error or '未知错误'}")

            if not compact and iteration.sandbox and iteration.sandbox.success and iteration.sandbox.output is not None:
                import json as _json
                try:
                    out_str = SkillGenerationService._summarize_text(
                        _json.dumps(iteration.sandbox.output, ensure_ascii=False, default=str),
                        max_chars=1200,
                        head_chars=700,
                    )
                except Exception:
                    out_str = SkillGenerationService._summarize_text(
                        iteration.sandbox.output,
                        max_chars=1200,
                        head_chars=700,
                    )
                parts.append(f"沙箱返回值（摘要）：{out_str}")

            if iteration.eval_score:
                parts.append(
                    "评估分数："
                    f"total={iteration.eval_score.total}, "
                    f"executability={iteration.eval_score.executability}, "
                    f"authenticity={iteration.eval_score.authenticity}, "
                    f"completeness={iteration.eval_score.completeness}, "
                    f"relevance={iteration.eval_score.relevance}, "
                    f"format_quality={iteration.eval_score.format_quality}"
                )

            if iteration.reflection and iteration.reflection.root_cause:
                parts.append(f"根因分析：{iteration.reflection.root_cause}")
                if iteration.reflection.fix_plan:
                    parts.append("修复计划：" + " → ".join(iteration.reflection.fix_plan[:5]))

            if not compact and iteration.feedback:
                feedback_excerpt = SkillGenerationService._summarize_text(
                    iteration.feedback,
                    max_chars=1200,
                    head_chars=700,
                )
                parts.append(f"系统反馈（摘要）：{feedback_excerpt}")

        return parts

    @staticmethod
    def _extract_lessons(results: List[PipelineResult]) -> List[str]:
        """从管线结果列表中提取去重的关键教训。"""
        lessons: List[str] = []
        for pr in results:
            for it in pr.iterations or []:
                if it.reflection and it.reflection.root_cause:
                    lessons.append(it.reflection.root_cause)
        return list(dict.fromkeys(lessons))[:15]

    @staticmethod
    def _build_pipeline_failure_feedback(
        pipeline_result: Optional[PipelineResult],
        user_feedback: str = "",
    ) -> str:
        if not pipeline_result:
            return user_feedback.strip()

        parts: List[str] = ["=== 上一轮管线失败信息 ==="]
        parts.extend(
            SkillGenerationService._format_single_pipeline(pipeline_result, compact=False)
        )

        if user_feedback.strip():
            parts.append(f"\n=== 用户补充修正意见 ===\n{user_feedback.strip()}")

        return "\n".join(parts)

    # 经验反馈的 token 预算（按 1 中文字 ≈ 2 token 估算，8K token ≈ 4K 字符）
    _EXPERIENCE_CHAR_BUDGET = 6000

    @staticmethod
    def _build_accumulated_experience(
        pipeline_history: List[PipelineResult],
        current_pipeline: Optional[PipelineResult],
        user_feedback: str = "",
    ) -> str:
        """
        构建累积经验反馈 — 渐进式压缩策略：

        1. 最近一次管线：完整详情（stdout/返回值/反馈）
        2. 更早的管线：仅保留根因分析和评分（compact 模式）
        3. 全量教训去重汇总
        4. 如果仍然超预算，从最早的历史开始裁剪
        """
        history = list(pipeline_history or [])
        all_results = list(history)
        if current_pipeline is not None:
            all_results.append(current_pipeline)

        if not all_results:
            return user_feedback.strip()

        budget = SkillGenerationService._EXPERIENCE_CHAR_BUDGET
        parts: List[str] = [
            f"=== 累积生成经验（共 {len(all_results)} 次尝试）===",
            "请从历史教训中吸取经验，避免重复犯错。\n",
        ]

        # ---- 关键教训汇总（始终保留，最高优先级）----
        lessons = SkillGenerationService._extract_lessons(all_results)
        if lessons:
            parts.append(f"=== 关键教训总结（{len(lessons)} 条，必须遵守）===")
            for i, lesson in enumerate(lessons, 1):
                parts.append(f"{i}. {lesson}")
            parts.append("")

        # ---- 最近一次管线：完整详情 ----
        latest = all_results[-1]
        success_label = "✅ 成功" if latest.success else "❌ 失败"
        latest_label = f"最近一次尝试（第 {len(all_results)} 次, {latest.total_rounds} 轮, {latest.total_time}s, {success_label}）"
        latest_lines = SkillGenerationService._format_single_pipeline(latest, latest_label, compact=False)
        parts.extend(latest_lines)

        # ---- 更早的管线：compact 模式，从最近往最早填充 ----
        older = all_results[:-1]
        if older:
            parts.append(f"\n=== 更早的 {len(older)} 次尝试（摘要）===")

            current_len = sum(len(p) for p in parts)
            remaining = budget - current_len - 300  # 预留尾部空间

            included = 0
            for pr in reversed(older):
                idx = older.index(pr) + 1
                s_label = "✅" if pr.success else "❌"
                pr_label = f"第 {idx} 次（{pr.total_rounds} 轮, {s_label}）"
                pr_lines = SkillGenerationService._format_single_pipeline(pr, pr_label, compact=True)
                block = "\n".join(pr_lines)
                if current_len + len(block) > remaining and included > 0:
                    parts.append(f"（更早的 {len(older) - included} 次尝试因篇幅省略，教训已汇总在上方）")
                    break
                parts.extend(pr_lines)
                current_len += len(block)
                included += 1

        if user_feedback.strip():
            parts.append(f"\n=== 用户本轮补充意见 ===\n{user_feedback.strip()}")

        parts.append("\n=== 要求 ===")
        parts.append("请结合以上教训，避免重复之前的错误，定向修复并生成高质量代码。")

        return "\n".join(parts)

    @staticmethod
    def _build_repair_plan_fallback(
        spec: SkillSpec,
        feedback: str,
        pipeline_feedback: str,
    ) -> str:
        return "\n".join([
            "## 我理解到的问题",
            f"- 当前 Skill 的目标仍然是：{spec.description}",
            f"- 你强调的新问题是：{feedback.strip() or '请按失败信息修正'}",
            "- 我会优先修复静态校验、沙箱执行和评分阶段已经暴露出的确定性错误，不会改动已确认的需求边界。",
            "",
            "## 修正计划",
            "1. 先根据上一轮失败信息定位最先导致失败的根因，优先消除阻断执行的问题。",
            "2. 保留现有 Skill 规格和目标输出，避免把修正过程扩展成新的需求。",
            "3. 基于上一轮代码定向修改，而不是重新从零生成。",
            "4. 对关键输入、关键数据缺失场景显式返回 error / invalid，避免用伪造默认值继续输出。",
            "5. 修正后重新通过静态校验、沙箱执行和质量评估。",
            "",
            "## 重新生成时的重点检查项",
            pipeline_feedback.strip() or "- 以上一轮失败会话的静态验证、沙箱和评估错误为主进行逐项修复。",
            "",
            "如果这份计划没有偏差，你再确认让我按这个计划重新生成。",
        ])

    def _generate_repair_plan_message(
        self,
        session: SkillCreationSession,
        feedback: str,
    ) -> Tuple[str, Optional[Any]]:
        """
        生成修正计划消息。

        Returns:
            (ai_message, llm_response) — llm_response 可能为 None（无规格或回退方案）。
            llm_response 供异步调用方记录 token 使用，避免在同步上下文中调用异步方法。
        """
        spec = session.spec
        if not spec:
            return "当前会话还没有可用的 Skill 规格，无法生成修正计划。", None

        accumulated_exp = self._build_accumulated_experience(
            pipeline_history=session.pipeline_history,
            current_pipeline=session.pipeline_result,
            user_feedback=feedback,
        )
        pipeline_feedback = self._build_pipeline_failure_feedback(
            session.pipeline_result,
            feedback,
        )
        last_code = self._get_last_generated_code(session.pipeline_result)
        code_excerpt = self._summarize_text(
            last_code,
            max_chars=12000,
            head_chars=7000,
        )
        attempt_count = len(session.pipeline_history) + (1 if session.pipeline_result else 0)
        prompt = f"""
你现在是 Skill 生成失败后的修正协作者。该 Skill 已经经过 {attempt_count} 次生成尝试，均未达标。
先不要输出代码，而是先向用户说明：
1. 从所有历史尝试中你总结出的关键问题是什么
2. 你准备怎么修（避免重复之前犯过的错误）
3. 重新生成时会重点检查什么

请严格遵守：
- 不要重新定义需求，不要扩展到新的功能范围
- 不要输出完整代码
- 不要承诺无法验证的内容
- 用中文回答
- 输出结构固定为：
  ## 历史尝试中的关键问题
  ## 修正计划
  ## 重新生成时的重点检查项

=== 当前 Skill 规格 ===
tool_id: {spec.tool_id}
display_name: {spec.display_name}
description: {spec.description}
category: {spec.category}
data_source: {spec.data_source}
test_input: {spec.test_input}

=== 累积经验（共 {attempt_count} 次尝试）===
{accumulated_exp}

=== 最近一次生成的代码（摘要，保留首尾） ===
{code_excerpt or '无'}

请给出一份让用户可以确认的修正计划。
""".strip()

        try:
            client = self._analyzer._get_client()
            response = client.chat([Message(role="user", content=prompt)])
            content = (getattr(response, "content", "") or "").strip()
            if content:
                return content, response
        except Exception as e:
            logger.warning(f"生成修正计划失败，使用回退方案: {e}")

        return self._build_repair_plan_fallback(spec, feedback, pipeline_feedback), None

    async def _launch_pipeline_task(
        self,
        *,
        session: SkillCreationSession,
        spec: SkillSpec,
        initial_feedback: str = "",
        initial_code: str = "",
        fact_report: Optional[ImplementationFactReport] = None,
        codegen_timeout: Optional[int] = None,
        iteration_mode: str = "repair",
    ) -> Dict[str, Any]:
        # 代码生成单次调用超时（秒）：None 用管线默认值；仅接受 60~1800 的整数
        if isinstance(codegen_timeout, bool) or not isinstance(codegen_timeout, int):
            codegen_timeout = None
        elif not (60 <= codegen_timeout <= 1800):
            codegen_timeout = None

        # external_api 模式：把接口预检实测事实（连通性/真实字段/实测查询参数）注入
        # spec.metadata，代码生成 prompt 据此构造【接口实测事实】区块——
        # LLM 不再臆造返回字段，也不再把业务过滤参数（如 brand）拼进 URL
        try:
            if classify_requirement_mode(spec) == "external_api":
                sess_doc = await self._db[SESSION_COLLECTION].find_one(
                    {"session_id": session.session_id}, {"interface_preflight": 1}
                )
                preflight = (sess_doc or {}).get("interface_preflight")
                if preflight:
                    metadata = dict(getattr(spec, "metadata", None) or {})
                    metadata["interface_preflight"] = preflight
                    spec.metadata = metadata
                    logger.info(
                        "[Preflight] 接口实测事实已注入代码生成: status=%s data_items=%s fields=%s probed_params=%s",
                        preflight.get("status"),
                        preflight.get("data_items"),
                        preflight.get("sample_fields"),
                        list((preflight.get("probed_params") or {}).keys()),
                    )
        except Exception as exc:
            logger.debug("[Preflight] 实测事实注入代码生成失败（已忽略）: %s", exc)

        session.status = SessionStatus.GENERATING
        if session.pipeline_result is not None:
            session.pipeline_history.append(session.pipeline_result)
        session.pipeline_result = None
        attempt_number = len(session.pipeline_history) + 1
        await self._save_session(session)
        await self._db[SESSION_COLLECTION].update_one(
            {"session_id": session.session_id},
            {
                "$set": {
                    "pipeline_stage": "code_generation",
                    "pipeline_message": "准备开始生成...",
                    "pipeline_iteration": 0,
                    "pipeline_progress": 0,
                    "pipeline_thinking": "",
                    "pipeline_eval_result": None,
                    "pipeline_details": [],
                    "updated_at": datetime.utcnow(),
                }
            },
        )

        from app.core.database import get_mongo_db_sync
        sync_db = get_mongo_db_sync()
        session_id = session.session_id

        def _progress_cb(stage: str, message: str, iteration: int, progress: float,
                         extra: Optional[Dict[str, Any]] = None):
            try:
                detail_event: Dict[str, Any] = {
                    "stage": stage,
                    "message": message,
                    "iteration": iteration,
                    "progress": progress,
                    "timestamp": datetime.utcnow(),
                }
                set_fields: Dict[str, Any] = {
                    "pipeline_stage": stage,
                    "pipeline_message": message,
                    "pipeline_iteration": iteration,
                    "pipeline_progress": progress,
                    "updated_at": datetime.utcnow(),
                }
                # 质量评估完成：结构化结果实时落库，前端轮询即可看到分数/评语
                eval_result = (extra or {}).get("eval_result")
                if eval_result:
                    detail_event["eval_result"] = eval_result
                    set_fields["pipeline_eval_result"] = eval_result

                sync_db[SESSION_COLLECTION].update_one(
                    {"session_id": session_id},
                    {
                        "$set": set_fields,
                        "$push": {
                            "pipeline_details": {
                                "$each": [detail_event],
                                "$slice": -30,
                            }
                        },
                    },
                )
            except Exception as e:
                logger.warning(f"更新 pipeline 进度失败: {e}")

        # 思考过程实时展示：缓冲 reasoning 增量，节流写入会话文档（前端轮询读取）
        thinking_state = {"buf": "", "last_flush": 0.0}
        THINKING_FLUSH_INTERVAL = 1.5   # 秒
        THINKING_DOC_TAIL = 6000        # 文档中仅保留尾部，防止无限增长

        def _flush_thinking() -> None:
            try:
                sync_db[SESSION_COLLECTION].update_one(
                    {"session_id": session_id},
                    {"$set": {
                        "pipeline_thinking": thinking_state["buf"][-THINKING_DOC_TAIL:],
                        "updated_at": datetime.utcnow(),
                    }},
                )
            except Exception as e:
                logger.warning(f"写入 pipeline_thinking 失败: {e}")

        def _thinking_cb(kind: str, text: str):
            try:
                import time as _time
                if kind == "reset":
                    thinking_state["buf"] = ""
                    thinking_state["last_flush"] = _time.time()
                    _flush_thinking()
                    return
                if kind != "reasoning" or not text:
                    return
                thinking_state["buf"] = (thinking_state["buf"] + text)[-THINKING_DOC_TAIL * 2:]
                now = _time.time()
                if now - thinking_state["last_flush"] >= THINKING_FLUSH_INTERVAL:
                    thinking_state["last_flush"] = now
                    _flush_thinking()
            except Exception as e:
                logger.warning(f"更新 pipeline_thinking 失败: {e}")

        async def _run_pipeline():
            try:
                # mem0: 召回同类 Skill 的历史教训，注入到 initial_feedback
                enriched_feedback = initial_feedback
                try:
                    mem0_lessons = await _recall_skill_lessons(self._db, spec)
                    if mem0_lessons:
                        enriched_feedback = (
                            f"{mem0_lessons}\n\n{initial_feedback}" if initial_feedback
                            else mem0_lessons
                        )
                        metadata = dict(getattr(spec, "metadata", None) or {})
                        metadata["cross_session_skill_lessons"] = mem0_lessons[:2000]
                        spec.metadata = metadata
                except Exception as e:
                    logger.debug("[mem0] Skill 教训召回失败（已忽略）: %s", e)

                # 捕获 fact_report 到局部变量，避免 lambda 闭包问题
                _fr = fact_report
                method_name = "run_agentic" if SKILL_GENERATION_AGENTIC_ENABLED else "run"
                logger.info("Skill 生成引擎: %s", method_name)
                result = await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: getattr(self._controller, method_name)(
                        spec,
                        initial_feedback=enriched_feedback,
                        initial_code=initial_code,
                        progress_callback=_progress_cb,
                        fact_report=_fr,
                        codegen_timeout=codegen_timeout,
                        thinking_callback=_thinking_cb,
                        iteration_mode=iteration_mode,
                    ),
                )
                # 流结束后冲刷剩余思考内容，避免尾部丢失
                _flush_thinking()
                session.status = SessionStatus.COMPLETED if result.success else SessionStatus.FAILED
                session.pipeline_result = result
                await self._save_session(session)

                try:
                    written_files = self._persist_generated_code_snapshots(
                        session_id=session.session_id,
                        tool_id=spec.tool_id,
                        attempt_number=attempt_number,
                        pipeline_result=result,
                    )
                    if written_files:
                        logger.info(
                            "📝 Skill 代码快照已保存: %s",
                            str((SKILL_CODE_SNAPSHOT_DIR / spec.tool_id / session.session_id).resolve()),
                        )
                except Exception as e:
                    logger.warning("⚠️ 保存 Skill 代码快照失败: %s", e)

                if result.success:
                    await self._save_skill(session, spec, result)

                # mem0: 将本次迭代教训写入记忆
                try:
                    await _store_skill_lessons(self._db, spec, result)
                except Exception as e:
                    logger.debug("[mem0] Skill 教训存储失败（已忽略）: %s", e)
            except Exception as e:
                logger.error(f"管线执行异常: {e}", exc_info=True)
                await self._db[SESSION_COLLECTION].update_one(
                    {"session_id": session_id},
                    {
                        "$set": {
                            "status": "failed",
                            "pipeline_stage": "error",
                            "pipeline_message": str(e),
                            "updated_at": datetime.utcnow(),
                        },
                        "$push": {
                            "pipeline_details": {
                                "$each": [{
                                    "stage": "error",
                                    "message": str(e),
                                    "iteration": 0,
                                    "progress": 0,
                                    "timestamp": datetime.utcnow(),
                                }],
                                "$slice": -30,
                            }
                        },
                    },
                )

        asyncio.create_task(_run_pipeline())

        return {
            "status": "generating",
            "session_id": session_id,
            "skill_id": None,
            "spec": spec.model_dump() if spec else None,
            "success": False,
            "total_rounds": 0,
            "total_time": 0,
            "final_score": None,
            "error": None,
        }

    @staticmethod
    def _apply_handoff_context_to_spec(spec: SkillSpec, handoff_context: Any) -> None:
        """将上游交接上下文附加到 SkillSpec.metadata，供 Agentic Loop 使用。"""
        if spec is None or handoff_context is None:
            return
        metadata = dict(getattr(spec, "metadata", None) or {})

        def _string_list(field: str, limit: int) -> List[str]:
            return [
                str(item).strip()
                for item in list(getattr(handoff_context, field, None) or [])
                if str(item).strip()
            ][:limit]

        context_summary = {
            "source": str(getattr(handoff_context, "source", "") or ""),
            "source_spec_id": str(getattr(handoff_context, "source_spec_id", "") or getattr(handoff_context, "spec_id", "") or ""),
            "source_name": str(getattr(handoff_context, "source_name", "") or getattr(handoff_context, "agent_name", "") or ""),
            "target_capability": str(getattr(handoff_context, "target_capability", "") or ""),
            "handoff_intent": str(getattr(handoff_context, "handoff_intent", "") or ""),
            "workshop_session_id": str(getattr(handoff_context, "workshop_session_id", "") or ""),
            "gap_id": str(getattr(handoff_context, "gap_id", "") or ""),
            "agent_goal": str(getattr(handoff_context, "agent_goal", "") or ""),
            "gap_context": str(getattr(handoff_context, "gap_context", "") or ""),
            "searched_capabilities": _string_list("searched_capabilities", 12),
            "confirmed_data_sources": _string_list("confirmed_data_sources", 12),
            "user_clarifications": _string_list("user_clarifications", 12),
            "related_gaps": _string_list("related_gaps", 12),
        }
        context_summary = {
            key: value for key, value in context_summary.items()
            if value not in ("", [], None)
        }
        if context_summary:
            metadata["handoff_context_summary"] = context_summary

        failures = _string_list("known_failure_summaries", 5)
        facts = _string_list("known_verified_facts", 12)
        if failures:
            metadata["known_failure_summaries"] = failures
        if facts:
            metadata["known_verified_facts"] = facts
        if context_summary or failures or facts:
            logger.info(
                "[SkillGeneration][HandoffContext] tool_id=%s context_keys=%s known_failures=%s known_facts=%s",
                getattr(spec, "tool_id", ""),
                sorted(context_summary.keys()),
                len(metadata.get("known_failure_summaries") or []),
                len(metadata.get("known_verified_facts") or []),
            )
        spec.metadata = metadata

    @staticmethod
    def _has_generation_context(context: Optional[Dict[str, Any]]) -> bool:
        if not context:
            return False
        return bool(
            context.get("category_hint")
            or context.get("data_source_hint")
            or context.get("stock_collections")
            or context.get("external_sources")
        )

    def _build_spec_from_skill_doc(self, doc: Dict[str, Any]) -> Optional[SkillSpec]:
        try:
            params = [SkillParameter(**p) for p in doc.get("parameters", [])]
            expected_output_data = doc.get("expected_output", {})
            expected_output = ExpectedOutput(**expected_output_data) if expected_output_data else ExpectedOutput()
            return SkillSpec(
                tool_id=doc.get("tool_id", ""),
                display_name=doc.get("display_name", ""),
                description=doc.get("description", ""),
                category=doc.get("category", "other"),
                data_source=doc.get("data_source", ""),
                parameters=params,
                expected_output=expected_output,
                test_input=doc.get("test_input", {}),
            )
        except Exception:
            return None

    async def _hydrate_skill_generation_context(self, doc: Dict[str, Any]) -> Dict[str, Any]:
        context = doc.get("generation_context")
        if self._has_generation_context(context):
            return doc

        metadata = dict(doc.get("metadata") or {})
        metadata_context = metadata.get("generation_context")
        if self._has_generation_context(metadata_context):
            doc["generation_context"] = metadata_context
            return doc

        recommendations: Optional[Dict[str, Any]] = None
        session_id = doc.get("session_id")
        if session_id:
            session = await self._load_session(session_id)
            if session:
                spec = session.spec if isinstance(session.spec, SkillSpec) else None
                recommendations = self._build_session_recommendations(spec=spec, session=session)

        if not self._has_generation_context(recommendations):
            spec = self._build_spec_from_skill_doc(doc)
            if spec is not None:
                recommendations = self._build_session_recommendations(spec=spec)

        if self._has_generation_context(recommendations):
            doc["generation_context"] = recommendations

        return doc

    # ==================== 需求沟通 ====================

    async def start_session(
        self,
        description: str,
        user_id: str = "",
        handoff_context: Optional[Dict[str, Any]] = None,
        iterate_skill_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        开始创建会话：提交初始需求

        Args:
            description: 用户需求描述
            user_id: 用户 ID
            handoff_context: 来自上游工坊的交接上下文
            iterate_skill_id: 迭代模式下的已有 Skill tool_id

        Returns:
            包含 session_id, ai_message, clarity_level 等信息的 dict
        """
        # 创建会话
        context = SkillHandoffContext(**handoff_context) if handoff_context else None
        session = self._analyzer.create_session(
            user_id=user_id, handoff_context=context, iterate_skill_id=iterate_skill_id,
        )

        # 迭代模式：加载已有 Skill 的上下文
        skill_context: Optional[str] = None
        if iterate_skill_id:
            try:
                skill_doc = await self._db[SKILL_COLLECTION].find_one(
                    {"tool_id": iterate_skill_id}
                )
                if skill_doc:
                    skill_doc.pop("_id", None)
                    code = skill_doc.get("code") or skill_doc.get("implementation") or ""
                    skill_context = json.dumps({
                        "tool_id": skill_doc.get("tool_id", ""),
                        "display_name": skill_doc.get("display_name", ""),
                        "description": skill_doc.get("description", ""),
                        "category": skill_doc.get("category", ""),
                        "parameters": skill_doc.get("parameters", []),
                        "status": skill_doc.get("status", ""),
                        "code_abbreviated": code[:1500] + ("..." if len(code) > 1500 else ""),
                    }, ensure_ascii=False, indent=2)
                    logger.info(
                        "[SkillGeneration][Iterate] 加载已有 Skill 上下文: tool_id=%s",
                        iterate_skill_id,
                    )
                else:
                    logger.warning(
                        "[SkillGeneration][Iterate] 未找到 Skill: tool_id=%s",
                        iterate_skill_id,
                    )
            except Exception as exc:
                logger.error("[SkillGeneration][Iterate] 加载 Skill 失败: %s", exc)

        # 处理第一轮输入（会做清晰度评估和边界检测）
        session, ai_message = await asyncio.get_event_loop().run_in_executor(
            None,
            self._analyzer.process_user_input,
            session,
            description,
            skill_context,  # 迭代模式下传入已有 Skill 上下文
        )

        # 持久化到 MongoDB
        session_doc = session.model_dump(mode="json")
        await self._db[SESSION_COLLECTION].insert_one(session_doc)

        max_rounds = self._analyzer._get_max_rounds(session.clarity_level)

        return {
            "session_id": session.session_id,
            "ai_message": ai_message,
            "clarity_level": session.clarity_level.value if session.clarity_level else "medium",
            "boundary_check": session.boundary_check.model_dump() if session.boundary_check else None,
            "current_round": session.current_round,
            "expected_rounds": max_rounds,
        }

    async def respond_to_session(
        self, session_id: str, user_message: str
    ) -> Dict[str, Any]:
        """
        用户回复对话轮次

        Returns:
            包含 ai_message, current_round, is_final_round 等信息的 dict
        """
        # 从 MongoDB 加载会话
        session = await self._load_session(session_id)
        if not session:
            raise ValueError(f"会话 {session_id} 不存在")

        if session.spec_confirmed:
            raise ValueError("规格已确认，无法继续对话")

        # 处理用户输入
        session, ai_message = await asyncio.get_event_loop().run_in_executor(
            None, self._analyzer.process_user_input, session, user_message
        )

        # 更新 MongoDB
        await self._save_session(session)

        max_rounds = self._analyzer._get_max_rounds(session.clarity_level)

        return {
            "session_id": session.session_id,
            "ai_message": ai_message,
            "current_round": session.current_round,
            "expected_rounds": max_rounds,
            "is_final_round": session.current_round >= max_rounds,
            "boundary_check": session.boundary_check.model_dump() if session.boundary_check else None,
        }

    async def _inherit_parent_interface_constraints(
        self, spec: SkillSpec, parent_tool_id: str
    ) -> bool:
        """迭代模式：从父 Skill 继承接口规格约束（含 URL 的 constraints）。

        背景：升级会话的对话中没有原始需求文本，规格生成的 URL 兜底提取
        拿不到接口地址，导致新版本 spec 丢失接口契约——确认页出现
        「未识别到接口 URL」警告，代码生成阶段会臆造 URL。
        来源优先级：父 Skill 的 constraints 字段（新版本已持久化）；
        老版本回退从父代码中提取接口 URL。
        """
        url_re = re.compile(r"https?://[A-Za-z0-9\-._~:/?#\[\]@!$&'()*+,;=%]+")

        def _base_urls(text: str) -> set:
            return {
                m.group(0).split("?")[0].rstrip(".,;:")
                for m in url_re.finditer(text or "")
            }

        try:
            parent = await self._db[SKILL_COLLECTION].find_one(
                {"tool_id": parent_tool_id},
                {"constraints": 1, "code": 1, "session_id": 1},
            )
        except Exception as exc:
            logger.warning("[Iterate] 加载父 Skill 失败（跳过接口约束继承）: %s", exc)
            return False
        if not parent:
            return False

        # 来源优先级：
        # 1) 父 Skill 的 constraints 字段（_save_skill 已持久化，新版本技能可用）
        # 2) 父 Skill 来源会话的 spec.constraints（老版本技能也有完整接口约束行）
        # 3) 父代码中提取接口 URL（最后兜底，要求多级路径以排除 Referer 等纯域名）
        interface_lines = [
            str(c) for c in (parent.get("constraints") or []) if url_re.search(str(c))
        ]
        if not interface_lines:
            origin_session_id = parent.get("session_id")
            if origin_session_id:
                try:
                    origin_sess = await self._db[SESSION_COLLECTION].find_one(
                        {"session_id": origin_session_id}, {"spec.constraints": 1}
                    )
                except Exception as exc:
                    logger.debug("[Iterate] 加载父会话失败: %s", exc)
                    origin_sess = None
                if origin_sess and origin_sess.get("spec"):
                    interface_lines = [
                        str(c)
                        for c in ((origin_sess["spec"] or {}).get("constraints") or [])
                        if url_re.search(str(c))
                    ]
        if not interface_lines:
            urls = [
                u
                for u in _base_urls(parent.get("code") or "")
                # 域名后至少 2 级路径（如 /motor/pc/car/rank_data），
                # 排除纯域名与单级路径的 Referer 引用
                if len([s for s in u.split("//", 1)[-1].split("/") if s]) >= 3
            ]
            interface_lines = [
                f"【接口规格 — 必须原样使用】接口 URL: {u}（继承自父版本 {parent_tool_id}，"
                "路径/参数名严禁改写，如 rank_data 不得写成 rank/data；"
                "URL 中的查询参数仅是示例，实现时以函数参数传参）"
                for u in urls
            ]
        if not interface_lines:
            return False

        existing = _base_urls("\n".join(str(c) for c in (spec.constraints or [])))
        added = False
        for line in interface_lines:
            line_urls = _base_urls(line)
            if line_urls and not (line_urls & existing):
                spec.constraints.insert(0, line)
                existing |= line_urls
                added = True
        if added:
            logger.info(
                "[Iterate] 已继承父版本接口规格约束 (parent=%s)", parent_tool_id
            )
        return added

    async def _load_parent_skill_code(self, parent_tool_id: str) -> str:
        """迭代模式：加载父版本完整已验证代码作为升级基线。

        背景：升级通常只是加字段/加参数等小调整，人类做法是在原代码上改几行。
        若不带父代码，首轮生成从零重写，既浪费又会丢掉父版本多轮迭代才修好的
        细节（分页/重试/本地过滤/字段映射等）。
        """
        try:
            parent = await self._db[SKILL_COLLECTION].find_one(
                {"tool_id": parent_tool_id},
                {"code": 1, "implementation": 1, "status": 1},
            )
        except Exception as exc:
            logger.warning("[Iterate] 加载父 Skill 代码失败（按从零生成处理）: %s", exc)
            return ""
        if not parent:
            logger.warning("[Iterate] 未找到父 Skill: tool_id=%s", parent_tool_id)
            return ""
        code = parent.get("code") or parent.get("implementation") or ""
        if code:
            logger.info(
                "[Iterate] 已加载父版本代码作为升级基线: parent=%s chars=%d status=%s",
                parent_tool_id, len(code), parent.get("status"),
            )
        return code

    async def _load_parent_skill_contract(
        self, parent_tool_id: str
    ) -> Optional[Dict[str, Any]]:
        """迭代模式：加载父版本完整契约（参数/约束/输出/完整代码）+ 计算新版本号。

        升级补丁模式的事实源：规格生成 LLM 读它定位变更点，补丁套用
        从它原样继承未提及的字段。版本号查询与 _save_skill 同一套逻辑，
        保证 spec.tool_id 在生成期就与最终落库一致（codegen 函数名/
        静态校验都按 tool_id 对齐，事后改会导致整轮作废）。
        """
        try:
            parent = await self._db[SKILL_COLLECTION].find_one(
                {"tool_id": parent_tool_id}
            )
        except Exception as exc:
            logger.warning("[Iterate] 加载父 Skill 契约失败: %s", exc)
            return None
        if not parent:
            logger.warning("[Iterate] 未找到父 Skill（契约加载）: tool_id=%s", parent_tool_id)
            return None

        root_tool_id = parent.get("parent_skill_id") or parent_tool_id
        # 系列内最大版本号（含根版本），与 _save_skill 的版本计算保持一致
        new_version = 2
        try:
            cursor = (
                self._db[SKILL_COLLECTION]
                .find({"$or": [{"tool_id": root_tool_id}, {"parent_skill_id": root_tool_id}]})
                .sort("version", -1)
                .limit(1)
            )
            max_docs = await cursor.to_list(1)
            if max_docs:
                new_version = int(max_docs[0].get("version") or 1) + 1
        except Exception as exc:
            logger.warning("[Iterate] 查询系列版本号失败，使用默认 v2: %s", exc)

        contract = {
            "tool_id": parent.get("tool_id") or parent_tool_id,
            "root_tool_id": root_tool_id,
            "new_tool_id": f"{root_tool_id}_v{new_version}",
            "new_version": new_version,
            "display_name": parent.get("display_name") or "",
            "description": parent.get("description") or "",
            "category": parent.get("category") or "utility",
            "data_source": parent.get("data_source") or "",
            "parameters": list(parent.get("parameters") or []),
            "expected_output": dict(parent.get("expected_output") or {}),
            "constraints": list(parent.get("constraints") or []),
            "test_input": dict(parent.get("test_input") or {}),
            "code": parent.get("code") or parent.get("implementation") or "",
        }
        logger.info(
            "[Iterate] 已加载父版本契约（补丁模式基座）: parent=%s root=%s next=%s "
            "params=%d constraints=%d code_chars=%d",
            contract["tool_id"], root_tool_id, contract["new_tool_id"],
            len(contract["parameters"]), len(contract["constraints"]),
            len(contract["code"]),
        )
        return contract

    async def _preflight_external_interface(
        self, spec: SkillSpec, parent_code: str = ""
    ) -> Optional[Dict[str, Any]]:
        """external_api 模式：沙箱内真实调用接口做连通性预检。

        在规格确认阶段就发现「URL 错误/接口不可达/参数问题」，
        避免等代码生成（每轮 2-4 分钟）后沙箱执行才暴露。

        parent_code: 升级场景的父版本代码——约束中只有裸 URL（无查询串）时，
        从中提取父代码已验证的查询参数（如 count/offset）作为预检基线，
        防止新 spec 参数（如 limit）被误判为接口可用参数。
        """
        from core.tools.external.interface_preflight import (
            build_interface_probe,
            interpret_probe_result,
        )
        from core.tools.external.sandbox_runner import SandboxRunner

        probe = build_interface_probe(spec, parent_code=parent_code)
        if probe is None:
            return None
        runner = SandboxRunner(timeout=25)
        sandbox = await asyncio.get_event_loop().run_in_executor(
            None, lambda: runner.run(probe["code"], spec, test_input=probe["params"])
        )
        verdict = interpret_probe_result(sandbox)
        verdict["url"] = probe["url"]
        # 实测验证可用的查询参数 = 基线参数（用户 URL 文档化查询参数）。
        # 疑似业务过滤参数（如 brand_name）经差分测试后落在
        # ignored_params（被忽略→本地过滤）/ server_filter_params（服务端过滤生效）
        baseline = probe.get("baseline_params") or {}
        if baseline:
            verdict["probed_params"] = dict(baseline)
        verdict["checked_at"] = datetime.utcnow().isoformat()
        logger.info(
            "[Preflight] 外部接口预检 tool_id=%s url=%s status=%s message=%s",
            spec.tool_id,
            probe["url"],
            verdict.get("status"),
            verdict.get("message"),
        )
        return verdict

    async def preview_spec(
        self, session_id: str, user_message: str = "确认"
    ) -> Optional[Dict[str, Any]]:
        """
        仅生成 SkillSpec 预览，不修改会话状态。
        用于规格确认步骤展示。

        流程：先生成草稿 spec → 运行侦察 → 基于侦察事实重新生成 enriched spec。
        """
        session = await self._load_session(session_id)
        if not session:
            raise ValueError(f"会话 {session_id} 不存在")

        # 迭代模式：加载父版本契约，规格生成走升级补丁模式（父契约 + delta）
        parent_contract = None
        if session.iterate_skill_id:
            parent_contract = await self._load_parent_skill_contract(
                session.iterate_skill_id
            )

        # 第一遍：生成草稿 spec（无侦察事实）
        draft_spec = await asyncio.get_event_loop().run_in_executor(
            None, self._analyzer.preview_spec, session, user_message, None, parent_contract
        )
        if not draft_spec:
            return None

        # 向量搜索：用 spec 描述从能力索引中召回语义相关的工具
        capability_hits = await self._search_capability_index(draft_spec)

        # 运行侦察层：基于草稿 spec 探测真实数据可用性（附带向量搜索结果）
        fact_report = await asyncio.get_event_loop().run_in_executor(
            None, self._reconnaissance.analyze, draft_spec, capability_hits
        )
        logger.info("🧭 侦察完成 (preview)，置信度: %.0f%%", fact_report.confidence * 100)

        # 第二遍：基于侦察事实重新生成 enriched spec。
        # 仅在侦察产出字段级实证事实且非 external_api 模式时执行——
        # external_api 模式侦察不探测外部接口，报告内容均为模式派生的静态指引
        # （字段清单还是从草稿回抄的），二次生成输入与草稿无实质差异，
        # 只会白白多花一次 LLM 调用（思考模型下约 5 分钟）。
        enriched_spec = None
        if (
            classify_requirement_mode(draft_spec) != "external_api"
            and fact_report.has_spec_grounding_facts
        ):
            enriched_spec = await asyncio.get_event_loop().run_in_executor(
                None, self._analyzer.preview_spec, session, user_message, fact_report,
                parent_contract,
            )
        final_spec = enriched_spec or draft_spec

        # 缓存 spec 与 fact_report 到 session，confirm_spec 时直接复用，
        # 避免再次调用 LLM 生成规格导致前端长时间停留在 0%。
        session.spec = final_spec
        self._apply_handoff_context_to_spec(session.spec, session.handoff_context)
        # 迭代模式：继承父版本接口规格约束（含 URL），确认页不再出现
        # 「未识别到接口 URL」警告，代码生成也不丢接口契约
        if session.iterate_skill_id:
            await self._inherit_parent_interface_constraints(
                session.spec, session.iterate_skill_id
            )
        session.fact_report = fact_report
        await self._save_session(session)

        # 外部接口预检：沙箱内真实调用接口验证连通性，结果展示在确认页
        interface_preflight = None
        if classify_requirement_mode(session.spec) == "external_api":
            # 升级场景：带父代码，预检基线沿用父版本已验证的查询参数
            preview_parent_code = ""
            if session.iterate_skill_id:
                preview_parent_code = await self._load_parent_skill_code(session.iterate_skill_id)
            try:
                interface_preflight = await self._preflight_external_interface(
                    session.spec, parent_code=preview_parent_code
                )
            except Exception as exc:
                logger.warning("[Preflight] 接口预检失败（不阻塞确认）: %s", exc)
            if interface_preflight is not None:
                try:
                    await self._db[SESSION_COLLECTION].update_one(
                        {"session_id": session.session_id},
                        {"$set": {"interface_preflight": interface_preflight}},
                    )
                except Exception as exc:
                    logger.warning("[Preflight] 预检结果落库失败: %s", exc)

        return {
            "spec": final_spec.model_dump(),
            "recommendations": self._build_session_recommendations(spec=final_spec, fact_report=fact_report),
            "fact_report": fact_report.model_dump() if fact_report else None,
            "interface_preflight": interface_preflight,
            # 升级补丁模式的变更点清单（确认页 diff 式展示：改了什么、其余继承）
            "upgrade_change_points": (
                (final_spec.metadata or {}).get("upgrade_change_points")
                if parent_contract else None
            ),
        }

    async def confirm_spec(
        self, session_id: str, user_message: str = "确认", codegen_timeout: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        确认规格并触发代码生成

        流程：复用 preview 阶段缓存的 fact_report，若无则现场侦察。
        将 fact_report 同时注入 spec 生成和管线执行，实现"侦察→定规→生成"闭环。

        Args:
            session_id: 会话 ID
            user_message: 确认消息
            codegen_timeout: 代码生成单次 LLM 调用超时（秒），None 用默认值

        Returns:
            包含 status, spec, generation_result 等信息的 dict
        """
        session = await self._load_session(session_id)
        if not session:
            raise ValueError(f"会话 {session_id} 不存在")

        # 复用 preview 阶段缓存的 fact_report，若无则先跑侦察
        fact_report = session.fact_report
        if fact_report is None:
            # 需要先生成草稿 spec 用于侦察
            draft_parent_contract = (
                await self._load_parent_skill_contract(session.iterate_skill_id)
                if session.iterate_skill_id else None
            )
            draft_spec = await asyncio.get_event_loop().run_in_executor(
                None, self._analyzer.preview_spec, session, user_message,
                None, draft_parent_contract,
            )
            if draft_spec:
                # 向量搜索：从能力索引中召回语义相关的工具
                capability_hits = await self._search_capability_index(draft_spec)
                fact_report = await asyncio.get_event_loop().run_in_executor(
                    None, self._reconnaissance.analyze, draft_spec, capability_hits
                )
                logger.info("🧭 侦察完成 (confirm)，置信度: %.0f%%", fact_report.confidence * 100)

        # 如果 preview 阶段已经缓存了规格，并且当前只是常规“确认”，
        # 则直接复用，避免 confirm 时再次调用 LLM 生成 SkillSpec。
        normalized_message = (user_message or "").strip()
        can_reuse_preview_spec = bool(
            session.spec
            and fact_report is not None
            and normalized_message in ("", "确认", "确认生成", "继续生成")
        )

        if can_reuse_preview_spec:
            spec = session.spec
            session.spec_confirmed = True
            session.status = SessionStatus.CONFIRMED
            session.updated_at = datetime.utcnow()
            await self._save_session(session)
        else:
            # 基于侦察事实生成最终 SkillSpec（迭代模式带父契约走补丁模式）
            confirm_parent_contract = (
                await self._load_parent_skill_contract(session.iterate_skill_id)
                if session.iterate_skill_id else None
            )
            session, spec = await asyncio.get_event_loop().run_in_executor(
                None, self._analyzer.confirm_spec, session, user_message, fact_report,
                confirm_parent_contract,
            )

        if not spec:
            return {
                "status": "failed",
                "message": "规格生成失败，请重新描述需求",
            }

        self._apply_handoff_context_to_spec(spec, session.handoff_context)

        # 迭代模式：继承父版本接口规格约束（含 URL）——preview 缓存复用路径
        # 也要兜底，防止升级版丢失接口契约导致代码生成臆造 URL
        if session.iterate_skill_id and await self._inherit_parent_interface_constraints(
            spec, session.iterate_skill_id
        ):
            session.spec = spec
            await self._save_session(session)

        # 迭代模式：提前加载父版本代码（预检基线参数 + 管线升级基线共用，避免重复查库）
        parent_code = ""
        if session.iterate_skill_id:
            parent_code = await self._load_parent_skill_code(session.iterate_skill_id)

        # 外部接口预检拦截：接口明确不可用（不可达/4xx/5xx）时阻止代码生成，
        # 避免烧掉 2-4 分钟/轮的生成后才在沙箱发现接口问题。
        # preview 已缓存结果则复用；直接确认（跳过 preview）时现跑。
        if classify_requirement_mode(spec) == "external_api":
            preflight = None
            try:
                sess_doc = await self._db[SESSION_COLLECTION].find_one(
                    {"session_id": session_id}, {"interface_preflight": 1}
                )
                preflight = (sess_doc or {}).get("interface_preflight")
            except Exception:
                preflight = None
            if preflight is None:
                try:
                    preflight = await self._preflight_external_interface(
                        spec, parent_code=parent_code
                    )
                except Exception as exc:
                    logger.warning("[Preflight] 确认阶段预检失败（放行）: %s", exc)
                if preflight is not None:
                    try:
                        await self._db[SESSION_COLLECTION].update_one(
                            {"session_id": session_id},
                            {"$set": {"interface_preflight": preflight}},
                        )
                    except Exception:
                        pass
            if preflight and preflight.get("status") == "failed":
                return {
                    "status": "failed",
                    "message": (
                        f"外部接口预检未通过，已阻止代码生成：{preflight.get('message')}。"
                        "请修正接口规格（URL/请求头/参数）后重新确认。"
                    ),
                    "interface_preflight": preflight,
                }

        # 迭代模式：父版本代码作为升级基线（小改动场景，避免从零重写）
        iteration_mode = "upgrade" if parent_code else "repair"

        # fact_report 同时传递给管线，跳过内部重复侦察
        return await self._launch_pipeline_task(
            session=session, spec=spec, fact_report=fact_report,
            codegen_timeout=codegen_timeout,
            initial_code=parent_code,
            iteration_mode=iteration_mode,
        )

    async def repair_session(
        self,
        session_id: str,
        feedback: str,
        repair_plan: str = "",
        codegen_timeout: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        基于当前失败会话重新修正并生成。

        使用累积的所有历史管线经验 + 用户补充意见作为新一轮的初始反馈，
        确保 LLM 能吸取之前每次尝试的教训，而不是只看到最近一次失败。
        """
        session = await self._load_session(session_id)
        if not session:
            raise ValueError(f"会话 {session_id} 不存在")
        if not session.spec_confirmed or not session.spec:
            raise ValueError("当前会话还没有确认规格，无法进入修正模式")
        if session.status != SessionStatus.FAILED:
            raise ValueError("只有失败的创建会话才能确认修正并重跑")

        merged_feedback = feedback.strip()
        if repair_plan.strip():
            merged_feedback = (
                f"{merged_feedback}\n\n=== 已确认的修正计划 ===\n{repair_plan.strip()}"
            )

        attempt_count = len(session.pipeline_history) + (1 if session.pipeline_result else 0)
        session.rounds.append(ConversationRound(
            round_number=len(session.rounds) + 1,
            user_message=f"[修正] {feedback}",
            ai_message=(
                f"已确认修正计划，结合前 {attempt_count} 次经验重新生成..."
                if repair_plan.strip() else
                f"已接收修正意见，结合前 {attempt_count} 次经验重新生成..."
            ),
        ))

        initial_feedback = self._build_accumulated_experience(
            pipeline_history=session.pipeline_history,
            current_pipeline=session.pipeline_result,
            user_feedback=merged_feedback,
        )
        initial_code = self._get_last_generated_code(session.pipeline_result)

        return await self._launch_pipeline_task(
            session=session,
            spec=session.spec,
            initial_feedback=initial_feedback,
            initial_code=initial_code,
            codegen_timeout=codegen_timeout,
        )

    async def preview_repair_session(
        self,
        session_id: str,
        feedback: str,
    ) -> Dict[str, Any]:
        """
        先生成 AI 修正计划，等待用户确认后再重跑。
        """
        session = await self._load_session(session_id)
        if not session:
            raise ValueError(f"会话 {session_id} 不存在")
        if not session.spec_confirmed or not session.spec:
            raise ValueError("当前会话还没有确认规格，无法生成修正计划")
        if session.status != SessionStatus.FAILED:
            raise ValueError("只有失败的创建会话才能先生成修正计划")

        ai_message, repair_llm_response = await asyncio.get_event_loop().run_in_executor(
            None,
            self._generate_repair_plan_message,
            session,
            feedback,
        )

        # 记录 token 使用（LLM 调用在同步方法中完成，此处在其异步调用方中记录）
        try:
            if repair_llm_response is not None:
                from app.services.usage_statistics_service import usage_statistics_service
                await usage_statistics_service.record_llm_usage(
                    response=repair_llm_response,
                    session_id=session_id,
                    analysis_type="skill_generation",
                )
        except Exception as e:
            logger.warning(f"记录 token 使用失败: {e}")

        session.rounds.append(ConversationRound(
            round_number=len(session.rounds) + 1,
            user_message=f"[修正讨论] {feedback}",
            ai_message=ai_message,
        ))
        await self._save_session(session)

        return {
            "status": "repair-planned",
            "session_id": session_id,
            "ai_message": ai_message,
        }

    # ==================== Skill 管理 ====================

    async def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """获取会话详情"""
        doc = await self._db[SESSION_COLLECTION].find_one({"session_id": session_id})
        if not doc:
            return None
        doc.pop("_id", None)
        try:
            session = SkillCreationSession(**doc)
            spec = session.spec if isinstance(session.spec, SkillSpec) else None
            doc["recommendations"] = self._build_session_recommendations(spec=spec, session=session)
        except Exception:
            rounds = doc.get("rounds", []) or []
            conversation = "\n\n".join(
                f"[用户 - 第{item.get('round_number', '?')}轮]: {item.get('user_message', '')}\n"
                f"[AI - 第{item.get('round_number', '?')}轮]: {item.get('ai_message', '')}"
                for item in rounds
            )
            doc["recommendations"] = self._analyzer.build_recommendations(conversation=conversation)
        return doc

    async def list_sessions(
        self,
        status: Optional[str] = None,
        user_id: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Dict[str, Any]:
        """列出创建会话（草稿/未完成）"""
        query: Dict[str, Any] = {}
        if status:
            # 支持逗号分隔的多状态：gathering,confirmed
            statuses = [s.strip() for s in status.split(",")]
            query["status"] = {"$in": statuses}
        if user_id:
            query["user_id"] = user_id

        total = await self._db[SESSION_COLLECTION].count_documents(query)
        skip = (page - 1) * page_size

        sessions = []
        cursor = (
            self._db[SESSION_COLLECTION]
            .find(query)
            .sort("updated_at", -1)
            .skip(skip)
            .limit(page_size)
        )
        async for doc in cursor:
            doc.pop("_id", None)
            try:
                session = SkillCreationSession(**doc)
                spec = session.spec if isinstance(session.spec, SkillSpec) else None
                doc["recommendations"] = self._build_session_recommendations(spec=spec, session=session)
            except Exception:
                rounds = doc.get("rounds", []) or []
                conversation = "\n\n".join(
                    f"[用户 - 第{item.get('round_number', '?')}轮]: {item.get('user_message', '')}\n"
                    f"[AI - 第{item.get('round_number', '?')}轮]: {item.get('ai_message', '')}"
                    for item in rounds
                )
                doc["recommendations"] = self._analyzer.build_recommendations(conversation=conversation)
            sessions.append(doc)

        return {
            "total": total,
            "page": page,
            "page_size": page_size,
            "items": sessions,
        }

    async def delete_session(self, session_id: str) -> bool:
        """删除草稿会话"""
        result = await self._db[SESSION_COLLECTION].delete_one({"session_id": session_id})
        return result.deleted_count > 0

    async def list_skills(
        self,
        category: Optional[str] = None,
        status: Optional[str] = None,
        source: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Dict[str, Any]:
        """列出外部 Skill（分页）"""
        query: Dict[str, Any] = {}
        if category:
            query["category"] = category
        if status:
            query["status"] = status
        if source:
            clean_source = str(source or "").strip()
            if clean_source == "agent_studio_auto_gap_resolution":
                query["origin_source"] = clean_source
            elif clean_source == "manual_or_other":
                query["origin_source"] = {"$ne": "agent_studio_auto_gap_resolution"}
            else:
                query["source"] = clean_source

        logger.info(
            "[SkillGeneration][ListSkills] start source=%s category=%s status=%s page=%s page_size=%s query=%s",
            source or "-",
            category or "-",
            status or "-",
            page,
            page_size,
            query,
        )

        total = await self._db[SKILL_COLLECTION].count_documents(query)
        skip = (page - 1) * page_size

        skills = []
        cursor = (
            self._db[SKILL_COLLECTION]
            .find(query)
            .sort("created_at", -1)
            .skip(skip)
            .limit(page_size)
        )
        async for doc in cursor:
            doc.pop("_id", None)
            doc = await self._hydrate_skill_generation_context(doc)
            doc["used_by_agents"] = await self._find_skill_agent_usage(str(doc.get("tool_id") or ""))
            skills.append(doc)

        logger.info(
            "[SkillGeneration][ListSkills] done source=%s total=%s returned=%s",
            source or "-",
            total,
            len(skills),
        )

        return {
            "total": total,
            "page": page,
            "page_size": page_size,
            "items": skills,
        }

    async def get_skill(self, skill_id: str) -> Optional[Dict[str, Any]]:
        """获取 Skill 详情"""
        clean_skill_id = str(skill_id or "").strip()
        logger.info(
            "[SkillGeneration][GetSkill] start skill_id=%s",
            clean_skill_id or "-",
        )
        doc = await self._db[SKILL_COLLECTION].find_one({"tool_id": clean_skill_id})
        if not doc:
            logger.info("[SkillGeneration][GetSkill] not_found skill_id=%s", clean_skill_id or "-")
            return None
        doc.pop("_id", None)
        doc = await self._hydrate_skill_generation_context(doc)
        doc["used_by_agents"] = await self._find_skill_agent_usage(str(doc.get("tool_id") or ""))
        logger.info(
            "[SkillGeneration][GetSkill] done skill_id=%s status=%s source=%s origin_source=%s",
            clean_skill_id or "-",
            doc.get("status", ""),
            doc.get("source", ""),
            doc.get("origin_source", ""),
        )
        return doc

    async def _find_skill_agent_usage(self, skill_id: str) -> List[Dict[str, Any]]:
        """反查 Skill 被哪些 Agent 版本使用。"""
        clean_skill_id = str(skill_id or "").strip()
        if not clean_skill_id:
            return []

        try:
            cursor = self._db["agent_versions"].find(
                {"required_tools": clean_skill_id},
                {
                    "_id": 0,
                    "version_id": 1,
                    "spec_id": 1,
                    "version": 1,
                    "status": 1,
                    "agent_metadata": 1,
                    "published_from_session_id": 1,
                    "updated_at": 1,
                },
            ).sort("updated_at", -1).limit(20)
            docs = await cursor.to_list(length=20)
        except Exception as exc:
            logger.debug("[SkillGeneration][AgentUsage] query failed skill_id=%s err=%s", clean_skill_id, exc)
            return []

        usage: List[Dict[str, Any]] = []
        for doc in docs or []:
            metadata = doc.get("agent_metadata") if isinstance(doc.get("agent_metadata"), dict) else {}
            usage.append({
                "version_id": str(doc.get("version_id") or ""),
                "spec_id": str(doc.get("spec_id") or ""),
                "version": doc.get("version"),
                "status": str(doc.get("status") or ""),
                "agent_name": str(metadata.get("name") or metadata.get("agent_name") or ""),
                "published_from_session_id": str(doc.get("published_from_session_id") or ""),
                "updated_at": str(doc.get("updated_at") or ""),
            })

        logger.info(
            "[SkillGeneration][AgentUsage] done skill_id=%s agents=%s",
            clean_skill_id,
            len(usage),
        )
        return usage

    async def get_skill_code(self, skill_id: str) -> Optional[str]:
        """获取 Skill 源代码"""
        doc = await self._db[SKILL_COLLECTION].find_one(
            {"tool_id": skill_id}, {"code": 1}
        )
        if not doc:
            return None
        return doc.get("code", "")

    async def get_skill_history(self, skill_id: str) -> Optional[Dict[str, Any]]:
        """
        获取 Skill 完整沟通历史：原始创建会话 + 所有优化会话

        Returns:
            {
                "skill_id": "...",
                "sections": [
                    { "type": "creation", "label": "创建", "session_id": "...", "rounds": [...], "created_at": "..." },
                    { "type": "optimize", "label": "优化 v2", "session_id": "...", "rounds": [...], "created_at": "...", "feedback": "..." },
                    ...
                ]
            }
        """
        skill_doc = await self._db[SKILL_COLLECTION].find_one({"tool_id": skill_id})
        if not skill_doc:
            return None

        sections = []

        # 原始创建会话
        original_session_id = skill_doc.get("session_id", "")
        if original_session_id:
            session = await self.get_session(original_session_id)
            if session:
                sections.append({
                    "type": "creation",
                    "label": "初始创建",
                    "session_id": original_session_id,
                    "rounds": session.get("rounds", []),
                    "created_at": session.get("created_at", ""),
                })

        # 所有优化会话
        optimize_ids = skill_doc.get("optimize_session_ids", [])
        # 向后兼容：如果只有旧的 optimize_session_id 字段
        legacy_id = skill_doc.get("optimize_session_id", "")
        if legacy_id and legacy_id not in optimize_ids:
            optimize_ids = [legacy_id] + optimize_ids

        for idx, opt_sid in enumerate(optimize_ids):
            session = await self.get_session(opt_sid)
            if session:
                version_label = f"优化 v{idx + 2}"
                # 从 rounds 中提取优化反馈
                feedback = ""
                rounds = session.get("rounds", [])
                if rounds:
                    first_msg = rounds[0].get("user_message", "")
                    if first_msg.startswith("[优化] "):
                        feedback = first_msg[len("[优化] "):]
                sections.append({
                    "type": "optimize",
                    "label": version_label,
                    "session_id": opt_sid,
                    "rounds": rounds,
                    "created_at": session.get("created_at", ""),
                    "feedback": feedback,
                })

        return {
            "skill_id": skill_id,
            "display_name": skill_doc.get("display_name", ""),
            "sections": sections,
        }

    async def update_skill_status(
        self, skill_id: str, new_status: str
    ) -> bool:
        """更新 Skill 状态（active / disabled / archived），并同步运行时 ToolRegistry。"""
        skill_doc = await self._db[SKILL_COLLECTION].find_one({"tool_id": skill_id})
        if not skill_doc:
            return False

        result = await self._db[SKILL_COLLECTION].update_one(
            {"tool_id": skill_id},
            {"$set": {"status": new_status, "updated_at": datetime.utcnow().isoformat()}},
        )

        try:
            from core.tools.registry import get_tool_registry
            registry = get_tool_registry()
            if new_status == "active":
                from core.tools.external_skill_loader import register_single_external_skill
                skill_doc["status"] = new_status
                register_single_external_skill(None, registry, skill_doc)
            else:
                registry.unregister(skill_id)
        except Exception as e:
            logger.warning(f"⚠️ Skill '{skill_id}' 运行时状态同步失败: {e}")

        return result.modified_count > 0

    async def update_skill_info(
        self, skill_id: str, display_name: str, description: str
    ) -> bool:
        """更新 Skill 的展示名称与功能说明（用户手动编辑）。

        仅允许改这两个展示字段——参数/代码/约束属于已验证契约，
        要改请走迭代优化生成新版本。更新后同步运行时 ToolRegistry
        （名称/描述是 ToolMetadata 的一部分）与能力索引。
        """
        clean_name = str(display_name or "").strip()
        clean_desc = str(description or "").strip()
        if not clean_name:
            raise ValueError("Skill 名称不能为空")

        skill_doc = await self._db[SKILL_COLLECTION].find_one({"tool_id": skill_id})
        if not skill_doc:
            return False

        await self._db[SKILL_COLLECTION].update_one(
            {"tool_id": skill_id},
            {
                "$set": {
                    "display_name": clean_name,
                    "description": clean_desc,
                    "updated_at": datetime.utcnow().isoformat(),
                }
            },
        )

        # 同步运行时注册（用更新后的文档重新注册，ToolMetadata 名称/描述随之刷新）
        try:
            from core.tools.registry import get_tool_registry
            from core.tools.external_skill_loader import register_single_external_skill

            skill_doc["display_name"] = clean_name
            skill_doc["description"] = clean_desc
            skill_doc["status"] = skill_doc.get("status", "active")
            register_single_external_skill(None, get_tool_registry(), skill_doc)
        except Exception as e:
            logger.warning(f"⚠️ Skill '{skill_id}' 说明更新后运行时同步失败: {e}")

        # 能力索引含名称/描述，异步刷新
        try:
            from app.services.capability_index_service import CapabilityIndexService
            asyncio.create_task(CapabilityIndexService(self._db).ensure_index())
        except Exception as e:
            logger.warning(f"⚠️ Skill '{skill_id}' 能力索引刷新失败: {e}")

        return True

    async def delete_skill(self, skill_id: str) -> bool:
        """删除 Skill，并清理运行时注册和工具绑定。"""
        result = await self._db[SKILL_COLLECTION].delete_one({"tool_id": skill_id})
        if result.deleted_count:
            await self._db.tool_agent_bindings.delete_many({"tool_id": skill_id})
            try:
                from core.tools.registry import get_tool_registry
                get_tool_registry().unregister(skill_id)
            except Exception as e:
                logger.warning(f"⚠️ Skill '{skill_id}' 运行时注销失败: {e}")
        return result.deleted_count > 0

    async def test_skill(
        self, skill_id: str, test_args: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """手动测试 Skill"""
        doc = await self._db[SKILL_COLLECTION].find_one({"tool_id": skill_id})
        if not doc:
            raise ValueError(f"Skill {skill_id} 不存在")

        code = doc.get("code", "")
        if not code:
            raise ValueError("Skill 没有代码")

        # 🔬 把即将执行的代码打到日志
        logger.info(f"🔬 [test_skill] 即将执行 skill={skill_id}, code_len={len(code)}\n" + code)

        # 使用 SandboxRunner 执行
        from core.tools.external import SandboxRunner, SkillSpec

        # 🔬 打印前端传来的 test_args
        logger.info(f"🔬 [test_skill] 原始 test_args={test_args}")

        # 过滤掉未填写的参数（None/空字符串），让函数默认值生效。
        # 注意 0/False 是合法入参（如 offset=0），不能当 falsy 删掉。
        if test_args:
            test_args = {k: v for k, v in test_args.items() if v is not None and v != ''}
            logger.info(f"🔬 [test_skill] 过滤后 test_args={test_args}")

        runner = SandboxRunner()
        # 构建简单的 spec 用于测试
        spec = SkillSpec(
            tool_id=doc["tool_id"],
            display_name=doc.get("display_name", ""),
            description=doc.get("description", ""),
            test_input=test_args or doc.get("test_input", {}),
        )
        sandbox_result = runner.run(code, spec)

        # 把子进程的 stdout/stderr 打到 webapi 日志
        if sandbox_result.stdout:
            for line in sandbox_result.stdout.split("\n"):
                line = line.strip()
                if line:
                    logger.info(f"📦 [Skill测试沙箱stdout] {line}")
        if sandbox_result.stderr:
            for line in sandbox_result.stderr.split("\n"):
                line = line.strip()
                if line:
                    logger.warning(f"📦 [Skill測試沙箱stderr] {line}")

        return {
            "success": sandbox_result.success,
            "output": sandbox_result.output,
            "stdout": sandbox_result.stdout,
            "stderr": sandbox_result.stderr,
            "execution_time": sandbox_result.execution_time,
            "error": sandbox_result.error,
        }

    async def optimize_skill(
        self, skill_id: str, feedback: str
    ) -> Dict[str, Any]:
        """
        优化已有 Skill：基于用户反馈重新生成代码

        流程：
        1. 加载已有 Skill 和原始 Session
        2. 将原始对话 + 当前代码 + 用户反馈 合成新的上下文
        3. 创建新 Session 记录优化过程
        4. 执行代码生成管线
        5. 成功则更新 Skill 代码，并保存优化版本号
        """
        # 加载现有 Skill
        skill_doc = await self._db[SKILL_COLLECTION].find_one({"tool_id": skill_id})
        if not skill_doc:
            raise ValueError(f"Skill {skill_id} 不存在")

        # 加载原始会话（获取原始沟通记录和 spec）
        original_session_id = skill_doc.get("session_id", "")
        original_session = None
        if original_session_id:
            original_session = await self.get_session(original_session_id)

        # 重建 SkillSpec
        params = [SkillParameter(**p) for p in skill_doc.get("parameters", [])]
        expected_output_data = skill_doc.get("expected_output", {})
        expected_output = ExpectedOutput(**expected_output_data) if expected_output_data else ExpectedOutput()

        spec = SkillSpec(
            tool_id=skill_doc["tool_id"],
            display_name=skill_doc.get("display_name", ""),
            description=skill_doc.get("description", ""),
            category=skill_doc.get("category", "other"),
            data_source=skill_doc.get("data_source", ""),
            parameters=params,
            expected_output=expected_output,
            test_input=skill_doc.get("test_input", {}),
        )

        # 构造增强反馈：原始对话摘要 + 当前代码 + 用户反馈
        enhanced_feedback = self._build_optimization_feedback(
            original_session=original_session,
            current_code=skill_doc.get("code", ""),
            user_feedback=feedback,
        )

        # 创建优化 Session
        optimize_session = self._analyzer.create_session(
            user_id=skill_doc.get("user_id", "")
        )
        optimize_session.status = SessionStatus.GENERATING
        optimize_session.rounds.append(ConversationRound(
            round_number=1,
            user_message=f"[优化] {feedback}",
            ai_message="开始优化 Skill...",
        ))
        optimize_session.spec = spec
        optimize_session.spec_confirmed = True
        await self._save_session(optimize_session)

        # 执行代码生成管线（带 feedback 和 previous_code）
        current_code = skill_doc.get("code", "")
        method_name = "run_agentic" if SKILL_GENERATION_AGENTIC_ENABLED else "run"
        result = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: getattr(self._controller, method_name)(
                spec,
                initial_feedback=enhanced_feedback,
                initial_code=current_code,
            )
        )

        # 更新优化 Session
        optimize_session.status = (
            SessionStatus.COMPLETED if result.success else SessionStatus.FAILED
        )
        optimize_session.pipeline_result = result
        await self._save_session(optimize_session)

        generation_context = None

        # 如果成功，更新 Skill
        if result.success:
            version = skill_doc.get("version", 1) + 1
            now = datetime.utcnow().isoformat()
            generation_context = self._build_session_recommendations(spec=spec, session=optimize_session)
            metadata = dict(result.final_metadata or {})
            metadata["generation_context"] = generation_context
            await self._db[SKILL_COLLECTION].update_one(
                {"tool_id": skill_id},
                {
                    "$set": {
                        "code": result.final_code,
                        "metadata": metadata,
                        "generation_context": generation_context,
                        "version": version,
                        "optimize_feedback": feedback,
                        "generation_rounds": result.total_rounds,
                        "generation_time": result.total_time,
                        "final_score": (
                            result.iterations[-1].eval_score.total
                            if result.iterations and result.iterations[-1].eval_score
                            else None
                        ),
                        "updated_at": now,
                    },
                    "$push": {
                        "optimize_session_ids": optimize_session.session_id,
                    },
                },
            )
            logger.info(f"✅ Skill '{skill_id}' 已优化到 v{version}")

        return {
            "status": "completed" if result.success else "failed",
            "skill_id": skill_id,
            "optimize_session_id": optimize_session.session_id,
            "success": result.success,
            "version": skill_doc.get("version", 1) + 1 if result.success else skill_doc.get("version", 1),
            "total_rounds": result.total_rounds,
            "total_time": result.total_time,
            "final_score": (
                result.iterations[-1].eval_score.total
                if result.iterations and result.iterations[-1].eval_score
                else None
            ),
            "generation_context": generation_context,
            "error": result.error,
        }

    @staticmethod
    def _build_optimization_feedback(
        original_session: Optional[Dict],
        current_code: str,
        user_feedback: str,
    ) -> str:
        """构建优化反馈上下文"""
        parts = []

        # 原始需求沟通摘要
        if original_session and original_session.get("rounds"):
            parts.append("=== 原始需求沟通记录 ===")
            for r in original_session["rounds"]:
                parts.append(f"[用户]: {r.get('user_message', '')}")
                parts.append(f"[AI]: {r.get('ai_message', '')}")

        # 当前代码
        if current_code:
            parts.append(f"\n=== 当前代码（需优化）===\n```python\n{current_code}\n```")

        # 用户反馈
        parts.append(f"\n=== 用户优化需求 ===\n{user_feedback}")

        return "\n".join(parts)

    # ==================== 内部工具方法 ====================

    async def _load_session(self, session_id: str) -> Optional[SkillCreationSession]:
        """从 MongoDB 加载会话"""
        doc = await self._db[SESSION_COLLECTION].find_one({"session_id": session_id})
        if not doc:
            return None
        doc.pop("_id", None)
        return SkillCreationSession(**doc)

    async def _save_session(self, session: SkillCreationSession) -> None:
        """保存会话到 MongoDB"""
        session.updated_at = datetime.utcnow()
        session_doc = session.model_dump(mode="json")
        await self._db[SESSION_COLLECTION].update_one(
            {"session_id": session.session_id},
            {"$set": session_doc},
            upsert=True,
        )

    async def _save_skill(
        self,
        session: SkillCreationSession,
        spec: SkillSpec,
        result: PipelineResult,
    ) -> str:
        """保存生成的 Skill 到 external_skills 集合"""
        now = datetime.utcnow().isoformat()
        generation_context = self._build_session_recommendations(spec=spec, session=session)
        role_metadata = self._infer_skill_role_metadata(spec, session)
        metadata = dict(result.final_metadata or {})
        metadata["generation_context"] = generation_context
        metadata.update({key: value for key, value in role_metadata.items() if value})
        skill_doc = {
            "tool_id": spec.tool_id,
            "display_name": spec.display_name,
            "description": spec.description,
            "category": spec.category,
            "data_source": spec.data_source,
            "parameters": [p.model_dump() for p in spec.parameters],
            "expected_output": spec.expected_output.model_dump(),
            # 持久化行为/接口规格约束：迭代升级时从中继承接口契约（含 URL），
            # 避免新版本丢失接口地址导致代码生成臆造 URL
            "constraints": list(spec.constraints or []),
            "code": result.final_code,
            "metadata": metadata,
            "test_input": spec.test_input,
            "generation_context": generation_context,
            "capability_tags": role_metadata.get("capability_tags") or [],
            "tool_role_hint": role_metadata.get("tool_role_hint") or "",
            "output_shape": role_metadata.get("output_shape") or "",
            "preferred_for": role_metadata.get("preferred_for") or [],
            "not_replacement_for": role_metadata.get("not_replacement_for") or [],
            "known_failure_summaries": metadata.get("known_failure_summaries") or [],
            "known_verified_facts": metadata.get("known_verified_facts") or [],
            "status": "active",
            "source": "generated",
            "session_id": session.session_id,
            "user_id": session.user_id,
            "generation_rounds": result.total_rounds,
            "generation_time": result.total_time,
            "final_score": (
                result.iterations[-1].eval_score.total
                if result.iterations and result.iterations[-1].eval_score
                else None
            ),
            "created_at": now,
            "updated_at": now,
        }

        # 反向来源追溯：来自 Agent Studio 缺口补齐的 Skill 写回 origin_* 字段（Phase 2）
        handoff = session.handoff_context
        if handoff is not None:
            handoff_source = str(getattr(handoff, "source", "") or "").strip()
            if handoff_source in ("agent_studio_gap", "agent_workshop_gap"):
                skill_doc["origin_source"] = "agent_studio_auto_gap_resolution"
                skill_doc["origin_workshop_session_id"] = str(getattr(handoff, "workshop_session_id", "") or "")
                skill_doc["origin_spec_id"] = str(getattr(handoff, "spec_id", "") or getattr(handoff, "source_spec_id", "") or "")
                skill_doc["origin_version_id"] = str(getattr(handoff, "version_id", "") or "")
                skill_doc["origin_gap_id"] = str(getattr(handoff, "gap_id", "") or "")
                skill_doc["origin_agent_name"] = str(getattr(handoff, "agent_name", "") or getattr(handoff, "source_name", "") or "")

        # 🔧 版本管理：迭代模式下计算版本号，确保 tool_id 符合 _v{N} 命名规则
        is_iteration = bool(session.iterate_skill_id)
        if is_iteration:
            original_tool_id = session.iterate_skill_id or ""
            try:
                original = await self._db[SKILL_COLLECTION].find_one(
                    {"tool_id": original_tool_id}
                )
            except Exception as exc:
                logger.warning("[SkillGeneration][Iterate] 查询原 Skill 失败，按新建处理: %s", exc)
                original = None

            if original:
                # parent_skill_id 指向根 Skill（如果原 Skill 也有 parent，沿用；否则用原 tool_id）
                parent_skill_id = original.get("parent_skill_id") or original_tool_id

                # 查找当前最大版本号（在所有同系列版本中）
                try:
                    cursor = self._db[SKILL_COLLECTION].find({
                        "$or": [
                            {"tool_id": parent_skill_id},
                            {"parent_skill_id": parent_skill_id},
                        ]
                    }).sort("version", -1).limit(1)
                    max_docs = await cursor.to_list(1)
                    new_version = (max_docs[0].get("version", 1) + 1) if max_docs else 2
                except Exception as exc:
                    logger.warning("[SkillGeneration][Iterate] 查询版本号失败，使用默认 v2: %s", exc)
                    new_version = 2

                # 确保 tool_id 符合命名规则：{parent_skill_id}_v{new_version}
                expected_tool_id = f"{parent_skill_id}_v{new_version}"
                if skill_doc["tool_id"] != expected_tool_id:
                    # LLM 可能没遵守约束，这里强制修正
                    logger.info(
                        "[SkillGeneration][Iterate] 修正 tool_id: %s → %s",
                        skill_doc["tool_id"],
                        expected_tool_id,
                    )
                    skill_doc["tool_id"] = expected_tool_id
                    spec.tool_id = expected_tool_id

                # 提取版本说明（取 session 第一轮用户消息前 50 字）
                version_note = ""
                if session.rounds:
                    version_note = (session.rounds[0].user_message or "")[:50]
                if not version_note:
                    version_note = "迭代优化"

                skill_doc["parent_skill_id"] = parent_skill_id
                skill_doc["version"] = new_version
                skill_doc["version_note"] = version_note
                skill_doc["iteration_session_id"] = session.session_id

                logger.info(
                    "[SkillGeneration][Iterate] 迭代保存: parent=%s, version=%d, tool_id=%s",
                    parent_skill_id,
                    new_version,
                    expected_tool_id,
                )
            else:
                # 原 Skill 不存在，降级为新建
                logger.warning(
                    "[SkillGeneration][Iterate] 原 Skill %s 不存在，降级为新建",
                    original_tool_id,
                )
                skill_doc["version"] = 1
        else:
            skill_doc["version"] = 1

        await self._db[SKILL_COLLECTION].insert_one(skill_doc)
        logger.info(f"✅ Skill '{spec.tool_id}' 已保存到数据库 (version={skill_doc.get('version', 1)})")

        try:
            from core.tools.registry import get_tool_registry
            from core.tools.external_skill_loader import register_single_external_skill
            from app.services.capability_index_service import CapabilityIndexService
            register_single_external_skill(None, get_tool_registry(), skill_doc)
            await CapabilityIndexService(self._db).ensure_index()
        except Exception as e:
            logger.warning(f"⚠️ Skill '{spec.tool_id}' 热注册失败（重启后生效）: {e}")

        return spec.tool_id


# ------------------------------------------------------------------
#  mem0 统一记忆层 — Skill 生成集成
# ------------------------------------------------------------------

def _build_skill_memory_metadata_filters(spec: SkillSpec) -> Optional[Dict[str, str]]:
    filters: Dict[str, str] = {}

    category = (spec.category or "").strip()
    data_source = (spec.data_source or "").strip()
    tool_id = (spec.tool_id or "").strip()

    if category:
        filters["category"] = category
    if data_source:
        filters["data_source"] = data_source
    if filters:
        return filters
    if tool_id:
        return {"tool_id": tool_id}
    return None


async def _recall_skill_lessons(db, spec: SkillSpec) -> str:
    """从 mem0 召回同类 Skill 的历史教训"""
    try:
        from core.memory.service import get_memory_service
        svc = get_memory_service(db)
        query = f"{spec.description} {spec.data_source} {spec.category}"
        return await svc.recall_formatted(
            query=query.strip(),
            agent_id="skill_generator",
            scopes=["skill_lesson"],
            limit=10,
            max_chars=2000,
            metadata_filters=_build_skill_memory_metadata_filters(spec),
            ranking_profile="skill_generation",
            group_by_scope=True,
            per_scope_limit=5,
        )
    except Exception as e:
        logger.debug("[mem0] Skill 教训召回失败: %s", e)
        return ""


async def _store_skill_lessons(db, spec: SkillSpec, result: PipelineResult) -> None:
    """将本次管线中的迭代教训写入 mem0。"""
    try:
        from core.memory.service import get_memory_service
        svc = get_memory_service(db)

        lessons = []
        metadata = dict(result.final_metadata or {})
        verified_facts = [str(item) for item in list(metadata.get("verified_facts") or []) if str(item).strip()]
        agentic_trace = metadata.get("agentic_trace") if isinstance(metadata.get("agentic_trace"), list) else []
        last_failure_summary = str(result.error or "").strip()
        if not last_failure_summary:
            for item in reversed(agentic_trace):
                if isinstance(item, dict) and str(item.get("failure_summary") or "").strip():
                    last_failure_summary = str(item.get("failure_summary") or "").strip()
                    break

        if last_failure_summary:
            lessons.append(
                f"Skill '{spec.tool_id}' ({spec.category}/{spec.data_source}) Agentic 失败摘要: {last_failure_summary[:1200]}"
            )
        if verified_facts:
            lessons.append(
                f"Skill '{spec.tool_id}' 已验证环境事实: " + "；".join(verified_facts[:8])
            )
        for it in (result.iterations or []):
            if it.reflection and it.reflection.root_cause:
                lessons.append(
                    f"Skill '{spec.tool_id}' ({spec.category}/{spec.data_source}) "
                    f"第{it.round_number}轮失败: {it.reflection.root_cause}"
                )

        if result.success:
            lessons.append(
                f"Skill '{spec.tool_id}' 最终在第{result.total_rounds}轮通过"
            )

        if not lessons:
            return

        messages = [{"role": "system", "content": "\n".join(lessons)}]
        await svc.store(
            messages,
            agent_id="skill_generator",
            scope="skill_lesson",
            metadata={
                "tool_id": spec.tool_id,
                "category": spec.category,
                "data_source": spec.data_source,
                "success": result.success,
                "total_rounds": result.total_rounds,
                "generation_engine": metadata.get("generation_engine", ""),
                "verified_fact_count": len(verified_facts),
            },
        )
    except Exception as e:
        logger.debug("[mem0] Skill 教训存储失败: %s", e)

