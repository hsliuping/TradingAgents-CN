"""Secret-free, create-only model runtime collections."""

MODEL_RUNTIME_COLLECTIONS = {
    "profiles": "ag_model_profiles",
    "prompts": "ag_model_prompt_versions",
    "capability_checks": "ag_model_capability_checks",
    "contract_checks": "ag_model_contract_checks",
    "runs": "ag_model_runs",
    "research_results": "ag_model_research_results",
    "validation_runs": "ag_model_validation_runs",
    "validation_snapshots": "ag_model_validation_evidence_snapshots",
    "validation_quality": "ag_model_validation_quality_reports",
    "validation_accounts": "ag_model_validation_account_evidence",
    "credentials": "ag_model_credentials",
    "credential_events": "ag_model_credential_events",
    "endpoints": "ag_model_provider_endpoints",
    "endpoint_models": "ag_model_endpoint_models",
    "endpoint_prices": "ag_model_endpoint_prices",
    "profile_assignments": "ag_model_profile_assignments",
    "endpoint_events": "ag_model_endpoint_events",
}

MODEL_RUNTIME_WRITE_COLLECTIONS = frozenset(MODEL_RUNTIME_COLLECTIONS.values())
