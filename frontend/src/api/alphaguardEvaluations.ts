import { ApiClient } from './request'

export interface EvaluationOverview {
  evaluated_subjects: number
  pending_horizon_labels: number
  insufficient_data_labels: number
  traded_subjects: number
  untraded_subjects: number
  counterfactual_samples: number
  attribution_completion_rate: number | null
  diagnostic_notice: string
}

export interface AccountEvaluation {
  metric_id: string
  account_id: string
  account_type: string
  period_start: string
  period_end: string
  status: string
  total_return: string | null
  max_drawdown: string | null
  total_fees: string | null
  average_exposure_pct: string | null
  turnover: string | null
  trade_count: number
  valuation_complete_days: number
  valuation_incomplete_days: number
}

export interface PairedComparison {
  comparison_id: string
  comparison_type: string
  symbol: string
  pairing_status: string
  comparability_reasons: string[]
  value_added_10d: string | null
  calculated_at: string
}

export interface CounterfactualEvaluation {
  counterfactual_id: string
  subject_id: string
  mode: string
  status: string
  net_pnl: string | null
  return_pct: string | null
  created_at: string
}

export interface Attribution {
  attribution_id: string
  subject_id: string
  status: string
  outcome_class: string
  primary_category: string | null
  confidence: string
  evidence_refs: string[]
  machine_explanation: string
  overrides?: Array<{
    override_id: string
    overridden_primary_category: string
    reason: string
    created_at: string
  }>
}

interface ItemsResponse<T> {
  items: T[]
}

export const alphaguardEvaluationApi = {
  overview() {
    return ApiClient.get<EvaluationOverview>('/api/alphaguard/evaluations/overview')
  },
  accounts() {
    return ApiClient.get<ItemsResponse<AccountEvaluation>>('/api/alphaguard/evaluations/accounts')
  },
  modelValue() {
    return ApiClient.get<ItemsResponse<PairedComparison>>('/api/alphaguard/evaluations/model-value')
  },
  counterfactuals() {
    return ApiClient.get<ItemsResponse<CounterfactualEvaluation>>(
      '/api/alphaguard/evaluations/counterfactuals'
    )
  },
  attributions() {
    return ApiClient.get<ItemsResponse<Attribution>>('/api/alphaguard/attributions')
  }
}
