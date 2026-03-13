import { ApiClient } from './request'

export interface ScreeningOrderBy { field: string; direction: 'asc' | 'desc' }
export interface ScreeningRunReq {
  market?: 'CN'
  date?: string | null
  adj?: 'qfq' | 'hfq' | 'none'
  conditions: any
  order_by?: ScreeningOrderBy[]
  limit?: number
  offset?: number
}

export interface ScreeningRunItem {
  code: string
  close?: number
  pct_chg?: number
  amount?: number
  ma20?: number
  rsi14?: number
  kdj_k?: number
  kdj_d?: number
  kdj_j?: number
  dif?: number
  dea?: number
  macd_hist?: number
}

export interface ScreeningRunResp { total: number; items: ScreeningRunItem[] }

// 筛选字段配置
export interface FieldInfo {
  name: string
  display_name: string
  field_type: string
  data_type: string
  description: string
  supported_operators: string[]
}

export interface FieldConfigResponse {
  fields: Record<string, FieldInfo>
  categories: Record<string, string[]>
}

// 行业列表响应
export interface IndustryOption {
  value: string
  label: string
  count: number
}

export interface IndustriesResponse {
  industries: IndustryOption[]
  total: number
}

// ---- 智能筛选相关接口 ----

export interface StockRecommendation {
  code: string
  name: string
  industry: string
  price?: number
  pe?: number
  pb?: number
  pct_change?: number
  reason: string
}

export interface ScreeningChatResponse {
  reply: string
  tools_used: string[]
  stocks: StockRecommendation[]
  phase: 'confirmation' | 'planning' | 'result'
  is_fallback?: boolean
}

export interface ScreeningMessageItem {
  role: 'user' | 'assistant'
  content: string
  tools_used?: string[]
  stocks?: StockRecommendation[]
  phase?: 'confirmation' | 'planning' | 'result'
  is_fallback?: boolean
}

export interface ScreeningConversationResponse {
  messages: ScreeningMessageItem[]
}

export interface ScreeningWsEnvelope<T = any> {
  type: 'connected' | 'started' | 'progress' | 'final' | 'error' | 'pong'
  data: T
}

export interface ScreeningWsProgressData {
  event: string
  phase?: 'confirmation' | 'planning' | 'result'
  message?: string
  tool?: string
  tools_used?: string[]
  stocks?: StockRecommendation[]
  preview?: string
  timestamp?: string
}

export const screeningApi = {
  run: (payload: ScreeningRunReq, options?: { timeout?: number }) =>
    ApiClient.post<ScreeningRunResp>('/api/screening/run', payload, { timeout: options?.timeout ?? 120000 }),
  getFields: () => ApiClient.get<FieldConfigResponse>('/api/screening/fields'),
  getIndustries: () => ApiClient.get<IndustriesResponse>('/api/screening/industries'),

  // 智能筛选
  intelligentChat: (message: string) =>
    ApiClient.post<ScreeningChatResponse>('/api/screening/intelligent/chat', { message }, { timeout: 180000 }),
  getIntelligentChatWsUrl: (token: string) => {
    const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const host = window.location.host
    return `${wsProtocol}//${host}/api/screening/intelligent/ws?token=${encodeURIComponent(token)}`
  },
  getIntelligentConversation: () =>
    ApiClient.get<ScreeningConversationResponse>('/api/screening/intelligent/conversation'),
  clearIntelligentConversation: () =>
    ApiClient.delete('/api/screening/intelligent/conversation'),
}

