/**
 * Agent 执行轨迹 API
 *
 * 对应后端 app/routers/execution_trace.py
 * 轨迹存于 MongoDB agent_execution_traces 集合，每次 manager agent 执行时自动写入。
 * 主要入口：任务中心按 task_id 跳转，查看某次分析的所有 Agent 执行轨迹。
 */

import { ApiClient } from './request'

// ==================== 类型定义 ====================

export interface LLMConfigSnapshot {
  model_name?: string | null
  temperature?: number | null
  max_tokens?: number | null
}

export interface TokenUsage {
  input_tokens?: number | null
  output_tokens?: number | null
  total_tokens?: number | null
}

export interface PromptSnapshot {
  system_prompt_hash?: string | null
  system_prompt_length?: number
  user_prompt_hash?: string | null
  user_prompt_length?: number
  // 全文（仅详情接口返回）
  system_prompt_full?: string | null
  user_prompt_full?: string | null
}

export interface InputSnapshot {
  input_keys: string[]
  input_lengths: Record<string, number>
}

export interface OutputSnapshot {
  output_raw_length?: number
  output_raw_preview?: string | null
  // 全文（仅详情接口返回）
  output_raw_full?: string | null
  output_parsed_keys: string[]
  output_parsed_success?: boolean | null
  output_parsed_type?: string | null
}

export interface ValidationResult {
  validation_status?: string | null // "passed" / "failed" / null
  validation_error?: string | null
  validation_details?: Record<string, any> | null
}

export interface ToolCallRecord {
  tool_name: string
  tool_args: Record<string, any>
  success: boolean
  error?: string | null
  result_length: number
  result_preview?: string | null
  duration_ms?: number | null
}

export interface ExecutionTrace {
  trace_id: string
  schema_version?: string
  agent_id: string
  agent_version?: string
  agent_type?: string // "manager" / "trader"
  manager_type?: string | null // "risk" / "research"

  workflow_id?: string | null
  execution_id?: string | null
  task_id?: string | null
  user_id?: string | null
  thread_id?: string | null

  ticker?: string | null
  analysis_date?: string | null

  llm_config?: LLMConfigSnapshot
  inputs?: InputSnapshot
  prompts?: PromptSnapshot
  output?: OutputSnapshot
  tool_calls?: ToolCallRecord[]
  token_usage?: TokenUsage
  validation?: ValidationResult

  success?: boolean
  error_message?: string | null
  error_type?: string | null

  started_at?: string
  finished_at?: string | null
  execution_duration_ms?: number | null
  llm_duration_ms?: number | null
  llm_call_count?: number

  metadata?: Record<string, any>
}

export interface ExecutionTraceQuery {
  task_id?: string
  agent_id?: string
  workflow_id?: string
  validation_status?: string
  success?: boolean
  start_date?: string
  end_date?: string
  skip?: number
  limit?: number
}

export interface ExecutionTraceListResponse {
  success: boolean
  data: {
    items: ExecutionTrace[]
    total: number
  }
  message: string
}

export interface ExecutionTraceDetailResponse {
  success: boolean
  data: ExecutionTrace
  message: string
}

// ==================== API 类 ====================

export class ExecutionTraceApi {
  /**
   * 获取执行轨迹列表（不含全文，点击详情才加载全文）
   */
  static getTraces(params: ExecutionTraceQuery = {}): Promise<ExecutionTraceListResponse> {
    const queryParams = new URLSearchParams()
    if (params.task_id) queryParams.append('task_id', params.task_id)
    if (params.agent_id) queryParams.append('agent_id', params.agent_id)
    if (params.workflow_id) queryParams.append('workflow_id', params.workflow_id)
    if (params.validation_status) queryParams.append('validation_status', params.validation_status)
    if (params.success !== undefined) queryParams.append('success', params.success.toString())
    if (params.start_date) queryParams.append('start_date', params.start_date)
    if (params.end_date) queryParams.append('end_date', params.end_date)
    if (params.skip !== undefined) queryParams.append('skip', params.skip.toString())
    if (params.limit !== undefined) queryParams.append('limit', params.limit.toString())

    const url = `/api/execution-traces${queryParams.toString() ? '?' + queryParams.toString() : ''}`
    return ApiClient.get(url)
  }

  /**
   * 获取单条轨迹详情（含 Prompt 全文、LLM 原始返回全文）
   */
  static getTraceDetail(traceId: string): Promise<ExecutionTraceDetailResponse> {
    return ApiClient.get(`/api/execution-traces/${traceId}`)
  }
}

export default ExecutionTraceApi
