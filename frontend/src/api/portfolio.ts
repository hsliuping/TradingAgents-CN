/**
 * 持仓分析 API
 */
import { ApiClient } from './request'

// ==================== 类型定义 ====================

/** 持仓数据来源 */
export type PositionSource = 'real' | 'paper' | 'all'

/** 持仓项 */
export interface PositionItem {
  id: string
  code: string
  name?: string
  market: string
  currency: string
  quantity: number
  cost_price: number
  current_price?: number
  market_value?: number
  unrealized_pnl?: number
  unrealized_pnl_pct?: number
  buy_date?: string
  industry?: string
  notes?: string
  source: string
  created_at: string
  updated_at: string
}

/** 添加持仓请求 */
export interface PositionCreatePayload {
  code: string
  name?: string
  market?: string
  quantity: number
  cost_price: number
  buy_date?: string
  notes?: string
}

/** 更新持仓请求 */
export interface PositionUpdatePayload {
  name?: string
  quantity?: number
  cost_price?: number
  buy_date?: string
  notes?: string
}

/** 行业分布 */
export interface IndustryDistribution {
  industry: string
  value: number
  percentage: number
  count: number
}

/** 持仓统计 */
export interface PortfolioStats {
  total_positions: number
  total_value: number
  total_cost: number
  unrealized_pnl: number
  unrealized_pnl_pct: number
  industry_distribution: IndustryDistribution[]
  market_distribution: Record<string, number>
}

/** 持仓快照 */
export interface PositionSnapshot {
  code: string
  name?: string
  market: string
  quantity: number
  cost_price: number
  current_price?: number
  market_value?: number
  unrealized_pnl?: number
  unrealized_pnl_pct?: number
  industry?: string
  holding_days?: number
}

/** 组合快照 */
export interface PortfolioSnapshot {
  total_positions: number
  total_value: number
  total_cost: number
  unrealized_pnl: number
  unrealized_pnl_pct: number
  positions: PositionSnapshot[]
}

/** 集中度分析 */
export interface ConcentrationAnalysis {
  top1_pct: number
  top3_pct: number
  top5_pct: number
  hhi_index: number
  industry_count: number
}

/** AI分析结果 */
export interface AIAnalysisResult {
  summary: string
  strengths: string[]
  weaknesses: string[]
  suggestions: string[]
  detailed_report?: string
}

/** 分析报告 */
export interface PortfolioAnalysisReport {
  analysis_id: string
  status: 'pending' | 'processing' | 'completed' | 'failed'
  health_score?: number
  risk_level?: string
  portfolio_snapshot: PortfolioSnapshot
  industry_distribution: IndustryDistribution[]
  concentration_analysis: ConcentrationAnalysis
  ai_analysis: AIAnalysisResult
  execution_time?: number
  error_message?: string
  created_at: string
}

/** 分析请求 */
export interface AnalysisRequestPayload {
  include_paper?: boolean
  research_depth?: string
}

// ==================== 单股持仓分析类型 ====================

/** 单股分析请求参数 */
export interface PositionAnalysisParams {
  research_depth?: string
  include_add_position?: boolean
  target_profit_pct?: number
  // 资金总量相关（用于风险分析）
  total_capital?: number          // 投资资金总量
  max_position_pct?: number       // 单只股票最大仓位比例（%），默认30
  max_loss_pct?: number           // 最大可接受亏损比例（%），默认10
}

/** 价格目标 */
export interface PriceTargets {
  stop_loss_price?: number
  stop_loss_pct?: number
  take_profit_price?: number
  take_profit_pct?: number
  breakeven_price?: number
}

/** 持仓风险指标 */
export interface PositionRiskMetrics {
  position_pct?: number           // 仓位占比（%）
  position_value?: number         // 持仓市值
  max_loss_amount?: number        // 最大可能亏损金额
  max_loss_impact_pct?: number    // 最大亏损对总资金影响（%）
  available_add_amount?: number   // 可加仓金额
  risk_level?: 'low' | 'medium' | 'high' | 'critical'  // 风险等级
  risk_summary?: string           // 风险概述
}

/** 单股持仓分析结果 */
export interface PositionAnalysisResult {
  analysis_id: string
  position_id: string
  code: string
  name?: string
  status: 'pending' | 'processing' | 'completed' | 'failed'
  action: 'add' | 'reduce' | 'hold' | 'clear'
  action_reason: string
  confidence: number
  price_targets: PriceTargets
  risk_assessment: string
  opportunity_assessment: string
  detailed_analysis: string
  suggested_quantity?: number     // 建议操作数量
  suggested_amount?: number       // 建议操作金额
  risk_metrics?: PositionRiskMetrics  // 风险指标（基于资金总量计算）
  execution_time?: number
  error_message?: string
  created_at: string
}

// ==================== API 方法 ====================

export const portfolioApi = {
  /** 获取持仓列表 */
  async getPositions(source: PositionSource = 'all') {
    return ApiClient.get<{ items: PositionItem[]; total: number }>(
      '/api/portfolio/positions',
      { source }
    )
  },

  /** 添加持仓 */
  async addPosition(data: PositionCreatePayload) {
    return ApiClient.post<PositionItem>('/api/portfolio/positions', data, { showLoading: true })
  },

  /** 更新持仓 */
  async updatePosition(positionId: string, data: PositionUpdatePayload) {
    return ApiClient.put<PositionItem>(`/api/portfolio/positions/${positionId}`, data, { showLoading: true })
  },

  /** 删除持仓 */
  async deletePosition(positionId: string) {
    return ApiClient.delete(`/api/portfolio/positions/${positionId}`, { showLoading: true })
  },

  /** 批量导入持仓 */
  async importPositions(positions: PositionCreatePayload[]) {
    return ApiClient.post<{ success_count: number; failed_count: number; errors: any[] }>(
      '/api/portfolio/positions/import',
      { positions },
      { showLoading: true }
    )
  },

  /** 获取持仓统计 */
  async getStatistics() {
    return ApiClient.get<PortfolioStats>('/api/portfolio/statistics')
  },

  /** 发起持仓分析 */
  async analyzePortfolio(params?: AnalysisRequestPayload) {
    return ApiClient.post<PortfolioAnalysisReport>('/api/portfolio/analysis', params || {}, { showLoading: true })
  },

  /** 获取分析历史 */
  async getAnalysisHistory(page = 1, pageSize = 10) {
    return ApiClient.get<{ items: PortfolioAnalysisReport[]; total: number; page: number; page_size: number }>(
      '/api/portfolio/analysis/history',
      { page, page_size: pageSize }
    )
  },

  /** 获取分析详情 */
  async getAnalysisDetail(analysisId: string) {
    return ApiClient.get<PortfolioAnalysisReport>(`/api/portfolio/analysis/${analysisId}`)
  },

  // ==================== 单股持仓分析 ====================

  /** 获取单个持仓详情 */
  async getPositionDetail(positionId: string) {
    return ApiClient.get<PositionItem>(`/api/portfolio/positions/${positionId}`)
  },

  /** 发起单股持仓分析 */
  async analyzePosition(positionId: string, params?: PositionAnalysisParams) {
    return ApiClient.post<PositionAnalysisResult>(
      `/api/portfolio/positions/${positionId}/analysis`,
      params || {},
      { showLoading: true }
    )
  },

  /** 获取单股分析历史 */
  async getPositionAnalysisHistory(positionId: string, page = 1, pageSize = 10) {
    return ApiClient.get<{ items: PositionAnalysisResult[]; total: number; page: number; page_size: number }>(
      `/api/portfolio/positions/${positionId}/analysis/history`,
      { page, page_size: pageSize }
    )
  },

  // ==================== 资金账户 API ====================

  /** 获取资金账户 */
  async getAccount() {
    return ApiClient.get<RealAccount>('/api/portfolio/account')
  },

  /** 获取账户摘要（含持仓市值和收益） */
  async getAccountSummary() {
    return ApiClient.get<AccountSummary>('/api/portfolio/account/summary')
  },

  /** 初始化资金账户 */
  async initializeAccount(initial_capital: number, currency = 'CNY') {
    return ApiClient.post<RealAccount>('/api/portfolio/account/initialize', {
      initial_capital,
      currency
    })
  },

  /** 入金 */
  async deposit(amount: number, currency = 'CNY', description?: string) {
    return ApiClient.post<RealAccount>('/api/portfolio/account/deposit', {
      transaction_type: 'deposit',
      amount,
      currency,
      description
    })
  },

  /** 出金 */
  async withdraw(amount: number, currency = 'CNY', description?: string) {
    return ApiClient.post<RealAccount>('/api/portfolio/account/withdraw', {
      transaction_type: 'withdraw',
      amount,
      currency,
      description
    })
  },

  /** 更新账户设置 */
  async updateAccountSettings(settings: AccountSettingsParams) {
    return ApiClient.put<RealAccount>('/api/portfolio/account/settings', settings)
  },

  /** 获取资金交易记录 */
  async getTransactions(currency?: string, limit = 50) {
    return ApiClient.get<{ items: CapitalTransaction[]; total: number }>(
      '/api/portfolio/account/transactions',
      { currency, limit }
    )
  },

  // ==================== 持仓变动记录 API ====================

  /** 获取持仓变动记录 */
  async getPositionChanges(params?: PositionChangeQueryParams) {
    return ApiClient.get<{ items: PositionChange[]; total: number; limit: number; skip: number }>(
      '/api/portfolio/position-changes',
      params || {}
    )
  }
}

// ==================== 资金账户类型定义 ====================

/** 资金账户 */
export interface RealAccount {
  user_id: string
  cash: Record<string, number>
  initial_capital: Record<string, number>
  total_deposit: Record<string, number>
  total_withdraw: Record<string, number>
  settings: {
    default_market: string
    max_position_pct: number
    max_loss_pct: number
  }
  created_at: string
  updated_at: string
}

/** 账户摘要 */
export interface AccountSummary {
  cash: Record<string, number>
  initial_capital: Record<string, number>
  total_deposit: Record<string, number>
  total_withdraw: Record<string, number>
  net_capital: Record<string, number>
  positions_value: Record<string, number>
  total_assets: Record<string, number>
  profit: Record<string, number>
  profit_pct: Record<string, number>
  settings: Record<string, any>
}

/** 资金交易记录 */
export interface CapitalTransaction {
  id: string
  user_id: string
  transaction_type: 'initial' | 'deposit' | 'withdraw' | 'dividend' | 'adjustment'
  amount: number
  currency: string
  balance_before: number
  balance_after: number
  description?: string
  created_at: string
}

/** 账户设置参数 */
export interface AccountSettingsParams {
  max_position_pct?: number
  max_loss_pct?: number
  default_market?: string
}

// ==================== 持仓变动记录类型定义 ====================

/** 持仓变动类型 */
export type PositionChangeType = 'buy' | 'add' | 'reduce' | 'sell' | 'adjust'

/** 持仓变动记录 */
export interface PositionChange {
  id: string
  user_id: string
  position_id?: string
  code: string
  name: string
  market: string
  currency: string
  change_type: PositionChangeType
  quantity_before: number
  cost_price_before: number
  cost_value_before: number
  quantity_after: number
  cost_price_after: number
  cost_value_after: number
  quantity_change: number
  cash_change: number
  trade_price?: number
  realized_profit?: number
  description?: string
  created_at: string
}

/** 持仓变动查询参数 */
export interface PositionChangeQueryParams {
  code?: string
  market?: string
  change_type?: PositionChangeType
  limit?: number
  skip?: number
}

