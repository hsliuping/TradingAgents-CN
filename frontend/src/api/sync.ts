/**
 * 多数据源同步相关API
 */
import { ApiClient } from './request'

// 数据源状态接口
export interface DataSourceStatus {
  name: string
  priority: number
  available: boolean
  description: string
  token_source?: 'database' | 'env'  // Token 来源（仅 Tushare）
}

// 同步状态接口
export interface SyncStatus {
  job: string
  status: 'idle' | 'running' | 'success' | 'success_with_errors' | 'failed' | 'never_run'
  started_at?: string
  finished_at?: string
  total: number
  inserted: number
  updated: number
  errors: number
  last_trade_date?: string
  data_sources_used: string[]
  source_stats?: Record<string, Record<string, number>>
  message?: string
}

// 同步请求参数
export interface SyncRequest {
  force?: boolean
  preferred_sources?: string[]
}

// API响应格式
export interface ApiResponse<T = any> {
  success: boolean
  message: string
  data: T
}

// 基础测试结果接口
export interface BaseTestResult {
  success: boolean
  message: string
  count?: number
  date?: string
}

// 测试结果接口（简化版）
export interface DataSourceTestResult {
  name: string
  priority: number
  available: boolean
  message: string
  token_source?: 'database' | 'env'  // Token 来源（仅 Tushare）
}

// 使用建议接口
export interface SyncRecommendations {
  primary_source?: {
    name: string
    priority: number
    reason: string
  }
  fallback_sources: Array<{
    name: string
    priority: number
  }>
  suggestions: string[]
  warnings: string[]
}

/**
 * 获取数据源状态
 */
export const getDataSourcesStatus = (): Promise<ApiResponse<DataSourceStatus[]>> => {
  return ApiClient.get('/api/sync/multi-source/sources/status')
}

/**
 * 获取当前正在使用的数据源
 */
export const getCurrentDataSource = (): Promise<ApiResponse<{
  name: string
  priority: number
  description: string
  token_source?: 'database' | 'env'
  token_source_display?: string
}>> => {
  return ApiClient.get('/api/sync/multi-source/sources/current')
}

/**
 * 获取同步状态
 */
export const getSyncStatus = (): Promise<ApiResponse<SyncStatus>> => {
  return ApiClient.get('/api/sync/multi-source/status')
}

/**
 * 运行股票基础信息同步
 */
export const runStockBasicsSync = (params?: {
  force?: boolean
  preferred_sources?: string
}): Promise<ApiResponse<SyncStatus>> => {
  const queryParams = new URLSearchParams()
  if (params?.force) {
    queryParams.append('force', 'true')
  }
  if (params?.preferred_sources) {
    queryParams.append('preferred_sources', params.preferred_sources)
  }

  const url = `/api/sync/multi-source/stock_basics/run${queryParams.toString() ? '?' + queryParams.toString() : ''}`
  return ApiClient.post(url, undefined, {
    timeout: 600000 // 🔥 同步操作需要更长时间，设置为10分钟（BaoStock需要逐个获取估值数据）
  })
}

/**
 * 测试数据源连接
 * @param sourceName - 可选，指定要测试的数据源名称。如果不指定，则测试所有数据源
 */
export const testDataSources = (sourceName?: string): Promise<ApiResponse<{ test_results: DataSourceTestResult[] }>> => {
  const params = sourceName ? { source_name: sourceName } : {}
  return ApiClient.post('/api/sync/multi-source/test-sources', params, {
    timeout: 15000 // 单个数据源测试超时15秒，多个数据源最多30秒
  })
}

/**
 * 获取同步建议
 */
export const getSyncRecommendations = (): Promise<ApiResponse<SyncRecommendations>> => {
  return ApiClient.get('/api/sync/multi-source/recommendations')
}

/**
 * 获取同步历史记录
 */
export const getSyncHistory = (params?: {
  page?: number
  page_size?: number
  status?: string
}): Promise<ApiResponse<{
  records: SyncStatus[]
  total: number
  page: number
  page_size: number
  has_more: boolean
}>> => {
  const queryParams = new URLSearchParams()
  if (params?.page) {
    queryParams.append('page', params.page.toString())
  }
  if (params?.page_size) {
    queryParams.append('page_size', params.page_size.toString())
  }
  if (params?.status) {
    queryParams.append('status', params.status)
  }

  const url = `/api/sync/multi-source/history${queryParams.toString() ? '?' + queryParams.toString() : ''}`
  return ApiClient.get(url)
}

/**
 * 清空同步缓存
 */
export const clearSyncCache = (): Promise<ApiResponse<{ cleared: boolean }>> => {
  return ApiClient.delete('/api/sync/multi-source/cache')
}

// 传统单一数据源同步API（保持兼容性）
export const runSingleSourceSync = (): Promise<ApiResponse<any>> => {
  return ApiClient.post('/api/sync/stock_basics/run')
}

export const getSingleSourceSyncStatus = (): Promise<ApiResponse<any>> => {
  return ApiClient.get('/api/sync/stock_basics/status')
}
