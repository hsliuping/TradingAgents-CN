import { ApiClient } from './request'

export interface ModelProfileStatus {
  role: 'RESEARCH_AGENT' | 'NORMAL_TRADER' | 'TOP_RISK_REVIEWER'
  profile_id: string
  profile_version: string
  provider: string
  model_name: string
  model_version?: string | null
  prompt_id?: string
  prompt_version?: string
  configured: boolean
  credential_status?: 'CONFIGURED' | 'NOT_CONFIGURED'
  capability: string
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
  total_tokens?: number | null
  estimated_cost?: number | null
  latency_ms: number
  error_category?: string | null
  created_at: string
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
  capabilityCheck(payload: {
    profile_id: string
    profile_version: string
    idempotency_key: string
    network: boolean
  }) {
    return ApiClient.post<Record<string, unknown>>(
      '/api/alphaguard/models/capability-check',
      payload
    )
  },
  snapshotRuns(snapshotId: string) {
    return ApiClient.get<{
      runs: ModelRunSummary[]
      research: ResearchResultSummary[]
    }>(`/api/alphaguard/models/snapshots/${encodeURIComponent(snapshotId)}/runs`)
  }
}
