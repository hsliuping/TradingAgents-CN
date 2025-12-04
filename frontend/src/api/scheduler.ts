/**
 * 定时任务管理 API
 */

import { ApiClient } from './request'

export interface Job {
  id: string
  name: string
  next_run_time: string | null
  paused: boolean
  trigger: string
  display_name?: string
  description?: string
  func?: string
  args?: any[]
  kwargs?: Record<string, any>
  misfire_grace_time?: number
  max_instances?: number
}

export interface JobHistory {
  job_id: string
  action: string
  status: string
  error_message?: string
  timestamp: string
}

export interface JobExecution {
  _id: string
  job_id: string
  job_name: string
  status: 'running' | 'success' | 'failed' | 'missed'
  scheduled_time: string
  execution_time?: number
  timestamp: string
  return_value?: string
  error_message?: string
  traceback?: string
  progress?: number
  progress_message?: string
  current_item?: string
  total_items?: number
  processed_items?: number
  updated_at?: string
  is_manual?: boolean
  cancel_requested?: boolean
}

export interface JobExecutionStats {
  total: number
  success: number
  failed: number
  missed: number
  avg_execution_time: number
  last_execution?: {
    status: string
    timestamp: string
    execution_time?: number
  }
}

export interface SchedulerStats {
  total_jobs: number
  running_jobs: number
  paused_jobs: number
  scheduler_running: boolean
  scheduler_state: number
}

export interface SchedulerHealth {
  status: string
  running: boolean
  state: number
  timestamp: string
}

/**
 * 获取所有定时任务列表
 */
export function getJobs() {
  return ApiClient.get<Job[]>('/api/scheduler/jobs')
}

/**
 * 获取任务详情
 */
export function getJobDetail(jobId: string) {
  return ApiClient.get<Job>(`/api/scheduler/jobs/${jobId}`)
}

/**
 * 暂停任务
 */
export function pauseJob(jobId: string) {
  return ApiClient.post<void>(`/api/scheduler/jobs/${jobId}/pause`)
}

/**
 * 恢复任务
 */
export function resumeJob(jobId: string) {
  return ApiClient.post<void>(`/api/scheduler/jobs/${jobId}/resume`)
}

/**
 * 手动触发任务
 */
export function triggerJob(jobId: string, force: boolean = true) {
  return ApiClient.post<void>(`/api/scheduler/jobs/${jobId}/trigger?force=${force}`)
}

/**
 * 获取任务执行历史
 */
export function getJobHistory(jobId: string, params?: { limit?: number; offset?: number }) {
  return ApiClient.get<{
    history: JobHistory[]
    total: number
    limit: number
    offset: number
  }>(`/api/scheduler/jobs/${jobId}/history`, params)
}

/**
 * 获取所有任务执行历史
 */
export function getAllHistory(params?: {
  limit?: number
  offset?: number
  job_id?: string
  status?: string
}) {
  return ApiClient.get<{
    history: JobHistory[]
    total: number
    limit: number
    offset: number
  }>('/api/scheduler/history', params)
}

/**
 * 获取调度器统计信息
 */
export function getSchedulerStats() {
  return ApiClient.get<SchedulerStats>('/api/scheduler/stats')
}

/**
 * 调度器健康检查
 */
export function getSchedulerHealth() {
  return ApiClient.get<SchedulerHealth>('/api/scheduler/health')
}

/**
 * 更新任务元数据（触发器名称和备注）
 */
export function updateJobMetadata(
  jobId: string,
  data: { display_name?: string; description?: string }
) {
  return ApiClient.put<void>(`/api/scheduler/jobs/${jobId}/metadata`, data)
}

/**
 * 获取任务执行历史
 */
export function getJobExecutions(params?: {
  job_id?: string
  status?: 'success' | 'failed' | 'missed' | 'running'
  is_manual?: boolean
  limit?: number
  offset?: number
}) {
  return ApiClient.get<{
    items: JobExecution[]
    total: number
    limit: number
    offset: number
  }>('/api/scheduler/executions', params)
}

/**
 * 获取指定任务的执行历史
 */
export function getSingleJobExecutions(
  jobId: string,
  params?: {
    status?: 'success' | 'failed' | 'missed' | 'running'
    is_manual?: boolean
    limit?: number
    offset?: number
  }
) {
  return ApiClient.get<{
    items: JobExecution[]
    total: number
    limit: number
    offset: number
  }>(`/api/scheduler/jobs/${jobId}/executions`, params)
}

/**
 * 获取任务执行统计信息
 */
export function getJobExecutionStats(jobId: string) {
  return ApiClient.get<JobExecutionStats>(`/api/scheduler/jobs/${jobId}/execution-stats`)
}

/**
 * 取消/终止任务执行
 */
export function cancelExecution(executionId: string) {
  return ApiClient.post<void>(`/api/scheduler/executions/${executionId}/cancel`)
}

/**
 * 标记执行记录为失败
 */
export function markExecutionFailed(executionId: string, reason?: string) {
  return ApiClient.post<void>(`/api/scheduler/executions/${executionId}/mark-failed`, null, {
    params: { reason: reason || '用户手动标记为失败' }
  })
}

/**
 * 删除执行记录
 */
export function deleteExecution(executionId: string) {
  return ApiClient.delete<void>(`/api/scheduler/executions/${executionId}`)
}
