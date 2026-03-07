import request from './request'

// ==================== 类型定义 ====================

export interface ChatRequest {
  session_id?: string
  message: string
  agent_type: string
  agent_name: string
  analysis_type?: 'general' | 'industry' | 'stock'
  industry?: string
  stock_symbol?: string
}

export interface ChatResponse {
  success: boolean
  session_id: string
  ai_message: string
  suggested_changes?: {
    template_changes?: Record<string, string>
    policy_changes?: Record<string, Record<string, unknown>>
  }
}

export interface DiffRequest {
  agent_type: string
  agent_name: string
  proposed_template?: Record<string, string>
  proposed_policy?: Record<string, unknown>
}

export interface DiffResponse {
  success: boolean
  before: { template: Record<string, string>; assembled: string }
  after: { template: Record<string, string>; assembled: string }
  diff_summary: string
}

// ==================== API 函数 ====================

export interface StockIndustryResult {
  success: boolean
  industry?: string | null
  name?: string | null
  code?: string
  message?: string
}

export interface IndustryProfileResult {
  success: boolean
  has_profile: boolean
  profile?: {
    id: string
    industry: string
    display_name: string
    analysis_focus: string
    dimension_count: number
  }
  message?: string
}

export interface WorkflowNode {
  node_id: string
  agent_id: string
  label: string
  type: string
  focus: string
}

export interface WorkflowItem {
  id: string
  name: string
  description: string
  agent_count: number
}

export const promptDesignApi = {
  /** 根据股票代码查询行业 */
  getStockIndustry: (symbol: string): Promise<StockIndustryResult> =>
    request.get('/api/v1/prompt-design/stock-industry', { params: { symbol } }),

  /** 检查行业是否有分析配置 */
  checkIndustryProfile: (industry: string): Promise<IndustryProfileResult> =>
    request.get('/api/v1/prompt-design/industry-profile', { params: { industry } }),

  /** 获取分析流程列表 */
  listWorkflows: (): Promise<{ success: boolean; workflows: WorkflowItem[] }> =>
    request.get('/api/v1/prompt-design/workflows'),

  /** 获取流程中的提示节点 */
  getWorkflowNodes: (workflowId: string): Promise<{ success: boolean; workflow_name: string; nodes: WorkflowNode[] }> =>
    request.get('/api/v1/prompt-design/workflow-nodes', { params: { workflow_id: workflowId } }),

  /** 对话式 Prompt 优化 */
  chat: (data: ChatRequest): Promise<ChatResponse> =>
    request.post('/api/v1/prompt-design/chat', data),

  /** 修改前后对比 */
  diff: (data: DiffRequest): Promise<DiffResponse> =>
    request.post('/api/v1/prompt-design/diff', data),
}

export default promptDesignApi
