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
}
