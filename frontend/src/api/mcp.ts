import { request, type ApiResponse } from './request'
import type { MCPConnector, MCPUpdatePayload, MCPTool } from '@/types/mcp'

const BASE = '/api/mcp/connectors'
const TOOLS_BASE = '/api/mcp/tools'

export const mcpApi = {
  list(): Promise<ApiResponse<MCPConnector[]>> {
    return request.get(BASE)
  },
  listTools(): Promise<ApiResponse<MCPTool[]>> {
    return request.get(TOOLS_BASE)
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

export type { MCPConnector, MCPUpdatePayload, MCPTool }
