import { ApiClient } from './request'

export type RecommendationStatus =
  | 'PENDING_REVIEW'
  | 'ACCEPTED'
  | 'REJECTED'
  | 'IGNORED'
  | 'EXPIRED'
  | 'SUPERSEDED'

export interface CandidateRecommendation {
  recommendation_id: string
  recommendation_run_id: string
  trade_date: string
  market: 'CN'
  symbol: string
  security_name: string
  security_type: 'A_SHARE' | 'EXCHANGE_TRADED_FUND'
  policy_id: string
  policy_version: string
  recommendation_score: string
  score_components: Record<string, string>
  risk_penalties: Record<string, string>
  recommendation_reason_codes: string[]
  recommendation_reasons: string[]
  risk_reason_codes: string[]
  risk_reasons: string[]
  data_quality_status: string
  regime_type: string | null
  strategy_signal_status: string | null
  evidence_refs: string[]
  factor_result_refs: string[]
  supersedes_recommendation_id: string | null
  input_hash: string
  output_hash: string
  expires_at: string
  created_at: string
  schema_version: string
  status: RecommendationStatus
  reviewed_at: string | null
  review_note: string | null
  candidate_id: string | null
}

export interface RecommendationRun {
  recommendation_run_id: string
  user_id: string
  trade_date: string
  universe_manifest_id: string
  universe_version: string
  policy_id: string
  policy_version: string
  data_version: string
  total_securities: number
  eligible_securities: number
  scored_securities: number
  recommended_securities: number
  filtered_reason_counts: Record<string, number>
  failed_symbols: string[]
  status: string
  duration_ms: number
  completed_at: string
  input_hash: string
  output_hash: string
  run_action?: 'CREATED' | 'REUSED'
}

export interface RecommendationDataCoverage {
  coverage_id?: string
  trade_date?: string
  status: 'NOT_READY' | 'PARTIAL' | 'READY' | 'DEGRADED'
  recommendation_data_ready: boolean
  universe_count?: number
  basic_info_ready_count?: number
  target_quote_ready_count?: number
  trade_status_ready_count?: number
  raw_history_ready_count?: number
  adjusted_history_ready_count?: number
  benchmark_ready_count?: number
  industry_ready_count?: number
  data_quality_pass_count?: number
  minimum_contract_ready_count?: number
  eligible_count?: number
  failed_symbol_count?: number
  required_history_days?: number
  coverage_percentage?: string
  blocking_reason_counts: Record<string, number>
  sync_completed_at?: string | null
  sync_duration_ms?: number
}

interface Items<T> { items: T[]; count?: number }

export const alphaguardRecommendationsApi = {
  list(params?: { status?: RecommendationStatus; limit?: number; skip?: number }) {
    return ApiClient.get<Items<CandidateRecommendation>>('/api/alphaguard/recommendations', params)
  },
  detail(recommendationId: string) {
    return ApiClient.get<CandidateRecommendation & Record<string, unknown>>(
      `/api/alphaguard/recommendations/${encodeURIComponent(recommendationId)}`
    )
  },
  runs(params?: { limit?: number }) {
    return ApiClient.get<Items<RecommendationRun>>('/api/alphaguard/recommendations/runs', params)
  },
  coverage(tradeDate?: string) {
    return ApiClient.get<RecommendationDataCoverage>(
      '/api/alphaguard/recommendations/coverage',
      tradeDate ? { trade_date: tradeDate } : undefined
    )
  },
  run(tradeDate?: string) {
    return ApiClient.post<RecommendationRun>('/api/alphaguard/recommendations/run', {
      trade_date: tradeDate || null
    })
  },
  accept(recommendationId: string, reviewNote?: string) {
    return ApiClient.post(
      `/api/alphaguard/recommendations/${encodeURIComponent(recommendationId)}/accept`,
      { review_note: reviewNote || null }
    )
  },
  reject(recommendationId: string, reviewNote?: string) {
    return ApiClient.post(
      `/api/alphaguard/recommendations/${encodeURIComponent(recommendationId)}/reject`,
      { review_note: reviewNote || null }
    )
  },
  ignore(recommendationId: string, reviewNote?: string) {
    return ApiClient.post(
      `/api/alphaguard/recommendations/${encodeURIComponent(recommendationId)}/ignore`,
      { review_note: reviewNote || null }
    )
  },
  batchAccept(recommendationIds: string[]) {
    return ApiClient.post('/api/alphaguard/recommendations/batch-accept', {
      recommendation_ids: recommendationIds,
      review_note: null
    })
  },
  batchReject(recommendationIds: string[]) {
    return ApiClient.post('/api/alphaguard/recommendations/batch-reject', {
      recommendation_ids: recommendationIds,
      review_note: null
    })
  }
}
