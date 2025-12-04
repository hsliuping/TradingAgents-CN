/**
 * 交易复盘 API
 */
import { ApiClient } from './request'

// ==================== 类型定义 ====================

/** 复盘类型 */
export type ReviewType = 'single_trade' | 'complete_trade' | 'periodic'

/** 复盘状态 */
export type ReviewStatus = 'pending' | 'processing' | 'completed' | 'failed'

/** 交易方向 */
export type TradeSide = 'buy' | 'sell'

/** 交易记录 */
export interface TradeRecord {
  trade_id: string
  code: string
  market: string
  side: TradeSide
  quantity: number
  price: number
  amount: number
  pnl: number
  commission: number
  timestamp: string
}

/** 交易信息汇总 */
export interface TradeInfo {
  code: string
  name?: string
  market: string
  trades: TradeRecord[]
  total_buy_quantity: number
  total_sell_quantity: number
  avg_buy_price: number
  avg_sell_price: number
  total_buy_amount: number
  total_sell_amount: number
  total_commission: number
  realized_pnl: number
  realized_pnl_pct: number
  first_buy_date?: string
  last_sell_date?: string
  holding_days: number
}

/** 市场数据快照 */
export interface MarketSnapshot {
  period_high?: number
  period_high_date?: string
  period_low?: number
  period_low_date?: string
  buy_date_open?: number
  buy_date_high?: number
  buy_date_low?: number
  buy_date_close?: number
  sell_date_open?: number
  sell_date_high?: number
  sell_date_low?: number
  sell_date_close?: number
  optimal_buy_price?: number
  optimal_buy_date?: string
  optimal_sell_price?: number
  optimal_sell_date?: string
  kline_data?: Array<{
    date: string
    open: number
    high: number
    low: number
    close: number
    volume: number
  }>
}

/** AI复盘分析结果 */
export interface AITradeReview {
  overall_score: number
  timing_score?: number
  position_score?: number
  discipline_score?: number
  summary: string
  strengths: string[]
  weaknesses: string[]
  suggestions: string[]
  timing_analysis?: string
  position_analysis?: string
  emotion_analysis?: string
  actual_pnl?: number
  optimal_pnl?: number
  missed_profit?: number
  avoided_loss?: number
}

/** 复盘报告 */
export interface TradeReviewReport {
  review_id: string
  review_type: ReviewType
  status: ReviewStatus
  trade_info: TradeInfo
  market_snapshot: MarketSnapshot
  ai_review: AITradeReview
  is_case_study: boolean
  tags: string[]
  execution_time?: number
  created_at: string
}

/** 复盘列表项 */
export interface ReviewListItem {
  review_id: string
  review_type: ReviewType
  code?: string
  name?: string
  realized_pnl: number
  overall_score: number
  status: ReviewStatus
  is_case_study: boolean
  created_at: string
}

/** 交易统计 */
export interface TradingStatistics {
  total_trades: number
  winning_trades: number
  losing_trades: number
  win_rate: number
  total_pnl: number
  avg_profit: number
  avg_loss: number
  profit_loss_ratio: number
  max_single_profit: number
  max_single_loss: number
  total_commission: number
}

/** 可复盘的股票 */
export interface ReviewableStock {
  code: string
  buy_count: number
  sell_count: number
  total_pnl: number
}

// ==================== 请求类型 ====================

/** 创建复盘请求 */
export interface CreateTradeReviewRequest {
  trade_ids: string[]
  review_type?: ReviewType
  code?: string
}

/** 保存案例请求 */
export interface SaveAsCaseRequest {
  review_id: string
  tags?: string[]
}

// ==================== API 方法 ====================

export const reviewApi = {
  /** 创建交易复盘 */
  async createTradeReview(data: CreateTradeReviewRequest) {
    return ApiClient.post<TradeReviewReport>('/api/review/trade', data, { showLoading: true })
  },

  /** 获取复盘历史列表 */
  async getReviewHistory(page = 1, pageSize = 10) {
    return ApiClient.get<{ items: ReviewListItem[]; total: number; page: number; page_size: number }>(
      '/api/review/trade/history',
      { page, page_size: pageSize }
    )
  },

  /** 获取复盘详情 */
  async getReviewDetail(reviewId: string) {
    return ApiClient.get<TradeReviewReport>(`/api/review/trade/${reviewId}`)
  },

  /** 保存为案例 */
  async saveAsCase(data: SaveAsCaseRequest) {
    return ApiClient.post<{ message: string }>('/api/review/case', data, { showLoading: true })
  },

  /** 获取案例库 */
  async getCases(page = 1, pageSize = 10) {
    return ApiClient.get<{ items: ReviewListItem[]; total: number; page: number; page_size: number }>(
      '/api/review/cases',
      { page, page_size: pageSize }
    )
  },

  /** 从案例库删除 */
  async deleteCase(reviewId: string) {
    return ApiClient.delete<{ message: string }>(`/api/review/case/${reviewId}`, { showLoading: true })
  },

  /** 获取交易统计 */
  async getTradingStatistics(startDate?: string, endDate?: string) {
    return ApiClient.get<TradingStatistics>('/api/review/statistics', {
      start_date: startDate,
      end_date: endDate
    })
  },

  /** 获取可复盘的交易列表 */
  async getReviewableTrades(code?: string, page = 1, pageSize = 20) {
    return ApiClient.get<{
      items: TradeRecord[]
      total: number
      page: number
      page_size: number
      completed_stocks: ReviewableStock[]
    }>('/api/review/reviewable-trades', { code, page, page_size: pageSize })
  },

  /** 获取某只股票的所有交易 */
  async getTradesByCode(code: string) {
    return ApiClient.get<{
      code: string
      trades: TradeRecord[]
      summary: {
        total_trades: number
        total_buy_quantity: number
        total_sell_quantity: number
        total_pnl: number
        is_closed: boolean
      }
    }>(`/api/review/trades-by-code/${code}`)
  }
}

