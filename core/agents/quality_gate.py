"""
分析师报告质量门禁。

在 invoke_with_tools() 返回后、AnalystAgent.execute() 返回前做轻量校验。
失败时分层降级：第1次重试 → 第2次标记 low_quality → 第3次写告警集合。

设计原则：
- 不阻塞工作流（标记而非中断）
- 不在 invoke_with_tools() 内部检查（保持工具循环单一职责）
- 首版只做长度 + 黑名单 + 结论关键词，不做数据引用检查（避免误杀）

相关文件：
- core/agents/analyst.py：调用方
- core/agents/base.py:1022-1043：invoke_with_tools 的兜底文案（与黑名单同步）
"""

import logging
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)

# 兜底文案黑名单（与 base.py 中的失败文案保持同步）
# 命中其中任何一个，说明报告生成失败
FALLBACK_BLACKLIST = [
    "工具执行或模型生成未完成，当前结论仍待验证",
    "分析未能完成（达到最大迭代次数",
    "分析报告生成失败：LLM 持续返回工具调用而不是报告内容",
    "分析报告生成失败：LLM 持续返回工具调用",
]

# 结论性关键词（报告至少包含一个）
# 缺少这些关键词说明 LLM 可能只罗列了数据，没有给出判断
CONCLUSION_KEYWORDS = [
    "研究观察", "结论", "判断", "观点", "风险", "机会",
    "乐观", "审慎", "中性", "证据", "依据",
    "利好", "利空", "增长", "下滑", "震荡", "趋势",
    "关注", "警惕", "展望",
]

# 最小报告长度（字符）
MIN_REPORT_LENGTH = 50


@dataclass
class QualityCheckResult:
    """质量门禁校验结果。"""

    is_valid: bool
    reason: str
    severity: str = "ok"  # ok / warning / critical

    @property
    def should_retry(self) -> bool:
        """是否应该重试（critical 级别才重试，warning 只标记不重试）。"""
        return self.severity == "critical" and not self.is_valid


def validate_analyst_report(
    content: str,
    agent_id: str = "",
    ticker: str = "",
) -> QualityCheckResult:
    """分析师报告质量门禁。

    检查维度（首版轻量）：
    1. 报告长度 < 50 字符 → critical
    2. 命中兜底文案黑名单 → critical
    3. 缺少结论性关键词 → warning（不重试，只标记）

    Args:
        content: 报告内容
        agent_id: 用于日志定位
        ticker: 用于日志定位

    Returns:
        QualityCheckResult：is_valid=False 时调用方应重试或标记 low_quality
    """
    # 维度1：空报告或过短
    if not content or not content.strip():
        return QualityCheckResult(
            is_valid=False,
            reason="报告内容为空",
            severity="critical",
        )

    stripped_len = len(content.strip())
    if stripped_len < MIN_REPORT_LENGTH:
        return QualityCheckResult(
            is_valid=False,
            reason=f"报告内容过短（{stripped_len} 字符 < {MIN_REPORT_LENGTH}）",
            severity="critical",
        )

    # 维度2：命中兜底文案黑名单
    for pattern in FALLBACK_BLACKLIST:
        if pattern in content:
            return QualityCheckResult(
                is_valid=False,
                reason=f"命中兜底文案黑名单: {pattern[:50]}",
                severity="critical",
            )

    # 维度3：缺少结论性关键词（warning 级别，不重试只标记）
    if not any(kw in content for kw in CONCLUSION_KEYWORDS):
        return QualityCheckResult(
            is_valid=False,
            reason="报告缺少结论性关键词（建议/结论/判断/风险等）",
            severity="warning",
        )

    return QualityCheckResult(is_valid=True, reason="", severity="ok")
