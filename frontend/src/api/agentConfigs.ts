import { request, type ApiResponse } from './request'

export interface PhaseAgentMode {
  slug: string
  name: string
  roleDefinition: string
  tools?: string[]
}

export interface PhaseAgentConfig {
  phase: number
  exists: boolean
  customModes: PhaseAgentMode[]
  path?: string
}

export interface PhaseAgentPayload {
  customModes: PhaseAgentMode[]
}

const BASE = '/api/agent-configs'

export const agentConfigApi = {
  getPhase(phase: number): Promise<ApiResponse<PhaseAgentConfig>> {
    return request.get(`${BASE}/${phase}`)
  },
  savePhase(phase: number, payload: PhaseAgentPayload): Promise<ApiResponse<PhaseAgentConfig>> {
    return request.put(`${BASE}/${phase}`, payload)
  }
}
