import { ApiClient } from './request'

/**
 * 新闻数据接口
 */
export interface NewsItem {
  id?: string
  title: string
  content?: string
  summary?: string
  source?: string
  publish_time: string
  url?: string
  symbol?: string
  category?: string
  sentiment?: string
  importance?: number
  data_source?: string
}

/**
 * 最新新闻响应
 */
export interface LatestNewsResponse {
  symbol?: string
  limit: number
  hours_back: number
  total_count: number
  news: NewsItem[]
}

/**
 * 新闻查询响应
 */
export interface NewsQueryResponse {
  symbol: string
  hours_back: number
  total_count: number
  news: NewsItem[]
}

/**
 * 新闻同步响应
 */
export interface NewsSyncResponse {
  sync_type: string
  symbol?: string
  data_sources?: string[]
  hours_back: number
  max_news_per_source: number
}

/**
 * 新闻API
 */
export const newsApi = {
  /**
   * 获取最新新闻
   * @param symbol 股票代码，为空则获取市场新闻
   * @param limit 返回数量限制
   * @param hours_back 回溯小时数
   */
  async getLatestNews(symbol?: string, limit: number = 10, hours_back: number = 24) {
    const params: any = { limit, hours_back }
    if (symbol) {
      params.symbol = symbol
    }
    return ApiClient.get<LatestNewsResponse>('/api/news-data/latest', params)
  },

  /**
   * 查询股票新闻
   * @param symbol 股票代码
   * @param hours_back 回溯小时数
   * @param limit 返回数量限制
   */
  async queryStockNews(symbol: string, hours_back: number = 24, limit: number = 20) {
    return ApiClient.get<NewsQueryResponse>(`/api/news-data/query/${symbol}`, {
      hours_back,
      limit
    })
  },

  /**
   * 同步市场新闻（后台任务）
   * @param hours_back 回溯小时数
   * @param max_news_per_source 每个数据源最大新闻数量
   */
  async syncMarketNews(hours_back: number = 24, max_news_per_source: number = 50) {
    return ApiClient.post<NewsSyncResponse>('/api/news-data/sync/start', {
      symbol: null,
      data_sources: null,
      hours_back,
      max_news_per_source
    })
  }
}

