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
  data_source: 'tushare' | 'akshare' | 'mixed'
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
  data_source_used?: 'tushare' | 'akshare'
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

export interface SyncHistoryRange {
  start_date: string
  end_date: string
  days: number
}

export interface SyncHistoryRecord {
  id: string
  user_id: string
  scope: 'single' | 'batch'
  symbol?: string | null
  symbols: string[]
  symbol_count: number
  sync_types: string[]
  historical_range?: SyncHistoryRange | null
  data_source_requested: string
  data_sources_used: string[]
  status: 'success' | 'partial_success' | 'failed'
  overall_success: boolean
  summary: string
  errors: string[]
  result: Record<string, any>
  started_at: string
  finished_at: string
  duration_seconds: number
  created_at: string
}

export interface SyncHistoryResponse {
  records: SyncHistoryRecord[]
  total: number
  page: number
  page_size: number
  has_more: boolean
  filters?: {
    symbol?: string | null
    sync_types?: string[]
    data_sources?: string[]
    range_start?: string | null
    range_end?: string | null
  }
}

export type DeleteSyncedDataType = 'historical' | 'financial' | 'basic' | 'realtime_cache'

export interface DeleteSyncedDataRequest {
  symbol: string
  delete_type: DeleteSyncedDataType
  delete_display_cache?: boolean
}

export interface DeleteSyncedDataResponse {
  symbol: string
  delete_type: DeleteSyncedDataType
  delete_type_label: string
  delete_display_cache: boolean
  symbol_variants: string[]
  deleted_count: number
  details: Array<{
    collection: string
    deleted_count: number
  }>
}

export interface SyncedDataSummaryItem {
  delete_type: DeleteSyncedDataType
  delete_type_label: string
  exists: boolean
  record_count: number
  data_sources: string[]
  latest_update: string | null
  range_start: string | null
  range_end: string | null
  affects_favorites_display: boolean
  impact_hint: string
  target_collections: string[]
}

export interface SyncHistoryQueryParams {
  page?: number
  page_size?: number
  symbol?: string
  sync_types?: string[]
  data_sources?: string[]
  range_start?: string
  range_end?: string
}

export interface SyncedDataSummaryQueryParams {
  symbol: string
  sync_types?: string[]
  data_sources?: string[]
  range_start?: string
  range_end?: string
  related_history_limit?: number
}

export interface SyncedDataSummaryResponse {
  symbol: string
  symbol_variants: string[]
  items: SyncedDataSummaryItem[]
  related_history: SyncHistoryRecord[]
  related_history_total: number
  query_context?: {
    symbol?: string | null
    sync_types?: string[]
    data_sources?: string[]
    range_start?: string | null
    range_end?: string | null
  }
}

export interface DeleteSyncedDataBatchRequest {
  symbol: string
  delete_types: DeleteSyncedDataType[]
  delete_display_cache?: boolean
}

export interface DeleteSyncedDataBatchResponse {
  symbol: string
  delete_types: DeleteSyncedDataType[]
  delete_type_labels: string[]
  delete_display_cache: boolean
  symbol_variants: string[]
  deleted_count: number
  details: Array<{
    collection: string
    deleted_count: number
  }>
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
  },

  /**
   * 获取同步历史
   */
  getHistory(params?: SyncHistoryQueryParams) {
    const query = {
      ...params,
      sync_types: params?.sync_types?.join(','),
      data_sources: params?.data_sources?.join(',')
    }
    return ApiClient.get<SyncHistoryResponse>('/api/stock-sync/history', query)
  },

  /**
   * 删除单条同步历史
   */
  deleteHistoryRecord(recordId: string) {
    return ApiClient.delete(`/api/stock-sync/history/${recordId}`)
  },

  /**
   * 清空同步历史
   */
  clearHistory(params?: Omit<SyncHistoryQueryParams, 'page' | 'page_size'>) {
    const query = {
      ...params,
      sync_types: params?.sync_types?.join(','),
      data_sources: params?.data_sources?.join(',')
    }
    return ApiClient.delete('/api/stock-sync/history', {
      params: query
    })
  },

  /**
   * 获取已同步数据概览
   */
  getDataSummary(params: SyncedDataSummaryQueryParams) {
    const query = {
      ...params,
      sync_types: params.sync_types?.join(','),
      data_sources: params.data_sources?.join(',')
    }
    return ApiClient.get<SyncedDataSummaryResponse>('/api/stock-sync/data-summary', query)
  },

  /**
   * 删除已同步数据
   */
  deleteSyncedData(request: DeleteSyncedDataRequest) {
    return ApiClient.post<DeleteSyncedDataResponse>('/api/stock-sync/data/delete', request)
  },

  /**
   * 批量删除已同步数据
   */
  deleteSyncedDataBatch(request: DeleteSyncedDataBatchRequest) {
    return ApiClient.post<DeleteSyncedDataBatchResponse>('/api/stock-sync/data/delete-batch', request)
  }
}
