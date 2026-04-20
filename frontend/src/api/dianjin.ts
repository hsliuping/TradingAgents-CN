import { ApiClient } from './request'

export interface DianjinRunRequest {
  min_pe: number
  max_pe: number
  min_dividend: number
  max_dividend: number
  min_market_cap: number
  ratio_threshold: number
  min_pb?: number | null
  max_pb?: number | null
  dividend_mode: 'any' | 'all'
  specific_stocks?: string
  kline_days?: number
  limit_count?: number
}

export interface DianjinResultItem {
  code: string
  name: string
  price: number
  pe_ttm: number
  dividend_yield: number
  market_cap: number
  pb: number
  ma120_ratio: number
  three_year_dividend: number[]
  three_year_dividend_pass: boolean
  three_year_all_pass: boolean
}

export interface DianjinRunStats {
  total_samples: number
  realtime_count: number
  first_filter_count: number
  ma120_pass_count: number
  final_count: number
  duration_ms: number
}

export interface DianjinRunResponse {
  items: DianjinResultItem[]
  stats: DianjinRunStats
  years: number[]
}

export const dianjinApi = {
  run: (payload: DianjinRunRequest, options?: { timeout?: number }) =>
    ApiClient.post<DianjinRunResponse>('/api/dianjin/run', payload, { timeout: options?.timeout ?? 300000 })
}
