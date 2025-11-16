import { ApiClient, type ApiResponse } from './request'

export interface AnalystDebugPayload {
  analyst_type: 'fundamentals' | 'market' | 'news' | 'social'
  template_id?: string
  use_current?: boolean
  llm: { provider: string; model: string; temperature?: number; max_tokens?: number; backend_url?: string; api_key?: string }
  stock: { symbol: string; market_type?: string; analysis_date?: string }
  dataopts?: Record<string, any>
}

export const TemplatesDebugApi = {
  async debugAnalyst(payload: AnalystDebugPayload): Promise<ApiResponse<{ report: string; template?: any; analyst_type: string; symbol: string }>> {
    return ApiClient.post('/api/v1/templates/debug/analyst', payload)
  }
}