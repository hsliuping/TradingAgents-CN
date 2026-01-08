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
  data_source: 'tushare' | 'akshare'
  days: number
}

export interface BatchStockSyncRequest {
  symbols: string[]
  sync_historical: boolean
  sync_financial: boolean
  sync_basic?: boolean
  data_source: 'tushare' | 'akshare'
  days: number
}

export interface SyncResult {
  success: boolean
  records?: number
  message?: string
  error?: string
}

export interface SingleStockSyncResponse {
  symbol: string
  realtime_sync: SyncResult | null
  historical_sync: SyncResult | null
  financial_sync: SyncResult | null
  basic_sync: SyncResult | null
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

export const stockSyncApi = {
  /**
   * 同步单个股票数据
   */
  syncSingle(request: SingleStockSyncRequest) {
    return ApiClient.post<SingleStockSyncResponse>('/api/stock-sync/single', request, {
      timeout: 120000 // 2分钟超时
    })
  },

  /**
   * 批量同步股票数据
   */
  syncBatch(request: BatchStockSyncRequest) {
    return ApiClient.post<BatchStockSyncResponse>('/api/stock-sync/batch', request, {
      timeout: 300000 // 5分钟超时
    })
  },

  /**
   * 获取股票同步状态
   */
  getStatus(symbol: string) {
    return ApiClient.get<StockSyncStatus>(`/api/stock-sync/status/${symbol}`)
  }
}

