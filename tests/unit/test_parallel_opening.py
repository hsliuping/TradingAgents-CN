"""A3 投资辩论并行开局单元测试

覆盖：
- _merge_debate_states：辩论状态合并规则（history 拼接顺序 / 非空值优先）
- _create_parallel_opening_node_func：并行执行、独立字段合并、
  共享 debate_state 深合并、count 增量
- WorkflowAPI._prepare_inputs：并行开局开关注入（默认 / env 回退 / 输入覆盖）
"""

import os
from types import SimpleNamespace

import pytest

from core.workflow.builder import WorkflowBuilder


# ==================== _merge_debate_states ====================

class TestMergeDebateStates:
    def test_old_empty_returns_new_copy(self):
        new = {"history": "Bull Analyst: A", "bull_history": "Bull Analyst: A"}
        merged = WorkflowBuilder._merge_debate_states(None, new)
        assert merged == new
        assert merged is not new

    def test_history_concat_in_speaker_order(self):
        old = {
            "history": "Bull Analyst: 观点A",
            "bull_history": "Bull Analyst: 观点A",
            "current_response": "Bull Analyst: 观点A",
        }
        new = {
            "history": "Bear Analyst: 观点B",
            "bear_history": "Bear Analyst: 观点B",
            "current_response": "Bear Analyst: 观点B",
        }
        merged = WorkflowBuilder._merge_debate_states(old, new)
        assert merged["history"] == "Bull Analyst: 观点A\nBear Analyst: 观点B"
        assert merged["bull_history"] == "Bull Analyst: 观点A"
        assert merged["bear_history"] == "Bear Analyst: 观点B"
        # 最新发言取后发言者
        assert merged["current_response"] == "Bear Analyst: 观点B"

    def test_nonempty_wins_over_empty(self):
        """并行双方基于同一初始 state 拷贝，bear 结果里 bull_history 为空，
        不能覆盖已合并的非空 bull_history"""
        old = {"history": "Bull Analyst: A", "bull_history": "Bull Analyst: A"}
        new = {
            "history": "Bear Analyst: B",
            "bear_history": "Bear Analyst: B",
            "bull_history": "",  # bear 拷贝自初始 state，bull_history 为空
        }
        merged = WorkflowBuilder._merge_debate_states(old, new)
        assert merged["bull_history"] == "Bull Analyst: A"
        assert merged["bear_history"] == "Bear Analyst: B"


# ==================== _create_parallel_opening_node_func ====================

def _make_builder_with_stubs(stub_results):
    """构造跳过 __init__ 的 WorkflowBuilder，stub 掉 _create_node_function"""
    builder = object.__new__(WorkflowBuilder)
    calls = []

    def fake_create_node_function(node):
        pid = node.id

        def fn(state):
            calls.append(pid)
            return stub_results[pid]

        return fn

    builder._create_node_function = fake_create_node_function
    return builder, calls


class TestParallelOpeningNode:
    BULL_RESULT = {
        "bull_report": "乐观简报",
        "investment_debate_state": {
            "history": "Bull Analyst: 观点A",
            "bull_history": "Bull Analyst: 观点A",
            "current_response": "Bull Analyst: 观点A",
        },
    }
    BEAR_RESULT = {
        "bear_report": "审慎简报",
        "investment_debate_state": {
            "history": "Bear Analyst: 观点B",
            "bear_history": "Bear Analyst: 观点B",
            "current_response": "Bear Analyst: 观点B",
        },
    }

    def _build_node_func(self):
        stub_results = {
            "bull_researcher": dict(self.BULL_RESULT),
            "bear_researcher": dict(self.BEAR_RESULT),
        }
        builder, calls = _make_builder_with_stubs(stub_results)
        config = {
            "participants": ["bull_researcher", "bear_researcher"],
            "rounds": 2,
            "next_node": "research_manager",
            "debate_key": "_debate_debate_count",
        }
        definition = SimpleNamespace(
            get_node=lambda pid: SimpleNamespace(id=pid)
        )
        node_func = builder._create_parallel_opening_node_func(
            "debate", config, definition
        )
        return node_func, calls

    def test_all_participants_executed(self):
        node_func, calls = self._build_node_func()
        node_func({"investment_debate_state": {"history": "", "count": 0}})
        assert sorted(calls) == ["bear_researcher", "bull_researcher"]

    def test_independent_fields_merged(self):
        node_func, _ = self._build_node_func()
        result = node_func({"investment_debate_state": {"history": "", "count": 0}})
        assert result["bull_report"] == "乐观简报"
        assert result["bear_report"] == "审慎简报"

    def test_debate_state_deep_merged(self):
        node_func, _ = self._build_node_func()
        result = node_func({"investment_debate_state": {"history": "", "count": 0}})
        ds = result["investment_debate_state"]
        assert ds["history"] == "Bull Analyst: 观点A\nBear Analyst: 观点B"
        assert ds["bull_history"] == "Bull Analyst: 观点A"
        assert ds["bear_history"] == "Bear Analyst: 观点B"

    def test_count_increment_equals_participants(self):
        node_func, _ = self._build_node_func()
        result = node_func({"investment_debate_state": {"history": "", "count": 0}})
        assert result["_debate_debate_count"] == 2

    def test_missing_debate_state_falls_back_to_input(self):
        """参与者都没返回 debate_state 时，沿用输入的初始 state"""
        stub_results = {
            "bull_researcher": {"bull_report": "x"},
            "bear_researcher": {"bear_report": "y"},
        }
        builder, _ = _make_builder_with_stubs(stub_results)
        config = {
            "participants": ["bull_researcher", "bear_researcher"],
            "rounds": 1,
            "next_node": "research_manager",
            "debate_key": "_debate_debate_count",
        }
        definition = SimpleNamespace(get_node=lambda pid: SimpleNamespace(id=pid))
        node_func = builder._create_parallel_opening_node_func(
            "debate", config, definition
        )
        initial = {"history": "", "count": 0}
        result = node_func({"investment_debate_state": initial})
        assert result["investment_debate_state"] == initial
        assert result["_debate_debate_count"] == 2


# ==================== 开关注入（workflow_api._prepare_inputs） ====================

class TestParallelOpeningSwitch:
    def _prepare(self, inputs=None, monkeypatch=None):
        from core.api.workflow_api import WorkflowAPI

        api = object.__new__(WorkflowAPI)
        if monkeypatch is not None:
            monkeypatch.delenv("RESEARCH_PARALLEL_OPENING", raising=False)
        return api._prepare_inputs(inputs or {"research_depth": "深度"})

    def test_default_on(self, monkeypatch):
        prepared = self._prepare(monkeypatch=monkeypatch)
        assert prepared["_parallel_opening"] is True

    def test_env_off_forces_off(self, monkeypatch):
        monkeypatch.setenv("RESEARCH_PARALLEL_OPENING", "off")
        prepared = self._prepare()
        assert prepared["_parallel_opening"] is False

    def test_env_on_overrides_explicit_input(self, monkeypatch):
        monkeypatch.setenv("RESEARCH_PARALLEL_OPENING", "on")
        prepared = self._prepare({"research_depth": "快速", "parallel_opening": False})
        assert prepared["_parallel_opening"] is True

    def test_input_override_when_env_auto(self, monkeypatch):
        monkeypatch.delenv("RESEARCH_PARALLEL_OPENING", raising=False)
        prepared = self._prepare({"research_depth": "标准", "parallel_opening": False})
        assert prepared["_parallel_opening"] is False

    def test_all_depths_default_on(self, monkeypatch):
        for depth in ("快速", "基础", "标准", "深度", "全面"):
            prepared = self._prepare(
                {"research_depth": depth}, monkeypatch=monkeypatch
            )
            assert prepared["_parallel_opening"] is True, f"{depth} 档应默认启用"
