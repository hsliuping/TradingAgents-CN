"""执行模式 PR2 单测：agent 层拦截开关化（A1-A5）+ 执行版 schema 路由

设计文档：docs/05-design/v4.0/execution-advice-mode-design.md §5.2 / §6
"""

import json

import pytest


def _set_switch(monkeypatch, on: bool):
    from core.agents import advice_mode

    class _Settings:
        EXECUTION_ADVICE_MODE = on

    monkeypatch.setattr("app.core.config.settings", _Settings())
    # 清空执行模板存在性缓存，保证用例间不串扰
    monkeypatch.setattr(advice_mode, "_EXECUTION_TEMPLATE_CACHE", {})
    return advice_mode


# ==================== use_execution_output 组合逻辑 ====================

class TestUseExecutionOutput:
    def test_switch_off_always_research(self, monkeypatch):
        advice_mode = _set_switch(monkeypatch, False)
        monkeypatch.setattr(
            advice_mode, "execution_template_available",
            lambda at, an: True,  # 即使模板存在，开关关也必须是研究模式
        )
        assert advice_mode.use_execution_output("managers_v2", "research_manager_v2") is False

    def test_switch_on_with_template(self, monkeypatch):
        advice_mode = _set_switch(monkeypatch, True)
        monkeypatch.setattr(
            advice_mode, "execution_template_available", lambda at, an: True
        )
        assert advice_mode.use_execution_output("managers_v2", "research_manager_v2") is True

    def test_switch_on_without_template_is_research(self, monkeypatch):
        """无效开关保证：发行版无 execution 模板 → 研究行为"""
        advice_mode = _set_switch(monkeypatch, True)
        monkeypatch.setattr(
            advice_mode, "execution_template_available", lambda at, an: False
        )
        assert advice_mode.use_execution_output("managers_v2", "research_manager_v2") is False

    def test_execution_template_available_short_circuits_when_off(self, monkeypatch):
        advice_mode = _set_switch(monkeypatch, False)
        # 开关关时不查库（cache 不会写入）
        assert advice_mode.execution_template_available("x", "y") is False
        assert advice_mode._EXECUTION_TEMPLATE_CACHE == {}


# ==================== A5：全局守卫 ====================

class TestGlobalGuard:
    def _guard(self, mode_mark):
        from core.agents.base import BaseAgent

        class _ConcreteAgent(BaseAgent):
            def execute(self, state):  # pragma: no cover - 仅为绕过抽象类限制
                return {}

        agent = object.__new__(_ConcreteAgent)
        if mode_mark is not None:
            agent._template_advice_mode = mode_mark
        return agent

    def test_guard_applied_by_default(self):
        agent = self._guard(None)
        out = agent._apply_global_trading_advice_guard("系统提示词")
        assert "合规防护" in out

    def test_guard_applied_in_research_mode(self):
        agent = self._guard("research")
        out = agent._apply_global_trading_advice_guard("系统提示词")
        assert "禁止输出具体买卖指令" in out

    def test_guard_skipped_in_execution_mode(self):
        agent = self._guard("execution")
        out = agent._apply_global_trading_advice_guard("系统提示词")
        assert out == "系统提示词"


# ==================== A2：trader 校验路由 ====================

class TestTraderValidationRouting:
    def _agent(self):
        from core.agents.adapters.trader_v2 import TraderV2

        return object.__new__(TraderV2)

    def test_research_mode_flags_forbidden_terms(self, monkeypatch):
        advice_mode = _set_switch(monkeypatch, False)
        monkeypatch.setattr(advice_mode, "execution_template_available", lambda at, an: True)
        agent = self._agent()
        text = "## 一句话结论\n## 为什么这么看\n建议买入该股票"
        warning = agent._validate_trader_output(text)
        assert warning is not None and "不合规术语" in warning

    def test_execution_mode_skips_terms_checks_structure(self, monkeypatch):
        advice_mode = _set_switch(monkeypatch, True)
        monkeypatch.setattr(advice_mode, "execution_template_available", lambda at, an: True)
        agent = self._agent()
        text = (
            "## 操作方向\nBUY\n## 建议仓位\n30%\n## 入场区间\n41-42\n"
            "## 分批计划\n第1档：涨至45减1/3\n## 止损与移动止盈\n止损39，跌破5日线\n"
            "## 触发条件\n放量滞涨\n## 核心依据\n证据A\n"
            "## 免责声明\n本内容为执行模式输出，仅供使用者个人决策参考，不构成任何投资建议；据此操作风险自担。"
        )
        assert agent._validate_trader_output(text) is None

    def test_execution_mode_missing_disclaimer_fails(self, monkeypatch):
        advice_mode = _set_switch(monkeypatch, True)
        monkeypatch.setattr(advice_mode, "execution_template_available", lambda at, an: True)
        agent = self._agent()
        text = "## 操作方向\nBUY\n## 止损与移动止盈\n止损39\n"
        warning = agent._validate_trader_output(text)
        assert warning is not None and "免责声明" in warning


# ==================== A3：research_manager schema 路由 ====================

_RESEARCH_JSON = json.dumps({
    "analysis_view": "审慎",
    "confidence": 0.6,
    "risk_score": 0.5,
    "summary": "摘要",
    "reasoning": "推理",
    "core_evidence": ["证据1"],
    "uncertainties": ["不确定性1"],
    "invalidation_conditions": ["失效前提1"],
    "watch_items": ["观察1"],
    "risk_warning": "风险提示",
    "observation_levels": {
        "support_1": "41.0",
        "resistance_1": "44.5",
        "invalidation_price": "39.8",
    },
}, ensure_ascii=False)


class TestResearchManagerSchemaRouting:
    def _agent(self):
        from core.agents.adapters.research_manager_v2 import ResearchManagerV2

        return object.__new__(ResearchManagerV2)

    def test_research_mode_drops_observation_levels(self, monkeypatch):
        advice_mode = _set_switch(monkeypatch, False)
        monkeypatch.setattr(advice_mode, "execution_template_available", lambda at, an: True)
        validated, err = self._agent()._validate_research_output(_RESEARCH_JSON)
        assert err is None
        assert "observation_levels" not in validated  # 研究 schema 忽略观察价位

    def test_execution_mode_keeps_observation_levels(self, monkeypatch):
        advice_mode = _set_switch(monkeypatch, True)
        monkeypatch.setattr(advice_mode, "execution_template_available", lambda at, an: True)
        validated, err = self._agent()._validate_research_output(_RESEARCH_JSON)
        assert err is None
        assert validated["observation_levels"]["support_1"] == "41.0"
        assert validated["observation_levels"]["invalidation_price"] == "39.8"


# ==================== A4：risk_manager schema 路由 ====================

_EXECUTION_DECISION_JSON = json.dumps({
    "risk_level": "中",
    "risk_score": 0.5,
    "reasoning": "推理",
    "key_risks": ["风险1"],
    "risk_control": "风控",
    "investment_adjustment": "审慎",
    "final_trade_decision": {
        "action": "BUY",
        "confidence": 0.65,
        "price_analysis_range": "41.0-44.5",
        "stop_loss_reference": "39.8",
        "position_ratio": 0.3,
        "trim_plan": ["第1档：涨至45减1/3"],
        "reasoning": "推理",
        "summary": "摘要",
        "risk_warning": "风险提示",
    },
}, ensure_ascii=False)


class TestRiskManagerSchemaRouting:
    def _agent(self):
        from core.agents.adapters.risk_manager_v2 import RiskManagerV2

        return object.__new__(RiskManagerV2)

    def test_research_mode_rejects_buy_action(self, monkeypatch):
        """研究模式：BUY 不在 Literal 值域 → 校验失败（保持主分支行为）"""
        advice_mode = _set_switch(monkeypatch, False)
        monkeypatch.setattr(advice_mode, "execution_template_available", lambda at, an: True)
        _, err = self._agent()._validate_risk_assessment(_EXECUTION_DECISION_JSON)
        assert err is not None and "Schema 校验失败" in err

    def test_execution_mode_accepts_buy_decision(self, monkeypatch):
        advice_mode = _set_switch(monkeypatch, True)
        monkeypatch.setattr(advice_mode, "execution_template_available", lambda at, an: True)
        validated, err = self._agent()._validate_risk_assessment(_EXECUTION_DECISION_JSON)
        assert err is None
        ftd = validated["final_trade_decision"]
        assert ftd["action"] == "BUY"
        assert ftd["stop_loss_reference"] == "39.8"
        assert ftd["position_ratio"] == 0.3

    def test_switch_on_without_template_still_research(self, monkeypatch):
        """无效开关保证：开关开 + 无执行模板 → BUY 仍被研究 schema 拒绝"""
        advice_mode = _set_switch(monkeypatch, True)
        monkeypatch.setattr(advice_mode, "execution_template_available", lambda at, an: False)
        _, err = self._agent()._validate_risk_assessment(_EXECUTION_DECISION_JSON)
        assert err is not None
