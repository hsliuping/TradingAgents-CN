"""Secret-free, create-only model runtime collections."""

MODEL_RUNTIME_COLLECTIONS = {
    "profiles": "ag_model_profiles",
    "prompts": "ag_model_prompt_versions",
    "capability_checks": "ag_model_capability_checks",
    "runs": "ag_model_runs",
    "research_results": "ag_model_research_results",
    "validation_runs": "ag_model_validation_runs",
}

MODEL_RUNTIME_WRITE_COLLECTIONS = frozenset(MODEL_RUNTIME_COLLECTIONS.values())
