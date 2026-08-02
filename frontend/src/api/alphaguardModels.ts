import { ApiClient } from './request'

export interface ModelProfileStatus {
  role: 'RESEARCH_AGENT' | 'NORMAL_TRADER' | 'TOP_RISK_REVIEWER'
  profile_id: string
  profile_version: string
  provider: string
  provider_type?: 'OPENAI_OFFICIAL' | 'OPENAI_COMPATIBLE'
  endpoint_profile_id?: string | null
  endpoint_profile_version?: string | null
  endpoint_model_id?: string | null
  price_version_id?: string | null
  model_name: string
  model_version?: string | null
  prompt_id?: string
  prompt_version?: string
  configured: boolean
  credential_status?: 'CONFIGURED' | 'NOT_CONFIGURED'
  capability: string
  capability_stale?: boolean
  capability_stale_reason?: 'CREDENTIAL_REVERIFIED' | null
  last_error_code?: string | null
  failure_summary?: string | null
  last_check?: string | null
  last_success?: string | null
  last_failure?: string | null
  latency_ms?: number | null
}

export interface ModelBudgetStatus {
  policy_id: string
  policy_version: string
  daily_calls: number
  max_daily_calls: number
  daily_cost: number
  max_daily_cost: number
  currency: string
  remaining_calls: number
  remaining_cost: number
}

export interface ModelRuntimeStatus {
  status: 'READY' | 'NOT_CONFIGURED' | 'DEGRADED'
  profiles: ModelProfileStatus[]
  budget?: ModelBudgetStatus
}

export interface ModelCredentialStatus {
  credential_id: string
  provider: string
  provider_type: 'OPENAI_OFFICIAL' | 'OPENAI_COMPATIBLE'
  endpoint_profile_id?: string | null
  endpoint_profile_version?: string | null
  normalized_origin?: string | null
  auth_scheme?: 'BEARER' | 'X_API_KEY' | null
  configured: boolean
  status: 'CONFIGURED' | 'NOT_CONFIGURED' | 'READY' | 'DEGRADED' | 'REVOKED'
  last_verified_at?: string | null
  last_error_code?: string | null
  sanitized_message?: string | null
  secret_store_status: 'READY' | 'UNAVAILABLE'
}

export interface CredentialCapabilitySummary {
  provider: string
  authentication_status: string
  provider_access_status: string
  normal_model_status: string
  top_model_status: string
  structured_output_status: string
  price_status: string
  budget_status: string
  checked_at: string
}

export interface ModelCredentialMutationResult {
  credential_id: string
  provider: string
  provider_type: 'OPENAI_OFFICIAL' | 'OPENAI_COMPATIBLE'
  endpoint_profile_id?: string | null
  endpoint_profile_version?: string | null
  configured: boolean
  stored: boolean
  replaced: boolean
  status: string
  secret_store_status: string
  capability: CredentialCapabilitySummary
  last_error_code?: string | null
  sanitized_message?: string | null
}

export interface ProviderEndpointProfile {
  endpoint_profile_id: string
  profile_version: string
  provider_type: 'OPENAI_OFFICIAL' | 'OPENAI_COMPATIBLE'
  display_name: string
  base_url?: string
  normalized_origin?: string
  api_mode?: 'OPENAI_CHAT_COMPLETIONS' | 'OPENAI_RESPONSES' | 'AUTO_DETECT'
  auth_scheme?: 'BEARER' | 'X_API_KEY'
  models_endpoint_enabled?: boolean
  structured_output_mode: 'NATIVE_JSON_SCHEMA' | 'TOOL_CALL' | 'JSON_ONLY' | 'UNKNOWN'
  state: 'DRAFT' | 'URL_VALIDATED' | 'CAPABILITY_CHECKED' | 'READY' | 'DEGRADED' | 'DISABLED' | 'REJECTED'
  enabled: boolean
  validation_allowed?: boolean
  production_allowed: boolean
  url_validation_status: 'NOT_CHECKED' | 'PASS' | 'REJECTED'
  data_transmission_confirmed?: boolean
  last_error_code?: string | null
  notes?: string | null
  configuration_stage?: ProviderConfigurationStage
  system_managed?: boolean
  latest_profile_version?: string
  has_newer_draft?: boolean
}

export type ProviderConfigurationStage =
  | 'DRAFT'
  | 'URL_VALIDATED'
  | 'CREDENTIAL_CONFIGURED'
  | 'AUTHENTICATED'
  | 'MODELS_REGISTERED'
  | 'PRICES_CONFIGURED'
  | 'PROFILES_CONFIGURED'
  | 'CAPABILITY_CHECKED'
  | 'READY'

export interface ProviderConfigurationComponent {
  key: string
  label: string
  complete: boolean
  status: string
  reason_code?: string | null
}

export interface ProviderConfigurationStatus {
  endpoint_profile_id: string
  endpoint_profile_version: string
  persisted_endpoint_state?: string
  stage: ProviderConfigurationStage
  production_allowed: boolean
  components: ProviderConfigurationComponent[]
  blocking_items: string[]
  budget_policy_id?: string
  budget_policy_version?: string
  budget_currency?: string
}

export interface EndpointModelDefinition {
  endpoint_model_id: string
  model_version: string
  endpoint_profile_id: string
  endpoint_profile_version: string
  remote_model_name: string
  display_name: string
  role_capabilities: Array<'RESEARCH_AGENT' | 'NORMAL_TRADER' | 'TOP_RISK_REVIEWER'>
  supports_json_schema: boolean
  supports_tool_call: boolean
  supports_reasoning?: boolean | null
  max_context_tokens?: number | null
  max_output_tokens?: number | null
  discovery_mode: 'MODELS_ENDPOINT' | 'MANUAL'
  status: 'UNVERIFIED' | 'READY' | 'UNSUPPORTED' | 'NOT_FOUND' | 'DISABLED'
  content_hash: string
}

export interface EndpointModelOption {
  remote_model_name: string
  display_name: string
}

export interface EndpointPriceVersion {
  price_version_id: string
  price_version: string
  endpoint_profile_id: string
  endpoint_profile_version: string
  endpoint_model_id: string
  endpoint_model_version: string
  pricing_source: 'PROVIDER_PUBLISHED' | 'SELF_HOSTED'
  input_price_per_million: string
  cached_input_price_per_million?: string | null
  output_price_per_million: string
  currency: string
  effective_at: string
  source_description: string
  verified: boolean
  content_hash: string
}

export interface PromptProfileSummary {
  prompt_id: string
  prompt_version: string
  role: string
  schema_target: string
  template_hash: string
  enabled: boolean
}

export interface ModelRunSummary {
  model_run_id: string
  snapshot_id?: string | null
  analysis_id: string
  run_mode: 'MODEL_CAPABILITY_CHECK' | 'REAL_MODEL_VALIDATION' | 'PRODUCTION' | 'PRODUCTION_REPROCESS' | 'RESEARCH_REPLAY' | 'DEMO'
  role: string
  agent_name: string
  model_profile_id: string
  model_profile_version: string
  model_name: string
  prompt_id: string
  prompt_version: string
  structured_output_status: string
  estimated_input_tokens?: number | null
  input_tokens?: number | null
  output_tokens?: number | null
  total_tokens?: number | null
  model_context_window?: number | null
  configured_max_output_tokens?: number | null
  remaining_context_capacity?: number | null
  context_usage_ratio?: number | null
  context_warning_level?: 'NONE' | 'OVER_70' | 'OVER_85' | 'OVER_95' | null
  estimated_cost?: number | null
  latency_ms: number
  request_hash: string
  response_hash?: string | null
  error_category?: string | null
  created_at: string
}

export interface RealModelValidationSummary {
  validation_run_id: string
  run_mode: 'REAL_MODEL_VALIDATION'
  status: string
  validation_contract_version?: string | null
  contract_hash?: string | null
  sample_selection_version?: string | null
  actual_production_decision?: false
  actual_execution?: false
  reused_from_validation_run_id?: string | null
  reused_research_and_normal?: boolean
  symbol?: string | null
  source_trade_date?: string | null
  snapshot_id?: string | null
  context_hash?: string | null
  decision_context_hash?: string | null
  source_quant_proposal_id?: string | null
  decision_evidence_pack_manifest_id?: string | null
  decision_evidence_status?: 'COMPLETE' | 'PARTIAL' | null
  decision_evidence_matrix?: Record<string, string> | null
  benchmark_count?: number | null
  normal_model_run_id?: string | null
  top_model_run_id?: string | null
  normal_result?: {
    status?: string | null
    action?: string | null
    model_meta?: { error_type?: string | null } | null
  } | null
  top_result?: {
    status?: string | null
    model_meta?: { error_type?: string | null } | null
  } | null
  consensus_status?: string | null
  hard_risk_status?: string | null
  execution_gate_status: 'BLOCKED_VALIDATION_MODE' | 'NOT_REACHED'
  execution_gate_invoked: boolean
  model_call_records: ModelRunSummary[]
  failure_code?: string | null
  created_at: string
}

export interface ResearchManagerContractCheckSummary {
  contract_check_id: string
  contract_id: 'research_manager_output_contract'
  contract_version: 'v2'
  schema_hash: string
  prompt_id: string
  prompt_version: string
  prompt_hash: string
  profile_id: string
  profile_version: string
  status: 'READY' | 'INVALID_OUTPUT' | 'MODEL_FAILED' | 'BUDGET_BLOCKED'
  model_run_id?: string | null
  payload_fields: string[]
  payload_field_types: string[]
  validation_error_fields: string[]
  validation_error_types: string[]
  total_tokens?: number | null
  latency_ms: number
  checked_at: string
}

export interface ModelCapabilityCheckResult {
  capability_check_id: string
  profile_id: string
  profile_version: string
  status: string
  error_code?: string | null
  sanitized_message?: string | null
  checked_at: string
}

export interface ResearchResultSummary {
  research_result_id: string
  agent_name: string
  agent_role: string
  status: string
  evidence_refs: string[]
  model_run_id?: string | null
  created_at: string
}

export const alphaguardModelsApi = {
  status() {
    return ApiClient.get<ModelRuntimeStatus>('/api/alphaguard/models/status')
  },
  validationRuns(limit = 20) {
    return ApiClient.get<{ items: RealModelValidationSummary[] }>(
      `/api/alphaguard/models/validation-runs?limit=${limit}`
    )
  },
  contractChecks(limit = 20) {
    return ApiClient.get<{ items: ResearchManagerContractCheckSummary[] }>(
      `/api/alphaguard/models/contract-checks?limit=${limit}`
    )
  },
  credentials() {
    return ApiClient.get<{
      items: ModelCredentialStatus[]
      secret_store_status: 'READY' | 'UNAVAILABLE'
    }>(
      '/api/alphaguard/models/credentials'
    )
  },
  createCredential(payload: {
    provider: string
    provider_type?: 'OPENAI_OFFICIAL' | 'OPENAI_COMPATIBLE'
    endpoint_profile_id?: string
    endpoint_profile_version?: string
    api_key: string
    base_url?: string
    credential_name: string
  }) {
    return ApiClient.post<ModelCredentialMutationResult>(
      '/api/alphaguard/models/credentials',
      payload,
      { skipErrorHandler: true }
    )
  },
  replaceCredential(
    credentialId: string,
    payload: { api_key: string; base_url?: string }
  ) {
    return ApiClient.put<ModelCredentialMutationResult>(
      `/api/alphaguard/models/credentials/${encodeURIComponent(credentialId)}`,
      payload,
      { skipErrorHandler: true }
    )
  },
  verifyCredential(credentialId: string) {
    return ApiClient.post<ModelCredentialMutationResult>(
      `/api/alphaguard/models/credentials/${encodeURIComponent(credentialId)}/verify`,
      {},
      { skipErrorHandler: true }
    )
  },
  revokeCredential(credentialId: string) {
    return ApiClient.delete<Record<string, unknown>>(
      `/api/alphaguard/models/credentials/${encodeURIComponent(credentialId)}`,
      { skipErrorHandler: true }
    )
  },
  prompts() {
    return ApiClient.get<{ items: PromptProfileSummary[] }>(
      '/api/alphaguard/models/prompts'
    )
  },
  endpoints() {
    return ApiClient.get<{ items: ProviderEndpointProfile[] }>(
      '/api/alphaguard/models/endpoints'
    )
  },
  createEndpoint(payload: {
    display_name: string
    provider_type: 'OPENAI_COMPATIBLE'
    base_url: string
    api_mode: 'OPENAI_CHAT_COMPLETIONS' | 'OPENAI_RESPONSES' | 'AUTO_DETECT'
    auth_scheme: 'BEARER' | 'X_API_KEY'
    models_endpoint_enabled: boolean
    structured_output_mode: 'NATIVE_JSON_SCHEMA' | 'TOOL_CALL' | 'JSON_ONLY' | 'UNKNOWN'
    notes?: string
    endpoint_profile_id?: string
    create_new_version?: boolean
  }) {
    return ApiClient.post<{ item: ProviderEndpointProfile; result: 'CREATED' | 'REUSED' }>(
      '/api/alphaguard/models/endpoints', payload, { skipErrorHandler: true }
    )
  },
  validateEndpoint(endpointId: string, payload: {
    profile_version: string
    confirm_data_transmission: boolean
  }) {
    return ApiClient.post<ProviderEndpointProfile>(
      `/api/alphaguard/models/endpoints/${encodeURIComponent(endpointId)}/validate`,
      payload,
      { skipErrorHandler: true }
    )
  },
  disableEndpoint(endpointId: string, profileVersion: string) {
    return ApiClient.post<ProviderEndpointProfile>(
      `/api/alphaguard/models/endpoints/${encodeURIComponent(endpointId)}/disable`,
      { profile_version: profileVersion },
      { skipErrorHandler: true }
    )
  },
  endpointModels(endpointId: string, profileVersion?: string) {
    const query = profileVersion ? `?profile_version=${encodeURIComponent(profileVersion)}` : ''
    return ApiClient.get<{ items: EndpointModelDefinition[] }>(
      `/api/alphaguard/models/endpoints/${encodeURIComponent(endpointId)}/models${query}`
    )
  },
  endpointConfigurationStatus(endpointId: string, profileVersion: string) {
    return ApiClient.get<ProviderConfigurationStatus>(
      `/api/alphaguard/models/endpoints/${encodeURIComponent(endpointId)}/configuration-status`,
      { profile_version: profileVersion }
    )
  },
  createEndpointModel(endpointId: string, payload: {
    endpoint_profile_version: string
    remote_model_name: string
    display_name: string
    role_capabilities: Array<'RESEARCH_AGENT' | 'NORMAL_TRADER' | 'TOP_RISK_REVIEWER'>
    supports_json_schema: boolean
    supports_tool_call: boolean
    supports_reasoning?: boolean
    max_context_tokens?: number
    max_output_tokens?: number
    endpoint_model_id?: string
    model_version?: string
  }) {
    return ApiClient.post<{ item: EndpointModelDefinition; result: 'CREATED' | 'REUSED' }>(
      `/api/alphaguard/models/endpoints/${encodeURIComponent(endpointId)}/models`,
      payload,
      { skipErrorHandler: true }
    )
  },
  discoverEndpointModels(endpointId: string, payload: {
    endpoint_profile_version: string
    credential_id?: string
  }) {
    return ApiClient.post<{ items: EndpointModelDefinition[] }>(
      `/api/alphaguard/models/endpoints/${encodeURIComponent(endpointId)}/models/discover`,
      payload,
      { skipErrorHandler: true }
    )
  },
  endpointModelOptions(endpointId: string, payload: {
    endpoint_profile_version: string
    credential_id: string
  }) {
    return ApiClient.post<{
      items: EndpointModelOption[]
      source: 'MODELS_ENDPOINT'
      status: 'READY' | 'EMPTY'
    }>(
      `/api/alphaguard/models/endpoints/${encodeURIComponent(endpointId)}/models/options`,
      payload,
      { skipErrorHandler: true }
    )
  },
  prices(endpointId?: string) {
    const query = endpointId ? `?endpoint_profile_id=${encodeURIComponent(endpointId)}` : ''
    return ApiClient.get<{ items: EndpointPriceVersion[] }>(
      `/api/alphaguard/models/prices${query}`
    )
  },
  createPrice(payload: {
    endpoint_profile_id: string
    endpoint_profile_version: string
    endpoint_model_id: string
    endpoint_model_version: string
    pricing_source: 'PROVIDER_PUBLISHED' | 'SELF_HOSTED'
    input_price_per_million: string
    cached_input_price_per_million?: string
    output_price_per_million: string
    currency: string
    effective_at: string
    source_description: string
    verified: boolean
  }) {
    return ApiClient.post<{ item: EndpointPriceVersion; result: 'CREATED' | 'REUSED' }>(
      '/api/alphaguard/models/prices', payload, { skipErrorHandler: true }
    )
  },
  assignCompatibleProfile(payload: {
    role: 'NORMAL_TRADER' | 'TOP_RISK_REVIEWER'
    profile_id: string
    profile_version: string
    endpoint_profile_id: string
    endpoint_profile_version: string
    endpoint_model_id: string
    endpoint_model_version: string
    credential_id: string
    price_version_id: string
    price_version: string
    prompt_profile_id: string
    explicit_same_model_confirmation: boolean
  }) {
    return ApiClient.post<Record<string, unknown>>(
      '/api/alphaguard/models/profiles/compatible', payload, { skipErrorHandler: true }
    )
  },
  configureDecisionModels(payload: {
    endpoint_profile_id: string
    endpoint_profile_version: string
    credential_id: string
    normal_endpoint_model_id: string
    normal_endpoint_model_version: string
    top_endpoint_model_id: string
    top_endpoint_model_version: string
    explicit_same_model_confirmation: boolean
  }) {
    return ApiClient.post<{ roles: Record<string, Record<string, unknown>> }>(
      '/api/alphaguard/models/profiles/decision-models',
      payload,
      { skipErrorHandler: true }
    )
  },
  runs(limit = 100) {
    return ApiClient.get<{ items: ModelRunSummary[] }>(
      `/api/alphaguard/models/runs?limit=${limit}`
    )
  },
  capabilityCheck(payload: {
    profile_id: string
    profile_version: string
    idempotency_key: string
    network: boolean
  }) {
    return ApiClient.post<ModelCapabilityCheckResult>(
      '/api/alphaguard/models/capability-check',
      payload,
      { skipErrorHandler: true }
    )
  },
  snapshotRuns(snapshotId: string) {
    return ApiClient.get<{
      runs: ModelRunSummary[]
      research: ResearchResultSummary[]
    }>(`/api/alphaguard/models/snapshots/${encodeURIComponent(snapshotId)}/runs`)
  }
}
