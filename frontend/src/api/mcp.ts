import request from './request'

// ==================== 类型定义 ====================

export interface MCPConnectionConfig {
  url?: string
  headers?: Record<string, string>
  command?: string
  args?: string[]
  env?: Record<string, string>
}

export interface MCPDiscoveredTool {
  name: string
  description: string
  input_schema: Record<string, any>
}

export interface MCPServer {
  server_id: string
  name: string
  description: string
  transport_type: 'sse' | 'streamable_http' | 'stdio'
  connection: MCPConnectionConfig
  discovered_tools: MCPDiscoveredTool[]
  is_enabled: boolean
  status: 'active' | 'inactive' | 'error' | 'unknown'
  last_error: string | null
  created_at: string
  updated_at: string
}

export interface MCPServerCreateRequest {
  server_id?: string
  name: string
  description?: string
  transport_type: 'sse' | 'streamable_http' | 'stdio'
  connection: MCPConnectionConfig
  is_enabled?: boolean
}

export interface MCPServerUpdateRequest {
  name?: string
  description?: string
  transport_type?: string
  connection?: MCPConnectionConfig
  is_enabled?: boolean
}

export interface MCPTool {
  tool_id: string
  name: string
  description: string
}

// ==================== API 函数 ====================

export const mcpApi = {
  /** 列出所有 MCP 服务器 */
  listServers: (): Promise<{ servers: MCPServer[]; total: number }> =>
    request.get('/api/mcp/servers'),

  /** 创建 MCP 服务器配置 */
  createServer: (data: MCPServerCreateRequest): Promise<{ server: MCPServer }> =>
    request.post('/api/mcp/servers', data),

  /** 获取单个 MCP 服务器 */
  getServer: (serverId: string): Promise<{ server: MCPServer }> =>
    request.get(`/api/mcp/servers/${serverId}`),

  /** 更新 MCP 服务器配置 */
  updateServer: (serverId: string, data: MCPServerUpdateRequest): Promise<{ server: MCPServer }> =>
    request.put(`/api/mcp/servers/${serverId}`, data),

  /** 删除 MCP 服务器 */
  deleteServer: (serverId: string): Promise<{ success: boolean; message: string }> =>
    request.delete(`/api/mcp/servers/${serverId}`),

  /** 测试 MCP 服务器连接 */
  testConnection: (serverId: string): Promise<{ success: boolean; server_id: string; transport_type: string; tool_count: number; error?: string }> =>
    request.post(`/api/mcp/servers/${serverId}/test`),

  /** 发现并同步 MCP 工具 */
  discoverTools: (serverId: string): Promise<{ success: boolean; server_id: string; tool_count: number; tools: MCPDiscoveredTool[]; registered: boolean }> =>
    request.post(`/api/mcp/servers/${serverId}/discover`),

  /** 启用或禁用 MCP 服务器 */
  toggleServer: (serverId: string, enabled: boolean): Promise<{ server: MCPServer; message: string }> =>
    request.post(`/api/mcp/servers/${serverId}/toggle`, { enabled }),

  /** 列出所有已注册的 MCP 工具 */
  listTools: (): Promise<{ tools: MCPTool[]; total: number }> =>
    request.get('/api/mcp/tools'),
}

export default mcpApi

