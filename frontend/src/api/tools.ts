import { request, type ApiResponse } from './request'

export interface AvailableTool {
  name: string
  description?: string
  source?: string
}

export const toolsApi = {
  list(includeMcp = true): Promise<ApiResponse<AvailableTool[]>> {
    return request.get('/api/tools/available', { params: { include_mcp: includeMcp } })
  }
}

