"""Dedicated PR-012 recommendation collections, isolated from trading PnL."""

RECOMMENDATION_COLLECTIONS = {
    "policies": "ag_candidate_recommendation_policies",
    "universe_manifests": "ag_candidate_universe_manifests",
    "eligibility_results": "ag_candidate_eligibility_results",
    "runs": "ag_candidate_recommendation_runs",
    "recommendations": "ag_candidate_recommendations",
    "review_events": "ag_candidate_recommendation_review_events",
    "evaluations": "ag_candidate_recommendation_evaluations",
}

RECOMMENDATION_WRITE_COLLECTIONS = frozenset(RECOMMENDATION_COLLECTIONS.values())
