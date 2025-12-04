import { ApiClient } from './request'

export interface FavoriteItem {
  symbol?: string  // 主字段：6位股票代码
  stock_code?: string  // 兼容字段（已废弃）
  stock_name: string
  market: string
  board?: string
  exchange?: string
  added_at?: string
  tags?: string[]
  notes?: string
  alert_price_high?: number | null
  alert_price_low?: number | null
  current_price?: number | null
  change_percent?: number | null
  volume?: number | null
}

export interface AddFavoriteReq {
  symbol?: string  // 主字段：6位股票代码
  stock_code?: string  // 兼容字段（已废弃）
  stock_name: string
  market?: string
  tags?: string[]
  notes?: string
  alert_price_high?: number | null
  alert_price_low?: number | null
}

export const favoritesApi = {
  /**
   * 获取收藏列表
   */
  list: () => ApiClient.get<FavoriteItem[]>('/api/favorites/'),

  /**
   * 添加收藏
   * @param payload 收藏信息（需包含 symbol 或 stock_code）
   */
  add: (payload: AddFavoriteReq) => ApiClient.post<{ message: string; symbol?: string; stock_code?: string }>('/api/favorites/', payload),

  /**
   * 更新收藏
   * @param symbol 股票代码（6位）
   * @param payload 更新内容
   */
  update: (symbol: string, payload: Partial<Pick<FavoriteItem, 'tags' | 'notes' | 'alert_price_high' | 'alert_price_low'>>) =>
    ApiClient.put<{ message: string; symbol?: string; stock_code?: string }>(`/api/favorites/${symbol}`, payload),

  /**
   * 删除收藏
   * @param symbol 股票代码（6位）
   */
  remove: (symbol: string) => ApiClient.delete<{ message: string; symbol?: string; stock_code?: string }>(`/api/favorites/${symbol}`),

  /**
   * 检查是否已收藏
   * @param symbol 股票代码（6位）
   */
  check: (symbol: string) => ApiClient.get<{ symbol?: string; stock_code?: string; is_favorite: boolean }>(`/api/favorites/check/${symbol}`),

  /**
   * 获取所有标签
   */
  tags: () => ApiClient.get<string[]>('/api/favorites/tags'),

  /**
   * 同步自选股实时行情
   * @param data_source 数据源（tushare/akshare）
   */
  syncRealtime: (data_source: string = 'tushare') =>
    ApiClient.post<{
      total: number
      success_count: number
      failed_count: number
      symbols: string[]
      data_source: string
      message: string
    }>('/api/favorites/sync-realtime', { data_source })
}

