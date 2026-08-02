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

export interface ChallengerSummary {
  experiment_id: string
  name: string
  status: string
  baseline_champion_id: string | null
  baseline_champion_version: string | null
  challenger_version_id: string | null
  change_type: string | null
  change_summary: string | null
  primary_variable_path: string
  config_hash: string | null
  validation_only: boolean
  promotion_eligible: boolean
  assignment_id: string | null
  assignment_status: string | null
  account_id: string | null
  cash_available: string | number | null
  cash_reserved: string | number | null
  position_count: number
  order_count: number
  fill_count: number
  run_count: number
  last_run_at: string | null
  last_run_status: string | null
  last_failure_code: string | null
  net_return: string | number | null
  total_fees: string | number | null
}

export interface ChallengerOptions {
  champions: ChampionAssignment[]
  component_versions: Array<{
    version_ref: string
    component_type: string
    component_key: string
    payload_hash: string
    execution_supported: boolean
  }>
  change_types: Array<{ value: string; label: string }>
}

interface Items<T> {
  items: T[]
}

export interface PromotionPolicy {
  policy_id: string
  policy_version: string
  required_run_types: string[]
  minimum_sample_rules: Record<string, string | number>
  require_leakage_pass: boolean
  require_robustness_pass: boolean
  require_shadow: boolean
  require_paper_challenger: boolean
  require_top_risk_review: boolean
  require_human_approval: boolean
  immutable_hash: string
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
  challengers() {
    return ApiClient.get<Items<ChallengerSummary>>('/api/alphaguard/experiments/challengers')
  },
  challengerOptions() {
    return ApiClient.get<ChallengerOptions>('/api/alphaguard/experiments/challengers/options')
  },
  challenger(experimentId: string) {
    return ApiClient.get<{ summary: ChallengerSummary; runs: Record<string, unknown>[] }>(
      `/api/alphaguard/experiments/challengers/${encodeURIComponent(experimentId)}`
    )
  },
  createChallenger(payload: {
    name: string
    description: string
    hypothesis: string
    component_type: string
    component_key: string
    baseline_version_ref: string
    challenger_version_ref: string
    primary_variable_path: string
    validation_only: boolean
  }) {
    return ApiClient.post<ExperimentDefinition>('/api/alphaguard/experiments/challengers', payload)
  },
  backtestChallenger(experimentId: string, datasetManifestId: string, splitId?: string) {
    return ApiClient.post(
      `/api/alphaguard/experiments/challengers/${encodeURIComponent(experimentId)}/backtest`,
      { dataset_manifest_id: datasetManifestId, split_id: splitId || null }
    )
  },
  shadowChallenger(experimentId: string, datasetManifestId: string) {
    return ApiClient.post(
      `/api/alphaguard/experiments/challengers/${encodeURIComponent(experimentId)}/shadow`,
      { dataset_manifest_id: datasetManifestId }
    )
  },
  activateChallenger(experimentId: string, activationTradeDate: string) {
    return ApiClient.post(
      `/api/alphaguard/experiments/challengers/${encodeURIComponent(experimentId)}/activate`,
      { activation_trade_date: activationTradeDate }
    )
  },
  pauseChallenger(experimentId: string, reason: string) {
    return ApiClient.post(
      `/api/alphaguard/experiments/challengers/${encodeURIComponent(experimentId)}/pause`,
      { reason }
    )
  },
  retireChallenger(experimentId: string, reason: string) {
    return ApiClient.post(
      `/api/alphaguard/experiments/challengers/${encodeURIComponent(experimentId)}/retire`,
      { reason }
    )
  },
  challengerRuns(experimentId: string) {
    return ApiClient.get<Items<Record<string, unknown>>>(
      `/api/alphaguard/experiments/challengers/${encodeURIComponent(experimentId)}/runs`
    )
  },
  challengerDecisions(experimentId: string) {
    return ApiClient.get<Items<Record<string, unknown>>>(
      `/api/alphaguard/experiments/challengers/${encodeURIComponent(experimentId)}/decisions`
    )
  },
  challengerOrders(experimentId: string) {
    return ApiClient.get<{ intents: Record<string, unknown>[]; orders: Record<string, unknown>[]; fills: Record<string, unknown>[] }>(
      `/api/alphaguard/experiments/challengers/${encodeURIComponent(experimentId)}/orders`
    )
  },
  challengerEvaluation(experimentId: string) {
    return ApiClient.get<Record<string, unknown>>(
      `/api/alphaguard/experiments/challengers/${encodeURIComponent(experimentId)}/evaluation`
    )
  },
  challengerComparison(experimentId: string) {
    return ApiClient.get<Record<string, unknown>>(
      `/api/alphaguard/experiments/challengers/${encodeURIComponent(experimentId)}/comparison`
    )
  },
  requestRiskReview(experimentId: string, comparisonReportId: string) {
    return ApiClient.post(
      `/api/alphaguard/experiments/${encodeURIComponent(experimentId)}/risk-review`,
      { comparison_report_id: comparisonReportId }
    )
  },
  promotionPolicy() {
    return ApiClient.get<{ policy: PromotionPolicy | null; status: string }>(
      '/api/alphaguard/experiments/promotion-policy'
    )
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
