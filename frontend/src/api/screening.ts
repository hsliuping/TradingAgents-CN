import { ApiClient } from './request'

export type WarningCategory = 'fallback_used' | 'proxy_used' | 'low_sample_size' | 'precision_degraded'

export interface FactorWarningPayload {
  warning_conditions: string[]
  warning_categories: WarningCategory[]
}

export interface FactorDiagnosticPayload {
  data_quality_tier?: string
  field_name?: string
  display_name?: string
  data_quality_state?: string | null
  unavailable_reason?: string | null
  missing_inputs?: string[]
  report_period?: string | null
  comparison_period?: string | null
}

export interface ScreeningOrderBy { field: string; direction: 'asc' | 'desc' }
export interface ScreeningConditionItem {
  field: string
  operator: string
  value: string | number | boolean | Array<string | number | boolean>
}
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
  symbol?: string
  name?: string
  industry?: string
  area?: string
  market?: string
  board?: string
  exchange?: string
  total_mv?: number
  circ_mv?: number
  pe?: number
  pb?: number
  pe_ttm?: number
  pb_mrq?: number
  roe?: number
  close?: number
  pct_chg?: number
  amount?: number
  turnover_rate?: number
  volume_ratio?: number
  ma20?: number
  rsi14?: number
  kdj_k?: number
  kdj_d?: number
  kdj_j?: number
  dif?: number
  dea?: number
  macd_hist?: number
  factor_diagnostics?: Record<string, FactorDiagnosticPayload>
  factor_warnings?: Record<string, FactorWarningPayload>
}

export interface ScreeningRunResp { total: number; items: ScreeningRunItem[] }

// 筛选字段配置
export interface FieldInfo {
  name: string
  display_name: string
  field_type: string
  data_type: string
  description: string
  unit?: string | null
  supported_operators: string[]
}

export interface FieldConfigResponse {
  fields: Record<string, FieldInfo>
  categories: Record<string, string[]>
  ui_metadata?: {
    category_order: string[]
    category_labels: Record<string, string>
    hidden_fields: string[]
    visible_fields_by_category: Record<string, string[]>
  }
}

export interface FactorRegistrySchema {
  field_name?: string
  display_name?: string
  data_type?: string
  description?: string
  unit?: string
}

export interface FactorRegistryCatalog {
  display_name?: string
  description?: string
}

export interface FactorRegistryScreening {
  registered: boolean
  field_type: string
  data_type: string
  unit: string
  supported_operators: string[]
  is_public_screening_field: boolean
}

export interface FactorRegistryItem {
  factor_id: string
  display_name: string
  governance_scope: string
  schema?: FactorRegistrySchema | null
  catalog?: FactorRegistryCatalog | null
  screening?: FactorRegistryScreening | null
  recommended_packs?: string[]
  is_registered_in_screening: boolean
  is_public_screening_field: boolean
}

export interface FactorRegistryResponse {
  total: number
  filters: {
    category?: string | null
    governance_scope: string
    screening_only: boolean
  }
  items: FactorRegistryItem[]
}

const LEGACY_STATIC_FIELDS: Record<string, FieldInfo> = {
  keyword: {
    name: 'keyword',
    display_name: '关键词',
    field_type: 'basic',
    data_type: 'string',
    description: '股票代码或名称',
    supported_operators: ['contains'],
  },
  symbol: {
    name: 'symbol',
    display_name: '股票代码',
    field_type: 'basic',
    data_type: 'string',
    description: '6位股票代码',
    supported_operators: ['==', '!=', 'in', 'not_in', 'contains'],
  },
  code: {
    name: 'code',
    display_name: '股票代码(已废弃)',
    field_type: 'basic',
    data_type: 'string',
    description: '6位股票代码(已废弃,使用symbol)',
    supported_operators: ['==', '!=', 'in', 'not_in', 'contains'],
  },
  name: {
    name: 'name',
    display_name: '股票名称',
    field_type: 'basic',
    data_type: 'string',
    description: '股票简称',
    supported_operators: ['contains', '==', '!='],
  },
  industry: {
    name: 'industry',
    display_name: '所属行业',
    field_type: 'basic',
    data_type: 'string',
    description: '申万行业分类',
    supported_operators: ['==', '!=', 'in', 'not_in', 'contains'],
  },
  area: {
    name: 'area',
    display_name: '所属地区',
    field_type: 'basic',
    data_type: 'string',
    description: '公司注册地区',
    supported_operators: ['==', '!=', 'in', 'not_in'],
  },
  market: {
    name: 'market',
    display_name: '所属市场',
    field_type: 'basic',
    data_type: 'string',
    description: '交易市场',
    supported_operators: ['==', '!=', 'in', 'not_in'],
  },
  total_mv: {
    name: 'total_mv',
    display_name: '总市值',
    field_type: 'basic',
    data_type: 'number',
    description: '公司总市值',
    unit: '亿',
    supported_operators: ['>', '<', '>=', '<=', 'between'],
  },
  circ_mv: {
    name: 'circ_mv',
    display_name: '流通市值',
    field_type: 'basic',
    data_type: 'number',
    description: '公司流通市值',
    unit: '亿',
    supported_operators: ['>', '<', '>=', '<=', 'between'],
  },
  pe: {
    name: 'pe',
    display_name: '市盈率',
    field_type: 'basic',
    data_type: 'number',
    description: 'Price to Earnings Ratio',
    supported_operators: ['>', '<', '>=', '<=', 'between'],
  },
  pb: {
    name: 'pb',
    display_name: '市净率',
    field_type: 'basic',
    data_type: 'number',
    description: 'Price to Book Ratio',
    supported_operators: ['>', '<', '>=', '<=', 'between'],
  },
  roe: {
    name: 'roe',
    display_name: '净资产收益率',
    field_type: 'basic',
    data_type: 'number',
    description: 'Return on Equity',
    unit: '%',
    supported_operators: ['>', '<', '>=', '<=', 'between'],
  },
  close: {
    name: 'close',
    display_name: '当前价格',
    field_type: 'basic',
    data_type: 'number',
    description: '最新收盘价',
    supported_operators: ['>', '<', '>=', '<=', 'between'],
  },
  pct_chg: {
    name: 'pct_chg',
    display_name: '涨跌幅',
    field_type: 'basic',
    data_type: 'number',
    description: '当日涨跌幅',
    supported_operators: ['>', '<', '>=', '<=', 'between'],
  },
  amount: {
    name: 'amount',
    display_name: '成交额',
    field_type: 'basic',
    data_type: 'number',
    description: '当日成交额',
    supported_operators: ['>', '<', '>=', '<=', 'between'],
  },
  turnover_rate: {
    name: 'turnover_rate',
    display_name: '换手率',
    field_type: 'basic',
    data_type: 'number',
    description: '换手率',
    supported_operators: ['>', '<', '>=', '<=', 'between'],
  },
  volume_ratio: {
    name: 'volume_ratio',
    display_name: '量比',
    field_type: 'basic',
    data_type: 'number',
    description: '量比',
    supported_operators: ['>', '<', '>=', '<=', 'between'],
  },
}

const LEGACY_CATEGORY_ORDER = {
  basic: ['keyword', 'symbol', 'code', 'name', 'industry', 'area', 'market'],
  market_value: ['total_mv', 'circ_mv'],
  financial: ['pe', 'pb', 'roe'],
  trading: ['turnover_rate', 'volume_ratio'],
  price: ['close', 'pct_chg', 'amount'],
  technical: [] as string[],
}

const LEGACY_UI_METADATA = {
  category_order: ['basic', 'market_value', 'financial', 'trading', 'price', 'technical'],
  category_labels: {
    basic: '基础条件',
    market_value: '市值规模',
    financial: '财务因子',
    trading: '交易活跃度',
    price: '价格表现',
    technical: '技术因子',
  },
  hidden_fields: ['code', 'market'],
  visible_fields_by_category: {} as Record<string, string[]>,
}

const dedupeFields = (fields: string[]) => Array.from(new Set(fields))

const mapRegistryItemToFieldInfo = (item: FactorRegistryItem): FieldInfo | null => {
  if (!item.screening?.registered) {
    return null
  }

  return {
    name: item.factor_id,
    display_name: item.display_name || item.schema?.display_name || item.catalog?.display_name || item.factor_id,
    field_type: item.screening.field_type,
    data_type: item.screening.data_type || item.schema?.data_type || 'string',
    description: item.schema?.description || item.catalog?.description || '',
    unit: item.screening.unit || item.schema?.unit || null,
    supported_operators: item.screening.supported_operators || [],
  }
}

const buildLegacyFieldConfigFromRegistry = (registry: FactorRegistryResponse): FieldConfigResponse => {
  const fields: Record<string, FieldInfo> = { ...LEGACY_STATIC_FIELDS }
  const categories = {
    basic: [...LEGACY_CATEGORY_ORDER.basic],
    market_value: [...LEGACY_CATEGORY_ORDER.market_value],
    financial: [...LEGACY_CATEGORY_ORDER.financial],
    trading: [...LEGACY_CATEGORY_ORDER.trading],
    price: [...LEGACY_CATEGORY_ORDER.price],
    technical: [...LEGACY_CATEGORY_ORDER.technical],
  }

  for (const item of registry.items || []) {
    const fieldInfo = mapRegistryItemToFieldInfo(item)
    if (!fieldInfo) {
      continue
    }

    fields[item.factor_id] = fieldInfo

    if (item.screening?.field_type === 'technical') {
      categories.technical.push(item.factor_id)
      continue
    }

    if (item.factor_id === 'total_mv' || item.factor_id === 'circ_mv') {
      categories.market_value.push(item.factor_id)
      continue
    }

    if (!(item.factor_id in LEGACY_STATIC_FIELDS)) {
      categories.financial.push(item.factor_id)
    }
  }

  return {
    fields,
    categories: {
      basic: dedupeFields(categories.basic),
      market_value: dedupeFields(categories.market_value),
      financial: dedupeFields(categories.financial),
      trading: dedupeFields(categories.trading),
      price: dedupeFields(categories.price),
      technical: dedupeFields(categories.technical),
    },
    ui_metadata: {
      ...LEGACY_UI_METADATA,
      visible_fields_by_category: {
        basic: dedupeFields(categories.basic).filter((field) => !LEGACY_UI_METADATA.hidden_fields.includes(field)),
        market_value: dedupeFields(categories.market_value).filter((field) => !LEGACY_UI_METADATA.hidden_fields.includes(field)),
        financial: dedupeFields(categories.financial).filter((field) => !LEGACY_UI_METADATA.hidden_fields.includes(field)),
        trading: dedupeFields(categories.trading).filter((field) => !LEGACY_UI_METADATA.hidden_fields.includes(field)),
        price: dedupeFields(categories.price).filter((field) => !LEGACY_UI_METADATA.hidden_fields.includes(field)),
        technical: dedupeFields(categories.technical).filter((field) => !LEGACY_UI_METADATA.hidden_fields.includes(field)),
      },
    },
  }
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
  pe_display_label?: string
  pb?: number
  pb_display_label?: string
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

export interface ScreeningPreset {
  id: string
  name: string
  basicFilters: Record<string, any>
  fieldFilters: Record<string, any>
  createdAt?: string
  updatedAt?: string
}

export interface ScreeningPresetListResponse {
  items: ScreeningPreset[]
}

export interface ScreeningPresetPayload {
  name: string
  basicFilters: Record<string, any>
  fieldFilters: Record<string, any>
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
  runEnhanced: (payload: { market?: 'CN'; date?: string | null; adj?: 'qfq' | 'hfq' | 'none'; conditions: ScreeningConditionItem[]; order_by?: ScreeningOrderBy[]; limit?: number; offset?: number; use_database_optimization?: boolean }, options?: { timeout?: number }) =>
    ApiClient.post<ScreeningRunResp>('/api/screening/enhanced', payload, { timeout: options?.timeout ?? 120000 }),
  getFactorRegistry: () => ApiClient.get<FactorRegistryResponse>('/api/screening/factor-registry?screening_only=true'),
  getFields: async () => {
    const response = await screeningApi.getFactorRegistry()
    const registry = response.data || response
    return buildLegacyFieldConfigFromRegistry(registry)
  },
  listPresets: () => ApiClient.get<ScreeningPresetListResponse>('/api/screening/presets'),
  createPreset: (payload: ScreeningPresetPayload) => ApiClient.post<{ preset: ScreeningPreset; message: string }>('/api/screening/presets', payload),
  updatePreset: (presetId: string, payload: ScreeningPresetPayload) => ApiClient.put<{ preset: ScreeningPreset; message: string }>(`/api/screening/presets/${encodeURIComponent(presetId)}`, payload),
  deletePreset: (presetId: string) => ApiClient.delete<{ id: string; message: string }>(`/api/screening/presets/${encodeURIComponent(presetId)}`),
  getIndustries: () => ApiClient.get<IndustriesResponse>('/api/screening/industries'),

  // 智能筛选
  intelligentChat: (message: string, conversation_id?: string) =>
    ApiClient.post<ScreeningChatResponse>('/api/screening/intelligent/chat', { message, conversation_id }, { timeout: 180000 }),
  getIntelligentChatWsUrl: (token?: string) => {
    const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const host = window.location.host
    const base = `${wsProtocol}//${host}/api/screening/intelligent/ws`
    return token ? `${base}?token=${encodeURIComponent(token)}` : base
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

