import { ApiClient } from './request'
import type { FactorDiagnosticPayload, FactorWarningPayload } from './screening'

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
  security_type?: string
  fund_type?: string
  track_index?: string
  fund_scale?: string | number
  fund_share?: string | number
  fund_share_date?: string
  management?: string
  custodian?: string
  management_fee?: string | number
  custodian_fee?: string | number
  unit_nav?: number
  accum_nav?: number
  nav_change_value?: number
  nav_growth_rate?: string | number
  market_price?: number
  premium_discount_rate?: string | number
  latest_nav_date?: string
  purchase_status?: string
  redemption_status?: string
  pe?: number
  pb?: number
  ps?: number      // 🔥 新增：市销率
  pe_ttm?: number
  pb_mrq?: number
  ps_ttm?: number  // 🔥 新增：市销率（TTM）
  roe?: number
  roa?: number
  debt_ratio?: number  // 🔥 新增：负债率
  debt_to_assets?: number
  dividend_yield?: number
  dividend_yield_ttm?: number
  current_ratio?: number
  quick_ratio?: number
  cash_ratio?: number
  assets_to_eqt?: number
  gross_margin?: number
  netprofit_margin?: number
  revenue?: number
  revenue_ttm?: number
  net_income?: number
  net_profit?: number
  net_profit_ttm?: number
  oper_profit?: number
  total_profit?: number
  total_assets?: number
  total_liab?: number
  total_equity?: number
  n_cashflow_act?: number
  report_period?: string
  report_type?: string
  ann_date?: string
  financial_data_source?: string
  total_mv?: number
  circ_mv?: number
  turnover_rate?: number
  volume_ratio?: number
  pe_is_realtime?: boolean  // PE是否为实时数据
  pe_source?: string        // PE数据来源
  pe_updated_at?: string    // PE更新时间
  factor_diagnostics?: Record<string, FactorDiagnosticPayload>
  factor_warnings?: Record<string, FactorWarningPayload>
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

export interface DataValidationResponse {
  is_valid: boolean
  message: string
  missing_data: string[]
  details: Record<string, any>
}

export interface StockFinancialSummary {
  report_period?: string
  report_type?: string
  ann_date?: string
  data_source?: string
  revenue?: number
  revenue_ttm?: number
  oper_rev?: number
  net_income?: number
  net_profit?: number
  net_profit_ttm?: number
  oper_profit?: number
  total_profit?: number
  gross_margin?: number
  netprofit_margin?: number
  roe?: number
  roa?: number
  roe_waa?: number
  roe_dt?: number
  debt_to_assets?: number
  assets_to_eqt?: number
  current_ratio?: number
  quick_ratio?: number
  cash_ratio?: number
  total_assets?: number
  total_liab?: number
  total_equity?: number
  total_cur_assets?: number
  total_cur_liab?: number
  money_cap?: number
  accounts_receiv?: number
  inventories?: number
  fix_assets?: number
  n_cashflow_act?: number
  n_cashflow_inv_act?: number
  n_cashflow_fin_act?: number
  c_cash_equ_end_period?: number
  c_cash_equ_beg_period?: number
  updated_at?: string
}

export interface StockFinancialsResponse {
  code: string
  name?: string
  data_source?: string
  report_period?: string
  report_type?: string
  ann_date?: string
  summary: StockFinancialSummary
  factor_snapshot?: Record<string, number | string | null>
  factor_diagnostics?: Record<string, FactorDiagnosticPayload>
  factor_warnings?: Record<string, FactorWarningPayload>
  raw_data?: Record<string, any[]>
  available_fields: string[]
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
   * 数据校验
   * @param symbol 股票代码
   * @param analysisDate 分析日期（YYYY-MM-DD）
   * @param marketType 市场类型（cn/hk/us）
   * @param options 校验选项
   */
  async validateData(
    symbol: string,
    analysisDate?: string,
    marketType: string = 'cn',
    options?: {
      check_basic_info?: boolean
      check_historical_data?: boolean
      check_financial_data?: boolean
      check_realtime_quotes?: boolean
    }
  ) {
    const params = new URLSearchParams({
      symbol,
      market_type: marketType,
      ...(analysisDate && { analysis_date: analysisDate }),
      ...(options?.check_basic_info !== undefined && { check_basic_info: String(options.check_basic_info) }),
      ...(options?.check_historical_data !== undefined && { check_historical_data: String(options.check_historical_data) }),
      ...(options?.check_financial_data !== undefined && { check_financial_data: String(options.check_financial_data) }),
      ...(options?.check_realtime_quotes !== undefined && { check_realtime_quotes: String(options.check_realtime_quotes) })
    })
    return ApiClient.get<DataValidationResponse>(`/api/stock-sync/validate?${params.toString()}`)
  },

  /**
   * 获取股票基本面数据
   * @param symbol 6位股票代码
   */
  async getFundamentals(symbol: string) {
    return ApiClient.get<FundamentalsResponse>(`/api/stocks/${symbol}/fundamentals`)
  },

  /**
   * 获取股票最新财务明细
   * @param symbol 6位股票代码
   * @param options includeRaw: 是否返回 raw_data 分组明细
   */
  async getFinancials(symbol: string, options?: { source?: string; includeRaw?: boolean }) {
    return ApiClient.get<StockFinancialsResponse>(
      `/api/stocks/${symbol}/financials`,
      {
        ...(options?.source ? { source: options.source } : {}),
        ...(options?.includeRaw !== undefined ? { include_raw: String(options.includeRaw) } : {}),
      },
      { skipErrorHandler: true }
    )
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
  }
}

