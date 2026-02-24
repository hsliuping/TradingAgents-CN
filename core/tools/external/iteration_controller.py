"""
迭代控制器 — 编排完整的 Skill 生成管线

流程：CodeGenerator → StaticValidator → SandboxRunner → OutputEvaluator
决策：PASS（评分 >= 7.0） / RETRY（< 7.0 且未超 3 轮） / FAIL（超过 3 轮）
"""

import logging
import time
from typing import Callable, Optional

from core.llm import UnifiedLLMClient

from .code_generator import CodeGenerator
from .output_evaluator import OutputEvaluator
from .sandbox_runner import SandboxRunner
from .skill_spec import (
    GeneratedCode,
    IterationRound,
    PipelineResult,
    SkillSpec,
)
from .static_validator import StaticValidator

logger = logging.getLogger(__name__)

# 最大迭代轮次
MAX_ITERATIONS = 3

# 通过阈值（加权总分），5.0 可接受：真实调用数据源但无数据时 Judge 易给 5-6 分
PASS_THRESHOLD = 5.0


class IterationController:
    """
    迭代控制器

    编排 CodeGenerator → StaticValidator → SandboxRunner → OutputEvaluator
    的完整管线，支持最多 3 轮自动重试。
    """

    def __init__(
        self,
        llm_client: Optional[UnifiedLLMClient] = None,
        provider: str = "deepseek",
        model: Optional[str] = None,
        max_iterations: int = MAX_ITERATIONS,
        skip_judge: bool = False,
    ):
        """
        Args:
            llm_client: 共享的 LLM 客户端
            provider: LLM 提供商
            model: 模型名称
            max_iterations: 最大迭代轮次
            skip_judge: 跳过 Judge LLM 评分（节省成本）
        """
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
        self._max_iterations = max_iterations

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
            initial_feedback: 初始反馈（优化场景使用，包含原始对话+代码+用户反馈）
            initial_code: 初始代码（优化场景使用，即当前代码）
            progress_callback: 进度回调 (stage, message, iteration, progress) 用于前端轮询同步

        Returns:
            PipelineResult: 管线最终结果
        """
        start_time = time.time()
        iterations = []
        feedback = initial_feedback
        previous_code = initial_code

        def _report(stage: str, message: str, it: int, prog: float):
            if progress_callback:
                try:
                    progress_callback(stage, message, it, prog)
                except Exception as e:
                    logger.warning(f"progress_callback 异常: {e}")

        for round_num in range(1, self._max_iterations + 1):
            logger.info(f"🔄 Skill 生成管线 — 第 {round_num}/{self._max_iterations} 轮")
            _report("iteration", f"第 {round_num}/{self._max_iterations} 轮", round_num, 0)

            iteration = IterationRound(round_number=round_num)

            # ===== 阶段 1: 代码生成 =====
            _report("code_generation", "正在生成代码...", round_num, 0.1)
            try:
                generated = self._generator.generate(
                    spec, feedback=feedback, previous_code=previous_code
                )
                iteration.generated_code = generated
                logger.info(f"✅ 代码生成完成 ({generated.generation_time}s)")
                _report("code_generation", f"代码生成完成 ({generated.generation_time}s)", round_num, 0.25)
            except Exception as e:
                logger.error(f"❌ 代码生成失败: {e}")
                iteration.decision = "FAIL"
                iteration.feedback = f"代码生成失败: {e}"
                iterations.append(iteration)
                break

            # ===== 阶段 2: 静态验证 =====
            _report("static_validation", "正在语法检查...", round_num, 0.3)
            validation = self._validator.validate(generated, spec)
            iteration.validation = validation

            if not validation.passed:
                feedback = self._build_feedback("静态验证", validation.errors)
                previous_code = generated.code
                iteration.decision = "RETRY"
                iteration.feedback = feedback
                iterations.append(iteration)
                _report("static_validation", f"静态验证失败，重试中...", round_num, 0.4)
                logger.warning(f"⚠️ 静态验证失败: {validation.errors}")
                continue

            logger.info("✅ 静态验证通过")
            _report("static_validation", "语法检查通过", round_num, 0.45)

            # ===== 阶段 3: 沙箱执行 =====
            _report("sandbox_execution", "正在沙箱执行...", round_num, 0.5)
            sandbox = self._runner.run(generated.code, spec)
            iteration.sandbox = sandbox

            if not sandbox.success:
                feedback = self._build_feedback("沙箱执行", [sandbox.error or "未知错误"])
                previous_code = generated.code
                iteration.decision = "RETRY"
                iteration.feedback = feedback
                iterations.append(iteration)
                _report("sandbox_execution", f"沙箱执行失败，重试中...", round_num, 0.6)
                logger.warning(f"⚠️ 沙箱执行失败: {sandbox.error}")
                continue

            logger.info(f"✅ 沙箱执行成功 ({sandbox.execution_time}s)")
            _report("sandbox_execution", f"沙箱执行成功 ({sandbox.execution_time}s)", round_num, 0.7)

            # ===== 阶段 4: 输出评估 =====
            _report("output_evaluation", "正在质量评估...", round_num, 0.75)
            eval_score = self._evaluator.evaluate(sandbox, spec, generated.code)
            iteration.eval_score = eval_score
            logger.info(f"📊 评估总分: {eval_score.total}")

            if eval_score.total >= PASS_THRESHOLD:
                iteration.decision = "PASS"
                iterations.append(iteration)
                _report("output_evaluation", f"评估通过，总分: {eval_score.total}", round_num, 1.0)
                logger.info(f"🎉 Skill 生成成功！总分: {eval_score.total}")
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
                feedback = self._build_eval_feedback(eval_score)
                previous_code = generated.code
                iteration.decision = "RETRY"
                iteration.feedback = feedback
                iterations.append(iteration)
                _report("output_evaluation", f"评分不足 ({eval_score.total}/10)，重试中...", round_num, 0.85)
                logger.warning(f"⚠️ 评分不足 ({eval_score.total} < {PASS_THRESHOLD})，重试")

        # 所有轮次用尽，仍未通过
        logger.error(f"❌ Skill 生成失败 — {self._max_iterations} 轮迭代后仍未通过")
        return PipelineResult(
            success=False,
            tool_id=spec.tool_id,
            iterations=iterations,
            total_rounds=self._max_iterations,
            total_time=round(time.time() - start_time, 2),
            error=f"经过 {self._max_iterations} 轮迭代后仍未达到质量标准",
        )

    async def arun(self, spec: SkillSpec) -> PipelineResult:
        """异步版本的 run（当前为同步包装，后续可改为全异步）"""
        # TODO: 实现全异步版本（agenerate → avalidate → arun → aevaluate）
        import asyncio
        return await asyncio.get_event_loop().run_in_executor(None, self.run, spec)

    # ==================== 反馈构建 ====================

    @staticmethod
    def _build_feedback(stage: str, errors: list) -> str:
        """构建反馈消息"""
        error_lines = "\n".join(f"  - {e}" for e in errors[:5])
        return f"【{stage}失败】\n{error_lines}"

    @staticmethod
    def _build_eval_feedback(score) -> str:
        """根据评分构建详细反馈"""
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
