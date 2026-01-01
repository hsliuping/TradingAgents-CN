/**
 * 社媒消息API接口
 */
import ApiClient from './request'

export interface SocialMediaMessage {
  message_id: string
  platform: string
  symbol: string
  message_type?: string
  content: string
  media_urls?: string[]
  hashtags?: string[]
  author: {
    author_id: string
    author_name: string
    verified?: boolean
    influence_score?: number
    followers_count?: number
    avatar_url?: string
  }
  engagement?: {
    views?: number
    likes?: number
    shares?: number
    comments?: number
    engagement_rate?: number
  }
  publish_time: string
  sentiment?: 'positive' | 'negative' | 'neutral'
  sentiment_score?: number
  keywords?: string[]
  topics?: string[]
  importance?: 'low' | 'medium' | 'high'
  credibility?: 'low' | 'medium' | 'high'
  location?: Record<string, string>
  language?: string
  data_source?: string
  crawler_version?: string
}

export interface UploadResponse {
  filename: string
  symbol: string
  platform: string
  total_messages: number
  saved: number
  failed: number
  upserted: number
  modified: number
}

export interface QueryParams {
  symbol?: string
  symbols?: string[]
  market?: string
  platform?: string
  message_type?: string
  start_time?: string
  end_time?: string
  sentiment?: string
  importance?: string
  min_influence_score?: number
  min_engagement_rate?: number
  verified_only?: boolean
  keywords?: string[]
  hashtags?: string[]
  limit?: number
  skip?: number
}

export interface Platform {
  code: string
  name: string
  description: string
}

export const socialMediaApi = {
  /**
   * 上传社媒消息文件
   * 注意：文件中的每条消息必须包含 symbol（股票代码）和 platform（平台）字段
   */
  async uploadFile(
    file: File,
    options?: {
      encoding?: string
      overwrite?: boolean
    }
  ): Promise<{ success: boolean; message: string; data: UploadResponse }> {
    const formData = new FormData()
    formData.append('file', file)
    
    if (options?.encoding) {
      formData.append('encoding', options.encoding)
    }
    if (options?.overwrite !== undefined) {
      formData.append('overwrite', String(options.overwrite))
    }

    return ApiClient.post('/api/social-media/upload', formData, {
      headers: {
        'Content-Type': 'multipart/form-data'
      }
    })
  },

  /**
   * 批量保存社媒消息
   */
  async saveMessages(
    symbol: string,
    messages: SocialMediaMessage[]
  ): Promise<{ success: boolean; message: string; data: any }> {
    return ApiClient.post('/api/social-media/save', {
      symbol,
      messages
    })
  },

  /**
   * 查询社媒消息
   */
  async queryMessages(
    params: QueryParams
  ): Promise<{ success: boolean; message: string; data: { messages: SocialMediaMessage[]; count: number } }> {
    return ApiClient.post('/api/social-media/query', params)
  },

  /**
   * 获取最新消息
   */
  async getLatestMessages(
    symbol: string,
    options?: {
      platform?: string
      limit?: number
    }
  ): Promise<{ success: boolean; message: string; data: { messages: SocialMediaMessage[]; count: number } }> {
    const params = new URLSearchParams()
    if (options?.platform) {
      params.append('platform', options.platform)
    }
    if (options?.limit) {
      params.append('limit', String(options.limit))
    }

    return ApiClient.get(`/api/social-media/latest/${symbol}?${params.toString()}`)
  },

  /**
   * 搜索消息
   */
  async searchMessages(
    query: string,
    options?: {
      symbol?: string
      platform?: string
      limit?: number
    }
  ): Promise<{ success: boolean; message: string; data: { messages: SocialMediaMessage[]; count: number } }> {
    const params = new URLSearchParams({ query })
    if (options?.symbol) {
      params.append('symbol', options.symbol)
    }
    if (options?.platform) {
      params.append('platform', options.platform)
    }
    if (options?.limit) {
      params.append('limit', String(options.limit))
    }

    return ApiClient.get(`/api/social-media/search?${params.toString()}`)
  },

  /**
   * 获取统计信息
   */
  async getStatistics(
    params?: {
      symbol?: string
      market?: string
      platform?: string
      sentiment?: string
      hoursBack?: number
    }
  ): Promise<{ success: boolean; message: string; data: any }> {
    const queryParams = new URLSearchParams()
    if (params?.symbol) {
      queryParams.append('symbol', params.symbol)
    }
    if (params?.market) {
      queryParams.append('market', params.market)
    }
    if (params?.platform) {
      queryParams.append('platform', params.platform)
    }
    if (params?.sentiment) {
      queryParams.append('sentiment', params.sentiment)
    }
    if (params?.hoursBack) {
      queryParams.append('hours_back', String(params.hoursBack))
    }

    return ApiClient.get(`/api/social-media/statistics?${queryParams.toString()}`)
  },

  /**
   * 获取支持的平台列表
   */
  async getPlatforms(): Promise<{ success: boolean; message: string; data: { platforms: Platform[]; count: number } }> {
    return ApiClient.get('/api/social-media/platforms')
  },

  /**
   * 获取情绪分析
   */
  async getSentimentAnalysis(
    symbol: string,
    options?: {
      platform?: string
      hoursBack?: number
    }
  ): Promise<{ success: boolean; message: string; data: any }> {
    const params = new URLSearchParams()
    if (options?.platform) {
      params.append('platform', options.platform)
    }
    if (options?.hoursBack) {
      params.append('hours_back', String(options.hoursBack))
    }

    return ApiClient.get(`/api/social-media/sentiment-analysis/${symbol}?${params.toString()}`)
  }
}

