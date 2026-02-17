import { ApiClient } from './request'

/**
 * 新闻增强API - 用于数据库分析和AI功能
 */
export const newsEnhancedApi = {
  /**
   * 获取增强词云数据
   */
  async getEnhancedWordcloud(hours: number = 24, top_n: number = 50, source?: string) {
    const params: any = { hours, top_n }
    if (source) params.source = source
    return ApiClient.get<any>("/api/market-news/enhanced-wordcloud", params)
  },

  /**
   * 获取新闻分析数据
   */
  async getNewsAnalytics(hours: number = 24, source?: string) {
    const params: any = { hours }
    if (source) params.source = source
    return ApiClient.get<any>("/api/market-news/analytics", params)
  },

  /**
   * 搜索新闻
   */
  async searchNews(keyword: string, limit: number = 50) {
    return ApiClient.get<any>("/api/market-news/search", { keyword, limit })
  },

  /**
   * 同步数据到增强数据库
   */
  async syncToEnhancedDB(hours: number = 24) {
    return ApiClient.post<any>("/api/market-news/sync-to-enhanced-db", { hours })
  }
}
