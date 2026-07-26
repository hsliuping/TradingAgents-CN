"""Declarative MongoDB index plan for AlphaGuard PR-003 and PR-004."""

from __future__ import annotations


ALPHAGUARD_INDEX_SPECS = {
    "ag_candidates": [
        {"keys": [("candidate_id", 1)], "name": "uniq_candidate_id", "unique": True},
        {
            "keys": [("user_id", 1), ("market", 1), ("symbol", 1)],
            "name": "uniq_user_market_symbol",
            "unique": True,
        },
        {"keys": [("status", 1), ("next_scan_at", 1)], "name": "idx_status_next_scan"},
        {"keys": [("user_id", 1), ("status", 1)], "name": "idx_user_status"},
        {"keys": [("sources", 1)], "name": "idx_sources"},
    ],
    "ag_candidate_events": [
        {
            "keys": [("event_id", 1)],
            "name": "uniq_candidate_event_id",
            "unique": True,
        },
        {
            "keys": [("candidate_id", 1), ("created_at", -1)],
            "name": "idx_candidate_created",
        },
        {"keys": [("user_id", 1), ("created_at", -1)], "name": "idx_user_created"},
    ],
    "ag_evidence_snapshots": [
        {"keys": [("snapshot_id", 1)], "name": "uniq_snapshot_id", "unique": True},
        {
            "keys": [("user_id", 1), ("symbol", 1), ("trade_date", -1)],
            "name": "idx_user_symbol_trade_date",
        },
        {
            "keys": [("symbol", 1), ("market", 1), ("trade_date", -1)],
            "name": "idx_symbol_market_trade_date",
        },
        {"keys": [("immutable_hash", 1)], "name": "idx_immutable_hash"},
    ],
    "ag_data_quality_reports": [
        {
            "keys": [("quality_report_id", 1)],
            "name": "uniq_quality_report_id",
            "unique": True,
        },
        {
            "keys": [("symbol", 1), ("market", 1), ("trade_date", -1)],
            "name": "idx_quality_symbol_market_trade_date",
        },
        {
            "keys": [("status", 1), ("checked_at", -1)],
            "name": "idx_quality_status_checked",
        },
    ],
    "ag_factor_definitions": [
        {
            "keys": [("factor_id", 1), ("factor_version", 1)],
            "name": "uniq_factor_version",
            "unique": True,
        },
        {"keys": [("group", 1), ("status", 1)], "name": "idx_factor_group_status"},
    ],
    "ag_factor_results": [
        {
            "keys": [
                ("snapshot_id", 1),
                ("factor_id", 1),
                ("factor_version", 1),
            ],
            "name": "uniq_snapshot_factor_version",
            "unique": True,
        },
        {"keys": [("snapshot_id", 1), ("group", 1)], "name": "idx_snapshot_group"},
        {"keys": [("input_hash", 1)], "name": "idx_factor_input_hash"},
        {
            "keys": [("symbol", 1), ("market", 1), ("trade_date", -1)],
            "name": "idx_factor_symbol_market_date",
        },
    ],
    "ag_regime_results": [
        {
            "keys": [("snapshot_id", 1), ("regime_version", 1)],
            "name": "uniq_snapshot_regime_version",
            "unique": True,
        },
        {"keys": [("regime", 1), ("trade_date", -1)], "name": "idx_regime_date"},
        {
            "keys": [("trade_date", -1), ("regime", 1)],
            "name": "idx_regime_trade_date",
        },
        {
            "keys": [("calculation_status", 1), ("trade_date", -1)],
            "name": "idx_regime_status_date",
        },
    ],
    "ag_strategy_definitions": [
        {
            "keys": [("strategy_id", 1), ("strategy_version", 1)],
            "name": "uniq_strategy_version",
            "unique": True,
        },
        {"keys": [("status", 1), ("strategy_id", 1)], "name": "idx_strategy_status"},
        {
            "keys": [("status", 1), ("supported_markets", 1)],
            "name": "idx_strategy_status_markets",
        },
    ],
    "ag_quant_proposals": [
        {
            "keys": [
                ("snapshot_id", 1),
                ("strategy_id", 1),
                ("strategy_version", 1),
            ],
            "name": "uniq_snapshot_strategy_version",
            "unique": True,
        },
        {"keys": [("proposal_id", 1)], "name": "uniq_proposal_id", "unique": True},
        {
            "keys": [("user_id", 1), ("trade_date", -1)],
            "name": "idx_proposal_user_date",
        },
        {
            "keys": [("candidate_id", 1), ("trade_date", -1)],
            "name": "idx_proposal_candidate_date",
        },
        {
            "keys": [("candidate_id", 1), ("created_at", -1)],
            "name": "idx_proposal_candidate_created",
        },
        {
            "keys": [("status", 1), ("created_at", -1)],
            "name": "idx_proposal_status_created",
        },
        {
            "keys": [("strategy_id", 1), ("trade_date", -1)],
            "name": "idx_proposal_strategy_date",
        },
    ],
    "ag_market_contexts": [
        {"keys": [("context_id", 1)], "name": "uniq_market_context_id", "unique": True},
        {
            "keys": [("market", 1), ("trade_date", -1)],
            "name": "idx_market_context_date",
        },
    ],
    "ag_quant_audit_events": [
        {"keys": [("event_id", 1)], "name": "uniq_quant_event_id", "unique": True},
        {
            "keys": [("snapshot_id", 1), ("created_at", -1)],
            "name": "idx_quant_event_snapshot_time",
        },
        {
            "keys": [("event_type", 1), ("created_at", -1)],
            "name": "idx_quant_event_type_time",
        },
    ],
    "ag_decision_contexts": [
        {
            "keys": [("decision_context_id", 1)],
            "name": "uniq_decision_context_id",
            "unique": True,
        },
        {
            "keys": [("analysis_id", 1)],
            "name": "uniq_decision_context_analysis",
            "unique": True,
        },
        {
            "keys": [("snapshot_id", 1), ("quant_proposal_id", 1)],
            "name": "idx_context_snapshot_proposal",
        },
        {"keys": [("context_hash", 1)], "name": "idx_context_hash"},
    ],
    "ag_consensus_decisions": [
        {
            "keys": [("consensus_id", 1)],
            "name": "uniq_consensus_id",
            "unique": True,
        },
        {
            "keys": [("analysis_id", 1)],
            "name": "uniq_consensus_analysis",
            "unique": True,
        },
        {
            "keys": [("snapshot_id", 1), ("created_at", -1)],
            "name": "idx_consensus_snapshot_created",
        },
        {
            "keys": [("status", 1), ("created_at", -1)],
            "name": "idx_consensus_status_created",
        },
    ],
    "ag_risk_policies": [
        {
            "keys": [("risk_policy_id", 1), ("version", 1)],
            "name": "uniq_risk_policy_version",
            "unique": True,
        },
        {"keys": [("status", 1)], "name": "idx_risk_policy_status"},
    ],
    "ag_risk_decisions": [
        {
            "keys": [("risk_decision_id", 1)],
            "name": "uniq_risk_decision_id",
            "unique": True,
        },
        {
            "keys": [("consensus_id", 1)],
            "name": "uniq_risk_consensus",
            "unique": True,
        },
        {
            "keys": [("snapshot_id", 1), ("created_at", -1)],
            "name": "idx_risk_snapshot_created",
        },
        {
            "keys": [("status", 1), ("created_at", -1)],
            "name": "idx_risk_status_created",
        },
        {
            "keys": [("account_id", 1), ("created_at", -1)],
            "name": "idx_risk_account_created",
        },
    ],
    "ag_decision_events": [
        {
            "keys": [("analysis_id", 1), ("created_at", -1)],
            "name": "idx_decision_event_analysis_created",
        },
        {
            "keys": [("snapshot_id", 1), ("created_at", -1)],
            "name": "idx_decision_event_snapshot_created",
        },
        {
            "keys": [("event_type", 1), ("created_at", -1)],
            "name": "idx_decision_event_type_created",
        },
    ],
    "ag_revision_requests": [
        {
            "keys": [("revision_request_id", 1)],
            "name": "uniq_revision_request_id",
            "unique": True,
        },
        {
            "keys": [("analysis_id", 1), ("revision_round", 1)],
            "name": "idx_revision_analysis_round",
        },
    ],
    "ag_decision_runs": [
        {
            "keys": [("decision_run_key", 1), ("attempt_number", 1)],
            "name": "uniq_decision_run_attempt",
            "unique": True,
        },
        {
            "keys": [("terminal_status", 1), ("updated_at", -1)],
            "name": "idx_decision_run_terminal",
        },
    ],
}
