import { ApiClient, type ApiResponse } from './request'

export interface AnalystDebugPayload {
  analyst_type: 'fundamentals' | 'market' | 'news' | 'social' | 'index_analyst' | 'sector_analyst'
  template_id?: string
  use_current?: boolean
  llm: { provider: string; model: string; temperature?: number; max_tokens?: number; backend_url?: string; api_key?: string }
  stock: { symbol: string; market_type?: string; analysis_date?: string }
  dataopts?: Record<string, any>
}

export const TemplatesDebugApi = {
  /**
   * 调试分析师模板
   * 注意：分析过程可能需要 2-5 分钟，设置较长超时时间并禁用重试
   */
  async debugAnalyst(payload: AnalystDebugPayload): Promise<ApiResponse<{ report: string; template?: any; analyst_type: string; symbol: string }>> {
    return ApiClient.post('/api/templates/debug/analyst', payload, {
      timeout: 10 * 60 * 1000,  // 10 分钟超时（分析可能需要 2-5 分钟）
      retryCount: 0  // 禁用重试，避免重复执行分析
    })
  }
}