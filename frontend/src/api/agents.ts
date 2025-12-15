/**
 * 智能体 API
 */
import request from './request'
import type { ToolMetadata } from './tools'

// 类型定义
export interface AgentMetadata {
  id: string
  name: string
  description: string
  category: 'analyst' | 'researcher' | 'trader' | 'risk' | 'manager'
  license_tier: 'free' | 'basic' | 'pro' | 'enterprise'
  inputs: string[]
  outputs: string[]
  icon: string
  color: string
  tags: string[]
  tools?: string[]
  default_tools?: string[]
  max_tool_calls?: number
  is_available?: boolean
  is_implemented?: boolean
  locked_reason?: string
}

export interface AgentCategory {
  id: string
  name: string
  count: number
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

// Agent 工具配置更新
export interface AgentToolsUpdate {
  tools: string[]
  default_tools?: string[]
  max_tool_calls?: number
}

// API 响应类型（与 app/core/response.py 保持一致）
interface ApiResponse<T> {
  success: boolean
  data?: T
  message?: string
  code?: number
  timestamp?: string
}

// API 方法
export const agentApi = {
  /**
   * 获取所有智能体
   */
  async listAll(): Promise<AgentMetadata[]> {
    const res: ApiResponse<AgentMetadata[]> = await request.get('/api/agents')
    return res.data || []
  },

  /**
   * 获取当前许可证可用的智能体
   */
  async listAvailable(): Promise<AgentMetadata[]> {
    const res: ApiResponse<AgentMetadata[]> = await request.get('/api/agents/available')
    return res.data || []
  },

  /**
   * 按类别获取智能体
   */
  async listByCategory(category: string): Promise<AgentMetadata[]> {
    const res: ApiResponse<AgentMetadata[]> = await request.get(`/api/agents/category/${category}`)
    return res.data || []
  },

  /**
   * 获取智能体详情
   */
  async get(id: string): Promise<AgentMetadata | null> {
    const res: ApiResponse<AgentMetadata> = await request.get(`/api/agents/${id}`)
    return res.data || null
  },

  /**
   * 获取所有类别
   */
  async getCategories(): Promise<AgentCategory[]> {
    const res: ApiResponse<AgentCategory[]> = await request.get('/api/agents/categories')
    return res.data || []
  },

  /**
   * 获取 Agent 的工具配置
   */
  async getAgentTools(agentId: string): Promise<AgentToolsConfig> {
    return await request.get<AgentToolsConfig>(`/api/agents/${agentId}/tools`) as unknown as AgentToolsConfig
  },

  /**
   * 更新 Agent 的工具配置
   */
  async updateAgentTools(agentId: string, data: AgentToolsUpdate) {
    return await request.put(`/api/agents/${agentId}/tools`, data)
  }
}

export default agentApi

