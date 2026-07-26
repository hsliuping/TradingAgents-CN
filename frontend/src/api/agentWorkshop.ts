import request from './request'

export interface WorkflowReference {
  workflow_id: string
  workflow_name: string
  status: string
  updated_at?: string
  referenced_agents: string[]
}

export interface DeleteWithReferencesResult {
  deleted: boolean
  blocked_by_workflows?: boolean
  workflow_references?: WorkflowReference[]
  message?: string
}

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
  progressSteps?: Array<{ text: string; tone?: 'info' | 'success' | 'warning'; meta?: string }>
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
  inferable_gaps?: InferableGapItem[]
  generated_by?: string
  error_message?: string
  raw_response?: string
}

/** 可推断缺口 — 可由已有数据组合推理出，不构成 blocking gap */
export interface InferableGapItem {
  gap: string
  inferable_from: string[]
  inference_approach: string
  confidence: string
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
  builder_contracts?: Record<string, any>
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

export interface AgentExecutionPlanStep {
  step_id: string
  title: string
  objective: string
  suggested_tools: string[]
  expected_evidence: string[]
  failure_signals: string[]
}

export interface AgentExecutionValidationPlan {
  mode: string
  validation_status: string
  rationale: string
  sample_input: Record<string, any>
  execution_steps: AgentExecutionPlanStep[]
  acceptance_checks: string[]
  fallback_rules: string[]
}

export interface AgentAutoResolvedGap {
  job_id?: string
  gap_id?: string
  gap?: string
  skill_tool_id: string
  skill_display_name?: string
  skill_session_id?: string
  resolution_stage?: string
  resolved_at?: string
}

// ================================================================
// v3.6.0 项6：Skill 生成 HITL 审核相关类型
// ================================================================

export interface SkillReviewItem {
  review_id: string
  session_id: string
  tool_id: string
  display_name: string
  description?: string
  source_path: 'agent_workshop' | 'ai_workflow' | string
  source_label?: string
  status: 'pending_review' | 'confirmed_bound' | 'rejected_unbound' | string
  skill_status?: string
  code_snippet?: string
  code_language?: string
  test_summary?: {
    passed?: boolean
    score?: number
    details?: Record<string, any>
    error?: string
  }
  test_passed?: boolean
  test_score?: number
  agent_name?: string
  agent_spec_id?: string
  target_agent_id?: string
  target_agent_name?: string
  workflow_id?: string
  blueprint_summary?: string
  created_at?: string
  updated_at?: string
  review_note?: string
  reviewer?: string
  reviewed_at?: string
  binding_error?: string
  is_expired?: boolean
}

export interface AgentGapResolutionDeadLetterItem {
  job_id: string
  workshop_session_id: string
  spec_id: string
  version_id?: string
  user_id?: string
  job_status: string
  gap_id: string
  description: string
  status: string
  pipeline_stage: string
  pipeline_message: string
  reason_code: string
  reason_message: string
  failed_at: string
  auto_retry_count: number
  max_attempts: number
  retry_count: number
  created_at: string
  updated_at: string
}

export interface AgentGapResolutionDeadLetterGroup {
  reason_code: string
  reason_message: string
  count: number
  job_count: number
  latest_failed_at: string
  job_ids: string[]
}

export interface AgentGapResolutionJobSummary {
  job_id: string
  workshop_session_id: string
  spec_id: string
  status: string
  summary: Record<string, number>
  dead_letter_count: number
  updated_at: string
}

export interface AgentGapResolutionDeadLettersResult {
  total: number
  items: AgentGapResolutionDeadLetterItem[]
  groups: AgentGapResolutionDeadLetterGroup[]
  jobs: AgentGapResolutionJobSummary[]
}

export interface AgentGapResolutionRecoverResult {
  recovered: number
  items: Array<{ job_id: string; gap_id: string; description: string }>
  jobs: Array<{ job_id: string; status: string; summary: Record<string, number>; updated_at: string }>
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
    auto_resolved_gaps?: AgentAutoResolvedGap[]
  }
  prompt_template_ref: Record<string, any>
  required_tools: string[]
  required_capabilities: string[]
  output_schema: Record<string, any>
  evaluation_policy: Record<string, any>
  execution_plan?: AgentExecutionValidationPlan
  debug_result?: Record<string, any>
  runtime_result?: Record<string, any>
  prompt_template_project_memory_binding_summary?: AgentProjectMemoryBindingSummary
  last_evaluation_summary?: AgentEvaluationSummary | null
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
  evidence_bundle?: AgentEvaluationEvidenceBundle | null
  evaluation_summary?: AgentEvaluationSummary
  project_memory_binding_summary?: AgentProjectMemoryBindingSummary
  decision: string
  created_at: string
  updated_at: string
}

export interface AgentProjectMemoryBindingSummary {
  source: string
  enabled: boolean
  valid: boolean
  review_status: string
  summary: string
  system_prompt_present?: boolean | null
  marker_present?: boolean | null
  matched_items: number
  expected_items: number
  missing_item_count: number
  missing_items_preview: string[]
  evaluation_valid?: boolean | null
  evaluation_status?: string | null
  decision?: string | null
}

export interface AgentEvaluationSummary {
  evaluation_id: string
  evaluation_type: string
  decision: string
  overall_score?: number | null
  created_at?: string | null
  evaluation_valid: boolean
  evaluation_status: string
  review_mode?: string
  worker_execution_mode?: string
  content_quality_decision?: string
  publish_readiness_decision?: string
  project_memory_binding: AgentProjectMemoryBindingSummary
}

export interface AgentEvaluationFinding {
  category: string
  severity?: string
  status: string
  title: string
  issue?: string
  evidence: string[]
}

export interface AgentEvaluationLayerSummary {
  score: number
  decision: string
  blockers?: string[]
  warnings?: string[]
}

export interface AgentEvaluationLayeredReview {
  content_quality?: AgentEvaluationLayerSummary
  publish_readiness?: AgentEvaluationLayerSummary
  blockers?: string[]
  warnings?: string[]
}

export interface AgentEvaluationRuntimeSummary {
  has_output_text: boolean
  has_output_payload: boolean
  has_debug_prompt: boolean
  tool_trace_observed: boolean
  required_tools: string[]
  spec_outputs: string[]
}

export interface AgentEvaluationEvidenceArtifact {
  artifact_type: string
  title: string
  path?: string
  content?: string
  metadata?: Record<string, any>
}

export interface AgentEvaluationManualReview {
  review_id: string
  target_path: string
  target_title?: string
  artifact_type?: string
  finding_id?: string
  worker_name?: string
  approved: boolean
  reason: string
  comment?: string
  reviewer?: string
  created_at: string
  updated_at: string
}

export interface AgentEvaluationCandidateFinding {
  finding_id: string
  category: string
  severity?: string
  title: string
  trigger: string
  status: string
}

export interface AgentEvaluationEvidenceTask {
  task_id: string
  finding_id: string
  worker_name: string
  objective: string
  evidence_targets: string[]
  status: string
}

export interface AgentEvaluationWorkerResult {
  task_id: string
  finding_id: string
  worker_name: string
  status: string
  source: string
  summary: string
  evidence: string[]
  artifacts: AgentEvaluationEvidenceArtifact[]
}

export interface AgentEvaluationOrchestrationSummary {
  mode: string
  worker_execution_mode: string
  nanobot_worker_enabled: boolean
  planned_task_count: number
  completed_worker_count: number
}

export interface AgentEvaluationEvidenceBundle {
  review_mode: string
  evaluation_valid: boolean
  evaluation_status: string
  findings: AgentEvaluationFinding[]
  official_issues: string[]
  insufficient_evidence: AgentEvaluationFinding[]
  invalid_reasons: string[]
  runtime_summary: AgentEvaluationRuntimeSummary
  candidate_findings?: AgentEvaluationCandidateFinding[]
  evidence_tasks?: AgentEvaluationEvidenceTask[]
  worker_results?: AgentEvaluationWorkerResult[]
  manual_reviews?: AgentEvaluationManualReview[]
  orchestrator?: AgentEvaluationOrchestrationSummary
}

export const getAgentEvaluationEvidenceBundle = (evaluation?: AgentEvaluationReport | null): AgentEvaluationEvidenceBundle | null => {
  if (!evaluation) return null
  const explicitBundle = evaluation.evidence_bundle
  if (explicitBundle && typeof explicitBundle === 'object') {
    return explicitBundle
  }
  const nestedBundle = evaluation.details?.evidence_bundle
  if (nestedBundle && typeof nestedBundle === 'object') {
    return nestedBundle as AgentEvaluationEvidenceBundle
  }
  return null
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

export interface AgentWorkshopReviewEvaluationArtifactResult {
  evaluation_id: string
  version_id: string
  publish_ready: boolean
  evaluation: AgentEvaluationReport
  manual_review: AgentEvaluationManualReview
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

  listGapResolutionDeadLetters: async (params?: { session_id?: string; spec_id?: string; limit?: number }): Promise<AgentGapResolutionDeadLettersResult> => {
    const res = await request.get<ApiOk<AgentGapResolutionDeadLettersResult>>(`${BASE}/gap-resolution/dead-letters`, { params })
    return (res as any).data
  },

  recoverGapResolutionDeadLetters: async (payload: {
    job_id?: string
    gap_ids?: string[]
    session_id?: string
    spec_id?: string
    reason_code?: string
    recover_all?: boolean
    reason?: string
  }): Promise<AgentGapResolutionRecoverResult> => {
    const res = await request.post<ApiOk<AgentGapResolutionRecoverResult>>(`${BASE}/gap-resolution/dead-letters/recover`, payload)
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

  deleteSpec: async (specId: string, force = false): Promise<DeleteWithReferencesResult & { spec_id: string }> => {
    const res = await request.delete<ApiOk<DeleteWithReferencesResult & { spec_id: string }>>(
      `${BASE}/specs/${specId}`,
      { params: { force } }
    )
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

  deleteVersion: async (versionId: string, force = false): Promise<DeleteWithReferencesResult & {
    deleted: boolean
    version_id: string
    spec_id: string
    current_version_id?: string | null
    remaining_versions: number
  }> => {
    const res = await request.delete<ApiOk<DeleteWithReferencesResult & {
      deleted: boolean
      version_id: string
      spec_id: string
      current_version_id?: string | null
      remaining_versions: number
    }>>(`${BASE}/versions/${versionId}`, { params: { force } })
    return (res as any).data
  },

  getVersionPrompt: async (versionId: string): Promise<AgentWorkshopVersionPrompt> => {
    const res = await request.get<ApiOk<AgentWorkshopVersionPrompt>>(`${BASE}/versions/${versionId}/prompt`)
    return (res as any).data
  },

  publishVersion: async (versionId: string): Promise<{
    version_id: string
    spec_id: string
    status: string
    previous_active_archived: boolean
    workflow_compatibility?: {
      valid: boolean
      errors: string[]
      warnings: string[]
    }
  }> => {
    const res = await request.post<ApiOk<{
      version_id: string
      spec_id: string
      status: string
      previous_active_archived: boolean
      workflow_compatibility?: {
        valid: boolean
        errors: string[]
        warnings: string[]
      }
    }>>(`${BASE}/versions/${versionId}/publish`, {})
    return (res as any).data
  },

  updateVersionMetadata: async (versionId: string, metadata: Record<string, any>): Promise<{
    version_id: string
    updated_fields: string[]
    agent_metadata: Record<string, any>
  }> => {
    const res = await request.put<ApiOk<{
      version_id: string
      updated_fields: string[]
      agent_metadata: Record<string, any>
    }>>(`${BASE}/versions/${versionId}/metadata`, { metadata })
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

  reviewEvaluationArtifact: async (evaluationId: string, payload: {
    target_path: string
    target_title?: string
    artifact_type?: string
    finding_id?: string
    worker_name?: string
    approved: boolean
    reason: string
    comment?: string
    reviewer?: string
  }): Promise<AgentWorkshopReviewEvaluationArtifactResult> => {
    const res = await request.post<ApiOk<AgentWorkshopReviewEvaluationArtifactResult>>(`${BASE}/evaluations/${evaluationId}/manual-reviews`, payload)
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

  updateSpec: async (specId: string, payload: { name?: string; primary_goal?: string }): Promise<{ spec_id: string; updated_fields: string[] }> => {
    const res = await request.put<ApiOk<{ spec_id: string; updated_fields: string[] }>>(`${BASE}/specs/${specId}`, payload)
    return (res as any).data
  },

  getTestProgress: async (versionId: string): Promise<{
    version_id: string
    status: string
    stage: string
    message: string
    started_at?: string
    updated_at?: string
  }> => {
    const res = await request.get<ApiOk<{
      version_id: string
      status: string
      stage: string
      message: string
      started_at?: string
      updated_at?: string
    }>>(`/api/agent-workshop/test-progress/${versionId}`)
    return (res as any).data
  },

  // ================================================================
  // v3.6.0 项6 路径B/C：Skill 生成 HITL 审核接口
  // ================================================================

  listSkillReviews: async (sessionId: string, sourcePath?: string): Promise<{
    session_id: string
    source_path_filter: string | null
    pending_count: number
    items: SkillReviewItem[]
  }> => {
    const res = await request.get<ApiOk<{
      session_id: string
      source_path_filter: string | null
      pending_count: number
      items: SkillReviewItem[]
    }>>(`${BASE}/skill-review/${sessionId}`, { params: { source_path: sourcePath } })
    return (res as any).data
  },

  getSkillReviewDetail: async (sessionId: string, toolId: string): Promise<SkillReviewItem> => {
    const res = await request.get<ApiOk<SkillReviewItem>>(`${BASE}/skill-review/${sessionId}/${toolId}`)
    return (res as any).data
  },

  confirmSkillReview: async (sessionId: string, toolId: string, payload?: { note?: string; user_id?: string }): Promise<{
    review_id: string
    tool_id: string
    status: string
    binding_result?: Record<string, any>
    message?: string
  }> => {
    const res = await request.post<ApiOk<{
      review_id: string
      tool_id: string
      status: string
      binding_result?: Record<string, any>
      message?: string
    }>>(`${BASE}/skill-review/${sessionId}/${toolId}/confirm`, payload || {})
    return (res as any).data
  },

  rejectSkillReview: async (sessionId: string, toolId: string, payload?: { note?: string; user_id?: string }): Promise<{
    review_id: string
    tool_id: string
    status: string
    message?: string
  }> => {
    const res = await request.post<ApiOk<{
      review_id: string
      tool_id: string
      status: string
      message?: string
    }>>(`${BASE}/skill-review/${sessionId}/${toolId}/reject`, payload || {})
    return (res as any).data
  },
}

export default agentWorkshopApi