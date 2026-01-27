/**
 * 个人交易计划 API
 */
import { ApiClient } from './request'

// ==================== 类型定义 ====================

/** 交易风格 */
export type TradingStyle = 'short_term' | 'medium_term' | 'long_term'

/** 风险偏好 */
export type RiskProfile = 'conservative' | 'balanced' | 'aggressive'

/** 交易计划状态 */
export type TradingSystemStatus = 'draft' | 'published'

/** 选股规则 */
export interface StockSelectionRule {
  analysis_config?: Record<string, any>
  must_have?: Array<Record<string, any>>
  exclude?: Array<Record<string, any>>
  bonus?: Array<Record<string, any>>
}

/** 择时规则 */
export interface TimingRule {
  market_condition?: Record<string, any>
  sector_condition?: Record<string, any>
  entry_signals?: Array<Record<string, any>>
  confirmation?: Array<Record<string, any>>
}

/** 仓位规则 */
export interface PositionRule {
  total_position?: Record<string, number>
  max_per_stock?: number
  max_holdings?: number
  min_holdings?: number
  scaling?: Record<string, any>
}

/** 持仓规则 */
export interface HoldingRule {
  review_frequency?: string
  add_conditions?: Array<Record<string, any>>
  reduce_conditions?: Array<Record<string, any>>
  switch_conditions?: Array<Record<string, any>>
}

/** 风险管理规则 */
export interface RiskManagementRule {
  stop_loss?: Record<string, any>
  take_profit?: Record<string, any>
  time_stop?: Record<string, any>
  logical_stop?: Record<string, any>
}

/** 复盘规则 */
export interface ReviewRule {
  frequency?: string
  checklist?: string[]
  case_save?: Record<string, any>
}

/** 纪律规则 */
export interface DisciplineRule {
  must_not?: Array<Record<string, any>>
  must_do?: Array<Record<string, any>>
  violation_actions?: Array<Record<string, any>>
}

/** 交易计划 */
export interface TradingSystem {
  id?: string
  user_id: string
  name: string
  description?: string
  style: TradingStyle
  risk_profile: RiskProfile
  version: string
  status: TradingSystemStatus
  is_active: boolean

  stock_selection?: StockSelectionRule
  timing?: TimingRule
  position?: PositionRule
  holding?: HoldingRule
  risk_management?: RiskManagementRule
  review?: ReviewRule
  discipline?: DisciplineRule

  // 草稿数据（仅在已发布版本中存在）
  draft_data?: TradingSystemUpdatePayload | null
  draft_updated_at?: string | null

  created_at: string
  updated_at: string
}

/** 创建交易计划请求 */
export interface TradingSystemCreatePayload {
  name: string
  description?: string
  style?: TradingStyle
  risk_profile?: RiskProfile
  
  stock_selection?: StockSelectionRule
  timing?: TimingRule
  position?: PositionRule
  holding?: HoldingRule
  risk_management?: RiskManagementRule
  review?: ReviewRule
  discipline?: DisciplineRule
}

/** 更新交易计划请求 */
export interface TradingSystemUpdatePayload {
  name?: string
  description?: string
  style?: TradingStyle
  risk_profile?: RiskProfile
  is_active?: boolean
  
  stock_selection?: StockSelectionRule
  timing?: TimingRule
  position?: PositionRule
  holding?: HoldingRule
  risk_management?: RiskManagementRule
  review?: ReviewRule
  discipline?: DisciplineRule
}

/** API 响应 */
export interface ApiResponse<T = any> {
  success: boolean
  data: T
  message: string
}

// ==================== API 方法 ====================

/**
 * 创建交易计划
 */
export function createTradingSystem(payload: TradingSystemCreatePayload) {
  return ApiClient.post<{ system: TradingSystem }>('/api/v1/trading-systems', payload)
}

/**
 * 获取交易计划列表
 */
export function getTradingSystems(isActive?: boolean) {
  const params = isActive !== undefined ? { is_active: isActive } : {}
  return ApiClient.get<{ systems: TradingSystem[]; total: number }>('/api/v1/trading-systems', params)
}

/**
 * 获取激活的交易计划
 */
export function getActiveTradingSystem() {
  return ApiClient.get<{ system: TradingSystem | null }>('/api/v1/trading-systems/active')
}

/**
 * 获取交易计划详情
 */
export function getTradingSystem(systemId: string) {
  return ApiClient.get<{ system: TradingSystem }>(`/api/v1/trading-systems/${systemId}`)
}

/**
 * 更新交易计划
 */
export function updateTradingSystem(
  systemId: string,
  payload: TradingSystemUpdatePayload,
  saveAsDraft: boolean = false
) {
  const params = saveAsDraft ? { save_as_draft: true } : {}
  return ApiClient.put<{ system: TradingSystem }>(
    `/api/v1/trading-systems/${systemId}`,
    payload,
    { params }
  )
}

/**
 * 删除交易计划
 */
export function deleteTradingSystem(systemId: string) {
  return ApiClient.delete<void>(`/api/v1/trading-systems/${systemId}`)
}

/**
 * 激活交易计划
 */
export function activateTradingSystem(systemId: string) {
  return ApiClient.post<{ system: TradingSystem }>(`/api/v1/trading-systems/${systemId}/activate`, {})
}

/** 交易计划评估结果 */
export interface TradingPlanEvaluation {
  overall_score: number
  strengths: string[]
  weaknesses: string[]
  suggestions: string[]
  detailed_analysis: string
  evaluation_date: string
}

/**
 * AI评估交易计划（已保存的计划）
 */
export function evaluateTradingSystem(systemId: string) {
  return ApiClient.post<{ evaluation: TradingPlanEvaluation }>(`/api/v1/trading-systems/${systemId}/evaluate`, {})
}

/**
 * AI评估交易计划草稿（未保存的计划）
 */
export function evaluateTradingPlanDraft(payload: TradingSystemCreatePayload) {
  return ApiClient.post<{ evaluation: TradingPlanEvaluation }>('/api/v1/trading-systems/evaluate-draft', payload)
}

/**
 * 评估历史记录项
 */
export interface EvaluationHistoryItem {
  evaluation_id: string
  system_id: string
  system_name: string
  system_version: string
  overall_score: number
  grade: string
  created_at: string
  summary: string
}

/**
 * 评估历史列表响应
 */
export interface EvaluationHistoryResponse {
  items: EvaluationHistoryItem[]
  total: number
  page: number
  page_size: number
}

/**
 * 获取交易计划评估历史
 */
export function getEvaluationHistory(systemId: string, page: number = 1, pageSize: number = 10) {
  return ApiClient.get<EvaluationHistoryResponse>(`/api/v1/trading-systems/${systemId}/evaluations`, {
    params: { page, page_size: pageSize }
  })
}

/**
 * 获取评估详情
 */
export function getEvaluationDetail(evaluationId: string) {
  return ApiClient.get<{ evaluation: any }>(`/api/v1/trading-systems/evaluations/${evaluationId}`)
}

// ==================== 版本管理 ====================

/** 交易计划版本 */
export interface TradingSystemVersion {
  id?: string
  system_id: string
  version: string
  improvement_summary: string
  snapshot: TradingSystem
  created_at: string
  created_by: string
}

/** 创建版本请求 */
export interface TradingSystemVersionCreatePayload {
  improvement_summary: string
  new_version?: string
}

/**
 * 创建交易计划新版本
 */
export function createTradingSystemVersion(systemId: string, payload: TradingSystemVersionCreatePayload) {
  return ApiClient.post<{ version: TradingSystemVersion }>(`/api/v1/trading-systems/${systemId}/versions`, payload)
}

/**
 * 获取交易计划的所有版本
 */
export function getTradingSystemVersions(systemId: string) {
  return ApiClient.get<{ versions: TradingSystemVersion[]; total: number }>(`/api/v1/trading-systems/${systemId}/versions`)
}

/**
 * 获取版本详情
 */
export function getTradingSystemVersion(versionId: string) {
  return ApiClient.get<{ version: TradingSystemVersion }>(`/api/v1/trading-systems/versions/${versionId}`)
}

/**
 * 发布交易计划（创建新版本并更新状态为已发布）
 */
export interface TradingSystemPublishPayload {
  improvement_summary: string
  new_version?: string
  update_data?: TradingSystemUpdatePayload
}

export function publishTradingSystem(
  systemId: string,
  publishPayload: TradingSystemPublishPayload
) {
  return ApiClient.post<{ system: TradingSystem }>(
    `/api/v1/trading-systems/${systemId}/publish`,
    publishPayload
  )
}

