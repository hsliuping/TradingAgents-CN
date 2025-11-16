import { ApiClient, type ApiResponse } from './request'

export interface TemplateItem {
  id: string
  agent_type: string
  agent_name: string
  template_name: string
  preference_type?: string
  is_system: boolean
  status: string
  version: number
  created_at?: string
  updated_at?: string
}

export interface TemplateListParams {
  agent_type?: string
  agent_name?: string
  preference_type?: string
  is_system?: boolean
  status?: string
}

export const TemplatesApi = {
  async list(params: TemplateListParams & { q?: string; skip?: number; limit?: number } = {}): Promise<ApiResponse<{ items: TemplateItem[]; total: number; skip?: number; limit?: number }>> {
    const res = await ApiClient.get('/api/v1/templates', params)
    const data = res.data as any
    const normalized = Array.isArray(data) ? { items: data, total: data.length } : { items: data.items || [], total: data.total || 0, skip: data.skip, limit: data.limit }
    return { ...res, data: normalized }
  },

  async get(template_id: string): Promise<ApiResponse<any>> {
    return ApiClient.get(`/api/v1/templates/${template_id}`)
  },

  async listByAgent(agent_type: string, agent_name: string, preference_type?: string, user_id?: string): Promise<ApiResponse<{ templates: any[]; total: number }>> {
    const params: Record<string, any> = {}
    if (preference_type) params.preference_type = preference_type
    if (user_id) params.user_id = user_id
    return ApiClient.get(`/api/v1/templates/agent/${agent_type}/${agent_name}`, params)
  }
}
