"""验证分析师报告质量门禁（v3.5.0 项1）。

测试场景：
1. 空报告 → critical 失败，should_retry=True
2. 过短报告（<50 字符）→ critical 失败，should_retry=True
3. 命中兜底文案黑名单 → critical 失败，should_retry=True
4. 缺结论关键词 → warning 失败，should_retry=False
5. 正常报告 → 通过
6. AnalystAgent._check_and_retry_quality：critical 重试1次成功 → 用新报告替换，返回 None
7. AnalystAgent._check_and_retry_quality：critical 重试仍失败 → 返回 quality_flag（retried=True）
8. AnalystAgent._check_and_retry_quality：warning 不重试 → 返回 quality_flag（retried=False）

运行方式：
    env\\Scripts\\python.exe scripts\\validate_quality_gate.py
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from core.agents.quality_gate import (
    FALLBACK_BLACKLIST,
    MIN_REPORT_LENGTH,
    QualityCheckResult,
    validate_analyst_report,
)


# ================================================================
# L1: validate_analyst_report 单元测试
# ================================================================


def test_case_1_empty_report() -> bool:
    """测试1：空报告 → critical"""
    print("\n[测试1] 空报告 → critical 失败")
    result = validate_analyst_report(content="", agent_id="news_analyst", ticker="600519")

    if result.is_valid:
        print(f"  ❌ 失败：期望 is_valid=False，实际 True")
        return False
    if result.severity != "critical":
        print(f"  ❌ 失败：期望 severity=critical，实际 {result.severity}")
        return False
    if not result.should_retry:
        print(f"  ❌ 失败：期望 should_retry=True（critical 应重试）")
        return False
    if "为空" not in result.reason:
        print(f"  ❌ 失败：期望 reason 包含 '为空'，实际 '{result.reason}'")
        return False

    print(f"  ✅ 通过：空报告被识别为 critical（reason={result.reason}）")
    return True


def test_case_2_short_report() -> bool:
    """测试2：过短报告 → critical"""
    print(f"\n[测试2] 过短报告（<{MIN_REPORT_LENGTH} 字符）→ critical 失败")

    short_content = "数据不足。"  # 5 字符
    result = validate_analyst_report(
        content=short_content, agent_id="market_analyst", ticker="600519"
    )

    if result.is_valid:
        print(f"  ❌ 失败：期望 is_valid=False")
        return False
    if result.severity != "critical":
        print(f"  ❌ 失败：期望 severity=critical，实际 {result.severity}")
        return False
    if not result.should_retry:
        print(f"  ❌ 失败：期望 should_retry=True")
        return False
    if "过短" not in result.reason:
        print(f"  ❌ 失败：期望 reason 包含 '过短'，实际 '{result.reason}'")
        return False

    print(f"  ✅ 通过：过短报告被识别为 critical（reason={result.reason}）")
    return True


def test_case_3_fallback_blacklist() -> bool:
    """测试3：命中兜底文案黑名单 → critical"""
    print("\n[测试3] 命中兜底文案黑名单 → critical 失败")

    all_pass = True
    for pattern in FALLBACK_BLACKLIST:
        # 把黑名单文案拼成"长但仍是兜底"的内容
        content = f"前言部分。{pattern}。结语部分。" * 2
        result = validate_analyst_report(
            content=content, agent_id="fundamentals_analyst", ticker="600519"
        )

        if result.is_valid:
            print(f"  ❌ 失败：黑名单文案 '{pattern[:30]}...' 未被识别")
            all_pass = False
            continue
        if result.severity != "critical":
            print(
                f"  ❌ 失败：黑名单文案 '{pattern[:30]}...' 期望 critical，实际 {result.severity}"
            )
            all_pass = False
            continue
        if not result.should_retry:
            print(f"  ❌ 失败：黑名单文案 '{pattern[:30]}...' 期望 should_retry=True")
            all_pass = False
            continue

    if all_pass:
        print(f"  ✅ 通过：所有 {len(FALLBACK_BLACKLIST)} 条黑名单文案被识别为 critical")
    return all_pass


def test_case_4_missing_conclusion_keywords() -> bool:
    """测试4：缺结论关键词 → warning（不重试）"""
    print("\n[测试4] 缺结论关键词 → warning 失败（不重试）")

    # 长度够，不含黑名单，但不含任何结论关键词
    # 注意：避开 CONCLUSION_KEYWORDS 中所有词（建议/结论/判断/观点/风险/机会/
    # 看涨/看跌/持有/买入/卖出/中性/利好/利空/增长/下滑/震荡/趋势/关注/警惕/展望）
    content = (
        "本报告展示基础数据。"
        "2026年第二季度营业收入10亿元，同比变化5%。"
        "研发投入1亿元，员工数2000人。"
        "资产负债率40%，流动比率1.5。"
        "以上为数据展示部分，无任何立场陈述。"
    )
    result = validate_analyst_report(
        content=content, agent_id="market_analyst", ticker="600519"
    )

    if result.is_valid:
        print(f"  ❌ 失败：缺结论关键词的报告不应通过")
        return False
    if result.severity != "warning":
        print(f"  ❌ 失败：期望 severity=warning，实际 {result.severity}")
        return False
    if result.should_retry:
        print(f"  ❌ 失败：warning 级别不应触发重试（should_retry 应为 False）")
        return False
    if "结论性关键词" not in result.reason:
        print(f"  ❌ 失败：期望 reason 包含 '结论性关键词'，实际 '{result.reason}'")
        return False

    print(f"  ✅ 通过：缺结论关键词被识别为 warning（不重试，只标记）")
    return True


def test_case_5_normal_report() -> bool:
    """测试5：正常报告 → 通过"""
    print("\n[测试5] 正常报告 → 通过")

    content = (
        "## 市场分析报告\n"
        "### 结论\n"
        "基于近期交易数据和基本面分析，**建议持有**该股票。\n"
        "### 风险提示\n"
        "短期可能存在震荡风险，但长期趋势向上。\n"
        "### 机会分析\n"
        "行业景气度提升，公司基本面持续改善，存在上涨机会。"
    )
    result = validate_analyst_report(
        content=content, agent_id="market_analyst", ticker="600519"
    )

    if not result.is_valid:
        print(f"  ❌ 失败：正常报告应通过，实际 is_valid=False（reason={result.reason}）")
        return False
    if result.severity != "ok":
        print(f"  ❌ 失败：期望 severity=ok，实际 {result.severity}")
        return False
    if result.should_retry:
        print(f"  ❌ 失败：通过的报告不应触发重试")
        return False

    print(f"  ✅ 通过：正常报告通过质量门禁")
    return True


# ================================================================
# L2: AnalystAgent._check_and_retry_quality 集成测试
# ================================================================


class _StubAnalystAgent:
    """最小化的 AnalystAgent 桩，仅暴露 _check_and_retry_quality 需要的接口。

    继承真实 AnalystAgent 会引入 LLM/工具依赖，这里只复用质量门禁逻辑。
    """

    def __init__(
        self,
        *,
        agent_id: str = "news_analyst",
        analyst_type: str = "news",
        retry_report: Optional[str] = None,
        retry_raises: Optional[Exception] = None,
    ):
        self.agent_id = agent_id
        self.analyst_type = analyst_type
        self._retry_report = None  # execute 中读取此属性替换报告
        self._langchain_tools = []  # 走 _llm.invoke 分支
        self._llm = MagicMock()
        self._retry_report_input = retry_report
        self._retry_raises = retry_raises

    # 复用真实实现
    def _check_and_retry_quality(self, report, messages, analysis_prompt, ticker):
        # 直接调用真实 AnalystAgent._check_and_retry_quality
        from core.agents.analyst import AnalystAgent

        return AnalystAgent._check_and_retry_quality(
            self, report=report, messages=messages,
            analysis_prompt=analysis_prompt, ticker=ticker,
        )

    def invoke_with_tools(self, messages, analysis_prompt=None):
        # 测试不应该走到这里（_langchain_tools 为空，走 _llm.invoke）
        raise RuntimeError("invoke_with_tools 不应被调用")


def _make_llm_response(content: str):
    """构造一个 langchain 风格的 LLM 响应对象。"""
    resp = MagicMock()
    resp.content = content
    return resp


async def test_case_6_critical_retry_success() -> bool:
    """测试6：critical 失败 → 重试1次成功 → 返回 None，_retry_report 被设置"""
    print("\n[测试6] critical 失败 → 重试1次成功 → 返回 None，报告被替换")

    bad_report = ""  # 空报告，触发 critical
    good_report = (
        "## 新闻分析报告\n"
        "### 结论\n"
        "近期舆情偏正面，**建议关注**。"
        "### 风险\n"
        "需警惕短期情绪过热带来的回调风险。"
    )

    agent = _StubAnalystAgent(
        agent_id="news_analyst",
        analyst_type="news",
        retry_report=good_report,
    )
    # 配置 _llm.invoke 在第二次调用时返回正常报告
    agent._llm.invoke = MagicMock(return_value=_make_llm_response(good_report))

    quality_flag = agent._check_and_retry_quality(
        report=bad_report,
        messages=[],
        analysis_prompt=None,
        ticker="600519",
    )

    if quality_flag is not None:
        print(
            f"  ❌ 失败：重试成功后期望返回 None，实际 {quality_flag}"
        )
        return False

    if not agent._retry_report:
        print(f"  ❌ 失败：重试成功后 _retry_report 应被设置")
        return False

    if agent._retry_report != good_report:
        print(
            f"  ❌ 失败：_retry_report 应等于重试后的报告，实际 {agent._retry_report[:50]}..."
        )
        return False

    print(f"  ✅ 通过：critical 重试1次成功，报告被替换，无 quality_flag")
    return True


async def test_case_7_critical_retry_still_fails() -> bool:
    """测试7：critical 失败 → 重试1次仍失败 → 返回 quality_flag（retried=True）"""
    print("\n[测试7] critical 失败 → 重试1次仍失败 → 返回 quality_flag（retried=True）")

    bad_report = ""  # 空报告
    still_bad_report = "工具执行或模型生成未完成，当前结论仍待验证"  # 命中黑名单

    agent = _StubAnalystAgent(
        agent_id="news_analyst",
        analyst_type="news",
        retry_report=still_bad_report,
    )
    agent._llm.invoke = MagicMock(
        return_value=_make_llm_response(still_bad_report)
    )

    quality_flag = agent._check_and_retry_quality(
        report=bad_report,
        messages=[],
        analysis_prompt=None,
        ticker="600519",
    )

    if quality_flag is None:
        print(f"  ❌ 失败：重试仍失败时应返回 quality_flag，实际 None")
        return False

    if quality_flag.get("retried") is not True:
        print(
            f"  ❌ 失败：期望 retried=True，实际 {quality_flag.get('retried')}"
        )
        return False

    if quality_flag.get("severity") != "critical":
        print(
            f"  ❌ 失败：期望 severity=critical，实际 {quality_flag.get('severity')}"
        )
        return False

    if quality_flag.get("agent_id") != "news_analyst":
        print(
            f"  ❌ 失败：期望 agent_id=news_analyst，实际 {quality_flag.get('agent_id')}"
        )
        return False

    print(
        f"  ✅ 通过：critical 重试仍失败，返回 quality_flag（retried=True, severity=critical）"
    )
    return True


async def test_case_8_warning_no_retry() -> bool:
    """测试8：warning 失败 → 不重试 → 返回 quality_flag（retried=False）"""
    print("\n[测试8] warning 失败 → 不重试 → 返回 quality_flag（retried=False）")

    # 长度够，不含黑名单，但缺结论关键词 → warning
    # 注意：避开 CONCLUSION_KEYWORDS 中所有词
    warning_report = (
        "本报告展示基础数据。"
        "营业收入10亿元，同比变化5%。"
        "研发投入1亿元，员工2000人。"
        "资产负债率40%，流动比率1.5。"
        "以上为数据展示部分，不含任何立场陈述。"
    )

    agent = _StubAnalystAgent(
        agent_id="fundamentals_analyst",
        analyst_type="fundamentals",
    )
    # warning 不应触发重试，所以 _llm.invoke 不应被调用
    invoke_called = False

    def _invoke_side_effect(*args, **kwargs):
        nonlocal invoke_called
        invoke_called = True
        return _make_llm_response("should not be called")

    agent._llm.invoke = MagicMock(side_effect=_invoke_side_effect)

    quality_flag = agent._check_and_retry_quality(
        report=warning_report,
        messages=[],
        analysis_prompt=None,
        ticker="600519",
    )

    if quality_flag is None:
        print(f"  ❌ 失败：warning 失败应返回 quality_flag")
        return False

    if quality_flag.get("retried") is not False:
        print(
            f"  ❌ 失败：期望 retried=False（warning 不重试），实际 {quality_flag.get('retried')}"
        )
        return False

    if quality_flag.get("severity") != "warning":
        print(
            f"  ❌ 失败：期望 severity=warning，实际 {quality_flag.get('severity')}"
        )
        return False

    if invoke_called:
        print(f"  ❌ 失败：warning 不应触发 LLM 重试调用")
        return False

    print(f"  ✅ 通过：warning 不重试，返回 quality_flag（retried=False, severity=warning）")
    return True


async def main() -> int:
    print("=" * 70)
    print("分析师报告质量门禁验证（v3.5.0 项1）")
    print("=" * 70)

    results: List[bool] = []
    # L1: 单元测试
    results.append(test_case_1_empty_report())
    results.append(test_case_2_short_report())
    results.append(test_case_3_fallback_blacklist())
    results.append(test_case_4_missing_conclusion_keywords())
    results.append(test_case_5_normal_report())
    # L2: 集成测试
    results.append(await test_case_6_critical_retry_success())
    results.append(await test_case_7_critical_retry_still_fails())
    results.append(await test_case_8_warning_no_retry())

    print("\n" + "=" * 70)
    passed = sum(1 for r in results if r)
    total = len(results)
    print(f"测试结果：{passed}/{total} 通过")
    print("=" * 70)

    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
