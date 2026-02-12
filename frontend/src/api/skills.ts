import request from './request'

// Skill 参数
export interface SkillParameter {
  name: string
  type: string
  description: string
  required?: boolean
  default?: any
}

// Skill 返回值
export interface SkillReturns {
  type: string
  description: string
  json_schema?: Record<string, any>
}

// Skill 实现
export interface SkillImplementation {
  type: 'python' | 'http' | 'mcp'
  // python
  module?: string
  function?: string
  // http
  url?: string
  method?: string
  headers?: Record<string, string>
  body_template?: Record<string, any>
  timeout?: number
  // mcp
  server_url?: string
  tool_name?: string
}

// Skill 响应
export interface SkillData {
  id: string
  name: string
  description: string
  version: string
  author: string
  category: string
  tags: string[]
  icon: string
  color: string
  when_to_use: string
  parameters: SkillParameter[]
  returns: SkillReturns | null
  implementation: SkillImplementation | null
  instructions: string
  enabled: boolean
  fc_enabled: boolean
  is_builtin: boolean
  skill_type: string      // knowledge, python, http, mcp
  is_executable: boolean
  created_at: string | null
  updated_at: string | null
}

// Skill 分类统计
export interface SkillCategory {
  id: string
  name: string
  count: number
}

// 创建/更新 Skill 请求
export interface SkillCreateRequest {
  name: string
  description: string
  version?: string
  author?: string
  category?: string
  tags?: string[]
  icon?: string
  color?: string
  when_to_use?: string
  parameters?: SkillParameter[]
  returns?: SkillReturns | null
  implementation?: SkillImplementation | null
  instructions?: string
  enabled?: boolean
  fc_enabled?: boolean
}

// 导入 SKILL.md 请求
export interface SkillImportRequest {
  content: string
}

// 导出 Skill 响应
export interface SkillExportResponse {
  content: string
  filename: string
}

// API 函数
export const skillsApi = {
  // 获取所有 Skill
  listSkills: async (params?: { category?: string; enabled?: boolean; skill_type?: string }): Promise<SkillData[]> => {
    return await request.get<SkillData[]>('/api/skills', { params }) as unknown as SkillData[]
  },

  // 获取 Skill 分类统计
  listCategories: async (): Promise<SkillCategory[]> => {
    return await request.get<SkillCategory[]>('/api/skills/categories') as unknown as SkillCategory[]
  },

  // 创建 Skill
  createSkill: async (data: SkillCreateRequest): Promise<SkillData> => {
    return await request.post<SkillData>('/api/skills', data) as unknown as SkillData
  },

  // 导入 SKILL.md 内容
  importSkill: async (content: string): Promise<SkillData> => {
    return await request.post<SkillData>('/api/skills/import', { content }) as unknown as SkillData
  },

  // 上传 SKILL.md 文件
  importSkillFile: async (file: File): Promise<SkillData> => {
    const formData = new FormData()
    formData.append('file', file)
    return await request.post<SkillData>('/api/skills/import-file', formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    }) as unknown as SkillData
  },

  // 获取 Skill 详情
  getSkill: async (skillName: string): Promise<SkillData> => {
    return await request.get<SkillData>(`/api/skills/${skillName}`) as unknown as SkillData
  },

  // 更新 Skill
  updateSkill: async (skillName: string, data: SkillCreateRequest): Promise<SkillData> => {
    return await request.put<SkillData>(`/api/skills/${skillName}`, data) as unknown as SkillData
  },

  // 删除 Skill
  deleteSkill: async (skillName: string) => {
    return await request.delete(`/api/skills/${skillName}`)
  },

  // 启用/禁用 Skill
  toggleSkill: async (skillName: string, enabled: boolean) => {
    return await request.post(`/api/skills/${skillName}/toggle`, { enabled })
  },

  // 导出 Skill 为 SKILL.md
  exportSkill: async (skillName: string): Promise<SkillExportResponse> => {
    return await request.get<SkillExportResponse>(`/api/skills/${skillName}/export`) as unknown as SkillExportResponse
  },
}

export default skillsApi

