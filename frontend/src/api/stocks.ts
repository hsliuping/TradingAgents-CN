import { ApiClient } from './request'

export interface QuoteResponse {
  symbol: string  // 主字段：6位股票代码
  code?: string   // 兼容字段（已废弃）
  full_symbol?: string  // 完整代码（如 000001.SZ）
  name?: string
  market?: string
  price?: number
  change_percent?: number
  amount?: number
  prev_close?: number
  turnover_rate?: number
  amplitude?: number  // 振幅（替代量比）
  trade_date?: string
  updated_at?: string
}

export interface FundamentalsResponse {
  symbol: string  // 主字段：6位股票代码
  code?: string   // 兼容字段（已废弃）
  full_symbol?: string  // 完整代码（如 000001.SZ）
  name?: string
  industry?: string
  market?: string
  sector?: string  // 板块
  pe?: number
  pb?: number
  ps?: number      // 🔥 新增：市销率
  pe_ttm?: number
  pb_mrq?: number
  ps_ttm?: number  // 🔥 新增：市销率（TTM）
  roe?: number
  debt_ratio?: number  // 🔥 新增：负债率
  total_mv?: number
  circ_mv?: number
  turnover_rate?: number
  volume_ratio?: number
  pe_is_realtime?: boolean  // PE是否为实时数据
  pe_source?: string        // PE数据来源
  pe_updated_at?: string    // PE更新时间
  updated_at?: string
}

export interface KlineBar {
  time: string
  open?: number
  high?: number
  low?: number
  close?: number
  volume?: number
  amount?: number
}

export interface KlineResponse {
  symbol: string  // 主字段：6位股票代码
  code?: string   // 兼容字段（已废弃）
  period: 'day'|'week'|'month'|'5m'|'15m'|'30m'|'60m'
  limit: number
  adj: 'none'|'qfq'|'hfq'
  source?: string
  items: KlineBar[]
}

export interface NewsItem {
  title: string
  source: string
  time: string
  url: string
  type: 'news' | 'announcement'
}

export interface NewsResponse {
  symbol: string  // 主字段：6位股票代码
  code?: string   // 兼容字段（已废弃）
  days: number
  limit: number
  include_announcements: boolean
  source?: string
  items: NewsItem[]
}

export interface MarketIndexItem {
  name: string
  market: string
  value?: number
  chg?: number
  open?: number
  high?: number
  low?: number
  volume?: number
  source?: string
}

export interface MarketSectorItem {
  name: string
  chg?: number
  volume?: number
  source?: string
}

export interface MarketMetricItem {
  name: string
  value: string
  desc: string
}

export interface MarketSentiment {
  yesterday_limit_up_up_rate?: number | null
  lianban_upgrade_rate?: number | null
  limit_break_rate?: number | null
}

export interface MarketSentimentDetailItem {
  success: number
  total: number
  stocks?: Array<{
    code: string
    name: string
  }>
}

export interface MarketSentimentDetail {
  yesterday_limit_up_up_rate?: MarketSentimentDetailItem
  lianban_upgrade_rate?: MarketSentimentDetailItem
  limit_break_rate?: MarketSentimentDetailItem
}

export interface MarketLimitChange {
  today_up: number
  today_down: number
  yesterday_up: number
  yesterday_down: number
  up_change: number
  down_change: number
}

export interface MarketLimitProgression {
  from: number
  to: number
  count: number
}

export interface MarketLimitupConcept {
  concept: string
  today: number
  yesterday: number
  change: number
}

export interface MarketPromotionRate {
  from: number
  to: number
  success: number
  total: number
  rate?: number | null
  stocks?: Array<{
    code: string
    name: string
  }>
}

export interface SectorLimitUpItem {
  name: string
  count: number
  stocks?: Array<{
    code: string
    name: string
  }>
}

export interface LimitupAnalysisSentimentItem {
  success: number
  total: number
  rate?: number | null
}

export interface LimitupAnalysisSentimentDetailItem {
  success: number
  total: number
  stocks?: Array<{
    code: string
    name?: string
    reason?: string
  }>
}

export interface LimitupAnalysisSentimentDetail {
  yesterday_up: LimitupAnalysisSentimentDetailItem
  lianban: LimitupAnalysisSentimentDetailItem
  break: LimitupAnalysisSentimentDetailItem
}

export interface LimitupAnalysisLimitChange {
  selected_up: number
  selected_down: number
  previous_up: number
  previous_down: number
  up_change: number
  down_change: number
}

export interface LimitupAnalysisConceptItem {
  concept: string
  today: number
  yesterday: number
  change: number
  today_stocks?: Array<{
    code: string
    name?: string
  }>
  yesterday_stocks?: Array<{
    code: string
    name?: string
  }>
}

export interface LimitupAnalysisContinuousItem {
  code: string
  name?: string
  days?: number
  price?: number
  reason?: string
  first_time?: string
  last_time?: string
  order_volume?: number
  order_amount?: number
  limit_type?: string
}

export interface LimitupAnalysisPromotionRate {
  from: number
  to: number
  success: number
  total: number
  rate?: number | null
  stocks?: Array<{
    code: string
    name?: string
    reason?: string
  }>
}

export interface LimitupAnalysisResponse {
  selected_date?: string | null
  previous_date?: string | null
  sentiment: {
    yesterday_up: LimitupAnalysisSentimentItem
    lianban: LimitupAnalysisSentimentItem
    break: LimitupAnalysisSentimentItem
  }
  sentiment_detail?: LimitupAnalysisSentimentDetail
  limit_change: LimitupAnalysisLimitChange
  concepts: LimitupAnalysisConceptItem[]
  continuous: LimitupAnalysisContinuousItem[]
  promotion_rates: LimitupAnalysisPromotionRate[]
}

export interface MarketOverviewResponse {
  updated_at: string
  indices: MarketIndexItem[]
  sectors: MarketSectorItem[]
  watchlist: Array<{
    code: string
    name: string
    price?: number
    chg?: number
    volume?: number
  }>
  watchlist_source?: 'favorites' | 'market'
  metrics: MarketMetricItem[]
  filters: {
    industries: string[]
    markets: string[]
    risks: string[]
  }
  sentiment?: MarketSentiment
  sentiment_detail?: MarketSentimentDetail
  limit_change?: MarketLimitChange
  limit_progression?: MarketLimitProgression[]
  promotion_rates?: MarketPromotionRate[]
  limitup_concepts?: MarketLimitupConcept[]
  sector_limitup?: SectorLimitUpItem[]
}

export const stocksApi = {
  /**
   * 获取股票行情
   * @param symbol 6位股票代码
   */
  async getQuote(symbol: string) {
    return ApiClient.get<QuoteResponse>(`/api/stocks/${symbol}/quote`)
  },

  /**
   * 获取股票基本面数据
   * @param symbol 6位股票代码
   */
  async getFundamentals(symbol: string) {
    return ApiClient.get<FundamentalsResponse>(`/api/stocks/${symbol}/fundamentals`)
  },

  /**
   * 获取K线数据
   * @param symbol 6位股票代码
   * @param period K线周期
   * @param limit 数据条数
   * @param adj 复权方式
   */
  async getKline(symbol: string, period: KlineResponse['period'] = 'day', limit = 120, adj: KlineResponse['adj'] = 'none') {
    return ApiClient.get<KlineResponse>(`/api/stocks/${symbol}/kline`, { period, limit, adj })
  },

  /**
   * 获取股票新闻
   * @param symbol 6位股票代码
   * @param days 天数
   * @param limit 数量限制
   * @param includeAnnouncements 是否包含公告
   */
  async getNews(symbol: string, days = 30, limit = 50, includeAnnouncements = true) {
    return ApiClient.get<NewsResponse>(`/api/stocks/${symbol}/news`, { days, limit, include_announcements: includeAnnouncements })
  },

  async getMarketOverview(sectorLimit = 12) {
    return ApiClient.get<MarketOverviewResponse>('/api/stocks/market/overview', { sector_limit: sectorLimit })
  },

  async getLimitupAnalysis(date?: string) {
    return ApiClient.get<LimitupAnalysisResponse>('/api/stocks/market/limitup-analysis', { date })
  }
}
