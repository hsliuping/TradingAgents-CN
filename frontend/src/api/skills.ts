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
  script_path?: string
  skill_dir?: string
  // python / http
  timeout?: number
  // http
  url?: string
  method?: string
  headers?: Record<string, string>
  body_template?: Record<string, any>
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

// 测试 Skill 请求
export interface SkillTestRequest {
  skill_name: string
  args: Record<string, any>
  question?: string
  timeout?: number
}

// 测试 Skill 响应
export interface SkillTestResult {
  success: boolean
  result?: any
  error?: string
  execution_time_ms: number
}

// GitHub 仓库中的 Skill
export interface GitHubRepoSkill {
  path: string
  name: string
  url: string
  raw_url: string
  size: number
}

// GitHub 仓库响应
export interface GitHubRepoResponse {
  owner: string
  repo: string
  skills: GitHubRepoSkill[]
  readme?: string
}

// 从 GitHub 导入请求
export interface ImportFromGitHubRequest {
  owner: string
  repo: string
  path: string
  test_args?: Record<string, any>
}

// 导入并测试响应
export interface ImportWithTestResponse {
  skill: SkillData
  test_result?: SkillTestResult
  message: string
}

// Smithery MCP Server
export interface SmitheryServer {
  id: string
  name: string
  description: string
  tools: Record<string, any>[]
  install_command: string
}

// 腾讯 SkillHub 技能
export interface SkillHubSkill {
  skill_id: string
  display_name: string
  description: string
  category: string
  author: string
  downloads: string
  version: string
  needs_api_key: boolean
  ai_score: string
  url: string
  install_command: string
}

// SkillHub 列表响应
export interface SkillHubListResponse {
  total: string
  skills: SkillHubSkill[]
  featured: SkillHubSkill[]
}

// 从 SkillHub 导入请求
export interface ImportFromSkillHubRequest {
  skill_id: string
  test_args?: Record<string, any>
}

// MCP Hub 中国服务器
export interface MCPHubServer {
  server_id: number
  qualified_name: string
  display_name: string
  description: string
  creator: string
  use_count: number
  tag: string
  is_domestic: boolean
  connections: string
  package_url: string
}

// MCP Hub 列表响应
export interface MCPHubListResponse {
  total: number
  page: number
  page_size: number
  servers: MCPHubServer[]
}

// AgentHub 资源项
export interface AgentHubItem {
  id: number
  pkg_id: string
  type: string
  display_name: string
  description: string
  version: string
  origin: string
  source_url: string
  stars: number
  downloads: number
  installs: number
  icon_url: string
}

// AgentHub 搜索响应
export interface AgentHubSearchResponse {
  total: number
  items: AgentHubItem[]
}

// 从 AgentHub 导入请求
export interface ImportFromAgentHubRequest {
  pkg_id: string
  test_args?: Record<string, any>
}

export interface ClawHubSearchResult {
  slug: string
  display_name: string
  summary: string
  version: string
  owner_handle: string
  owner_display_name: string
  canonical_url: string
  score: number
  updated_at?: number
}

export interface ClawHubSearchResponse {
  query: string
  total: number
  results: ClawHubSearchResult[]
}

export interface ClawHubInstallResponse {
  success: boolean
  skill_name: string
  skill_dir: string
  version: string
  has_scripts: boolean
  scripts_count: number
  extracted_files_count: number
  skill_type?: string
  message: string
}

// ZIP / URL 导入响应
export interface ImportZipResponse {
  success: boolean
  skill_name: string
  skill_dir: string
  has_scripts: boolean
  scripts_count: number
  dependencies_installed?: boolean
  dependencies_log?: string
  message: string
}

export interface InstallDepsResponse {
  success: boolean
  installed: boolean
  log: string
  message: string
}

export interface ImportUrlRequest {
  url: string
  name?: string
}

export interface LocalSkillItem {
  name: string
  skill_dir: string
  has_scripts: boolean
  has_skill_md: boolean
  source: string
  version: string
  installed_at: string
  canonical_url: string
  imported_to_db: boolean
}

export interface CredentialRequirement {
  name: string
  description: string
  required: boolean
  config_type: 'env' | 'script_arg'
  config_command: string
  configured: boolean
  masked_value: string
}

export interface CredentialStatusResponse {
  skill_name: string
  required: CredentialRequirement[]
  extra: Array<{ name: string; masked_value: string }>
  all_configured: boolean
  missing_required: string[]
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

  // 从 URL 导入 SKILL.md
  importSkillFromUrl: async (url: string): Promise<SkillData> => {
    return await request.post<SkillData>('/api/skills/import-url', { url }) as unknown as SkillData
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
  deleteSkill: async (skillName: string): Promise<{ success?: boolean; message?: string }> => {
    return await request.delete(`/api/skills/${skillName}`) as unknown as { success?: boolean; message?: string }
  },

  // 启用/禁用 Skill
  toggleSkill: async (skillName: string, enabled: boolean) => {
    return await request.post(`/api/skills/${skillName}/toggle`, { enabled })
  },

  // 导出 Skill 为 SKILL.md
  exportSkill: async (skillName: string): Promise<SkillExportResponse> => {
    return await request.get<SkillExportResponse>(`/api/skills/${skillName}/export`) as unknown as SkillExportResponse
  },

  // 测试 Skill
  testSkill: async (data: SkillTestRequest): Promise<SkillTestResult> => {
    return await request.post<SkillTestResult>('/api/skills/test', data) as unknown as SkillTestResult
  },

  // 获取 GitHub 仓库中的 Skill 列表
  listGitHubRepoSkills: async (owner: string, repo: string): Promise<GitHubRepoResponse> => {
    return await request.get<GitHubRepoResponse>(`/api/skills/github/repo/${owner}/${repo}`) as unknown as GitHubRepoResponse
  },

  // 从 GitHub 导入 Skill
  importFromGitHub: async (data: ImportFromGitHubRequest): Promise<ImportWithTestResponse> => {
    return await request.post<ImportWithTestResponse>('/api/skills/import-github', data) as unknown as ImportWithTestResponse
  },

  // 获取 Smithery MCP Server 列表
  listSmitheryServers: async (): Promise<SmitheryServer[]> => {
    return await request.get<SmitheryServer[]>('/api/skills/smithery/servers') as unknown as SmitheryServer[]
  },

  // 获取腾讯 SkillHub 技能列表
  listSkillHubSkills: async (params?: { keyword?: string }): Promise<SkillHubListResponse> => {
    return await request.get<SkillHubListResponse>('/api/skills/skillhub/skills', { params }) as unknown as SkillHubListResponse
  },

  // 从 SkillHub 导入 Skill
  importFromSkillHub: async (data: ImportFromSkillHubRequest): Promise<ImportWithTestResponse> => {
    return await request.post<ImportWithTestResponse>('/api/skills/import-skillhub', data) as unknown as ImportWithTestResponse
  },

  // 获取 MCP Hub 中国服务器列表
  listMCPHubServers: async (params?: { page?: number; page_size?: number; keyword?: string }): Promise<MCPHubListResponse> => {
    return await request.get<MCPHubListResponse>('/api/skills/mcphub/servers', { params }) as unknown as MCPHubListResponse
  },

  // 搜索 AgentHub 资源
  searchAgentHub: async (params?: { q?: string; type_filter?: string; page?: number; page_size?: number }): Promise<AgentHubSearchResponse> => {
    return await request.get<AgentHubSearchResponse>('/api/skills/agenthub/search', { params }) as unknown as AgentHubSearchResponse
  },

  // 从 AgentHub 导入 Skill
  importFromAgentHub: async (data: ImportFromAgentHubRequest): Promise<ImportWithTestResponse> => {
    return await request.post<ImportWithTestResponse>('/api/skills/import-agenthub', data) as unknown as ImportWithTestResponse
  },

  // 搜索 ClawHub Skill
  searchClawHub: async (params: { q: string; limit?: number }): Promise<ClawHubSearchResponse> => {
    return await request.get<ClawHubSearchResponse>('/api/skills/clawhub/search', { params }) as unknown as ClawHubSearchResponse
  },

  // 从 ClawHub 安装 Skill
  installClawHub: async (data: { slug: string; version?: string; tag?: string }): Promise<ClawHubInstallResponse> => {
    return await request.post<ClawHubInstallResponse>('/api/skills/install-clawhub', data) as unknown as ClawHubInstallResponse
  },

  // 上传 ZIP 文件导入 Skill
  importZip: async (file: File): Promise<ImportZipResponse> => {
    const formData = new FormData()
    formData.append('file', file)
    return await request.post<ImportZipResponse>('/api/skills/import-zip', formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    }) as unknown as ImportZipResponse
  },

  // 通过 URL 下载导入 Skill
  importFromUrl: async (data: ImportUrlRequest): Promise<ImportZipResponse> => {
    return await request.post<ImportZipResponse>('/api/skills/import-url', data) as unknown as ImportZipResponse
  },

  // 手动安装某个 Skill 的依赖（requirements.txt）
  installSkillDeps: async (skillName: string): Promise<InstallDepsResponse> => {
    return await request.post<InstallDepsResponse>(
      `/api/skills/${encodeURIComponent(skillName)}/install-deps`,
      {}
    ) as unknown as InstallDepsResponse
  },

  // 导入本地 Skill 包
  importLocalSkill: async (data: { skill_dir: string }) => {
    return await request.post('/api/skills/import-local', data)
  },

  // 列出本地 Skill 包
  listLocalSkills: async (): Promise<LocalSkillItem[]> => {
    return await request.get<LocalSkillItem[]>('/api/skills/local') as unknown as LocalSkillItem[]
  },

  // 获取 Skill 凭证状态
  getCredentialStatus: async (skillName: string): Promise<CredentialStatusResponse> => {
    return await request.get<CredentialStatusResponse>(`/api/skills/${skillName}/credentials`) as unknown as CredentialStatusResponse
  },

  // 保存 Skill 凭证
  saveCredentials: async (skillName: string, credentials: Record<string, string>) => {
    return await request.post(`/api/skills/${skillName}/credentials`, { credentials })
  },

  // 通过脚本命令配置凭证
  configureCredentialViaScript: async (skillName: string, data: { config_command: string; credential_value: string; script_path?: string; timeout?: number }) => {
    return await request.post(`/api/skills/${skillName}/credentials/configure-script`, data)
  },
}

export default skillsApi

