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
  type: 'start' | 'end' | 'analyst' | 'researcher' | 'trader' | 'risk' | 'manager' | 'condition' | 'parallel' | 'merge' | 'debate' | 'tool'
  agent_id?: string
  tool_id?: string
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
  workflow_type?: string
  input_config?: WorkflowInputConfig
  output_config?: any
}

/**
 * 输入参数控件类型
 */
export type InputFieldType = 'string' | 'textarea' | 'number' | 'boolean' | 'date' | 'select' | 'multiselect'

/**
 * 单个输入参数定义
 */
export interface InputFieldConfig {
  name: string                  // 参数名（传给后端的 key）
  label: string                 // 表单显示标签
  type: InputFieldType
  required: boolean
  default?: any
  description?: string          // 参数描述/提示
  placeholder?: string
  options?: any[]               // 选项列表（select/multiselect 时使用）
  option_labels?: string[]      // 选项显示名（与 options 一一对应）
  min?: number
  max?: number
  group?: string                // 分组标签
  order?: number
}

/**
 * 工作流输入参数配置
 */
export interface WorkflowInputConfig {
  fields: InputFieldConfig[]
}

export interface WorkflowSummary {
  id: string
  name: string
  description: string
  version: string
  tags: string[]
  is_template: boolean
  is_default?: boolean
  workflow_type?: string
  created_at?: string
  updated_at?: string
}

/**
 * 判断工作流是否适合在分析页面（单股/批量分析）的"分析流程"下拉框中选择。
 *
 * 排除以下流程：
 * 1. v1.0 及更早的已弃用流程（主版本 < 2）
 * 2. 快速分析流（非完整分析流）
 * 3. 空白流程
 */
export function isSelectableAnalysisWorkflow(w: WorkflowSummary, expectedType: string): boolean {
  if (w.workflow_type !== expectedType) return false
  // v1.0 及更早流程已弃用，仅保留主版本 >= 2 的流程
  const major = parseInt((w.version || '0').split('.')[0], 10) || 0
  if (major < 2) return false
  // 排除快速分析流、空白流程等非完整分析流
  const name = w.name || ''
  if (name.includes('快速') || name.includes('空白')) return false
  return true
}

export interface ValidationResult {
  is_valid: boolean
  errors: string[]
  warnings: string[]
}

export interface ExecutionResult {
  success: boolean
  task_id?: string  // v2.0 异步执行返回的任务ID
  status?: string   // v2.0 任务状态
  message?: string  // v2.0 提示消息
  result?: Record<string, any>  // v1.x 同步执行的结果
  execution?: {  // v1.x 执行信息
    id: string
    workflow_id: string
    state: string
    started_at?: string
    completed_at?: string
    error?: string
  }
  error?: string
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
  async validate(data: Partial<WorkflowDefinition>): Promise<ApiResponse<ValidationResult>> {
    const res: ApiResponse<ValidationResult> = await request.post('/api/workflows/validate', data)
    return res
  },

  /**
   * 执行工作流
   * 注意：工作流执行是长时间操作（可能需要5-30分钟），设置较长超时时间并禁用重试
   */
  async execute(id: string, inputs: Record<string, any>): Promise<ExecutionResult> {
    const res: ApiResponse<ExecutionResult> = await request.post(`/api/workflows/${id}/execute`, inputs, {
      timeout: 30 * 60 * 1000,  // 30分钟超时
      retryCount: 0  // 禁用重试，避免重复执行
    } as any)
    // 从 ApiResponse 中提取实际的执行结果
    if (res.success && res.data) {
      return res.data
    }
    // 如果外层失败，构造一个失败的 ExecutionResult
    return {
      success: false,
      error: res.message || '执行失败'
    }
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
