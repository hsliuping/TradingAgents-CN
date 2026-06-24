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

/** 字段映射项（支持一源多目标） */
export interface FieldMappingItem {
  source?: string
  target?: string
  key?: string
  value?: string
}

/** MCP 数据源字段映射配置（datasource 类服务器使用） */
export interface MCPDataMapping {
  tool_name: string
  target_collection: string
  adapter?: string
  /** 旧格式：一对一映射，同 key 会覆盖 */
  field_mapping?: Record<string, string>
  /** 新格式：数组，支持一个源字段映射到多个目标字段 */
  field_mapping_list?: FieldMappingItem[]
  unit_conversion?: Record<string, { from: string; to: string; factor: number }>
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
  /** 服务器分类：datasource（数据源类）| function（功能类） */
  category: 'datasource' | 'function'
  /** 数据源类字段映射配置（category=datasource 时有效） */
  data_mappings: MCPDataMapping[]
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
  /** 服务器分类：datasource | function（默认 function） */
  category?: 'datasource' | 'function'
  /** 数据源类字段映射配置 */
  data_mappings?: MCPDataMapping[]
}

export interface MCPServerUpdateRequest {
  name?: string
  description?: string
  transport_type?: string
  connection?: MCPConnectionConfig
  is_enabled?: boolean
  category?: 'datasource' | 'function'
  data_mappings?: MCPDataMapping[]
}

export interface MCPTool {
  tool_id: string
  name: string
  description: string
}

export interface MCPDetectedField {
  name: string
  sample: string
  type: string
}

export interface MCPProbeResult {
  success: boolean
  tool_name: string
  raw_result: string
  detected_fields: MCPDetectedField[]
}

export interface AIMappingSuggestion {
  source: string
  target: string
  reason: string
}

export interface AIMappingResult {
  success: boolean
  mappings: AIMappingSuggestion[]
  explanation: string
  detected_fields: MCPDetectedField[]
  collection_fields: string[]
  collection_field_descriptions: Record<string, string>
}

// 凭证响应
export interface CredentialItem {
  id: string
  name: string
  key_name: string
  key_value_masked: string
  server_id: string | null
  description: string
  created_at: string
  updated_at: string
}

// 创建凭证请求
export interface CredentialCreateRequest {
  name: string
  key_name: string
  key_value: string
  server_id?: string
  description?: string
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

  /** 获取服务器已发现工具列表（从数据库缓存，不重连服务器） */
  listServerTools: (serverId: string): Promise<{ tools: MCPDiscoveredTool[]; total: number }> =>
    request.get(`/api/mcp/servers/${serverId}/tools-list`),

  /** 探测工具输出字段（试调用） */
  probeTool: (
    serverId: string,
    toolName: string,
    args: Record<string, any>
  ): Promise<MCPProbeResult> =>
    request.post(`/api/mcp/servers/${serverId}/probe-tool`, {
      tool_name: toolName,
      arguments: args,
    }),

  /** 获取 MongoDB 数据库中所有集合名称列表 */
  listCollections: (): Promise<{ collections: string[]; total: number }> =>
    request.get('/api/mcp/collections'),

  /** AI 智能字段映射建议（自动探测工具字段 + 采样集合 + LLM 推断） */
  aiSuggestMapping: (
    serverId: string,
    toolName: string,
    targetCollection: string
  ): Promise<AIMappingResult> =>
    request.post(`/api/mcp/servers/${serverId}/ai-suggest-mapping`, {
      tool_name: toolName,
      target_collection: targetCollection,
    }),

  // 凭证保险箱
  listCredentials: async (): Promise<CredentialItem[]> => {
    return await request.get<CredentialItem[]>('/api/mcp/credentials') as unknown as CredentialItem[]
  },

  createCredential: async (data: CredentialCreateRequest): Promise<CredentialItem> => {
    return await request.post<CredentialItem>('/api/mcp/credentials', data) as unknown as CredentialItem
  },

  deleteCredential: async (id: string): Promise<void> => {
    await request.delete(`/api/mcp/credentials/${id}`)
  },

  applyCredentialToServer: async (credentialId: string, serverId: string): Promise<void> => {
    await request.post(`/api/mcp/credentials/${credentialId}/apply/${serverId}`)
  },
}

export default mcpApi

