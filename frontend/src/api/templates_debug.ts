import { ApiClient, type ApiResponse } from './request'

export interface AnalystDebugPayload {
  analyst_type: 'fundamentals' | 'market' | 'news' | 'social' | 'index_analyst' | 'sector_analyst'
  agent_version?: string
  template_id?: string
  use_current?: boolean
  workflow_id?: string  // 🆕 工作流ID（用于加载流程专属提示词）
  llm: { provider: string; model: string; temperature?: number; max_tokens?: number; backend_url?: string; api_key?: string }
  stock: { symbol: string; market_type?: string; analysis_date?: string }
  dataopts?: Record<string, any>
}

// 🆕 工作流调试请求类型
export interface WorkflowDebugPayload {
  workflow_id: string
  llm: { provider: string; model: string; temperature?: number; max_tokens?: number; backend_url?: string; api_key?: string }
  stock: { symbol: string; market_type?: string; analysis_date?: string }
  dataopts?: Record<string, any>
}

// 🆕 工作流信息类型
export interface WorkflowInfo {
  id: string
  name: string
  description?: string
  type: 'template' | 'custom'
  is_system: boolean
  category?: string
  tags?: string[]
}

export const TemplatesDebugApi = {
  /**
   * 获取所有可用于调试的agents
   */
  async listDebugAgents(): Promise<ApiResponse<Array<{
    id: string
    name: string
    version: string
    category: string
    description?: string
  }>>> {
    return ApiClient.get('/api/templates/debug/agents')
  },

  /**
   * 🆕 获取所有可用于调试的工作流
   */
  async listDebugWorkflows(): Promise<ApiResponse<WorkflowInfo[]>> {
    return ApiClient.get('/api/templates/debug/workflows')
  },

  /**
   * 调试分析师模板
   * 注意：分析过程可能需要 2-5 分钟，设置较长超时时间并禁用重试
   */
  async debugAnalyst(payload: AnalystDebugPayload): Promise<ApiResponse<{ report: string; template?: any; analyst_type: string; symbol: string }>> {
    return ApiClient.post('/api/templates/debug/analyst', payload, {
      timeout: 10 * 60 * 1000,  // 10 分钟超时（分析可能需要 2-5 分钟）
      retryCount: 0  // 禁用重试，避免重复执行分析
    })
  },

  /**
   * 🆕 调试完整工作流
   * 执行指定的工作流并返回所有 Agent 的输出结果
   */
  async debugWorkflow(payload: WorkflowDebugPayload): Promise<ApiResponse<{
    workflow_id: string
    workflow_name: string
    symbol: string
    analysis_date?: string
    report: string
    agent_reports: Record<string, string>
    report_length: number
  }>> {
    return ApiClient.post('/api/templates/debug/workflow', payload, {
      timeout: 15 * 60 * 1000,  // 15 分钟超时（完整工作流可能需要更长时间）
      retryCount: 0  // 禁用重试
    })
  }
}