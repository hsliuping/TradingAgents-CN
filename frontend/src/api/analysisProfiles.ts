import { ApiClient, type ApiResponse } from './request'

// ── 类型定义 ──

export interface AnalysisDimension {
  name: string
  description: string
  importance?: string
  data_source?: string
  weight?: number
}

export interface IndustryProfile {
  id?: string
  industry: string
  display_name: string
  analysis_dimensions: AnalysisDimension[]
  analysis_focus: string
  key_metrics: string[]
  comparable_companies: string[]
  source?: string
  is_active: boolean
  created_at?: string
  updated_at?: string
}

export interface StockProfile {
  id?: string
  stock_symbol: string
  stock_name?: string
  industry?: string
  special_notes: string
  analysis_dimensions: AnalysisDimension[]
  is_active: boolean
  created_at?: string
  updated_at?: string
}

// ── 覆盖评估类型 ──

export interface SourceRef {
  type: string
  type_label: string
  name: string
  detail: string
}

export interface ItemAssessment {
  name: string
  description: string
  requested_data_source: string
  coverage_status: 'directly_usable' | 'partially_usable' | 'external_required' | 'review_recommended'
  coverage_label: string
  recommended_action: string
  recommended_action_label: string
  matched_sources: SourceRef[]
  missing_requirements: string[]
  user_note: string
}

export interface CoverageSummary {
  overall_status: 'ready' | 'review_needed' | 'prune_needed'
  overall_label: string
  dimension_counts: Record<string, number>
  metric_counts: Record<string, number>
  recommendations: string[]
}

export interface CapabilitySnapshot {
  builtin_sources: { key: string; label: string; description: string }[]
  enabled_mcp_servers: { server_id: string; name: string; description: string; tool_count: number }[]
  active_skills: { tool_id: string; name: string; description: string }[]
  manual_import: { available: boolean; label: string; description: string }
  counts: { builtin_sources: number; enabled_mcp_servers: number; active_skills: number }
  notes: string[]
}

export interface GeneratePreview {
  profile: IndustryProfile
  coverage_summary: CoverageSummary
  capability_snapshot: CapabilitySnapshot
  dimension_assessments: ItemAssessment[]
  metric_assessments: ItemAssessment[]
  next_step_guidance: string[]
}

export interface GenerateIndustryOptions {
  user_request?: string
  existing_profile?: Partial<IndustryProfile>
}

// ── API 接口 ──

export const analysisProfilesApi = {
  // 行业配置
  async listIndustries(isActive?: boolean): Promise<ApiResponse<IndustryProfile[]>> {
    const params: Record<string, any> = {}
    if (isActive !== undefined) params.is_active = isActive
    const res = await ApiClient.get('/api/analysis-profiles/industries', params)
    return res as ApiResponse<IndustryProfile[]>
  },

  async getIndustry(profileId: string): Promise<ApiResponse<IndustryProfile>> {
    return ApiClient.get(`/api/analysis-profiles/industries/${profileId}`)
  },

  async createIndustry(data: Partial<IndustryProfile>): Promise<ApiResponse<IndustryProfile>> {
    return ApiClient.post('/api/analysis-profiles/industries', data)
  },

  async updateIndustry(profileId: string, data: Partial<IndustryProfile>): Promise<ApiResponse<IndustryProfile>> {
    return ApiClient.put(`/api/analysis-profiles/industries/${profileId}`, data)
  },

  async deleteIndustry(profileId: string): Promise<ApiResponse<any>> {
    return ApiClient.delete(`/api/analysis-profiles/industries/${profileId}`)
  },

  async generateIndustry(industry: string, options?: GenerateIndustryOptions): Promise<ApiResponse<GeneratePreview>> {
    return ApiClient.post('/api/analysis-profiles/industries/generate', {
      industry,
      user_request: options?.user_request || '',
      existing_profile: options?.existing_profile || undefined,
    })
  },

  /** 获取数据库中所有实际行业名称（来自 stock_basic_info） */
  async getIndustryList(): Promise<ApiResponse<string[]>> {
    return ApiClient.get('/api/analysis-profiles/industry-list')
  },

  // 个股配置
  async listStocks(industry?: string): Promise<ApiResponse<StockProfile[]>> {
    const params: Record<string, any> = {}
    if (industry) params.industry = industry
    const res = await ApiClient.get('/api/analysis-profiles/stocks', params)
    return res as ApiResponse<StockProfile[]>
  },

  async getStock(stockSymbol: string): Promise<ApiResponse<StockProfile>> {
    return ApiClient.get(`/api/analysis-profiles/stocks/${stockSymbol}`)
  }
}

