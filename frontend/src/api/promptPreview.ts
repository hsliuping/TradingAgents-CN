import request from './request'

// ==================== 类型定义 ====================

export interface PromptPreviewRequest {
  agent_type: string
  agent_name: string
  analysis_type?: 'general' | 'industry' | 'stock'
  industry?: string
  stock_symbol?: string
  task_description?: string
  include_capability?: boolean
}

export interface PromptPreviewResponse {
  final_prompt: string
  sections: Record<string, string>
  sources: Record<string, string>
  template_id: string
  profile_used: {
    industry?: string
    stock_symbol?: string
    industry_profile_found: boolean
    stock_profile_found: boolean
  }
  capability_gaps: string[]
}

export interface IndustryItem {
  industry: string
  display_name: string
  analysis_focus: string
}

export interface AgentItem {
  agent_type: string
  agent_name: string
  template_count: number
}

// ==================== API 函数 ====================

export const promptPreviewApi = {
  /** 预览组装后的最终 Prompt */
  assemble: (data: PromptPreviewRequest): Promise<PromptPreviewResponse> =>
    request.post('/api/v1/prompt-preview/assemble', data),

  /** 获取行业列表 */
  listIndustries: (): Promise<{ industries: IndustryItem[] }> =>
    request.get('/api/v1/prompt-preview/industries'),

  /** 获取 Agent 列表 */
  listAgents: (): Promise<{ agents: AgentItem[] }> =>
    request.get('/api/v1/prompt-preview/agents'),

  /** 获取能力快照 */
  getCapabilitySnapshot: (): Promise<{
    success: boolean
    snapshot: {
      builtin_sources: Array<{ key: string; label: string; description: string }>
      enabled_mcp_servers: Array<{ server_id: string; name: string; tool_count: number }>
      active_skills: Array<{ tool_id: string; name: string; description: string }>
      counts: { builtin_sources: number; enabled_mcp_servers: number; active_skills: number }
    }
  }> => request.get('/api/v1/prompt-preview/capability-snapshot'),
}

export default promptPreviewApi