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
  },

  /**
   * 获取财联社/新浪/电报列表
   * @param source 新闻来源: '财联社电报' | '新浪财经' | '外媒'
   */
  async getTelegraphList(source: string) {
    return ApiClient.get<any[]>(`/api/market-news/telegraph`, { source })
  },

  /**
   * 刷新新闻列表
   * @param source 新闻来源
   */
  async refreshTelegraphList(source: string) {
    return ApiClient.post<any[]>(`/api/market-news/refresh`, { source })
  },

  /**
   * 获取全球股指
   */
  async getGlobalStockIndexes() {
    return ApiClient.get<any>('/api/market-news/global-indexes')
  },

  /**
   * 获取行业排名
   * @param sort 排序方式: '0' 涨幅降序 | '1' 涨幅升序
   * @param count 数量
   */
  async getIndustryRank(sort: string = '0', count: number = 150) {
    return ApiClient.get<any[]>(`/api/market-news/industry-rank`, { sort, count })
  },

  /**
   * AI 市场资讯总结
   * @param question 问题
   */
  async summaryMarketNews(question: string) {
    return ApiClient.post<any>('/api/market-news/ai-summary', { question })
  },

  /**
   * 获取智能分组聚合的新闻
   * @param source 新闻来源，不指定则获取所有来源
   * @param strategy 排序策略: dynamic_hot(热点优先) | timeline(时间线优先)
   */
  async getGroupedNews(source: string | null | undefined, strategy: string = "dynamic_hot") {
    const params: any = { strategy }
    if (source) {
      params.source = source
    }
    return ApiClient.get<any>("/api/market-news/grouped", params)
  },

  /**
   * 刷新智能分组聚合的新闻
   * @param source 新闻来源，不指定则刷新所有来源
   * @param strategy 排序策略
   */
  async refreshGroupedNews(source: string | null | undefined, strategy: string = "dynamic_hot") {
    return ApiClient.post<any>("/api/market-news/refresh-grouped", { source, strategy })
  },

  /**
   * 获取新闻关键词分析
   * @param hours 统计最近多少小时的关键词
   * @param top_n 返回前N个关键词
   */
  async getNewsKeywords(hours: number = 24, top_n: number = 50) {
    return ApiClient.get<any>("/api/market-news/keywords", { hours, top_n })
 },
  /**
   * 获取增强词云数据（从enhanced数据库）
   * @param hours 统计最近多少小时
   * @param top_n 返回前N个词
   * @param source 指定来源（可选）
   */
  async getEnhancedWordcloud(hours: number = 24, top_n: number = 50, source?: string) {
    const params: any = { hours, top_n }
    if (source) {
      params.source = source
    }
    return ApiClient.get<any>("/api/market-news/enhanced-wordcloud", params)
  },
  /**
   * 获取新闻分析数据
   * @param hours 统计最近多少小时
   * @param source 指定来源（可选）
   */
  async getNewsAnalytics(hours: number = 24, source?: string) {
    const params: any = { hours }
    if (source) {
      params.source = source
    }
    return ApiClient.get<any>("/api/market-news/analytics", params)
  },
  /**
   * 搜索新闻
   * @param keyword 搜索关键词
   * @param limit 返回数量限制
   */
  async searchNews(keyword: string, limit: number = 50) {
    return ApiClient.get<any>("/api/market-news/search", { keyword, limit })
  }
}
