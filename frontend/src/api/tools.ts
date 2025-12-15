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
  is_builtin?: boolean
}

// 工具配置更新
export interface ToolConfigUpdate {
  is_online?: boolean
  timeout?: number
  rate_limit?: number
  description?: string
  category?: string
}

// HTTP工具配置
export interface HttpToolConfig {
  url: string
  method: string
  headers: Record<string, string>
}

// 自定义工具定义
export interface CustomToolDefinition {
  id: string
  name: string
  description: string
  category: string
  parameters: ToolParameter[]
  implementation: HttpToolConfig
  is_online: boolean
  timeout: number
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

  // 创建分类
  createCategory: async (data: { id: string; name: string }) => {
    return await request.post('/api/tools/categories', data)
  },

  // 更新分类
  updateCategory: async (id: string, data: { name: string }) => {
    return await request.put(`/api/tools/categories/${id}`, data)
  },

  // 删除分类
  deleteCategory: async (id: string) => {
    return await request.delete(`/api/tools/categories/${id}`)
  },

  // 创建自定义工具
  createCustomTool: async (data: CustomToolDefinition) => {
    return await request.post('/api/tools/custom', data)
  },

  // 获取自定义工具定义
  getCustomTool: async (toolId: string): Promise<CustomToolDefinition> => {
    return await request.get<CustomToolDefinition>(`/api/tools/custom/${toolId}`) as unknown as CustomToolDefinition
  },

  // 更新自定义工具
  updateCustomTool: async (toolId: string, data: CustomToolDefinition) => {
    return await request.put(`/api/tools/custom/${toolId}`, data)
  },

  // 删除自定义工具
  deleteCustomTool: async (toolId: string) => {
    return await request.delete(`/api/tools/custom/${toolId}`)
  },

  // 获取单个工具详情
  getTool: async (toolId: string): Promise<ToolMetadata> => {
    return await request.get<ToolMetadata>(`/api/tools/${toolId}`) as unknown as ToolMetadata
  },

  // 更新工具配置
  updateToolConfig: async (toolId: string, data: ToolConfigUpdate) => {
    return await request.put(`/api/tools/${toolId}`, data)
  },
}

export default toolsApi

