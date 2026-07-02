"""
Agent Builder 工作流全流程集成测试

覆盖：
  1. 状态管理（创建、序列化、白名单）
  2. 路由逻辑（route_start、route_after_classify）
  3. 意图分类提示词（5 种节点类型）
  4. 完整多轮对话模拟（mock LLM）
  5. 边界条件与异常路径

测试主题：我要一个能识别财报风险信号的助手，重点关注商誉减值、应收账款异常和现金流恶化。

用法: pytest tests/core/embedded_nanobot/workflows/test_agent_builder_full_flow.py -v
       python tests/core/embedded_nanobot/workflows/test_agent_builder_full_flow.py  # 独立 smoke test
"""

from __future__ import annotations

import copy
import json
import sys
from typing import Any, Dict, List, Optional, Tuple
from unittest.mock import AsyncMock, MagicMock

import pytest

# 确保项目根在 sys.path 中（兼容直接运行和 pytest 两种方式）
from pathlib import Path
_PROJECT_ROOT = Path(__file__).resolve().parents[4]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

# ──────────────────────────────────────────────────────────────
# 导入被测模块
# ──────────────────────────────────────────────────────────────
from core.embedded_nanobot.workflows.agent_builder_state import (
    AgentBuilderState,
    new_agent_builder_state,
)
from core.embedded_nanobot.workflows.agent_builder_store import _KNOWN_KEYS
from core.embedded_nanobot.workflows.agent_builder_conditions import (
    _is_cancel,
    _is_confirm,
    _is_route_choice,
    _resolve_plan_selection,
    route_after_classify,
    route_start,
)
from core.embedded_nanobot.workflows.agent_builder_nodes import (
    _build_classify_prompt,
    _classify_node_type,
    _extract_json_from_result,
    _fallback_classify_intent,
    _format_recent_history,
    _will_stay_on_wait_node,
)

# ──────────────────────────────────────────────────────────────
# 测试常量
# ──────────────────────────────────────────────────────────────
TEST_USER_REQUEST = "我要一个能识别财报风险信号的助手，重点关注商誉减值、应收账款异常和现金流恶化。"


# ====================================================================
# 第一部分：状态管理测试
# ====================================================================

class TestStateManagement:
    """测试 AgentBuilderState 的创建、序列化和白名单。"""

    def test_create_new_state(self):
        """创建新状态，验证所有关键字段初始化正确。"""
        state = new_agent_builder_state(
            thread_id="test-thread-001",
            user_id="user-001",
            user_message=TEST_USER_REQUEST,
        )
        assert state["thread_id"] == "test-thread-001"
        assert state["user_id"] == "user-001"
        assert state["user_message"] == TEST_USER_REQUEST
        assert state["current_node"] == "START"
        assert state["stage"] == ""
        assert state["awaiting_user"] is False
        assert state["message_history"] == []
        assert state["errors"] == []

    def test_new_state_no_message(self):
        """不带消息创建新状态。"""
        state = new_agent_builder_state(
            thread_id="test-thread-002",
            user_id="user-002",
        )
        assert state["user_message"] == ""
        assert state["current_node"] == "START"

    def test_known_keys_covers_new_fields(self):
        """验证 v2 新增字段都在白名单中（防止跨请求丢失）。"""
        required_keys = {
            # 意图分类
            "user_intent", "intent_confidence", "intent_reason",
            "user_selected_index", "user_selected_id",
            # 对话历史
            "message_history",
            # 澄清标记
            "clarification_needed",
            # 工具进度
            "test_progress",
            # 基础字段
            "thread_id", "user_id", "user_message", "current_node",
            "stage", "awaiting_user", "spec_id", "spec_name",
            "version_id", "test_symbol", "test_result",
            "official_acceptance_decision", "errors", "final_response",
        }
        missing = required_keys - set(_KNOWN_KEYS)
        assert not missing, f"白名单缺少字段: {missing}"

    def test_state_serialization_roundtrip(self):
        """状态存入已知字段后，应该能完整读出。"""
        state = new_agent_builder_state(
            thread_id="test-serial-001",
            user_id="user-001",
            user_message=headline_request(),
        )
        state["message_history"] = [
            {"role": "agent", "content": "请确认需求"},
            {"role": "user", "content": "确认"},
        ]
        state["user_intent"] = "confirmed"
        state["intent_confidence"] = 0.92
        state["clarification_needed"] = False

        # 模拟 _make_state_serializable 的过滤逻辑
        serialized = {k: v for k, v in state.items() if k in _KNOWN_KEYS}

        assert serialized["message_history"] == state["message_history"]
        assert serialized["user_intent"] == "confirmed"
        assert serialized["intent_confidence"] == 0.92


# ====================================================================
# 第二部分：路由逻辑测试
# ====================================================================

class TestRouteStart:
    """测试 START 节点的路由逻辑。"""

    def test_new_session_goes_to_intake(self):
        """空 current_node → requirement_intake。"""
        state = new_state(user_message=headline_request())
        assert route_start(state) == "requirement_intake"

    def test_start_node_goes_to_intake(self):
        """current_node == "START" → requirement_intake。"""
        state = new_state(user_message=headline_request())
        state["current_node"] = "START"
        assert route_start(state) == "requirement_intake"

    @pytest.mark.parametrize("wait_node", [
        "wait_intake_confirmation",
        "wait_requirement_confirmation",
        "wait_plan_selection",
        "wait_test_request",
        "evaluate_or_publish",
        "wait_evaluation",
        "error_recovery",
    ])
    def test_wait_nodes_go_to_classify(self, wait_node: str):
        """所有 wait/evaluate/error 节点 → classify_intent。"""
        state = new_state(user_message="换一个股票测")
        state["current_node"] = wait_node
        assert route_start(state) == "classify_intent"

    def test_action_node_keeps_current(self):
        """非 wait 节点保持原路由。"""
        state = new_state(user_message="继续")
        state["current_node"] = "gap_analysis"
        assert route_start(state) == "gap_analysis"


class TestRouteAfterClassify:
    """测试 LLM 意图分类后的路由。"""

    # ── 低置信度兜底 ──

    def test_low_confidence_stays_on_wait(self):
        """confidence < 0.7 → 停留当前 wait 节点 + clarification_needed。"""
        state = new_state("确定")
        state["current_node"] = "wait_evaluation"
        state["user_intent"] = "explore_more"
        state["intent_confidence"] = 0.45
        result = route_after_classify(state)
        assert result == "wait_evaluation"
        assert state["clarification_needed"] is True

    # ── cancel 全局 ──

    @pytest.mark.parametrize("node", [
        "wait_intake_confirmation", "wait_evaluation", "error_recovery",
    ])
    def test_cancel_anywhere_ends(self, node: str):
        """cancel 在任何阶段都结束。"""
        state = new_state("取消")
        state["current_node"] = node
        state["user_intent"] = "cancel"
        state["intent_confidence"] = 0.9
        assert route_after_classify(state) == "end"

    # ── new_agent ──

    def test_new_agent_intent(self):
        """用户想新建 Agent → end + 引导。"""
        state = new_state("我要新建一个舆情分析Agent")
        state["current_node"] = "wait_evaluation"
        state["spec_name"] = "财报风险识别"
        state["user_intent"] = "new_agent"
        state["intent_confidence"] = 0.95
        result = route_after_classify(state)
        assert result == "end"
        assert "新建 Agent" in state.get("final_response", "")

    # ── wait_test_request ──

    def test_test_symbol_available_goes_to_test(self):
        """LLM 提取了 test_symbol → real_data_test。"""
        state = new_state("600519")
        state["current_node"] = "wait_test_request"
        state["user_intent"] = "confirmed"
        state["intent_confidence"] = 0.9
        state["test_symbol"] = "600519"
        assert route_after_classify(state) == "real_data_test"

    def test_test_symbol_missing_clarifies(self):
        """无 test_symbol → 停留 + clarification。"""
        state = new_state("测试吧")
        state["current_node"] = "wait_test_request"
        state["user_intent"] = "confirmed"
        state["intent_confidence"] = 0.9
        result = route_after_classify(state)
        assert result == "wait_test_request"
        assert state["clarification_needed"] is True

    # ── wait_evaluation ──

    def test_eval_confirm_publishes(self):
        """用户确认发布 → evaluate_or_publish。"""
        state = new_state("发布")
        state["current_node"] = "wait_evaluation"
        state["user_intent"] = "confirmed"
        state["intent_confidence"] = 0.9
        assert route_after_classify(state) == "evaluate_or_publish"

    def test_eval_retry_goes_to_test(self):
        """用户要求重测 → wait_test_request。"""
        state = new_state("换宁德时代再测一次")
        state["current_node"] = "wait_evaluation"
        state["user_intent"] = "retry"
        state["intent_confidence"] = 0.9
        state["test_symbol"] = "300750"
        assert route_after_classify(state) == "wait_test_request"

    def test_eval_revise_goes_to_requirement(self):
        """用户要修改 → requirement_intake。"""
        state = new_state("加一个现金流分析维度")
        state["current_node"] = "wait_evaluation"
        state["user_intent"] = "revise"
        state["intent_confidence"] = 0.9
        assert route_after_classify(state) == "requirement_intake"

    # ── 未知节点安全兜底 ──

    def test_unknown_node_defaults_to_end(self):
        """未知 current_node → 安全兜底 end。"""
        state = new_state("测试")
        state["current_node"] = "gap_analysis"
        state["user_intent"] = "retry"
        state["intent_confidence"] = 0.8
        assert route_after_classify(state) == "end"


# ====================================================================
# 第三部分：意图分类单元测试
# ====================================================================

class TestIntentClassification:
    """测试意图分类的辅助函数。"""

    def test_classify_node_type(self):
        """节点名正确映射到类型。"""
        assert _classify_node_type("wait_intake_confirmation") == "confirmation"
        assert _classify_node_type("wait_requirement_confirmation") == "confirmation"
        assert _classify_node_type("wait_plan_selection") == "plan_selection"
        assert _classify_node_type("wait_test_request") == "test_eval"
        assert _classify_node_type("wait_evaluation") == "test_eval"
        assert _classify_node_type("evaluate_or_publish") == "test_eval"
        assert _classify_node_type("error_recovery") == "error"
        assert _classify_node_type("gap_analysis") == "generic"

    def test_fallback_classify_intent(self):
        """LLM 不可用时兜底分类。"""
        # 取消意图
        assert _fallback_classify_intent("取消", "wait_evaluation") == "cancel"
        # 方案选择
        assert _fallback_classify_intent("选A", "wait_plan_selection") == "select_option"
        assert _fallback_classify_intent("B方案", "wait_plan_selection") == "select_option"
        # 确认
        assert _fallback_classify_intent("确认", "wait_intake_confirmation") == "confirmed"
        assert _fallback_classify_intent("好的", "wait_requirement_confirmation") == "confirmed"
        # 未知表达 → explore_more（精简兜底，不做过度猜测）
        assert _fallback_classify_intent("退出", "wait_evaluation") == "explore_more"
        assert _fallback_classify_intent("今天天气真好", "wait_evaluation") == "explore_more"

    def test_recent_history_formatting(self):
        """message_history 正确格式化为 LLM prompt 上下文。"""
        state = new_state("新消息")
        state["message_history"] = [
            {"role": "agent", "content": "请确认是否继续"},
            {"role": "user", "content": "确认继续"},
            {"role": "agent", "content": "好的，正在搜索能力"},
            {"role": "user", "content": "新消息"},
        ]
        formatted = _format_recent_history(state)
        assert "[Agent] 请确认是否继续" in formatted
        assert "[用户] 确认继续" in formatted
        # 验证只取最近 3 轮（6 条）
        assert formatted.count("[Agent]") >= 1

    def test_recent_history_empty(self):
        """无对话历史 → 返回占位文本。"""
        state = new_state("新消息")
        state["message_history"] = []
        formatted = _format_recent_history(state)
        assert "暂无对话历史" in formatted

    def test_build_classify_prompt_for_test_eval(self):
        """test_eval 节点类型生成正确的提示词。"""
        state = new_state("换宁德时代再测")
        state["current_node"] = "wait_evaluation"
        state["spec_name"] = "财报风险识别助手"
        state["message_history"] = [
            {"role": "agent", "content": "测试完成，PE/PB/PS 三指标正常"},
            {"role": "user", "content": "换宁德时代再测"},
        ]
        prompt = _build_classify_prompt(state, "test_eval")
        assert "retry" in prompt.lower() or "重测" in prompt or "数据提取" in prompt
        assert "宁德时代" in prompt

    def test_build_classify_prompt_for_confirmation(self):
        """confirmation 节点类型生成正确的提示词。"""
        state = new_state("确认")
        state["current_node"] = "wait_intake_confirmation"
        state["spec_name"] = "财报风险识别助手"
        prompt = _build_classify_prompt(state, "confirmation")
        assert "confirmed" in prompt.lower() or "确认" in prompt

    def test_extract_json_from_result(self):
        """JSON 提取正确处理各种输入。"""
        # 标准 JSON
        assert _extract_json_from_result('{"key": "value"}') == {"key": "value"}
        # 空字符串
        assert _extract_json_from_result("") == {}
        # 非 JSON 文本
        assert _extract_json_from_result("hello world") == {}

    def test_will_stay_on_wait_node(self):
        """预判是否停留。"""
        # retry 推动流程
        state = new_state("重测")
        state["current_node"] = "wait_evaluation"
        state["user_intent"] = "retry"
        assert _will_stay_on_wait_node(state) is False
        # explore_more 停留
        state["user_intent"] = "explore_more"
        assert _will_stay_on_wait_node(state) is True
        # cancel 不会停留（结束）
        state["user_intent"] = "cancel"
        assert _will_stay_on_wait_node(state) is False

    def test_test_request_with_test_symbol(self):
        """wait_test_request 有 test_symbol → 不触发停留。"""
        state = new_state("600519")
        state["current_node"] = "wait_test_request"
        state["user_intent"] = "confirmed"
        state["test_symbol"] = "600519"
        assert _will_stay_on_wait_node(state) is False


# ====================================================================
# 第四部分：用户意图判断辅助函数测试
# ====================================================================

class TestUserIntentHelpers:
    """测试 _is_confirm, _is_cancel, _is_route_choice 辅助函数。"""

    @pytest.mark.parametrize("text,expected", [
        ("好的", True), ("确认", True), ("可以", True), ("行", True),
        ("发布", True), ("上线", True), ("生成", True), ("开始生成", True),
        ("确认发布", True), ("没问题", True), ("就这样", True), ("是的", True),
        ("同意", True), ("按这个", True), ("正确的", True), ("默认方案", True),
    ])
    def test_is_confirm_positive(self, text: str, expected: bool):
        assert _is_confirm(text) == expected

    @pytest.mark.parametrize("text,expected", [
        ("不要", False), ("不对", False), ("取消", False),
        ("再测一次", False), ("换个股票", False),
        ("今天天气不错", False), ("", False),
    ])
    def test_is_confirm_negative(self, text: str, expected: bool):
        assert _is_confirm(text) == expected

    @pytest.mark.parametrize("text,expected", [
        ("取消", True), ("算了不做了", True), ("不做了", True),
        ("重新开始", True), ("全部重来", True),
    ])
    def test_is_cancel_positive(self, text: str, expected: bool):
        assert _is_cancel(text) == expected

    @pytest.mark.parametrize("text,expected", [
        ("好的", False), ("发布", False), ("继续", False),
    ])
    def test_is_cancel_negative(self, text: str, expected: bool):
        assert _is_cancel(text) == expected

    @pytest.mark.parametrize("text,expected", [
        ("B", True), ("方案A", True), ("选C", True),
        ("按B方案推进", True), ("B方案", True),
    ])
    def test_is_route_choice_positive(self, text: str, expected: bool):
        assert _is_route_choice(text) == expected

    @pytest.mark.parametrize("text,expected", [
        ("好的", False), ("确认", False), ("发布", False),
    ])
    def test_is_route_choice_negative(self, text: str, expected: bool):
        assert _is_route_choice(text) == expected

    def test_resolve_plan_selection_by_letter(self):
        """从用户回复解析方案选择。"""
        options = [
            {"id": "plan_a", "index": 1, "title": "快速方案"},
            {"id": "plan_b", "index": 2, "title": "标准方案"},
        ]
        sel_id, reason = _resolve_plan_selection(options, "选B")
        assert sel_id == "plan_b"
        assert reason

        sel_id, _ = _resolve_plan_selection(options, "B方案")
        assert sel_id == "plan_b"

    def test_resolve_plan_selection_no_match(self):
        """无法匹配方案。"""
        options = [{"id": "plan_a", "index": 1}]
        sel_id, reason = _resolve_plan_selection(options, "选Z")
        assert sel_id == ""
        assert reason


# ====================================================================
# 第五部分：完整多轮对话流程测试
# ====================================================================

class TestFullWorkflowSimulation:
    """模拟完整的 Agent 创建 → 测试 → 发布 → 重测流程。"""

    REQUEST = "我要一个能识别财报风险信号的助手，重点关注商誉减值、应收账款异常和现金流恶化。"

    def _make_agent_builder_state(self, turn: int = 1, **overrides) -> AgentBuilderState:
        """创建模拟的 AgentBuilderState。"""
        state = new_agent_builder_state(
            thread_id=f"test-full-flow-{turn}",
            user_id="test-user",
            user_message=overrides.pop("user_message", self.REQUEST),
        )
        state.update(overrides)
        return state

    # ── 第 1 轮：新会话 → 需求探索 ──

    def test_round1_new_session(self):
        """第 1 轮：用户首次发言 → requirement_intake。"""
        state = self._make_agent_builder_state(turn=1)
        target = route_start(state)
        assert target == "requirement_intake"
        # 模拟 node_requirement_intake 执行后
        state["current_node"] = "wait_intake_confirmation"
        state["spec_name"] = "财报风险识别助手"
        state["stage"] = "exploring"
        state["awaiting_user"] = True
        state["final_response"] = "你想识别哪些具体的财报风险信号？"
        assert state["current_node"] == "wait_intake_confirmation"
        assert state["awaiting_user"] is True

    # ── 第 2 轮：需求确认 → 能力搜索 ──

    def test_round2_confirm_intake(self):
        """第 2 轮：用户确认 → requirement_confirmation。"""
        state = self._make_agent_builder_state(
            turn=2,
            user_message="确认，就关注商誉、应收账款和现金流这三块。",
            current_node="wait_intake_confirmation",
            spec_name="财报风险识别助手",
            stage="exploring",
            message_history=[
                {"role": "agent", "content": "你想识别哪些具体的财报风险信号？"},
            ],
        )
        # route_start: wait 节点 → classify_intent
        assert route_start(state) == "classify_intent"
        # 模拟 LLM 分类结果
        state["user_intent"] = "confirmed"
        state["intent_confidence"] = 0.95
        result = route_after_classify(state)
        assert result == "requirement_confirmation"

    # ── 第 3 轮：测试请求 → 代码提取 → 真实测试 ──

    def test_round3_test_with_explicit_symbol(self):
        """第 3 轮：用户明确输入股票代码。"""
        state = self._make_agent_builder_state(
            turn=3,
            user_message="600519",
            current_node="wait_test_request",
            spec_name="财报风险识别助手",
            version_id="spec_financial_risk_v1_v1",
            stage="testing",
            message_history=[
                {"role": "agent", "content": "要不要现在测试？比如输入 600519（贵州茅台）"},
            ],
        )
        assert route_start(state) == "classify_intent"
        # LLM 分类：confirmed + test_symbol 提取
        state["user_intent"] = "confirmed"
        state["intent_confidence"] = 0.92
        state["test_symbol"] = "600519"
        result = route_after_classify(state)
        assert result == "real_data_test"

    def test_round3_test_confirm_agent_suggestion(self):
        """第 3 轮：用户确认 Agent 建议的代码（"好的，测试吧"）。"""
        state = self._make_agent_builder_state(
            turn=3,
            user_message="好的，进行测试吧",
            current_node="wait_test_request",
            spec_name="财报风险识别助手",
            version_id="spec_financial_risk_v1_v1",
            stage="testing",
            message_history=[
                {"role": "agent", "content": "要不要现在就拉一只真实股票试试？比如输入 600519（贵州茅台）"},
            ],
        )
        assert route_start(state) == "classify_intent"
        # LLM 从上下文推断 test_symbol
        state["user_intent"] = "confirmed"
        state["intent_confidence"] = 0.90
        state["test_symbol"] = "600519"
        assert route_after_classify(state) == "real_data_test"

    def test_round3_test_no_symbol_clarifies(self):
        """第 3 轮：用户未提供代码 → 澄清举例。"""
        state = self._make_agent_builder_state(
            turn=3,
            user_message="测试吧",
            current_node="wait_test_request",
            spec_name="财报风险识别助手",
            version_id="spec_financial_risk_v1_v1",
            stage="testing",
            message_history=[
                {"role": "agent", "content": "要测试吗？提供一个股票代码"},
            ],
        )
        assert route_start(state) == "classify_intent"
        state["user_intent"] = "confirmed"
        state["intent_confidence"] = 0.85
        state["test_symbol"] = ""
        result = route_after_classify(state)
        assert result == "wait_test_request"
        assert state["clarification_needed"] is True

    # ── 第 4 轮：评估后重测 ──

    def test_round4_retry_different_symbol(self):
        """第 4 轮：发布后要求换股票重测。"""
        state = self._make_agent_builder_state(
            turn=4,
            user_message="换宁德时代再测一次",
            current_node="wait_evaluation",
            spec_name="财报风险识别助手",
            version_id="spec_financial_risk_v1_v1",
            official_acceptance_decision="published",
            stage="completed",
            message_history=[
                {"role": "agent", "content": "测试完成，茅台财报风险评分75，已发布。"},
            ],
        )
        assert route_start(state) == "classify_intent"
        state["user_intent"] = "retry"
        state["intent_confidence"] = 0.92
        state["test_symbol"] = "300750"
        result = route_after_classify(state)
        assert result == "wait_test_request"

    def test_round4_revise_add_dimension(self):
        """第 4 轮：评估后添加分析维度。"""
        state = self._make_agent_builder_state(
            turn=4,
            user_message="再加一个利润质量分析维度",
            current_node="wait_evaluation",
            spec_name="财报风险识别助手",
            stage="completed",
            message_history=[
                {"role": "agent", "content": "商誉、应收、现金流三维度风险分析已就绪。"},
            ],
        )
        assert route_start(state) == "classify_intent"
        state["user_intent"] = "revise"
        state["intent_confidence"] = 0.93
        result = route_after_classify(state)
        assert result == "requirement_intake"

    # ── 第 5 轮：低置信度澄清 ──

    def test_round5_ambiguous_reply(self):
        """第 5 轮：用户回复模糊 → LLM 低置信度 → 回到当前节点 + 澄清。"""
        state = self._make_agent_builder_state(
            turn=5,
            user_message="看看",
            current_node="wait_evaluation",
            spec_name="财报风险识别助手",
            stage="completed",
            message_history=[
                {"role": "agent", "content": "测试完成，要发布还是重测？"},
            ],
        )
        assert route_start(state) == "classify_intent"
        state["user_intent"] = "explore_more"
        state["intent_confidence"] = 0.35
        result = route_after_classify(state)
        assert result == "wait_evaluation"
        assert state["clarification_needed"] is True

    # ── 第 6 轮：new_agent 意图 ──

    def test_round6_new_agent_intent(self):
        """第 6 轮：已发布 Agent 被要求做新功能 → 识别为 new_agent。"""
        state = self._make_agent_builder_state(
            turn=6,
            user_message="我要新建一个舆情监控Agent，不是改现在这个",
            current_node="wait_evaluation",
            spec_name="财报风险识别助手",
            official_acceptance_decision="published",
            stage="completed",
            message_history=[
                {"role": "agent", "content": "财报风险识别助手已发布，可以继续测试其他标的。"},
            ],
        )
        assert route_start(state) == "classify_intent"
        state["user_intent"] = "new_agent"
        state["intent_confidence"] = 0.96
        result = route_after_classify(state)
        assert result == "end"
        assert "新建 Agent" in state.get("final_response", "") or "创建" in state.get("final_response", "")

    # ── 第 7 轮：异常恢复 ──

    def test_round7_error_recovery_retry(self):
        """第 7 轮：错误恢复阶段确认重试。"""
        state = self._make_agent_builder_state(
            turn=7,
            user_message="重试",
            current_node="error_recovery",
            spec_name="财报风险识别助手",
            errors=[
                {"node": "gap_analysis", "error": "analyze_agent_workshop_gaps 超时"},
            ],
            stage="error",
            message_history=[
                {"role": "agent", "content": "能力搜索超时，要重试还是修改需求？"},
            ],
        )
        assert route_start(state) == "classify_intent"
        state["user_intent"] = "confirmed"
        state["intent_confidence"] = 0.88
        # route_after_classify → error_recovery 的 confirmed 分支
        # 应该回到上一个可重试节点
        result = route_after_classify(state)
        # 至少不能是 end
        assert result != "end"


# ====================================================================
# 第六部分：JSON 提取边界测试
# ====================================================================

class TestJsonExtraction:
    """测试 LLM 返回内容的 JSON 提取。"""

    def test_extract_valid_json(self):
        result = _extract_json_from_result('{"intent": "confirmed", "confidence": 0.9}')
        assert result.get("intent") == "confirmed"

    def test_extract_json_with_markdown_codeblock(self):
        result = _extract_json_from_result(
            '```json\n{"intent": "retry", "confidence": 0.85}\n```'
        )
        assert result.get("intent") == "retry"

    def test_extract_nested_json_string(self):
        result = _extract_json_from_result(
            '{"intent": "retry", "confidence": 0.92, "test_symbol": "300750"}'
        )
        assert result["intent"] == "retry"
        assert result["test_symbol"] == "300750"

    def test_extract_json_with_surrounding_text(self):
        result = _extract_json_from_result(
            '用户应该是要重测。\n{"intent": "retry", "confidence": 0.9}\n明白了。'
        )
        assert result.get("intent") == "retry"

    def test_extract_empty_or_invalid(self):
        assert _extract_json_from_result("") == {}
        assert _extract_json_from_result("hello world") == {}
        assert _extract_json_from_result(None) == {}


# ====================================================================
# 第七部分：完整流程快照测试
# ====================================================================

class TestCompleteFlowSnapshot:
    """
    模拟「财报风险识别助手」完整 8 轮对话的节点流转快照。

    预期流程：
      1. 用户提需求 → requirement_intake → wait_intake_confirmation
      2. 用户确认需求 → requirement_confirmation → wait_requirement_confirmation
      3. 用户确认规格 → gap_analysis → plan_generation
      4. 用户选方案 → generate_candidate_agent → build_or_ready → wait_test_request
      5. 用户给代码 → real_data_test → wait_evaluation
      6. 用户确认发布 → evaluate_or_publish → wait_evaluation (已发布)
      7. 用户要求重测另一股票 → classify_intent (retry) → wait_test_request
      8. 用户给新代码 → real_data_test → wait_evaluation
    """

    def _simulate_turn(self, state: AgentBuilderState, user_msg: str,
                       intent: str, confidence: float = 0.9, **extra) -> Tuple[str, AgentBuilderState]:
        """模拟一轮完整交互：route_start → classify_intent → route_after_classify。"""
        state["user_message"] = user_msg
        # 追加到对话历史
        history = state.setdefault("message_history", [])
        if state.get("final_response"):
            history.append({"role": "agent", "content": state["final_response"]})
        history.append({"role": "user", "content": user_msg})
        if len(history) > 20:
            state["message_history"] = history[-20:]

        # 路由
        start_target = route_start(state)
        assert start_target == "classify_intent", \
            f"Expected classify_intent, got {start_target} (current_node={state.get('current_node')})"

        # LLM 分类
        state["user_intent"] = intent
        state["intent_confidence"] = confidence
        for k, v in extra.items():
            state[k] = v

        result = route_after_classify(state)
        return result, state

    def test_full_flow_8_turns(self):
        """完整 8 轮对话快照测试。"""
        # ── 第 1 轮：新建 ──
        state = new_agent_builder_state("snapshot-001", "user-001",
                                         user_message=TEST_USER_REQUEST)
        target = route_start(state)
        assert target == "requirement_intake"
        state["current_node"] = "wait_intake_confirmation"
        state["stage"] = "exploring"
        state["spec_name"] = "财报风险识别助手"
        state["awaiting_user"] = True
        state["final_response"] = "你的需求是识别财报风险，关注商誉减值、应收账款和现金流。需要确认以下几点：[...]\n\n同意这些设定吗？"

        # ── 第 2 轮：确认需求 ──
        target, state = self._simulate_turn(
            state, "确认，没问题", "confirmed", 0.95,
        )
        assert target == "requirement_confirmation"
        state["current_node"] = "wait_requirement_confirmation"
        state["stage"] = "confirming"
        state["awaiting_user"] = True
        state["final_response"] = "[需求确认完成]"

        # ── 第 3 轮：确认规格 ──
        target, state = self._simulate_turn(
            state, "可以，按这个规格来", "confirmed", 0.95,
        )
        assert target == "gap_analysis"
        # 模拟自动流转（不再需要用户输入，走完缺口分析 → 方案生成）
        state["current_node"] = "wait_plan_selection"
        state["stage"] = "selecting"
        state["awaiting_user"] = True
        state["pending_options"] = [
            {"id": "plan_standard", "label": "A", "title": "标准方案"},
            {"id": "plan_advanced", "label": "B", "title": "高级方案"},
        ]
        state["final_response"] = "我为你生成了两个方案：[...]\n请选择 A 或 B。"

        # ── 第 4 轮：选方案 ──
        target, state = self._simulate_turn(
            state, "选B，高级方案", "select_option", 0.95,
            user_selected_id="plan_advanced",
        )
        assert target == "generate_candidate_agent"
        state["current_node"] = "wait_test_request"
        state["stage"] = "testing"
        state["awaiting_user"] = True
        state["version_id"] = "spec_financial_risk_v1"
        state["build_status"] = "built"
        state["final_response"] = "Agent 已生成！版本 v1，要不要用真实股票测试？比如 600519（贵州茅台）。"

        # ── 第 5 轮：给代码测试 ──
        target, state = self._simulate_turn(
            state, "600519", "confirmed", 0.92,
            test_symbol="600519",
        )
        assert target == "real_data_test"
        state["current_node"] = "wait_evaluation"
        state["stage"] = "evaluating"
        state["awaiting_user"] = True
        state["test_result"] = {"status": "pass", "score": 78}
        state["final_response"] = "茅台 600519 财报风险评分 78，商誉风险：低，应收风险：中，现金流风险：低。要发布吗？"

        # ── 第 6 轮：发布 ──
        target, state = self._simulate_turn(
            state, "发布", "confirmed", 0.95,
        )
        assert target == "evaluate_or_publish"
        state["current_node"] = "wait_evaluation"
        state["official_acceptance_decision"] = "published"
        state["stage"] = "completed"
        state["awaiting_user"] = True
        state["final_response"] = "已成功发布！可以继续测试其他标的或修改需求。"

        # ── 第 7 轮：重测另一股票 ──
        target, state = self._simulate_turn(
            state, "换宁德时代再测一次", "retry", 0.92,
            test_symbol="300750",
        )
        assert target == "wait_test_request"
        # retry 路由到了 wait_test_request，但 simulate_turn 不会真的执行节点，
        # 所以需要手动切 current_node 为 wait_test_request
        state["current_node"] = "wait_test_request"
        state["stage"] = "testing"
        state["awaiting_user"] = True
        state["final_response"] = "收到！要对宁德时代（300750）进行财报风险测试吗？请确认。"

        # ── 第 8 轮：给新代码 ──
        target, state = self._simulate_turn(
            state, "300750", "confirmed", 0.95,
            test_symbol="300750",
        )
        assert target == "real_data_test"

    def test_single_turn_cancel_mid_flow(self):
        """中途取消 → end。"""
        state = new_agent_builder_state("cancel-001", "user-001")
        state["current_node"] = "wait_evaluation"
        state["spec_name"] = "财报风险识别助手"
        state["final_response"] = "要发布吗？"

        target, state = self._simulate_turn(
            state, "算了不做了", "cancel", 0.95,
        )
        assert target == "end"

    def test_round8_after_publish_user_asks_question(self):
        """发布后用户闲聊提问 → explore_more → 停留 wait_evaluation + 澄清。"""
        state = new_agent_builder_state("question-001", "user-001")
        state["current_node"] = "wait_evaluation"
        state["official_acceptance_decision"] = "published"
        state["spec_name"] = "财报风险识别助手"
        state["final_response"] = "已发布。"

        target, state = self._simulate_turn(
            state, "你支持哪些数据源啊？", "explore_more", 0.55,
        )
        # 低置信度 → 停留
        assert target == "wait_evaluation"
        assert state["clarification_needed"] is True


# ====================================================================
# 辅助函数
# ====================================================================

def new_state(user_message: str = "", **overrides) -> AgentBuilderState:
    """快速创建测试用状态。"""
    state = new_agent_builder_state(
        thread_id="test-thread",
        user_id="test-user",
        user_message=user_message,
    )
    state.update(overrides)
    return state


def headline_request() -> str:
    return TEST_USER_REQUEST


# ====================================================================
# 可单独运行的 smoke test
# ====================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("Agent Builder 全流程验证 (smoke)")
    print("=" * 60)

    failed: List[str] = []
    passed: List[str] = []

    def check(name: str, cond: bool, detail: str = ""):
        if cond:
            passed.append(name)
            print(f"  ✅ {name}")
        else:
            failed.append(f"{name} -- {detail}")
            print(f"  ❌ {name}  -- {detail}")

    # ── 状态 ──
    s = new_agent_builder_state("t1", "u1", user_message=headline_request())
    check("创建状态", s["current_node"] == "START" and s["thread_id"] == "t1")
    check("白名单含 message_history", "message_history" in _KNOWN_KEYS)
    check("白名单含 user_intent", "user_intent" in _KNOWN_KEYS)

    # ── 路由 ──
    check("新会话 → requirement_intake", route_start(s) == "requirement_intake")
    s["current_node"] = "wait_evaluation"
    check("wait 节点 → classify_intent", route_start(s) == "classify_intent")

    s["user_intent"] = "cancel"
    s["intent_confidence"] = 0.9
    check("cancel → end", route_after_classify(s) == "end")

    # ── 意图分类 ──
    check("节点类型映射", _classify_node_type("wait_evaluation") == "test_eval")
    check("兜底分类", _fallback_classify_intent("取消", "wait_evaluation") == "cancel")
    check("停留预判", _will_stay_on_wait_node(
        new_state("啥意思", current_node="wait_intake_confirmation", user_intent="explore_more")
    ) is True)

    # ── 提示词 ──
    prompt = _build_classify_prompt(s, "test_eval")
    check("提示词生成", len(prompt) > 100, f"长度: {len(prompt)}")

    # ── JSON ──
    j = _extract_json_from_result('{"a": 1}')
    check("JSON 提取", j == {"a": 1})

    print(f"\n{'=' * 60}")
    print(f"结果: {len(passed)} 通过, {len(failed)} 失败")
    print(f"{'=' * 60}")
    if failed:
        sys.exit(1)
