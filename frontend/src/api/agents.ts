/**
 * 智能体 API
 */
import request from './request'

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
  is_available?: boolean
  is_implemented?: boolean
  locked_reason?: string
}

export interface AgentCategory {
  id: string
  name: string
  count: number
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
  }
}

export default agentApi

