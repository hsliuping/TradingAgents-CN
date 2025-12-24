/**
 * 个人交易计划 API
 */
import { ApiClient } from './request'

// ==================== 类型定义 ====================

/** 交易风格 */
export type TradingStyle = 'short_term' | 'medium_term' | 'long_term'

/** 风险偏好 */
export type RiskProfile = 'conservative' | 'balanced' | 'aggressive'

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
  is_active: boolean

  stock_selection?: StockSelectionRule
  timing?: TimingRule
  position?: PositionRule
  holding?: HoldingRule
  risk_management?: RiskManagementRule
  review?: ReviewRule
  discipline?: DisciplineRule

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
export function updateTradingSystem(systemId: string, payload: TradingSystemUpdatePayload) {
  return ApiClient.put<{ system: TradingSystem }>(`/api/v1/trading-systems/${systemId}`, payload)
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

