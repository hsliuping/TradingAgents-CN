"""
输出评估器 — 双层评估机制

第 1 层: 基础检查（零 LLM 成本）
  - 返回值非空
  - 返回类型正确
  - 包含期望字段

第 2 层: Judge LLM 深度评分（5 个维度，0-10 分）
  - 可执行性、真实性、完整性、相关性、格式质量
"""

import json
import logging
import queue
import threading
from typing import Any, Callable, Dict, Optional

from core.llm import UnifiedLLMClient, Message

from .skill_spec import EvalScore, ImplementationFactReport, SandboxResult, SkillSpec

logger = logging.getLogger(__name__)

JUDGE_LLM_TIMEOUT_SECONDS = 120
JUDGE_LLM_MAX_TOKENS = 1200


class OutputEvaluator:
    """
    输出评估器

    对沙箱执行结果进行双层评估：基础检查（免费）+ Judge LLM（付费）。
    """

    def __init__(
        self,
        llm_client: Optional[UnifiedLLMClient] = None,
        provider: str = "deepseek",
        model: Optional[str] = None,
        skip_judge: bool = False,
        quick_llm_client: Optional[UnifiedLLMClient] = None,
    ):
        """
        Args:
            llm_client: 预配置的 LLM 客户端
            provider: LLM 提供商
            model: 模型名称
            skip_judge: 跳过 Judge LLM（仅做基础检查）
            quick_llm_client: 快速模型客户端（Judge 评分优先使用，失败回退主模型）
        """
        self._client = llm_client
        self._provider = provider
        self._model = model
        self._skip_judge = skip_judge
        self._quick_client = quick_llm_client

    def _get_client(self) -> UnifiedLLMClient:
        """懒加载 LLM 客户端"""
        if self._client is None:
            kwargs = {}
            if self._model:
                kwargs["model"] = self._model
            self._client = UnifiedLLMClient.from_provider(self._provider, **kwargs)
        return self._client

    def evaluate(
        self,
        sandbox_result: SandboxResult,
        spec: SkillSpec,
        code: str,
        fact_report: Optional[ImplementationFactReport] = None,
    ) -> EvalScore:
        """
        评估沙箱执行结果

        Args:
            sandbox_result: 沙箱执行结果
            spec: Skill 规格书
            code: 生成的代码
            fact_report: 侦察层事实报告（包含已命中的 available_helpers，用于防止 LLM 误判函数不存在）

        Returns:
            EvalScore: 评估打分
        """
        score = EvalScore()

        # ===== 第 1 层: 基础检查 =====
        basic_passed = self._basic_check(sandbox_result, spec, score)

        if not basic_passed:
            # 基础检查不过，直接返回低分
            return score

        # ===== 第 2 层: Judge LLM 深度评分 =====
        if not self._skip_judge:
            self._judge_llm_eval(sandbox_result, spec, code, score, fact_report)

        return score

    # ==================== 第 1 层: 基础检查 ====================

    def _basic_check(
        self, result: SandboxResult, spec: SkillSpec, score: EvalScore
    ) -> bool:
        """
        基础检查 — 零 LLM 成本

        Returns:
            bool: 是否通过基础检查
        """
        # 1. 执行是否成功
        if not result.success:
            score.executability = 0.0
            return False

        score.executability = 6.0  # 能跑起来至少 6 分

        output = result.output

        # 2. 返回值非空
        if output is None or output == "" or output == [] or output == {}:
            score.completeness = 1.0
            score.authenticity = 1.0
            return False

        score.completeness = 5.0  # 有返回至少 5 分

        # 3. 检查期望字段
        expected_fields = spec.expected_output.fields
        if expected_fields and isinstance(output, (list, dict)):
            sample = output[0] if isinstance(output, list) and output else output
            if isinstance(sample, dict):
                present = sum(1 for f in expected_fields if f in sample)
                ratio = present / len(expected_fields) if expected_fields else 1.0
                score.completeness = round(5.0 + ratio * 5.0, 1)
                score.format_quality = round(ratio * 8.0, 1)

        # 4. 返回类型检查
        expected_type = spec.expected_output.type
        if "list" in expected_type and isinstance(output, list):
            score.format_quality = max(score.format_quality, 7.0)
        elif "dict" in expected_type and isinstance(output, dict):
            score.format_quality = max(score.format_quality, 7.0)
        elif "str" in expected_type and isinstance(output, str):
            score.format_quality = max(score.format_quality, 7.0)

        score.authenticity = 5.0  # 基础检查无法判断真实性
        score.relevance = 5.0    # 基础检查无法判断相关性

        return True

    # ==================== 第 2 层: Judge LLM (Simple Inline Prompt) ====================

    def _judge_llm_eval(
        self,
        result: SandboxResult,
        spec: SkillSpec,
        code: str,
        score: EvalScore,
        fact_report: Optional[ImplementationFactReport] = None,
    ) -> None:
        """Judge LLM 深度评分 — 简单内联 prompt，所有证据一次性传入"""
        import json as _json

        test_symbol = spec.test_input.get("symbol", "") or spec.test_input.get("code", "")
        test_name = spec.test_input.get("name", "") or spec.test_input.get("display_name", "")
        output_preview = self._format_output_preview(result.output)

        # 构建 helper 清单
        helpers_block = "（无 helper）"
        if fact_report and fact_report.available_helpers:
            lines = []
            for h in fact_report.available_helpers:
                ds_tag = getattr(h, 'data_source_handling', 'self_contained') or 'self_contained'
                sig = getattr(h, 'signature', '') or '(无签名)'
                lines.append(f"  {h.name}: {sig} [{ds_tag}]")
            if lines:
                helpers_block = "\n".join(lines)

        # 构建日志摘要（取最后 60 行，约 4000 字符）
        log_block = "（无日志）"
        if result.stdout:
            log_lines = result.stdout.strip().split("\n")
            log_block = "\n".join(log_lines[-60:])

        # 构建内联 user message
        user_msg = (
            f"测试标的: {test_symbol} {test_name}\n"
            f"Skill 名称: {spec.display_name}\n\n"
            f"【沙箱执行结果】\n"
            f"  success: {result.success}\n"
            f"  error: {result.error or '无'}\n"
            f"  输出 JSON: {output_preview}\n\n"
            f"【沙箱日志（最后 60 行）】\n{log_block}\n\n"
            f"【已确认可用的 helper 函数】\n{helpers_block}\n\n"
            f"评分标准（1-10 分）:\n"
            f"  executability: 正常执行≥7，有异常≤3\n"
            f"  authenticity: 真实数据≥8，数据矛盾≤3，no_data 合理 5-6\n"
            f"  completeness: 字段完整≥8，核心字段为空≤4\n"
            f"  relevance: 精准匹配≥8，答非所问≤3\n"
            f"  format_quality: 格式规范≥7，命名混乱≤4\n\n"
            f"规则：执行成功=所有函数必然存在，严禁根据训练知识判断函数'不存在'\n\n"
            f"输出格式，只输出以下，不要其他内容：\n"
            f"<verdict>\n"
            f'{{"executability": <分>, "authenticity": <分>, "completeness": <分>, '
            f'"relevance": <分>, "format_quality": <分>, "expert_comment": "<一句话>"}}\n'
            f"</verdict>"
        )

        try:
            import re

            logger.info(f"\n{'─'*50}\n📤 [OutputEvaluator] Judge LLM 启动 ({len(user_msg)} 字符)\n{'─'*50}")
            raw = self._call_judge_llm_simple(user_msg, spec.tool_id)
            if raw is None:
                logger.warning("Judge LLM 超时，保留基础检查分数 | tool_id=%s", spec.tool_id)
                return

            logger.info(f"\n{'─'*50}\n📥 [OutputEvaluator] Judge LLM 输出\n{'─'*50}\n{raw}\n{'─'*50}")

            # 从 <verdict> 标签提取 JSON
            verdict_match = re.search(r"<verdict>\s*(.*?)\s*</verdict>", raw, re.DOTALL)
            if verdict_match:
                json_str = verdict_match.group(1).strip()
            else:
                fallback = re.search(r"\{[^{}]*\}", raw)
                json_str = fallback.group() if fallback else ""

            if json_str:
                scores = _json.loads(json_str)
                score.executability = float(scores.get("executability", score.executability))
                score.authenticity = float(scores.get("authenticity", score.authenticity))
                score.completeness = float(scores.get("completeness", score.completeness))
                score.relevance = float(scores.get("relevance", score.relevance))
                score.format_quality = float(scores.get("format_quality", score.format_quality))

                # 硬规则：执行成功必须≥7
                if result.success and score.executability < 7.0:
                    logger.warning(f"LLM 误判: success=True 但 executability={score.executability}<7，强制提升")
                    score.executability = 7.0

                comment = str(scores.get("expert_comment", "")).strip()
                if comment:
                    score.expert_comment = comment
                    logger.info(f"🎯 Judge LLM 评分: {score.total} | {comment}")
                else:
                    logger.info(f"🎯 Judge LLM 评分: {score.total}")
            else:
                logger.warning(f"⚠️ Judge LLM 输出中未找到 JSON: {raw[:500]}")
        except Exception as e:
            logger.warning(f"Judge LLM 评分失败，保留基础检查分数: {e}")

    def _call_judge_llm_simple(self, user_msg: str, tool_id: str) -> Optional[str]:
        """简单 LLM 调用（无工具，单次请求 + 超时保护）。

        Judge 评分是判断类任务，优先走快速模型（秒级），
        快速模型失败或空回复时回退主模型。
        """
        result_queue: "queue.Queue[tuple[str, Any]]" = queue.Queue(maxsize=1)

        def _worker() -> None:
            try:
                messages = [
                    Message(role="system", content="你是金融数据评估专家，评估 Skill 工具的输出质量。严格按格式输出 <verdict> JSON。"),
                    Message(role="user", content=user_msg),
                ]
                if self._quick_client is not None:
                    try:
                        response = self._quick_client.chat(
                            messages, temperature=0.0, max_tokens=2048
                        )
                        content = (response.content or "").strip()
                        if content:
                            result_queue.put(("ok", content))
                            return
                        logger.warning("Judge 快速模型返回空内容，回退主模型")
                    except Exception as quick_exc:
                        logger.warning(f"Judge 快速模型调用失败，回退主模型: {quick_exc}")
                client = self._get_client()
                response = client.chat(messages, temperature=0.0, max_tokens=2048)
                result_queue.put(("ok", response.content or ""))
            except Exception as exc:
                result_queue.put(("error", exc))

        worker = threading.Thread(
            target=_worker, name=f"skill-judge-{tool_id}", daemon=True
        )
        worker.start()
        worker.join(JUDGE_LLM_TIMEOUT_SECONDS)

        if worker.is_alive():
            return None
        status, payload = result_queue.get_nowait()
        if status == "error":
            raise payload
        return str(payload)

    # ==================== 工具方法 ====================

    @staticmethod
    def _format_output_preview(output: Any, max_len: int = 8000) -> str:
        """格式化输出预览"""
        if output is None:
            return "(空)"
        try:
            text = json.dumps(output, ensure_ascii=False, indent=2, default=str)
        except (TypeError, ValueError):
            text = str(output)
        if len(text) > max_len:
            text = text[:max_len] + "\n... (截断)"
        return text
