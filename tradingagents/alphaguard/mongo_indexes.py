"""Declarative create-only MongoDB index plan for AlphaGuard."""

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
    "ag_candidate_recommendation_policies": [
        {
            "keys": [("policy_id", 1), ("policy_version", 1)],
            "name": "uniq_candidate_recommendation_policy",
            "unique": True,
        },
        {"keys": [("config_hash", 1)], "name": "idx_candidate_recommendation_policy_hash"},
    ],
    "ag_candidate_universe_manifests": [
        {"keys": [("manifest_id", 1)], "name": "uniq_candidate_universe_manifest", "unique": True},
        {
            "keys": [("market", 1), ("universe_date", 1), ("universe_version", 1)],
            "name": "uniq_candidate_universe_version",
            "unique": True,
        },
        {"keys": [("universe_hash", 1)], "name": "idx_candidate_universe_hash"},
    ],
    "ag_candidate_eligibility_results": [
        {
            "keys": [("eligibility_result_id", 1)],
            "name": "uniq_candidate_eligibility_result",
            "unique": True,
        },
        {
            "keys": [("recommendation_run_id", 1), ("symbol", 1)],
            "name": "uniq_candidate_run_symbol_eligibility",
            "unique": True,
        },
        {"keys": [("trade_date", -1), ("eligible", 1)], "name": "idx_candidate_eligibility_date"},
    ],
    "ag_candidate_recommendation_runs": [
        {
            "keys": [("recommendation_run_id", 1)],
            "name": "uniq_candidate_recommendation_run",
            "unique": True,
        },
        {
            "keys": [("user_id", 1), ("trade_date", -1), ("completed_at", -1)],
            "name": "idx_candidate_recommendation_run_user_date",
        },
        {"keys": [("input_hash", 1)], "name": "idx_candidate_recommendation_run_input"},
    ],
    "ag_candidate_recommendations": [
        {"keys": [("recommendation_id", 1)], "name": "uniq_candidate_recommendation", "unique": True},
        {
            "keys": [("user_id", 1), ("trade_date", -1), ("recommendation_score", -1)],
            "name": "idx_candidate_recommendation_user_date_score",
        },
        {
            "keys": [("recommendation_run_id", 1), ("symbol", 1)],
            "name": "uniq_candidate_recommendation_run_symbol",
            "unique": True,
        },
        {"keys": [("expires_at", 1)], "name": "idx_candidate_recommendation_expiry"},
    ],
    "ag_candidate_recommendation_review_events": [
        {
            "keys": [("review_event_id", 1)],
            "name": "uniq_candidate_recommendation_review_event",
            "unique": True,
        },
        {
            "keys": [("recommendation_id", 1)],
            "name": "uniq_candidate_recommendation_terminal_review",
            "unique": True,
        },
        {"keys": [("user_id", 1), ("created_at", -1)], "name": "idx_candidate_review_user_time"},
    ],
    "ag_candidate_recommendation_evaluations": [
        {"keys": [("evaluation_id", 1)], "name": "uniq_candidate_recommendation_evaluation", "unique": True},
        {
            "keys": [("recommendation_id", 1)],
            "name": "uniq_candidate_recommendation_evaluation_source",
            "unique": True,
        },
        {"keys": [("status", 1), ("trade_date", 1)], "name": "idx_candidate_recommendation_evaluation_maturity"},
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
            "keys": [("ref_id", 1)],
            "name": "uniq_market_context_ref",
            "unique": True,
            "sparse": True,
        },
        {
            "keys": [("market", 1), ("trade_date", 1), ("data_version", 1)],
            "name": "uniq_market_context_version",
            "unique": True,
        },
        {
            "keys": [("market", 1), ("trade_date", -1)],
            "name": "idx_market_context_date",
        },
        {
            "keys": [("calculation_status", 1), ("trade_date", -1)],
            "name": "idx_market_context_status_date",
        },
    ],
    "ag_market_context_window_manifests": [
        {
            "keys": [("manifest_id", 1)],
            "name": "uniq_market_context_window_manifest",
            "unique": True,
        },
        {
            "keys": [("market", 1), ("as_of_trade_date", 1)],
            "name": "uniq_market_context_window_as_of",
            "unique": True,
        },
        {
            "keys": [("manifest_hash", 1)],
            "name": "idx_market_context_window_hash",
        },
    ],
    "ag_benchmark_price_window_manifests": [
        {
            "keys": [("manifest_id", 1)],
            "name": "uniq_benchmark_price_window_manifest",
            "unique": True,
        },
        {
            "keys": [
                ("market", 1),
                ("benchmark_symbol", 1),
                ("as_of_trade_date", 1),
                ("required_count", 1),
            ],
            "name": "uniq_benchmark_price_window_as_of",
            "unique": True,
        },
        {
            "keys": [("manifest_hash", 1)],
            "name": "idx_benchmark_price_window_hash",
        },
    ],
    "ag_decision_evidence_pack_manifests": [
        {
            "keys": [("manifest_id", 1)],
            "name": "uniq_decision_evidence_pack_manifest",
            "unique": True,
        },
        {
            "keys": [
                ("source_snapshot_id", 1),
                ("symbol", 1),
                ("source_trade_date", 1),
                ("schema_version", 1),
                ("calculation_version", 1),
            ],
            "name": "uniq_decision_evidence_pack_source",
            "unique": True,
        },
        {
            "keys": [("manifest_hash", 1)],
            "name": "idx_decision_evidence_pack_hash",
        },
    ],
    "stock_corporate_actions": [
        {
            "keys": [("ref_id", 1)],
            "name": "uniq_stock_corporate_action_ref",
            "unique": True,
        },
        {
            "keys": [("symbol", 1), ("published_at", -1)],
            "name": "idx_stock_corporate_action_symbol_time",
        },
    ],
    "ag_security_master_sources": [
        {
            "keys": [("source_id", 1)],
            "name": "uniq_security_master_source_id",
            "unique": True,
        },
        {
            "keys": [
                ("symbol", 1),
                ("market", 1),
                ("provider", 1),
                ("data_version", 1),
            ],
            "name": "uniq_security_master_source_version",
            "unique": True,
        },
        {
            "keys": [("symbol", 1), ("collected_at", -1)],
            "name": "idx_security_master_source_symbol",
        },
    ],
    "ag_market_context_sources": [
        {
            "keys": [("source_id", 1)],
            "name": "uniq_market_context_source_id",
            "unique": True,
        },
        {
            "keys": [
                ("market", 1),
                ("trade_date", 1),
                ("provider", 1),
                ("provider_version", 1),
                ("normalization_version", 1),
            ],
            "name": "uniq_market_context_source_version",
            "unique": True,
        },
        {
            "keys": [("content_hash", 1)],
            "name": "idx_market_context_source_hash",
        },
    ],
    "ag_security_trading_statuses": [
        {
            "keys": [("trading_status_id", 1)],
            "name": "uniq_security_trading_status_id",
            "unique": True,
        },
        {
            "keys": [("ref_id", 1)],
            "name": "uniq_security_trading_status_ref",
            "unique": True,
        },
        {
            "keys": [
                ("symbol", 1),
                ("market", 1),
                ("trade_date", 1),
                ("data_version", 1),
            ],
            "name": "uniq_security_trading_status_version",
            "unique": True,
        },
        {
            "keys": [
                ("symbol", 1),
                ("market", 1),
                ("trade_date", -1),
                ("calculation_status", 1),
            ],
            "name": "idx_security_trading_status_lookup",
        },
    ],
    "ag_production_data_events": [
        {
            "keys": [("event_id", 1)],
            "name": "uniq_production_data_event",
            "unique": True,
        },
        {
            "keys": [("event_type", 1), ("created_at", -1)],
            "name": "idx_production_data_event_type",
        },
        {
            "keys": [("symbol", 1), ("trade_date", -1)],
            "name": "idx_production_data_event_symbol_date",
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
    "ag_paper_accounts": [
        {
            "keys": [("user_id", 1), ("account_type", 1), ("market", 1)],
            "name": "uniq_paper_user_type_market",
            "unique": True,
        },
        {"keys": [("account_id", 1)], "name": "uniq_paper_account_id", "unique": True},
        {
            "keys": [("status", 1), ("account_type", 1)],
            "name": "idx_paper_account_status_type",
        },
    ],
    "ag_benchmark_execution_decisions": [
        {
            "keys": [("benchmark_decision_id", 1)],
            "name": "uniq_benchmark_decision_id",
            "unique": True,
        },
        {
            "keys": [("source_type", 1), ("source_object_id", 1), ("account_id", 1)],
            "name": "uniq_benchmark_source_account",
            "unique": True,
        },
    ],
    "ag_order_intents": [
        {"keys": [("intent_id", 1)], "name": "uniq_intent_id", "unique": True},
        {
            "keys": [("idempotency_key", 1)],
            "name": "uniq_intent_idempotency",
            "unique": True,
        },
        {
            "keys": [("account_id", 1), ("created_at", -1)],
            "name": "idx_intent_account_created",
        },
        {
            "keys": [("source_object_id", 1), ("source_type", 1)],
            "name": "idx_intent_source",
        },
        {
            "keys": [("experiment_id", 1), ("challenger_version_id", 1), ("created_at", -1)],
            "name": "idx_intent_challenger_lineage",
        },
    ],
    "ag_paper_orders": [
        {"keys": [("order_id", 1)], "name": "uniq_paper_order_id", "unique": True},
        {"keys": [("intent_id", 1)], "name": "uniq_paper_order_intent", "unique": True},
        {
            "keys": [("account_id", 1), ("status", 1), ("created_at", -1)],
            "name": "idx_paper_order_account_status",
        },
        {
            "keys": [("status", 1), ("earliest_execute_at", 1)],
            "name": "idx_paper_order_status_earliest",
        },
        {
            "keys": [("symbol", 1), ("trade_date", -1)],
            "name": "idx_paper_order_symbol_date",
        },
        {
            "keys": [("experiment_id", 1), ("challenger_version_id", 1), ("created_at", -1)],
            "name": "idx_paper_order_challenger_lineage",
        },
    ],
    "ag_paper_fills": [
        {"keys": [("fill_id", 1)], "name": "uniq_paper_fill_id", "unique": True},
        {
            "keys": [("idempotency_key", 1)],
            "name": "uniq_paper_fill_idempotency",
            "unique": True,
        },
        {
            "keys": [("order_id", 1), ("trade_date", 1)],
            "name": "uniq_paper_fill_order_date",
            "unique": True,
        },
        {
            "keys": [("account_id", 1), ("trade_date", -1)],
            "name": "idx_paper_fill_account_date",
        },
        {
            "keys": [("experiment_id", 1), ("challenger_version_id", 1), ("trade_date", -1)],
            "name": "idx_paper_fill_challenger_lineage",
        },
    ],
    "ag_paper_positions": [
        {
            "keys": [("account_id", 1), ("market", 1), ("symbol", 1)],
            "name": "uniq_paper_position",
            "unique": True,
        },
        {
            "keys": [("account_id", 1), ("quantity", 1)],
            "name": "idx_paper_position_quantity",
        },
        {
            "keys": [("experiment_id", 1), ("challenger_version_id", 1), ("account_id", 1)],
            "name": "idx_paper_position_challenger_lineage",
        },
    ],
    "ag_paper_position_lots": [
        {"keys": [("lot_id", 1)], "name": "uniq_paper_lot_id", "unique": True},
        {
            "keys": [("source_fill_id", 1)],
            "name": "uniq_paper_lot_fill",
            "unique": True,
        },
        {
            "keys": [("account_id", 1), ("symbol", 1), ("available_from_date", 1)],
            "name": "idx_paper_lot_availability",
        },
        {
            "keys": [("account_id", 1), ("status", 1)],
            "name": "idx_paper_lot_status",
        },
    ],
    "ag_paper_reservations": [
        {
            "keys": [("reservation_id", 1)],
            "name": "uniq_paper_reservation_id",
            "unique": True,
        },
        {
            "keys": [("idempotency_key", 1)],
            "name": "uniq_paper_reservation_idempotency",
            "unique": True,
        },
        {
            "keys": [("order_id", 1), ("status", 1)],
            "name": "idx_paper_reservation_order_status",
        },
    ],
    "ag_execution_market_snapshots": [
        {
            "keys": [("execution_snapshot_id", 1)],
            "name": "uniq_execution_snapshot_id",
            "unique": True,
        },
        {
            "keys": [("symbol", 1), ("market", 1), ("trade_date", 1), ("data_version", 1)],
            "name": "uniq_execution_symbol_date_version",
            "unique": True,
        },
        {
            "keys": [("trade_date", -1), ("market", 1)],
            "name": "idx_execution_snapshot_date_market",
        },
    ],
    "ag_settlement_records": [
        {
            "keys": [("settlement_id", 1)],
            "name": "uniq_settlement_id",
            "unique": True,
        },
        {"keys": [("fill_id", 1)], "name": "uniq_settlement_fill", "unique": True},
        {
            "keys": [("status", 1), ("updated_at", 1)],
            "name": "idx_settlement_status_updated",
        },
        {
            "keys": [("experiment_id", 1), ("challenger_version_id", 1), ("created_at", -1)],
            "name": "idx_settlement_challenger_lineage",
        },
    ],
    "ag_paper_ledger_entries": [
        {
            "keys": [("ledger_entry_id", 1)],
            "name": "uniq_paper_ledger_id",
            "unique": True,
        },
        {
            "keys": [("idempotency_key", 1)],
            "name": "uniq_paper_ledger_idempotency",
            "unique": True,
        },
        {
            "keys": [("account_id", 1), ("created_at", -1)],
            "name": "idx_paper_ledger_account_created",
        },
        {
            "keys": [("experiment_id", 1), ("challenger_version_id", 1), ("created_at", -1)],
            "name": "idx_paper_ledger_challenger_lineage",
        },
    ],
    "ag_execution_outbox": [
        {
            "keys": [("outbox_event_id", 1)],
            "name": "uniq_execution_outbox_event_id",
            "unique": True,
        },
        {
            "keys": [("idempotency_key", 1)],
            "name": "uniq_execution_outbox_idempotency",
            "unique": True,
        },
        {
            "keys": [("status", 1), ("next_attempt_at", 1)],
            "name": "idx_execution_outbox_status_next",
        },
        {
            "keys": [("experiment_id", 1), ("challenger_version_id", 1), ("created_at", -1)],
            "name": "idx_execution_outbox_challenger_lineage",
        },
    ],
    "ag_paper_account_snapshots": [
        {
            "keys": [("account_id", 1), ("trade_date", 1)],
            "name": "uniq_paper_account_snapshot",
            "unique": True,
        },
        {
            "keys": [("trade_date", -1), ("account_id", 1)],
            "name": "idx_paper_account_snapshot_date",
        },
    ],
    "ag_paper_job_runs": [
        {
            "keys": [("idempotency_key", 1)],
            "name": "uniq_paper_job_idempotency",
            "unique": True,
        },
        {
            "keys": [("job_type", 1), ("trade_date", -1)],
            "name": "idx_paper_job_type_date",
        },
        {
            "keys": [("status", 1), ("created_at", -1)],
            "name": "idx_paper_job_status_created",
        },
    ],
    "ag_paper_events": [
        {
            "keys": [("event_id", 1)],
            "name": "uniq_paper_event_id",
            "unique": True,
        },
        {
            "keys": [("account_id", 1), ("created_at", -1)],
            "name": "idx_paper_event_account_created",
        },
        {
            "keys": [("order_id", 1), ("created_at", -1)],
            "name": "idx_paper_event_order_created",
        },
        {
            "keys": [("event_type", 1), ("created_at", -1)],
            "name": "idx_paper_event_type_created",
        },
    ],
    "ag_paper_policies": [
        {
            "keys": [("policy_type", 1), ("version", 1)],
            "name": "uniq_paper_policy_version",
            "unique": True,
        },
    ],
    "ag_eval_subjects": [
        {
            "keys": [
                ("subject_type", 1),
                ("source_object_id", 1),
                ("evaluation_version", 1),
            ],
            "name": "uniq_eval_subject_source_version",
            "unique": True,
        },
        {"keys": [("subject_id", 1)], "name": "uniq_eval_subject_id", "unique": True},
        {
            "keys": [("user_id", 1), ("decision_trade_date", -1)],
            "name": "idx_eval_subject_user_date",
        },
        {
            "keys": [("snapshot_id", 1), ("decision_stage", 1)],
            "name": "idx_eval_subject_snapshot_stage",
        },
        {
            "keys": [("symbol", 1), ("market", 1), ("decision_trade_date", -1)],
            "name": "idx_eval_subject_symbol_date",
        },
        {
            "keys": [("decision_stage", 1), ("decision_status", 1)],
            "name": "idx_eval_subject_stage_status",
        },
    ],
    "ag_eval_horizon_labels": [
        {
            "keys": [
                ("subject_id", 1),
                ("horizon", 1),
                ("anchor_type", 1),
                ("calculation_version", 1),
            ],
            "name": "uniq_eval_label_subject_horizon",
            "unique": True,
        },
        {"keys": [("label_id", 1)], "name": "uniq_eval_label_id", "unique": True},
        {
            "keys": [("status", 1), ("horizon_end_date", 1)],
            "name": "idx_eval_label_status_maturity",
        },
        {
            "keys": [("horizon", 1), ("calculated_at", -1)],
            "name": "idx_eval_label_horizon_calculated",
        },
    ],
    "ag_eval_counterfactuals": [
        {
            "keys": [
                ("subject_id", 1),
                ("mode", 1),
                ("execution_rule_version", 1),
            ],
            "name": "uniq_eval_counterfactual_subject_mode",
            "unique": True,
        },
        {
            "keys": [("counterfactual_id", 1)],
            "name": "uniq_eval_counterfactual_id",
            "unique": True,
        },
        {
            "keys": [("status", 1), ("created_at", -1)],
            "name": "idx_eval_counterfactual_status",
        },
    ],
    "ag_eval_account_metrics": [
        {
            "keys": [
                ("account_id", 1),
                ("period_start", 1),
                ("period_end", 1),
                ("metric_version", 1),
            ],
            "name": "uniq_eval_account_metric_period",
            "unique": True,
        },
        {
            "keys": [("account_type", 1), ("period_end", -1)],
            "name": "idx_eval_account_type_period",
        },
        {
            "keys": [("status", 1), ("period_end", -1)],
            "name": "idx_eval_account_status_period",
        },
    ],
    "ag_eval_paired_comparisons": [
        {
            "keys": [
                ("comparison_type", 1),
                ("left_subject_id", 1),
                ("right_subject_id", 1),
                ("comparison_version", 1),
            ],
            "name": "uniq_eval_paired_subjects",
            "unique": True,
        },
        {
            "keys": [("snapshot_id", 1), ("comparison_type", 1)],
            "name": "idx_eval_paired_snapshot_type",
        },
        {
            "keys": [("pairing_status", 1), ("calculated_at", -1)],
            "name": "idx_eval_paired_status",
        },
    ],
    "ag_eval_attributions": [
        {
            "keys": [("subject_id", 1), ("attribution_rule_version", 1)],
            "name": "uniq_eval_attribution_subject_version",
            "unique": True,
        },
        {
            "keys": [("attribution_id", 1)],
            "name": "uniq_eval_attribution_id",
            "unique": True,
        },
        {
            "keys": [("primary_category", 1), ("calculated_at", -1)],
            "name": "idx_eval_attribution_category",
        },
        {
            "keys": [("outcome_class", 1), ("calculated_at", -1)],
            "name": "idx_eval_attribution_outcome",
        },
        {
            "keys": [("status", 1), ("calculated_at", -1)],
            "name": "idx_eval_attribution_status",
        },
    ],
    "ag_eval_attribution_overrides": [
        {
            "keys": [("override_id", 1)],
            "name": "uniq_eval_override_id",
            "unique": True,
        },
        {
            "keys": [("attribution_id", 1), ("created_at", -1)],
            "name": "idx_eval_override_attribution",
        },
        {
            "keys": [("user_id", 1), ("created_at", -1)],
            "name": "idx_eval_override_user",
        },
    ],
    "ag_eval_runs": [
        {
            "keys": [("idempotency_key", 1)],
            "name": "uniq_eval_run_idempotency",
            "unique": True,
        },
        {
            "keys": [("status", 1), ("as_of_trade_date", -1)],
            "name": "idx_eval_run_status_date",
        },
        {"keys": [("started_at", -1)], "name": "idx_eval_run_started"},
    ],
    "ag_eval_events": [
        {"keys": [("event_id", 1)], "name": "uniq_eval_event_id", "unique": True},
        {
            "keys": [("subject_id", 1), ("created_at", -1)],
            "name": "idx_eval_event_subject",
        },
        {
            "keys": [("evaluation_job_id", 1), ("created_at", -1)],
            "name": "idx_eval_event_job",
        },
        {
            "keys": [("event_type", 1), ("created_at", -1)],
            "name": "idx_eval_event_type",
        },
    ],
    "ag_eval_factor_metrics": [
        {"keys": [("metric_id", 1)], "name": "uniq_eval_factor_metric", "unique": True},
        {"keys": [("scope_user_id", 1), ("group_key", 1), ("period_end", -1)], "name": "idx_eval_factor_period"},
    ],
    "ag_eval_regime_metrics": [
        {"keys": [("metric_id", 1)], "name": "uniq_eval_regime_metric", "unique": True},
        {"keys": [("scope_user_id", 1), ("group_key", 1), ("period_end", -1)], "name": "idx_eval_regime_period"},
    ],
    "ag_eval_strategy_metrics": [
        {"keys": [("metric_id", 1)], "name": "uniq_eval_strategy_metric", "unique": True},
        {"keys": [("scope_user_id", 1), ("group_key", 1), ("period_end", -1)], "name": "idx_eval_strategy_period"},
    ],
    "ag_eval_execution_metrics": [
        {"keys": [("metric_id", 1)], "name": "uniq_eval_execution_metric", "unique": True},
        {
            "keys": [("scope_user_id", 1), ("module_type", 1), ("group_key", 1), ("period_end", -1)],
            "name": "idx_eval_execution_group_period",
        },
    ],
    # PR-008 experiment collections are create-only and never share identity
    # with production research, decision, evaluation, or paper-trading facts.
    "ag_exp_component_versions": [
        {"keys": [("version_ref", 1)], "name": "uniq_exp_component_version", "unique": True},
        {
            "keys": [("component_type", 1), ("component_key", 1), ("market", 1)],
            "name": "idx_exp_component_identity",
        },
        {"keys": [("payload_hash", 1)], "name": "idx_exp_component_hash"},
    ],
    "ag_exp_definitions": [
        {"keys": [("experiment_id", 1)], "name": "uniq_experiment_id", "unique": True},
        {"keys": [("user_id", 1), ("status", 1)], "name": "idx_exp_user_status"},
        {
            "keys": [("component_type", 1), ("component_key", 1), ("market", 1)],
            "name": "idx_exp_component_slot",
        },
        {"keys": [("status", 1), ("created_at", -1)], "name": "idx_exp_status_created"},
    ],
    "ag_exp_variable_changes": [
        {"keys": [("change_id", 1)], "name": "uniq_exp_change_id", "unique": True},
        {
            "keys": [("experiment_id", 1), ("variable_path", 1)],
            "name": "uniq_exp_change_path",
            "unique": True,
        },
        {"keys": [("experiment_id", 1), ("is_primary", 1)], "name": "idx_exp_primary_change"},
    ],
    "ag_exp_dataset_manifests": [
        {"keys": [("dataset_manifest_id", 1)], "name": "uniq_exp_manifest_id", "unique": True},
        {"keys": [("manifest_hash", 1)], "name": "uniq_exp_manifest_hash", "unique": True},
        {
            "keys": [("experiment_id", 1), ("start_trade_date", 1), ("end_trade_date", 1)],
            "name": "idx_exp_manifest_range",
        },
    ],
    "ag_exp_time_splits": [
        {"keys": [("split_id", 1)], "name": "uniq_exp_split_id", "unique": True},
        {
            "keys": [("dataset_manifest_id", 1), ("method", 1), ("fold_number", 1)],
            "name": "uniq_exp_manifest_fold",
            "unique": True,
        },
    ],
    "ag_exp_runs": [
        {"keys": [("run_id", 1)], "name": "uniq_exp_run_id", "unique": True},
        {
            "keys": [
                ("experiment_id", 1),
                ("run_type", 1),
                ("dataset_manifest_id", 1),
                ("split_id", 1),
                ("input_hash", 1),
            ],
            "name": "uniq_exp_run_input",
            "unique": True,
        },
        {"keys": [("status", 1), ("created_at", -1)], "name": "idx_exp_run_status"},
        {"keys": [("experiment_id", 1), ("run_type", 1)], "name": "idx_exp_run_type"},
    ],
    "ag_exp_run_results": [
        {"keys": [("result_id", 1)], "name": "uniq_exp_result_id", "unique": True},
        {"keys": [("run_id", 1)], "name": "uniq_exp_result_run", "unique": True},
        {"keys": [("experiment_id", 1), ("calculated_at", -1)], "name": "idx_exp_result_experiment"},
    ],
    "ag_exp_leakage_audits": [
        {"keys": [("leakage_audit_id", 1)], "name": "uniq_exp_leakage_id", "unique": True},
        {"keys": [("run_id", 1)], "name": "uniq_exp_leakage_run", "unique": True},
        {"keys": [("status", 1), ("created_at", -1)], "name": "idx_exp_leakage_status"},
    ],
    "ag_exp_robustness_reports": [
        {"keys": [("robustness_report_id", 1)], "name": "uniq_exp_robustness_id", "unique": True},
        {"keys": [("run_id", 1)], "name": "uniq_exp_robustness_run", "unique": True},
        {"keys": [("status", 1), ("created_at", -1)], "name": "idx_exp_robustness_status"},
    ],
    "ag_exp_shadow_runs": [
        {"keys": [("shadow_run_id", 1)], "name": "uniq_exp_shadow_run", "unique": True},
        {"keys": [("experiment_id", 1), ("status", 1)], "name": "idx_exp_shadow_status"},
    ],
    "ag_exp_shadow_outputs": [
        {"keys": [("output_id", 1)], "name": "uniq_exp_shadow_output", "unique": True},
        {
            "keys": [("experiment_id", 1), ("run_id", 1), ("snapshot_id", 1)],
            "name": "uniq_exp_shadow_opportunity",
            "unique": True,
        },
        {"keys": [("run_id", 1), ("trade_date", 1)], "name": "idx_exp_shadow_date"},
    ],
    "ag_exp_challenger_assignments": [
        {"keys": [("assignment_id", 1)], "name": "uniq_exp_challenger_assignment", "unique": True},
        {"keys": [("experiment_id", 1), ("status", 1)], "name": "idx_exp_challenger_status"},
        {"keys": [("account_id", 1), ("activation_trade_date", 1)], "name": "idx_exp_challenger_account"},
        {"keys": [("exclusivity_key", 1), ("status", 1)], "name": "idx_exp_challenger_exclusivity"},
    ],
    "ag_exp_challenger_runs": [
        {"keys": [("run_id", 1)], "name": "uniq_exp_challenger_run", "unique": True},
        {"keys": [("task_identity", 1)], "name": "uniq_exp_challenger_task", "unique": True},
        {
            "keys": [
                ("experiment_id", 1),
                ("challenger_version_id", 1),
                ("trading_date", 1),
                ("candidate_id", 1),
            ],
            "name": "idx_exp_challenger_run_identity",
        },
        {"keys": [("status", 1), ("updated_at", -1)], "name": "idx_exp_challenger_run_status"},
    ],
    "ag_exp_challenger_objects": [
        {"keys": [("record_id", 1)], "name": "uniq_exp_challenger_object", "unique": True},
        {
            "keys": [
                ("experiment_id", 1),
                ("challenger_version_id", 1),
                ("run_id", 1),
                ("object_type", 1),
                ("object_id", 1),
            ],
            "name": "uniq_exp_challenger_stage_identity",
            "unique": True,
        },
        {"keys": [("snapshot_id", 1), ("object_type", 1)], "name": "idx_exp_challenger_snapshot_stage"},
    ],
    "ag_exp_comparison_reports": [
        {"keys": [("comparison_report_id", 1)], "name": "uniq_exp_comparison_id", "unique": True},
        {"keys": [("experiment_id", 1), ("report_hash", 1)], "name": "uniq_exp_comparison_hash", "unique": True},
        {"keys": [("status", 1), ("created_at", -1)], "name": "idx_exp_comparison_status"},
    ],
    "ag_exp_risk_reviews": [
        {"keys": [("review_id", 1)], "name": "uniq_exp_risk_review_id", "unique": True},
        {"keys": [("comparison_report_id", 1)], "name": "uniq_exp_risk_review_report", "unique": True},
        {"keys": [("experiment_id", 1), ("created_at", -1)], "name": "idx_exp_risk_review"},
    ],
    "ag_exp_promotion_policies": [
        {
            "keys": [("policy_id", 1), ("policy_version", 1)],
            "name": "uniq_exp_promotion_policy",
            "unique": True,
        },
        {"keys": [("immutable_hash", 1)], "name": "uniq_exp_policy_hash", "unique": True},
    ],
    "ag_exp_promotion_requests": [
        {"keys": [("promotion_request_id", 1)], "name": "uniq_exp_promotion_request", "unique": True},
        {"keys": [("experiment_id", 1), ("status", 1)], "name": "idx_exp_promotion_status"},
    ],
    "ag_exp_promotion_approvals": [
        {"keys": [("approval_id", 1)], "name": "uniq_exp_promotion_approval", "unique": True},
        {"keys": [("promotion_request_id", 1)], "name": "uniq_exp_approval_request", "unique": True},
    ],
    "ag_exp_promotion_sagas": [
        {"keys": [("promotion_saga_id", 1)], "name": "uniq_exp_promotion_saga", "unique": True},
        {"keys": [("promotion_request_id", 1)], "name": "idx_exp_saga_request"},
        {"keys": [("rollback_id", 1)], "name": "idx_exp_saga_rollback"},
        {"keys": [("status", 1), ("created_at", -1)], "name": "idx_exp_saga_status"},
    ],
    "ag_exp_champion_assignments": [
        {"keys": [("champion_slot_id", 1)], "name": "uniq_exp_champion_slot", "unique": True},
        {
            "keys": [("component_type", 1), ("component_key", 1), ("market", 1)],
            "name": "uniq_exp_champion_identity",
            "unique": True,
        },
        {"keys": [("status", 1), ("updated_at", -1)], "name": "idx_exp_champion_status"},
    ],
    "ag_exp_champion_history": [
        {"keys": [("history_id", 1)], "name": "uniq_exp_champion_history", "unique": True},
        {
            "keys": [("champion_slot_id", 1), ("assignment.assignment_version", -1)],
            "name": "idx_exp_champion_history_version",
        },
    ],
    "ag_exp_rollbacks": [
        {"keys": [("rollback_id", 1)], "name": "uniq_exp_rollback_id", "unique": True},
        {"keys": [("champion_slot_id", 1), ("created_at", -1)], "name": "idx_exp_rollback_slot"},
    ],
    "ag_exp_locks": [
        {"keys": [("lock_type", 1), ("created_at", -1)], "name": "idx_exp_lock_type"},
    ],
    "ag_exp_task_runs": [
        {"keys": [("task_run_id", 1)], "name": "uniq_exp_task_run", "unique": True},
        {"keys": [("idempotency_key", 1)], "name": "uniq_exp_task_idempotency", "unique": True},
        {"keys": [("status", 1), ("created_at", 1)], "name": "idx_exp_task_pending"},
        {"keys": [("job_type", 1), ("trade_date", -1)], "name": "idx_exp_task_type_date"},
    ],
    "ag_exp_events": [
        {"keys": [("event_id", 1)], "name": "uniq_exp_event_id", "unique": True},
        {"keys": [("experiment_id", 1), ("created_at", -1)], "name": "idx_exp_event_experiment"},
        {"keys": [("event_type", 1), ("created_at", -1)], "name": "idx_exp_event_type"},
        {"keys": [("champion_slot_id", 1), ("created_at", -1)], "name": "idx_exp_event_champion"},
    ],
    # PR-009 operational facts are append-only or state-controlled and never
    # replace research, decision, paper, evaluation, or experiment facts.
    "ag_ops_alerts": [
        {"keys": [("alert_id", 1)], "name": "uniq_ops_alert_id", "unique": True},
        {"keys": [("status", 1), ("severity", 1), ("last_seen_at", -1)], "name": "idx_ops_alert_status"},
        {"keys": [("code", 1), ("source_object_id", 1)], "name": "idx_ops_alert_fingerprint"},
    ],
    "ag_ops_events": [
        {"keys": [("event_id", 1)], "name": "uniq_ops_event_id", "unique": True},
        {"keys": [("event_type", 1), ("created_at", -1)], "name": "idx_ops_event_type"},
        {"keys": [("alert_id", 1), ("created_at", -1)], "name": "idx_ops_event_alert"},
        {"keys": [("job_request_id", 1), ("created_at", -1)], "name": "idx_ops_event_job"},
    ],
    "ag_ops_check_runs": [
        {"keys": [("check_run_id", 1)], "name": "uniq_ops_check_run", "unique": True},
        {"keys": [("report_hash", 1)], "name": "idx_ops_check_report_hash"},
        {"keys": [("created_at", -1)], "name": "idx_ops_check_created"},
    ],
    "ag_ops_job_requests": [
        {"keys": [("job_request_id", 1)], "name": "uniq_ops_job_request", "unique": True},
        {"keys": [("idempotency_key", 1)], "name": "uniq_ops_job_idempotency", "unique": True},
        {"keys": [("status", 1), ("created_at", 1)], "name": "idx_ops_job_pending"},
        {"keys": [("job_name", 1), ("created_at", -1)], "name": "idx_ops_job_name"},
    ],
    # Historical backfill is a research-only namespace.  These indexes are
    # create-only and intentionally do not touch PR-006 execution/account
    # collections or PR-003 production snapshots/results.
    "ag_research_backfill_runs": [
        {"keys": [("backfill_run_id", 1)], "name": "uniq_research_backfill_run", "unique": True},
        {"keys": [("input_hash", 1)], "name": "uniq_research_backfill_input", "unique": True},
        {"keys": [("status", 1), ("created_at", -1)], "name": "idx_research_backfill_status"},
    ],
    "ag_research_backfill_samples": [
        {"keys": [("sample_id", 1)], "name": "uniq_research_sample", "unique": True},
        {
            "keys": [("backfill_run_id", 1), ("symbol", 1), ("trade_date", 1)],
            "name": "uniq_research_run_symbol_date",
            "unique": True,
        },
        {"keys": [("backfill_run_id", 1), ("status", 1)], "name": "idx_research_sample_status"},
    ],
    "ag_research_coverage": [
        {"keys": [("coverage_id", 1)], "name": "uniq_research_coverage", "unique": True},
        {
            "keys": [("backfill_run_id", 1), ("symbol", 1), ("trade_date", 1)],
            "name": "uniq_research_coverage_sample",
            "unique": True,
        },
        {"keys": [("status", 1), ("trade_date", 1)], "name": "idx_research_coverage_status"},
    ],
    "ag_research_market_context_sources": [
        {"keys": [("source_id", 1)], "name": "uniq_research_market_source", "unique": True},
        {
            "keys": [
                ("market", 1),
                ("trade_date", 1),
                ("provider", 1),
                ("provider_version", 1),
                ("normalization_version", 1),
            ],
            "name": "uniq_research_market_source_identity",
            "unique": True,
        },
        {"keys": [("content_hash", 1)], "name": "idx_research_market_source_hash"},
    ],
    "ag_research_market_contexts": [
        {"keys": [("context_id", 1)], "name": "uniq_research_market_context", "unique": True},
        {
            "keys": [("market", 1), ("trade_date", 1), ("data_version", 1)],
            "name": "uniq_research_market_context_version",
            "unique": True,
        },
        {"keys": [("calculation_status", 1), ("trade_date", 1)], "name": "idx_research_market_context_status"},
    ],
    "ag_research_snapshots": [
        {"keys": [("research_snapshot_id", 1)], "name": "uniq_research_snapshot", "unique": True},
        {"keys": [("sample_id", 1)], "name": "uniq_research_snapshot_sample", "unique": True},
        {"keys": [("backfill_run_id", 1), ("source_trade_date", 1)], "name": "idx_research_snapshot_run_date"},
    ],
    "ag_research_evidence_contract_snapshots": [
        {
            "keys": [("snapshot_id", 1)],
            "name": "uniq_research_evidence_contract_snapshot",
            "unique": True,
        },
        {
            "keys": [
                ("user_id", 1),
                ("symbol", 1),
                ("trade_date", 1),
                ("schema_version", 1),
            ],
            "name": "uniq_research_evidence_contract_identity",
            "unique": True,
        },
        {
            "keys": [("immutable_hash", 1)],
            "name": "idx_research_evidence_contract_hash",
        },
    ],
    "ag_research_evidence_contract_quality": [
        {
            "keys": [("quality_report_id", 1)],
            "name": "uniq_research_evidence_contract_quality",
            "unique": True,
        },
        {
            "keys": [("symbol", 1), ("trade_date", 1)],
            "name": "idx_research_evidence_contract_quality_identity",
        },
    ],
    "ag_research_evidence_contract_factor_results": [
        {
            "keys": [
                ("snapshot_id", 1),
                ("factor_id", 1),
                ("factor_version", 1),
            ],
            "name": "uniq_research_evidence_contract_factor",
            "unique": True,
        },
    ],
    "ag_research_evidence_contract_regime_results": [
        {
            "keys": [("regime_result_id", 1)],
            "name": "uniq_research_evidence_contract_regime",
            "unique": True,
        },
        {
            "keys": [("snapshot_id", 1), ("regime_version", 1)],
            "name": "uniq_research_evidence_contract_regime_identity",
            "unique": True,
        },
    ],
    "ag_research_evidence_contract_proposals": [
        {
            "keys": [("proposal_id", 1)],
            "name": "uniq_research_evidence_contract_proposal",
            "unique": True,
        },
        {
            "keys": [
                ("snapshot_id", 1),
                ("strategy_id", 1),
                ("strategy_version", 1),
            ],
            "name": "uniq_research_evidence_contract_proposal_identity",
            "unique": True,
        },
    ],
    "ag_research_evidence_contract_events": [
        {
            "keys": [("event_id", 1)],
            "name": "uniq_research_evidence_contract_event",
            "unique": True,
        },
        {
            "keys": [("snapshot_id", 1), ("created_at", -1)],
            "name": "idx_research_evidence_contract_event_snapshot",
        },
    ],
    "ag_research_evidence_contract_runs": [
        {
            "keys": [("validation_run_id", 1)],
            "name": "uniq_research_evidence_contract_run",
            "unique": True,
        },
        {
            "keys": [("source_trade_date", 1), ("run_mode", 1)],
            "name": "uniq_research_evidence_contract_run_date",
            "unique": True,
        },
        {
            "keys": [("result_hash", 1)],
            "name": "idx_research_evidence_contract_run_hash",
        },
    ],
    "ag_research_decision_path_validations": [
        {
            "keys": [("validation_id", 1)],
            "name": "uniq_research_decision_path_validation",
            "unique": True,
        },
        {
            "keys": [("backfill_run_id", 1), ("run_mode", 1)],
            "name": "uniq_research_decision_path_run",
            "unique": True,
        },
        {
            "keys": [("result_hash", 1)],
            "name": "idx_research_decision_path_hash",
        },
    ],
    "ag_research_factor_results": [
        {"keys": [("result_id", 1)], "name": "uniq_research_factor_result", "unique": True},
        {"keys": [("backfill_run_id", 1), ("sample_id", 1)], "name": "idx_research_factor_sample"},
    ],
    "ag_research_factor_bundles": [
        {"keys": [("sample_id", 1)], "name": "uniq_research_factor_bundle", "unique": True},
        {"keys": [("backfill_run_id", 1)], "name": "idx_research_factor_bundle_run"},
    ],
    "ag_research_regime_results": [
        {"keys": [("regime_result_id", 1)], "name": "uniq_research_regime_result", "unique": True},
        {"keys": [("sample_id", 1)], "name": "uniq_research_regime_sample", "unique": True},
        {"keys": [("backfill_run_id", 1)], "name": "idx_research_regime_run"},
    ],
    "ag_research_quant_proposals": [
        {"keys": [("proposal_id", 1)], "name": "uniq_research_quant_proposal", "unique": True},
        {"keys": [("backfill_run_id", 1), ("sample_id", 1)], "name": "idx_research_proposal_sample"},
    ],
    "ag_research_execution_snapshots": [
        {"keys": [("execution_snapshot_id", 1)], "name": "uniq_research_execution_snapshot", "unique": True},
        {
            "keys": [("symbol", 1), ("market", 1), ("trade_date", 1), ("data_version", 1)],
            "name": "uniq_research_execution_market_version",
            "unique": True,
        },
    ],
    "ag_research_shadow_executions": [
        {"keys": [("shadow_execution_id", 1)], "name": "uniq_research_shadow_execution", "unique": True},
        {
            "keys": [("backfill_run_id", 1), ("proposal_id", 1)],
            "name": "uniq_research_shadow_proposal",
            "unique": True,
        },
        {"keys": [("status", 1), ("created_at", -1)], "name": "idx_research_shadow_status"},
    ],
    "ag_research_backfill_reports": [
        {"keys": [("report_id", 1)], "name": "uniq_research_backfill_report", "unique": True},
        {"keys": [("backfill_run_id", 1)], "name": "uniq_research_backfill_run_report", "unique": True},
        {"keys": [("status", 1), ("created_at", -1)], "name": "idx_research_backfill_report_status"},
    ],
    "ag_research_backfill_events": [
        {"keys": [("event_id", 1)], "name": "uniq_research_backfill_event", "unique": True},
        {"keys": [("backfill_run_id", 1), ("created_at", -1)], "name": "idx_research_backfill_event_run"},
        {"keys": [("event_type", 1), ("created_at", -1)], "name": "idx_research_backfill_event_type"},
    ],
    "ag_model_profiles": [
        {
            "keys": [("profile_id", 1), ("profile_version", 1)],
            "name": "uniq_model_profile_version",
            "unique": True,
        },
        {"keys": [("role", 1), ("enabled", 1)], "name": "idx_model_profile_role"},
        {"keys": [("config_hash", 1)], "name": "idx_model_profile_hash"},
    ],
    "ag_model_prompt_versions": [
        {
            "keys": [("prompt_id", 1), ("prompt_version", 1)],
            "name": "uniq_model_prompt_version",
            "unique": True,
        },
        {"keys": [("role", 1), ("enabled", 1)], "name": "idx_model_prompt_role"},
        {"keys": [("template_hash", 1)], "name": "idx_model_prompt_hash"},
    ],
    "ag_model_capability_checks": [
        {
            "keys": [("capability_check_id", 1)],
            "name": "uniq_model_capability_check",
            "unique": True,
        },
        {
            "keys": [
                ("profile_id", 1),
                ("profile_version", 1),
                ("checked_at", -1),
            ],
            "name": "idx_model_capability_profile",
        },
        {"keys": [("status", 1), ("checked_at", -1)], "name": "idx_model_capability_status"},
    ],
    "ag_model_contract_checks": [
        {
            "keys": [("contract_check_id", 1)],
            "name": "uniq_model_contract_check",
            "unique": True,
        },
        {
            "keys": [
                ("contract_id", 1),
                ("contract_version", 1),
                ("profile_id", 1),
                ("profile_version", 1),
                ("input_hash", 1),
            ],
            "name": "uniq_model_contract_check_identity",
            "unique": True,
        },
        {"keys": [("status", 1), ("checked_at", -1)], "name": "idx_model_contract_check_status"},
    ],
    "ag_model_runs": [
        {
            "keys": [("model_run_id", 1)],
            "name": "uniq_model_run",
            "unique": True,
        },
        {
            "keys": [
                ("analysis_id", 1),
                ("snapshot_id", 1),
                ("run_mode", 1),
                ("role", 1),
                ("agent_name", 1),
                ("model_profile_id", 1),
                ("model_profile_version", 1),
                ("prompt_id", 1),
                ("prompt_version", 1),
                ("request_hash", 1),
                ("attempt", 1),
            ],
            "name": "uniq_model_run_identity",
            "unique": True,
        },
        {"keys": [("snapshot_id", 1), ("created_at", -1)], "name": "idx_model_run_snapshot"},
        {"keys": [("run_mode", 1), ("created_at", -1)], "name": "idx_model_run_mode"},
        {"keys": [("error_category", 1), ("created_at", -1)], "name": "idx_model_run_error"},
    ],
    "ag_model_research_results": [
        {
            "keys": [("research_result_id", 1)],
            "name": "uniq_model_research_result",
            "unique": True,
        },
        {
            "keys": [
                ("analysis_id", 1),
                ("snapshot_id", 1),
                ("context_hash", 1),
                ("agent_name", 1),
            ],
            "name": "uniq_model_research_identity",
            "unique": True,
        },
        {"keys": [("status", 1), ("created_at", -1)], "name": "idx_model_research_status"},
    ],
    "ag_model_validation_runs": [
        {
            "keys": [("validation_run_id", 1)],
            "name": "uniq_model_validation_run",
            "unique": True,
        },
        {"keys": [("status", 1), ("created_at", -1)], "name": "idx_model_validation_status"},
        {"keys": [("snapshot_id", 1), ("created_at", -1)], "name": "idx_model_validation_snapshot"},
    ],
    "ag_model_validation_evidence_snapshots": [
        {
            "keys": [("snapshot_id", 1)],
            "name": "uniq_model_validation_snapshot_id",
            "unique": True,
        },
        {
            "keys": [("source_trade_date", 1), ("symbol", 1)],
            "name": "idx_model_validation_snapshot_source",
        },
    ],
    "ag_model_validation_quality_reports": [
        {
            "keys": [("quality_report_id", 1)],
            "name": "uniq_model_validation_quality_id",
            "unique": True,
        },
    ],
    "ag_model_validation_account_evidence": [
        {
            "keys": [("ref_id", 1)],
            "name": "uniq_model_validation_account_ref",
            "unique": True,
        },
    ],
    "ag_model_credentials": [
        {
            "keys": [("credential_id", 1)],
            "name": "uniq_model_credential_id",
            "unique": True,
        },
        {
            "keys": [
                ("provider_type", 1),
                ("endpoint_profile_id", 1),
                ("endpoint_profile_version", 1),
                ("normalized_origin", 1),
                ("auth_scheme", 1),
            ],
            "name": "uniq_model_credential_endpoint_binding",
            "unique": True,
            "sparse": True,
        },
        {"keys": [("provider", 1)], "name": "idx_model_credential_provider"},
        {
            "keys": [("status", 1), ("updated_at", -1)],
            "name": "idx_model_credential_status",
        },
    ],
    "ag_model_credential_events": [
        {
            "keys": [("credential_id", 1), ("created_at", -1)],
            "name": "idx_model_credential_event_credential",
        },
        {
            "keys": [("provider", 1), ("action", 1), ("created_at", -1)],
            "name": "idx_model_credential_event_action",
        },
        {
            "keys": [("status", 1), ("created_at", -1)],
            "name": "idx_model_credential_event_status",
        },
    ],
    "ag_model_provider_endpoints": [
        {
            "keys": [("endpoint_profile_id", 1), ("profile_version", 1)],
            "name": "uniq_model_endpoint_version",
            "unique": True,
        },
        {
            "keys": [("normalized_origin", 1), ("profile_version", 1)],
            "name": "idx_model_endpoint_origin_version",
        },
        {"keys": [("state", 1), ("created_at", -1)], "name": "idx_model_endpoint_state"},
        {"keys": [("config_hash", 1)], "name": "idx_model_endpoint_hash"},
    ],
    "ag_model_endpoint_models": [
        {
            "keys": [("endpoint_model_id", 1), ("model_version", 1)],
            "name": "uniq_endpoint_model_version",
            "unique": True,
        },
        {
            "keys": [
                ("endpoint_profile_id", 1),
                ("endpoint_profile_version", 1),
                ("remote_model_name", 1),
                ("model_version", 1),
            ],
            "name": "uniq_endpoint_remote_model_version",
            "unique": True,
        },
        {"keys": [("content_hash", 1)], "name": "idx_endpoint_model_hash"},
    ],
    "ag_model_endpoint_prices": [
        {
            "keys": [("price_version_id", 1)],
            "name": "uniq_endpoint_price_id",
            "unique": True,
        },
        {
            "keys": [
                ("endpoint_model_id", 1),
                ("endpoint_model_version", 1),
                ("effective_at", 1),
                ("price_version", 1),
            ],
            "name": "uniq_endpoint_model_effective_price",
            "unique": True,
        },
        {"keys": [("content_hash", 1)], "name": "idx_endpoint_price_hash"},
    ],
    "ag_model_profile_assignments": [
        {
            "keys": [("assignment_id", 1)],
            "name": "uniq_model_profile_assignment",
            "unique": True,
        },
        {"keys": [("role", 1), ("assigned_at", -1)], "name": "idx_model_assignment_role"},
        {"keys": [("assignment_hash", 1)], "name": "idx_model_assignment_hash"},
    ],
    "ag_model_endpoint_events": [
        {
            "keys": [("validation_event_id", 1)],
            "name": "uniq_model_endpoint_event",
            "unique": True,
        },
        {
            "keys": [
                ("endpoint_profile_id", 1),
                ("endpoint_profile_version", 1),
                ("created_at", -1),
            ],
            "name": "idx_model_endpoint_event_endpoint",
        },
        {"keys": [("status", 1), ("created_at", -1)], "name": "idx_model_endpoint_event_status"},
    ],
}
