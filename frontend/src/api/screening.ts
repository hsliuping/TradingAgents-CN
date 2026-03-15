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
  roe?: number
  roa?: number
  gross_margin?: number
  netprofit_margin?: number
  dividend_yield?: number
  debt_to_assets?: number
  assets_to_eqt?: number
  current_ratio?: number
  quick_ratio?: number
  cash_ratio?: number
  revenue_ttm?: number
  net_profit_ttm?: number
  n_cashflow_act?: number
  report_period?: string
  pct_change?: number
  reason: string
}

export interface ScreeningChatResponse {
  reply: string
  tools_used: string[]
  stocks: StockRecommendation[]
  phase: 'confirmation' | 'planning' | 'result'
  conversation_id?: string
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
  conversation_id?: string
  messages: ScreeningMessageItem[]
}

export interface ScreeningConversationSummary {
  conversation_id: string
  title: string
  preview: string
  message_count: number
  created_at?: string
  updated_at?: string
}

export interface ScreeningConversationListResponse {
  items: ScreeningConversationSummary[]
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
  summary?: Record<string, number>
  timestamp?: string
}

export const screeningApi = {
  run: (payload: ScreeningRunReq, options?: { timeout?: number }) =>
    ApiClient.post<ScreeningRunResp>('/api/screening/run', payload, { timeout: options?.timeout ?? 120000 }),
  getFields: () => ApiClient.get<FieldConfigResponse>('/api/screening/fields'),
  getIndustries: () => ApiClient.get<IndustriesResponse>('/api/screening/industries'),

  // 智能筛选
  intelligentChat: (message: string, conversation_id?: string) =>
    ApiClient.post<ScreeningChatResponse>('/api/screening/intelligent/chat', { message, conversation_id }, { timeout: 180000 }),
  getIntelligentChatWsUrl: (token: string) => {
    const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const host = window.location.host
    return `${wsProtocol}//${host}/api/screening/intelligent/ws?token=${encodeURIComponent(token)}`
  },
  listIntelligentConversations: () =>
    ApiClient.get<ScreeningConversationListResponse>('/api/screening/intelligent/conversations'),
  getIntelligentConversation: (conversation_id?: string) =>
    ApiClient.get<ScreeningConversationResponse>(conversation_id
      ? `/api/screening/intelligent/conversation?conversation_id=${encodeURIComponent(conversation_id)}`
      : '/api/screening/intelligent/conversation'),
  clearIntelligentConversation: (conversation_id?: string) =>
    ApiClient.delete(conversation_id
      ? `/api/screening/intelligent/conversation?conversation_id=${encodeURIComponent(conversation_id)}`
      : '/api/screening/intelligent/conversation'),
}

