"""
Agent Builder 工作流条件边函数

每个 wait_* 节点的条件判断逻辑。
条件函数不调用 LLM，只做规则判断。
"""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING

from core.embedded_nanobot.workflows.agent_builder_state import AgentBuilderState

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────
# 通用确认解析
# ──────────────────────────────────────────────────────────────

def _is_confirm(text: str) -> bool:
    """用户是否表示确认/好的/可以。"""
    t = (text or "").strip().lower()
    if not t:
        return False
    confirm_words = (
        "确认", "可以", "好的", "行", "没问题", "没问题了",
        "就这样", "按这个", "没错", "对的", "正确", "ok", "yes",
        "生成", "开始生成", "直接生成", "出吧", "开始吧", "继续",
        "是的", "对", "嗯", "好", "按默认", "默认的", "默认方案",
        "同意", "赞成", "推进",
        "发布", "上线", "确认发布",
    )
    return any(t == w or t.startswith(w) for w in confirm_words)


def _is_route_choice(text: str) -> bool:
    """用户是否在选择路线/方案（如 B、按B、方案B、B方案、按B方案推进）。

    LLM 在需求探索/确认阶段可能提出 A/B 路线让用户选择，
    用户的回复（如 "B"、"按B方案推进"、"选B"）应被视为确认推进。
    """
    t = (text or "").strip().lower()
    if not t:
        return False
    normalized = re.sub(r"\s+", "", t)
    # 单字母 A/B/C/D
    if normalized in {"a", "b", "c", "d"}:
        return True
    # 字母+方案 / 方案+字母 / 按字母 / 选字母
    for letter in ("a", "b", "c", "d"):
        if (
            f"{letter}方案" in normalized
            or f"方案{letter}" in normalized
            or f"按{letter}" in normalized
            or f"选{letter}" in normalized
            or f"选择{letter}" in normalized
            or f"路线{letter}" in normalized
            or f"{letter}路线" in normalized
        ):
            return True
    return False


def _is_revise(text: str) -> bool:
    """用户是否表示修改/调整/补充。"""
    t = (text or "").strip().lower()
    if not t:
        return False
    revise_keywords = (
        "再加", "换个", "改成", "不要", "算了", "重新来", "换一个",
        "补充", "增加维度", "也加上", "再增加", "还包括", "修改",
        "调整", "加一个", "去掉", "换个方向", "不用", "不想",
        "改一下", "能不能", "能不能加", "再加一个", "还要",
    )
    return any(kw in t for kw in revise_keywords)


def _is_cancel(text: str) -> bool:
    """用户是否表示取消/重新开始。"""
    t = (text or "").strip().lower()
    if not t:
        return False
    cancel_words = ("取消", "算了不做了", "不做了", "重新开始", "全部重来")
    return any(t == w or t.startswith(w) for w in cancel_words)


# ──────────────────────────────────────────────────────────────
# 方案选择解析
# ──────────────────────────────────────────────────────────────

def _resolve_plan_selection(
    pending_options: list, text: str
) -> tuple[str, str]:
    """从用户回复中解析方案选择。

    返回 (selected_plan_id, reason)。
    """
    t = (text or "").strip().lower()
    normalized = re.sub(r"\s+", "", t)
    if not pending_options:
        return "", "no_options"

    # 按字母/数字匹配
    index_map = {"a": 1, "b": 2, "c": 3, "d": 4}
    selected_index = 0
    for letter, idx in index_map.items():
        if (
            f"方案{letter}" in normalized      # 方案b
            or f"{letter}方案" in normalized    # b方案
            or f"选{letter}" in normalized      # 选b
            or f"选择{letter}" in normalized    # 选择b
            or f"按{letter}" in normalized      # 按b
            or f"路线{letter}" in normalized    # 路线b
            or f"{letter}路线" in normalized    # b路线
            or normalized == letter             # b
        ):
            selected_index = idx
            break

    if not selected_index:
        if "第一个" in normalized or "第1个" in normalized or normalized in {"1", "方案1", "方案一"}:
            selected_index = 1
        elif "第二个" in normalized or "第2个" in normalized or normalized in {"2", "方案2", "方案二"}:
            selected_index = 2
        elif "第三个" in normalized or "第3个" in normalized or normalized in {"3", "方案3", "方案三"}:
            selected_index = 3

    if selected_index:
        for opt in pending_options:
            if int(opt.get("index") or 0) == selected_index:
                return str(opt.get("id") or "").strip(), f"matched_index_{selected_index}"

    # 推荐方案 / 默认
    recommend_keywords = ("推荐", "按这个", "可以", "确认", "好的", "行", "开始生成", "就这个")
    if any(kw in normalized for kw in recommend_keywords):
        for opt in pending_options:
            if opt.get("recommended"):
                return str(opt.get("id") or "").strip(), "recommended"
        if pending_options:
            return str(pending_options[0].get("id") or "").strip(), "default_first"

    return "", "no_match"


def _detect_intent_change(text: str) -> bool:
    """用户是否在任意阶段表示要改变需求/方向。"""
    t = (text or "").strip().lower()
    if not t:
        return False
    keywords = (
        "再加", "换个", "改成", "不要", "算了", "重新来", "换一个",
        "补充", "增加维度", "也加上", "再增加", "还包括",
    )
    return any(kw in t for kw in keywords)


# ──────────────────────────────────────────────────────────────
# 条件边路由函数
# ──────────────────────────────────────────────────────────────

def _log_route(func_name: str, state: "AgentBuilderState", result: str):
    """统一的路由日志。"""
    logger.info(
        "[Route] %s → %s (node=%s stage=%s pending=%d msg=%.60s)",
        func_name,
        result,
        state.get("current_node", "?"),
        state.get("stage", "?"),
        len(state.get("pending_options", [])),
        (state.get("user_message", "") or "")[:60],
    )


def route_start(state: "AgentBuilderState") -> str:
    """START 路由：根据 current_node 决定是新会话还是从 wait 节点恢复。

    从 wait 节点恢复时，先路由到 classify_intent 节点，
    让 LLM 判断用户意图后再路由到下一步。
    """
    node = state.get("current_node", "")

    if not node or node == "START":
        result = "requirement_intake"
        _log_route("route_start", state, result)
        return result

    # 版本冲突等待用户决策：用户回复后直接回到 build_or_ready 重建
    if state.get("build_status") == "pending_user_decision":
        logger.info(
            "[RouteStart][Debug] pending_user_decision detected | current_node=%s | decision_ctx_keys=%s | build_status=%s",
            node,
            list(state.get("decision_context", {}).keys()) if state.get("decision_context") else [],
            state.get("build_status"),
        )
        result = "build_or_ready"
        _log_route("route_start", state, result)
        return result

    # 已发布版本等待用户决策：用户回复后走 classify_intent 判断是创建新版本还是取消
    if state.get("build_status") == "pending_iteration_decision":
        logger.info(
            "[RouteStart][Debug] pending_iteration_decision detected | current_node=%s | user_message=%s",
            node,
            (state.get("user_message", "") or "")[:100],
        )
        result = "classify_intent"
        _log_route("route_start", state, result)
        return result

    # 从 wait / evaluate / error 节点恢复 → 先走 LLM 意图分类
    # build_or_ready 不在列表中：当 pending_user_decision 状态时，用户回复直接回到 build_or_ready 重新构建
    if node in (
        "wait_intake_confirmation",
        "wait_requirement_confirmation",
        "wait_plan_selection",
        "wait_test_request",
        "evaluate_or_publish",
        "wait_evaluation",
        "error_recovery",
    ):
        result = "classify_intent"
        _log_route("route_start", state, result)
        return result

    # 其他节点：直接继续
    result = node
    _log_route("route_start", state, result)
    return result


def route_after_classify(state: "AgentBuilderState") -> str:
    """LLM 意图分类后的路由。

    读取 state["user_intent"]、state["intent_confidence"]、state["current_node"]，
    决定下一步去哪个节点。

    规则：
      1. confidence < 0.7 → 回到当前 wait 节点，触发 clarification_needed
      2. intent = "new_agent" → 留在当前 wait 节点（提示用户手动创建）
      3. 其他按意图 + 节点组合路由
    """
    current_node = state.get("current_node", "")
    intent = state.get("user_intent", "explore_more")
    confidence = state.get("intent_confidence", 0.0)
    msg = state.get("user_message", "")

    # 默认清除澄清标记
    state["clarification_needed"] = False

    logger.info(
        "[Route][AfterClassify] current_node=%s intent=%s confidence=%.2f msg=%.60s",
        current_node, intent, confidence, msg,
    )

    # ── cancel 在任何阶段都结束 ──
    if intent == "cancel":
        result = "end"
        _log_route("route_after_classify", state, result)
        return result

    # ── new_agent：提示用户手动创建，留在当前 wait 节点 ──
    if intent == "new_agent":
        result = current_node if current_node.startswith("wait_") or current_node in ("evaluate_or_publish", "error_recovery") else "wait_evaluation"
        _log_route("route_after_classify", state, result)
        return result

    # ── rerun_gap：用户要求重跑当前 Agent 工坊能力缺口分析 ──
    if intent == "rerun_gap":
        state["stage"] = "capability_check"
        state["gap_report"] = {}
        state["candidate_plans"] = []
        state["pending_options"] = []
        state["selected_plan_id"] = ""
        result = "gap_analysis"
        _log_route("route_after_classify", state, result)
        return result

    # ── regenerate_plan：用户要求基于当前 gap 重新生成候选解决方案 ──
    if intent == "regenerate_plan":
        state["stage"] = "plan_selection_pending"
        state["candidate_plans"] = []
        state["pending_options"] = []
        state["selected_plan_id"] = ""
        result = "plan_generation"
        _log_route("route_after_classify", state, result)
        return result

    # ── 低置信度：LLM 搞不清楚用户意思，回到当前 wait 节点触发澄清 ──
    if confidence < 0.7:
        wait_node = current_node
        # 确保回到的是有效的 wait 节点
        if not (wait_node.startswith("wait_") or wait_node in ("evaluate_or_publish", "error_recovery")):
            wait_node = "wait_evaluation"  # 兜底
        state["clarification_needed"] = True
        logger.info(
            "[Route][LowConfidence] confidence=%.2f → stay_on=%s clarify=1",
            confidence, wait_node,
        )
        _log_route("route_after_classify", state, wait_node)
        return wait_node

    # ── wait_intake_confirmation：需求探索阶段 ──
    if current_node == "wait_intake_confirmation":
        if intent in ("confirmed", "select_option"):
            # confirmed / select_option 都视为确认推进
            result = "requirement_confirmation"
        elif intent == "revise":
            result = "requirement_intake"
        else:  # explore_more
            result = "wait_intake_confirmation"
            state["clarification_needed"] = True

    # ── wait_requirement_confirmation：需求确认阶段 ──
    elif current_node == "wait_requirement_confirmation":
        if intent in ("confirmed", "select_option"):
            result = "gap_analysis"
        elif intent == "revise":
            result = "requirement_confirmation"
        else:  # explore_more
            result = "wait_requirement_confirmation"
            state["clarification_needed"] = True

    # ── wait_plan_selection：方案选择阶段 ──
    elif current_node == "wait_plan_selection":
        if intent == "select_option" or intent == "create_skill":
            # create_skill：用户要补齐缺失skill，优先选择包含新skill开发的方案
            # 优先用 LLM 解析的 selected_index / selected_id
            selected_id = _resolve_selected_from_llm(state)
            if selected_id:
                state["selected_plan_id"] = selected_id
                result = "generate_candidate_agent"
            else:
                # LLM 没解析出来，用规则兜底
                selected_id, reason = _resolve_plan_selection(
                    state.get("pending_options", []), msg
                )
                if selected_id:
                    state["selected_plan_id"] = selected_id
                    result = "generate_candidate_agent"
                elif intent == "create_skill":
                    # 🔑 create_skill 兜底：找包含"补齐"/"开发"/"skill"关键词的方案
                    selected_id = _find_skill_creation_plan(state.get("pending_options", []))
                    if selected_id:
                        state["selected_plan_id"] = selected_id
                        result = "generate_candidate_agent"
                    else:
                        # 没有包含skill开发的方案，用推荐方案
                        state["selected_plan_id"] = state.get("recommended_plan_id", "")
                        if not state["selected_plan_id"] and state.get("pending_options"):
                            state["selected_plan_id"] = state["pending_options"][0].get("id", "")
                        result = "generate_candidate_agent" if state.get("selected_plan_id") else "wait_plan_selection"
                        if not state.get("selected_plan_id"):
                            state["clarification_needed"] = True
                else:
                    result = "wait_plan_selection"
                    state["clarification_needed"] = True
        elif intent == "confirmed":
            # 用户说"确认"/"推荐"→ 用推荐方案
            state["selected_plan_id"] = state.get("recommended_plan_id", "")
            if not state["selected_plan_id"] and state.get("pending_options"):
                state["selected_plan_id"] = state["pending_options"][0].get("id", "")
            if state["selected_plan_id"]:
                result = "generate_candidate_agent"
            else:
                result = "wait_plan_selection"
                state["clarification_needed"] = True
        elif intent == "revise":
            result = "requirement_intake"
        else:  # explore_more
            result = "wait_plan_selection"
            state["clarification_needed"] = True

    # ── wait_test_request：等待测试标的 ──
    elif current_node == "wait_test_request":
        if state.get("build_status") == "pending_iteration_decision":
            # 已发布版本决策点：用户确认创建新版本 → 回到 generate_candidate_agent
            # （节点入口会自动 iterate 创建新 session，然后用之前选好的方案继续生成）
            if intent in ("confirmed", "select_option"):
                result = "generate_candidate_agent"
            elif intent == "cancel":
                result = "end"
                state["stage"] = "cancelled"
            else:
                result = "wait_test_request"
                state["clarification_needed"] = True
        elif state.get("test_symbol"):
            result = "real_data_test"
        elif intent == "create_skill":
            # 用户要创建缺失的 skill，停在当前节点，由 node 输出提示
            result = "wait_test_request"
            state["skill_creation_requested"] = True
        elif intent == "cancel":
            result = "end"
        else:
            result = "wait_test_request"
            state["clarification_needed"] = True

    # ── 评估阶段（等待用户决策） ──
    elif current_node == "wait_evaluation":
        if intent in ("cancel",):
            result = "end"
            state["stage"] = "cancelled"
        elif intent in ("confirmed", "select_option"):
            # 用户确认发布 → 进入发布流程
            result = "evaluate_or_publish"
        elif intent == "create_skill":
            # 用户要创建缺失的 skill
            result = "wait_evaluation"
            state["skill_creation_requested"] = True
        elif intent in ("revise",):
            result = "iterate_agent_version" if state.get("version_id") else "requirement_intake"
        elif intent == "retry":
            # 用户要求重测：如果本轮已解析出测试标的，直接进入真数据测试；否则先等待标的。
            result = "real_data_test" if state.get("test_symbol") else "wait_test_request"
        else:
            result = "wait_evaluation"
            state["clarification_needed"] = True

    # ── 评估阶段（发布中） ──
    elif current_node == "evaluate_or_publish":
        if intent in ("confirmed", "select_option"):
            # 用户确认发布/继续评估 → 进入发布评估节点。
            result = "evaluate_or_publish"
        elif intent == "retry":
            # 用户想重新测试；有标的则直接测，否则先等待标的。
            result = "real_data_test" if state.get("test_symbol") else "wait_test_request"
        elif intent == "revise":
            # 用户想升级/修改已评估版本 → 创建下一轮迭代草稿
            result = "iterate_agent_version" if state.get("version_id") else "requirement_intake"
        elif intent == "cancel":
            result = "end"
        else:
            # explore_more：用户问问题，还在评估阶段
            result = "evaluate_or_publish"
            state["clarification_needed"] = True

    # ── error_recovery：错误恢复阶段 ──
    elif current_node == "error_recovery":
        if intent in ("confirmed", "retry", "select_option"):
            # 用户想重试（如"重试""再来一次""retry"）
            result = _resolve_error_retry_target(state)
        elif intent == "revise":
            # 用户要修改 → 回到需求探索
            result = "requirement_intake"
        elif intent == "cancel":
            result = "end"
        else:
            # explore_more：用户还在问问题
            result = "error_recovery"
            state["clarification_needed"] = True

    else:
        # 未知节点：安全兜底到 END，避免错误路由到 action 节点
        logger.warning(
            "[Route][AfterClassify] 非预期的 current_node=%s, intent=%s → 兜底到 end",
            current_node, intent,
        )
        result = "end"

    _log_route("route_after_classify", state, result)
    return result


def _resolve_selected_from_llm(state: "AgentBuilderState") -> str:
    """从 LLM 分类结果中解析选中的方案 ID。"""
    pending = state.get("pending_options", []) or []
    # 优先用 selected_index
    sel_idx = state.get("user_selected_index")
    if sel_idx:
        for opt in pending:
            if int(opt.get("index") or 0) == int(sel_idx):
                return str(opt.get("id") or "").strip()
    # 其次用 selected_id
    sel_id = state.get("user_selected_id", "")
    if sel_id:
        for opt in pending:
            if str(opt.get("id") or "") == str(sel_id):
                return str(opt.get("id") or "").strip()
    return ""


def _find_skill_creation_plan(options: list) -> str:
    """从方案列表中找到包含 skill/工具开发的方案 ID。"""
    skill_keywords = ["补齐", "开发", "skill", "创建.*工具", "新增.*工具", "量化评分"]
    for opt in options:
        name = str(opt.get("name", opt.get("id", ""))).lower()
        desc = str(opt.get("description", opt.get("summary", ""))).lower()
        text = f"{name} {desc}"
        for kw in skill_keywords:
            if re.search(kw, text, re.IGNORECASE):
                return str(opt.get("id") or "").strip()
    # 没找到，返回推荐方案
    for opt in options:
        if opt.get("recommended"):
            return str(opt.get("id") or "").strip()
    return ""


def route_after_intake(state: "AgentBuilderState") -> str:
    """需求探索后的路由。"""
    if _is_cancel(state.get("user_message", "")):
        result = "end"
    elif state.get("spec_id") and (
        _is_confirm(state.get("user_message", "")) or _is_route_choice(state.get("user_message", ""))
    ):
        result = "requirement_confirmation"
    else:
        result = "wait_intake_confirmation"
    _log_route("route_after_intake", state, result)
    return result


def route_after_gap_analysis(state: "AgentBuilderState") -> str:
    """gap 分析后的路由。"""
    result = "plan_generation"
    _log_route("route_after_gap_analysis", state, result)
    return result


def route_after_plan_generation(state: "AgentBuilderState") -> str:
    """方案生成后的路由。"""
    result = "wait_plan_selection"
    _log_route("route_after_plan_generation", state, result)
    return result


def route_wait_plan_selection(state: "AgentBuilderState") -> str:
    """等待用户选择方案。"""
    msg = state.get("user_message", "")
    if _is_cancel(msg):
        result = "end"
    elif _detect_intent_change(msg):
        result = "requirement_intake"
    else:
        selected_id, reason = _resolve_plan_selection(
            state.get("pending_options", []), msg
        )
        logger.info(
            "[PlanSelection][Condition] result=%s, reason=%s, pending_options=%d",
            selected_id, reason, len(state.get("pending_options", [])),
        )
        if selected_id:
            state["selected_plan_id"] = selected_id
            result = "generate_candidate_agent"
        elif _is_confirm(msg):
            state["selected_plan_id"] = state.get("recommended_plan_id", "")
            if not state["selected_plan_id"] and state.get("pending_options"):
                state["selected_plan_id"] = state["pending_options"][0].get("id", "")
            result = "generate_candidate_agent" if state["selected_plan_id"] else "wait_plan_selection"
        else:
            result = "wait_plan_selection"
    _log_route("route_wait_plan_selection", state, result)
    return result


def route_after_generate(state: "AgentBuilderState") -> str:
    """生成 Agent 后的路由。"""
    if state.get("build_status") == "pending_iteration_decision":
        # 已发布版本被 phase_guard 拦截 → 展示决策选项给用户
        result = "wait_test_request"
    elif state.get("errors"):
        result = "error_recovery"
    elif state.get("selected_plan_id") == "quick":
        result = "wait_test_request"
    elif state.get("build_status") == "built":
        result = "wait_test_request"
    elif state.get("generated_agent"):
        result = "build_or_ready"
    else:
        result = "error_recovery"
    _log_route("route_after_generate", state, result)
    return result


def route_after_build(state: "AgentBuilderState") -> str:
    """构建后的路由。"""
    build_status = state.get("build_status", "")
    if build_status in ("built", "skipped", "pending_user_decision"):
        result = "wait_test_request"
    elif build_status == "skipped_no_session":
        # 没有 workshop_session_id，无法构建版本 → 进入错误恢复
        result = "error_recovery"
    elif state.get("errors"):
        result = "error_recovery"
    else:
        result = "wait_test_request" if build_status == "built" else "error_recovery"
    _log_route("route_after_build", state, result)
    return result


def route_after_test(state: "AgentBuilderState") -> str:
    """测试后的路由：测试完成 → 等待用户决策（发布/重测/修改/取消）。

    不再自动进入发布流程，让用户有明确机会查看测试结果
    并决定下一步操作。
    """
    result = "wait_evaluation" if not state.get("errors") else "error_recovery"
    _log_route("route_after_test", state, result)
    return result


def _resolve_error_retry_target(state: "AgentBuilderState") -> str:
    """从 errors 中提取出错节点，返回重试目标。

    注意：这里对 state["errors"] 的修改不会持久化到节点
    （LangGraph 条件函数的 state 修改不持久化）。
    真正的错误清除在 classify_intent 节点内完成。
    """
    errors = state.get("errors", []) or []
    failed_node = ""
    for e in reversed(errors):
        if isinstance(e, dict):
            failed_node = str(e.get("node") or "").strip()
            if failed_node:
                break

    if failed_node:
        # 清除该节点的错误
        state["errors"] = [
            e for e in errors
            if not (isinstance(e, dict) and e.get("node") == failed_node)
        ]
        return failed_node

    return "wait_test_request"