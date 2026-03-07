import request from './request'

// ==================== 类型定义 ====================

export interface PromptInjectionPolicy {
  id?: string
  agent_type: string
  agent_name: string
  scope: 'general' | 'industry' | 'stock'
  enabled: boolean
  injection_mode: 'none' | 'summary' | 'full'
  inherit_industry_for_stock: boolean
  include_capability_block: boolean
  include_external_gap_notice: boolean
  include_comparable_companies: boolean
  inject_position: 'system_prompt' | 'analysis_requirements' | 'constraints'
  version?: number
  created_at?: string
  updated_at?: string
}

export interface PromptInjectionPolicyCreate {
  agent_type: string
  agent_name: string
  scope?: 'general' | 'industry' | 'stock'
  enabled?: boolean
  injection_mode?: 'none' | 'summary' | 'full'
  inherit_industry_for_stock?: boolean
  include_capability_block?: boolean
  include_external_gap_notice?: boolean
  include_comparable_companies?: boolean
  inject_position?: 'system_prompt' | 'analysis_requirements' | 'constraints'
}

export interface PromptInjectionPolicyUpdate {
  enabled?: boolean
  injection_mode?: 'none' | 'summary' | 'full'
  inherit_industry_for_stock?: boolean
  include_capability_block?: boolean
  include_external_gap_notice?: boolean
  include_comparable_companies?: boolean
  inject_position?: 'system_prompt' | 'analysis_requirements' | 'constraints'
}

// ==================== API 函数 ====================

export const promptPoliciesApi = {
  /** 列表查询（支持过滤） */
  list: (params?: {
    agent_type?: string
    agent_name?: string
    scope?: string
  }): Promise<{ policies: PromptInjectionPolicy[]; total: number }> =>
    request.get('/api/v1/prompt-policies', { params }),

  /** 获取单个策略 */
  get: (id: string): Promise<{ policy: PromptInjectionPolicy }> =>
    request.get(`/api/v1/prompt-policies/${id}`),

  /** 创建策略 */
  create: (data: PromptInjectionPolicyCreate): Promise<{ policy: PromptInjectionPolicy }> =>
    request.post('/api/v1/prompt-policies', data),

  /** 更新策略 */
  update: (id: string, data: PromptInjectionPolicyUpdate): Promise<{ policy: PromptInjectionPolicy }> =>
    request.put(`/api/v1/prompt-policies/${id}`, data),

  /** 删除策略 */
  delete: (id: string): Promise<{ success: boolean }> =>
    request.delete(`/api/v1/prompt-policies/${id}`),
}

export default promptPoliciesApi
