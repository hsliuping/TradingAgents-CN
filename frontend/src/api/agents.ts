import { request, type ApiResponse } from './request'

export interface AgentConfig {
  id: string
  name: string
  stage: 'analysis' | 'research' | 'risk' | 'trading'
  type: string
  description?: string
  prompt?: string
  enabled: boolean
  is_system: boolean
}

const BASE = '/api/agents'

export const agentsApi = {
  list(): Promise<ApiResponse<AgentConfig[]>> {
    return request.get(BASE)
  },
  save(data: AgentConfig): Promise<ApiResponse<AgentConfig>> {
    return request.post(BASE, data)
  },
  delete(id: string): Promise<ApiResponse<void>> {
    return request.delete(`${BASE}/${id}`)
  }
}
