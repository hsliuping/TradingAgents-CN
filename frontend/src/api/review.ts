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
  plan_adherence?: string  // 计划执行情况
  plan_deviation?: string   // 偏离说明
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
  trading_system_id?: string  // 关联的交易计划ID
  trading_system_name?: string  // 关联的交易计划名称
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
  name?: string
  market?: string
  status?: 'completed' | 'holding'  // completed=已完成交易, holding=持仓中
  buy_count: number
  sell_count: number
  total_pnl: number
  total_buy_amount?: number
  total_sell_amount?: number
  last_trade_time?: string
}

// ==================== 请求类型 ====================

/** 创建复盘请求 */
export interface CreateTradeReviewRequest {
  trade_ids: string[]
  review_type?: ReviewType
  code?: string
  source?: 'real' | 'paper'  // 数据源：真实持仓或模拟持仓
  trading_system_id?: string  // 关联的交易计划ID
  use_workflow?: boolean  // 是否使用工作流引擎（v2.0）
}

/** 保存案例请求 */
export interface SaveAsCaseRequest {
  review_id: string
  tags?: string[]
}

/** 复盘历史筛选参数 */
export interface ReviewHistoryFilter {
  page?: number
  pageSize?: number
  code?: string
  startDate?: string
  endDate?: string
  reviewType?: ReviewType
}

/** 可复盘交易筛选参数 */
export interface ReviewableTradesFilter {
  code?: string
  startDate?: string
  endDate?: string
  page?: number
  pageSize?: number
}

/** 阶段性复盘周期类型 */
export type PeriodType = 'week' | 'month' | 'quarter' | 'year'

/** 创建阶段性复盘请求 */
export interface CreatePeriodicReviewRequest {
  period_type: PeriodType
  start_date: string
  end_date: string
  source?: 'paper' | 'position'  // 数据源: paper(模拟交易) 或 position(持仓操作)
}

/** AI阶段性复盘结果 */
export interface AIPeriodicReview {
  overall_score: number
  summary: string
  trading_style: string
  common_mistakes: string[]
  improvement_areas: string[]
  action_plan: string[]
  best_trade?: string
  worst_trade?: string
}

/** 交易摘要项 */
export interface TradeSummaryItem {
  code: string
  name?: string
  side: string
  quantity: number
  price: number
  pnl: number
  pnl_pct: number
  timestamp: string
}

/** 阶段性复盘报告 */
export interface PeriodicReviewReport {
  review_id: string
  period_type: PeriodType
  period_start: string
  period_end: string
  statistics: TradingStatistics
  trades_summary: TradeSummaryItem[]
  ai_review: AIPeriodicReview
  status: ReviewStatus
  execution_time?: number
  created_at: string
}

/** 阶段性复盘列表项 */
export interface PeriodicReviewListItem {
  review_id: string
  period_type: PeriodType
  period_start: string
  period_end: string
  source?: 'paper' | 'position'
  total_trades: number
  total_pnl: number
  win_rate: number
  overall_score: number
  status: ReviewStatus
  created_at: string
}

// ==================== API 方法 ====================

export const reviewApi = {
  /** 创建交易复盘 */
  async createTradeReview(data: CreateTradeReviewRequest) {
    return ApiClient.post<TradeReviewReport>('/api/review/trade', data, {
      showLoading: true,
      timeout: 600000,  // 600秒超时（10分钟）
      retryCount: 0     // 禁用重试，避免重复分析
    })
  },

  /** 获取复盘历史列表，支持筛选 */
  async getReviewHistory(filter: ReviewHistoryFilter = {}) {
    const { page = 1, pageSize = 10, code, startDate, endDate, reviewType } = filter
    return ApiClient.get<{ items: ReviewListItem[]; total: number; page: number; page_size: number }>(
      '/api/review/trade/history',
      {
        page,
        page_size: pageSize,
        code,
        start_date: startDate,
        end_date: endDate,
        review_type: reviewType
      }
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
  async getCases(params: { page?: number; pageSize?: number; source?: 'paper' | 'position' } = {}) {
    const { page = 1, pageSize = 10, source } = params
    const queryParams: Record<string, any> = { page, page_size: pageSize }
    if (source) {
      queryParams.source = source
    }
    return ApiClient.get<{ items: ReviewListItem[]; total: number; page: number; page_size: number }>(
      '/api/review/cases',
      queryParams
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

  /** 获取可复盘的交易列表，支持筛选 */
  async getReviewableTrades(filter: ReviewableTradesFilter = {}) {
    const { code, startDate, endDate, page = 1, pageSize = 20 } = filter
    return ApiClient.get<{
      items: TradeRecord[]
      total: number
      page: number
      page_size: number
      completed_stocks: ReviewableStock[]
      all_stocks: ReviewableStock[]  // 所有有交易的股票（包括只买入的）
    }>('/api/review/reviewable-trades', {
      code,
      start_date: startDate,
      end_date: endDate,
      page,
      page_size: pageSize
    })
  },

  /** 获取某只股票的所有交易 */
  async getTradesByCode(code: string, source: 'real' | 'paper' = 'real') {
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
    }>(`/api/review/trades-by-code/${code}`, { source })
  },

  // ==================== 阶段性复盘 ====================

  /** 创建阶段性复盘 */
  async createPeriodicReview(data: CreatePeriodicReviewRequest) {
    return ApiClient.post<PeriodicReviewReport>('/api/review/periodic', data, {
      showLoading: true,
      timeout: 600000,  // 600秒超时（10分钟）
      retryCount: 0     // 禁用重试，避免重复分析
    })
  },

  /** 获取阶段性复盘历史 */
  async getPeriodicReviewHistory(page = 1, pageSize = 10, source?: 'paper' | 'position') {
    const params: Record<string, any> = { page, page_size: pageSize }
    if (source) {
      params.source = source
    }
    return ApiClient.get<{ items: PeriodicReviewListItem[]; total: number; page: number; page_size: number }>(
      '/api/review/periodic/history',
      params
    )
  },

  /** 获取阶段性复盘详情 */
  async getPeriodicReviewDetail(reviewId: string) {
    return ApiClient.get<PeriodicReviewReport>(`/api/review/periodic/${reviewId}`)
  }
}

