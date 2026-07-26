"""Declarative MongoDB index plan for AlphaGuard PR-003."""

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
}
