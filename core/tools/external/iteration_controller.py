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
  FAIL  — 超过 10 轮仍未通过，并附带每轮失败原因
"""

import json
import logging
import re
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from core.llm import UnifiedLLMClient, Message
from core.llm.tool_normalizer import ToolCallNormalizer

from .business_verifier import BusinessVerifierRegistry
from .code_generator import CODEGEN_LLM_TIMEOUT_SECONDS, CodeGenerator
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

MAX_ITERATIONS = 10
PASS_THRESHOLD = 8.5
# 连续相同失败检测阈值：连续 N 轮业务验收失败项完全一致则判定为不可恢复
# 由 5 调整为 3：更早触发熔断，避免在不可恢复的失败上浪费迭代预算
_STALE_FAILURE_THRESHOLD = 3

# 快照落盘根目录（与 SkillGenerationService 保持一致）
_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_SNAPSHOT_DIR = _PROJECT_ROOT / "data" / "code" / "skill"


@dataclass
class PipelineToolResult:
    """Agentic Loop 中单轮 pipeline_tool 的结构化结果。"""

    status: str = "fail"  # pass / fail / blocked
    round_number: int = 1
    iteration: Optional[IterationRound] = None
    code_path: str = ""
    snapshot_path: str = ""
    static_validation: Dict[str, Any] = field(default_factory=dict)
    sandbox_result: Dict[str, Any] = field(default_factory=dict)
    evaluation: Dict[str, Any] = field(default_factory=dict)
    failure_summary: str = ""
    verified_facts: List[str] = field(default_factory=list)
    should_retry: bool = True
    final_code: str = ""
    final_metadata: Dict[str, Any] = field(default_factory=dict)

    def to_public_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "round_number": self.round_number,
            "code_path": self.code_path,
            "snapshot_path": self.snapshot_path,
            "static_validation": self.static_validation,
            "sandbox_result": self.sandbox_result,
            "evaluation": self.evaluation,
            "failure_summary": self.failure_summary,
            "verified_facts": self.verified_facts,
            "should_retry": self.should_retry,
            "has_final_code": bool(self.final_code),
        }


class _AgenticPipelineAbort(Exception):
    """pipeline_tool 内部遇到不可恢复失败时用于中断单轮执行。"""

    def __init__(self, result: PipelineToolResult):
        self.result = result
        super().__init__(result.failure_summary or result.status)


class IterationController:
    """
    迭代控制器

    编排 CodeGenerator → StaticValidator → SandboxRunner → OutputEvaluator
    的完整管线，在每轮失败时插入 LLM 反思步骤，最多 10 轮自动重试。
    """

    def __init__(
        self,
        llm_client: Optional[UnifiedLLMClient] = None,
        provider: str = "deepseek",
        model: Optional[str] = None,
        max_iterations: int = MAX_ITERATIONS,
        skip_judge: bool = False,
        reconnaissance_controller: Optional[ReconnaissanceController] = None,
        quick_llm_client: Optional[UnifiedLLMClient] = None,
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
            quick_llm_client=quick_llm_client,
        )
        self._business_verifiers = BusinessVerifierRegistry(
            llm_client=llm_client,
            provider=provider,
            model=model,
        )
        self._reconnaissance = reconnaissance_controller or DefaultReconnaissanceController()
        self._llm_client = llm_client
        self._provider = provider
        self._model = model
        self._max_iterations = max_iterations
        self._agentic_trace: List[Dict[str, Any]] = []

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
        fact_report: Optional[ImplementationFactReport] = None,
        codegen_timeout: Optional[int] = None,
        thinking_callback: Optional[Callable[[str, str], None]] = None,
        iteration_mode: str = "repair",
    ) -> PipelineResult:
        """
        执行完整的生成管线

        Args:
            spec: Skill 规格书（已确认）
            initial_feedback: 初始反馈（优化场景使用）
            initial_code: 初始代码（优化场景使用）
            progress_callback: 进度回调 (stage, message, iteration, progress)
            fact_report: 预构建的侦察报告（侦察前置模式），为 None 时内部自动执行侦察
            codegen_timeout: 代码生成单次 LLM 调用超时（秒），None 用默认值
            thinking_callback: 思考过程回调 on_thinking(kind, text)，透传给代码生成器实时展示
            iteration_mode: "repair"=失败后定向修复；"upgrade"=在已验证旧版本上最小改动升级

        Returns:
            PipelineResult: 管线最终结果
        """
        start_time = time.time()
        run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        iterations: List[IterationRound] = []
        feedback = initial_feedback
        previous_code = initial_code

        def _report(stage: str, message: str, it: int, prog: float, extra: Optional[Dict[str, Any]] = None):
            if progress_callback:
                try:
                    progress_callback(stage, message, it, prog, extra)
                except Exception as e:
                    logger.warning(f"progress_callback 异常: {e}")

        if fact_report is not None:
            # 侦察前置模式：复用上游已完成的侦察报告
            logger.info(
                "🧭 复用上游侦察报告 | strategy=%s | helpers=%d | checks=%d",
                fact_report.recommended_strategy or "(none)",
                len(fact_report.available_helpers),
                len(fact_report.validation_checks),
            )
            self._persist_fact_report(spec.tool_id, run_id, fact_report)
        else:
            # 内部侦察模式（向后兼容）
            try:
                _report("reconnaissance", "正在整理实现事实...", 0, 0.03)
                fact_report = self._reconnaissance.analyze(spec)
                logger.info(
                    "🧭 前置侦察完成 | strategy=%s | helpers=%d | checks=%d",
                    fact_report.recommended_strategy or "(none)",
                    len(fact_report.available_helpers),
                    len(fact_report.validation_checks),
                )
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
                    timeout_seconds=codegen_timeout,
                    on_thinking=thinking_callback,
                    # 仅首轮（基于父版本代码）用升级文案；后续轮是在修新代码的问题
                    iteration_mode=("upgrade" if iteration_mode == "upgrade" and round_num == 1 else "repair"),
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
                self._persist_stage_artifact(
                    tool_id=spec.tool_id,
                    run_id=run_id,
                    round_num=round_num,
                    stage="code_generation",
                    payload={
                        "success": True,
                        "generation_time": generated.generation_time,
                        "code_lines": len(code_lines),
                        "metadata": generated.metadata or {},
                    },
                    code=generated.code,
                )
                _report("code_generation", f"代码生成完成 ({generated.generation_time}s)", round_num, 0.2)
            except Exception as e:
                logger.error(f"❌ [第{round_num}轮] 代码生成失败: {e}")
                self._persist_stage_artifact(
                    tool_id=spec.tool_id,
                    run_id=run_id,
                    round_num=round_num,
                    stage="code_generation",
                    payload={
                        "success": False,
                        "error": str(e),
                    },
                )
                iteration.decision = "FAIL"
                iteration.feedback = f"代码生成失败: {e}"
                iterations.append(iteration)
                self._persist_round_snapshot(spec.tool_id, run_id, round_num, iteration, fact_report)
                break

            # ===== 阶段 2: 静态验证 =====
            _report("static_validation", "正在语法检查...", round_num, 0.25)
            validation = self._validator.validate(generated, spec)
            iteration.validation = validation
            self._persist_stage_artifact(
                tool_id=spec.tool_id,
                run_id=run_id,
                round_num=round_num,
                stage="static_validation",
                payload={
                    "passed": validation.passed,
                    "errors": validation.errors[:20],
                    "warnings": (validation.warnings or [])[:20],
                },
                code=generated.code,
            )

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
            self._persist_stage_artifact(
                tool_id=spec.tool_id,
                run_id=run_id,
                round_num=round_num,
                stage="sandbox_execution",
                payload={
                    "success": sandbox.success,
                    "execution_time": sandbox.execution_time,
                    "error": sandbox.error,
                    "stdout": sandbox.stdout,
                    "stderr": sandbox.stderr,
                    "output": sandbox.output,
                },
                code=generated.code,
            )

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
                    fact_report=fact_report,
                sandbox_success=getattr(sandbox, "success", False),
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
                # ---- 提前退出：反思建议放弃 ----
                if not reflection.should_retry:
                    iteration.decision = "FAIL"
                    iteration.feedback = feedback
                    iterations.append(iteration)
                    self._persist_round_snapshot(spec.tool_id, run_id, round_num, iteration, fact_report)
                    _report("sandbox_execution", "反思判定不可修复，提前终止", round_num, 0.55)
                    logger.warning(
                        f"🛑 [第{round_num}轮] 反思建议放弃 (should_retry=False): {reflection.root_cause}"
                    )
                    break
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

            # ===== 阶段 4: 业务验收（结构检查，零 LLM 成本） =====
            business_verification = self._business_verifiers.resolve(spec).verify(
                sandbox,
                spec,
                fact_report,
            )
            iteration.business_verification = business_verification
            self._persist_stage_artifact(
                tool_id=spec.tool_id,
                run_id=run_id,
                round_num=round_num,
                stage="business_verification",
                payload={
                    "passed": business_verification.passed,
                    "business_score": business_verification.business_score,
                    "failures": [failure.model_dump() for failure in business_verification.failures[:20]],
                    "warnings": business_verification.warnings[:20],
                    "details": business_verification.details,
                },
                code=generated.code,
            )
            logger.info(
                f"🧪 [第{round_num}轮] 业务验收:\n"
                f"   通过: {business_verification.passed}\n"
                f"   业务分: {business_verification.business_score}\n"
                f"   失败项: {len(business_verification.failures)}"
            )

            if not business_verification.passed:
                # 业务验收不通过，收集错误反馈
                _report("output_evaluation", "业务验收未通过，正在分析...", round_num, 0.58)
                failure_messages = []
                failure_messages.extend(self._build_business_errors(business_verification))
                extra_context_parts = [self._build_business_reflection_context(business_verification)]

                # 【新增】财经专家判断：如果沙箱输出包含 no_data，判断是否业务合理 + 推荐换股
                expert_advice = self._check_no_data_and_advise(
                    spec, sandbox.output, fact_report
                )
                if expert_advice:
                    extra_context_parts.append(expert_advice)

                reflection = self._reflect_on_failure(
                    spec=spec,
                    code=generated.code,
                    stage="业务验收",
                    error="\n".join(failure_messages),
                    stdout=sandbox.stdout,
                    stderr=sandbox.stderr,
                    output=sandbox.output,
                    fact_report=fact_report,
                    sandbox_success=getattr(sandbox, "success", False),
                    extra_context="\n\n".join(part for part in extra_context_parts if part),
                )
                iteration.reflection = reflection
                feedback = self._build_rich_feedback(
                    stage="业务验收",
                    errors=failure_messages,
                    code=generated.code,
                    spec=spec,
                    stdout=sandbox.stdout,
                    stderr=sandbox.stderr,
                    output=sandbox.output,
                    reflection=reflection,
                )
                # 把专家建议追加到 feedback
                if expert_advice:
                    feedback = f"{feedback}\n\n{expert_advice}"
                iteration.decision = "RETRY"
                iteration.feedback = feedback
                iterations.append(iteration)
                self._persist_round_snapshot(spec.tool_id, run_id, round_num, iteration, fact_report)
                _report("output_evaluation", "业务验收失败，反思后重试中...", round_num, 0.7)
                continue

            # ===== 阶段 5: 黑盒验证 — 标准函数参考对比 =====
            _report("reference_comparison", "正在对比标准函数输出...", round_num, 0.65)
            ref_comparison_failures = self._compare_with_reference_helpers(
                sandbox, spec, fact_report
            )
            if ref_comparison_failures:
                logger.warning(
                    f"⚠️ [第{round_num}轮] 🔴 黑盒验证失败: 输出值不符合标准函数参考\n"
                    + "\n".join(f"   ❌ {f}" for f in ref_comparison_failures[:5])
                )
                _report("reflection", "黑盒验证失败（值不正确），跳过白盒代码审查，正在分析...", round_num, 0.68)
                reflection = self._reflect_on_failure(
                    spec=spec,
                    code=generated.code,
                    stage="黑盒验证（标准函数参考对比）",
                    error="\n".join(ref_comparison_failures),
                    stdout=sandbox.stdout,
                    stderr="",
                    output=sandbox.output,
                    fact_report=fact_report,
                sandbox_success=getattr(sandbox, "success", False),
            )
                iteration.reflection = reflection
                feedback = self._build_rich_feedback(
                    stage="黑盒验证（标准函数参考对比）",
                    errors=ref_comparison_failures,
                    code=generated.code,
                    spec=spec,
                    stdout=sandbox.stdout,
                    output=sandbox.output,
                    reflection=reflection,
                )
                iteration.decision = "RETRY"
                iteration.feedback = feedback
                iterations.append(iteration)
                self._persist_round_snapshot(spec.tool_id, run_id, round_num, iteration, fact_report)
                _report("reference_comparison", "黑盒验证失败，反思后重试中...", round_num, 0.72)
                continue

            _report("reference_comparison", "黑盒验证通过，输出值与标准函数一致", round_num, 0.7)

            # ===== 阶段 6: 白盒评估 — Judge LLM 代码审查 =====
            _report("output_evaluation", "正在白盒代码质量评估...", round_num, 0.75)
            eval_score = self._evaluator.evaluate(sandbox, spec, generated.code, fact_report=fact_report)
            iteration.eval_score = eval_score
            self._persist_stage_artifact(
                tool_id=spec.tool_id,
                run_id=run_id,
                round_num=round_num,
                stage="output_evaluation",
                payload={
                    "eval_score": iteration.eval_score.model_dump(),
                },
                code=generated.code,
            )
            logger.info(
                f"📊 [第{round_num}轮] 评估得分:\n"
                f"   总分: {eval_score.total}/10 (阈值: {PASS_THRESHOLD})\n"
                f"   可执行性: {eval_score.executability} | 真实性: {eval_score.authenticity}\n"
                f"   完整性: {eval_score.completeness} | 相关性: {eval_score.relevance}\n"
                f"   格式质量: {eval_score.format_quality}"
            )
            # 评估结果实时透出：前端在评估完成的瞬间即可看到各维度分数与评语
            _eval_passed = eval_score.total >= PASS_THRESHOLD
            _report(
                "output_evaluation",
                f"质量评估完成：{eval_score.total}/10（{'达标' if _eval_passed else '未达标'}）",
                round_num,
                0.77,
                extra=self._build_eval_result_extra(eval_score, round_num),
            )

            if eval_score.total < PASS_THRESHOLD:
                _report("reflection", f"白盒评审未通过 ({eval_score.total}/10)，正在分析...", round_num, 0.78)
                failure_messages = []
                failure_messages.extend(self._build_eval_errors(eval_score))
                extra_context = []
                extra_context.append(self._build_eval_reflection_context(eval_score))
                reflection = self._reflect_on_failure(
                    spec=spec,
                    code=generated.code,
                    stage="白盒代码评审",
                    error="\n".join(failure_messages),
                    stdout=sandbox.stdout,
                    stderr="",
                    output=sandbox.output,
                    fact_report=fact_report,
                sandbox_success=getattr(sandbox, "success", False),
            )
                iteration.reflection = reflection
                feedback = self._build_rich_feedback(
                    stage="白盒代码评审",
                    errors=failure_messages,
                    code=generated.code,
                    spec=spec,
                    stdout=sandbox.stdout,
                    output=sandbox.output,
                    reflection=reflection,
                )
                iteration.decision = "RETRY"
                iteration.feedback = feedback
                iterations.append(iteration)
                self._persist_round_snapshot(spec.tool_id, run_id, round_num, iteration, fact_report)
                _report("output_evaluation", "白盒评审未通过，反思后重试中...", round_num, 0.82)
                continue

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
                        fact_report=fact_report,
                        sandbox_success=getattr(sandbox, "success", False),
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
                    fact_report=fact_report,
                    sandbox_success=getattr(sandbox, "success", False),
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

                # ---- 提前退出：反思建议放弃 ----
                if not reflection.should_retry:
                    iteration.decision = "FAIL"
                    iteration.feedback = feedback
                    iterations.append(iteration)
                    self._persist_round_snapshot(spec.tool_id, run_id, round_num, iteration, fact_report)
                    _report("output_evaluation", "反思判定不可修复，提前终止", round_num, 0.8)
                    logger.warning(
                        f"🛑 [第{round_num}轮] 反思建议放弃 (should_retry=False): {reflection.root_cause}"
                    )
                    break

                # ---- 提前退出：连续相同失败检测 ----
                if self._detect_stale_failures(iterations):
                    iteration.decision = "FAIL"
                    iteration.feedback = feedback + "\n\n[系统] 连续多轮业务验收失败项完全相同，判定为数据源不可用，提前终止。"
                    iterations.append(iteration)
                    self._persist_round_snapshot(spec.tool_id, run_id, round_num, iteration, fact_report)
                    _report("output_evaluation", "连续相同失败，数据不可用，提前终止", round_num, 0.8)
                    logger.warning(
                        f"🛑 [第{round_num}轮] 连续 {_STALE_FAILURE_THRESHOLD} 轮相同业务验收失败，判定为不可恢复"
                    )
                    break

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
        # v3.6.0 项6 路径A：失败后写入 skill_iteration_alerts 集合，等待人工决策
        self._write_iteration_alert(
            spec=spec,
            run_id=run_id,
            iterations=iterations,
            failure_summary=failure_summary,
            total_time=total_time,
            engine="legacy_pipeline",
        )
        return PipelineResult(
            success=False,
            tool_id=spec.tool_id,
            iterations=iterations,
            total_rounds=self._max_iterations,
            total_time=round(time.time() - start_time, 2),
            error=failure_summary,
        )

    # ==================== 提前退出检测 ====================

    @staticmethod
    def _detect_stale_failures(iterations: List[IterationRound]) -> bool:
        """
        检测连续 N 轮业务验收的失败项是否完全相同。
        如果是，说明失败原因是外部数据不可用，继续迭代不会改善。
        """
        if len(iterations) < _STALE_FAILURE_THRESHOLD:
            return False

        recent = iterations[-_STALE_FAILURE_THRESHOLD:]

        # 提取每轮的失败 rule_id 集合
        failure_sets: List[frozenset] = []
        for it in recent:
            if it.business_verification and not it.business_verification.passed:
                rule_ids = frozenset(f.rule_id for f in it.business_verification.failures)
                failure_sets.append(rule_ids)
            else:
                return False  # 有一轮通过了或没有业务验收，不算连续

        if len(failure_sets) < _STALE_FAILURE_THRESHOLD:
            return False

        # 所有集合相同
        return len(set(failure_sets)) == 1

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
    def _dump_agentic_prompt_to_logfile(
        spec: SkillSpec,
        system_prompt: str,
        user_prompt: str,
        fact_report: Optional[ImplementationFactReport],
    ) -> None:
        """将 agentic 模式的完整 system/user prompt 写入日志文件，方便排查 LLM 未调用推荐 helper 的问题。

        日志文件位置：logs/codegen_prompts/agentic_<tool_id>_<timestamp>.log
        """
        try:
            from datetime import datetime
            log_dir = Path("logs/codegen_prompts")
            log_dir.mkdir(parents=True, exist_ok=True)

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            safe_tool_id = re.sub(r"[^\w\-]", "_", spec.tool_id or "unknown")

            # 构建 helper 摘要
            helper_summary = "（无 fact_report）"
            if fact_report:
                if fact_report.available_helpers:
                    helper_lines = []
                    for h in fact_report.available_helpers:
                        helper_lines.append(
                            f"  - {h.module}.{h.name} | signature={h.signature or ''} | "
                            f"data_source_handling={h.data_source_handling or ''} | reason={h.reason or ''}"
                        )
                    helper_summary = f"共 {len(fact_report.available_helpers)} 个:\n" + "\n".join(helper_lines)
                else:
                    helper_summary = "available_helpers 为空"

            content = (
                f"{'=' * 80}\n"
                f"# Agentic SkillGeneration Prompt Dump\n"
                f"{'=' * 80}\n"
                f"# tool_id: {spec.tool_id}\n"
                f"# timestamp: {timestamp}\n"
                f"# spec.display_name: {spec.display_name}\n"
                f"# spec.description: {spec.description[:200] if spec.description else ''}\n"
                f"# system_prompt 长度: {len(system_prompt)} 字符\n"
                f"# user_prompt 长度: {len(user_prompt)} 字符\n"
                f"\n"
                f"{'─' * 80}\n"
                f"## 侦察层推荐的 available_helpers\n"
                f"{'─' * 80}\n"
                f"{helper_summary}\n"
                f"\n"
                f"{'─' * 80}\n"
                f"## Agentic System Prompt（完整）\n"
                f"{'─' * 80}\n"
                f"{system_prompt}\n"
                f"\n"
                f"{'─' * 80}\n"
                f"## Agentic User Prompt（完整）\n"
                f"{'─' * 80}\n"
                f"{user_prompt}\n"
            )

            hist_path = log_dir / f"agentic_{safe_tool_id}_{timestamp}.log"
            hist_path.write_text(content, encoding="utf-8")

            latest_path = log_dir / f"agentic_{safe_tool_id}_latest.log"
            latest_path.write_text(content, encoding="utf-8")

            logger.info(
                f"[AgenticSkill] Prompt dump 已写入: {latest_path} "
                f"(system={len(system_prompt)}字符, user={len(user_prompt)}字符, "
                f"helpers={len(fact_report.available_helpers) if fact_report else 0}个)"
            )
        except Exception as exc:
            logger.warning(f"[AgenticSkill] 写入 prompt dump 日志失败: {exc}", exc_info=True)

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
    def _persist_stage_artifact(
        tool_id: str,
        run_id: str,
        round_num: int,
        stage: str,
        payload: Dict[str, Any],
        code: str = "",
    ) -> Optional[Path]:
        """阶段一完成就立即落盘，便于定位卡在哪一步。"""
        try:
            d = IterationController._get_snapshot_dir(tool_id, run_id)
            stage_payload = {
                "tool_id": tool_id,
                "run_id": run_id,
                "round_number": round_num,
                "stage": stage,
                "updated_at": datetime.utcnow().isoformat(),
                **payload,
            }
            path = d / f"round_{round_num:02d}_{stage}.json"
            path.write_text(
                json.dumps(stage_payload, ensure_ascii=False, indent=2, default=str),
                encoding="utf-8",
            )
            latest_path = d / "latest_stage.json"
            latest_path.write_text(
                json.dumps(stage_payload, ensure_ascii=False, indent=2, default=str),
                encoding="utf-8",
            )
            if code:
                code_path = d / f"round_{round_num:02d}.py"
                code_path.write_text((code or "") + ("" if code.endswith("\n") else "\n"), encoding="utf-8")
            logger.info("📝 阶段结果已落盘: %s", path)
            return path
        except Exception as exc:
            logger.warning("⚠️ 阶段结果落盘失败(stage=%s, round=%s): %s", stage, round_num, exc)
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

    # ==================== 失败告警（v3.6.0 项6 路径A） ====================

    def _write_iteration_alert(
        self,
        *,
        spec: SkillSpec,
        run_id: str,
        iterations: List[IterationRound],
        failure_summary: str,
        total_time: float,
        engine: str = "legacy_pipeline",
        extra_metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """迭代失败后写入 skill_iteration_alerts 集合，供前端展示并等待人工决策。

        v3.6.0 项6 路径A：原本迭代失败后直接放弃，用户只能查看日志；
        现在写入 MongoDB 集合，前端可展示失败原因，用户可选择：
        - 手动调整 spec 后重新生成
        - 直接放弃
        - 标记为已解决（不再提示）

        失败处理策略：
        - MongoDB 不可用 → 只记日志，不阻塞返回
        - 写入异常 → 只记日志，不阻塞返回
        """
        try:
            from app.core.database import get_mongo_db_sync
            from datetime import datetime

            db = get_mongo_db_sync()
            if db is None:
                logger.warning("[IterationAlert] db 句柄为空，跳过写入告警")
                return

            # 从 spec.metadata 提取关联上下文（session_id / user_id 等）
            spec_metadata = getattr(spec, "metadata", None) or {}
            if not isinstance(spec_metadata, dict):
                spec_metadata = {}

            session_id = str(spec_metadata.get("session_id") or spec_metadata.get("skill_session_id") or "")
            user_id = str(spec_metadata.get("user_id") or "")
            workshop_session_id = str(spec_metadata.get("workshop_session_id") or "")
            agent_spec_id = str(spec_metadata.get("agent_spec_id") or "")

            # 收集每轮失败摘要（最多 5 轮，避免文档过大）
            round_summaries = []
            for it in iterations[-5:]:
                round_summaries.append({
                    "round": it.round_number,
                    "decision": it.decision or "",
                    "validation_passed": bool(it.validation.passed) if it.validation else None,
                    "sandbox_success": bool(it.sandbox.success) if it.sandbox else None,
                    "eval_total": float(it.eval_score.total) if it.eval_score else None,
                    "business_passed": bool(it.business_verification.passed) if it.business_verification else None,
                    "root_cause": it.reflection.root_cause if it.reflection else "",
                })

            alert_doc = {
                "alert_id": f"alert_{run_id}_{spec.tool_id}",
                "tool_id": spec.tool_id,
                "display_name": getattr(spec, "display_name", "") or "",
                "description": (getattr(spec, "description", "") or "")[:500],
                "session_id": session_id,
                "workshop_session_id": workshop_session_id,
                "agent_spec_id": agent_spec_id,
                "user_id": user_id,
                "engine": engine,
                "run_id": run_id,
                "total_rounds": len(iterations),
                "total_time_seconds": total_time,
                "failure_summary": failure_summary[:5000],
                "round_summaries": round_summaries,
                "status": "pending_human_review",  # pending_human_review / resolved_give_up / resolved_retry / resolved_manual
                "created_at": datetime.utcnow().isoformat(),
                "extra_metadata": extra_metadata or {},
            }

            result = db.skill_iteration_alerts.update_one(
                {"alert_id": alert_doc["alert_id"]},
                {"$set": alert_doc},
                upsert=True,
            )
            logger.info(
                "[IterationAlert] 已写入告警 alert_id=%s tool_id=%s rounds=%d matched=%d modified=%d upserted=%s",
                alert_doc["alert_id"],
                spec.tool_id,
                len(iterations),
                result.matched_count,
                result.modified_count,
                result.upserted_id is not None,
            )
        except Exception as exc:
            logger.warning("[IterationAlert] 写入告警失败（不阻塞主流程）: %s", exc)

    # ==================== Agentic Loop / pipeline_tool ====================

    def run_agentic(
        self,
        spec: SkillSpec,
        initial_feedback: str = "",
        initial_code: str = "",
        progress_callback: Optional[Callable[[str, str, int, float], None]] = None,
        fact_report: Optional[ImplementationFactReport] = None,
        codegen_timeout: Optional[int] = None,
        thinking_callback: Optional[Callable[[str, str], None]] = None,
        iteration_mode: str = "repair",
    ) -> PipelineResult:
        """SkillGeneration 专用 Agent Loop。

        外层 LLM 可以在每轮 pipeline_tool 前后调用常驻查询/探针工具；pipeline_tool
        只执行单轮候选生成与质控，不在内部做多轮重试。

        iteration_mode: "repair"=失败后定向修复；"upgrade"=在已验证旧版本
        （initial_code）上做最小改动升级，首轮代码生成携带升级基线与指令。
        """
        start_time = time.time()
        run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        iterations: List[IterationRound] = []
        feedback = initial_feedback
        previous_code = initial_code
        verified_facts: List[str] = []
        # 从侦察报告中继承已验证事实，避免 Agentic LLM 重复探索
        if fact_report:
            for h in (fact_report.available_helpers or [])[:10]:
                sig = (h.signature or "").strip()
                if sig:
                    verified_facts.append(f"{h.name} 签名已验证: {sig[:80]}")
                else:
                    verified_facts.append(f"{h.name} 已验证可用（模块: {h.module}）")
            for f in (fact_report.schema_facts or [])[:8]:
                desc = f.description or f.fact or ""
                if desc:
                    verified_facts.append(desc[:120])
        self._agentic_trace = []
        logger.info(
            "🤖 [AgenticSkill] start tool_id=%s max_steps=%s initial_feedback_chars=%s initial_code_chars=%s fact_report=%s",
            spec.tool_id,
            self._max_iterations,
            len(initial_feedback or ""),
            len(initial_code or ""),
            bool(fact_report),
        )

        def _report(stage: str, message: str, it: int, prog: float, extra: Optional[Dict[str, Any]] = None):
            if progress_callback:
                try:
                    progress_callback(stage, message, it, prog, extra)
                except Exception as e:
                    logger.warning("progress_callback 异常: %s", e)

        if fact_report is None:
            try:
                _report("reconnaissance", "正在整理实现事实...", 0, 0.03)
                fact_report = self._reconnaissance.analyze(spec)
                self._persist_fact_report(spec.tool_id, run_id, fact_report)
            except Exception as exc:
                logger.warning("⚠️ Agentic 前置侦察失败，继续运行: %s", exc)
        elif fact_report is not None:
            self._persist_fact_report(spec.tool_id, run_id, fact_report)

        agentic_state = {
            "feedback": feedback,
            "previous_code": previous_code,
            "verified_facts": verified_facts,
            "progress_callback": _report,
            "codegen_timeout": codegen_timeout,
            "thinking_callback": thinking_callback,
        }
        tools = self._build_agentic_tools(
            spec=spec,
            run_id=run_id,
            iterations=iterations,
            fact_report=fact_report,
            state=agentic_state,
            iteration_mode=iteration_mode,
        )
        tool_defs = [ToolCallNormalizer.normalize_tool_definition(func) for func in tools.values()]
        client = self._get_client()
        client.inject_tools(tools)

        known_context = self._extract_known_context_from_spec(spec)
        logger.info(
            "🤖 [AgenticSkill] context tool_id=%s known_failures=%s known_facts=%s tools=%s",
            spec.tool_id,
            len(known_context.get("known_failure_summaries") or []),
            len(known_context.get("known_verified_facts") or []),
            sorted(tools.keys()),
        )
        agentic_system_prompt = self._build_agentic_system_prompt(spec)
        agentic_user_prompt = self._build_agentic_task_prompt(
            spec, initial_feedback, fact_report, known_context,
            parent_code=(initial_code if iteration_mode == "upgrade" else ""),
        )

        # 将完整的 agentic prompt 写入日志文件，方便排查 LLM 未调用推荐 helper 的问题
        self._dump_agentic_prompt_to_logfile(spec, agentic_system_prompt, agentic_user_prompt, fact_report)

        messages: List[Message] = [
            Message(role="system", content=agentic_system_prompt),
            Message(role="user", content=agentic_user_prompt),
        ]

        final_result: Optional[PipelineToolResult] = None
        failure_result: Optional[PipelineToolResult] = None
        stale_failure_counts: Dict[str, int] = {}
        # 探索节奏跟踪：避免 LLM 浪费步数在重复探索上
        consecutive_explore_steps = 0
        total_explore_steps = 0
        _MAX_CONSECUTIVE_EXPLORE = 2
        _MAX_TOTAL_EXPLORE = 4

        for step in range(1, self._max_iterations + 1):
            _report("agentic_loop", f"Agentic Skill 生成循环第 {step}/{self._max_iterations} 步", step, min(0.05 + step * 0.08, 0.9))
            logger.info(
                "🤖 [AgenticSkill] step=%s/%s tool_id=%s messages=%s verified_facts=%s consecutive_explore=%s total_explore=%s",
                step,
                self._max_iterations,
                spec.tool_id,
                len(messages),
                len(verified_facts),
                consecutive_explore_steps,
                total_explore_steps,
            )
            try:
                response = client.chat(
                    messages,
                    tools=tool_defs,
                    auto_execute_tools=False,
                    max_tokens=2048,
                    temperature=0.2,
                    tool_choice="auto",
                )
            except Exception as exc:
                logger.warning("Agentic Loop LLM 调用失败，降级为单轮 pipeline_tool: %s", exc)
                tools["pipeline_tool"]()
                failure_result = self._last_agentic_pipeline_result
                if failure_result and failure_result.iteration:
                    iterations.append(failure_result.iteration)
                break

            if response.has_tool_calls:
                tool_names = [str(call.name or "") for call in response.tool_calls]
                # 判断本步是否调用了 pipeline_tool
                step_called_pipeline = any(name == "pipeline_tool" for name in tool_names)
                logger.info(
                    "🤖 [AgenticSkill] step=%s tool_calls=%s pipeline=%s tool_id=%s",
                    step,
                    tool_names,
                    step_called_pipeline,
                    spec.tool_id,
                )
                messages.append(response.to_message())
                for tool_call in response.tool_calls:
                    result = ToolCallNormalizer.execute_tool_call(tool_call, tools)
                    content = result.content or ""
                    if result.name != "pipeline_tool":
                        fact = self._build_verified_fact_from_tool_result(result.name, content)
                        if fact and fact not in verified_facts:
                            verified_facts.append(fact)
                    self._agentic_trace.append({
                        "step": step,
                        "tool": result.name,
                        "arguments": tool_call.arguments,
                        "is_error": result.is_error,
                        "content_excerpt": content[:2000],
                    })
                    messages.append(Message(
                        role="tool",
                        content=content,
                        tool_call_id=result.tool_call_id,
                        name=result.name,
                    ))
                    if result.name == "pipeline_tool":
                        latest = self._last_agentic_pipeline_result
                        if latest and latest.iteration:
                            if latest.iteration not in iterations:
                                iterations.append(latest.iteration)
                            failure_result = latest
                            logger.info(
                                "🤖 [AgenticSkill] pipeline_result tool_id=%s round=%s status=%s should_retry=%s summary=%s",
                                spec.tool_id,
                                latest.round_number,
                                latest.status,
                                latest.should_retry,
                                (latest.failure_summary or "")[:300],
                            )
                            feedback = latest.failure_summary or feedback
                            previous_code = latest.final_code or previous_code
                            if latest.status == "pass":
                                final_result = latest
                                break
                            if latest.failure_summary:
                                signature = self._stale_failure_signature(latest.failure_summary)
                                stale_failure_counts[signature] = stale_failure_counts.get(signature, 0) + 1
                                messages.append(Message(
                                    role="user",
                                    content=(
                                        "上一轮 pipeline_tool 失败摘要如下，请基于它决定下一步："
                                        "需要查真实数据就调用 run_readonly_query，需要探测接口就调用 probe_interface，"
                                        "需要诊断脚本就调用 run_diagnostic_script，信息足够后再调用 pipeline_tool。\n"
                                        f"{latest.failure_summary}"
                                    ),
                                ))
                                # 静态验证是纯确定性检查（无环境噪声）：同一签名连续 2 次
                                # 即说明 LLM 修不动，通常是规格级错误（如参数名不可实现），
                                # 早熔断省一轮 2-4 分钟的代码生成
                                is_static_sig = signature.startswith("静态验证失败")
                                effective_threshold = 2 if is_static_sig else _STALE_FAILURE_THRESHOLD
                                if stale_failure_counts[signature] >= effective_threshold:
                                    blocked_hint = (
                                        "该错误为确定性校验失败且两轮重试未变，"
                                        "大概率是规格问题而非代码问题——请检查 SkillSpec 的参数定义是否可实现。"
                                        if is_static_sig
                                        else ""
                                    )
                                    failure_result = PipelineToolResult(
                                        status="blocked",
                                        round_number=latest.round_number,
                                        failure_summary=(
                                            f"连续 {effective_threshold} 次出现相同失败，触发 stale failure 熔断。"
                                            f"{blocked_hint}\n{latest.failure_summary}"
                                        ),
                                        verified_facts=list(verified_facts),
                                        should_retry=False,
                                    )
                                    logger.warning(
                                        "🤖 [AgenticSkill] stale_failure_blocked tool_id=%s signature=%s count=%s threshold=%s",
                                        spec.tool_id,
                                        signature[:120],
                                        stale_failure_counts[signature],
                                        effective_threshold,
                                    )
                                    break
                            if latest.status == "blocked" or not latest.should_retry:
                                break
                if final_result:
                    break
                if failure_result and (failure_result.status == "blocked" or not failure_result.should_retry):
                    break
                # 探索节奏统计：若本步未调用 pipeline_tool，记为探索步
                if not step_called_pipeline:
                    consecutive_explore_steps += 1
                    total_explore_steps += 1
                    if consecutive_explore_steps >= _MAX_CONSECUTIVE_EXPLORE or total_explore_steps >= _MAX_TOTAL_EXPLORE:
                        # 注入强制提醒，推动 LLM 下一步直接调用 pipeline_tool
                        reminder = (
                            f"⚠️ 你已连续探索 {consecutive_explore_steps} 步（累计 {total_explore_steps} 步），"
                            f"超过探索预算。下一步必须直接调用 pipeline_tool 生成代码，"
                            f"不要再调用 run_readonly_query / probe_interface / run_diagnostic_script / describe_runtime_helper 等探索工具。"
                        )
                        messages.append(Message(role="user", content=reminder))
                        logger.warning(
                            "🤖 [AgenticSkill] explore_budget_exceeded tool_id=%s step=%s consecutive=%s total=%s",
                            spec.tool_id, step, consecutive_explore_steps, total_explore_steps,
                        )
                else:
                    # 调用过 pipeline_tool，重置连续计数
                    consecutive_explore_steps = 0
                continue

            content = (response.content or "").strip()
            if content:
                messages.append(Message(role="assistant", content=content))
            if not iterations:
                logger.info("Agentic Loop 未调用 pipeline_tool，强制执行一轮受治理生成。")
                tools["pipeline_tool"]()
                failure_result = self._last_agentic_pipeline_result
                if failure_result and failure_result.iteration:
                    iterations.append(failure_result.iteration)
                if failure_result and failure_result.status == "pass":
                    final_result = failure_result
            break

        # 兜底：如果 LLM 用尽所有步骤仍未通过（无论是否调用过 pipeline_tool），强制再执行一轮
        if not final_result:
            last_round = iterations[-1] if iterations else None
            last_feedback = last_round.feedback if last_round else ""
            logger.warning(
                "🤖 [AgenticSkill] LLM 用尽 %s 步仍未通过，强制再执行一轮 pipeline_tool tool_id=%s last_feedback=%s",
                self._max_iterations,
                spec.tool_id,
                (last_feedback[:80] + "...") if last_feedback else "(none)",
            )
            # 把最后一轮的失败反馈写入 agentic_state，让 pipeline_tool 定向修复
            if last_feedback:
                agentic_state["feedback"] = last_feedback
            tools["pipeline_tool"]()
            failure_result = self._last_agentic_pipeline_result
            if failure_result and failure_result.iteration:
                iterations.append(failure_result.iteration)
            if failure_result and failure_result.status == "pass":
                final_result = failure_result

        total_time = round(time.time() - start_time, 2)
        if final_result:
            _report("output_evaluation", "Agentic Skill 生成通过", final_result.round_number, 1.0)
            logger.info(
                "🤖 [AgenticSkill] success tool_id=%s rounds=%s total_time=%.2fs trace_events=%s verified_facts=%s",
                spec.tool_id,
                len(iterations),
                total_time,
                len(self._agentic_trace),
                len(verified_facts),
            )
            return PipelineResult(
                success=True,
                tool_id=spec.tool_id,
                final_code=final_result.final_code,
                final_metadata={
                    **(final_result.final_metadata or {}),
                    "generation_engine": "agentic_loop",
                    "agentic_trace": self._public_agentic_trace(self._agentic_trace),
                    "verified_facts": verified_facts,
                },
                iterations=iterations,
                total_rounds=len(iterations),
                total_time=total_time,
            )

        error = self._build_failure_summary(iterations) if iterations else "Agentic Skill 生成未产生有效候选代码"
        if failure_result and failure_result.failure_summary:
            error = failure_result.failure_summary + "\n\n" + error
        logger.warning(
            "🤖 [AgenticSkill] failed tool_id=%s rounds=%s total_time=%.2fs trace_events=%s verified_facts=%s error=%s",
            spec.tool_id,
            len(iterations),
            total_time,
            len(self._agentic_trace),
            len(verified_facts),
            error[:500],
        )
        # v3.6.0 项6 路径A：失败后写入 skill_iteration_alerts 集合，等待人工决策
        self._write_iteration_alert(
            spec=spec,
            run_id=run_id,
            iterations=iterations,
            failure_summary=error,
            total_time=total_time,
            engine="agentic_loop",
            extra_metadata={
                "agentic_trace": self._public_agentic_trace(self._agentic_trace),
                "verified_facts": verified_facts,
            },
        )
        return PipelineResult(
            success=False,
            tool_id=spec.tool_id,
            iterations=iterations,
            total_rounds=len(iterations),
            total_time=total_time,
            error=error,
            final_metadata={
                "generation_engine": "agentic_loop",
                "agentic_trace": self._public_agentic_trace(self._agentic_trace),
                "verified_facts": verified_facts,
            },
        )

    @property
    def _last_agentic_pipeline_result(self) -> Optional[PipelineToolResult]:
        trace = getattr(self, "_agentic_trace", []) or []
        for item in reversed(trace):
            result = item.get("pipeline_result")
            if isinstance(result, PipelineToolResult):
                return result
        return None

    @_last_agentic_pipeline_result.setter
    def _last_agentic_pipeline_result(self, value: Optional[PipelineToolResult]) -> None:
        if not hasattr(self, "_agentic_trace"):
            self._agentic_trace = []
        if value is None:
            return
        self._agentic_trace.append({
            "event": "pipeline_result",
            "status": value.status,
            "round_number": value.round_number,
            "failure_summary": value.failure_summary[:2000],
            "code_path": value.code_path,
            "snapshot_path": value.snapshot_path,
            "should_retry": value.should_retry,
            "pipeline_result": value,
        })

    @staticmethod
    def _public_agentic_trace(trace: List[Dict[str, Any]], limit: int = 80) -> List[Dict[str, Any]]:
        public_items: List[Dict[str, Any]] = []
        for item in trace[-limit:]:
            public_items.append({
                key: value
                for key, value in item.items()
                if key != "pipeline_result"
            })
        return public_items

    @staticmethod
    def _stale_failure_signature(summary: str) -> str:
        text = " ".join(str(summary or "").split())
        return text[:500]

    @staticmethod
    def _build_verified_fact_from_tool_result(tool_name: str, content: str) -> str:
        if not content:
            return ""
        try:
            data = json.loads(content)
        except Exception:
            return f"{tool_name} returned {len(content)} chars"
        if isinstance(data, dict):
            if data.get("success") is False:
                return f"{tool_name} failed: {str(data.get('error') or '')[:180]}"
            if tool_name == "probe_interface":
                func = data.get("function") or data.get("source_or_helper") or "unknown"
                shape = data.get("shape") or {}
                return f"probe_interface confirmed {func}: {shape}"
            if tool_name == "run_readonly_query":
                collection = data.get("collection") or "unknown"
                return f"run_readonly_query confirmed {collection}: returned_count={data.get('returned_count')}"
            if tool_name == "run_diagnostic_script":
                output = data.get("output") if isinstance(data.get("output"), dict) else {}
                return f"run_diagnostic_script success={data.get('success')}, tool_call_count={output.get('tool_call_count')}"
        return f"{tool_name} returned structured result"

    def _build_agentic_tools(
        self,
        *,
        spec: SkillSpec,
        run_id: str,
        iterations: List[IterationRound],
        fact_report: Optional[ImplementationFactReport],
        state: Dict[str, Any],
        iteration_mode: str = "repair",
    ) -> Dict[str, Callable]:
        from .recon_tools import (
            check_field_coverage,
            describe_runtime_helper,
            inspect_collection_schema,
            inspect_symbol_sample,
            list_analysis_tools,
            list_available_collections,
            list_external_data_sources,
            list_runtime_functions,
            probe_interface,
            run_readonly_query,
        )

        def run_diagnostic_script(script: str) -> str:
            """在构建期沙箱中执行诊断脚本，用于确认真实字段、接口返回形状和数据覆盖率。
            脚本内可直接 import core.skill_runtime.data_access / core.skill_runtime.project_access 验证返回形状；
            也可调用 hermes_tools.run_readonly_query / hermes_tools.probe_interface 等侦察函数（仅诊断用）。
            最终 Skill 代码不得依赖 hermes_tools，只能使用 core.skill_runtime.* 公开 API。"""
            logger.info(
                "🤖 [AgenticSkill] diagnostic_script tool_id=%s script_chars=%s",
                spec.tool_id,
                len(script or ""),
            )
            result = self._runner.run_diagnostic_script(script)
            payload = {
                "success": result.success,
                "output": result.output,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "error": result.error,
                "execution_time": result.execution_time,
            }
            return json.dumps(payload, ensure_ascii=False, default=str)

        def pipeline_tool() -> str:
            """执行一轮受治理的候选 Skill 生成与质控。
            单轮包含：代码生成、静态校验、沙箱执行、Judge 评分、业务验收和边缘测试。
            不会在工具内部自动进入下一轮；下一步由 Agent Loop 决定。"""
            round_num = len(iterations) + 1
            # 仅首轮（基于父版本代码）用升级文案；首轮之后 previous_code 已换成
            # 本轮新生成的代码，属于失败修复语义
            round_mode = "upgrade" if iteration_mode == "upgrade" and round_num == 1 else "repair"
            result = self._run_pipeline_tool_once(
                spec=spec,
                run_id=run_id,
                round_num=round_num,
                feedback=state.get("feedback", ""),
                previous_code=state.get("previous_code", ""),
                fact_report=fact_report,
                progress_callback=state.get("progress_callback"),
                verified_facts=state.get("verified_facts") or [],
                codegen_timeout=state.get("codegen_timeout"),
                thinking_callback=state.get("thinking_callback"),
                iteration_mode=round_mode,
            )
            self._last_agentic_pipeline_result = result
            state["feedback"] = result.failure_summary or state.get("feedback", "")
            if result.final_code:
                state["previous_code"] = result.final_code
            for fact in result.verified_facts:
                if fact not in state["verified_facts"]:
                    state["verified_facts"].append(fact)
            return json.dumps(result.to_public_dict(), ensure_ascii=False, default=str)

        return {
            "pipeline_tool": pipeline_tool,
            "run_diagnostic_script": run_diagnostic_script,
            "run_readonly_query": run_readonly_query,
            "probe_interface": probe_interface,
            "inspect_collection_schema": inspect_collection_schema,
            "inspect_symbol_sample": inspect_symbol_sample,
            "check_field_coverage": check_field_coverage,
            "describe_runtime_helper": describe_runtime_helper,
            "list_runtime_functions": list_runtime_functions,
            "list_analysis_tools": list_analysis_tools,
            "list_available_collections": list_available_collections,
            "list_external_data_sources": list_external_data_sources,
        }

    @staticmethod
    def _build_agentic_system_prompt(spec: Optional[SkillSpec] = None) -> str:
        """Agent Loop 协调者 system prompt，按需求类型分流。

        external_api（外部接口集成，如懂车帝）：去掉本地 helper 复用/数据源标签/
        股票代码预检等本地数据假设，替换为外部接口防御规则。
        """
        from .requirement_analyzer import classify_requirement_mode

        mode = classify_requirement_mode(spec) if spec is not None else "local_data"
        if mode == "external_api":
            return """你是 SkillGeneration 专用 Agent Loop，不是普通聊天助手。
目标：生成一个可注册的 Python Skill，并通过平台硬性质控。

本需求为外部接口集成：数据来自外部 API（与本地股票数据库无关），不要建议查询本地股票集合或使用本地股票数据 helper。

你可以调用工具：
- pipeline_tool：执行一轮受治理的候选代码生成与质控（代码生成→静态校验→沙箱执行→评分）。这是核心工具，必须调用。
- run_readonly_query：查询真实样本文档，确认字段和覆盖率（仅在 pipeline_tool 失败后需要核实字段时使用）。
- probe_interface：真实调用已登记 helper，确认返回形状（仅在 pipeline_tool 失败后需要确认接口形状时使用）。
- run_diagnostic_script：执行构建期诊断脚本，脚本内可直接 import core.skill_runtime.* 或 core.tools.implementations.* 来验证返回形状。
- list_external_data_sources：列出系统已登记的外部数据源目录。
- inspect_collection_schema / inspect_symbol_sample / check_field_coverage / describe_runtime_helper / list_runtime_functions：结构探测工具。

关键规则（按优先级）：
1. 侦察报告（fact_report）已经为你准备好了，包含接口事实、推荐策略和验证检查。请直接调用 pipeline_tool 生成代码，不要重复侦察。
2. pipeline_tool 是核心工具。第一轮请直接调用 pipeline_tool，不要先做任何探索。
3. 只有当 pipeline_tool 返回 failure_summary 且失败原因明确是"字段名错误""接口返回形状不匹配""数据源不可用"时，才使用 probe_interface / run_diagnostic_script 等工具针对性核实，然后再次调用 pipeline_tool。
4. 最终 Skill 代码必须是独立可运行的同步纯 Python 函数（禁止 async def / await）；
   允许使用 requests 等标准 HTTP 库直接调用外部接口，不要导入 core.skill_runtime 本地数据模块。
   禁止依赖 hermes_tools、RPC stub、构建期诊断工具、agent_builder/assistant_ops/skill_builder 等流程类工具。
5. 接口字段以实际响应为准：字段映射必须来自侦察报告确认的响应结构，禁止臆造字段名或路径。
6. 不要跳过 pipeline_tool；只有 pipeline_tool pass 才算成功。
7. 如果确认外部接口无法提供目标能力（限流/鉴权/字段缺失），应停止重试并说明阻塞原因。
8. 最多 10 步。每步要么调用 pipeline_tool，要么做针对性核实，不要无目的探索。
9. **探索节奏约束**：连续探索步数（非 pipeline_tool 调用）不得超过 2 步；累计探索步数不得超过 4 步。每 3 步内至少调用 1 次 pipeline_tool。
10. 🛡️ 外部接口错误预防（生成的代码必须遵循，避免边缘测试失败）：
   - 参数防御：必填参数缺失或格式非法时立即返回 {"status": "error", "error_code": "invalid_param", "message": ...}，不发起网络请求。
   - HTTP 调用必须设置超时（timeout=10 左右）并 try-except 包裹；限流时短暂退避，不要在循环里逐条打接口。
   - 数据为空时优雅返回：{"status": "success", "data": [], "message": "未找到xxx数据"}，绝不可伪造数据。
   - 返回值一致性：无论成功失败，返回 dict 必须包含 status 字段（"success"/"error"）。
   - 异常兜底：主函数体用 try-except 包裹，捕获异常后返回结构化错误响应，不要抛出未捕获异常。
   - 边缘测试会传入非法参数值，代码必须在 5 秒内返回错误响应，不能超时。"""

        return """你是 SkillGeneration 专用 Agent Loop，不是普通聊天助手。
目标：生成一个可注册的 Python Skill，并通过平台硬性质控。

你可以调用工具：
- pipeline_tool：执行一轮受治理的候选代码生成与质控（代码生成→静态校验→沙箱执行→评分）。这是核心工具，必须调用。
- run_readonly_query：查询真实样本文档，确认字段和覆盖率（仅在 pipeline_tool 失败后需要核实字段时使用）。
- probe_interface：真实调用已登记 helper，确认返回形状（仅在 pipeline_tool 失败后需要确认接口形状时使用）。
- run_diagnostic_script：执行构建期诊断脚本，脚本内可直接 import core.skill_runtime.* 或 core.tools.implementations.* 来验证返回形状。
- list_analysis_tools：列出所有可复用的分析类工具（fundamentals/market/technical/portfolio/risk 等 180+ 个）及其完整导入路径。生成的 Skill 代码可直接 from <module_path> import <function_name> 调用这些工具。
- inspect_collection_schema / inspect_symbol_sample / check_field_coverage / describe_runtime_helper / list_runtime_functions：结构探测工具。

关键规则（按优先级）：
1. 侦察报告（fact_report）已经为你准备好了，包含可用 helper、推荐策略和验证检查。请直接调用 pipeline_tool 生成代码，不要重复侦察。
2. pipeline_tool 是核心工具。第一轮请直接调用 pipeline_tool，不要先做任何探索。
3. 只有当 pipeline_tool 返回 failure_summary 且失败原因明确是"字段名错误""接口返回形状不匹配""数据源不可用"时，才使用 run_readonly_query / probe_interface / run_diagnostic_script 等工具针对性核实，然后再次调用 pipeline_tool。
4. 最终 Skill 代码允许导入以下模块：
   - core.skill_runtime.data_access / core.skill_runtime.project_access / core.skill_runtime.standard_financial_apis（标准数据访问）
   - core.tools.implementations.fundamentals / market / technical / portfolio / risk / news / social / trade_review / legacy_bridge（180+ 个分析工具，与 agent 工坊共享）
   禁止依赖 hermes_tools、RPC stub、构建期诊断工具、agent_builder/assistant_ops/skill_builder 等流程类工具。
5. 必须复用已有工具：如果 fact_report.available_helpers 中已有完成目标能力的工具，必须直接 import 调用，禁止自行实现等价的数据获取逻辑。
6. **数据源标签使用规则**（根据 available_helpers 中每个 helper 的 data_source_handling 标签决策）：
   - `self_contained`：helper 已自包含数据源调用，直接调用即可，不要再额外调用外部数据源补数据
   - `local_only`：helper 只查本地 MongoDB，若返回为空或数据不足，需在 skill 中补充外部数据源调用（如 tushare/akshare/finnhub）或 core.skill_runtime.external_sources
   - `partial`：helper 仅覆盖部分需求，需结合其它 helper 或补充数据源/计算逻辑一起使用
7. 不要跳过 pipeline_tool；只有 pipeline_tool pass 才算成功。
8. 如果确认数据源无法提供目标能力，应停止重试并说明阻塞原因。
9. 最多 10 步。每步要么调用 pipeline_tool，要么做针对性核实，不要无目的探索。
10. **探索节奏约束**：连续探索步数（非 pipeline_tool 调用）不得超过 2 步；累计探索步数不得超过 4 步。每 3 步内至少调用 1 次 pipeline_tool。若 fact_report 已给出 helper 签名，直接调用 pipeline_tool，不要先 probe_interface 验证。
11. 🛡️ 通用错误预防（生成的代码必须遵循，避免边缘测试失败）：
   - 股票代码预检：函数开头用 get_stock_basic_info(symbol) 验证，不存在时立即返回 {"status": "error", "error_code": "symbol_not_found", "message": ..., "symbol": symbol}，不要继续后续查询。
   - 数据为空时优雅返回：关键数据查询结果为空时返回结构化错误响应，不要让后续计算崩溃。
   - 除零保护：所有比率计算用安全除法（denominator 为 0 或接近 0 时返回 None）。
   - 异常兜底：主函数体用 try-except 包裹，捕获异常后返回结构化错误响应，不要抛出未捕获异常。
   - 返回值一致性：无论成功失败，返回 dict 必须包含 status 字段（"success"/"error"）和 symbol 字段。
   - 边缘测试会传入不存在的股票代码，代码必须在 5 秒内返回错误响应，不能超时。"""

    @staticmethod
    def _extract_known_context_from_spec(spec: SkillSpec) -> Dict[str, List[str]]:
        metadata = getattr(spec, "metadata", None) or {}
        if not isinstance(metadata, dict):
            return {"known_failure_summaries": [], "known_verified_facts": []}
        return {
            "known_failure_summaries": [str(item) for item in list(metadata.get("known_failure_summaries") or []) if str(item).strip()][:5],
            "known_verified_facts": [str(item) for item in list(metadata.get("known_verified_facts") or []) if str(item).strip()][:12],
        }

    @staticmethod
    def _build_agentic_task_prompt(
        spec: SkillSpec,
        initial_feedback: str,
        fact_report: Optional[ImplementationFactReport],
        known_context: Optional[Dict[str, List[str]]] = None,
        parent_code: str = "",
    ) -> str:
        # 只提取关键摘要，避免注入完整 fact_report JSON（过大且不聚焦）
        recon_digest = ""
        if fact_report:
            parts = []
            # 1. 推荐策略（1 行）
            if fact_report.recommended_strategy:
                parts.append(f"【推荐策略】\n{fact_report.recommended_strategy}")
            # 2. 已验证的可用 helper（名称 + 模块 + 签名 + 数据源标签，每项 1-2 行）
            if fact_report.available_helpers:
                helper_lines = []
                for h in fact_report.available_helpers[:15]:  # 最多 15 个
                    sig = (h.signature or "")[:120]  # 签名截断
                    ds = h.data_source_handling or "self_contained"
                    helper_lines.append(f"- {h.name} | {h.module} | {sig} | 数据源:{ds}")
                parts.append(
                    "【已验证可用 helper（无需重复探索）】\n"
                    + "  数据源标签: self_contained=自包含(直接调用); local_only=仅本地MongoDB(可能需补充外部数据源); partial=部分覆盖\n"
                    + "\n".join(helper_lines)
                )
            # 3. 已验证事实（每项 1 行，最多 12 条）
            if fact_report.schema_facts:
                fact_lines = []
                for f in fact_report.schema_facts[:12]:
                    desc = f.description or f.fact or ""
                    if desc:
                        fact_lines.append(f"- {desc[:150]}")
                if fact_lines:
                    parts.append("【已验证字段事实】\n" + "\n".join(fact_lines))
            # 4. 禁止路径（每项 1 行，最多 5 条）
            if fact_report.blocked_paths:
                blocked_lines = [f"- {p.path}: {p.reason}" for p in fact_report.blocked_paths[:5]]
                parts.append("【禁止路径】\n" + "\n".join(blocked_lines))
            recon_digest = "\n\n".join(parts) if parts else "(无)"

        known_context = known_context or {}
        known_failures = "\n".join(f"- {item}" for item in list(known_context.get("known_failure_summaries") or [])[:5])
        known_facts = "\n".join(f"- {item}" for item in list(known_context.get("known_verified_facts") or [])[:12])

        # 接口预检实测事实（external_api 模式）：与 codegen user prompt 共用同一区块，
        # 协调者据此写反馈——不会给出「把被忽略的业务过滤参数拼进 URL」这类错误指导
        from .interface_preflight import build_preflight_facts_text

        preflight_block = build_preflight_facts_text(
            (getattr(spec, "metadata", None) or {}).get("interface_preflight")
        )

        # 版本升级场景：父版本是已验证基线，协调者必须规划「最小改动」而非从零重做
        upgrade_block = ""
        if parent_code:
            from .code_generator import CodeGenerator

            parent_snippet = CodeGenerator._format_previous_code_for_prompt(parent_code)
            upgrade_block = f"""
【⬆️ 版本升级任务 — 这是对已有 Skill 的升级，不是从零生成】

当前版本代码（已通过验证，是本次升级的基线）：
```python
{parent_snippet}
```

升级规划要求：
- 先识别新规格与当前版本的差异点（加字段/加参数/调整过滤等），只让 pipeline_tool 改动差异相关代码
- 当前版本的请求构造、分页、重试、响应解析、本地过滤、字段映射等已验证逻辑必须保留，严禁指示 pipeline_tool 重写
- 若首轮候选把已验证逻辑改坏，后续反馈中明确要求回退到基线实现
"""
        return f"""请完成以下 Skill 生成任务。

【SkillSpec】
{json.dumps(spec.model_dump(mode="json"), ensure_ascii=False, indent=2, default=str)}
{preflight_block}{upgrade_block}
【已有反馈/经验】
{initial_feedback or '(无)'}

【同一次 GapJob 已知失败摘要】
{known_failures or '(无)'}

【同一次 GapJob 已验证环境事实】
{known_facts or '(无)'}

【侦察阶段已验证结果（无需重复探索）】
{recon_digest}

⚠️ 重要：以上 helper 签名和字段事实已在侦察阶段验证过，不要重复调用 describe_runtime_helper / probe_interface / run_diagnostic_script 探索它们。
请直接调用 pipeline_tool 生成并验证候选 Skill。
仅当 pipeline_tool 失败且失败原因涉及"未探索过"的字段名/接口形状/数据源可用性时，才用探索工具针对性核实（最多 2 步），然后立即再次调用 pipeline_tool。"""


    def _run_pipeline_tool_once(
        self,
        *,
        spec: SkillSpec,
        run_id: str,
        round_num: int,
        feedback: str,
        previous_code: str,
        fact_report: Optional[ImplementationFactReport],
        progress_callback: Optional[Callable[[str, str, int, float], None]],
        verified_facts: List[str],
        codegen_timeout: Optional[int] = None,
        thinking_callback: Optional[Callable[[str, str], None]] = None,
        iteration_mode: str = "repair",
    ) -> PipelineToolResult:
        iteration = IterationRound(round_number=round_num)

        def _report(stage: str, message: str, progress: float, extra: Optional[Dict[str, Any]] = None) -> None:
            if progress_callback:
                progress_callback(stage, message, round_num, progress, extra)

        def _finish(status: str, summary: str, should_retry: bool = True) -> PipelineToolResult:
            snapshot_path = self._persist_round_snapshot(spec.tool_id, run_id, round_num, iteration, fact_report)
            code_path = ""
            if iteration.generated_code:
                code_path = str(self._get_snapshot_dir(spec.tool_id, run_id) / f"round_{round_num:02d}.py")
            return PipelineToolResult(
                status=status,
                round_number=round_num,
                iteration=iteration,
                code_path=code_path,
                snapshot_path=str(snapshot_path or ""),
                static_validation=iteration.validation.model_dump() if iteration.validation else {},
                sandbox_result=iteration.sandbox.model_dump() if iteration.sandbox else {},
                evaluation=self._build_pipeline_tool_evaluation(iteration),
                failure_summary=summary,
                verified_facts=list(verified_facts),
                should_retry=should_retry,
                final_code=iteration.generated_code.code if iteration.generated_code else "",
                final_metadata=iteration.generated_code.metadata if iteration.generated_code else {},
            )

        try:
            logger.info(
                "🔁 [pipeline_tool] start tool_id=%s round=%s feedback_chars=%s previous_code_chars=%s verified_facts=%s",
                spec.tool_id,
                round_num,
                len(feedback or ""),
                len(previous_code or ""),
                len(verified_facts or []),
            )
            _report("code_generation", "正在生成代码...", 0.1)
            generated = self._generator.generate(
                spec,
                feedback=feedback,
                previous_code=previous_code,
                fact_report=fact_report,
                timeout_seconds=codegen_timeout,
                on_thinking=thinking_callback,
                iteration_mode=iteration_mode,
            )
            iteration.generated_code = generated
            self._persist_stage_artifact(
                tool_id=spec.tool_id,
                run_id=run_id,
                round_num=round_num,
                stage="code_generation",
                payload={
                    "success": True,
                    "generation_time": generated.generation_time,
                    "code_lines": len((generated.code or "").split("\n")),
                    "metadata": generated.metadata or {},
                    "agentic_loop": True,
                },
                code=generated.code,
            )

            _report("static_validation", "正在语法检查...", 0.25)
            validation = self._validator.validate(generated, spec)
            iteration.validation = validation
            self._persist_stage_artifact(
                tool_id=spec.tool_id,
                run_id=run_id,
                round_num=round_num,
                stage="static_validation",
                payload={"passed": validation.passed, "errors": validation.errors[:20], "warnings": validation.warnings[:20]},
                code=generated.code,
            )
            if not validation.passed:
                logger.warning(
                    "🔁 [pipeline_tool] static_failed tool_id=%s round=%s errors=%s",
                    spec.tool_id,
                    round_num,
                    validation.errors[:5],
                )
                iteration.decision = "RETRY"
                summary = "静态验证失败：" + "；".join(validation.errors[:5])
                iteration.feedback = self._build_rich_feedback(stage="静态验证", errors=validation.errors, code=generated.code, spec=spec)
                return _finish("fail", summary)

            _report("sandbox_execution", "正在沙箱执行...", 0.4)
            sandbox = self._runner.run(generated.code, spec)
            iteration.sandbox = sandbox
            self._persist_stage_artifact(
                tool_id=spec.tool_id,
                run_id=run_id,
                round_num=round_num,
                stage="sandbox_execution",
                payload={
                    "success": sandbox.success,
                    "execution_time": sandbox.execution_time,
                    "error": sandbox.error,
                    "stdout": sandbox.stdout,
                    "stderr": sandbox.stderr,
                    "output": sandbox.output,
                },
                code=generated.code,
            )
            if not sandbox.success:
                logger.warning(
                    "🔁 [pipeline_tool] sandbox_failed tool_id=%s round=%s error=%s stdout_chars=%s stderr_chars=%s",
                    spec.tool_id,
                    round_num,
                    sandbox.error,
                    len(sandbox.stdout or ""),
                    len(sandbox.stderr or ""),
                )
                reflection = self._reflect_on_failure(
                    spec=spec,
                    code=generated.code,
                    stage="沙箱执行",
                    error=sandbox.error or "未知错误",
                    stdout=sandbox.stdout,
                    stderr=sandbox.stderr,
                    output=sandbox.output,
                    fact_report=fact_report,
                sandbox_success=getattr(sandbox, "success", False),
            )
                iteration.reflection = reflection
                iteration.decision = "FAIL" if not reflection.should_retry else "RETRY"
                iteration.feedback = self._build_rich_feedback(
                    stage="沙箱执行",
                    errors=[sandbox.error or "未知错误"],
                    code=generated.code,
                    spec=spec,
                    stdout=sandbox.stdout,
                    stderr=sandbox.stderr,
                    output=sandbox.output,
                    reflection=reflection,
                )
                return _finish(
                    "blocked" if not reflection.should_retry else "fail",
                    self._build_agentic_failure_summary(iteration),
                    should_retry=reflection.should_retry,
                )

            _report("output_evaluation", "正在质量评估...", 0.65)
            eval_score = self._evaluator.evaluate(sandbox, spec, generated.code, fact_report=fact_report)
            iteration.eval_score = eval_score
            business_verification = self._business_verifiers.resolve(spec).verify(sandbox, spec, fact_report)
            iteration.business_verification = business_verification
            self._persist_stage_artifact(
                tool_id=spec.tool_id,
                run_id=run_id,
                round_num=round_num,
                stage="output_evaluation",
                payload={
                    "eval_score": eval_score.model_dump(),
                    "business_verification": business_verification.model_dump(),
                },
                code=generated.code,
            )
            # 评估结果实时透出（含业务验收是否通过）
            _eval_extra = self._build_eval_result_extra(eval_score, round_num)
            _eval_extra["eval_result"]["business_passed"] = business_verification.passed
            _eval_passed = eval_score.total >= PASS_THRESHOLD
            _report(
                "output_evaluation",
                f"质量评估完成：{eval_score.total}/10（{'达标' if _eval_passed else '未达标'}）",
                0.77,
                extra=_eval_extra,
            )

            if self._is_systemic_business_verifier_failure(business_verification):
                iteration.decision = "FAIL"
                summary = "系统级业务验收规则配置错误，当前失败并非代码实现缺陷。"
                iteration.feedback = summary
                return _finish("blocked", summary, should_retry=False)

            if eval_score.total >= PASS_THRESHOLD and business_verification.passed:
                logger.info(
                    "🔁 [pipeline_tool] quality_pass tool_id=%s round=%s score=%.2f business_pass=%s",
                    spec.tool_id,
                    round_num,
                    eval_score.total,
                    business_verification.passed,
                )
                _report("edge_testing", "正在执行边缘测试验证...", 0.8)
                edge_failures = self._run_edge_tests(generated.code, spec)
                if edge_failures:
                    reflection = self._reflect_on_failure(
                        spec=spec,
                        code=generated.code,
                        stage="边缘测试",
                        error="\n".join(edge_failures),
                        stdout=sandbox.stdout,
                        stderr="",
                        output=sandbox.output,
                        fact_report=fact_report,
                        sandbox_success=getattr(sandbox, "success", False),
                    )
                    iteration.reflection = reflection
                    iteration.decision = "RETRY"
                    iteration.feedback = self._build_rich_feedback(
                        stage="边缘测试",
                        errors=edge_failures,
                        code=generated.code,
                        spec=spec,
                        stdout=sandbox.stdout,
                        output=sandbox.output,
                        reflection=reflection,
                    )
                    return _finish("fail", self._build_agentic_failure_summary(iteration), should_retry=reflection.should_retry)

                iteration.decision = "PASS"
                result = _finish("pass", "pipeline_tool 单轮质控通过", should_retry=False)
                logger.info(
                    "🔁 [pipeline_tool] pass tool_id=%s round=%s code_path=%s snapshot=%s",
                    spec.tool_id,
                    round_num,
                    result.code_path,
                    result.snapshot_path,
                )
                _report("output_evaluation", "评估通过", 1.0)
                return result

            failure_messages: List[str] = []
            logger.warning(
                "🔁 [pipeline_tool] quality_failed tool_id=%s round=%s score=%.2f business_pass=%s business_failures=%s",
                spec.tool_id,
                round_num,
                eval_score.total,
                business_verification.passed,
                len(business_verification.failures or []),
            )
            extra_context_parts: List[str] = []
            if eval_score.total < PASS_THRESHOLD:
                failure_messages.extend(self._build_eval_errors(eval_score))
                extra_context_parts.append(self._build_eval_reflection_context(eval_score))
            if not business_verification.passed:
                failure_messages.extend(self._build_business_errors(business_verification))
                extra_context_parts.append(self._build_business_reflection_context(business_verification))
            reflection = self._reflect_on_failure(
                spec=spec,
                code=generated.code,
                stage="质量评估/业务验收",
                error="\n".join(failure_messages),
                stdout=sandbox.stdout,
                stderr=sandbox.stderr,
                output=sandbox.output,
                fact_report=fact_report,
                    sandbox_success=getattr(sandbox, "success", False),
                    extra_context="\n\n".join(part for part in extra_context_parts if part),
            )
            iteration.reflection = reflection
            iteration.decision = "FAIL" if not reflection.should_retry else "RETRY"
            iteration.feedback = self._build_rich_feedback(
                stage="质量评估/业务验收",
                errors=failure_messages,
                code=generated.code,
                spec=spec,
                stdout=sandbox.stdout,
                stderr=sandbox.stderr,
                output=sandbox.output,
                reflection=reflection,
            )
            return _finish(
                "blocked" if not reflection.should_retry else "fail",
                self._build_agentic_failure_summary(iteration),
                should_retry=reflection.should_retry,
            )
        except Exception as exc:
            logger.error("pipeline_tool 单轮执行异常: %s", exc, exc_info=True)
            # 异常（尤其是代码生成超时）必须显式上报到进度流，
            # 否则前端停留在“正在生成代码...”看不到失败原因
            exc_text = str(exc)
            is_timeout = "timed out" in exc_text.lower() or "timeout" in exc_text.lower()
            if is_timeout:
                _report(
                    "error",
                    f"第 {round_num} 轮代码生成超时（{codegen_timeout or CODEGEN_LLM_TIMEOUT_SECONDS}s）: {exc_text}。"
                    "可在生成失败后调大超时时长重新提交。",
                    0.95,
                )
            else:
                _report("error", f"第 {round_num} 轮执行异常: {exc_text}", 0.95)
            iteration.decision = "FAIL"
            iteration.feedback = f"pipeline_tool 执行异常: {exc}"
            return _finish("blocked", iteration.feedback, should_retry=False)

    @staticmethod
    def _build_pipeline_tool_evaluation(iteration: IterationRound) -> Dict[str, Any]:
        payload: Dict[str, Any] = {}
        if iteration.eval_score:
            payload["eval_score"] = iteration.eval_score.model_dump()
        if iteration.business_verification:
            payload["business_verification"] = iteration.business_verification.model_dump()
        if iteration.reflection:
            payload["reflection"] = iteration.reflection.model_dump()
        return payload

    @staticmethod
    def _build_agentic_failure_summary(iteration: IterationRound) -> str:
        parts: List[str] = [f"第 {iteration.round_number} 轮失败"]
        if iteration.validation and not iteration.validation.passed:
            parts.append("静态验证失败：" + "；".join(iteration.validation.errors[:5]))
        if iteration.sandbox and not iteration.sandbox.success:
            parts.append(f"沙箱执行失败：{iteration.sandbox.error or '未知错误'}")
            if iteration.sandbox.stdout:
                parts.append("stdout 摘要：" + IterationController._summarize_text(iteration.sandbox.stdout, max_chars=1000))
            if iteration.sandbox.stderr:
                parts.append("stderr 摘要：" + IterationController._summarize_text(iteration.sandbox.stderr, max_chars=1000))
        if iteration.eval_score:
            parts.append(f"评分：total={iteration.eval_score.total}/10")
        if iteration.business_verification and not iteration.business_verification.passed:
            failures = [failure.message for failure in iteration.business_verification.failures[:5]]
            if failures:
                parts.append("业务验收失败：" + "；".join(failures))
        if iteration.reflection:
            parts.append(f"根因：{iteration.reflection.root_cause}")
            if iteration.reflection.fix_plan:
                parts.append("修复计划：" + "；".join(iteration.reflection.fix_plan[:5]))
        return "\n".join(parts)

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
        fact_report: Optional[ImplementationFactReport] = None,
        sandbox_success: bool = False,
    ) -> ReflectionResult:
        """LLM 反思 — agentic 模式，LLM 按需获取证据分析根因并制定修复计划"""

        # ── 构建工具函数（闭包）──
        def get_error_info() -> str:
            """获取失败信息（阶段、错误消息、stderr）"""
            import json as _json
            info = {
                "stage": stage,
                "error": error[:2000],
                "stderr": (stderr or "")[:2000],
                "extra_context": extra_context[:1000] if extra_context else "",
            }
            return _json.dumps(info, ensure_ascii=False)

        def get_sandbox_logs(lines: int = 30) -> str:
            """获取沙箱运行日志的最后 N 行"""
            if not stdout:
                return "（无日志）"
            log_lines = stdout.strip().split("\n")
            try:
                lines = int(lines)
            except (TypeError, ValueError):
                lines = 30
            return "\n".join(log_lines[-lines:])

        def get_output() -> str:
            """获取 Skill 输出结果"""
            if output is None:
                return "（无输出）"
            try:
                return json.dumps(output, ensure_ascii=False, indent=2, default=str)[:4000]
            except Exception:
                return str(output)[:4000]

        def get_code_section(start_line: int = 1, end_line: int = 50) -> str:
            """获取代码的指定行范围"""
            code_lines = code.split("\n")
            try:
                start_line = int(start_line)
                end_line = int(end_line)
            except (TypeError, ValueError):
                pass
            return "\n".join(code_lines[start_line - 1 : end_line])

        def get_helper_signatures() -> str:
            """获取已确认可用的 helper 函数签名"""
            if not fact_report or not fact_report.available_helpers:
                return "（无 helper）"
            lines = []
            for h in fact_report.available_helpers:
                ds = h.data_source_handling or "self_contained"
                sig = h.signature or "(无签名)"
                lines.append(f"{h.name}: {sig} [数据源:{ds}]")
            return "\n".join(lines)

        tools = {
            "get_error_info": get_error_info,
            "get_sandbox_logs": get_sandbox_logs,
            "get_output": get_output,
            "get_code_section": get_code_section,
            "get_helper_signatures": get_helper_signatures,
        }

        # ── 引导式 system prompt（告诉 LLM 诊断流程，而不是随机探索）──
        system_prompt = (
            f"你是资深 Python 开发者。按以下流程逐步诊断 Skill 工具问题：\n\n"
            f"Skill 功能：{spec.description}\n"
            f"失败阶段：{stage}\n"
            f"沙箱执行状态：success={sandbox_success}\n\n"
            f"诊断流程（严格按顺序，每步只调用一个工具）：\n"
            f"  第1步: get_error_info → 了解失败类型（异常/数据矛盾/评分低）\n"
            f"  第2步: get_sandbox_logs(lines=40) + get_output → 看日志和输出\n"
            f"  第3步（可选）: get_code_section → 仅在前两步不足以定位根因时使用\n"
            f"  第4步: 立即输出 verdict\n\n"
            f"关键规则：\n"
            f"1. sandbox_success=true → 函数必然存在，根因是字段映射/业务逻辑\n"
            f"2. 代码调用 helper ≠ 需要换函数\n"
            f"3. 工具总调用次数 ≤4 次，超过后必须输出 verdict\n\n"
            f"<verdict>\n"
            f'{{"root_cause": "具体根因（哪行代码/哪个字段）", "fix_plan": ["步骤1", "步骤2"], '
            f'"should_retry": true/false, "confidence": 0.0-1.0}}\n'
            f"</verdict>"
        )

        try:
            client = self._get_client()
            logger.info(
                f"\n{'─'*50}\n"
                f"📤 [Reflection] Agentic LLM 启动 | tool_id={spec.tool_id}\n"
                f"{'─'*50}"
            )

            # 用线程超时包装 LLM 调用
            import threading
            # agentic 反思含最多 5 轮工具调用往返，配合深度推理模型需要充足时间；
            # 此前 120s 屡屡超时，且超时被误判为"不可修复"直接终止迭代
            REFLECTION_LLM_TIMEOUT = 300
            response_holder: Dict[str, Any] = {"raw": None, "error": None}

            def _call_reflection_llm() -> None:
                try:
                    from core.llm.tool_normalizer import ToolCallNormalizer

                    client.inject_tools(tools)
                    tool_defs = [
                        ToolCallNormalizer.normalize_tool_definition(func, name=name)
                        for name, func in tools.items()
                    ]
                    messages = [
                        Message(role="system", content=system_prompt),
                        Message(
                            role="user",
                            content="请按上述诊断流程逐步分析。先调用 get_error_info 开始。",
                        ),
                    ]
                    resp = client.chat(
                        messages,
                        tools=tool_defs,
                        auto_execute_tools=True,
                        max_tool_rounds=5,
                        temperature=0.2,
                        max_tokens=8192,
                    )
                    response_holder["raw"] = (resp.content or "").strip()
                except Exception as exc:
                    response_holder["error"] = str(exc)

            thread = threading.Thread(target=_call_reflection_llm, daemon=True)
            thread.start()
            thread.join(timeout=REFLECTION_LLM_TIMEOUT)

            if thread.is_alive():
                logger.warning(
                    f"⚠️ [Reflection] LLM 调用超时（{REFLECTION_LLM_TIMEOUT}s），跳过反思 | tool_id={spec.tool_id}"
                )
                # 反思超时属于基础设施问题，不是"不可修复"的业务判定：
                # 回退为继续重试（无定向修复计划），不得因反思超时直接终止迭代
                return ReflectionResult(
                    root_cause=f"反思 LLM 调用超时（{REFLECTION_LLM_TIMEOUT}s），已跳过反思分析，回退为普通重试",
                    fix_plan=[],
                    should_retry=True,
                    confidence=0.3,
                )

            if response_holder["error"]:
                logger.warning(f"⚠️ [Reflection] LLM 调用失败: {response_holder['error']}")
                return ReflectionResult(
                    root_cause=f"反思 LLM 调用失败: {response_holder['error']}",
                    fix_plan=[],
                    should_retry=False,
                )

            raw = response_holder["raw"] or ""
            logger.info(
                f"\n{'─'*50}\n"
                f"📥 [Reflection] LLM 输出 ({len(raw)} 字符)\n"
                f"{'─'*50}\n"
                f"{raw}\n"
                f"{'─'*50}"
            )

            import re
            # 优先从 <verdict> 标签中提取 JSON
            verdict_match = re.search(r"<verdict>\s*(.*?)\s*</verdict>", raw, re.DOTALL)
            if verdict_match:
                json_str = verdict_match.group(1).strip()
            else:
                fallback_match = re.search(r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}", raw, re.DOTALL)
                json_str = fallback_match.group() if fallback_match else ""

            if json_str:
                data = json.loads(json_str)
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

    # ==================== 财经专家判断 ====================

    def _check_no_data_and_advise(
        self,
        spec: SkillSpec,
        sandbox_output: Any,
        fact_report: Optional[ImplementationFactReport] = None,
    ) -> str:
        """检查沙箱输出是否包含 no_data，如果是则调用财经专家判断合理性 + 推荐换股。

        返回专家建议文本（用于注入 feedback 和 extra_context），无 no_data 则返回空字符串。
        """
        if not sandbox_output or not isinstance(sandbox_output, dict):
            return ""

        # 检测沙箱输出中是否有 no_data / 无数据 信号
        output_status = str(sandbox_output.get("status", "")).lower()
        has_no_data_signal = (
            output_status in ("no_data", "no_news", "no_pledge", "error")
            or "无数据" in str(sandbox_output.get("message", ""))
            or "无可用" in str(sandbox_output.get("message", ""))
            or "不可用" in str(sandbox_output.get("message", ""))
        )
        if not has_no_data_signal:
            return ""

        # 检查是否所有数值字段都为 null（另一种 no_data 信号）
        if output_status == "success":
            profile = sandbox_output.get("profile", {})
            if isinstance(profile, dict):
                null_fields = sum(
                    1 for v in profile.values() if v is None or v == ""
                )
                total_fields = len(profile)
                if total_fields >= 3 and null_fields >= total_fields * 0.7:
                    has_no_data_signal = True

        if not has_no_data_signal:
            return ""

        # 提取测试股票信息
        test_symbol = (
            spec.test_input.get("symbol")
            or spec.test_input.get("code")
            or str(sandbox_output.get("symbol", ""))
            or ""
        )
        if not test_symbol:
            return ""

        # 如果 fact_report 已经有专家判断（侦察层做的），直接复用
        if fact_report and fact_report.notes:
            expert_notes = [
                n for n in fact_report.notes
                if "专家判断" in n or "推荐测试股票" in n or "建议换股" in n
            ]
            if expert_notes:
                return "【财经专家判断（来自侦察层）】\n" + "\n".join(expert_notes)

        # 调用财经专家判断
        try:
            from .financial_expert_advisor import get_financial_expert_advisor

            advisor = get_financial_expert_advisor(
                llm_client=self._get_client_safe() if hasattr(self, "_get_client_safe") else self._get_client(),
                provider=self._provider,
                model=self._model,
            )

            # 获取股票基础信息
            stock_name = ""
            industry = ""
            try:
                from core.skill_runtime.data_access import get_stock_basic_info

                basic = get_stock_basic_info(test_symbol) or {}
                stock_name = basic.get("name", "")
                industry = basic.get("industry", "")
            except Exception:
                pass

            # 推断数据类型
            data_type = "所需数据"
            helper_name = ""
            if fact_report and fact_report.available_helpers:
                helper_name = fact_report.available_helpers[0].name
                name_lower = helper_name.lower()
                if "pledge" in name_lower:
                    data_type = "质押数据"
                elif "financial" in name_lower or "annual" in name_lower:
                    data_type = "财务数据"
                elif "news" in name_lower or "announcement" in name_lower:
                    data_type = "新闻/公告数据"
                elif "valuation" in name_lower:
                    data_type = "估值数据"

            # helper 的 warnings（从 sandbox_output 提取）
            helper_warnings = []
            if isinstance(sandbox_output.get("data_source_note"), str):
                helper_warnings.append(sandbox_output.get("data_source_note"))
            if sandbox_output.get("note"):
                helper_warnings.append(str(sandbox_output.get("note")))

            judgment = advisor.judge_no_data_rationality(
                stock_symbol=test_symbol,
                stock_name=stock_name,
                industry=industry,
                skill_purpose=spec.display_name or spec.description or "",
                data_type=data_type,
                helper_name=helper_name,
                helper_warnings=helper_warnings,
                skill_category=getattr(spec, "category", ""),
            )

            logger.info(
                f"🧠 [财经专家] no_data 判断: is_rational={judgment.is_rational}, "
                f"confidence={judgment.confidence:.2f}, stock={test_symbol}"
            )
            return judgment.to_feedback_text()

        except Exception as e:
            logger.warning(f"⚠️ 财经专家判断失败: {e}")
            return ""

    def _get_client_safe(self):
        """安全获取 LLM 客户端，失败返回 None"""
        try:
            return self._get_client()
        except Exception:
            return None

    # ==================== 标准函数参考对比 ====================

    def _compare_with_reference_helpers(
        self,
        sandbox_result: SandboxResult,
        spec: SkillSpec,
        fact_report: Optional[ImplementationFactReport] = None,
    ) -> List[str]:
        """
        当侦察层推荐了可复用的标准 helper 时，运行这些 helper 并与 Skill 输出对比。

        如果 Skill 输出与标准 helper 输出差异过大（如关键数值字段不一致），
        说明 Skill 代码没有正确复用/实现功能，应返回 RETRY。
        """
        failures: List[str] = []
        if not fact_report or not fact_report.available_helpers:
            return failures

        # 获取测试股票代码
        test_symbol = spec.test_input.get("symbol") or spec.test_input.get("code") or ""
        if not test_symbol:
            return failures

        for helper in fact_report.available_helpers[:3]:  # 最多比较 3 个 helpers
            try:
                # 动态导入并执行标准函数
                reference_result = self._run_reference_helper(
                    helper.module or "", helper.name or "", test_symbol, spec.test_input
                )
                if reference_result is None:
                    continue

                skill_output = sandbox_result.output

                # 提取关键数值字段进行对比
                diffs = self._compare_outputs(helper.name or "", reference_result, skill_output)
                if diffs:
                    failures.extend(diffs)
                    logger.info(
                        f"🔍 [参考对比] {helper.name}: 发现 {len(diffs)} 个差异"
                    )
                else:
                    logger.info(f"✅ [参考对比] {helper.name}: 输出一致，通过")
            except Exception as exc:
                logger.warning(f"⚠️ [参考对比] {helper.name}: 执行失败 {exc}")

        return failures

    @staticmethod
    def _run_reference_helper(
        module: str,
        function_name: str,
        symbol: str,
        test_input: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """动态导入并执行标准 helper 函数"""
        try:
            # module 已经是完整路径（如 core.skill_runtime.standard_financial_apis）
            # 直接使用，不要重复拼接
            func = None
            candidate_modules = [module]
            # 如果 module 不是以 core. 开头，补充候选路径
            if not module.startswith("core."):
                candidate_modules.append(f"core.skill_runtime.{module}")
                candidate_modules.append(f"core.tools.implementations.fundamentals.{module}")

            for full_module in candidate_modules:
                try:
                    mod = __import__(full_module, fromlist=[function_name])
                    func = getattr(mod, function_name, None)
                    if func is not None and callable(func):
                        break
                except ImportError:
                    continue

            if func is None or not callable(func):
                logger.warning(f"⚠️ [参考对比] 函数 {function_name} 在 {module} 中未找到")
                return None

            # 调用标准函数
            result = func(symbol=symbol)
            if isinstance(result, str):
                import json
                result = json.loads(result)
            return result if isinstance(result, dict) else {"value": result}
        except Exception as e:
            logger.warning(f"⚠️ [参考对比] 执行 {function_name} 失败: {e}")
            return None

    @staticmethod
    def _compare_outputs(
        helper_name: str,
        reference: Dict[str, Any],
        skill_output: Any,
    ) -> List[str]:
        """比较两个输出的关键差异"""
        diffs: List[str] = []

        # 递归提取数值字段
        def _extract_numeric(obj: Any, prefix: str = "") -> Dict[str, float]:
            values: Dict[str, float] = {}
            if isinstance(obj, dict):
                for k, v in obj.items():
                    full = f"{prefix}.{k}" if prefix else k
                    if isinstance(v, (int, float)) and not isinstance(v, bool):
                        values[full] = float(v)
                    elif isinstance(v, dict):
                        values.update(_extract_numeric(v, full))
            return values

        ref_values = _extract_numeric(reference)
        skill_values = _extract_numeric(skill_output) if isinstance(skill_output, dict) else {}

        if not ref_values:
            return diffs

        # 找到共同的字段进行比较
        common_fields = set(ref_values.keys()) & set(skill_values.keys())
        if not common_fields:
            diffs.append(
                f"[{helper_name}] 标准函数返回 {len(ref_values)} 个数值字段，"
                f"但 Skill 输出中找不到任何匹配字段，可能是字段命名不一致"
            )
            return diffs

        for field in sorted(common_fields):
            ref_val = ref_values[field]
            skill_val = skill_values[field]

            # 两个都是 0：全部通过（可能是真正的 0 值）
            if ref_val == 0.0 and skill_val == 0.0:
                continue

            # Reference 有值但 Skill 为 0：严重问题
            if ref_val != 0.0 and skill_val == 0.0:
                diffs.append(
                    f"[{helper_name}] 字段 {field}: 标准函数={ref_val}, Skill=0 "
                    f"(数据获取或计算逻辑有误，不应为 0)"
                )
                continue

            # Reference 为 0 但 Skill 有值：可能正常（Skill 提供了额外数据）
            if ref_val == 0.0 and skill_val != 0.0:
                continue

            # 两者都有值，比较差异比例
            if ref_val != 0.0:
                ratio = abs(skill_val - ref_val) / abs(ref_val)
                if ratio > 0.5:  # 差异超过 50%
                    diffs.append(
                        f"[{helper_name}] 字段 {field}: 标准函数={ref_val:.4f}, "
                        f"Skill={skill_val:.4f} (差异 {ratio:.0%})"
                    )

        return diffs

    # ==================== 边缘测试 ====================

    def _run_edge_tests(self, code: str, spec: SkillSpec) -> List[str]:
        """
        在主测试通过后，运行额外的边缘测试场景：
        1. 空/无效参数测试 — 函数不应崩溃
        2. LLM 生成的测试用例 — 检查是否有 mock 数据

        边缘测试使用更短的超时（10s），强制执行“无效输入 5 秒内返回错误响应”的规则。
        """
        failures: List[str] = []

        # 边缘测试使用独立的短超时 runner，强制代码对无效输入快速失败
        edge_runner = self._get_edge_test_runner()

        edge_inputs = self._generate_edge_inputs(spec)
        for label, test_input in edge_inputs:
            try:
                result = edge_runner.run(code, spec, test_input=test_input)
                if not result.success:
                    # 沙箱执行崩溃或超时都算失败
                    err_msg = result.error or "未知"
                    if "超时" in err_msg or "timeout" in err_msg.lower():
                        failures.append(
                            f"边缘测试「{label}」超时：代码未在 10s 内对无效输入返回响应，"
                            f"必须在函数开头做股票代码预检并快速返回错误。详情: {err_msg}"
                        )
                    else:
                        failures.append(f"边缘测试「{label}」执行崩溃: {err_msg}")
                elif result.output is not None:
                    output_str = json.dumps(result.output, ensure_ascii=False, default=str)
                    if self._looks_like_mock_data(output_str):
                        failures.append(f"边缘测试「{label}」返回疑似模拟数据")
            except Exception as e:
                failures.append(f"边缘测试「{label}」异常: {e}")

        return failures

    def _get_edge_test_runner(self):
        """获取边缘测试专用 runner（短超时）。"""
        # 懒加载并缓存，避免每次边缘测试都创建新实例
        if getattr(self, "_edge_runner", None) is None:
            self._edge_runner = SandboxRunner(timeout=10)
        return self._edge_runner

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
    def _is_systemic_business_verifier_failure(result: BusinessVerificationResult) -> bool:
        unsupported = result.details.get("unsupported_rule_types") or []
        if unsupported:
            return True
        return any("未支持的业务验收规则类型" in failure.message for failure in result.failures)

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
    def _summarize_text(
        text: Any,
        *,
        max_chars: int,
        head_chars: Optional[int] = None,
        separator: str = "\n... (中间省略) ...\n",
    ) -> str:
        """长文本默认保留首尾，避免执行尾部异常信息被截断。"""
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
            stdout_excerpt = IterationController._summarize_text(
                stdout,
                max_chars=2200,
                head_chars=1200,
            )
            parts.append(f"\n## 标准输出 (stdout 摘要)\n{stdout_excerpt}")

            # 提取 helper 返回结构信息（关键：告诉代码生成器 helper 实际返回哪些字段）
            helper_return_keys = IterationController._extract_helper_return_keys(stdout)
            if helper_return_keys:
                parts.append(f"\n## Helper 实际返回字段（🚨 代码必须匹配这些字段名）\n{helper_return_keys}")

        if stderr:
            stderr_excerpt = IterationController._summarize_text(
                stderr,
                max_chars=2200,
                head_chars=1200,
            )
            parts.append(f"\n## 标准错误 (stderr 摘要)\n{stderr_excerpt}")

        if output is not None:
            try:
                output_str = IterationController._summarize_text(
                    json.dumps(output, ensure_ascii=False, indent=2, default=str),
                    max_chars=2500,
                    head_chars=1500,
                )
            except Exception:
                output_str = IterationController._summarize_text(
                    output,
                    max_chars=2500,
                    head_chars=1500,
                )
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
        parts.append("⚠️ 优先修复数据获取和业务逻辑问题，不要仅仅调整 status 字段值来规避验收。")

        return "\n".join(parts)

    @staticmethod
    def _build_eval_result_extra(score, round_num: int) -> Dict[str, Any]:
        """构造质量评估实时事件数据（供前端在评估完成瞬间展示）。"""
        data = score.model_dump()
        # total 是 @property，model_dump 不包含，需显式带出
        data["total"] = score.total
        data["round"] = round_num
        data["passed"] = score.total >= PASS_THRESHOLD
        return {"eval_result": data}

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

    @staticmethod
    def _extract_helper_return_keys(stdout: str) -> str:
        """从沙箱 stdout 提取 helper 函数的返回结构（字段名），帮助代码生成器正确映射"""
        import re
        # 匹配 "📊 xxx 返回结构: ['field1', 'field2', ...]" 或 "returned keys: ['field1', ...]"
        pattern = re.compile(r"(?:返回结构|returned keys|返回键).*?\[([^\]]+)\]", re.IGNORECASE)
        matches = pattern.findall(stdout)
        if not matches:
            # 也尝试匹配纯 "keys: ['...']" 格式
            pattern2 = re.compile(r"(?:keys|字段)[：:]\s*\[([^\]]+)\]", re.IGNORECASE)
            matches = pattern2.findall(stdout)

        if not matches:
            return ""

        lines = []
        seen_keys = set()
        for m in matches:
            keys_str = m.strip()
            # 解析 key 列表
            keys = [k.strip().strip("'\"") for k in keys_str.split(",") if k.strip().strip("'\"")]
            key_sig = ", ".join(keys[:12])  # 最多 12 个字段
            if key_sig and key_sig not in seen_keys:
                seen_keys.add(key_sig)
                lines.append(f"  [{key_sig}]")

        if not lines:
            return ""
        return "\n".join(lines[:5])  # 最多 5 个 helper 的返回结构
