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
from typing import Any, Optional

from core.llm import UnifiedLLMClient, Message

from .skill_spec import EvalScore, SandboxResult, SkillSpec

logger = logging.getLogger(__name__)


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
    ):
        """
        Args:
            llm_client: 预配置的 LLM 客户端
            provider: LLM 提供商
            model: 模型名称
            skip_judge: 跳过 Judge LLM（仅做基础检查）
        """
        self._client = llm_client
        self._provider = provider
        self._model = model
        self._skip_judge = skip_judge

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
    ) -> EvalScore:
        """
        评估沙箱执行结果

        Args:
            sandbox_result: 沙箱执行结果
            spec: Skill 规格书
            code: 生成的代码

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
            self._judge_llm_eval(sandbox_result, spec, code, score)

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

    # ==================== 第 2 层: Judge LLM ====================

    def _judge_llm_eval(
        self,
        result: SandboxResult,
        spec: SkillSpec,
        code: str,
        score: EvalScore,
    ) -> None:
        """Judge LLM 深度评分"""
        client = self._get_client()
        output_preview = self._format_output_preview(result.output)

        prompt = (
            "你是一个代码质量评审专家。请对以下工具函数的执行结果进行评分。\n\n"
            f"【Skill 规格】\n"
            f"- 名称: {spec.display_name}\n"
            f"- 描述: {spec.description}\n"
            f"- 期望输出类型: {spec.expected_output.type}\n"
            f"- 期望字段: {', '.join(spec.expected_output.fields) or '无'}\n\n"
            f"【执行结果】\n{output_preview}\n\n"
            f"【生成的代码】\n```python\n{code[:2000]}\n```\n\n"
            "【评分说明】\n"
            "- 若返回 {\"status\": \"success\", \"data\": [], \"message\": \"未找到xxx数据\"}，说明真实调用了数据源但无数据，应给 authenticity≥7、completeness≥6，不要因数据为空而打低分。\n"
            "- 若返回了 mock/模拟/假数据，authenticity 应打低分。\n"
            "- 代码能执行且格式正确，executability、format_quality 应≥7。\n\n"
            "请用 JSON 格式输出 5 个维度的评分（0-10），不要输出其他内容：\n"
            '{"executability": <分>, "authenticity": <分>, '
            '"completeness": <分>, "relevance": <分>, "format_quality": <分>}'
        )

        try:
            import re
            logger.info(
                f"\n{'─'*50}\n"
                f"📤 [OutputEvaluator] Judge LLM 输入 ({len(prompt)} 字符)\n"
                f"{'─'*50}\n"
                f"{prompt[:3000]}\n"
                f"{'...(截断)' if len(prompt) > 3000 else ''}\n"
                f"{'─'*50}"
            )
            messages = [Message(role="user", content=prompt)]
            response = client.chat(messages)
            raw = response.content or ""
            logger.info(
                f"\n{'─'*50}\n"
                f"📥 [OutputEvaluator] Judge LLM 输出 ({len(raw)} 字符)\n"
                f"{'─'*50}\n"
                f"{raw}\n"
                f"{'─'*50}"
            )

            json_match = re.search(r"\{[^}]+\}", raw, re.DOTALL)
            if json_match:
                scores = json.loads(json_match.group())
                score.executability = float(scores.get("executability", score.executability))
                score.authenticity = float(scores.get("authenticity", score.authenticity))
                score.completeness = float(scores.get("completeness", score.completeness))
                score.relevance = float(scores.get("relevance", score.relevance))
                score.format_quality = float(scores.get("format_quality", score.format_quality))
                logger.info(f"🎯 Judge LLM 评分: {score.total}")
            else:
                logger.warning(f"⚠️ Judge LLM 输出中未找到 JSON: {raw[:500]}")
        except Exception as e:
            logger.warning(f"Judge LLM 评分失败，保留基础检查分数: {e}")

    # ==================== 工具方法 ====================

    @staticmethod
    def _format_output_preview(output: Any, max_len: int = 1500) -> str:
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
