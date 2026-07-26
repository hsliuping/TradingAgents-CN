"""Dedicated PR-008 experiment collections.

Every experiment result lives under ``ag_exp_*``.  Production research,
decision, evaluation and trading collections are read-only inputs.
"""

EXPERIMENT_COLLECTIONS = {
    "component_versions": "ag_exp_component_versions",
    "definitions": "ag_exp_definitions",
    "variable_changes": "ag_exp_variable_changes",
    "dataset_manifests": "ag_exp_dataset_manifests",
    "time_splits": "ag_exp_time_splits",
    "runs": "ag_exp_runs",
    "run_results": "ag_exp_run_results",
    "leakage_audits": "ag_exp_leakage_audits",
    "robustness_reports": "ag_exp_robustness_reports",
    "shadow_runs": "ag_exp_shadow_runs",
    "shadow_outputs": "ag_exp_shadow_outputs",
    "challenger_assignments": "ag_exp_challenger_assignments",
    "comparison_reports": "ag_exp_comparison_reports",
    "risk_reviews": "ag_exp_risk_reviews",
    "promotion_policies": "ag_exp_promotion_policies",
    "promotion_requests": "ag_exp_promotion_requests",
    "promotion_approvals": "ag_exp_promotion_approvals",
    "promotion_sagas": "ag_exp_promotion_sagas",
    "champion_assignments": "ag_exp_champion_assignments",
    "champion_history": "ag_exp_champion_history",
    "rollbacks": "ag_exp_rollbacks",
    "locks": "ag_exp_locks",
    "task_runs": "ag_exp_task_runs",
    "events": "ag_exp_events",
}

EXPERIMENT_WRITE_COLLECTIONS = frozenset(EXPERIMENT_COLLECTIONS.values())
