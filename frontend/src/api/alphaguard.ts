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
  trace_id?: string | null
  reason?: string | null
  created_at: string
}

export interface QuantProposalSummary {
  quant_proposal_id: string
  candidate_id?: string | null
  snapshot_id: string
  symbol: string
  market: string
  status: string
  action_candidate: string
  strategy_id: string
  strategy_version: string
  created_at: string
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

