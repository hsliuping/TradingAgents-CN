"""智能助手质量架构（A11）—— 契约型唯一质量出口 ReplyGate。

设计文档 §3.3：
- 契约校验（治 B 类裸透传）：
  * answer 型必须 llm_processed=True（路径契约禁止未经 LLM 直出）；
  * passthrough_allowed 型的 route_id 必须在登记白名单内。
- A 类溯源检查（仅对 answer 型）：收编 defense 的四道防线。

不做文本重叠率/链接数等启发式在线阻断（v1 评审废弃，见决策 D1/D5）：
阈值既误伤合理引用又放过重排透传，且豁免面会大到关卡失效。
B 类靠契约强制，文本统计信号只做离线分析。
"""

import logging
from typing import List, Optional

from . import defense
from .models import (
    EVIDENCE_HISTORY_TOOL,
    EVIDENCE_MEMORY,
    EVIDENCE_SEARCH,
    EVIDENCE_TOOL,
    ROUTE_TYPE_ANSWER,
    REGISTERED_PASSTHROUGH,
    CheckFailure,
    Evidence,
    GateResult,
    ReplyCandidate,
)

logger = logging.getLogger(__name__)

# 失败检查 → 人读说明
_CHECK_REASONS = {
    "llm_processed_contract": "answer 型路径未经 LLM 处理（契约禁止裸直出）",
    "passthrough_registration": "直出路径未在白名单登记",
    "fabricated_tool_json": "回复含编造的工具 JSON 结构化结果",
    "fabricated_tool_refs": "回复伪造了工具调用痕迹",
    "unsourced_numbers": "未调用工具却包含大量具体数字",
    "untraced_risky_numbers": "包含无法溯源到工具/搜索/历史/用户输入的高风险数字",
}

# 降级回退时每条证据摘录的最大长度
_EVIDENCE_SNIPPET_LIMIT = 800
_FALLBACK_EVIDENCE_LIMIT = 8


class ReplyGate:
    """所有路径回复的唯一质量出口（无状态，可复用单例）。"""

    def run(
        self,
        candidate: ReplyCandidate,
        user_message: str = "",
        history_tool_contents: Optional[List[str]] = None,
    ) -> GateResult:
        failures: List[CheckFailure] = []

        # ① 路径类型契约校验
        if candidate.route_type == ROUTE_TYPE_ANSWER:
            if not candidate.llm_processed:
                failures.append(self._fail("llm_processed_contract"))
        else:
            if candidate.route_id not in REGISTERED_PASSTHROUGH:
                failures.append(
                    CheckFailure(
                        check="passthrough_registration",
                        reason=f"直出路径 {candidate.route_id!r} 未在白名单登记",
                    )
                )

        # ② A 类溯源检查（仅 answer 型；契约失败时必拦，无需重复跑溯源）
        if candidate.route_type == ROUTE_TYPE_ANSWER and candidate.llm_processed:
            failures.extend(self._run_answer_checks(candidate, user_message, history_tool_contents or []))

        return GateResult(passed=not failures, failures=failures)

    @staticmethod
    def _fail(check: str) -> CheckFailure:
        return CheckFailure(check=check, reason=_CHECK_REASONS.get(check, check))

    @staticmethod
    def _run_answer_checks(
        candidate: ReplyCandidate,
        user_message: str,
        history_tool_contents: List[str],
    ) -> List[CheckFailure]:
        """把 evidence 还原成四道防线需要的入参并逐一执行。"""
        out: List[CheckFailure] = []
        reply = candidate.reply or ""
        tools_used = candidate.tools_used or []

        # tool/search 证据 → 本轮 tool_results（防线只读 content/is_error）
        tool_results = [
            {"tool": ev.source_id, "content": ev.content or ""}
            for ev in candidate.evidence
            if ev.source_type in (EVIDENCE_TOOL, EVIDENCE_SEARCH)
        ]
        # history_tool/memory 证据 + 调用方传入的多轮历史 → 可信文本
        trusted = list(history_tool_contents)
        trusted.extend(
            ev.content or ""
            for ev in candidate.evidence
            if ev.source_type in (EVIDENCE_HISTORY_TOOL, EVIDENCE_MEMORY)
        )

        if defense._has_fabricated_tool_json(reply):
            out.append(ReplyGate._fail("fabricated_tool_json"))
        if defense._has_fabricated_tool_refs(reply, tools_used):
            out.append(ReplyGate._fail("fabricated_tool_refs"))
        if defense._has_unsourced_numbers(reply, tools_used):
            out.append(ReplyGate._fail("unsourced_numbers"))
        if defense._has_untraced_risky_numbers(
            reply, tool_results, tools_used, user_message, trusted
        ):
            out.append(ReplyGate._fail("untraced_risky_numbers"))
        return out


def build_fallback_candidate(
    candidate: ReplyCandidate,
    failures: List[CheckFailure],
) -> ReplyCandidate:
    """关卡不通过的第②级降级：回退"局限说明 + 证据原文"（不裸透传、不丢功能）。

    第①级"反馈重答"由各 answer 路径在调用 LLM 时自行完成（主路径 _do_chat
    已有精细重试；快路径已内置一次总结）。走到这里说明重答后仍不过，
    转为登记的 fallback_evidence 系统直出，保证用户拿得到真实资料。
    """
    checks = "、".join(dict.fromkeys(f.check for f in failures)) or "来源校验"
    header = (
        f"抱歉，本次生成的回答未能通过数据质量校验（{checks}），"
        "为避免呈现未经核实的信息，以下仅提供系统实际获取到的原始资料，"
        "请您结合来源自行判断：\n\n"
    )

    presentable = [
        ev
        for ev in candidate.evidence
        if ev.source_type in (EVIDENCE_TOOL, EVIDENCE_SEARCH) and ev.content
    ]
    if presentable:
        blocks = []
        for ev in presentable[:_FALLBACK_EVIDENCE_LIMIT]:
            snippet = ev.content.strip()
            if len(snippet) > _EVIDENCE_SNIPPET_LIMIT:
                snippet = snippet[:_EVIDENCE_SNIPPET_LIMIT] + "……"
            blocks.append(f"【资料来源：{ev.source_id}】\n{snippet}")
        body = "\n\n".join(blocks)
    else:
        body = "（本次未获取到可引用的原始资料，请更换更具体的问法后重试。）"

    return ReplyCandidate.passthrough(
        reply=header + body,
        route_id="fallback_evidence",
        tools_used=candidate.tools_used,
        evidence=candidate.evidence,
        meta={"degraded_from": candidate.route_id, "failed_checks": [f.check for f in failures]},
    )
