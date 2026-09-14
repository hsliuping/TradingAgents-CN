# -*- coding: utf-8 -*-
"""管线超时控制与 Judge 模型分级测试。

背景：代码生成用深度思考模型常需 3-6 分钟，240s 默认超时多次触发
"Request timed out"，且 OpenAI SDK 超时报文（timed out）与重试关键词
（timeout）不匹配导致从不重试；Judge 质量评估为判断类任务却被绑定
思考模型。本组测试覆盖：超时可重试、Judge 走快速模型、代码生成
超时可按次覆盖。
"""
from types import SimpleNamespace

from core.tools.external.code_generator import (
    CODEGEN_LLM_TIMEOUT_SECONDS,
    CodeGenerator,
)
from core.tools.external.output_evaluator import OutputEvaluator
from core.utils.retry import is_retryable


class _FakeClient:
    def __init__(self, content: str = "ok", raise_exc: Exception | None = None):
        self._content = content
        self._raise = raise_exc
        self.calls = 0

    def chat(self, messages, **kwargs):
        self.calls += 1
        if self._raise:
            raise self._raise
        return SimpleNamespace(content=self._content)


# ---------- 超时可重试 ----------

def test_openai_timeout_message_is_retryable():
    # OpenAI SDK 的超时报文是 "Request timed out."（timed out 两个词），
    # 此前关键词表只有 "timeout" 导致匹配不上、从不重试
    assert is_retryable(Exception("Request timed out.")) is True
    assert is_retryable(Exception("APITimeoutError: Request timed out.")) is True
    assert is_retryable(Exception("Read timeout")) is True


def test_non_retryable_error_still_not_retried():
    assert is_retryable(Exception("Error code: 403 - AccountOverdueError")) is False
    assert is_retryable(ValueError("bad spec")) is False


# ---------- Judge 走快速模型 ----------

def test_judge_uses_quick_model():
    quick, main = _FakeClient("<verdict>{}</verdict>"), _FakeClient("<verdict>{}</verdict>")
    evaluator = OutputEvaluator(llm_client=main, quick_llm_client=quick)

    out = evaluator._call_judge_llm_simple("评估输出", "tid")

    assert out == "<verdict>{}</verdict>"
    assert quick.calls == 1
    assert main.calls == 0


def test_judge_falls_back_to_main():
    quick = _FakeClient(raise_exc=RuntimeError("Error code: 403"))
    main = _FakeClient("<verdict>{}</verdict>")
    evaluator = OutputEvaluator(llm_client=main, quick_llm_client=quick)

    out = evaluator._call_judge_llm_simple("评估输出", "tid")

    assert out == "<verdict>{}</verdict>"
    assert main.calls == 1


def test_judge_without_quick_uses_main():
    main = _FakeClient("<verdict>{}</verdict>")
    evaluator = OutputEvaluator(llm_client=main)

    out = evaluator._call_judge_llm_simple("评估输出", "tid")

    assert out == "<verdict>{}</verdict>"
    assert main.calls == 1


# ---------- 代码生成超时按次覆盖 ----------

class _FakeAdapterClient:
    """带 adapter/config 结构的假客户端，用于验证超时覆写"""

    def __init__(self, timeout: int):
        self._adapter = SimpleNamespace(
            config=SimpleNamespace(timeout=timeout),
            initialize=lambda: None,
        )


def test_codegen_default_timeout_is_480():
    assert CODEGEN_LLM_TIMEOUT_SECONDS == 480


def test_codegen_get_client_overrides_timeout():
    client = _FakeAdapterClient(timeout=240)
    generator = CodeGenerator(llm_client=client)  # type: ignore[arg-type]

    generator._get_client(timeout_seconds=900)

    assert client._adapter.config.timeout == 900


def test_codegen_get_client_resets_to_smaller_timeout():
    # 用户可以把超时调小（如换成快模型后），不能只升不降
    client = _FakeAdapterClient(timeout=900)
    generator = CodeGenerator(llm_client=client)  # type: ignore[arg-type]

    generator._get_client(timeout_seconds=120)

    assert client._adapter.config.timeout == 120
