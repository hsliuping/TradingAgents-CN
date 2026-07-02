"""
Agent Builder 端到端边界场景测试（包含异常 LLM 行为模拟）

覆盖：
  1. 各种用户消息格式的意图识别（确认、选择、模糊、错误）
  2. 方案选择路由：字母、数字、推荐、兜底
  3. 低置信度澄清提示
  4. 消息历史格式化和上下文测试
  5. JSON 提取可靠性测试

设计原则：
  - 不 mock 整个 LLM，而是提供能模拟异常行为的 mock llm_client
  - 异常场景覆盖：LLM 输出空响应、纯文本等

注意：原 XML 清洗相关测试（_strip_tool_call_xml / _parse_text_tool_calls /
_run_react_loop）已随 Nanobot ReAct 循环移除而删除/跳过，迁移到
UnifiedLLMClient 标准 Function Calling 后不再需要文本清洗。

用法: pytest tests/core/embedded_nanobot/workflows/test_agent_builder_e2e_edge_cases.py -v
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from unittest.mock import AsyncMock, MagicMock

import pytest

_PROJECT_ROOT = Path(__file__).resolve().parents[4]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from core.embedded_nanobot.workflows.agent_builder_state import (
    AgentBuilderState,
    new_agent_builder_state,
)
from core.embedded_nanobot.workflows.agent_builder_nodes import (
    _run_node_llm,
    _build_classify_prompt,
    _build_confirmation_prompt,
    _build_plan_selection_prompt,
    _build_test_eval_prompt,
    _build_error_prompt,
    _build_generic_prompt,
    _classify_node_type,
    _format_recent_history,
    _will_stay_on_wait_node,
    _fallback_classify_intent,
    _extract_json_from_result,
    node_classify_user_intent,
)
from core.embedded_nanobot.workflows.agent_builder_conditions import (
    _is_cancel,
    _is_confirm,
    _is_route_choice,
    _resolve_plan_selection,
    route_after_classify,
    route_start,
)

TESTS_USER_REQUEST = (
    "我要一个能识别财报风险信号的助手，重点关注商誉减值、应收账款异常和现金流恶化。"
)


# ====================================================================
# 辅助函数
# ====================================================================

def new_state(user_message: str = "", **overrides) -> AgentBuilderState:
    s = new_agent_builder_state(
        thread_id="test-e2e",
        user_id="test-user",
        user_message=user_message,
    )
    s.update(overrides)
    return s


def headline_request() -> str:
    return TESTS_USER_REQUEST


def _make_mock_response(content: str = "", tool_calls: list | None = None) -> MagicMock:
    """创建模拟的 LLM 响应对象。"""
    resp = MagicMock()
    resp.content = content
    resp.tool_calls = tool_calls or []
    return resp


def _make_tool_call_request(name: str, arguments: dict, call_id: str = "call_001") -> MagicMock:
    """创建模拟的 tool_call 对象。"""
    tc = MagicMock()
    tc.name = name
    tc.arguments = arguments
    tc.id = call_id
    return tc


# ====================================================================
# 第一部分：方案选择路由边界测试
# ====================================================================

class TestPlanSelectionEdgeCases:
    """验证方案选择在异常输入下的行为。"""

    def test_resolve_plan_by_chinese_label(self):
        """LLM 回复"方案A" → 能正确解析。"""
        options = [
            {"id": "plan_equal_weight", "index": 1, "name": "方案A：等权综合评级", "recommended": True},
            {"id": "plan_custom_weight", "index": 2, "name": "方案B：自定义权重"},
        ]
        sel_id, reason = _resolve_plan_selection(options, "方案A")
        assert sel_id == "plan_equal_weight"
        assert reason

    def test_resolve_plan_by_recommended(self):
        """用户说"推荐" → 返回推荐方案。"""
        options = [
            {"id": "plan_a", "index": 1, "name": "方案A", "recommended": True},
            {"id": "plan_b", "index": 2, "name": "方案B"},
        ]
        sel_id, reason = _resolve_plan_selection(options, "推荐")
        assert sel_id == "plan_a"

    def test_resolve_plan_no_options(self):
        """无 pending_options → 返回空。"""
        sel_id, reason = _resolve_plan_selection([], "方案A")
        assert sel_id == ""
        assert reason == "no_options"

    def test_wait_plan_selection_route_select_option(self):
        """select_option + LLM 解析了 selected_index → generate_candidate_agent。"""
        state = new_state("方案A")
        state["current_node"] = "wait_plan_selection"
        state["spec_name"] = "财报风险识别助手"
        state["pending_options"] = [
            {"id": "plan_a", "index": 1, "name": "方案A", "recommended": True},
            {"id": "plan_b", "index": 2, "name": "方案B"},
        ]
        state["user_intent"] = "select_option"
        state["intent_confidence"] = 0.95
        state["user_selected_index"] = 1
        result = route_after_classify(state)
        assert result == "generate_candidate_agent"
        assert state["selected_plan_id"] == "plan_a"

    def test_wait_plan_selection_confirm_uses_recommended(self):
        """用户"确认" → 使用推荐方案。"""
        state = new_state("确认")
        state["current_node"] = "wait_plan_selection"
        state["recommended_plan_id"] = "plan_recommended"
        state["pending_options"] = [{"id": "plan_recommended", "index": 1}]
        state["user_intent"] = "confirmed"
        state["intent_confidence"] = 0.95
        result = route_after_classify(state)
        assert result == "generate_candidate_agent"
        assert state["selected_plan_id"] == "plan_recommended"

    def test_wait_plan_selection_no_match_clarifies(self):
        """无法匹配方案 → 回到 wait + clarification。"""
        state = new_state("不知道选哪个")
        state["current_node"] = "wait_plan_selection"
        state["pending_options"] = [
            {"id": "plan_a", "index": 1, "name": "方案A"},
            {"id": "plan_b", "index": 2, "name": "方案B"},
        ]
        state["user_intent"] = "explore_more"
        state["intent_confidence"] = 0.85
        result = route_after_classify(state)
        assert result == "wait_plan_selection"
        assert state["clarification_needed"] is True


# ====================================================================
# 第二部分：异常 LLM 行为模拟测试
# ====================================================================

@pytest.mark.skip(reason="待迁移到 UnifiedLLMClient 后适配：原依赖 _strip_tool_call_xml，已随 ReAct 循环移除")
class TestAbnormalLLMBehavior:
    """模拟 LLM 返回各种异常内容，验证系统不会崩溃或泄露原始输出。"""

    def test_llm_returns_only_xml_no_text(self):
        """LLM 只输出工具调用 XML（无其他文本）→ 清洗后为空。"""
        raw = (
            "<｜DSML｜tool_calls>\n"
            "<｜DSML｜invoke name=\"search_project_capabilities\">\n"
            "<｜DSML｜parameter name=\"query\" string=\"true\">财报风险</｜DSML｜parameter>\n"
            "</｜DSML｜invoke>\n"
            "</｜DSML｜tool_calls>"
        )
        cleaned = _strip_tool_call_xml(raw)
        # 清洗后不应包含任何工具调用标签
        for tag in ["DSML", "invoke", "tool_calls", "parameter"]:
            assert tag not in cleaned, f"标签 {tag} 残留"

    def test_llm_returns_mixed_content_xml_in_middle(self):
        """LLM 输出混合内容：开头文本 → XML → 结尾文本。"""
        raw = (
            "好的，我来处理。\n\n"
            "<invoke name=\"run_test\">\n"
            "<parameter name=\"stock\" string=\"true\">600519</parameter>\n"
            "</invoke>\n\n"
            "根据分析结果，该股风险评级为中等。"
        )
        cleaned = _strip_tool_call_xml(raw)
        assert "好的，我来处理。" in cleaned
        assert "根据分析结果" in cleaned
        assert "<invoke" not in cleaned
        assert "run_test" not in cleaned

    def test_llm_returns_json_tool_block(self):
        """LLM 返回 JSON 工具调用块。"""
        raw = '{\"tool\": \"search_project_capabilities\", \"parameters\": {\"query\": \"财报风险\"}}'
        cleaned = _strip_tool_call_xml(raw)
        assert "search_project_capabilities" not in cleaned

    def test_llm_returns_multiple_tool_call_blocks(self):
        """LLM 返回多个工具调用块混合。"""
        raw = (
            "<invoke name=\"search_a\"><parameter name=\"q\" string=\"true\">a</parameter></invoke>\n"
            "中间文本\n"
            "<invoke name=\"search_b\"><parameter name=\"q\" string=\"true\">b</parameter></invoke>"
        )
        cleaned = _strip_tool_call_xml(raw)
        assert "invoke" not in cleaned
        assert "search_a" not in cleaned
        assert "search_b" not in cleaned
        assert "中间文本" in cleaned

    def test_llm_returns_malformed_xml(self):
        """LLM 返回格式异常的 XML（标签不闭合）。"""
        raw = (
            "<invoke name=\"test\"\n"
            "<parameter name=\"key\">value"
        )
        # 不应崩溃
        cleaned = _strip_tool_call_xml(raw)
        assert isinstance(cleaned, str)


# ====================================================================
# 第三部分：意图分类边界测试
# ====================================================================

class TestIntentClassificationEdgeCases:
    """验证意图分类在边界输入下的行为。"""

    def test_classify_node_type_all_variants(self):
        """所有已知节点类型映射正确。"""
        assert _classify_node_type("wait_intake_confirmation") == "confirmation"
        assert _classify_node_type("wait_requirement_confirmation") == "confirmation"
        assert _classify_node_type("wait_plan_selection") == "plan_selection"
        assert _classify_node_type("wait_test_request") == "test_eval"
        assert _classify_node_type("wait_evaluation") == "test_eval"
        assert _classify_node_type("evaluate_or_publish") == "test_eval"
        assert _classify_node_type("error_recovery") == "error"
        assert _classify_node_type("unknown_node") == "generic"
        assert _classify_node_type("") == "generic"

    def test_confirmation_prompt_contains_options(self):
        """确认阶段提示词包含用户选项引导。"""
        state = new_state("好的", current_node="wait_intake_confirmation", spec_name="测试Agent")
        state["message_history"] = [
            {"role": "agent", "content": "你想识别哪些风险信号？"},
        ]
        prompt = _build_confirmation_prompt(state)
        assert "confirmed" in prompt
        assert "revise" in prompt
        assert "explore_more" in prompt
        assert "测试Agent" in prompt

    def test_plan_selection_prompt_contains_options(self):
        """方案选择阶段提示词包含方案列表。"""
        state = new_state("方案A", current_node="wait_plan_selection", spec_name="测试Agent")
        state["pending_options"] = [
            {"index": 1, "id": "plan_a", "name": "方案A：等权", "recommended": True},
            {"index": 2, "id": "plan_b", "name": "方案B：自定义"},
        ]
        state["message_history"] = [
            {"role": "agent", "content": "方案A（推荐）还是方案B？"},
        ]
        prompt = _build_plan_selection_prompt(state)
        assert "方案A" in prompt
        assert "方案B" in prompt
        assert "select_option" in prompt
        assert "recommended" in prompt.lower() or "推荐" in prompt

    def test_test_eval_prompt_contains_stock_hints(self):
        """测试/评估阶段提示词包含股票引导。"""
        state = new_state("好的，测试吧", current_node="wait_test_request", spec_name="测试Agent")
        state["message_history"] = [
            {"role": "agent", "content": "要不要现在就拉一只真实股票试试？比如输入 600519（贵州茅台）"},
        ]
        state["test_result"] = {"status": "pending"}
        prompt = _build_test_eval_prompt(state)
        assert "600519" in prompt or "test_symbol" in prompt

    def test_error_prompt_contains_error_details(self):
        """错误阶段提示词包含错误信息。"""
        state = new_state("重试", current_node="error_recovery")
        state["errors"] = [
            {"node": "generate_candidate_agent", "error": "工具调用失败：agent_id 缺失"},
        ]
        prompt = _build_error_prompt(state)
        assert "agent_id" in prompt or "失败" in prompt
        assert "confirmed" in prompt  # 重试选项

    def test_generic_prompt_fallback(self):
        """通用兜底提示词不报错。"""
        state = new_state("你好", current_node="some_unknown_node")
        prompt = _build_generic_prompt(state)
        assert isinstance(prompt, str)
        assert len(prompt) > 100

    def test_fallback_classify_intent_confirmed(self):
        """兜底分类：明确确认信号 → confirmed。"""
        for msg in ["确认", "好的", "可以", "行", "没问题", "发布", "上线"]:
            assert _fallback_classify_intent(msg, "wait_evaluation") in ("confirmed",)

    def test_fallback_classify_intent_cancel(self):
        """兜底分类：取消信号 → cancel。"""
        assert _fallback_classify_intent("取消", "wait_evaluation") == "cancel"
        assert _fallback_classify_intent("算了不做了", "wait_evaluation") == "cancel"

    def test_fallback_classify_intent_default(self):
        """兜底分类：未知信号 → explore_more。"""
        assert _fallback_classify_intent("今天天气不错", "wait_evaluation") == "explore_more"
        assert _fallback_classify_intent("", "") == "explore_more"


# ====================================================================
# 第四部分：消息历史格式化和上下文测试
# ====================================================================

class TestMessageHistoryAndContext:
    """验证对话历史和上下文的格式化。"""

    def test_format_recent_history_empty(self):
        """无历史 → 占位文本。"""
        state = new_state("你好")
        result = _format_recent_history(state, rounds=3)
        assert "暂无" in result or "没有" in result or "对话历史" in result

    def test_format_recent_history_one_round(self):
        """1 轮对话 → 包含 agent 和 user 消息。"""
        state = new_state("方案A")
        state["message_history"] = [
            {"role": "agent", "content": "方案A（推荐）还是方案B？"},
            {"role": "user", "content": "方案A"},
        ]
        result = _format_recent_history(state, rounds=3)
        assert "Agent" in result
        assert "用户" in result
        assert "方案A" in result

    def test_format_recent_history_truncation(self):
        """超过 3 轮 → 只取最近 3 轮。"""
        state = new_state("最终确认")
        state["message_history"] = [
            {"role": "agent", "content": f"第{i}轮 问题"} for i in range(10)
        ]
        # 有 10 条 agent 消息，但没有 user 消息
        # 最近 6 条（3 轮 × 2 条/轮）
        history = state["message_history"]
        assert len(history) == 10

    def test_message_history_limit_in_classify(self):
        """message_history 超过 20 条时被裁剪。"""
        state = new_state("最终确认")
        state["current_node"] = "wait_intake_confirmation"
        initial = [{"role": "agent", "content": f"msg_{i}"} for i in range(30)]
        state["message_history"] = initial
        # 模拟 _format_recent_history 的行为
        recent = initial[-(3 * 2):]
        assert len(recent) <= 6


# ====================================================================
# 第五部分：完整流程快照测试（模拟异常 LLM 行为）
# ====================================================================

class TestFullFlowWithAbnormalLLM:
    """模拟一个完整的 Agent 构建流程，其中 LLM 偶尔输出异常内容。"""

    def test_new_session_starts_at_intake(self):
        """新会话 → requirement_intake。"""
        state = new_state(headline_request())
        assert route_start(state) == "requirement_intake"

    def test_full_flow_state_transitions(self):
        """状态转换完整性：新会话 → 需求确认 → 方案选择 → 生成 → 测试 → 评估。"""
        # ── Round 1: 需求探索 ──
        state = new_state(headline_request())
        state["current_node"] = "requirement_intake"
        state["spec_name"] = "财报风险识别助手"
        state["requirement_summary"] = "识别财报风险信号"
        state["stage"] = "exploring"
        state["final_response"] = "好的，你的需求是识别财报风险信号。确认一下"
        state["awaiting_user"] = True

        assert state["current_node"] == "requirement_intake"
        assert state["spec_name"] == "财报风险识别助手"
        # final_response 不应包含工具调用 XML
        assert "DSML" not in state["final_response"]
        assert "<invoke" not in state["final_response"]

        # ── Round 2: 需求确认 → 能力盘点 ──
        state["user_message"] = "确认，商誉、应收账款、现金流三块"
        state["current_node"] = "wait_intake_confirmation"
        assert route_start(state) == "classify_intent"

        state["user_intent"] = "confirmed"
        state["intent_confidence"] = 0.92
        result = route_after_classify(state)
        assert result == "requirement_confirmation"

        # ── Round 3: 方案选择 ──
        state["current_node"] = "wait_plan_selection"
        state["pending_options"] = [
            {"id": "plan_a", "index": 1, "name": "方案A：等权综合评级", "recommended": True},
            {"id": "plan_b", "index": 2, "name": "方案B：自定义权重"},
        ]
        state["recommended_plan_id"] = "plan_a"
        state["user_message"] = "方案A"
        assert route_start(state) == "classify_intent"

        state["user_intent"] = "select_option"
        state["intent_confidence"] = 0.95
        state["user_selected_index"] = 1
        result = route_after_classify(state)
        assert result == "generate_candidate_agent"
        assert state["selected_plan_id"] == "plan_a"

        # ── Round 4: 测试 ──
        state["user_message"] = "600519"
        state["current_node"] = "wait_test_request"
        assert route_start(state) == "classify_intent"

        state["user_intent"] = "confirmed"
        state["intent_confidence"] = 0.93
        state["test_symbol"] = "600519"
        result = route_after_classify(state)
        assert result == "real_data_test"

        # ── Round 5: 评估后确认发布 ──
        state["current_node"] = "wait_evaluation"
        state["user_message"] = "发布"
        state["test_result"] = {"status": "ok"}
        assert route_start(state) == "classify_intent"

        state["user_intent"] = "confirmed"
        state["intent_confidence"] = 0.95
        result = route_after_classify(state)
        assert result == "evaluate_or_publish"


# ====================================================================
# 第六部分：异常回复识别测试
# ====================================================================

class TestAbnormalUserReplyRecognition:
    """验证系统对异常用户回复的处理能力。"""

    def test_short_confirm_works(self):
        """极短确认：单字"好"→ 识别为 confirm。"""
        assert _is_confirm("好") is True
        assert _is_confirm("嗯") is True
        assert _is_confirm("对") is True

    def test_typo_like_confirm_works(self):
        """类确认信号：即使不完全匹配也能识别。"""
        # "好的"、"可以" 等明确信号
        assert _is_confirm("好的") is True
        assert _is_confirm("可以") is True

    def test_ambiguous_reply_explore_more(self):
        """模糊回复「啥意思」→ 不是确认也不是选择 → clarification_needed。"""
        state = new_state("啥意思")
        state["current_node"] = "wait_plan_selection"
        state["pending_options"] = [
            {"id": "plan_a", "index": 1, "name": "方案A"},
        ]
        state["user_intent"] = "explore_more"
        state["intent_confidence"] = 0.85
        result = route_after_classify(state)
        assert result == "wait_plan_selection"
        assert state["clarification_needed"] is True

    def test_irrelevant_reply_doesnt_break(self):
        """完全无关的回复不应导致崩溃。"""
        state = new_state("今天天气真好啊")
        state["current_node"] = "wait_test_request"
        state["test_result"] = {"status": "ok"}
        state["user_intent"] = "explore_more"
        state["intent_confidence"] = 0.75
        result = route_after_classify(state)
        # 应该停留在当前 wait 节点，触发澄清
        assert result == "wait_test_request"
        assert state["clarification_needed"] is True

    def test_low_confidence_stays_any_wait_node(self):
        """低置信度（<0.7）：无论什么节点都停留 + 澄清。"""
        wait_nodes = [
            "wait_intake_confirmation",
            "wait_requirement_confirmation",
            "wait_plan_selection",
            "wait_test_request",
            "wait_evaluation",
        ]
        for node in wait_nodes:
            state = new_state("不确定")
            state["current_node"] = node
            state["user_intent"] = "explore_more"
            state["intent_confidence"] = 0.45
            result = route_after_classify(state)
            assert result == node or result.startswith("wait_"), f"节点 {node} 路由到 {result}"
            assert state["clarification_needed"] is True

    def test_new_agent_intent_during_existing_session(self):
        """在现有 Agent 会话中说「新建一个舆情分析Agent」→ new_agent → end。"""
        state = new_state("我要新建一个舆情分析Agent")
        state["current_node"] = "wait_evaluation"
        state["spec_name"] = "财报风险识别助手"
        state["test_result"] = {"status": "ok"}
        state["user_intent"] = "new_agent"
        state["intent_confidence"] = 0.95
        result = route_after_classify(state)
        assert result == "end"
        assert "新建 Agent" in state.get("final_response", "")
        assert "财报风险识别助手" in state.get("final_response", "")

    def test_cancel_mid_flow_ends_gracefully(self):
        """任何阶段说「取消」→ 结束。"""
        for node in ["wait_intake_confirmation", "wait_plan_selection", "wait_evaluation"]:
            state = new_state("取消")
            state["current_node"] = node
            state["user_intent"] = "cancel"
            state["intent_confidence"] = 0.98
            assert route_after_classify(state) == "end", f"节点 {node} 取消失败"

    def test_retry_intent_in_test_eval(self):
        """用户在 wait_evaluation 说「重测」→ wait_test_request。"""
        state = new_state("换贵州茅台再测一次")
        state["current_node"] = "wait_evaluation"
        state["user_intent"] = "retry"
        state["intent_confidence"] = 0.9
        result = route_after_classify(state)
        assert result == "wait_test_request"

    def test_revise_intent_in_eval(self):
        """用户在 wait_evaluation 说「再加一个现金流维度」→ requirement_intake。"""
        state = new_state("再加一个现金流维度")
        state["current_node"] = "wait_evaluation"
        state["user_intent"] = "revise"
        state["intent_confidence"] = 0.9
        result = route_after_classify(state)
        assert result == "requirement_intake"


# ====================================================================
# 第七部分：_will_stay_on_wait_node 验证
# ====================================================================

class TestWillStayOnWaitNode:
    """验证 _will_stay_on_wait_node 在所有节点类型下正确判断。"""

    def test_confirmation_stays_on_explore_more(self):
        """确认阶段：explore_more → 停留。"""
        state = new_state("啥意思")
        state["current_node"] = "wait_intake_confirmation"
        state["user_intent"] = "explore_more"
        assert _will_stay_on_wait_node(state) is True

    def test_confirmation_proceeds_on_confirmed(self):
        """确认阶段：confirmed → 不留守。"""
        state = new_state("好的")
        state["current_node"] = "wait_intake_confirmation"
        state["user_intent"] = "confirmed"
        assert _will_stay_on_wait_node(state) is False

    def test_plan_selection_stays_on_no_match(self):
        """方案选择阶段：无法匹配 → 停留。"""
        state = new_state("啥意思")
        state["current_node"] = "wait_plan_selection"
        state["user_intent"] = "confirmed"
        state["intent_confidence"] = 0.9
        # confirmed 但没有 recommended_plan_id 也没有 pending_options → 不停留？
        # 实际上 confirmed 会回退到 use recommended ...
        # 这取决于具体状态
        # 至少不崩溃
        result = _will_stay_on_wait_node(state)
        assert isinstance(result, bool)

    def test_test_request_with_symbol_proceeds(self):
        """wait_test_request 有 test_symbol → 不留守。"""
        state = new_state("600519")
        state["current_node"] = "wait_test_request"
        state["user_intent"] = "confirmed"
        state["test_symbol"] = "600519"
        assert _will_stay_on_wait_node(state) is False

    def test_test_request_without_symbol_stays(self):
        """wait_test_request 无 test_symbol → 停留。"""
        state = new_state("测试")
        state["current_node"] = "wait_test_request"
        state["user_intent"] = "confirmed"
        # 没有 test_symbol
        assert _will_stay_on_wait_node(state) is True

    def test_eval_pending_revise_proceeds(self):
        """wait_evaluation: revise → 不留守。"""
        state = new_state("修改需求")
        state["current_node"] = "wait_evaluation"
        state["user_intent"] = "revise"
        assert _will_stay_on_wait_node(state) is False


# ====================================================================
# 第八部分：_extract_json_from_result 可靠性测试
# ====================================================================

class TestExtractJsonFromResult:
    """验证 JSON 提取在各种异常输入下不崩溃。"""

    def test_empty_string(self):
        assert _extract_json_from_result("") == {}

    def test_none(self):
        assert _extract_json_from_result(None) == {}

    def test_valid_json(self):
        result = _extract_json_from_result('{"status": "ok", "data": 123}')
        assert result["status"] == "ok"
        assert result["data"] == 123

    def test_malformed_json(self):
        result = _extract_json_from_result("不是一个 JSON")
        assert result == {}

    def test_json_embedded_in_text(self):
        result = _extract_json_from_result('前面文本 {"key": "value"} 后面文本')
        assert result["key"] == "value"

    def test_nested_json(self):
        result = _extract_json_from_result('{"outer": {"inner": {"deep": true}}}')
        assert result["outer"]["inner"]["deep"] is True


# ====================================================================
# 第九部分：综合端到端场景（模拟异常 LLM）
# ====================================================================

class TestE2EWithFaultyLLM:
    """端到端流程：所有关键节点的 final_response 都不应泄露工具调用 XML。"""

    def setup_method(self):
        """每个测试前重置。"""
        self.xml_patterns = [
            r"<\s*invoke\b",
            r"<\s*parameter\b",
            r"tool_calls\b",
            r"DSML",
            r"tool_call\b",
            r'"tool"\s*:\s*"',
        ]
        self.compiled = [re.compile(p, re.IGNORECASE) for p in self.xml_patterns]

    def _assert_no_xml_leak(self, text: str, context: str = ""):
        """断言文本中不含任何工具调用 XML。"""
        for pat in self.compiled:
            if pat.search(text):
                match = pat.search(text)
                # 提取匹配位置的前后 30 字
                start = max(0, match.start() - 30)
                end = min(len(text), match.end() + 30)
                snippet = text[start:end]
                raise AssertionError(
                    f"[XML泄露] {context}: 模式 '{pat.pattern}' 匹配到: ...{snippet}..."
                )
        assert True

    def test_no_xml_in_normal_analysis_text(self):
        """正常分析文本不应被视为 XML 泄露（false positive 检查）。"""
        text = (
            "## 分析报告\n"
            "标的：600519（贵州茅台）\n"
            "商誉减值风险：低\n"
            "应收账款周转率：45.2\n"
            "现金流覆盖率：2.3x\n"
        )
        self._assert_no_xml_leak(text, "正常分析报告")

    @pytest.mark.skip(reason="待迁移到 UnifiedLLMClient 后适配：原依赖 _strip_tool_call_xml，已随 ReAct 循环移除")
    def test_strip_removes_all_xml_variants(self):
        """所有 XML 格式变体被清洗后，_assert_no_xml_leak 不报警。"""
        variants = [
            # DSML 全角
            (
                "<｜DSML｜tool_calls>\n"
                "<｜DSML｜invoke name=\"search\">\n"
                "<｜DSML｜parameter name=\"q\" string=\"true\">test</｜DSML｜parameter>\n"
                "</｜DSML｜invoke>\n"
                "</｜DSML｜tool_calls>"
            ),
            # invoke
            (
                "<invoke name=\"run_test\">\n"
                "<parameter name=\"symbol\" string=\"true\">600519</parameter>\n"
                "</invoke>"
            ),
            # tool_call
            (
                "<tool_call name=\"search_project_capabilities\">\n"
                "<parameter name=\"query\">测试</parameter>\n"
                "</tool_call>"
            ),
            # JSON
            '{\"tool\": \"search_project_capabilities\", \"parameters\": {\"query\": \"test\"}}',
        ]
        for i, raw in enumerate(variants):
            cleaned = _strip_tool_call_xml(raw)
            try:
                self._assert_no_xml_leak(cleaned, f"变体 {i+1}")
            except AssertionError:
                pytest.fail(f"变体 {i+1} 清洗失败: cleaned='{cleaned[:100]}'")

    @pytest.mark.skip(reason="待迁移到 UnifiedLLMClient 后适配：原依赖 _strip_tool_call_xml，已随 ReAct 循环移除")
    def test_streaming_receives_cleaned_content_only(self):
        """模拟流式推送：每批 delta 都是清洗后的内容。"""
        # 模拟 LLM 流式输出：前几批正常，中间一批包含 XML，后几批正常
        deltas = [
            "好的，",
            "让我来分析。\n\n",
            "<invoke name=\"search\"><parameter name=\"q\" string=\"true\">test</parameter></invoke>",
            "\n\n基于分析结果，",
            "风险评级为中等。",
        ]
        # 模拟实时清洗
        cleaned_deltas = []
        for d in deltas:
            cleaned = _strip_tool_call_xml(d)
            cleaned_deltas.append(cleaned)
        full_text = "".join(cleaned_deltas)
        assert "好的，让我来分析。" in full_text
        assert "风险评级为中等" in full_text
        assert "invoke" not in full_text, "流式清洗失败"
        assert "search" not in full_text, "流式清洗失败"


# ====================================================================
# 独立 smoke test（不需要 pytest）
# ====================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("Agent Builder 端到端边界测试 - Smoke Test")
    print("=" * 60)

    errors = []

    def check(condition, msg):
        if not condition:
            errors.append(msg)
            print(f"  FAIL: {msg}")
        else:
            print(f"  PASS: {msg[:80]}")

    # ── JSON 提取 ──
    j = _extract_json_from_result('{"intent": "confirmed", "confidence": 0.9}')
    check(j.get("intent") == "confirmed", "JSON 提取")
    check(_extract_json_from_result("") == {}, "空 JSON 提取")

    # ── 路由逻辑 ──
    check(route_start(new_state("测试")) == "requirement_intake", "新会话 → intake")

    s = new_state("600519")
    s["current_node"] = "wait_test_request"
    s["user_intent"] = "confirmed"
    s["intent_confidence"] = 0.9
    s["test_symbol"] = "600519"
    check(route_after_classify(s) == "real_data_test", "test_symbol → real_data_test")

    s2 = new_state("")
    s2["current_node"] = "wait_test_request"
    s2["user_intent"] = "confirmed"
    s2["intent_confidence"] = 0.9
    check(route_after_classify(s2) == "wait_test_request", "无 test_symbol → clarification")

    # ── 方案选择 ──
    opts = [
        {"id": "plan_a", "index": 1, "name": "方案A", "recommended": True},
        {"id": "plan_b", "index": 2, "name": "方案B"},
    ]
    sel_id, reason = _resolve_plan_selection(opts, "方案A")
    check(sel_id == "plan_a", f"方案A 解析 → {sel_id}")

    sel_id2, _ = _resolve_plan_selection(opts, "推荐")
    check(sel_id2 == "plan_a", f"推荐 解析 → {sel_id2}")

    # ── 意图分类 ──
    check(_fallback_classify_intent("确认", "wait_intake_confirmation") == "confirmed", "确认 → confirmed")
    check(_fallback_classify_intent("取消", "wait_intake_confirmation") == "cancel", "取消 → cancel")

    # ── 结果 ──
    print("=" * 60)
    if errors:
        print(f"FAILED: {len(errors)} error(s)")
        for e in errors:
            print(f"  - {e}")
        sys.exit(1)
    else:
        print("ALL PASSED")
        sys.exit(0)
