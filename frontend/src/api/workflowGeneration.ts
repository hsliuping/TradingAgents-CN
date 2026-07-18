import request from './request'

// ==================== 类型定义 ====================

/** 开始会话请求 */
export interface WfStartSessionRequest {
  description: string
  user_id?: string
}

/** 会话响应 */
export interface WfSessionResult {
  session_id: string
  ai_message: string
  status: string
  current_round: number
}

/** 确认创建结果 */
export interface WfConfirmResult {
  status: string
  session_id: string
  workflow_id?: string
  blueprint_summary?: string
  creation_report?: WfCreationReport
  published?: boolean
  error?: string
}

/** 工作流结构信息 */
export interface WfWorkflowStructure {
  name: string
  description: string
  summary: string
  nodes: { id: string; type: string; label: string; agent_id: string; description: string }[]
  edges: { source: string; target: string; label: string }[]
}

/** 创建报告 */
export interface WfCreationReport {
  workflow_structure?: WfWorkflowStructure
  prompts_created: {
    agent_id: string
    template_id: string | null
    new_role: string
    reshaping_direction?: string
    key_focus_areas?: string[]
  }[]
  prompts_default: { agent_id: string; name: string; reason: string }[]
  skills_created: { name?: string; skill_id?: string; status: string; skipped?: boolean }[]
  skills_failed: { name?: string; error?: string; status: string }[]
  bindings_created?: number
  bindings_info?: { skill_name: string; skill_id: string; target_agent_id: string }[]
}

/** 优化结果 */
export interface WfOptimizeResult {
  session_id: string
  ai_message: string
  status: string
  optimization_round: number
}

/** 确认优化结果 */
export interface WfConfirmOptResult {
  status: string
  session_id: string
  workflow_id?: string
  optimization_round?: number
  error?: string
}

/** 发布结果 */
export interface WfPublishResult {
  session_id: string
  workflow_id?: string
  published_prompts: number
  published_skills: number
  published_bindings: number
  workflow_published: boolean
  message: string
}

/** 对话轮次 */
export interface WfConversationRound {
  round_num: number
  user_message: string
  ai_message: string
  phase?: string
  timestamp?: string
}

/** 沟通历史分段 */
export interface WfHistorySection {
  type: 'initial_creation' | 'optimization'
  label: string
  rounds: WfConversationRound[]
  created_at?: string
  feedback?: string
}

/** 沟通历史 */
export interface WfSessionHistory {
  session_id: string
  workflow_id?: string
  sections: WfHistorySection[]
}

/** 会话详情（list 返回的每条记录） */
export interface WfSessionItem {
  session_id: string
  user_id: string
  status: string
  rounds: WfConversationRound[]
  current_round: number
  blueprint?: Record<string, any>
  workflow_id?: string
  creation_report?: WfCreationReport
  created_at: string
  updated_at: string
}

/** 分页会话列表 */
export interface WfPaginatedSessions {
  total: number
  page: number
  page_size: number
  items: WfSessionItem[]
}

/** 标准 API 响应包装 */
interface ApiOk<T> {
  success: boolean
  data: T
  message: string
}

// ==================== API 函数 ====================

const BASE = '/api/workflow-generation'

export const workflowGenerationApi = {
  // ---------- 会话对话 ----------

  /** 开始创建会话 */
  startSession: async (data: WfStartSessionRequest): Promise<WfSessionResult> => {
    const res = await request.post<ApiOk<WfSessionResult>>(`${BASE}/sessions/start`, data)
    return (res as any).data
  },

  /** 回复对话 */
  respondToSession: async (sessionId: string, message: string): Promise<WfSessionResult> => {
    const res = await request.post<ApiOk<WfSessionResult>>(`${BASE}/sessions/${sessionId}/respond`, { message })
    return (res as any).data
  },

  /** 确认方案并创建工作流 */
  confirmAndCreate: async (
    sessionId: string,
    options?: { message?: string; workflow_type?: string },
  ): Promise<WfConfirmResult> => {
    const res = await request.post<ApiOk<WfConfirmResult>>(
      `${BASE}/sessions/${sessionId}/confirm`,
      {
        message: options?.message ?? '确认',
        workflow_type: options?.workflow_type,
      },
    )
    return (res as any).data
  },

  // ---------- 迭代优化 ----------

  /** 提交优化反馈 */
  optimize: async (sessionId: string, feedback: string): Promise<WfOptimizeResult> => {
    const res = await request.post<ApiOk<WfOptimizeResult>>(`${BASE}/sessions/${sessionId}/optimize`, { feedback })
    return (res as any).data
  },

  /** 确认并应用优化 */
  confirmOptimization: async (sessionId: string): Promise<WfConfirmOptResult> => {
    const res = await request.post<ApiOk<WfConfirmOptResult>>(`${BASE}/sessions/${sessionId}/confirm-optimization`, {})
    return (res as any).data
  },

  /** 发布草稿工作流为正式版本 */
  publishSession: async (sessionId: string): Promise<WfPublishResult> => {
    const res = await request.post<ApiOk<WfPublishResult>>(`${BASE}/sessions/${sessionId}/publish`, {})
    return (res as any).data
  },

  // ---------- 会话管理 ----------

  /** 列出会话 */
  listSessions: async (params?: {
    status?: string
    user_id?: string
    page?: number
    page_size?: number
  }): Promise<WfPaginatedSessions> => {
    const res = await request.get<ApiOk<WfPaginatedSessions>>(`${BASE}/sessions`, { params })
    return (res as any).data
  },

  /** 获取会话详情 */
  getSession: async (sessionId: string): Promise<WfSessionItem> => {
    const res = await request.get<ApiOk<WfSessionItem>>(`${BASE}/sessions/${sessionId}`)
    return (res as any).data
  },

  /** 获取完整沟通记录 */
  getSessionHistory: async (sessionId: string): Promise<WfSessionHistory> => {
    const res = await request.get<ApiOk<WfSessionHistory>>(`${BASE}/sessions/${sessionId}/history`)
    return (res as any).data
  },

  /** 删除会话 */
  deleteSession: async (sessionId: string): Promise<any> => {
    const res = await request.delete<ApiOk<any>>(`${BASE}/sessions/${sessionId}`)
    return (res as any).data
  },
}

export default workflowGenerationApi

