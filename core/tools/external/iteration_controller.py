"""
迭代控制器 — Agent 驱动的 Skill 生成管线

借鉴 OpenClaw Agent Loop 思想：LLM 主导迭代过程，可以看到完整的执行上下文
（sandbox stdout/stderr/output），在每轮失败后先做反思分析再定向修复。

管线流程：
  CodeGenerator → StaticValidator → SandboxRunner → OutputEvaluator
                                                      ↓ (PASS后)
                                                  边缘测试验证

迭代决策：
  PASS  — 评分 >= 8.0 且边缘测试通过
  RETRY — 评分不足、沙箱失败或边缘测试失败，且未超轮次上限
  FAIL  — 超过 8 轮仍未通过，并附带每轮失败原因
"""

import json
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from core.llm import UnifiedLLMClient, Message

from .business_verifier import BusinessVerifierRegistry
from .code_generator import CodeGenerator
from .output_evaluator import OutputEvaluator
from .reconnaissance_controller import DefaultReconnaissanceController, ReconnaissanceController
from .sandbox_runner import SandboxRunner
from .skill_spec import (
    BusinessVerificationResult,
    GeneratedCode,
    ImplementationFactReport,
    IterationRound,
    PipelineResult,
    ReflectionResult,
    SandboxResult,
    SkillSpec,
)
from .static_validator import StaticValidator

logger = logging.getLogger(__name__)

MAX_ITERATIONS = 8
PASS_THRESHOLD = 8.0

# 快照落盘根目录（与 SkillGenerationService 保持一致）
_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_SNAPSHOT_DIR = _PROJECT_ROOT / "data" / "code" / "skill"


class IterationController:
    """
    迭代控制器

    编排 CodeGenerator → StaticValidator → SandboxRunner → OutputEvaluator
    的完整管线，在每轮失败时插入 LLM 反思步骤，最多 5 轮自动重试。
    """

    def __init__(
        self,
        llm_client: Optional[UnifiedLLMClient] = None,
        provider: str = "deepseek",
        model: Optional[str] = None,
        max_iterations: int = MAX_ITERATIONS,
        skip_judge: bool = False,
        reconnaissance_controller: Optional[ReconnaissanceController] = None,
    ):
        self._generator = CodeGenerator(
            llm_client=llm_client, provider=provider, model=model
        )
        self._validator = StaticValidator()
        self._runner = SandboxRunner()
        self._evaluator = OutputEvaluator(
            llm_client=llm_client,
            provider=provider,
            model=model,
            skip_judge=skip_judge,
        )
        self._business_verifiers = BusinessVerifierRegistry()
        self._reconnaissance = reconnaissance_controller or DefaultReconnaissanceController()
        self._llm_client = llm_client
        self._provider = provider
        self._model = model
        self._max_iterations = max_iterations

    def _get_client(self) -> UnifiedLLMClient:
        if self._llm_client is None:
            kwargs = {}
            if self._model:
                kwargs["model"] = self._model
            self._llm_client = UnifiedLLMClient.from_provider(self._provider, **kwargs)
        return self._llm_client

    def run(
        self, spec: SkillSpec,
        initial_feedback: str = "",
        initial_code: str = "",
        progress_callback: Optional[Callable[[str, str, int, float], None]] = None,
    ) -> PipelineResult:
        """
        执行完整的生成管线

        Args:
            spec: Skill 规格书（已确认）
            initial_feedback: 初始反馈（优化场景使用）
            initial_code: 初始代码（优化场景使用）
            progress_callback: 进度回调 (stage, message, iteration, progress)

        Returns:
            PipelineResult: 管线最终结果
        """
        start_time = time.time()
        run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        iterations: List[IterationRound] = []
        feedback = initial_feedback
        previous_code = initial_code
        fact_report: Optional[ImplementationFactReport] = None

        def _report(stage: str, message: str, it: int, prog: float):
            if progress_callback:
                try:
                    progress_callback(stage, message, it, prog)
                except Exception as e:
                    logger.warning(f"progress_callback 异常: {e}")

        try:
            _report("reconnaissance", "正在整理实现事实...", 0, 0.03)
            fact_report = self._reconnaissance.analyze(spec)
            logger.info(
                "🧭 前置侦察完成 | strategy=%s | helpers=%d | checks=%d",
                fact_report.recommended_strategy or "(none)",
                len(fact_report.available_helpers),
                len(fact_report.validation_checks),
            )
            # 侦察报告即时落盘
            self._persist_fact_report(spec.tool_id, run_id, fact_report)

            for idx, update in enumerate(self._build_reconnaissance_updates(fact_report), start=1):
                logger.info("🧭 侦察摘要[%d]: %s", idx, update)
                _report("reconnaissance", update, 0, min(0.03 + idx * 0.01, 0.08))
            _report("reconnaissance", "实现事实整理完成", 0, 0.08)
        except Exception as e:
            logger.warning(f"⚠️ 前置侦察失败，继续使用原有生成流程: {e}")
            _report("reconnaissance", "实现事实整理失败，降级为原流程", 0, 0.08)

        for round_num in range(1, self._max_iterations + 1):
            logger.info(
                f"\n{'='*60}\n"
                f"🔄 Skill 生成管线 — 第 {round_num}/{self._max_iterations} 轮 | tool_id={spec.tool_id}\n"
                f"{'='*60}"
            )
            _report("iteration", f"第 {round_num}/{self._max_iterations} 轮", round_num, 0)

            iteration = IterationRound(round_number=round_num)

            # ===== 阶段 1: 代码生成 =====
            _report("code_generation", "正在生成代码...", round_num, 0.1)
            try:
                generated = self._generator.generate(
                    spec,
                    feedback=feedback,
                    previous_code=previous_code,
                    fact_report=fact_report,
                )
                iteration.generated_code = generated
                # 详细日志：代码摘要
                code_lines = generated.code.split("\n") if generated.code else []
                logger.info(
                    f"✅ [第{round_num}轮] 代码生成完成\n"
                    f"   ⏱️  耗时: {generated.generation_time}s\n"
                    f"   📏 代码行数: {len(code_lines)}\n"
                    f"   📝 代码前5行:\n"
                    + "\n".join(f"      | {line}" for line in code_lines[:5])
                    + (f"\n      | ... (共 {len(code_lines)} 行)" if len(code_lines) > 5 else "")
                )
                _report("code_generation", f"代码生成完成 ({generated.generation_time}s)", round_num, 0.2)
            except Exception as e:
                logger.error(f"❌ [第{round_num}轮] 代码生成失败: {e}")
                iteration.decision = "FAIL"
                iteration.feedback = f"代码生成失败: {e}"
                iterations.append(iteration)
                self._persist_round_snapshot(spec.tool_id, run_id, round_num, iteration, fact_report)
                break

            # ===== 阶段 2: 静态验证 =====
            _report("static_validation", "正在语法检查...", round_num, 0.25)
            validation = self._validator.validate(generated, spec)
            iteration.validation = validation

            if not validation.passed:
                feedback = self._build_rich_feedback(
                    stage="静态验证",
                    errors=validation.errors,
                    code=generated.code,
                    spec=spec,
                )
                previous_code = generated.code
                iteration.decision = "RETRY"
                iteration.feedback = feedback
                iterations.append(iteration)
                self._persist_round_snapshot(spec.tool_id, run_id, round_num, iteration, fact_report)
                _report("static_validation", "静态验证失败，重试中...", round_num, 0.3)
                logger.warning(
                    f"⚠️ [第{round_num}轮] 静态验证失败:\n"
                    + "\n".join(f"   ❌ {err}" for err in validation.errors[:5])
                )
                continue

            logger.info(f"✅ [第{round_num}轮] 静态验证通过")
            _report("static_validation", "语法检查通过", round_num, 0.35)

            # ===== 阶段 3: 沙箱执行 =====
            _report("sandbox_execution", "正在沙箱执行...", round_num, 0.4)
            sandbox = self._runner.run(generated.code, spec)
            iteration.sandbox = sandbox

            if not sandbox.success:
                _report("reflection", "正在分析失败原因...", round_num, 0.5)
                logger.warning(
                    f"⚠️ [第{round_num}轮] 沙箱执行失败:\n"
                    f"   错误: {sandbox.error or '未知错误'}\n"
                    f"   stderr: {(sandbox.stderr or '(空)')[:500]}"
                )
                reflection = self._reflect_on_failure(
                    spec=spec,
                    code=generated.code,
                    stage="沙箱执行",
                    error=sandbox.error or "未知错误",
                    stdout=sandbox.stdout,
                    stderr=sandbox.stderr,
                    output=sandbox.output,
                )
                iteration.reflection = reflection
                logger.info(
                    f"🔍 [第{round_num}轮] 反思结果:\n"
                    f"   根因: {reflection.root_cause}\n"
                    f"   修复计划: {reflection.fix_plan}\n"
                    f"   置信度: {reflection.confidence}"
                )

                feedback = self._build_rich_feedback(
                    stage="沙箱执行",
                    errors=[sandbox.error or "未知错误"],
                    code=generated.code,
                    spec=spec,
                    stdout=sandbox.stdout,
                    stderr=sandbox.stderr,
                    output=sandbox.output,
                    reflection=reflection,
                )
                previous_code = generated.code
                iteration.decision = "RETRY"
                iteration.feedback = feedback
                iterations.append(iteration)
                self._persist_round_snapshot(spec.tool_id, run_id, round_num, iteration, fact_report)
                _report("sandbox_execution", "沙箱执行失败，反思后重试中...", round_num, 0.55)
                continue

            # 详细日志：沙箱执行结果
            output_preview = ""
            if sandbox.output is not None:
                try:
                    output_preview = json.dumps(sandbox.output, ensure_ascii=False, default=str)[:500]
                except Exception:
                    output_preview = str(sandbox.output)[:500]
            logger.info(
                f"✅ [第{round_num}轮] 沙箱执行成功\n"
                f"   ⏱️  耗时: {sandbox.execution_time}s\n"
                f"   📤 返回值预览: {output_preview or '(空)'}\n"
                f"   📺 stdout: {(sandbox.stdout or '(空)')[:300]}"
            )
            _report("sandbox_execution", f"沙箱执行成功 ({sandbox.execution_time}s)", round_num, 0.6)

            # ===== 阶段 4: 输出评估 =====
            _report("output_evaluation", "正在质量评估...", round_num, 0.65)
            eval_score = self._evaluator.evaluate(sandbox, spec, generated.code)
            iteration.eval_score = eval_score
            logger.info(
                f"📊 [第{round_num}轮] 评估得分:\n"
                f"   总分: {eval_score.total}/10 (阈值: {PASS_THRESHOLD})\n"
                f"   可执行性: {eval_score.executability} | 真实性: {eval_score.authenticity}\n"
                f"   完整性: {eval_score.completeness} | 相关性: {eval_score.relevance}\n"
                f"   格式质量: {eval_score.format_quality}"
            )

            business_verification = self._business_verifiers.resolve(spec).verify(
                sandbox,
                spec,
                fact_report,
            )
            iteration.business_verification = business_verification
            logger.info(
                f"🧪 [第{round_num}轮] 业务验收:\n"
                f"   通过: {business_verification.passed}\n"
                f"   业务分: {business_verification.business_score}\n"
                f"   失败项: {len(business_verification.failures)}"
            )

            if eval_score.total >= PASS_THRESHOLD and business_verification.passed:
                # ===== 阶段 5: 边缘测试验证 =====
                _report("edge_testing", "正在执行边缘测试验证...", round_num, 0.8)
                edge_failures = self._run_edge_tests(generated.code, spec)

                if edge_failures:
                    logger.warning(
                        f"⚠️ [第{round_num}轮] 边缘测试发现 {len(edge_failures)} 个问题:\n"
                        + "\n".join(f"   ❌ {f}" for f in edge_failures[:5])
                    )
                    _report("reflection", "边缘测试失败，正在分析...", round_num, 0.85)
                    reflection = self._reflect_on_failure(
                        spec=spec,
                        code=generated.code,
                        stage="边缘测试",
                        error="\n".join(edge_failures),
                        stdout=sandbox.stdout,
                        stderr="",
                        output=sandbox.output,
                    )
                    iteration.reflection = reflection

                    feedback = self._build_rich_feedback(
                        stage="边缘测试",
                        errors=edge_failures,
                        code=generated.code,
                        spec=spec,
                        stdout=sandbox.stdout,
                        output=sandbox.output,
                        reflection=reflection,
                    )
                    previous_code = generated.code
                    iteration.decision = "RETRY"
                    iteration.feedback = feedback
                    iterations.append(iteration)
                    self._persist_round_snapshot(spec.tool_id, run_id, round_num, iteration, fact_report)
                    _report("edge_testing", "边缘测试失败，反思后重试中...", round_num, 0.9)
                    continue

                # 全部通过
                iteration.decision = "PASS"
                iterations.append(iteration)
                self._persist_round_snapshot(spec.tool_id, run_id, round_num, iteration, fact_report)
                _report("output_evaluation", f"评估通过，总分: {eval_score.total}", round_num, 1.0)
                total_time = round(time.time() - start_time, 2)
                logger.info(
                    f"\n{'='*60}\n"
                    f"🎉 Skill 生成成功！\n"
                    f"   tool_id: {spec.tool_id}\n"
                    f"   总分: {eval_score.total}/10\n"
                    f"   业务验收: 通过\n"
                    f"   迭代轮数: {round_num}\n"
                    f"   总耗时: {total_time}s\n"
                    f"   代码行数: {len(generated.code.split(chr(10)))}\n"
                    f"{'='*60}"
                )
                return PipelineResult(
                    success=True,
                    tool_id=spec.tool_id,
                    final_code=generated.code,
                    final_metadata=generated.metadata,
                    iterations=iterations,
                    total_rounds=round_num,
                    total_time=round(time.time() - start_time, 2),
                )
            else:
                failure_messages: List[str] = []
                extra_context_parts: List[str] = []
                if eval_score.total < PASS_THRESHOLD:
                    failure_messages.extend(self._build_eval_errors(eval_score))
                    extra_context_parts.append(self._build_eval_reflection_context(eval_score))
                if not business_verification.passed:
                    failure_messages.extend(self._build_business_errors(business_verification))
                    extra_context_parts.append(self._build_business_reflection_context(business_verification))

                reason = (
                    f"评分不足 ({eval_score.total}/10)"
                    if eval_score.total < PASS_THRESHOLD and business_verification.passed
                    else "业务验收未通过"
                    if eval_score.total >= PASS_THRESHOLD and not business_verification.passed
                    else f"评分不足且业务验收未通过 ({eval_score.total}/10)"
                )
                _report("reflection", f"{reason}，正在分析...", round_num, 0.75)
                reflection = self._reflect_on_failure(
                    spec=spec,
                    code=generated.code,
                    stage="质量评估/业务验收",
                    error="\n".join(failure_messages),
                    stdout=sandbox.stdout,
                    stderr=sandbox.stderr,
                    output=sandbox.output,
                    extra_context="\n\n".join(part for part in extra_context_parts if part),
                )
                iteration.reflection = reflection
                logger.info(
                    f"🔍 [第{round_num}轮] 反思结果:\n"
                    f"   根因: {reflection.root_cause}\n"
                    f"   修复计划: {reflection.fix_plan}\n"
                    f"   置信度: {reflection.confidence}"
                )

                feedback = self._build_rich_feedback(
                    stage="质量评估/业务验收",
                    errors=failure_messages,
                    code=generated.code,
                    spec=spec,
                    stdout=sandbox.stdout,
                    stderr=sandbox.stderr,
                    output=sandbox.output,
                    reflection=reflection,
                )
                previous_code = generated.code
                iteration.decision = "RETRY"
                iteration.feedback = feedback
                iterations.append(iteration)
                self._persist_round_snapshot(spec.tool_id, run_id, round_num, iteration, fact_report)
                _report("output_evaluation", f"{reason}，反思后重试中...", round_num, 0.8)
                logger.warning(f"⚠️ [第{round_num}轮] {reason}，进入下一轮")

        failure_summary = self._build_failure_summary(iterations)
        total_time = round(time.time() - start_time, 2)
        logger.error(
            f"\n{'='*60}\n"
            f"❌ Skill 生成失败 — {self._max_iterations} 轮迭代后仍未通过\n"
            f"   tool_id: {spec.tool_id}\n"
            f"   总耗时: {total_time}s\n"
            f"{'='*60}"
        )
        return PipelineResult(
            success=False,
            tool_id=spec.tool_id,
            iterations=iterations,
            total_rounds=self._max_iterations,
            total_time=round(time.time() - start_time, 2),
            error=failure_summary,
        )

    # ==================== 即时落盘 ====================

    @staticmethod
    def _get_snapshot_dir(tool_id: str, run_id: str) -> Path:
        """获取当前运行批次的快照目录: data/code/skill/{tool_id}/{run_id}/"""
        d = _SNAPSHOT_DIR / tool_id / run_id
        d.mkdir(parents=True, exist_ok=True)
        return d

    @staticmethod
    def _persist_fact_report(
        tool_id: str,
        run_id: str,
        fact_report: ImplementationFactReport,
    ) -> Optional[Path]:
        """侦察完成后立即落盘 fact_report.json。"""
        try:
            d = IterationController._get_snapshot_dir(tool_id, run_id)
            path = d / "fact_report.json"
            data = fact_report.model_dump(mode="json")
            path.write_text(
                json.dumps(data, ensure_ascii=False, indent=2, default=str),
                encoding="utf-8",
            )
            logger.info("📝 侦察报告已落盘: %s", path)
            return path
        except Exception as exc:
            logger.warning("⚠️ 侦察报告落盘失败: %s", exc)
            return None

    @staticmethod
    def _persist_round_snapshot(
        tool_id: str,
        run_id: str,
        round_num: int,
        iteration: IterationRound,
        fact_report: Optional[ImplementationFactReport] = None,
    ) -> Optional[Path]:
        """每轮迭代结束后立即落盘该轮完整快照（含代码、评分、反思等）。"""
        try:
            d = IterationController._get_snapshot_dir(tool_id, run_id)
            snapshot: Dict[str, Any] = {
                "round_number": round_num,
                "decision": iteration.decision,
                "feedback_excerpt": (iteration.feedback or "")[:2000],
            }
            # 生成的代码
            if iteration.generated_code:
                g = iteration.generated_code
                snapshot["generated_code"] = {
                    "code_lines": len((g.code or "").split("\n")),
                    "generation_time": g.generation_time,
                    "metadata": g.metadata,
                }
                # 同时保存完整代码文件
                code_path = d / f"round_{round_num:02d}.py"
                code_path.write_text(
                    (g.code or "") + "\n", encoding="utf-8"
                )
            # 静态验证
            if iteration.validation:
                snapshot["validation"] = {
                    "passed": iteration.validation.passed,
                    "errors": iteration.validation.errors[:10],
                }
            # 沙箱执行
            if iteration.sandbox:
                sb = iteration.sandbox
                snapshot["sandbox"] = {
                    "success": sb.success,
                    "execution_time": sb.execution_time,
                    "error": (sb.error or "")[:500],
                    "stdout_excerpt": (sb.stdout or "")[:500],
                    "output_excerpt": str(sb.output)[:1000] if sb.output else None,
                }
            # 评估得分
            if iteration.eval_score:
                snapshot["eval_score"] = iteration.eval_score.model_dump()
            # 业务验收
            if iteration.business_verification:
                bv = iteration.business_verification
                snapshot["business_verification"] = {
                    "passed": bv.passed,
                    "business_score": bv.business_score,
                    "failures": bv.failures[:10],
                }
            # 反思
            if iteration.reflection:
                r = iteration.reflection
                snapshot["reflection"] = {
                    "root_cause": r.root_cause,
                    "fix_plan": r.fix_plan,
                    "should_retry": r.should_retry,
                    "confidence": r.confidence,
                }
            # 附带当轮的侦察报告引用（置信度+策略摘要即可）
            if fact_report:
                snapshot["fact_report_summary"] = {
                    "confidence": fact_report.confidence,
                    "strategy": (fact_report.recommended_strategy or "")[:200],
                    "helpers_count": len(fact_report.available_helpers),
                    "checks_count": len(fact_report.validation_checks),
                }

            path = d / f"round_{round_num:02d}_snapshot.json"
            path.write_text(
                json.dumps(snapshot, ensure_ascii=False, indent=2, default=str),
                encoding="utf-8",
            )
            logger.info("📝 第%d轮快照已落盘: %s", round_num, path)
            return path
        except Exception as exc:
            logger.warning("⚠️ 第%d轮快照落盘失败: %s", round_num, exc)
            return None

    @staticmethod
    def _build_reconnaissance_updates(fact_report: ImplementationFactReport) -> List[str]:
        updates: List[str] = []
        if fact_report.recommended_strategy:
            updates.append(f"侦察策略：{fact_report.recommended_strategy}")

        collections = [
            item.source
            for item in fact_report.schema_facts
            if item.source.startswith("stock_") or item.source == "market_quotes"
        ]
        if collections:
            unique_collections = list(dict.fromkeys(collections))[:3]
            updates.append(f"命中本地集合：{'、'.join(unique_collections)}")

        if fact_report.available_helpers:
            helper_names = [f"{item.module}.{item.name}" for item in fact_report.available_helpers[:3]]
            updates.append(f"推荐 helper：{'；'.join(helper_names)}")

        if fact_report.sample_fields:
            sample_parts: List[str] = []
            for collection, fields in list(fact_report.sample_fields.items())[:2]:
                sample_parts.append(f"{collection}: {', '.join(fields[:6])}")
            if sample_parts:
                updates.append(f"样本字段：{'；'.join(sample_parts)}")

        if fact_report.runtime_gaps:
            gap_parts = [item.reason for item in fact_report.runtime_gaps[:2] if item.reason]
            if gap_parts:
                updates.append(f"侦察提示：{'；'.join(gap_parts)}")

        if fact_report.validation_checks:
            check_parts = [check.field or check.name for check in fact_report.validation_checks[:4]]
            updates.append(f"动态验收字段：{'、'.join(check_parts)}")

        return updates[:6]

    async def arun(self, spec: SkillSpec) -> PipelineResult:
        """异步版本的 run"""
        import asyncio
        return await asyncio.get_event_loop().run_in_executor(None, self.run, spec)

    # ==================== 反思机制 ====================

    def _reflect_on_failure(
        self,
        *,
        spec: SkillSpec,
        code: str,
        stage: str,
        error: str,
        stdout: str = "",
        stderr: str = "",
        output: Any = None,
        extra_context: str = "",
    ) -> ReflectionResult:
        """
        LLM 反思 — 在每轮失败后分析根因并制定修复计划。

        借鉴 OpenClaw 的 Agent Loop：让 LLM 看到完整的执行上下文后
        做出判断，而非机械地转发错误消息。
        """
        output_preview = ""
        if output is not None:
            try:
                output_preview = json.dumps(output, ensure_ascii=False, indent=2, default=str)[:2000]
            except Exception:
                output_preview = str(output)[:2000]

        code_context = self._format_code_for_prompt(code)
        extra_context_block = f"\n【补充上下文】\n{extra_context}\n" if extra_context else ""

        prompt = f"""你是一位资深 Python 开发者。一个自动生成的工具函数在「{stage}」阶段失败了。
请分析根因并给出精准的修复计划。

【Skill 目标】
- tool_id: {spec.tool_id}
- 功能: {spec.description}
- 数据源: {spec.data_source or '未指定'}

【生成的代码】
```python
{code_context}
```

{extra_context_block}

【失败信息】
{error}

【标准输出 stdout】
{(stdout or '(空)')[:1500]}

【标准错误 stderr】
{(stderr or '(空)')[:1500]}

【函数返回值】
{output_preview or '(空)'}

请用 JSON 格式回复，不要输出其他内容：
{{"root_cause": "一句话说明根因", "fix_plan": ["修复步骤1", "修复步骤2", ...], "should_retry": true/false, "confidence": 0.0-1.0}}
"""
        try:
            client = self._get_client()
            logger.info(
                f"\n{'─'*50}\n"
                f"📤 [Reflection] LLM 输入 ({len(prompt)} 字符)\n"
                f"{'─'*50}\n"
                f"{prompt[:3000]}\n"
                f"{'...(截断)' if len(prompt) > 3000 else ''}\n"
                f"{'─'*50}"
            )
            response = client.chat([Message(role="user", content=prompt)])
            raw = (response.content or "").strip()
            logger.info(
                f"\n{'─'*50}\n"
                f"📥 [Reflection] LLM 输出 ({len(raw)} 字符)\n"
                f"{'─'*50}\n"
                f"{raw}\n"
                f"{'─'*50}"
            )

            import re
            json_match = re.search(r"\{[^}]+\}", raw, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
                return ReflectionResult(
                    root_cause=data.get("root_cause", "未知"),
                    fix_plan=data.get("fix_plan", []),
                    should_retry=data.get("should_retry", True),
                    confidence=float(data.get("confidence", 0.5)),
                )
        except Exception as e:
            logger.warning(f"LLM 反思分析失败，使用默认反馈: {e}")

        return ReflectionResult(
            root_cause=f"{stage}阶段失败: {error[:200]}",
            fix_plan=["修复上述报错", "确保代码可正常执行"],
            should_retry=True,
            confidence=0.3,
        )

    # ==================== 边缘测试 ====================

    def _run_edge_tests(self, code: str, spec: SkillSpec) -> List[str]:
        """
        在主测试通过后，运行额外的边缘测试场景：
        1. 空/无效参数测试 — 函数不应崩溃
        2. LLM 生成的测试用例 — 检查是否有 mock 数据
        """
        failures: List[str] = []

        edge_inputs = self._generate_edge_inputs(spec)
        for label, test_input in edge_inputs:
            try:
                result = self._runner.run(code, spec, test_input=test_input)
                if not result.success:
                    failures.append(f"边缘测试「{label}」执行崩溃: {result.error or '未知'}")
                elif result.output is not None:
                    output_str = json.dumps(result.output, ensure_ascii=False, default=str)
                    if self._looks_like_mock_data(output_str):
                        failures.append(f"边缘测试「{label}」返回疑似模拟数据")
            except Exception as e:
                failures.append(f"边缘测试「{label}」异常: {e}")

        return failures

    @staticmethod
    def _generate_edge_inputs(spec: SkillSpec) -> List[tuple]:
        """根据 spec 参数定义生成边缘测试输入"""
        edges: List[tuple] = []

        has_symbol = any(
            p.name in ("symbol", "ticker", "stock_code", "code")
            for p in spec.parameters
        )
        if has_symbol:
            edge_args = dict(spec.test_input) if spec.test_input else {}
            symbol_key = next(
                (p.name for p in spec.parameters
                 if p.name in ("symbol", "ticker", "stock_code", "code")),
                None,
            )
            if symbol_key:
                edge_args[symbol_key] = "999999"
                edges.append(("不存在的股票代码", edge_args))

        return edges

    @staticmethod
    def _looks_like_mock_data(output_str: str) -> bool:
        mock_indicators = [
            '"mock"', '"模拟"', '"fake"', '"dummy"', '"placeholder"',
            '"示例数据"', '"测试数据"', '"sample"',
            "_generate_mock", "generate_fake", "random.uniform",
        ]
        lower = output_str.lower()
        return any(ind.lower() in lower for ind in mock_indicators)

    # ==================== 失败报告 ====================

    @staticmethod
    def _build_failure_summary(iterations: List[IterationRound]) -> str:
        """
        汇总所有迭代轮次的失败原因，生成结构化的失败报告。
        """
        parts = [f"经过 {len(iterations)} 轮迭代仍未达到质量标准（≥{PASS_THRESHOLD}/10 分）。各轮失败原因如下：\n"]

        for it in iterations:
            header = f"【第 {it.round_number} 轮 — 决策: {it.decision or 'UNKNOWN'}】"
            parts.append(header)

            if it.validation and not it.validation.passed:
                parts.append(f"  静态验证失败:")
                for err in it.validation.errors[:3]:
                    parts.append(f"    - {err}")

            if it.sandbox and not it.sandbox.success:
                parts.append(f"  沙箱执行失败: {it.sandbox.error or '未知错误'}")

            if it.eval_score:
                parts.append(
                    f"  评分: 总分={it.eval_score.total}, "
                    f"可执行性={it.eval_score.executability}, "
                    f"真实性={it.eval_score.authenticity}, "
                    f"完整性={it.eval_score.completeness}, "
                    f"相关性={it.eval_score.relevance}, "
                    f"格式={it.eval_score.format_quality}"
                )
                weak = []
                if it.eval_score.executability < 8.0:
                    weak.append(f"可执行性({it.eval_score.executability})")
                if it.eval_score.authenticity < 8.0:
                    weak.append(f"真实性({it.eval_score.authenticity})")
                if it.eval_score.completeness < 8.0:
                    weak.append(f"完整性({it.eval_score.completeness})")
                if it.eval_score.relevance < 8.0:
                    weak.append(f"相关性({it.eval_score.relevance})")
                if it.eval_score.format_quality < 8.0:
                    weak.append(f"格式质量({it.eval_score.format_quality})")
                if weak:
                    parts.append(f"  不达标维度: {', '.join(weak)}")

            if it.business_verification:
                parts.append(
                    f"  业务验收: passed={it.business_verification.passed}, "
                    f"business_score={it.business_verification.business_score}"
                )
                if it.business_verification.failures:
                    parts.append(
                        "  业务失败项: "
                        + "; ".join(f.message for f in it.business_verification.failures[:5])
                    )

            if it.reflection and it.reflection.root_cause:
                parts.append(f"  根因分析: {it.reflection.root_cause}")

            parts.append("")

        return "\n".join(parts).strip()

    @staticmethod
    def _build_business_errors(result: BusinessVerificationResult) -> List[str]:
        errors = [failure.message for failure in result.failures]
        if not errors and not result.passed:
            errors.append("业务验收未通过")
        return errors

    @staticmethod
    def _build_business_reflection_context(result: BusinessVerificationResult) -> str:
        lines = [
            f"- 业务验收通过: {result.passed}",
            f"- 业务分: {result.business_score}/10",
            f"- 验收器: {result.details.get('verifier', 'unknown')}",
        ]
        if result.failures:
            lines.append("- 失败规则:")
            for failure in result.failures[:5]:
                lines.append(f"  - {failure.rule_id}: {failure.message}")
        if result.warnings:
            lines.append("- 警告:")
            for warning in result.warnings[:5]:
                lines.append(f"  - {warning}")
        return "\n".join(lines)

    @staticmethod
    def _format_code_for_prompt(
        code: str,
        *,
        max_chars: int = 12000,
        full_code_line_limit: int = 260,
        head_lines: int = 140,
        tail_lines: int = 100,
    ) -> str:
        """为反思阶段优先保留完整代码，超长时再保留首尾关键片段。"""
        if not code:
            return ""

        lines = code.splitlines()
        if len(code) <= max_chars and len(lines) <= full_code_line_limit:
            return code

        if len(lines) <= head_lines + tail_lines:
            combined = code
        else:
            combined = (
                "\n".join(lines[:head_lines])
                + f"\n# ... (中间省略，共 {len(lines)} 行) ...\n"
                + "\n".join(lines[-tail_lines:])
            )

        if len(combined) <= max_chars:
            return combined

        keep_each_side = max((max_chars - 32) // 2, 1000)
        return (
            combined[:keep_each_side]
            + "\n# ... (中间省略) ...\n"
            + combined[-keep_each_side:]
        )

    @staticmethod
    def _build_eval_reflection_context(score) -> str:
        """把评估分项显式传给反思模型，避免它只看到总分不足。"""
        lines = [
            f"- 总分: {score.total}/10（阈值: {PASS_THRESHOLD}）",
            f"- 可执行性: {score.executability}/10",
            f"- 真实性: {score.authenticity}/10",
            f"- 完整性: {score.completeness}/10",
            f"- 相关性: {score.relevance}/10",
            f"- 格式质量: {score.format_quality}/10",
        ]

        weak_dims = []
        if score.executability < PASS_THRESHOLD:
            weak_dims.append(f"可执行性({score.executability})")
        if score.authenticity < PASS_THRESHOLD:
            weak_dims.append(f"真实性({score.authenticity})")
        if score.completeness < PASS_THRESHOLD:
            weak_dims.append(f"完整性({score.completeness})")
        if score.relevance < PASS_THRESHOLD:
            weak_dims.append(f"相关性({score.relevance})")
        if score.format_quality < PASS_THRESHOLD:
            weak_dims.append(f"格式质量({score.format_quality})")

        if weak_dims:
            lines.append(f"- 不达标维度: {', '.join(weak_dims)}")

        return "\n".join(lines)

    # ==================== 反馈构建 ====================

    @staticmethod
    def _build_rich_feedback(
        *,
        stage: str,
        errors: List[str],
        code: str,
        spec: SkillSpec,
        stdout: str = "",
        stderr: str = "",
        output: Any = None,
        reflection: Optional[ReflectionResult] = None,
    ) -> str:
        """
        构建丰富的反馈上下文 — 包含完整的执行信息和 LLM 反思分析。
        """
        parts = [f"【{stage}失败 — 第 N 轮迭代反馈】"]

        parts.append("\n## 错误详情")
        for e in errors[:8]:
            parts.append(f"  - {e}")

        if stdout:
            parts.append(f"\n## 标准输出 (stdout 截断)\n{stdout[:1500]}")

        if stderr:
            parts.append(f"\n## 标准错误 (stderr 截断)\n{stderr[:1500]}")

        if output is not None:
            try:
                output_str = json.dumps(output, ensure_ascii=False, indent=2, default=str)[:2000]
            except Exception:
                output_str = str(output)[:2000]
            parts.append(f"\n## 函数实际返回值\n{output_str}")

        if reflection:
            parts.append(f"\n## AI 根因分析\n{reflection.root_cause}")
            if reflection.fix_plan:
                parts.append("\n## 修复计划")
                for i, step in enumerate(reflection.fix_plan, 1):
                    parts.append(f"  {i}. {step}")

        parts.append("\n## 修复要求")
        parts.append("请根据以上完整的执行上下文，定向修复代码中的问题。")
        parts.append("优先解决导致失败的根因，不要重新设计整体架构。")
        parts.append("保留已经正确工作的部分，只修改有问题的代码。")

        return "\n".join(parts)

    @staticmethod
    def _build_eval_errors(score) -> List[str]:
        """根据评分构建具体问题列表"""
        errors = []
        if score.executability < 7.0:
            errors.append(f"可执行性不足 ({score.executability}/10)")
        if score.authenticity < 7.0:
            errors.append(f"返回数据不够真实 ({score.authenticity}/10)")
        if score.completeness < 7.0:
            errors.append(f"功能不够完整 ({score.completeness}/10)")
        if score.relevance < 7.0:
            errors.append(f"与需求相关性不足 ({score.relevance}/10)")
        if score.format_quality < 7.0:
            errors.append(f"输出格式质量不足 ({score.format_quality}/10)")
        return errors or [f"综合评分 {score.total}/10 低于阈值 {PASS_THRESHOLD}"]

    @staticmethod
    def _build_feedback(stage: str, errors: list) -> str:
        """旧版简单反馈（保留兼容性）"""
        error_lines = "\n".join(f"  - {e}" for e in errors[:5])
        return f"【{stage}失败】\n{error_lines}"

    @staticmethod
    def _build_eval_feedback(score) -> str:
        """旧版评分反馈（保留兼容性）"""
        parts = []
        if score.executability < 7.0:
            parts.append(f"可执行性不足 ({score.executability}/10)")
        if score.authenticity < 7.0:
            parts.append(f"返回数据不够真实 ({score.authenticity}/10)")
        if score.completeness < 7.0:
            parts.append(f"功能不够完整 ({score.completeness}/10)")
        if score.relevance < 7.0:
            parts.append(f"与需求相关性不足 ({score.relevance}/10)")
        if score.format_quality < 7.0:
            parts.append(f"输出格式质量不足 ({score.format_quality}/10)")
        feedback_lines = "\n".join(f"  - {p}" for p in parts)
        return f"【评分不足 ({score.total}/10)】\n{feedback_lines}\n请针对以上维度改进代码。"
