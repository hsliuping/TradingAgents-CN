import request from './request'

// ==================== 类型定义 ====================

/** 开始会话请求 */
export interface StartSessionRequest {
  description: string
  user_id?: string
  handoff_context?: SkillHandoffContext
  iterate_skill_id?: string
  provider?: string
  model?: string
  /** 需求分析模型（覆盖系统默认的深度推理模型） */
  reasoning_model?: string
  /** 代码生成模型（覆盖系统默认的编程模型） */
  coding_model?: string
}

export interface SkillHandoffContext {
  source: string
  source_spec_id?: string
  source_name?: string
  target_capability?: string
  handoff_intent?: string
}

/** 可用模型项 */
export interface AvailableModelItem {
  model_name: string
  display_name: string
  provider: string
  enabled: boolean
}

/** 模型列表响应 */
export interface AvailableModelsResult {
  models: AvailableModelItem[]
  default_reasoning_model: string | null
  default_coding_model: string | null
}

/** 会话响应 */
export interface SessionStartResult {
  session_id: string
  ai_message: string
  clarity_level: string
  boundary_check: BoundaryCheck | null
  current_round: number
  expected_rounds: number
}

/** 对话回复结果 */
export interface SessionRespondResult {
  session_id: string
  ai_message: string
  current_round: number
  expected_rounds: number
  is_final_round: boolean
  boundary_check?: BoundaryCheck | null
}

/** 确认生成结果 */
export interface ConfirmResult {
  status: string
  session_id: string
  skill_id: string | null
  spec: Record<string, any> | null
  success: boolean
  total_rounds: number
  total_time: number
  final_score: number | null
  error: string | null
  /** 外部接口预检拦截时的说明 */
  message?: string | null
  interface_preflight?: InterfacePreflightResult | null
}

export interface RepairPlanResult {
  status: string
  session_id: string
  ai_message: string
}

export interface IterationRoundDetail {
  round_number: number
  feedback?: string
  decision?: string
  validation?: {
    passed?: boolean
    errors?: string[]
    warnings?: string[]
  } | null
  sandbox?: {
    success?: boolean
    error?: string | null
    stdout?: string
    stderr?: string
  } | null
  eval_score?: {
    executability?: number
    authenticity?: number
    completeness?: number
    relevance?: number
    format_quality?: number
    total?: number
  } | null
}

export interface PipelineResultDetail {
  success?: boolean
  tool_id?: string
  final_code?: string
  final_metadata?: Record<string, any>
  iterations?: IterationRoundDetail[]
  total_rounds?: number
  total_time?: number
  error?: string | null
}

/** 质量评估实时结果（Judge 白盒评分） */
export interface PipelineEvalResult {
  executability: number
  authenticity: number
  completeness: number
  relevance: number
  format_quality: number
  total: number
  /** 第几轮评估（从 1 开始） */
  round?: number
  /** 是否达到通过阈值 */
  passed: boolean
  /** Judge 专家一句话评语 */
  expert_comment?: string
  /** 业务验收（黑盒）是否通过，agentic 路径下可能返回 */
  business_passed?: boolean
}

/** 边界检测 */
export interface BoundaryCheck {
  within_boundary: boolean
  complexity_score: number
  concerns: string[]
  decomposition_suggestions: string[]
}

export interface SkillAgentUsage {
  version_id: string
  spec_id: string
  version?: number | null
  status: string
  agent_name: string
  published_from_session_id?: string
  updated_at?: string
}

/** 外部 Skill */
export interface ExternalSkill {
  tool_id: string
  display_name: string
  description: string
  category: string
  data_source: string
  parameters: SkillParameter[]
  code: string
  status: string
  source: string
  origin_source?: string
  origin_workshop_session_id?: string
  origin_spec_id?: string
  origin_version_id?: string
  origin_gap_id?: string
  origin_agent_name?: string
  used_by_agents?: SkillAgentUsage[]
  session_id: string
  generation_rounds: number
  generation_time: number
  final_score: number | null
  generation_context?: SkillGenerationRecommendations | null
  created_at: string
  updated_at: string
}

/** Skill 参数 */
export interface SkillParameter {
  name: string
  type: string
  description: string
  required: boolean
  default?: any
}

export interface StockDataCatalogField {
  name: string
  type: string
  description: string
}

export interface StockDataCatalogCollection {
  collection: string
  purpose: string
  preferred_access: string[]
  query_keys: string[]
  notes: string[]
  fields: StockDataCatalogField[]
}

export interface StockDataCatalogResult {
  collections: StockDataCatalogCollection[]
  doc: string
}

export interface ExternalDataSourceCatalogItem {
  source_id: string
  display_name: string
  source_type: string
  markets: string[]
  categories: string[]
  preferred_for: string[]
  interfaces: string[]
  constraints: string[]
  notes: string[]
}

export interface ExternalDataSourceCatalogResult {
  sources: ExternalDataSourceCatalogItem[]
  doc: string
}

export interface SkillGenerationRecommendations {
  category_hint: string
  data_source_hint: string
  stock_collections: string[]
  external_sources: string[]
  /** 目录外数据源名（如 dongchedi）；非空表示需求指定了系统目录之外的来源 */
  unknown_data_source?: string
  /** 需求类型：external_api（外部 API 集成，不评估本地/目录资产）/ local_data（默认） */
  requirement_mode?: 'external_api' | 'local_data'
}

export interface ReconToolTrace {
  tool_name: string
  arguments: Record<string, any>
  success: boolean
  duration_ms: number
  result_preview: string
  error?: string
}

/** 外部接口预检结果（规格确认阶段的连通性验证） */
export interface InterfacePreflightResult {
  /** verified=连通且有数据 / warning=可达但无数据 / failed=不可用 */
  status: 'verified' | 'warning' | 'failed'
  message: string
  url?: string
  http_status?: number
  data_items?: number
  sample_fields?: string[]
  /** 差分测试：实测被接口忽略的参数（传入与否返回相同数据，须本地过滤） */
  ignored_params?: string[]
  /** 差分测试：实测会改变接口返回的业务参数（服务端过滤疑似生效，可拼 URL） */
  server_filter_params?: string[]
  /** 实测验证可用的查询参数（用户 URL 文档化查询参数） */
  probed_params?: Record<string, any>
  checked_at?: string
}

export interface ImplementationFactReportView {
  task_summary: string
  recommended_strategy: string
  available_helpers: Array<{ module: string; name: string; reason?: string; signature?: string; data_source_handling?: string }>
  sample_fields: Record<string, string[]>
  validation_checks: Array<{ name: string; description: string; field?: string }>
  notes: string[]
  tool_traces: ReconToolTrace[]
  confidence: number
}

/** 分页列表 */
export interface PaginatedSkills {
  total: number
  page: number
  page_size: number
  items: ExternalSkill[]
}

/** 沙箱测试结果 */
export interface TestResult {
  success: boolean
  output: any
  stdout: string
  stderr: string
  execution_time: number
  error: string | null
}

/** 对话轮次 */
export interface ConversationRound {
  round_number: number
  ai_message: string
  user_message: string
  timestamp: string
}

/** 会话详情 */
export interface SessionDetail {
  session_id: string
  user_id: string
  status: string
  rounds: ConversationRound[]
  current_round: number
  clarity_level: string | null
  boundary_check: BoundaryCheck | null
  handoff_context?: SkillHandoffContext | null
  spec: Record<string, any> | null
  fact_report?: ImplementationFactReportView | null
  spec_confirmed: boolean
  recommendations?: SkillGenerationRecommendations | null
  pipeline_result: Record<string, any> | null
  pipeline_stage?: string
  pipeline_message?: string
  pipeline_iteration?: number
  pipeline_progress?: number
  /** 代码生成的实时思考过程（reasoning_content 尾部片段） */
  pipeline_thinking?: string
  /** 最近一轮质量评估结果（Judge 评分，评估完成即出现） */
  pipeline_eval_result?: PipelineEvalResult | null
  pipeline_details?: Array<{
    stage: string
    message: string
    iteration: number
    progress: number
    timestamp?: string
    eval_result?: PipelineEvalResult
  }>
  created_at: string
  updated_at: string
}

/** 优化结果 */
export interface OptimizeResult {
  status: string
  skill_id: string
  optimize_session_id: string
  success: boolean
  version: number
  total_rounds: number
  total_time: number
  final_score: number | null
  generation_context?: SkillGenerationRecommendations | null
  error: string | null
}

/** 沟通历史分段（创建/优化） */
export interface HistorySection {
  type: 'creation' | 'optimize'
  label: string
  session_id: string
  rounds: ConversationRound[]
  created_at: string
  feedback?: string
}

/** Skill 完整沟通历史 */
export interface SkillHistory {
  skill_id: string
  display_name: string
  sections: HistorySection[]
}

/** 标准 API 响应包装 */
interface ApiOk<T> {
  success: boolean
  data: T
  message: string
}

// ==================== API 函数 ====================

const BASE = '/api/skill-generation'

// LLM 慢接口专用配置：
// - 超时提高到 20 分钟：需求对话/规格生成涉及多次 LLM 调用，可能超过全局默认 600s，
//   超时截断会导致后端还在跑、前端却已报错（旧会话即因此出现连环重发）
// - retryCount: 0 禁止超时自动重发：这些 POST 非幂等（会新建会话/推进轮次/触发生成），
//   自动重发会在后端堆积重复的长耗时任务并触发 LLM 限流
const SLOW_LLM_OP_CONFIG = { timeout: 1200000, retryCount: 0 }

export const skillGenerationApi = {
  // ---------- 模型选择 ----------

  /** 获取 Skill 生成可用的模型列表（用于下拉选择） */
  listAvailableModels: async (): Promise<AvailableModelsResult> => {
    const res = await request.get<ApiOk<AvailableModelsResult>>(`${BASE}/models`)
    return (res as any).data
  },

  /** 获取股票数据集合目录 */
  getStockDataCatalog: async (): Promise<StockDataCatalogResult> => {
    const res = await request.get<ApiOk<StockDataCatalogResult>>(`${BASE}/catalog/stock-data`)
    return (res as any).data
  },

  /** 获取外部接口与数据源目录 */
  getExternalDataSourceCatalog: async (): Promise<ExternalDataSourceCatalogResult> => {
    const res = await request.get<ApiOk<ExternalDataSourceCatalogResult>>(`${BASE}/catalog/external-data-sources`)
    return (res as any).data
  },

  // ---------- 需求沟通 ----------

  /** 开始创建会话 */
  startSession: async (data: StartSessionRequest): Promise<SessionStartResult> => {
    const res = await request.post<ApiOk<SessionStartResult>>(`${BASE}/sessions/start`, data, SLOW_LLM_OP_CONFIG)
    return (res as any).data
  },

  /** 回复对话 */
  respondToSession: async (sessionId: string, message: string): Promise<SessionRespondResult> => {
    const res = await request.post<ApiOk<SessionRespondResult>>(`${BASE}/sessions/${sessionId}/respond`, { message }, SLOW_LLM_OP_CONFIG)
    return (res as any).data
  },

  /** 预览规格（不执行管线），用于规格确认步骤 */
  previewSpec: async (sessionId: string, message: string = '确认'): Promise<{ spec: Record<string, any>; recommendations?: SkillGenerationRecommendations | null; fact_report?: ImplementationFactReportView | null; interface_preflight?: InterfacePreflightResult | null; upgrade_change_points?: string[] | null }> => {
    const res = await request.post<ApiOk<{ spec: Record<string, any>; recommendations?: SkillGenerationRecommendations | null; fact_report?: ImplementationFactReportView | null; interface_preflight?: InterfacePreflightResult | null; upgrade_change_points?: string[] | null }>>(`${BASE}/sessions/${sessionId}/preview-spec`, { message }, SLOW_LLM_OP_CONFIG)
    return (res as any).data
  },

  /** 确认规格并生成（异步，返回 generating 后需轮询 getSession 获取最终结果） */
  confirmSpec: async (sessionId: string, message: string = '确认', codegenTimeout?: number): Promise<ConfirmResult> => {
    const res = await request.post<ApiOk<ConfirmResult>>(`${BASE}/sessions/${sessionId}/confirm`, { message, codegen_timeout: codegenTimeout ?? null }, SLOW_LLM_OP_CONFIG)
    return (res as any).data
  },

  /** 先让 AI 解释它理解到的问题和修正计划 */
  previewRepairSession: async (sessionId: string, feedback: string): Promise<RepairPlanResult> => {
    const res = await request.post<ApiOk<RepairPlanResult>>(`${BASE}/sessions/${sessionId}/repair-plan`, { feedback }, SLOW_LLM_OP_CONFIG)
    return (res as any).data
  },

  /** 当修正计划确认后，再真正重新生成 */
  repairSession: async (sessionId: string, feedback: string, repairPlan: string = '', codegenTimeout?: number): Promise<ConfirmResult> => {
    const res = await request.post<ApiOk<ConfirmResult>>(`${BASE}/sessions/${sessionId}/repair`, { feedback, repair_plan: repairPlan, codegen_timeout: codegenTimeout ?? null }, SLOW_LLM_OP_CONFIG)
    return (res as any).data
  },

  /** 列出会话（草稿/未完成） */
  listSessions: async (params?: {
    status?: string
    user_id?: string
    page?: number
    page_size?: number
  }): Promise<{ total: number; page: number; page_size: number; items: SessionDetail[] }> => {
    const res = await request.get<ApiOk<any>>(`${BASE}/sessions`, { params })
    return (res as any).data
  },

  /** 获取会话详情（包含对话轮次） */
  getSession: async (sessionId: string): Promise<SessionDetail> => {
    const res = await request.get<ApiOk<SessionDetail>>(`${BASE}/sessions/${sessionId}`)
    return (res as any).data
  },

  /** 删除草稿会话 */
  deleteSession: async (sessionId: string): Promise<any> => {
    const res = await request.delete<ApiOk<any>>(`${BASE}/sessions/${sessionId}`)
    return (res as any).data
  },

  // ---------- Skill 管理 ----------

  /** 列出外部 Skill */
  listSkills: async (params?: { category?: string; status?: string; source?: string; page?: number; page_size?: number }): Promise<PaginatedSkills> => {
    const res = await request.get<ApiOk<PaginatedSkills>>(`${BASE}/skills`, { params })
    return (res as any).data
  },

  /** 获取 Skill 详情 */
  getSkill: async (skillId: string): Promise<ExternalSkill> => {
    const res = await request.get<ApiOk<ExternalSkill>>(`${BASE}/skills/${skillId}`)
    return (res as any).data
  },

  /** 查看 Skill 源代码 */
  getSkillCode: async (skillId: string): Promise<{ tool_id: string; code: string }> => {
    const res = await request.get<ApiOk<{ tool_id: string; code: string }>>(`${BASE}/skills/${skillId}/code`)
    return (res as any).data
  },

  /** 获取 Skill 完整沟通历史（创建 + 所有优化） */
  getSkillHistory: async (skillId: string): Promise<SkillHistory> => {
    const res = await request.get<ApiOk<SkillHistory>>(`${BASE}/skills/${skillId}/history`)
    return (res as any).data
  },

  /** 更新 Skill 状态 */
  updateSkillStatus: async (skillId: string, status: string): Promise<any> => {
    const res = await request.put<ApiOk<any>>(`${BASE}/skills/${skillId}/status`, { status })
    return (res as any).data
  },

  /** 更新 Skill 展示名称与功能说明 */
  updateSkillInfo: async (
    skillId: string,
    displayName: string,
    description: string,
  ): Promise<{ tool_id: string; display_name: string; description: string }> => {
    const res = await request.put<ApiOk<any>>(`${BASE}/skills/${skillId}/info`, {
      display_name: displayName,
      description: description,
    })
    return (res as any).data
  },

  /** 删除 Skill */
  deleteSkill: async (skillId: string): Promise<any> => {
    const res = await request.delete<ApiOk<any>>(`${BASE}/skills/${skillId}`)
    return (res as any).data
  },

  /** 测试 Skill */
  testSkill: async (skillId: string, args?: Record<string, any>): Promise<TestResult> => {
    const res = await request.post<ApiOk<TestResult>>(`${BASE}/skills/${skillId}/test`, { args: args || {} })
    return (res as any).data
  },

  /** 优化 Skill */
  optimizeSkill: async (skillId: string, feedback: string): Promise<OptimizeResult> => {
    const res = await request.post<ApiOk<OptimizeResult>>(`${BASE}/skills/${skillId}/optimize`, { feedback })
    return (res as any).data
  },
}

export default skillGenerationApi

