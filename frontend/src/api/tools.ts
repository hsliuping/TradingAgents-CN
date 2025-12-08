import request from './request'

// 工具参数
export interface ToolParameter {
  name: string
  type: string
  description: string
  required: boolean
  default?: any
  enum?: any[]
}

// 工具元数据
export interface ToolMetadata {
  id: string
  name: string
  description: string
  category: string
  data_source: string
  is_online: boolean
  timeout: number
  rate_limit?: number
  icon: string
  color: string
  parameters: ToolParameter[]
}

// 工具类别
export interface ToolCategory {
  id: string
  name: string
}

// Agent 工具配置
export interface AgentToolsConfig {
  agent_id: string
  agent_name: string
  tools: string[]
  default_tools: string[]
  max_tool_calls: number
  available_tools: ToolMetadata[]
}

// API 函数
export const toolsApi = {
  // 获取所有工具
  listTools: async (params?: { category?: string; is_online?: boolean }): Promise<ToolMetadata[]> => {
    // 注意：request 拦截器已经返回 response.data，所以这里直接返回
    return await request.get<ToolMetadata[]>('/api/tools', { params }) as unknown as ToolMetadata[]
  },

  // 获取工具类别
  listCategories: async (): Promise<ToolCategory[]> => {
    return await request.get<ToolCategory[]>('/api/tools/categories') as unknown as ToolCategory[]
  },

  // 获取单个工具详情
  getTool: async (toolId: string): Promise<ToolMetadata> => {
    return await request.get<ToolMetadata>(`/api/tools/${toolId}`) as unknown as ToolMetadata
  },

  // 获取 Agent 的工具配置
  getAgentTools: async (agentId: string): Promise<AgentToolsConfig> => {
    return await request.get<AgentToolsConfig>(`/api/tools/agent/${agentId}`) as unknown as AgentToolsConfig
  },
}

export default toolsApi

