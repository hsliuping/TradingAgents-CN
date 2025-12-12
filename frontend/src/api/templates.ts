import ApiClient from './request'

export interface TemplateItem {
  id: string
  name: string
  description?: string
  type?: string
  created_at?: string
  updated_at?: string
  [key: string]: any
}

export interface CreateTemplatePayload {
  name: string
  description?: string
  type?: string
  config?: any
}

export interface UpdateTemplatePayload extends Partial<CreateTemplatePayload> {}

export const TemplatesApi = {
  list(params?: Record<string, any>) {
    return ApiClient.get<TemplateItem[]>('/api/templates', { params })
  },

  get(id: string) {
    return ApiClient.get<TemplateItem>(`/api/templates/${id}`)
  },

  create(payload: CreateTemplatePayload) {
    return ApiClient.post<TemplateItem>('/api/templates', payload)
  },

  update(id: string, payload: UpdateTemplatePayload) {
    return ApiClient.put<TemplateItem>(`/api/templates/${id}` , payload)
  },

  remove(id: string) {
    return ApiClient.delete<void>(`/api/templates/${id}`)
  },

  listAgentTemplates(params?: Record<string, any>) {
    return ApiClient.get<TemplateItem[]>('/api/agents/templates', { params })
  }
}

export default TemplatesApi