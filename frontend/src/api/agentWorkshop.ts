import request from './request'

export interface AgentWorkshopStartRequest {
  description: string
  user_id?: string
}

export interface AgentWorkshopOverview {
  name: string
  domain: string
  primary_goal: string
  outputs: string[]
  non_goals: string[]
}

export interface AgentWorkshopCapabilitySnapshot {
  builtin_data_tools: string[]
  builtin_analysis_tools: string[]
  external_data_skills: string[]
  external_analysis_skills: string[]
  external_skill_tool_ids: string[]
  valuation_tools: string[]
  valuation_skills: string[]
  summary_text: string
  totals: {
    builtin_tools: number
    external_skills: number
  }
}

export interface AgentWorkshopVersionPrompt {
  version_id: string
  template_id?: string | null
  template_name?: string | null
  status?: string | null
  content?: {
    system_prompt?: string
    user_prompt?: string
    tool_guidance?: string
    analysis_requirements?: string
    output_format?: string
    constraints?: string
  } | null
  message?: string
}

export interface AgentWorkshopSessionResult {
  session_id: string
  spec_id: string
  ai_message: string
  stage: string
  current_round: number
  completeness_score: number
  feasibility_status?: string
  refusal_reason?: string
  pending_questions: string[]
  spec_overview: AgentWorkshopOverview
}

export interface AgentWorkshopMessage {
  role: string
  content: string
  timestamp: string
}

export interface AgentSpecIOField {
  name: string
  type?: string
  required?: boolean
  description?: string
}

export type AgentSpecIOItem = string | AgentSpecIOField

export interface AgentSpec {
  spec_id: string
  name: string
  domain: string
  target_users: string[]
  primary_goal: string
  responsibilities: string[]
  non_goals: string[]
  inputs: AgentSpecIOItem[]
  outputs: AgentSpecIOItem[]
  success_criteria: string[]
  constraints: string[]
  preferred_methods: string[]
  sample_symbols: string[]
  status: string
  source: string
  owner_user_id: string
  latest_session_id?: string
  current_version_id?: string | null
  version_count: number
  created_at: string
  updated_at: string
}

export interface SuggestedToolItem {
  tool_id: string
  description?: string
  why_needed?: string
}

export interface AgentWorkshopGapAnalysis {
  existing_tools: string[]
  suggested_tools: SuggestedToolItem[]
  suggested_capabilities: SuggestedToolItem[]
  manual_dependencies: string[]
  blocking_gaps: string[]
  fallback_strategy: string[]
  build_recommendations: string[]
  notes: string[]
  generated_by?: string
  error_message?: string
  raw_response?: string
}

export interface AgentWorkshopToolSchemaField {
  name: string
  type: string
  required?: boolean
  description: string
}

export interface AgentWorkshopToolingPlanItem {
  tool_id: string
  tool_name: string
  capability_description?: string
  priority: string
  why_needed: string
  solves_gaps: string[]
  fallback_before_ready: string
  dependencies: string[]
  inputs: AgentWorkshopToolSchemaField[]
  outputs: AgentWorkshopToolSchemaField[]
  acceptance_criteria: string[]
}

export interface AgentWorkshopToolingPlan {
  summary: string
  missing_capabilities: string[]
  draft_tools: AgentWorkshopToolingPlanItem[]
  implementation_order: string[]
  notes: string[]
  generated_by?: string
  error_message?: string
  raw_response?: string
}

export interface AgentWorkshopSessionDetail {
  session_id: string
  spec_id: string
  user_id: string
  stage: string
  current_round: number
  messages: AgentWorkshopMessage[]
  current_spec_snapshot: AgentSpec
  pending_questions: string[]
  completeness_score: number
  feasibility_status?: string
  refusal_reason?: string
  gap_report?: AgentWorkshopGapAnalysis | null
  tooling_plan?: AgentWorkshopToolingPlan | null
  created_at: string
  updated_at: string
}

export interface AgentWorkshopPreviewResult {
  spec: AgentSpec
  completeness_score: number
  pending_questions: string[]
  feasibility_status?: string
  refusal_reason?: string
  readiness: string
}

export interface AgentWorkshopGapResult {
  session_id: string
  spec_id: string
  gap_report: AgentWorkshopGapAnalysis
}

export interface AgentWorkshopToolingPlanResult {
  session_id: string
  spec_id: string
  tooling_plan: AgentWorkshopToolingPlan
}

export interface AgentVersion {
  version_id: string
  spec_id: string
  version: number
  status: string
  agent_metadata: Record<string, any> & {
    id?: string
    name?: string
    version?: string
    maintenance_status?: 'maintained' | 'unmaintained'
  }
  prompt_template_ref: Record<string, any>
  required_tools: string[]
  required_capabilities: string[]
  output_schema: Record<string, any>
  evaluation_policy: Record<string, any>
  published_from_session_id?: string | null
  created_at: string
  updated_at: string
}

export interface AgentWorkshopBuildVersionResult {
  session_id: string
  spec_id: string
  version: AgentVersion
}

export interface AgentEvaluationReport {
  evaluation_id: string
  version_id: string
  evaluation_type: string
  sample_set_id?: string | null
  scores: Record<string, any>
  issues: string[]
  recommendations: string[]
  details?: Record<string, any>
  decision: string
  created_at: string
  updated_at: string
}

export interface AgentWorkshopValuationTraceabilityItem {
  label: string
  value: string
  source_type: string
  judgement: string
  evidence_tools?: string[]
  notes?: string[]
}

export interface AgentBenchmarkCase {
  case_id: string
  title: string
  input_payload: Record<string, any>
  expected_outputs: string[]
  required_keywords: string[]
  forbidden_keywords: string[]
  expected_methods: string[]
}

export interface AgentBenchmarkSampleSet {
  sample_set_id: string
  spec_id: string
  name: string
  domain: string
  description: string
  cases: AgentBenchmarkCase[]
  created_at: string
  updated_at: string
}

export interface AgentWorkshopEvaluateVersionResult {
  version_id: string
  evaluation: AgentEvaluationReport
}

export interface AgentWorkshopDebugVersionResult {
  version_id: string
  spec_id: string
  symbol: string
  analysis_date: string
  report: string
  report_length: number
  runtime_agent_id: string
  output_field?: string
  raw_result?: Record<string, any>
  debug_prompt?: {
    system_prompt?: string
    user_prompt?: string
    llm_final_response?: string
    response_type?: string
    tool_mode?: boolean
    tool_trace?: Array<{
      tool_name?: string
      tool_args?: Record<string, any>
      success?: boolean
      result_preview?: string
      result_length?: number
    }>
  }
  template?: {
    template_id?: string
    template_name?: string
  }
  metadata?: {
    agent_id?: string
    agent_name?: string
    maintenance_status?: 'maintained' | 'unmaintained'
    required_tools?: string[]
    user_goal?: string
  }
}

export interface AgentWorkshopIterateVersionResult {
  source_version_id: string
  session_id: string
  spec_id: string
  ai_message: string
}

export interface PaginatedAgentWorkshopSessions {
  total: number
  page: number
  page_size: number
  items: AgentWorkshopSessionDetail[]
}

export interface PaginatedAgentSpecs {
  total: number
  page: number
  page_size: number
  items: AgentSpec[]
}

export interface PaginatedAgentVersions {
  total: number
  page: number
  page_size: number
  items: AgentVersion[]
}

export interface PaginatedAgentEvaluations {
  total: number
  page: number
  page_size: number
  items: AgentEvaluationReport[]
}

export interface AgentSampleSetListResult {
  spec_id: string
  items: AgentBenchmarkSampleSet[]
}

interface ApiOk<T> {
  success: boolean
  data: T
  message: string
}

const BASE = '/api/agent-workshop'

export const agentWorkshopApi = {
  startSession: async (data: AgentWorkshopStartRequest): Promise<AgentWorkshopSessionResult> => {
    const res = await request.post<ApiOk<AgentWorkshopSessionResult>>(`${BASE}/sessions/start`, data)
    return (res as any).data
  },

  respondToSession: async (sessionId: string, message: string): Promise<AgentWorkshopSessionResult> => {
    const res = await request.post<ApiOk<AgentWorkshopSessionResult>>(`${BASE}/sessions/${sessionId}/respond`, { message })
    return (res as any).data
  },

  previewSpec: async (sessionId: string, message: string = '确认'): Promise<AgentWorkshopPreviewResult> => {
    const res = await request.post<ApiOk<AgentWorkshopPreviewResult>>(`${BASE}/sessions/${sessionId}/preview-spec`, { message })
    return (res as any).data
  },

  analyzeGaps: async (sessionId: string): Promise<AgentWorkshopGapResult> => {
    const res = await request.post<ApiOk<AgentWorkshopGapResult>>(`${BASE}/sessions/${sessionId}/analyze-gaps`, {})
    return (res as any).data
  },

  buildVersion: async (sessionId: string): Promise<AgentWorkshopBuildVersionResult> => {
    const res = await request.post<ApiOk<AgentWorkshopBuildVersionResult>>(`${BASE}/sessions/${sessionId}/build-version`, {})
    return (res as any).data
  },

  generateToolingPlan: async (sessionId: string): Promise<AgentWorkshopToolingPlanResult> => {
    const res = await request.post<ApiOk<AgentWorkshopToolingPlanResult>>(`${BASE}/sessions/${sessionId}/generate-tooling-plan`, {})
    return (res as any).data
  },

  listSessions: async (params?: { stage?: string; user_id?: string; page?: number; page_size?: number }): Promise<PaginatedAgentWorkshopSessions> => {
    const res = await request.get<ApiOk<PaginatedAgentWorkshopSessions>>(`${BASE}/sessions`, { params })
    return (res as any).data
  },

  getCapabilitySnapshot: async (): Promise<AgentWorkshopCapabilitySnapshot> => {
    const res = await request.get<ApiOk<AgentWorkshopCapabilitySnapshot>>(`${BASE}/capability-snapshot`)
    return (res as any).data
  },

  getSession: async (sessionId: string): Promise<AgentWorkshopSessionDetail> => {
    const res = await request.get<ApiOk<AgentWorkshopSessionDetail>>(`${BASE}/sessions/${sessionId}`)
    return (res as any).data
  },

  deleteSession: async (sessionId: string): Promise<{ deleted: boolean }> => {
    const res = await request.delete<ApiOk<{ deleted: boolean }>>(`${BASE}/sessions/${sessionId}`)
    return (res as any).data
  },

  listSpecs: async (params?: { status?: string; user_id?: string; page?: number; page_size?: number }): Promise<PaginatedAgentSpecs> => {
    const res = await request.get<ApiOk<PaginatedAgentSpecs>>(`${BASE}/specs`, { params })
    return (res as any).data
  },

  getSpec: async (specId: string): Promise<AgentSpec> => {
    const res = await request.get<ApiOk<AgentSpec>>(`${BASE}/specs/${specId}`)
    return (res as any).data
  },

  deleteSpec: async (specId: string): Promise<{ deleted: boolean; spec_id: string }> => {
    const res = await request.delete<ApiOk<{ deleted: boolean; spec_id: string }>>(`${BASE}/specs/${specId}`)
    return (res as any).data
  },

  listVersions: async (params?: { spec_id?: string; status?: string; page?: number; page_size?: number }): Promise<PaginatedAgentVersions> => {
    const res = await request.get<ApiOk<PaginatedAgentVersions>>(`${BASE}/versions`, { params })
    return (res as any).data
  },

  getVersion: async (versionId: string): Promise<AgentVersion> => {
    const res = await request.get<ApiOk<AgentVersion>>(`${BASE}/versions/${versionId}`)
    return (res as any).data
  },

  getVersionPrompt: async (versionId: string): Promise<AgentWorkshopVersionPrompt> => {
    const res = await request.get<ApiOk<AgentWorkshopVersionPrompt>>(`${BASE}/versions/${versionId}/prompt`)
    return (res as any).data
  },

  evaluateVersion: async (versionId: string, payload?: {
    evaluation_type?: string
    sample_set_id?: string
    user_feedback?: string
    benchmark_outputs?: Array<{ case_id: string; output_text?: string; output_payload?: Record<string, any> }>
    runtime_result?: Record<string, any>
  }): Promise<AgentWorkshopEvaluateVersionResult> => {
    const res = await request.post<ApiOk<AgentWorkshopEvaluateVersionResult>>(`${BASE}/versions/${versionId}/evaluate`, payload || {})
    return (res as any).data
  },

  debugVersion: async (versionId: string, payload: {
    llm: {
      provider: string
      model: string
      temperature?: number
      max_tokens?: number
      backend_url?: string
      api_key?: string
    }
    stock: {
      symbol: string
      market_type?: string
      analysis_date?: string
    }
    user_goal?: string
    prompt_overrides?: Record<string, any>
  }): Promise<AgentWorkshopDebugVersionResult> => {
    const res = await request.post<ApiOk<AgentWorkshopDebugVersionResult>>(
      `${BASE}/versions/${versionId}/debug`,
      payload,
      {
        timeout: 15 * 60 * 1000,
        retryCount: 0,
      } as any,
    )
    return (res as any).data
  },

  listEvaluations: async (versionId: string, params?: { page?: number; page_size?: number }): Promise<PaginatedAgentEvaluations> => {
    const res = await request.get<ApiOk<PaginatedAgentEvaluations>>(`${BASE}/versions/${versionId}/evaluations`, { params })
    return (res as any).data
  },

  iterateVersion: async (versionId: string, payload?: { feedback?: string }): Promise<AgentWorkshopIterateVersionResult> => {
    const res = await request.post<ApiOk<AgentWorkshopIterateVersionResult>>(`${BASE}/versions/${versionId}/iterate`, payload || {})
    return (res as any).data
  },

  listSampleSets: async (specId: string): Promise<AgentSampleSetListResult> => {
    const res = await request.get<ApiOk<AgentSampleSetListResult>>(`${BASE}/specs/${specId}/sample-sets`)
    return (res as any).data
  },
}

export default agentWorkshopApi