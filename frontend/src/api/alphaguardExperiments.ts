import { ApiClient } from './request'

export interface ChampionAssignment {
  champion_slot_id: string
  component_type: string
  component_key: string
  market: string
  current_version_ref: string
  previous_version_ref: string | null
  effective_from_trade_date: string
  status: string
  assignment_hash: string
  source_experiment_id: string | null
}

export interface ExperimentDefinition {
  experiment_id: string
  name: string
  hypothesis: string
  component_type: string
  component_key: string
  primary_variable_path: string
  baseline_version_ref: string
  challenger_version_ref: string
  experiment_mode: string
  promotion_eligible: boolean
  execution_supported: boolean
  status: string
}

export interface ExperimentDetail {
  definition: ExperimentDefinition
  variable_changes: Record<string, unknown>[]
  dataset_manifests: Record<string, unknown>[]
  runs: Record<string, unknown>[]
  shadow_runs: Record<string, unknown>[]
  challenger_assignments: Record<string, unknown>[]
  comparison_reports: Record<string, unknown>[]
  risk_reviews: Record<string, unknown>[]
  promotion_requests: Record<string, unknown>[]
  events: Record<string, unknown>[]
}

interface Items<T> {
  items: T[]
}

export const alphaguardExperimentApi = {
  champions() {
    return ApiClient.get<Items<ChampionAssignment>>('/api/alphaguard/champions')
  },
  champion(slotId: string) {
    return ApiClient.get<Record<string, unknown>>(
      `/api/alphaguard/champions/${encodeURIComponent(slotId)}`
    )
  },
  experiments() {
    return ApiClient.get<Items<ExperimentDefinition>>('/api/alphaguard/experiments')
  },
  experiment(experimentId: string) {
    return ApiClient.get<ExperimentDetail>(
      `/api/alphaguard/experiments/${encodeURIComponent(experimentId)}`
    )
  },
  approvePromotion(requestId: string, payload: {
    decision_reason: string
    confirmation_text: string
    current_champion_hash: string
    proposed_champion_hash: string
  }) {
    return ApiClient.post(
      `/api/alphaguard/promotion-requests/${encodeURIComponent(requestId)}/approve`,
      payload
    )
  },
  rejectPromotion(requestId: string, reason: string) {
    return ApiClient.post(
      `/api/alphaguard/promotion-requests/${encodeURIComponent(requestId)}/reject`,
      { reason }
    )
  },
  rollbackChampion(slotId: string, payload: {
    reason: string
    confirmation_text: string
    current_champion_hash: string
    effective_from_trade_date: string
  }) {
    return ApiClient.post(
      `/api/alphaguard/champions/${encodeURIComponent(slotId)}/rollback`,
      payload
    )
  }
}
