"""执行模式 PR3 单测：服务层清洗旁路（compliance 统一守卫）+ 复盘护栏 + 留痕

设计文档：docs/05-design/v4.0/execution-advice-mode-design.md §5.3 / §7.2
"""

import pytest


def _set_bypass(monkeypatch, active: bool):
    """控制 compliance._execution_bypass_active 的两个输入"""
    from core.agents import advice_mode

    class _Settings:
        EXECUTION_ADVICE_MODE = active

    monkeypatch.setattr("app.core.config.settings", _Settings())
    monkeypatch.setattr(advice_mode, "_EXECUTION_TEMPLATE_CACHE", {})
    monkeypatch.setattr(advice_mode, "_ANY_EXECUTION_TEMPLATE_CACHE", None)
    # 全局执行模板存在性与开关保持一致（开关开=有模板，开关关=无模板）
    monkeypatch.setattr(advice_mode, "any_execution_template_exists", lambda: active)


# ==================== S1：持仓 payload ====================

class TestPositionPayloadBypass:
    _PAYLOAD = {
        "action": "trim",
        "summary": "浮盈超过5%，按计划执行第一档减仓",
        "price_targets": {"trim_1": 45.0},
        "suggested_quantity": 300,
        "suggested_amount": 13500,
        "risk_assessment": "跌破5日线需警惕回撤",
    }

    def test_research_mode_forces_hold(self, monkeypatch):
        _set_bypass(monkeypatch, False)
        from app.utils.compliance import sanitize_position_analysis_payload

        out = sanitize_position_analysis_payload(dict(self._PAYLOAD))
        assert out["action"] == "hold"
        assert out["price_targets"] == {}
        assert out["suggested_quantity"] is None
        assert out["suggested_amount"] is None

    def test_execution_mode_passthrough(self, monkeypatch):
        _set_bypass(monkeypatch, True)
        from app.utils.compliance import sanitize_position_analysis_payload

        out = sanitize_position_analysis_payload(dict(self._PAYLOAD))
        assert out["action"] == "trim"
        assert out["price_targets"] == {"trim_1": 45.0}
        assert out["suggested_quantity"] == 300
        assert out["suggested_amount"] == 13500


# ==================== S3：复盘 payload ====================

class TestTradeReviewPayloadBypass:
    _PAYLOAD = {
        "summary": "本次止盈执行到位",
        "optimal_pnl": 1500.0,
        "missed_profit": 800.0,
        "avoided_loss": 300.0,
        "suggestions": ["浮盈5%未设保本单，下次开仓当日将止损上移成本线"],
    }

    def test_research_mode_drops_quant_fields(self, monkeypatch):
        _set_bypass(monkeypatch, False)
        from app.utils.compliance import sanitize_trade_review_payload

        out = sanitize_trade_review_payload(dict(self._PAYLOAD))
        assert "optimal_pnl" not in out
        assert "missed_profit" not in out
        assert "avoided_loss" not in out

    def test_execution_mode_keeps_quant_fields(self, monkeypatch):
        _set_bypass(monkeypatch, True)
        from app.utils.compliance import sanitize_trade_review_payload

        out = sanitize_trade_review_payload(dict(self._PAYLOAD))
        assert out["optimal_pnl"] == 1500.0
        assert out["missed_profit"] == 800.0
        assert out["avoided_loss"] == 300.0
        assert "保本单" in out["suggestions"][0]


# ==================== S4：报告键白名单 ====================

class TestFilterReportsBypass:
    def test_research_mode_whitelists_keys(self, monkeypatch):
        _set_bypass(monkeypatch, False)
        from app.utils.compliance import filter_analysis_reports

        reports = {"market_report": "市场结构分析内容" * 2, "trader_investment_plan": "操作建议计划内容"}
        out = filter_analysis_reports(reports)
        assert "market_report" in out
        assert "trader_investment_plan" not in out  # 决策类键被白名单排除

    def test_execution_mode_passes_all_keys(self, monkeypatch):
        _set_bypass(monkeypatch, True)
        from app.utils.compliance import filter_analysis_reports

        reports = {"market_report": "市场结构分析内容", "trader_investment_plan": "BUY，止损 39.8"}
        out = filter_analysis_reports(reports)
        assert out["trader_investment_plan"] == "BUY，止损 39.8"


# ==================== 判定类与文本块 ====================

class TestTextBlockBypass:
    def test_contains_actionable(self, monkeypatch):
        _set_bypass(monkeypatch, False)
        from app.utils.compliance import contains_actionable_content

        assert contains_actionable_content("建议买入该股票") is True
        _set_bypass(monkeypatch, True)
        assert contains_actionable_content("建议买入该股票") is False

    def test_sanitize_text_block_keeps_action_lines_in_execution(self, monkeypatch):
        _set_bypass(monkeypatch, True)
        from app.utils.compliance import sanitize_text_block

        text = "操作方向：BUY，建议仓位 30%，止损参考 39.8 元"
        out = sanitize_text_block(text)
        assert "BUY" in out and "39.8" in out

    def test_sanitize_text_block_strips_action_lines_in_research(self, monkeypatch):
        _set_bypass(monkeypatch, False)
        from app.utils.compliance import sanitize_text_block

        out = sanitize_text_block("操作方向：BUY，建议买入该股票并设置止损")
        assert "BUY" not in out


# ==================== S2：复盘提示词护栏 ====================

class TestReviewGuardrailsBypass:
    def _service(self):
        from app.services.trade_review_service import TradeReviewService

        return object.__new__(TradeReviewService)

    def test_research_mode_appends_guardrails(self, monkeypatch):
        _set_bypass(monkeypatch, False)
        out = self._service()._append_review_guardrails("复盘提示词")
        assert "输出约束" in out

    def test_execution_mode_returns_prompt_unchanged(self, monkeypatch):
        _set_bypass(monkeypatch, True)
        out = self._service()._append_review_guardrails("复盘提示词")
        assert out == "复盘提示词"
