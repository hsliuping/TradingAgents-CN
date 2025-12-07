import { request, type ApiResponse } from './request'
import type { MCPConnector, MCPUpdatePayload } from '@/types/mcp'

const BASE = '/api/mcp/connectors'

export const mcpApi = {
  list(): Promise<ApiResponse<MCPConnector[]>> {
    return request.get(BASE)
  },
  batchUpdate(payload: MCPUpdatePayload): Promise<ApiResponse<void>> {
    return request.post(`${BASE}/update`, payload)
  },
  toggle(name: string, enabled: boolean): Promise<ApiResponse<{ enabled: boolean }>> {
    return request.patch(`${BASE}/${name}/toggle`, { enabled })
  },
  delete(name: string): Promise<ApiResponse<void>> {
    return request.delete(`${BASE}/${name}`)
  }
}

export type { MCPConnector, MCPUpdatePayload }
