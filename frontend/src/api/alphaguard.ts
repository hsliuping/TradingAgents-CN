import { ApiClient } from './request'

export interface CandidateEntry {
  candidate_id: string
  symbol: string
  market: 'CN'
  name?: string | null
  sources: string[]
  status: string
  priority: number
  active_plan_id?: string | null
  active_order_ids: string[]
  held_account_ids: string[]
  cooldown_until?: string | null
  next_scan_at?: string | null
  latest_snapshot_id?: string | null
  removal_requested: boolean
  updated_at: string
}

export interface DecisionEvent {
  event_id?: string
  event_type: string
  analysis_id?: string | null
  snapshot_id?: string | null
  quant_proposal_id?: string | null
  plan_id?: string | null
  review_id?: string | null
  consensus_id?: string | null
  risk_decision_id?: string | null
  intent_id?: string | null
  status?: string | null
  trace_id?: string | null
  reason?: string | null
  input_hash?: string | null
  output_hash?: string | null
  component_version?: string | null
  evidence_refs?: unknown[]
  created_at: string
}

export interface QuantProposalSummary {
  proposal_id: string
  candidate_id?: string | null
  snapshot_id: string
  symbol: string
  market: string
  trade_date?: string
  status: string
  action_candidate: string
  strategy_id: string
  strategy_version: string
  regime_result_id?: string | null
  factor_set_version?: string | null
  reason_codes?: string[]
  explanation?: string
  input_hash?: string
  evidence_refs?: Array<Record<string, unknown>>
  automated_execution_allowed?: boolean
  created_at: string
}

export interface EvidenceSnapshotSummary {
  snapshot_id: string
  analysis_id?: string | null
  symbol: string
  market: string
  trade_date: string
  price_data_version: string
  financial_data_version: string
  news_data_version: string
  market_context_id?: string | null
  data_quality: {
    status: string
    blocking_reasons: string[]
    missing_fields: string[]
    checked_at: string
  }
  raw_refs: Record<string, string[]>
  prompt_versions: Record<string, string>
  champion_version_refs?: Record<string, string>
  factor_version_set: Record<string, string>
  strategy_version?: string | null
  immutable_hash: string
  created_at: string
}

export interface FactorResultSummary {
  factor_result_id: string
  factor_id: string
  factor_version: string
  calculation_status: string
  normalized_score?: number | null
  missing_inputs?: string[]
  input_hash: string
  calculated_at: string
}

export interface RegimeResultSummary {
  regime_result_id: string
  snapshot_id: string
  calculation_status: string
  regime?: string | null
  evidence: string[]
  regime_version: string
  input_hash: string
  calculated_at: string
}

interface Items<T> {
  items: T[]
}

export const alphaguardApi = {
  candidates(params?: Record<string, unknown>) {
    return ApiClient.get<Items<CandidateEntry>>('/api/alphaguard/candidates', params)
  },
  addCandidate(payload: { symbol: string; market: 'CN'; name?: string; priority: number }) {
    return ApiClient.post<CandidateEntry>('/api/alphaguard/candidates', payload)
  },
  removeCandidate(candidateId: string) {
    return ApiClient.delete<{
      candidate: CandidateEntry
      monitoring_retained: boolean
      retention_reasons: string[]
      physically_deleted: false
    }>(`/api/alphaguard/candidates/${encodeURIComponent(candidateId)}`)
  },
  reconcileCandidates() {
    return ApiClient.post<Record<string, number>>('/api/alphaguard/candidates/reconcile')
  },
  quantProposals(params?: Record<string, unknown>) {
    return ApiClient.get<Items<QuantProposalSummary>>('/api/alphaguard/quant-proposals', params)
  },
  evidenceSnapshot(snapshotId: string) {
    return ApiClient.get<EvidenceSnapshotSummary>(
      `/api/alphaguard/evidence/snapshots/${encodeURIComponent(snapshotId)}`
    )
  },
  factorResults(snapshotId: string) {
    return ApiClient.get<Items<FactorResultSummary>>(
      `/api/alphaguard/factors/results/${encodeURIComponent(snapshotId)}`
    )
  },
  regime(snapshotId: string) {
    return ApiClient.get<RegimeResultSummary>(
      `/api/alphaguard/regimes/${encodeURIComponent(snapshotId)}`
    )
  },
  decisionEvents(params?: Record<string, unknown>) {
    return ApiClient.get<Items<DecisionEvent>>('/api/alphaguard/decision-events', params)
  },
  normalPlan(planId: string) {
    return ApiClient.get<Record<string, unknown>>(
      `/api/alphaguard/decisions/${encodeURIComponent(planId)}`
    )
  },
  topReview(reviewId: string) {
    return ApiClient.get<Record<string, unknown>>(
      `/api/alphaguard/reviews/${encodeURIComponent(reviewId)}`
    )
  },
  consensus(consensusId: string) {
    return ApiClient.get<Record<string, unknown>>(
      `/api/alphaguard/consensus/${encodeURIComponent(consensusId)}`
    )
  },
  riskDecision(riskDecisionId: string) {
    return ApiClient.get<Record<string, unknown>>(
      `/api/alphaguard/risk-decisions/${encodeURIComponent(riskDecisionId)}`
    )
  }
}
