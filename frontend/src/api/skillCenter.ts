import request from './request'

export interface SkillSummary {
  skill_id: string
  display_name: string
  description: string
  source: string
  type: string
  status: string
  bindable: boolean
  tool_id?: string
  test_status?: string
  last_tested_at?: string
  bindings: { agents: string[]; workflows: string[] }
  created_at?: string
  updated_at?: string
}

export interface SkillStats {
  total: number
  standard: number
  external: number
  active: number
  bindings: number
}

export const skillCenterApi = {
  listSkills: async (params?: { status?: string; source?: string }): Promise<SkillSummary[]> => {
    return await request.get<SkillSummary[]>('/api/skill-center/skills', { params }) as unknown as SkillSummary[]
  },

  getSkillDetail: async (skillId: string): Promise<SkillSummary> => {
    return await request.get<SkillSummary>(`/api/skill-center/skills/${skillId}`) as unknown as SkillSummary
  },

  testSkill: async (skillId: string): Promise<{ success: boolean; result?: any; error?: string }> => {
    return await request.get(`/api/skill-center/skills/${skillId}/test`) as unknown as { success: boolean; result?: any; error?: string }
  },

  bindSkillToAgent: async (skillId: string, agentId: string): Promise<{ success: boolean; message: string }> => {
    return await request.post(`/api/skill-center/skills/${skillId}/bind/${agentId}`) as unknown as { success: boolean; message: string }
  },

  unbindSkillFromAgent: async (skillId: string, agentId: string): Promise<{ success: boolean; message: string }> => {
    return await request.delete(`/api/skill-center/skills/${skillId}/bind/${agentId}`) as unknown as { success: boolean; message: string }
  },

  getStats: async (): Promise<SkillStats> => {
    return await request.get<SkillStats>('/api/skill-center/stats') as unknown as SkillStats
  },

  // 批量绑定 Skill 到多个 Agent
  batchBindSkill: async (skillId: string, agentIds: string[], priority?: number): Promise<{ success: boolean; bound: string[]; failed: string[]; message: string }> => {
    return await request.post(`/api/skill-center/skills/${skillId}/bind-batch`, { agent_ids: agentIds, priority: priority || 0 }) as unknown as { success: boolean; bound: string[]; failed: string[]; message: string }
  },

  // 获取 Skill 的绑定关系
  getSkillBindings: async (skillId: string): Promise<{ agents: Array<{ agent_id: string; name: string; category: string; priority: number }> }> => {
    return await request.get(`/api/skill-center/skills/${skillId}/bindings`) as unknown as { agents: Array<{ agent_id: string; name: string; category: string; priority: number }> }
  },

  // 查询工具执行日志
  getToolLogs: async (params?: { tool_id?: string; agent_id?: string; analysis_id?: string; success?: boolean; limit?: number }): Promise<{ logs: any[]; count: number }> => {
    return await request.get('/api/skill-center/tool-logs', { params }) as unknown as { logs: any[]; count: number }
  },

  // 工具执行日志统计
  getToolLogStats: async (): Promise<{ total: number; success: number; failed: number; by_tool: any[]; by_agent: any[] }> => {
    return await request.get('/api/skill-center/tool-logs/stats') as unknown as { total: number; success: number; failed: number; by_tool: any[]; by_agent: any[] }
  },
}

export default skillCenterApi