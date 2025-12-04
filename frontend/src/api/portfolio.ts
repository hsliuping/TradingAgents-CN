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
}

/** 价格目标 */
export interface PriceTargets {
  stop_loss_price?: number
  stop_loss_pct?: number
  take_profit_price?: number
  take_profit_pct?: number
  breakeven_price?: number
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
  }
}

