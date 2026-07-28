"""Dedicated historical-research collections.

No collection in this module is an execution, account, position or ledger
collection.  PR-006 state is read-only during backfill.
"""

BACKFILL_COLLECTIONS = {
    "runs": "ag_research_backfill_runs",
    "samples": "ag_research_backfill_samples",
    "coverage": "ag_research_coverage",
    "market_context_sources": "ag_research_market_context_sources",
    "market_contexts": "ag_research_market_contexts",
    "snapshots": "ag_research_snapshots",
    "factor_results": "ag_research_factor_results",
    "factor_bundles": "ag_research_factor_bundles",
    "regime_results": "ag_research_regime_results",
    "quant_proposals": "ag_research_quant_proposals",
    "execution_snapshots": "ag_research_execution_snapshots",
    "shadow_executions": "ag_research_shadow_executions",
    "reports": "ag_research_backfill_reports",
    "events": "ag_research_backfill_events",
}

BACKFILL_WRITE_COLLECTIONS = frozenset(BACKFILL_COLLECTIONS.values())
