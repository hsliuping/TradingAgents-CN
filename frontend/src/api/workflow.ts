/**
 * 工作流 API
 */
import request from './request'
import type { ApiResponse } from './request'

// 类型定义
export interface Position {
  x: number
  y: number
}

export interface NodeDefinition {
  id: string
  type: 'start' | 'end' | 'analyst' | 'researcher' | 'trader' | 'risk' | 'manager' | 'condition' | 'parallel' | 'merge' | 'debate'
  agent_id?: string
  label: string
  position: Position
  config?: Record<string, any>
  condition?: string
}

export interface EdgeDefinition {
  id: string
  source: string
  target: string
  type?: 'normal' | 'conditional'
  condition?: string
  label?: string
  animated?: boolean
}

export interface WorkflowDefinition {
  id: string
  name: string
  description: string
  version: string
  nodes: NodeDefinition[]
  edges: EdgeDefinition[]
  created_at?: string
  updated_at?: string
  created_by?: string
  config?: Record<string, any>
  tags: string[]
  is_template: boolean
}

export interface WorkflowSummary {
  id: string
  name: string
  description: string
  version: string
  tags: string[]
  is_template: boolean
  created_at?: string
  updated_at?: string
}

export interface ValidationResult {
  is_valid: boolean
  errors: string[]
  warnings: string[]
}

export interface ExecutionResult {
  success: boolean
  result?: Record<string, any>
  execution?: {
    id: string
    workflow_id: string
    state: string
    started_at?: string
    completed_at?: string
    error?: string
  }
  error?: string
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
export const workflowApi = {
  /**
   * 获取所有工作流列表
   */
  async listAll(): Promise<WorkflowSummary[]> {
    const res: ApiResponse<WorkflowSummary[]> = await request.get('/api/workflows')
    return res.data || []
  },

  /**
   * 获取预定义模板
   */
  async getTemplates(): Promise<WorkflowDefinition[]> {
    const res: ApiResponse<WorkflowDefinition[]> = await request.get('/api/workflows/templates')
    return res.data || []
  },

  /**
   * 获取单个工作流详情
   */
  async get(id: string): Promise<WorkflowDefinition | null> {
    const res: ApiResponse<WorkflowDefinition> = await request.get(`/api/workflows/${id}`)
    return res.data || null
  },

  /**
   * 创建新工作流
   */
  create(data: Partial<WorkflowDefinition>): Promise<ApiResponse<WorkflowDefinition>> {
    return request.post('/api/workflows', data)
  },

  /**
   * 更新工作流
   */
  update(id: string, data: Partial<WorkflowDefinition>): Promise<ApiResponse<WorkflowDefinition>> {
    return request.put(`/api/workflows/${id}`, data)
  },

  /**
   * 删除工作流
   */
  delete(id: string): Promise<{ success: boolean; error?: string }> {
    return request.delete(`/api/workflows/${id}`)
  },

  /**
   * 验证工作流定义
   */
  validate(data: Partial<WorkflowDefinition>): Promise<ValidationResult> {
    return request.post('/api/workflows/validate', data)
  },

  /**
   * 执行工作流
   */
  execute(id: string, inputs: Record<string, any>): Promise<ExecutionResult> {
    return request.post(`/api/workflows/${id}/execute`, inputs)
  },

  /**
   * 从模板创建工作流
   */
  createFromTemplate(templateId: string, name: string): Promise<ApiResponse<WorkflowDefinition>> {
    return request.post('/api/workflows/from-template', { template_id: templateId, name })
  },

  /**
   * 复制工作流
   */
  duplicate(id: string, name: string): Promise<ApiResponse<WorkflowDefinition>> {
    return request.post(`/api/workflows/${id}/duplicate`, { name })
  },

  /**
   * 设为默认分析流
   */
  setAsDefault(id: string): Promise<ApiResponse<void>> {
    return request.post(`/api/workflows/${id}/set-default`)
  }
}

export default workflowApi

