"""Deterministic AlphaGuard UI demo scenarios.

These objects are intentionally synthetic and may only be persisted in the
``alphaguard_ui_demo`` database. They exercise presentation contracts without
calling any production trading service.
"""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from typing import Any


DEMO_DATABASE_NAME = "alphaguard_ui_demo"
DEMO_SCENARIO_ID = "alphaguard-ui-guided-demo-v1"


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _snapshot(
    symbol: str,
    *,
    quality: str = "PASS",
    blocking: list[str] | None = None,
) -> dict[str, Any]:
    snapshot_id = f"demo-snapshot-{symbol}"
    return {
        "snapshot_id": snapshot_id,
        "analysis_id": f"demo-analysis-{symbol}",
        "symbol": symbol,
        "market": "CN",
        "trade_date": "2026-07-28",
        "price_data_version": "demo-price-v1",
        "financial_data_version": "demo-financial-v1",
        "news_data_version": "demo-news-v1",
        "market_context_id": "demo-market-context-v1" if quality == "PASS" else None,
        "data_quality": {
            "status": quality,
            "blocking_reasons": blocking or [],
            "missing_fields": ["financial.available_at"] if quality == "FAIL" else [],
            "checked_at": "2026-07-28T15:35:00+08:00",
        },
        "raw_refs": {
            "prices": [f"demo-price-{symbol}-20260728"],
            "financials": [] if quality == "FAIL" else [f"demo-financial-{symbol}"],
            "news": [f"demo-news-{symbol}"],
            "announcements": [f"demo-announcement-{symbol}"],
        },
        "prompt_versions": {
            "normal_trade_plan": "normal-trade-plan-demo-v1",
            "top_review_decision": "top-review-demo-v1",
        },
        "champion_version_refs": {
            "factor_set": "factor-set-demo-v1",
            "regime": "regime-demo-v1",
            "strategy": "strategy-demo-v1",
        },
        "factor_version_set": {
            "momentum": "momentum-v1",
            "quality": "quality-v1",
            "volatility": "volatility-v1",
        },
        "strategy_version": "strategy-demo-v1",
        "immutable_hash": _hash(snapshot_id),
        "created_at": "2026-07-28T15:36:00+08:00",
    }


def _factors(symbol: str) -> list[dict[str, Any]]:
    return [
        {
            "factor_result_id": f"demo-factor-{factor}-{symbol}",
            "factor_id": factor,
            "factor_version": f"{factor}-v1",
            "calculation_status": "CALCULATED",
            "normalized_score": score,
            "missing_inputs": [],
            "input_hash": _hash(f"{factor}:{symbol}"),
            "calculated_at": "2026-07-28T15:37:00+08:00",
        }
        for factor, score in (("momentum", 0.62), ("quality", 0.71), ("volatility", 0.44))
    ]


def _regime(symbol: str, status: str = "CALCULATED") -> dict[str, Any]:
    return {
        "regime_result_id": f"demo-regime-{symbol}",
        "snapshot_id": f"demo-snapshot-{symbol}",
        "calculation_status": status,
        "regime": "RANGE_WEAK" if status == "CALCULATED" else None,
        "evidence": [
            "demo benchmark MA20 below MA60",
            "demo market breadth neutral",
        ] if status == "CALCULATED" else ["DataQuality stopped the chain"],
        "regime_version": "regime-demo-v1",
        "input_hash": _hash(f"regime:{symbol}"),
        "calculated_at": "2026-07-28T15:38:00+08:00",
    }


def _proposal(symbol: str, status: str, reason: str) -> dict[str, Any]:
    return {
        "proposal_id": f"demo-proposal-{symbol}",
        "candidate_id": f"demo-candidate-{symbol}",
        "snapshot_id": f"demo-snapshot-{symbol}",
        "symbol": symbol,
        "market": "CN",
        "trade_date": "2026-07-28",
        "status": status,
        "action_candidate": "BUY" if status == "TRIGGERED" else "WATCH",
        "strategy_id": "SWING_TREND_PULLBACK",
        "strategy_version": "strategy-demo-v1",
        "regime_result_id": f"demo-regime-{symbol}",
        "factor_set_version": "factor-set-demo-v1",
        "reason_codes": [reason],
        "explanation": reason.replace("_", " "),
        "input_hash": _hash(f"proposal:{symbol}:{status}"),
        "evidence_refs": [{"snapshot_id": f"demo-snapshot-{symbol}"}],
        "automated_execution_allowed": status == "TRIGGERED",
        "created_at": "2026-07-28T15:39:00+08:00",
    }


def _event(symbol: str, stage: str, status: str, reason: str) -> dict[str, Any]:
    id_field = {
        "normal": "plan_id",
        "top": "review_id",
        "consensus": "consensus_id",
        "risk": "risk_decision_id",
        "intent": "intent_id",
    }[stage]
    component_version = {
        "normal": "normal-prompt-demo-v1",
        "top": "top-review-demo-v1",
        "consensus": "consensus-demo-v1",
        "risk": "hard-risk-demo-v1",
        "intent": "order-intent-demo-v1",
    }[stage]
    return {
        "event_id": f"demo-event-{stage}-{symbol}",
        "event_type": f"DEMO_{stage.upper()}",
        "analysis_id": f"demo-analysis-{symbol}",
        "snapshot_id": f"demo-snapshot-{symbol}",
        "quant_proposal_id": f"demo-proposal-{symbol}",
        id_field: f"demo-{stage}-{symbol}",
        "status": status,
        "trace_id": f"demo-trace-{symbol}",
        "reason": reason,
        "input_hash": _hash(f"{stage}:input:{symbol}"),
        "output_hash": _hash(f"{stage}:output:{symbol}:{status}"),
        "component_version": component_version,
        "evidence_refs": [f"demo-snapshot-{symbol}", f"demo-proposal-{symbol}"],
        "created_at": "2026-07-28T15:40:00+08:00",
    }


def _readiness() -> dict[str, Any]:
    services = [
        {
            "service_name": name,
            "status": "HEALTHY",
            "required": True,
            "reachable": True,
            "latency_ms": 1.0,
            "error_code": None,
            "sanitized_message": "isolated demo service",
            "last_checked_at": "2026-07-29T10:00:00+08:00",
        }
        for name in ("api", "mongodb-demo", "redis-not-used", "scheduler-disabled", "queue-worker-disabled", "analysis-worker-disabled")
    ]
    data = [
        {
            "component": component,
            "status": "READY",
            "market": "CN",
            "coverage_start": "2026-07-24",
            "coverage_end": "2026-07-28",
            "record_count": count,
            "required_for": ["UI_DEMO"],
            "blocking_reasons": [],
            "warnings": ["SYNTHETIC_DEMO_DATA"],
        }
        for component, count in (
            ("TRADING_CALENDAR", 3),
            ("QFQ_PRICE_DATA", 5),
            ("RAW_PRICE_DATA", 5),
            ("FINANCIAL_DATA", 5),
            ("NEWS_DATA", 5),
            ("ANNOUNCEMENT_DATA", 5),
            ("MARKET_CONTEXT", 1),
            ("MODEL_PROVIDER", 1),
            ("CHAMPION_ASSIGNMENTS", 5),
        )
    ]
    jobs = [
        {
            "job_name": "demo_fixture",
            "worker_name": "disabled-in-demo",
            "status": "COMPLETED",
            "last_run_id": "demo-seed-v1",
            "last_started_at": "2026-07-29T09:59:59+08:00",
            "last_finished_at": "2026-07-29T10:00:00+08:00",
            "next_scheduled_at": None,
            "retry_count": 0,
            "backlog_count": 0,
            "error_code": None,
            "sanitized_message": "No scheduler or worker is started in demo mode",
        }
    ]
    return {
        "report_id": "demo-readiness-v1",
        "overall_status": "DEGRADED_PAPER",
        "system_mode": "SIM_AUTONOMOUS_DEMO",
        "live_trading_enabled": False,
        "live_execution_allowed": False,
        "service_health": services,
        "data_readiness": data,
        "job_health": jobs,
        "blocking_items": ["FULL_CHALLENGER_PIPELINE_NOT_READY"],
        "warnings": ["DEMO_ENVIRONMENT", "SYNTHETIC_DATA_NOT_INVESTMENT_RESULTS"],
        "paper_execution_ready": True,
        "evaluation_ready": True,
        "experiment_ready": True,
        "challenger_ready": False,
        "live_ready": False,
        "code_commit": "demo-fixture",
        "build_version": "ui-demo-v1",
        "config_hash": _hash("demo-config-v1"),
        "report_hash": _hash("demo-readiness-v1"),
        "generated_at": "2026-07-29T10:00:00+08:00",
    }


def build_demo_fixture() -> dict[str, Any]:
    symbols = ("600519", "601318", "000333", "002594", "300750")
    names = {
        "600519": "贵州茅台",
        "601318": "中国平安",
        "000333": "美的集团",
        "002594": "比亚迪",
        "300750": "宁德时代",
    }
    snapshots = {
        symbol: _snapshot(
            symbol,
            quality="FAIL" if symbol == "600519" else "PASS",
            blocking=["FINANCIAL_PUBLICATION_TIME_UNVERIFIED"] if symbol == "600519" else [],
        )
        for symbol in symbols
    }
    factors = {symbol: ([] if symbol == "600519" else _factors(symbol)) for symbol in symbols}
    regimes = {
        symbol: _regime(symbol, "INSUFFICIENT_DATA" if symbol == "600519" else "CALCULATED")
        for symbol in symbols
    }
    proposals = [
        _proposal("601318", "WATCH", "STRATEGY_SETUP_NOT_COMPLETE"),
        _proposal("000333", "TRIGGERED", "DEMO_TOP_REVIEW_PATH"),
        _proposal("002594", "TRIGGERED", "DEMO_HARD_RISK_PATH"),
        _proposal("300750", "TRIGGERED", "DEMO_COMPLETE_PASS_PATH"),
    ]
    candidates = [
        {
            "candidate_id": f"demo-candidate-{symbol}",
            "symbol": symbol,
            "market": "CN",
            "name": names[symbol],
            "sources": ["USER_SELECTED"],
            "status": "ACTIVE",
            "priority": 50,
            "active_plan_id": None,
            "active_order_ids": ["demo-order-300750"] if symbol == "300750" else [],
            "held_account_ids": ["demo-account-top"] if symbol == "300750" else [],
            "cooldown_until": None,
            "next_scan_at": None,
            "latest_snapshot_id": f"demo-snapshot-{symbol}",
            "removal_requested": False,
            "updated_at": "2026-07-28T15:45:00+08:00",
        }
        for symbol in symbols
    ]
    events = [
        _event("000333", "normal", "PROPOSE_TRADE", "Normal proposed a bounded paper trade"),
        _event("000333", "top", "REJECT", "TopReview rejected evidence concentration risk"),
        _event("002594", "normal", "PROPOSE_TRADE", "Normal proposed a bounded paper trade"),
        _event("002594", "top", "CONFIRM", "TopReview confirmed the proposal"),
        _event("002594", "consensus", "PASS", "Normal and Top reached consensus"),
        _event("002594", "risk", "HARD_RISK_REJECT", "Position concentration limit blocked the trade"),
        _event("300750", "normal", "PROPOSE_TRADE", "Normal proposed a bounded paper trade"),
        _event("300750", "top", "CONFIRM", "TopReview confirmed the proposal"),
        _event("300750", "consensus", "PASS", "Normal and Top reached consensus"),
        _event("300750", "risk", "PASS", "HardRisk approved the bounded paper order"),
        _event("300750", "intent", "CREATED", "OrderIntent created for next trading day execution"),
    ]
    accounts = [
        {
            "account_id": account_id,
            "user_id": "demo-user",
            "account_type": account_type,
            "market": "CN",
            "currency": "CNY",
            "status": "ACTIVE",
            "initial_cash": "1000000.00",
            "cash_available": cash,
            "cash_reserved": "0.00",
            "realized_pnl": "0.00",
            "total_fees": fees,
            "updated_at": "2026-07-29T10:00:00+08:00",
            "execution_environment": "PAPER",
            "live_execution_allowed": False,
        }
        for account_id, account_type, cash, fees in (
            ("demo-account-quant", "PAPER_QUANT", "1000000.00", "0.00"),
            ("demo-account-normal", "PAPER_NORMAL", "1000000.00", "0.00"),
            ("demo-account-top", "PAPER_TOP_CONFIRMED", "980492.20", "7.80"),
        )
    ]
    champions = [
        {
            "champion_slot_id": f"demo-champion-{index}",
            "component_type": component_type,
            "component_key": component_key,
            "market": "CN",
            "current_version_ref": version,
            "previous_version_ref": None,
            "effective_from_trade_date": "2026-07-27",
            "status": "ACTIVE",
            "assignment_hash": _hash(f"champion:{component_key}:{version}"),
            "source_experiment_id": None,
        }
        for index, (component_type, component_key, version) in enumerate(
            (
                ("FACTOR_SET", "default_cn", "factor-set-v1"),
                ("REGIME_CONFIG", "cn_market", "regime-v1"),
                ("STRATEGY_CONFIG", "swing_pullback", "strategy-v1"),
                ("NORMAL_PROMPT", "normal_trade", "normal-prompt-v1"),
                ("HARD_RISK_CONFIG", "paper_cn", "hard-risk-v1"),
            ),
            start=1,
        )
    ]
    experiment = {
        "experiment_id": "demo-experiment-leakage-fail",
        "name": "泄漏审计失败演示",
        "hypothesis": "单变量权重调整可能改善稳健性；本演示故意包含未来标签泄漏。",
        "component_type": "FACTOR_WEIGHT",
        "component_key": "momentum_weight",
        "primary_variable_path": "factor_set.momentum_weight",
        "baseline_version_ref": "factor-set-v1",
        "challenger_version_ref": "factor-set-demo-challenger-v1",
        "experiment_mode": "UNIVARIATE",
        "promotion_eligible": False,
        "execution_supported": True,
        "status": "SUSPENDED",
    }
    readiness = _readiness()
    fixture: dict[str, Any] = {
        "scenario_id": DEMO_SCENARIO_ID,
        "schema_version": "1.0",
        "demo_only": True,
        "user": {
            "id": "demo-user",
            "username": "alphaguard_demo",
            "email": "demo@localhost.invalid",
            "is_active": True,
            "is_verified": True,
            "is_admin": True,
            "created_at": "2026-07-29T09:00:00+08:00",
            "updated_at": "2026-07-29T09:00:00+08:00",
            "last_login": None,
            "preferences": {
                "default_market": "A股",
                "default_depth": "3",
                "ui_theme": "light",
                "language": "zh-CN",
                "notifications_enabled": False,
                "email_notifications": False,
            },
            "daily_quota": 0,
            "concurrent_limit": 0,
            "total_analyses": 0,
            "successful_analyses": 0,
            "failed_analyses": 0,
        },
        "readiness": readiness,
        "operations": {
            "services": readiness["service_health"],
            "data": readiness["data_readiness"],
            "jobs": readiness["job_health"],
            "alerts": [
                {
                    "alert_id": "demo-alert-regime",
                    "severity": "WARNING",
                    "category": "DATA",
                    "code": "DEMO_SCENARIO_DATAQUALITY_FAIL",
                    "title": "演示 DataQuality fail-closed",
                    "sanitized_message": "Synthetic demo scenario; no production effect",
                    "source_module": "app.demo",
                    "source_object_id": "demo-snapshot-600519",
                    "trace_id": "demo-trace-600519",
                    "first_seen_at": "2026-07-29T10:00:00+08:00",
                    "last_seen_at": "2026-07-29T10:00:00+08:00",
                    "occurrence_count": 1,
                    "status": "OPEN",
                }
            ],
        },
        "candidates": candidates,
        "snapshots": snapshots,
        "factors": factors,
        "regimes": regimes,
        "proposals": proposals,
        "decision_events": events,
        "accounts": accounts,
        "positions": {
            "demo-account-top": [{
                "position_id": "demo-position-300750",
                "account_id": "demo-account-top",
                "symbol": "300750",
                "market": "CN",
                "currency": "CNY",
                "quantity": 100,
                "available_quantity": 100,
                "reserved_quantity": 0,
                "average_cost": "195.078",
                "total_cost": "19507.80",
                "realized_pnl": "0.00",
                "total_fees": "7.80",
                "updated_at": "2026-07-29T09:31:00+08:00",
            }],
        },
        "lots": {
            "demo-account-top": [{
                "lot_id": "demo-lot-300750",
                "account_id": "demo-account-top",
                "symbol": "300750",
                "acquired_trade_date": "2026-07-29",
                "original_quantity": 100,
                "remaining_quantity": 100,
                "reserved_quantity": 0,
                "unit_cost": "195.078",
                "total_cost": "19507.80",
                "available_from_date": "2026-07-30",
                "status": "OPEN",
            }],
        },
        "orders": {
            "demo-account-top": [{
                "order_id": "demo-order-300750",
                "intent_id": "demo-intent-300750",
                "account_id": "demo-account-top",
                "account_type": "PAPER_TOP_CONFIRMED",
                "candidate_id": "demo-candidate-300750",
                "source_type": "CONSENSUS_HARD_RISK_PASS",
                "source_object_id": "demo-risk-300750",
                "risk_decision_id": "demo-risk-300750",
                "symbol": "300750",
                "side": "BUY",
                "order_type": "LIMIT",
                "requested_quantity": 100,
                "filled_quantity": 100,
                "remaining_quantity": 0,
                "limit_price": "196.00",
                "average_fill_price": "195.00",
                "total_fees": "7.80",
                "status": "FILLED",
                "reject_reason": None,
                "created_at": "2026-07-28T15:42:00+08:00",
            }],
        },
        "fills": {
            "demo-account-top": [{
                "fill_id": "demo-fill-300750",
                "order_id": "demo-order-300750",
                "account_id": "demo-account-top",
                "trade_date": "2026-07-29",
                "symbol": "300750",
                "side": "BUY",
                "quantity": 100,
                "price": "195.00",
                "notional": "19500.00",
                "fee_breakdown": {
                    "commission": "5.00",
                    "stamp_duty": "0.00",
                    "transfer_fee": "0.39",
                    "regulatory_fee": "2.41",
                    "other_fees": "0.00",
                    "total_fee": "7.80",
                    "fee_policy_version": "fee-demo-v1",
                },
                "matching_engine_version": "matching-demo-v1",
                "fee_policy_version": "fee-demo-v1",
                "created_at": "2026-07-29T09:31:00+08:00",
            }],
        },
        "account_snapshots": {
            "demo-account-quant": [{"account_snapshot_id": "demo-as-quant", "account_id": "demo-account-quant", "trade_date": "2026-07-29", "cash_available": "1000000.00", "cash_reserved": "0.00", "position_market_value": "0.00", "total_equity": "1000000.00", "valuation_complete": True, "missing_price_symbols": []}],
            "demo-account-normal": [{"account_snapshot_id": "demo-as-normal", "account_id": "demo-account-normal", "trade_date": "2026-07-29", "cash_available": "1000000.00", "cash_reserved": "0.00", "position_market_value": "0.00", "total_equity": "1000000.00", "valuation_complete": True, "missing_price_symbols": []}],
            "demo-account-top": [{"account_snapshot_id": "demo-as-top", "account_id": "demo-account-top", "trade_date": "2026-07-29", "cash_available": "980492.20", "cash_reserved": "0.00", "position_market_value": "19580.00", "total_equity": "1000072.20", "valuation_complete": True, "missing_price_symbols": []}],
        },
        "evaluation": {
            "overview": {
                "evaluated_subjects": 5,
                "historical_research_subjects": 0,
                "production_subjects": 5,
                "actual_trade_subjects": 1,
                "horizon_status": {"1D:CALCULATED": 5, "5D:CALCULATED": 5, "10D:CALCULATED": 5, "20D:CALCULATED": 5},
                "pending_horizon_labels": 0,
                "insufficient_data_labels": 0,
                "traded_subjects": 1,
                "untraded_subjects": 4,
                "counterfactual_samples": 4,
                "attribution_completion_rate": 1.0,
                "diagnostic_notice": "Synthetic demo evaluation; not account performance",
            },
            "research_summary": {
                "status": "DEMO_REPORT",
                "report": {
                    "report_id": "demo-research-report",
                    "status": "COMPLETED",
                    "created_at": "2026-07-29T10:00:00+08:00",
                    "run_mode": "UI_DEMO",
                    "research_only": True,
                    "factor_summary": {
                        "momentum@momentum-v1": {
                            "sample_count": 5,
                            "missing_count": 1,
                            "missing_rate": 0.2,
                            "horizon_returns": {
                                horizon: {"average_raw_return": value}
                                for horizon, value in (
                                    ("1D", 0.004),
                                    ("5D", 0.012),
                                    ("10D", 0.018),
                                    ("20D", 0.024),
                                )
                            },
                        },
                    },
                    "regime_summary": {"distribution": {"RANGE_WEAK": 4, "INSUFFICIENT_DATA": 1}, "forward_metrics": {"RANGE_WEAK": {"benchmark_return_20D": {"average": 0.011}, "stock_mae_20D": {"average": -0.032, "worst": -0.071}}}},
                    "strategy_summary": {"status_distribution": {"TRIGGERED": 3, "WATCH": 1, "INSUFFICIENT_DATA": 1}, "entry_touch_evaluated_count": 3, "entry_touch_count": 2, "entry_touch_rate": 0.6667},
                    "model_summary": {"top_reject": 1, "consensus_pass": 2},
                    "risk_execution_summary": {"hard_risk_reject": 1, "paper_fill": 1},
                    "evaluation_summary": {"decision_close_horizon_status": {"1D:CALCULATED": 5, "5D:CALCULATED": 5, "10D:CALCULATED": 5, "20D:CALCULATED": 5}, "attribution_distribution": {"DATA_QUALITY": 1, "MODEL_REVIEW": 1, "HARD_RISK": 1, "EXECUTED": 1, "WATCH": 1}},
                    "caveats": ["Synthetic UI fixture", "Not production performance"],
                },
                "boundary": {"research_only": True, "formal_account_performance": False, "version_discontinuity_code": "PENDING_VERSION_DISCONTINUITY"},
            },
            "accounts": [{"metric_id": "demo-metric-top", "account_id": "demo-account-top", "account_type": "PAPER_TOP_CONFIRMED", "period_start": "2026-07-29", "period_end": "2026-07-29", "status": "CALCULATED", "total_return": "0.0000722", "max_drawdown": "0.0000000", "total_fees": "7.80", "average_exposure_pct": "0.01958", "turnover": "0.01950", "trade_count": 1, "valuation_complete_days": 1, "valuation_incomplete_days": 0}],
            "comparisons": [{"comparison_id": "demo-comparison-top", "comparison_type": "TOP_VS_NORMAL", "symbol": "300750", "pairing_status": "PAIRED", "comparability_reasons": [], "value_added_10d": "0.006", "calculated_at": "2026-07-29T10:00:00+08:00"}],
            "counterfactuals": [{"counterfactual_id": "demo-cf-601318", "subject_id": "demo-subject-601318", "mode": "NO_TRADE", "status": "CALCULATED", "net_pnl": "0.00", "return_pct": "0.008", "created_at": "2026-07-29T10:00:00+08:00"}],
            "attributions": [{"attribution_id": "demo-attr-300750", "subject_id": "demo-subject-300750", "status": "CALCULATED", "outcome_class": "PROFIT", "primary_category": "EXECUTION", "confidence": "0.82", "evidence_refs": ["demo-fill-300750"], "machine_explanation": "Demo T+1 fill matured with locked prices", "overrides": []}],
        },
        "champions": champions,
        "experiments": [experiment],
        "experiment_details": {
            experiment["experiment_id"]: {
                "definition": experiment,
                "variable_changes": [{"variable_path": "factor_set.momentum_weight", "baseline_value": "0.20", "challenger_value": "0.25", "is_primary": True}],
                "dataset_manifests": [{"dataset_manifest_id": "demo-manifest-v1", "snapshot_ids": ["demo-snapshot-300750"], "manifest_hash": _hash("demo-manifest-v1")}],
                "runs": [{"run_id": "demo-run-leakage", "run_type": "OUT_OF_SAMPLE", "status": "COMPLETED"}],
                "shadow_runs": [],
                "challenger_assignments": [],
                "comparison_reports": [{"comparison_report_id": "demo-comparison-insufficient", "status": "INSUFFICIENT_DATA", "negative_metrics": ["paired sample count below policy minimum"]}],
                "risk_reviews": [{"risk_review_id": "demo-risk-review", "status": "REJECT", "reason": "LEAKAGE_AUDIT_FAILED", "leakage_audit": {"status": "FAIL", "evaluation_label_leakage": True}}],
                "promotion_requests": [],
                "events": [{"event_id": "demo-exp-event", "event_type": "LEAKAGE_AUDIT_FAILED", "reason": "future evaluation label referenced", "created_at": "2026-07-29T10:00:00+08:00"}],
            }
        },
        "promotion_policy": {
            "policy_id": "promotion-policy",
            "policy_version": "v1",
            "required_run_types": ["HISTORICAL_REPLAY", "OUT_OF_SAMPLE", "ROBUSTNESS", "SHADOW", "PAPER_CHALLENGER"],
            "minimum_sample_rules": {"historical_samples": 100, "out_of_sample_samples": 50, "paired_samples": 30, "shadow_trade_days": 5, "challenger_trade_days": 20},
            "require_leakage_pass": True,
            "require_robustness_pass": True,
            "require_shadow": True,
            "require_paper_challenger": True,
            "require_top_risk_review": True,
            "require_human_approval": True,
            "immutable_hash": _hash("demo-promotion-policy-v1"),
        },
    }
    canonical = json.dumps(fixture, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    fixture["fixture_hash"] = _hash(canonical)
    return fixture


def clone_demo_fixture() -> dict[str, Any]:
    return deepcopy(build_demo_fixture())
