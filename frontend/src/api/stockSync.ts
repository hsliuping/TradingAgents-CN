/**
 * 股票数据同步 API
 */

import { ApiClient } from './request'

export interface SingleStockSyncRequest {
  symbol: string
  sync_realtime?: boolean
  sync_historical: boolean
  sync_financial: boolean
  sync_basic?: boolean
  data_source: 'tushare' | 'akshare' | 'qmt'
  days: number
}

export interface BatchStockSyncRequest {
  symbols: string[]
  sync_historical: boolean
  sync_financial: boolean
  sync_basic?: boolean
  data_source: 'tushare' | 'akshare' | 'qmt'
  days: number
}

export interface SyncResult {
  success: boolean
  records?: number
  message?: string
  error?: string
  data_source_used?: string
}

export interface SingleStockSyncResponse {
  symbol: string
  realtime_sync: SyncResult | null
  historical_sync: SyncResult | null
  financial_sync: SyncResult | null
  basic_sync: SyncResult | null
  overall_success?: boolean
}

export interface BatchStockSyncResponse {
  total: number
  symbols: string[]
  historical_sync: {
    success_count: number
    error_count: number
    total_records: number
    message: string
  } | null
  financial_sync: {
    success_count: number
    error_count: number
    total_symbols: number
    message: string
  } | null
  basic_sync: {
    success_count: number
    error_count: number
    total_symbols: number
    message: string
  } | null
}

export interface StockSyncStatus {
  symbol: string
  historical_data: {
    last_sync: string | null
    last_date: string | null
    total_records: number
  }
  financial_data: {
    last_sync: string | null
    last_report_period: string | null
    total_records: number
  }
}

export type StockSyncTaskType = 'single' | 'batch'
export type StockSyncTaskState = 'pending' | 'running' | 'success' | 'success_with_errors' | 'failed'

export interface StockSyncTaskSubmission {
  task_id: string
  task_type: StockSyncTaskType
  status: StockSyncTaskState
  message?: string | null
  symbol?: string
  symbols?: string[]
  created_at: string
}

export interface StockSyncTaskStatus {
  task_id: string
  task_type: StockSyncTaskType
  status: StockSyncTaskState
  message?: string | null
  symbol?: string
  symbols?: string[]
  created_at: string
  started_at?: string | null
  finished_at?: string | null
  result?: SingleStockSyncResponse | BatchStockSyncResponse | null
  error?: string | null
}

export const stockSyncApi = {
  /**
   * 同步单个股票数据
   */
  syncSingle(request: SingleStockSyncRequest) {
    return ApiClient.post<StockSyncTaskSubmission>('/api/stock-sync/single', request, {
      timeout: 15000 // 后端改为提交任务后立即返回
    })
  },

  /**
   * 批量同步股票数据
   */
  syncBatch(request: BatchStockSyncRequest) {
    return ApiClient.post<StockSyncTaskSubmission>('/api/stock-sync/batch', request, {
      timeout: 15000 // 后端改为提交任务后立即返回
    })
  },

  /**
   * 获取同步任务状态
   */
  getTaskStatus(taskId: string) {
    return ApiClient.get<StockSyncTaskStatus>(`/api/stock-sync/tasks/${taskId}`)
  },

  /**
   * 获取股票同步状态
   */
  getStatus(symbol: string) {
    return ApiClient.get<StockSyncStatus>(`/api/stock-sync/status/${symbol}`)
  }
}

