/**
 * 定时任务相关API
 */
import { ApiClient } from './request'

// 挂起的执行记录
export interface SuspendedExecution {
  execution_id: string
  progress: number
  processed_items?: number
  total_items?: number
  current_item?: string
  started_at?: string
  message?: string
}

export interface RunningExecution {
  execution_id: string
  progress: number
  processed_items?: number
  total_items?: number
  current_item?: string
  started_at?: string
  updated_at?: string
  message?: string
}

// 任务状态
export interface JobStatus {
  id: string  // 后端返回的是 id，不是 job_id
  name: string
  paused: boolean  // 后端返回的是 paused，不是 enabled
  next_run_time?: string
  last_run_time?: string
  trigger?: string
  display_name?: string
  description?: string
  has_suspended_execution?: boolean  // 是否有挂起的执行记录
  suspended_execution?: SuspendedExecution  // 挂起的执行记录详情
  has_running_execution?: boolean
  running_execution?: RunningExecution
}

// 任务进度
export interface JobProgress {
  job_id: string
  execution_id?: string  // 🔥 执行记录ID，用于终止操作
  progress: number
  status: 'running' | 'success' | 'failed' | 'unknown'
  message?: string
  current_item?: string
  total_items?: number
  processed_items?: number
  started_at?: string  // 开始时间
  updated_at?: string   // 更新时间
}

export interface JobHistory {
  [key: string]: any
}

export interface JobExecution {
  [key: string]: any
}

export interface SchedulerStats {
  total_jobs: number
  running_jobs: number
  paused_jobs: number
  [key: string]: any
}

export type Job = JobStatus

// API响应格式
export interface ApiResponse<T = any> {
  success: boolean
  message: string
  data: T
}

/**
 * 获取所有定时任务列表
 */
export const getJobs = (): Promise<ApiResponse<JobStatus[]>> => {
  return ApiClient.get('/api/scheduler/jobs')
}

/**
 * 获取任务详情
 */
export const getJobDetail = (jobId: string): Promise<ApiResponse<JobStatus>> => {
  return ApiClient.get(`/api/scheduler/jobs/${jobId}`)
}

/**
 * 获取任务实时进度
 */
export const getJobProgress = (jobId: string): Promise<ApiResponse<JobProgress>> => {
  return ApiClient.get(`/api/scheduler/jobs/${jobId}/progress`)
}

/**
 * 手动触发任务
 */
export const triggerJob = (jobId: string, options?: {
  force?: boolean
  incremental?: boolean  // 是否增量同步（仅历史数据同步任务有效）
}): Promise<ApiResponse<void>> => {
  const params = new URLSearchParams()
  if (options?.force) {
    params.append('force', 'true')
  }
  if (options?.incremental !== undefined) {
    params.append('incremental', options.incremental ? 'true' : 'false')
  }
  const queryString = params.toString()
  return ApiClient.post(`/api/scheduler/jobs/${jobId}/trigger${queryString ? '?' + queryString : ''}`)
}

/**
 * 暂停任务
 */
export const pauseJob = (jobId: string): Promise<ApiResponse<void>> => {
  return ApiClient.post(`/api/scheduler/jobs/${jobId}/pause`)
}

/**
 * 恢复任务
 */
export const resumeJob = (jobId: string): Promise<ApiResponse<void>> => {
  return ApiClient.post(`/api/scheduler/jobs/${jobId}/resume`)
}

/**
 * 恢复挂起的任务执行（从上次中断的位置继续）
 */
export const resumeSuspendedExecution = (executionId: string): Promise<ApiResponse<void>> => {
  return ApiClient.post(`/api/scheduler/executions/${executionId}/resume`)
}

/**
 * 取消挂起的任务执行记录（用户选择重新开始时使用）
 */
export const cancelSuspendedExecution = (executionId: string): Promise<ApiResponse<void>> => {
  return ApiClient.post(`/api/scheduler/executions/${executionId}/cancel`)
}

/**
 * 获取调度器统计信息
 */
export const getSchedulerStats = (): Promise<ApiResponse<any>> => {
  return ApiClient.get('/api/scheduler/stats')
}

/**
 * 更新任务元数据（显示名称和描述）
 */
export const updateJobMetadata = (
  jobId: string,
  metadata: {
    display_name?: string
    description?: string
  }
): Promise<ApiResponse<void>> => {
  return ApiClient.put(`/api/scheduler/jobs/${jobId}/metadata`, metadata)
}

/**
 * 重新调度任务（修改CRON表达式）
 */
export const rescheduleJob = (
  jobId: string,
  cron: string
): Promise<ApiResponse<void>> => {
  return ApiClient.put(`/api/scheduler/jobs/${jobId}/schedule`, { cron })
}

/**
 * 获取任务执行历史（所有任务）
 */
export const getJobExecutions = (params?: {
  job_id?: string
  status?: string
  is_manual?: boolean
  limit?: number
  offset?: number
}): Promise<ApiResponse<{
  items: any[]
  total: number
  limit: number
  offset: number
}>> => {
  const queryParams = new URLSearchParams()
  if (params?.job_id) queryParams.append('job_id', params.job_id)
  if (params?.status) queryParams.append('status', params.status)
  if (params?.is_manual !== undefined) queryParams.append('is_manual', String(params.is_manual))
  if (params?.limit) queryParams.append('limit', String(params.limit))
  if (params?.offset) queryParams.append('offset', String(params.offset))
  
  const queryString = queryParams.toString()
  return ApiClient.get(`/api/scheduler/executions${queryString ? '?' + queryString : ''}`)
}

/**
 * 获取指定任务的执行历史
 */
export const getSingleJobExecutions = (
  jobId: string,
  params?: {
    status?: string
    is_manual?: boolean
    limit?: number
    offset?: number
  }
): Promise<ApiResponse<{
  items: any[]
  total: number
  limit: number
  offset: number
}>> => {
  const queryParams = new URLSearchParams()
  if (params?.status) queryParams.append('status', params.status)
  if (params?.is_manual !== undefined) queryParams.append('is_manual', String(params.is_manual))
  if (params?.limit) queryParams.append('limit', String(params.limit))
  if (params?.offset) queryParams.append('offset', String(params.offset))
  
  const queryString = queryParams.toString()
  return ApiClient.get(`/api/scheduler/jobs/${jobId}/executions${queryString ? '?' + queryString : ''}`)
}

/**
 * 取消执行记录（通用，包括挂起的执行）
 */
export const cancelExecution = (executionId: string): Promise<ApiResponse<void>> => {
  return ApiClient.post(`/api/scheduler/executions/${executionId}/cancel`)
}

/**
 * 标记执行记录为失败
 */
export const markExecutionFailed = (
  executionId: string,
  reason?: string
): Promise<ApiResponse<void>> => {
  const params = new URLSearchParams()
  if (reason) {
    params.append('reason', reason)
  }
  const queryString = params.toString()
  return ApiClient.post(`/api/scheduler/executions/${executionId}/mark-failed${queryString ? '?' + queryString : ''}`)
}

/**
 * 删除执行记录
 */
export const deleteExecution = (executionId: string): Promise<ApiResponse<void>> => {
  return ApiClient.delete(`/api/scheduler/executions/${executionId}`)
}

/**
 * 重试失败的股票（只重试可重试的错误，跳过无数据的错误）
 * 适用于历史数据同步任务（Tushare/AKShare）
 */
export const retryFailedSymbols = (
  executionId: string,
  options?: {
    start_date?: string  // 开始日期（可选，默认使用原任务的日期）
    end_date?: string     // 结束日期（可选，默认使用原任务的日期）
    period?: 'daily' | 'weekly' | 'monthly'  // 数据周期，默认daily
  }
): Promise<ApiResponse<{
  total_retried: number      // 重试的股票总数
  success_count: number      // 成功数
  error_count: number        // 失败数
  no_data_count: number     // 无数据数（已跳过）
  retryable_errors_count: number  // 可重试错误数
}>> => {
  const params = new URLSearchParams()
  if (options?.start_date) {
    params.append('start_date', options.start_date)
  }
  if (options?.end_date) {
    params.append('end_date', options.end_date)
  }
  if (options?.period) {
    params.append('period', options.period)
  }
  const queryString = params.toString()
  return ApiClient.post(`/api/scheduler/executions/${executionId}/retry-failed${queryString ? '?' + queryString : ''}`)
}
